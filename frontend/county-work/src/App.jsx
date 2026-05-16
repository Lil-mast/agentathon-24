import React, { useState } from 'react';
import './index.css';
import { askBudget, subscribeSMS } from './api';

function App() {
  const [question, setQuestion] = useState('');
  const [ward, setWard] = useState('');
  const [lang, setLang] = useState('en');
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [askError, setAskError] = useState('');

  const [subPhone, setSubPhone] = useState('');
  const [subWard, setSubWard] = useState('');
  const [subLang, setSubLang] = useState('en');
  const [subscribing, setSubscribing] = useState(false);
  const [subStatus, setSubStatus] = useState(null);
  const [subError, setSubError] = useState('');

  async function handleAsk(e) {
    e?.preventDefault();
    const q = question.trim();
    if (!q) return;
    setAsking(true);
    setAskError('');
    setAnswer(null);
    try {
      const result = await askBudget({
        question: q,
        ward: ward.trim() || undefined,
        lang,
      });
      setAnswer(result);
    } catch (err) {
      setAskError(err.message || 'Something went wrong.');
    } finally {
      setAsking(false);
    }
  }

  async function handleSubscribe(e) {
    e.preventDefault();
    setSubscribing(true);
    setSubError('');
    setSubStatus(null);
    try {
      const result = await subscribeSMS({
        phone: subPhone.trim(),
        ward: subWard.trim(),
        language: subLang,
      });
      setSubStatus(result);
      setSubPhone('');
      setSubWard('');
    } catch (err) {
      setSubError(err.message || 'Subscribe failed.');
    } finally {
      setSubscribing(false);
    }
  }

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
          <a href="#ask" className="nav-link">Ask</a>
          <a href="#digest" className="nav-link">SMS Digest</a>
          <a href="#features" className="nav-link">Features</a>
        </div>
        <a href="#ask" className="btn-primary">Get Started</a>
      </nav>

      <main>
        <section className="hero" id="ask">
          <h1>Your County's Budget,<br />Demystified.</h1>
          <p>
            Ask any question about Nairobi's county budget and get a clear, cited answer in plain language.
          </p>

          <form className="search-container" onSubmit={handleAsk}>
            <input
              type="text"
              className="search-input"
              placeholder="e.g. How much was allocated to roads in Kasarani?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={asking}
            />
            <button type="submit" className="btn-primary search-btn" disabled={asking || !question.trim()}>
              {asking ? 'Asking...' : 'Ask AI'}
            </button>
          </form>

          <div className="ask-options">
            <input
              type="text"
              className="filter-input"
              placeholder="Filter by ward (optional)"
              value={ward}
              onChange={(e) => setWard(e.target.value)}
              disabled={asking}
            />
            <select
              className="filter-input"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              disabled={asking}
            >
              <option value="en">English</option>
              <option value="sw">Kiswahili</option>
            </select>
          </div>

          {askError && (
            <div className="answer-panel error glass">
              <strong>Could not answer:</strong> {askError}
            </div>
          )}

          {answer && (
            <article className="answer-panel glass">
              <h2 className="answer-title">Answer</h2>
              <p className="answer-text">{answer.answer}</p>
              {answer.citations?.length > 0 && (
                <div className="citations">
                  <span className="citations-label">Sources</span>
                  <ul>
                    {answer.citations.map((c, i) => (
                      <li key={i}>
                        Page {c.page ?? '?'} {c.section ? `· ${c.section}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="answer-meta">
                {answer.chunks_used ?? 0} excerpts retrieved
                {answer.ward ? ` · ward: ${answer.ward}` : ''}
              </div>
            </article>
          )}
        </section>

        <section className="features" id="features">
          <div className="feature-card glass">
            <div className="feature-icon">✨</div>
            <h3 className="feature-title">Plain Language Q&amp;A</h3>
            <p className="feature-text">
              No more confusing jargon. The AI translates dense PBB lines into clear answers about projects in your ward, with page citations from the source PDF.
            </p>
          </div>

          <div className="feature-card glass">
            <div className="feature-icon">📜</div>
            <h3 className="feature-title">Gazette Monitor</h3>
            <p className="feature-text">
              We continuously scan the Kenya Gazette. If an amendment changes a ward's allocation, it lands in our amendments feed within hours.
            </p>
          </div>

          <div className="feature-card glass">
            <div className="feature-icon">📱</div>
            <h3 className="feature-title">SMS Digests</h3>
            <p className="feature-text">
              No internet? No problem. Subscribe with your phone and ward to get weekly SMS updates on your area's top allocations in English or Swahili.
            </p>
          </div>
        </section>

        <section className="digest" id="digest">
          <h2 className="section-title">Get the weekly SMS digest</h2>
          <p className="section-sub">Enter your phone number and ward; we send a short summary every Monday morning.</p>
          <form className="subscribe-form glass" onSubmit={handleSubscribe}>
            <input
              type="tel"
              className="filter-input"
              placeholder="+2547XXXXXXXX"
              value={subPhone}
              onChange={(e) => setSubPhone(e.target.value)}
              required
              disabled={subscribing}
            />
            <input
              type="text"
              className="filter-input"
              placeholder="Ward (e.g. Kasarani)"
              value={subWard}
              onChange={(e) => setSubWard(e.target.value)}
              required
              disabled={subscribing}
            />
            <select
              className="filter-input"
              value={subLang}
              onChange={(e) => setSubLang(e.target.value)}
              disabled={subscribing}
            >
              <option value="en">English</option>
              <option value="sw">Kiswahili</option>
            </select>
            <button type="submit" className="btn-primary" disabled={subscribing}>
              {subscribing ? 'Subscribing...' : 'Subscribe'}
            </button>
          </form>
          {subStatus && (
            <p className="subscribe-status">
              ✓ Subscribed {subStatus.phone} to {subStatus.ward} ({subStatus.language === 'sw' ? 'Kiswahili' : 'English'}).
            </p>
          )}
          {subError && <p className="subscribe-status error">⚠ {subError}</p>}
        </section>
      </main>
    </div>
  );
}

export default App;
