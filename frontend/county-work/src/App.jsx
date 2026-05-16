import React from 'react';
import './index.css';

function App() {
  return (
    <div className="app-container">
      <nav className="navbar">
        <a href="/" className="logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
          WaziBudget
        </a>
        <div className="nav-links">
          <a href="#" className="nav-link">Home</a>
          <a href="#" className="nav-link">Amendments</a>
          <a href="#" className="nav-link">SMS Digest</a>
        </div>
        <button className="btn-primary">Connect</button>
      </nav>

      <main>
        <section className="hero">
          <h1>Your County's Budget,<br />Demystified.</h1>
          <p>
            Ask any question you have about a county budget and get a clear, concise answer in plain language.
          </p>

          <div className="search-container">
            <input
              type="text"
              className="search-input"
              placeholder="Ask about allocations in your ward [name of ward]..."
            />
            <button className="btn-primary search-btn">Ask AI</button>
          </div>
        </section>

        <section className="features">
          <div className="feature-card glass">
            <div className="feature-icon">✨</div>
            <h3 className="feature-title">Plain Language Q&A</h3>
            <p className="feature-text">
              No more confusing financial jargon. Our AI translates complex budget lines into simple, clear answers about your local projects.
            </p>
          </div>

          <div className="feature-card glass">
            <div className="feature-icon">📜</div>
            <h3 className="feature-title">Gazette Monitor</h3>
            <p className="feature-text">
              We continuously scan the official Kenya Gazette. If an amendment affects your ward's budget, you'll see it here instantly.
            </p>
          </div>

          <div className="feature-card glass">
            <div className="feature-icon">📱</div>
            <h3 className="feature-title">SMS Digests</h3>
            <p className="feature-text">
              No internet? No problem. Subscribe to get weekly updates on your ward's top allocations right to your phone in English or Swahili.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
