# Frontend Tasks — County Budget Watchdog

**Focus:** Build a React-based interface allowing ward residents to query various county budgets, view amendments, and subscribe to localized SMS digests.

**Stack:** React.js (Vite), React Router DOM, Vanilla CSS, Axios/Fetch.

---

## 1. Project skeleton & Global Setup

- [ ] Scaffold the React app using Vite (`npm create vite@latest`).
- [ ] Set up the directory structure: `src/components/`, `src/pages/`, `src/services/`, and `src/assets/`.
- [ ] Configure environment variables (e.g., `VITE_API_BASE_URL` in `.env.example`).
- [ ] Implement a core design system in Vanilla CSS. **Requirement:** The UI must feel premium—use vibrant colors, glassmorphism, responsive layouts, and interactive micro-animations instead of a generic MVP look.

## 2. Agent & Q&A Interface (Aligns with Backend Person 2)

- [ ] Write `src/services/agentApi.js`:
  - Connect to `POST /api/ask` with payload `{ "question": str, "ward": str, "lang": "en"|"sw" }`.
  - Connect to `POST /api/agent/chat` for multi-turn sessions proxying to Vertex AI Agent Builder.
- [ ] Build the Chat UI:
  - A friendly, accessible search/chat interface for residents to ask about various county budgets.
  - Handle loading states while Gemini 1.5 Pro generates responses.
  - Render the AI's plain-language answers elegantly.
  - **Citations:** Extract and neatly display citations (e.g., page numbers, sections) returned by the backend so users can verify claims.
  - Include a global Language Toggle to switch between English and Swahili.

## 3. Gazette Amendments Dashboard (Aligns with Backend Person 3)

- [ ] Write `src/services/amendmentsApi.js`:
  - Connect to `GET /api/amendments?ward=X` to fetch recent changes detected by the gazette monitor.
- [ ] Build the Dashboard UI:
  - Create a feed to display budget amendments for a selected ward.
  - Render data points gracefully: `change_summary`, `sector`, `amount_delta`, and `detected_at`.
  - Add interactive filters to allow residents to switch between different wards and view specific local impacts.

## 4. SMS Digest Subscriptions (Aligns with Backend Person 3)

- [ ] Write `src/services/subscribeApi.js`:
  - Connect to `POST /api/subscribe` sending `{ phone, ward, language }`.
  - Connect to `POST /api/unsubscribe` sending `{ phone }`.
- [ ] Build the Landing & Subscription UI:
  - Create a captivating landing page that explains the platform's value.
  - Build a subscription form requesting the user's phone number, ward, and preferred language (en/sw).
  - Add frontend validation for phone numbers (ensuring E.164 format) before submitting to the backend.
  - Provide polished success/error feedback (toast notifications or modals) upon form submission.

## Team Split Recommendation

| Person | Area | Tasks |
|--------|------|-------|
| 1 | Chat & Q&A | Multi-turn chat UI, citation rendering, language toggle, and integrating `/api/ask` & `/api/agent/chat`. |
| 2 | Subscriptions | Landing page, SMS subscription form, frontend E.164 validation, and integrating `/api/subscribe`. |
| 3 | Amendments | Ward selection filters, amendment data cards, and integrating `/api/amendments`. |

## Deliverables

- A fully responsive React SPA.
- Centralized API services mapping exactly to the Flask backend routes.
- High-quality Vanilla CSS styling across the Chat, Subscription, and Dashboard views.
