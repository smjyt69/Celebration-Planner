# Celebration Planner

A GenAI-assisted planning assistant for **weddings, birthdays and community events**. Give it your date, guest count, budget and context, and it returns a budget split, a realistic timeline, a vendor checklist with questions to ask, and personalised ideas. You can then ask it follow-up questions in plain language.

## 1. Chosen vertical and persona

**Vertical:** Celebration & Event Planner.

**Persona:** the *first-time organiser*: a family member, host or community volunteer planning an event on a fixed budget, often on short notice and without a professional planner. They need to know *what to book, when, and how much to spend*, and they want the plan to adapt when their situation changes.

## 2. Approach and logic

The design splits the work by what each part is good at:

| Layer | Responsibility | Why |
|---|---|---|
| **Deterministic planning engine** (`planner/engine.py`) | Budget, timeline, vendors, notes, offline Q&A | Money and dates must be exact, explainable and testable. No hallucinated numbers. |
| **GenAI layer** (`planner/llm.py`) | Extra personalised ideas and free-form questions | Open-ended, creative work is where a language model adds value. |
| **Fallback** | If there is no API key or the call fails, the engine answers | The app is always usable; AI is an enhancement, never a single point of failure. |

### Decisions the engine makes from your context

| Context | Decision |
|---|---|
| **Budget per guest** vs. a per-event, per-currency minimum | If too low, the plan is flagged, catering gets priority (money moves from decor and entertainment), and the note says how many guests the budget *does* support. |
| **Venue = home** | Venue share drops to 5%; the freed money goes to catering and decor. The venue vendor is removed. More than 60 guests triggers a capacity warning. |
| **Venue = outdoor** | +3% weather contingency; tent and power-backup vendors added; monsoon / summer-heat advice by month. |
| **Days until the event** vs. the ideal lead time (wedding 270, birthday 45, community 60) | If short, every task's offset is scaled down proportionally so nothing is scheduled in the past. Under 14 days, only the key tasks are kept. |
| **Season** | Peak-wedding-season warning (Nov to Feb): book venues, photographers and caterers first. |
| **Dietary needs** | Added to the caterer's questions and to the ideas (for example, labelling dishes). |
| **Children / senior guests** | Adds a kids' safety host or accessible seating and ramps to the vendor list, plus matching ideas. |
| **Style and interests** | Pick from four style banks; interests become themed ideas (known interests have curated ideas, unknown ones become a themed moment). |

Budget amounts always add up **exactly** to the total: percentages are whole numbers summing to 100, and any rounding remainder goes to the contingency line.

## 3. How the solution works

```
Browser form ──POST /api/plan──▶ validation ──▶ engine ──▶ JSON plan ──▶ accessible UI
                 /api/ideas ───▶ validation ──▶ engine ──▶ (+ LLM ideas if key set)
                 /api/ask ─────▶ validation ──▶ engine ──▶ LLM answer, or offline answer
```

```
planner/
  __init__.py     create_app(): wires settings, LLM client, security, routes and error handlers
  config.py       Settings dataclass, read once from the environment (immutable)
  routes.py       Blueprint: pages, /healthz and the JSON API (thin: validate, call engine, respond)
  security.py     Security headers (CSP etc.) and per-client throttling
  ratelimit.py    Sliding-window RateLimiter (bounded memory)
  validation.py   Strict parsing of every input into an immutable PlanRequest
  engine.py       Pure functions: budget, timeline, vendors, ideas, notes, offline answers
  models.py       TypedDict / NamedTuple shapes for the plan and templates
  data.py         All tunable content: weights, timelines, vendors, idea banks
  llm.py          Optional Anthropic Messages API client (stdlib only, cached, fails safe)
static/           index.html, styles.css, app.js (no inline scripts or styles)
tests/            86 tests: engine, validation, config, rate limiter, LLM client, API, security
wsgi.py           Entry point
pyproject.toml    ruff, mypy and pytest configuration
.github/workflows/ci.yml   Runs the tests on every push; lint and type checks run advisory
```

### Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...                    # optional, enables AI ideas/answers (see .env.example)
python wsgi.py                                         # http://127.0.0.1:5000
```

Without a key, everything works except the AI-written ideas and answers, which fall back to the built-in engine.
Production: `gunicorn wsgi:app` (set `TRUST_PROXY=1` only when behind a reverse proxy you control).

### Deploy on Render

1. Push this repo to GitHub (public, single `main` branch).
2. In Render: **New > Blueprint**, select the repo. `render.yaml` configures everything (free plan, gunicorn, health check at `/healthz`, `TRUST_PROXY=1`).
   Or create a **Web Service** manually: build `pip install -r requirements.txt`, start `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`, and set `TRUST_PROXY=1`.
3. Optional: add `ANTHROPIC_API_KEY` under **Environment** in the dashboard to enable AI answers.
4. Free instances sleep after about 15 minutes idle, so the first request after a pause can take up to a minute.

### Run the tests and checks

```bash
python -m unittest discover -s tests -t .      # no extra packages needed (pytest also works)
pip install -r requirements-dev.txt
ruff check . && mypy                           # style and type checks (config in pyproject.toml)
```

### API

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/plan` | event fields | Full plan (summary, notes, budget, timeline, vendors, ideas) |
| `POST /api/ideas` | event fields | Built-in ideas plus AI ideas when available |
| `POST /api/ask` | event fields + `question` | `{answer, source}` where `source` is `ai` or `offline` |
| `GET /healthz` | n/a | `{"status": "ok"}` |

Event fields: `event_type` (wedding / birthday / community), `event_date` (YYYY-MM-DD), `budget`, `guests`, and optional `title`, `currency` (INR/USD/EUR/GBP), `venue_type` (indoor/outdoor/home), `vibe`, `dietary[]`, `attendees[]`, `interests[]`.

## 4. Quality, security, accessibility

**Security**
- All input validated and normalised server-side (types, ranges, whitelists, ISO-only dates, control characters stripped, lengths capped); errors are reported per field.
- Request bodies capped at 16 KB; per-client rate limits (60/min plan, 10/min for AI endpoints, which cost money); `429` with `Retry-After`.
- Strict CSP (`script-src 'self'`, no `unsafe-inline`), plus `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; API responses are `no-store`.
- Front end builds the DOM with `textContent` only (no HTML strings), and a test enforces that.
- API key comes from the environment, is never logged or returned, and `.env` is git-ignored. The AI endpoint URL is a constant (no SSRF). User text sent to the model is escaped, treated as data, and the system prompt tells the model not to follow instructions inside it.
- Unhandled errors return a generic message; details stay in server logs.

**Efficiency**
- Deterministic engine runs in microseconds with no external calls; the LLM is only used for open-ended asks.
- LLM responses are cached (bounded LRU), prompts send a compact slice of the plan, and token limits are set.
- One dependency (Flask); the repo is a few hundred KB.

**Accessibility**
- Semantic HTML, labelled controls, fieldsets and legends, skip link, one `h1` with a sensible heading order.
- Errors are announced (`role="alert"`), linked to inputs with `aria-describedby` / `aria-invalid`; status and answers use `aria-live`.
- Fully keyboard operable, visible focus rings, 44px touch targets, native `<details>` and `<progress>`.
- Light/dark colour schemes with high-contrast palettes, no colour-only meaning, reduced-motion support, responsive layout and a print stylesheet.

**Testing:** 86 `unittest` cases cover budget invariants (weights and amounts always sum correctly across every event / venue / affordability combination), timeline compression, vendor filtering, validation edge cases, API status codes, rate limiting, security headers, path traversal, prompt-injection handling, LLM failure fallback and caching.

## 5. Assumptions

- **Benchmarks are heuristics.** The minimum spend per guest, budget percentages and lead times in `planner/data.py` are illustrative starting points, not market quotes. They are meant to be tuned.
- **Seasonal advice assumes an Indian climate and wedding calendar** (monsoon June to September, peak wedding season November to February).
- **Amounts are whole currency units**, and the app plans a single event (not multi-day ceremonies).
- **No vendor names, prices or availability are invented.** The vendor list is a checklist of what to ask and agree in writing, not a directory.
- **Rate limiting is in-memory**, which suits a single process; use a shared store if you scale out.
- **Checklist progress is stored in the browser** (`localStorage`) only, so there are no accounts and no personal data stored on the server.
- Plans are guidance; confirm prices and availability with vendors.
