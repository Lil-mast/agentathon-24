import { useEffect, useState } from 'react';
import './index.css';
import { askBudget, subscribeSMS } from './api';

const impactStats = [
  ['17+', 'budget documents indexed'],
  ['85', 'Nairobi wards covered'],
  ['24/7', 'plain-language budget answers'],
];

const focusAreas = [
  {
    title: 'Ward Allocation Clarity',
    text: "Understand what Nairobi's budget says about roads, markets, health centers, water, and other projects near you.",
  },
  {
    title: 'Cited Public Answers',
    text: 'Every response points back to the source pages so residents can verify the numbers instead of trusting a black box.',
  },
  {
    title: 'Gazette Watch',
    text: 'Track amendments and changes that can shift money after the budget is published.',
  },
  {
    title: 'Offline Civic Access',
    text: 'SMS digests keep residents informed even when they do not have reliable data or a laptop nearby.',
  },
];

const eventCards = [
  ['Budget Q&A Clinic', 'Every Monday', 'Ask about ward projects and get a cited answer in minutes.'],
  ['Gazette Change Brief', 'Weekly watch', 'See which amendments could affect allocations in your area.'],
  ['SMS Resident Digest', 'Monday morning', 'Short, practical updates for residents in English or Kiswahili.'],
];

function App() {
  const [loading, setLoading] = useState(true);
  const [theme, setTheme] = useState(() => {
    const savedTheme = window.localStorage.getItem('wazi-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });
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

  useEffect(() => {
    const timer = window.setTimeout(() => setLoading(false), 1400);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem('wazi-theme', theme);
  }, [theme]);

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
    <>
      {loading && (
        <div className="loading-screen" role="status" aria-live="polite">
          <div className="kenya-flag" aria-hidden="true">
            <span className="flag-black" />
            <span className="flag-white" />
            <span className="flag-red" />
            <span className="flag-white" />
            <span className="flag-green" />
            <span className="flag-shield" />
          </div>
          <p>Loading WaziBudget Kenya</p>
        </div>
      )}

      <div className="app-container">
      <div className="top-strip">
        <span>Nairobi County public budget assistant</span>
        <a href="#digest">Get weekly SMS updates</a>
      </div>

      <nav className="navbar">
        <a href="/" className="logo">
          <span className="logo-mark">WB</span>
          <span>WaziBudget</span>
        </a>
        <div className="nav-links">
          <a href="#ask" className="nav-link">Ask</a>
          <a href="#features" className="nav-link">Features</a>
          <a href="#events" className="nav-link">Updates</a>
          <a href="#digest" className="nav-link">SMS Digest</a>
        </div>
        <div className="nav-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            <span className="theme-toggle-icon" aria-hidden="true">
              {theme === 'dark' ? 'L' : 'D'}
            </span>
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
          <a href="#ask" className="btn-primary nav-cta">Ask the budget</a>
        </div>
      </nav>

      <main>
        <section className="hero" id="ask">
          <div className="hero-copy">
            <span className="eyebrow">Together, we make budgets readable</span>
            <h1>Your County's Budget, Demystified.</h1>
            <p>
              Ask any question about Nairobi's county budget and get a clear, cited answer in plain language.
            </p>
            <div className="hero-actions">
              <a href="#ask-form" className="btn-primary">Ask now</a>
              <a href="#features" className="btn-secondary">See what it tracks</a>
            </div>
          </div>

          <aside className="hero-card glass">
            <span className="hero-card-kicker">Resident desk</span>
            <h2>Find the money behind local promises.</h2>
    
            <div className="hero-card-footer">
              <span>60k+ residents can benefit</span>
              <a href="#digest">Join digest</a>
            </div>
          </aside>

          <div className="stats-row">
            {impactStats.map(([value, label]) => (
              <div className="stat-card" key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>

          <div className="ask-desk glass" id="ask-form">
            <div className="desk-heading">
              <span className="eyebrow">Ask the public record</span>
              <h2>What do you want to know?</h2>
            </div>

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
          <div className="section-heading">
            <span className="eyebrow">Leading the way to clearer budgets</span>
            <h2>Built for residents who need answers, not spreadsheets.</h2>
          </div>

          <div className="feature-grid">
            {focusAreas.map((feature) => (
              <div className="feature-card glass" key={feature.title}>
                <div className="feature-icon" aria-hidden="true" />
                <h3 className="feature-title">{feature.title}</h3>
                <p className="feature-text">{feature.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="contribution-panel">
          <div>
            <span className="eyebrow">Powered by public data</span>
            <h2>County finance should be easy to question.</h2>
            <p>
              WaziBudget turns long PDFs, gazette notices, and budget jargon into answers residents can use in meetings, forums, and everyday decisions.
            </p>
          </div>
          <div className="raised-card">
            <strong>0.00</strong>
            <span>shillings required to ask a question</span>
            <a href="#ask" className="btn-primary">Start asking</a>
          </div>
        </section>

        <section className="events" id="events">
          <div className="section-heading centered">
            <span className="eyebrow">Upcoming civic updates</span>
            <h2>Stay close to the decisions that shape your ward.</h2>
          </div>

          <div className="event-list">
            {eventCards.map(([title, date, text]) => (
              <article className="event-card" key={title}>
                <span>{date}</span>
                <h3>{title}</h3>
                <p>{text}</p>
                <a href="#ask">Open desk</a>
              </article>
            ))}
          </div>
        </section>

        <section className="digest" id="digest">
          <span className="eyebrow">Join the campaign for clarity</span>
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
              Subscribed {subStatus.phone} to {subStatus.ward} ({subStatus.language === 'sw' ? 'Kiswahili' : 'English'}).
            </p>
          )}
          {subError && <p className="subscribe-status error">{subError}</p>}
        </section>
      </main>
      </div>
    </>
  );
}

export default App;
