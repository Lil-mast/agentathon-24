# Backend Tasks — Person 3: Gazette Monitor & SMS Digests

**Focus:** Watch the county gazette for budget amendments and push SMS digests to subscribed residents.

**Stack:** Python, Flask, BigQuery, Gemini 1.5 Pro (for summarization), an SMS provider (Africa's Talking or Twilio), APScheduler / Cloud Scheduler.

---

## 1. Subscriber management

- [ ] Add BigQuery table `subscribers`:
  - `phone, ward, language (en|sw), subscribed_at, active`.
- [ ] Add Flask routes in `app/routes/subscribe.py`:
  - `POST /api/subscribe` — `{ phone, ward, language }`.
  - `POST /api/unsubscribe` — `{ phone }`.
- [ ] Validate phone numbers (E.164) and dedupe.

## 2. Gazette monitor

- [ ] Add `app/services/gazette.py`:
  - `fetch_latest_notices()` — scrape or pull the official Kenya Gazette / county gazette feed.
  - For each notice, store in BigQuery table `gazette_notices`:
    - `notice_id, published_at, title, url, raw_text, hash, processed`.
- [ ] Add `scripts/poll_gazette.py` — runs the fetcher and inserts new notices only (dedupe by hash).
- [ ] Wire it to a scheduler:
  - Dev: APScheduler inside Flask (`app/scheduler.py`).
  - Prod: Cloud Scheduler hitting `POST /internal/poll-gazette`.

## 3. Amendment detection

- [ ] In `app/services/amendments.py`:
  - For each new gazette notice, ask Gemini 1.5 Pro: "Does this notice amend the county budget? If yes, what changed (ward, sector, amount)? Return JSON."
  - Store positive matches in `budget_amendments` table:
    - `amendment_id, notice_id, ward, sector, change_summary, amount_delta, detected_at`.
- [ ] Add `GET /api/amendments?ward=X` so the frontend can show recent changes.

## 4. SMS digest generation

- [ ] In `app/services/digest.py`:
  - For each active subscriber, build a 160-char digest covering:
    - Their ward’s top 3 budget allocations.
    - Any amendments detected in the last 7 days.
  - Use Gemini 1.5 Pro to compress and translate (en/sw) the digest.
- [ ] Add `POST /internal/send-digests`:
  - Loops subscribers, generates per-ward digest, sends via SMS provider.
- [ ] Schedule weekly (e.g. Monday 9am) via Cloud Scheduler.

## 5. SMS provider integration

- [ ] Add `app/services/sms.py` with a thin wrapper:
  - `send_sms(to, message)` using Africa's Talking (preferred for KE) or Twilio.
  - Read API keys from env.
- [ ] Log every send to BigQuery table `sms_log` (`phone, message, status, sent_at`) for audit.

## 6. Inbound SMS Q&A (stretch)

- [ ] Add `POST /api/sms/inbound` webhook:
  - Accept resident questions via SMS.
  - Call Person 2’s `/api/ask` with the resident’s ward.
  - Reply with the trimmed (≤160 chars) answer.

## Deliverables

- Subscriber sign-up endpoints.
- Gazette polling + amendment detection running on a schedule.
- Working weekly SMS digest pipeline with logs in BigQuery.
- (Stretch) Two-way SMS Q&A.
