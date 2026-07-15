"""
Flask backend for the volatility modeling engine.

Endpoints:
    GET  /api/health           - liveness check
    POST /api/fit               - upload CSV, fit + compare GARCH/EGARCH/GJR-GARCH
    POST /api/forecast          - fit a single chosen model and forecast forward
    POST /api/regime            - classify current volatility regime from a fitted series

Designed to run comfortably on a 512MB container:
  - single gunicorn worker (set in Procfile / start command)
  - hard caps on rows / horizon / simulations (see volatility_model.py)
  - explicit gc.collect() after each heavy fit
  - no server-side session state; the frontend holds fit results between calls
"""

import gc
import io
import os

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from volatility_model import (
    MAX_ROWS,
    SUPPORTED_DISTS,
    SUPPORTED_MODELS,
    VolatilityInputError,
    compare_models,
    fit_single_model,
    forecast_volatility,
    generate_signal,
    label_regime,
    parse_price_series,
    prices_to_returns,
    returns_from_prices,
)

app = Flask(__name__)
CORS(app)  # tighten allowed origins once the frontend domain is known

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2MB is plenty for 10k rows of date,price
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def _read_csv_from_request() -> pd.DataFrame:
    """Read an uploaded CSV file from the request, enforcing basic limits."""
    if "file" not in request.files:
        raise VolatilityInputError("No file uploaded (expected form field 'file').")

    file = request.files["file"]
    if file.filename == "":
        raise VolatilityInputError("Empty filename.")

    raw = file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise VolatilityInputError("File too large.")

    try:
        df = pd.read_csv(io.BytesIO(raw), usecols=lambda c: c.lower() in ("date", "price"))
        df.columns = [c.lower() for c in df.columns]
    except Exception as exc:
        raise VolatilityInputError(f"Could not parse CSV: {exc}")

    return df


@app.errorhandler(VolatilityInputError)
def handle_input_error(exc: VolatilityInputError):
    return jsonify({"error": str(exc)}), 400


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/meta", methods=["GET"])
def meta():
    """Expose supported models/distributions/limits for the frontend to render."""
    return jsonify({
        "models": SUPPORTED_MODELS,
        "distributions": list(SUPPORTED_DISTS.keys()),
        "max_rows": MAX_ROWS,
    })


@app.route("/api/fit", methods=["POST"])
def fit():
    """
    Upload a CSV (date, price), fit all supported models with the requested
    distribution, and return a comparison (AIC/BIC ranked) plus each model's
    conditional volatility series and regime label for the best model.
    """
    df = _read_csv_from_request()
    returns = prices_to_returns(df)
    del df

    dist = request.form.get("distribution", "t")
    if dist not in SUPPORTED_DISTS:
        raise VolatilityInputError(f"Unsupported distribution '{dist}'.")

    comparison = compare_models(returns, dist=dist)

    best = next((r for r in comparison["results"] if r.get("model") == comparison["best_model"]), None)
    regime = label_regime(best["conditional_volatility"]) if best else None

    gc.collect()
    return jsonify({
        "n_observations": len(returns),
        "distribution": dist,
        "comparison": comparison,
        "regime": regime,
    })


@app.route("/api/forecast", methods=["POST"])
def forecast():
    """
    Upload a CSV plus a chosen model/distribution/horizon, return a forward
    volatility forecast. Kept as a separate endpoint since simulation-based
    forecasting is heavier than a plain fit.
    """
    df = _read_csv_from_request()
    returns = prices_to_returns(df)
    del df

    model_name = request.form.get("model", "EGARCH")
    dist = request.form.get("distribution", "t")
    horizon = request.form.get("horizon", 10)
    simulations = request.form.get("simulations", 500)

    if model_name not in SUPPORTED_MODELS:
        raise VolatilityInputError(f"Unsupported model '{model_name}'.")

    result = forecast_volatility(returns, model_name, dist,
                                  horizon=horizon, simulations=simulations)
    gc.collect()
    return jsonify(result)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    One-call endpoint for the frontend: upload a CSV, get back everything
    needed to render the page — graph data (dates/prices/conditional
    volatility), a volatility regime label, and an illustrative buy/sell/
    hold/watch signal.

    Only fits the single best-comparing model (fast) rather than the full
    3-model comparison, since the UI only needs one volatility line.
    Use /api/fit instead if you want the full model comparison table.
    """
    df = _read_csv_from_request()
    parsed = parse_price_series(df)
    del df

    dist = request.form.get("distribution", "t")
    if dist not in SUPPORTED_DISTS:
        raise VolatilityInputError(f"Unsupported distribution '{dist}'.")

    # periods_per_year controls annualization of volatility for regime
    # classification: 252 for daily data (default), 52 for weekly, 12 for
    # monthly. Wrong assumption here won't break the model fit, but will
    # skew the calm/elevated/turbulent label and therefore the signal.
    periods_per_year = int(request.form.get("periods_per_year", 252))

    returns = returns_from_prices(parsed["prices"])
    result = fit_single_model(returns, "EGARCH", dist)
    regime = label_regime(result["conditional_volatility"], periods_per_year=periods_per_year)
    signal = generate_signal(parsed["prices"], regime["regime"])

    # Align dates/prices with the conditional volatility series: the first
    # price has no return, so conditional_volatility is one shorter.
    dates = parsed["dates"][1:] if parsed["dates"] else None
    prices_aligned = parsed["prices"][1:]

    gc.collect()
    return jsonify({
        "model": "EGARCH",
        "distribution": dist,
        "n_observations": len(returns),
        "dates": dates,
        "prices": prices_aligned,
        "conditional_volatility": result["conditional_volatility"],
        "regime": regime,
        "signal": signal,
    })


@app.route("/api/regime", methods=["POST"])
def regime():
    """
    Convenience endpoint: fit a single model and return only the regime
    label, for lightweight polling/UI use cases.
    """
    df = _read_csv_from_request()
    returns = prices_to_returns(df)
    del df

    model_name = request.form.get("model", "EGARCH")
    dist = request.form.get("distribution", "t")

    result = fit_single_model(returns, model_name, dist)
    reg = label_regime(result["conditional_volatility"])
    gc.collect()
    return jsonify(reg)


if __name__ == "__main__":
    # Local dev only; Render/production uses gunicorn (see Procfile).
    # Reads $PORT so this still behaves sensibly if ever invoked directly
    # in an environment like Render that injects PORT.
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)