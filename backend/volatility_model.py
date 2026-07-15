"""
Core volatility modeling logic.

Fits GARCH / EGARCH / GJR-GARCH models on a return series using the `arch`
package, compares them via AIC/BIC, and produces conditional volatility,
forecasts, and a simple volatility regime label.

Kept deliberately light on memory: no caching of intermediate arrays beyond
what's needed for the response, explicit gc.collect() after heavy fits, and
hard caps on input size / forecast horizon / simulation paths so this stays
well within a 512MB free-tier container even at 10,000 input rows.
"""

import gc
import numpy as np
import pandas as pd
from arch import arch_model
from arch.univariate.base import ARCHModelResult

MAX_ROWS = 10_000
MIN_ROWS = 50
MAX_FORECAST_HORIZON = 30
MAX_SIMULATIONS = 1000

SUPPORTED_MODELS = ["GARCH", "EGARCH", "GJR-GARCH"]
SUPPORTED_DISTS = {
    "normal": "normal",
    "t": "t",
    "skewt": "skewt",
}


class VolatilityInputError(ValueError):
    """Raised for bad/oversized input so the route layer can 400 cleanly."""


def parse_price_series(df: pd.DataFrame) -> dict:
    """
    Clean and sort an uploaded date/price dataframe.

    Returns a dict with aligned 'dates' (list of ISO strings, or None if no
    date column was given) and 'prices' (list of floats), after dropping
    invalid rows and enforcing row/positivity limits. This is the single
    place that validates a raw upload, so every endpoint sees the same
    guarantees about the data it's given.
    """
    if "price" not in df.columns:
        raise VolatilityInputError("CSV must contain a 'price' column.")

    if len(df) > MAX_ROWS:
        raise VolatilityInputError(f"Max {MAX_ROWS} rows supported, got {len(df)}.")

    df = df.copy()
    has_dates = "date" in df.columns
    if has_dates:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date")

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"])

    if len(df) < MIN_ROWS:
        raise VolatilityInputError(f"Need at least {MIN_ROWS} valid price rows.")

    if (df["price"] <= 0).any():
        raise VolatilityInputError("Prices must be positive (non-positive values found).")

    dates = df["date"].dt.strftime("%Y-%m-%d").tolist() if has_dates else None
    prices = df["price"].tolist()

    return {"dates": dates, "prices": prices}


def returns_from_prices(prices) -> pd.Series:
    """
    Convert a price series into a percentage log-return series.

    Returns are scaled by 100 (standard practice for arch — keeps the
    optimizer well-conditioned vs. raw decimals).
    """
    prices = pd.Series(prices, dtype=float)
    returns = 100 * np.log(prices / prices.shift(1))
    returns = returns.dropna().reset_index(drop=True)

    if len(returns) < MIN_ROWS:
        raise VolatilityInputError("Not enough valid data points after cleaning.")

    return returns


def prices_to_returns(df: pd.DataFrame) -> pd.Series:
    """Back-compat wrapper: parse a dataframe straight to a return series."""
    parsed = parse_price_series(df)
    return returns_from_prices(parsed["prices"])


def _model_kwargs(model_name: str) -> dict:
    """Map a friendly model name to arch_model's vol/p/o/q kwargs."""
    if model_name == "GARCH":
        return dict(vol="GARCH", p=1, o=0, q=1)
    if model_name == "EGARCH":
        return dict(vol="EGARCH", p=1, o=1, q=1)
    if model_name == "GJR-GARCH":
        return dict(vol="GARCH", p=1, o=1, q=1)  # o>0 on GARCH => GJR-GARCH
    raise VolatilityInputError(f"Unsupported model '{model_name}'.")


def fit_single_model(returns: pd.Series, model_name: str, dist: str) -> dict:
    """Fit one volatility model and return a lightweight result dict."""
    if dist not in SUPPORTED_DISTS:
        raise VolatilityInputError(f"Unsupported distribution '{dist}'.")

    kwargs = _model_kwargs(model_name)
    am = arch_model(returns, mean="Constant", dist=SUPPORTED_DISTS[dist], **kwargs)

    res: ARCHModelResult = am.fit(disp="off", show_warning=False)

    result = {
        "model": model_name,
        "distribution": dist,
        "aic": float(res.aic),
        "bic": float(res.bic),
        "loglikelihood": float(res.loglikelihood),
        "params": {k: float(v) for k, v in res.params.to_dict().items()},
        "conditional_volatility": res.conditional_volatility.tolist(),
    }

    del am, res
    return result


def compare_models(returns: pd.Series, dist: str = "t", models=None) -> dict:
    """
    Fit all requested models on the same series and rank by AIC (lower is
    better). Returns each model's summary plus which one "wins".
    """
    models = models or SUPPORTED_MODELS
    fitted = []
    for name in models:
        try:
            fitted.append(fit_single_model(returns, name, dist))
        except Exception as exc:  # a single model failing shouldn't kill the request
            fitted.append({"model": name, "distribution": dist, "error": str(exc)})
        gc.collect()

    valid = [f for f in fitted if "error" not in f]
    best = min(valid, key=lambda f: f["aic"]) if valid else None

    return {
        "results": fitted,
        "best_model": best["model"] if best else None,
    }


def forecast_volatility(returns: pd.Series, model_name: str, dist: str,
                         horizon: int = 10, simulations: int = 500) -> dict:
    """
    Refit the chosen model and produce a forward volatility forecast.

    Uses simulation-based forecasting (required for EGARCH's asymmetric
    news-impact term) but caps horizon/simulations to bound memory and CPU.
    """
    horizon = min(max(int(horizon), 1), MAX_FORECAST_HORIZON)
    simulations = min(max(int(simulations), 100), MAX_SIMULATIONS)

    kwargs = _model_kwargs(model_name)
    am = arch_model(returns, mean="Constant", dist=SUPPORTED_DISTS.get(dist, "t"), **kwargs)
    res = am.fit(disp="off", show_warning=False)

    fc = res.forecast(horizon=horizon, method="simulation",
                       simulations=simulations, reindex=False)

    variance_path = fc.variance.values[-1]  # last row = forecast from end of sample
    vol_path = np.sqrt(variance_path).tolist()

    out = {
        "model": model_name,
        "distribution": dist,
        "horizon": horizon,
        "forecast_volatility": vol_path,
    }

    del am, res, fc
    gc.collect()
    return out


CALM_ANNUALIZED_PCT = 15.0
ELEVATED_ANNUALIZED_PCT = 30.0


def label_regime(conditional_volatility, periods_per_year: int = 252) -> dict:
    """
    Classify current volatility against fixed, industry-standard annualized
    bands rather than the series' own history.

    An earlier version compared today's volatility to percentiles of the
    same series — but that's relative, so an absolutely calm market could
    still get flagged "turbulent" just for ticking up slightly on its own
    quiet baseline. Absolute annualized bands (roughly: <15% calm, 15-30%
    elevated, >30% turbulent for equities) give a reading that means the
    same thing regardless of how quiet or wild the uploaded series has
    historically been — which is what you want feeding into a signal.
    """
    vol = np.asarray(conditional_volatility, dtype=float)
    recent_daily_pct = float(vol[-1])  # conditional_volatility is already in % (returns were *100)
    annualized_pct = recent_daily_pct * np.sqrt(periods_per_year)

    if annualized_pct < CALM_ANNUALIZED_PCT:
        regime = "calm"
    elif annualized_pct < ELEVATED_ANNUALIZED_PCT:
        regime = "elevated"
    else:
        regime = "turbulent"

    return {
        "regime": regime,
        "recent_daily_volatility_pct": round(recent_daily_pct, 4),
        "annualized_volatility_pct": round(annualized_pct, 2),
        "calm_threshold_pct": CALM_ANNUALIZED_PCT,
        "elevated_threshold_pct": ELEVATED_ANNUALIZED_PCT,
    }


def generate_signal(prices, regime: str, short_window: int = 10, long_window: int = 30) -> dict:
    """
    A simple, transparent trend + volatility-regime heuristic.

    This is NOT investment advice or a real trading strategy — it's an
    illustrative rule for the project: trend direction comes from a
    short-vs-long moving-average crossover, and the volatility regime acts
    as a brake (turbulent conditions downgrade any signal to "hold" since
    confidence in a trend read is lower when volatility is spiking).

    Windows are scaled down automatically for shorter series so this still
    produces a sensible reading on small uploads.
    """
    prices = np.asarray(prices, dtype=float)
    n = len(prices)

    short_window = max(2, min(short_window, n // 4)) if n >= 8 else max(2, n // 2)
    long_window = max(short_window + 1, min(long_window, n // 2)) if n >= 8 else n

    short_ma = prices[-short_window:].mean()
    long_ma = prices[-long_window:].mean()
    trend = "up" if short_ma > long_ma else "down"
    trend_strength_pct = float((short_ma - long_ma) / long_ma * 100)

    if regime == "turbulent":
        signal = "hold"
        reason = "Volatility is in the turbulent regime, so any trend signal is treated as unreliable."
    elif regime == "elevated":
        signal = "hold" if trend == "down" else "watch"
        reason = ("Volatility is elevated with a downward trend — caution advised."
                  if trend == "down" else
                  "Volatility is elevated with an upward trend — worth watching, not yet confirmed.")
    else:  # calm
        signal = "buy" if trend == "up" else "sell"
        reason = (f"Calm volatility with a {trend}ward short/long moving-average crossover "
                   f"({trend_strength_pct:+.2f}%).")

    return {
        "signal": signal,
        "trend": trend,
        "trend_strength_pct": round(trend_strength_pct, 3),
        "regime": regime,
        "reason": reason,
        "disclaimer": "Illustrative heuristic only — not financial advice.",
    }