import React, { useState } from 'react';
import './App.css';
import PillNav from './PillNav';
    import logo from "./assets/react.svg";
import TextPressure from './component/TextPressure';


export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [file, setFile] = useState(null);
  const [dist, setDist] = useState('t');
  const [periods, setPeriods] = useState(252);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files.length > 0) setFile(e.target.files[0]);
  };

  const toggleTheme = () => setIsDarkMode(!isDarkMode);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('distribution', dist);
    formData.append('periods_per_year', periods);

    try {
      const response = await fetch('http://127.0.0.1:5001/api/analyze', {
        method: 'POST',
        body: formData,
      });
      
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("text/html")) {
        const htmlText = await response.text();
        console.error("Received HTML instead of JSON:", htmlText);
        throw new Error(`Server returned an HTML page (Status ${response.status}). Check your Python terminal for crash logs!`);
      }

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to process data');
      }
      
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // 1. Define your Nav Items and tie them to your state logic
  const navItems = [
    { label: 'Home', href: '#home', onClick: (e) => { e.preventDefault(); setActiveTab('home'); } },
    { label: 'About', href: '#about', onClick: (e) => { e.preventDefault(); setActiveTab('about'); } },
    { label: 'Workshop', href: '#workshop', onClick: (e) => { e.preventDefault(); setActiveTab('workshop'); } }
  ];

  return (
    <div className={`app-wrapper ${isDarkMode ? 'dark-theme' : ''}`}>
      <div className="main-canvas">
        
        {/* Decorative CSS Background Shapes */}
        <div className="deco-circle-large"></div>
        <div className="deco-circle-small"></div>

        {/* Inner Padding Wrapper */}
        <div className="canvas-content">
          
          {/* Navigation Container */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '60px', padding: '15px 0', borderBottom: '1px solid var(--border-line)' }}>
            
            <PillNav
              items={navItems}
              activeHref={`#${activeTab}`}
              className="elegant-pill-nav"
              ease="power2.easeOut"
              baseColor="var(--text-teal)" 
              pillColor="transparent" 
              pillTextColor="var(--text-dark)"
              hoveredPillTextColor="var(--bg-canvas)"
              theme={isDarkMode ? "dark" : "light"}
              initialLoadAnimation={false}
            />

            {/* Theme Toggle Button positioned on the far right */}
            <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle Theme">
              {isDarkMode ? '☼' : '☾'}
            </button>
            
          </div>
          
          {/* Content Area */}
          <div className="content-layer">
            
            {/* TAB 1: HOME (Updated with TextPressure) */}
            {activeTab === 'home' && (
              <div className="hero-layout-wide" style={{ margin: '0 auto', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                
                {/* TextPressure Heading Container */}
                <div style={{ 
                      position: 'relative', 
                      height: 'auto', // Auto height to accommodate two lines
                      width: '100%', 
                      display: 'flex', 
                      flexDirection: 'column', // Stack them vertically
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      marginBottom: '20px' 
                  }}>
                    
                    {/* First Line: "Aesthetic" in Teal */}
                    <TextPressure
                      text="Aesthetic"
                      flex={true}
                      alpha={false}
                      stroke={false}
                      width={true}
                      weight={true}
                      italic={true}
                      textColor="#417272" // Hardcoded Teal
                      strokeColor="#417272"
                      minFontSize={80}
                    />
                    
                    {/* Second Line: "Econometrics" in Dark/Light theme default */}
                    <TextPressure
                      text="Econometrics"
                      flex={true}
                      alpha={false}
                      stroke={false}
                      width={true}
                      weight={true}
                      italic={true}
                      textColor={isDarkMode ? "#e8eceb" : "#1d1c1a"} // Theme responsive
                      strokeColor="#417272"
                      minFontSize={80}
                    />
                  </div>

                <p className="subtitle" style={{ maxWidth: '800px', margin: '0 auto 50px auto' }}>
                  We provide the most elegant modeling solutions for your financial time-series data. 
                  Discover the underlying beauty of market dynamics through rigorous, sophisticated volatility analysis.
                </p>

                {/* About Cards */}
                <div className="about-grid" style={{ textAlign: 'left', width: '100%', marginBottom: '60px' }}>
                  <div className="about-card">
                    <h3 className="card-title">Precision Modeling</h3>
                    <p className="card-text">
                      Our proprietary engine strips away the noise of raw market data, revealing the underlying structural breaks and conditional variances.
                    </p>
                  </div>
                  <div className="about-card">
                    <h3 className="card-title">Seamless Experience</h3>
                    <p className="card-text">
                      We have reimagined the user experience, blending high-end aesthetic design with uncompromising mathematical rigor.
                    </p>
                  </div>
                  <div className="about-card">
                    <h3 className="card-title">Actionable Insights</h3>
                    <p className="card-text">
                      Categorize your current volatility into intuitive regimes—Calm, Elevated, or Turbulent—to help guide your strategic positioning.
                    </p>
                  </div>
                </div>

                <button className="primary-btn" onClick={() => setActiveTab('workshop')}>
                  Enter the Workshop
                </button>
              </div>
            )}

            {/* TAB 2: ABOUT */}
            {activeTab === 'about' && (
              <div className="hero-layout-wide">
                <h2>The Science of Beauty & Math</h2>
                <p className="subtitle" style={{ maxWidth: '600px' }}>
                  Underneath our soft exterior lies a rigorous statistical engine. We utilize the ARCH framework to bring clarity to market turbulence.
                </p>
                
                <div className="about-grid">
                  <div className="about-card">
                    <div className="card-icon">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                      </svg>
                    </div>
                    <h3 className="card-title">Asymmetric Smoothing</h3>
                    <p className="card-text">
                      Powered by the EGARCH framework, our engine captures the leverage effect smoothly, ensuring negative market shocks are treated with specialized precision.
                    </p>
                  </div>

                  <div className="about-card">
                    <div className="card-icon">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                      </svg>
                    </div>
                    <h3 className="card-title">Distribution Customization</h3>
                    <p className="card-text">
                      Whether your data fits a standard Gaussian profile or requires the heavy-tailed nourishment of a Student's t-distribution, we adapt to your specific needs.
                    </p>
                  </div>

                  <div className="about-card">
                    <div className="card-icon">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <path d="M3 9h18M9 21V9"/>
                      </svg>
                    </div>
                    <h3 className="card-title">Regime Classification</h3>
                    <p className="card-text">
                      We gracefully categorize your current volatility into Calm, Elevated, or Turbulent states using fixed annualized percentage thresholds for pure clarity.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: WORKSHOP */}
            {activeTab === 'workshop' && (
              <div className="workshop-layout">
                <div className="form-panel">
                  <h2>Analysis Engine</h2>
                  <form onSubmit={handleAnalyze}>
                    <div className="form-group">
                      <label>Historical Data (CSV)</label>
                      <div className="custom-file-upload">
                        <label htmlFor="csv-upload" className="file-label">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" y1="3" x2="12" y2="15"></line>
                          </svg>
                          <span>{file ? file.name : "Browse for CSV file..."}</span>
                        </label>
                        <input id="csv-upload" type="file" accept=".csv" onChange={handleFileChange} />
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Statistical Distribution</label>
                      <div className="custom-select-wrapper">
                        <select value={dist} onChange={(e) => setDist(e.target.value)}>
                          <option value="t">Student's t (Heavy Tails)</option>
                          <option value="normal">Gaussian (Normal)</option>
                          <option value="skewt">Skewed Student's t</option>
                        </select>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Periods Per Year (Annualization)</label>
                      <input type="number" value={periods} onChange={(e) => setPeriods(e.target.value)} className="elegant-input" />
                    </div>

                    <button type="submit" disabled={loading} className="primary-btn" style={{ marginTop: '20px', width: '100%' }}>
                      {loading ? 'Processing...' : 'Run Diagnostics'}
                    </button>

                    {error && <div style={{ color: 'var(--error-red)', marginTop: '15px', textAlign: 'center', fontWeight: '500' }}>{error}</div>}
                  </form>
                </div>

                <div className="results-panel">
                  {result ? (
                    <div>
                      <h3 style={{ fontFamily: 'DM Serif Display', marginTop: 0 }}>Diagnosis Results</h3>
                      
                      <div className="result-row">
                        <span>Volatility Regime</span>
                        <span className="result-value">{result.regime?.regime}</span>
                      </div>
                      <div className="result-row">
                        <span>Market Signal</span>
                        <span className="result-value">{result.signal?.signal}</span>
                      </div>
                      <div className="result-row">
                        <span>Annualized Volatility</span>
                        <span className="result-value">{result.regime?.annualized_volatility_pct}%</span>
                      </div>

                      <p style={{ fontStyle: 'italic', marginTop: '20px', fontSize: '15px', opacity: 0.8 }}>
                        "{result.signal?.reason}"
                      </p>

                      {result.prices && (
                        <table className="elegant-table">
                          <thead>
                            <tr>
                              <th>T-Minus</th>
                              <th>Price</th>
                              <th>Target Volatility</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.prices.slice(-4).map((price, idx) => (
                              <tr key={idx}>
                                <td>{result.dates ? result.dates[result.dates.length - 4 + idx] : `T-${4 - idx}`}</td>
                                <td>${price.toFixed(2)}</td>
                                <td style={{ color: 'var(--text-teal)', fontWeight: '500' }}>
                                  {(result.conditional_volatility[result.conditional_volatility.length - 4 + idx]).toFixed(4)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  ) : (
                    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-teal)', opacity: 0.6 }}>
                      <p style={{ fontFamily: 'DM Serif Display', fontSize: '20px' }}>Awaiting data input...</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Updated Footer Area */}
        <footer className="app-footer">
          <div className="footer-credits">
            
            {/* Amith S */}
            <div className="creator-profile">
              <span className="creator-name">Amith S</span>
              <div className="creator-links">
                <a href="https://github.com/amythology" target="_blank" rel="noreferrer">GitHub</a>
                <span className="link-divider">|</span>
                <a href="https://www.linkedin.com/in/amythologies" target="_blank" rel="noreferrer">LinkedIn</a>
              </div>
            </div>

            {/* Mayoori M Bhat */}
            <div className="creator-profile">
              <span className="creator-name">Mayoori M Bhat</span>
              <div className="creator-links">
                <a href="https://github.com/mayooribhat1506" target="_blank" rel="noreferrer">GitHub</a>
              </div>
            </div>

          </div>

          <div className="footer-text" style={{ marginTop: '30px' }}>
            © 2026 Aesthetic Econometrics. All rights reserved.
          </div>
        </footer>

      </div>
    </div>
  );
}