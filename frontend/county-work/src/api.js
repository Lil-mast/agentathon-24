// Same-origin calls; nginx (prod) and the Vite dev proxy both forward
// /api and /health to the Flask backend, so no base URL is needed here.

async function postJSON(path, body) {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const message = data?.error || `Request failed (${resp.status})`;
    throw new Error(message);
  }
  return data;
}

async function getJSON(path) {
  const resp = await fetch(path);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const message = data?.error || `Request failed (${resp.status})`;
    throw new Error(message);
  }
  return data;
}

export function askBudget({ question, ward, lang = 'en' }) {
  return postJSON('/api/ask', { question, ward, lang });
}

export function subscribeSMS({ phone, ward, language = 'en' }) {
  return postJSON('/api/subscribe', { phone, ward, language });
}

export function listAmendments({ ward } = {}) {
  const qs = ward ? `?ward=${encodeURIComponent(ward)}` : '';
  return getJSON(`/api/amendments${qs}`);
}

export function checkHealth() {
  return getJSON('/health');
}
