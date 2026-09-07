# Nifty Signal

A private market learning journal for Ravi. Ten daily direction calls, every result kept, and a comparison with simply buying the same stocks. The interface uses plain English and works on desktop and mobile.

**This is a working local research foundation. It does not place orders, generate validated live investment advice, or promise profits. The default history is synthetic and labelled throughout.**

**Public data:** [PUBLIC_DATA.md](PUBLIC_DATA.md) covers Yahoo prices and ET Markets, LiveMint and RBI news without a broker key. Real-data imports have been verified locally; the news learning model is still pending.

**Live hosting:** [DEPLOYMENT.md](DEPLOYMENT.md) covers the GitHub Pages frontend, authenticated backend, Upstox price adapter, persistent scheduler and private Telegram setup. Integration code is provided; external services need your credentials and server before they can run.

**Prediction knowledge:** [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md) defines the planned news, company-event and historical-reaction layer, including how we will test whether it improves the price-only baseline. This layer is not running yet.

## Run it

Requires Python 3.11 or newer and Node 20.19 or newer. Python 3.13 is used in the tested setup. On this Mac, use `/opt/homebrew/bin/python3.13` explicitly; the macOS approval shell may otherwise select Python 3.9.

```bash
cd /Users/ravjoshi/Desktop/codebases/finance-stock-buddy
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd frontend
npm install
npm run build
cd ..
bash scripts/start.sh
```

Open **http://127.0.0.1:8000**. The first startup creates a local SQLite database and deterministic sample history. Later starts keep saved decisions. There is no need for a broker, an API key, a cloud account, or a Telegram bot to explore the app.

`backend/requirements-lock.txt` records the exact Python versions used in local checks. Use it instead of `requirements.txt` to reproduce that environment; use `npm ci` with the checked-in frontend lockfile.

For frontend development, keep the API running and run `npm run dev` in `frontend`. Open http://127.0.0.1:5173. Vite forwards `/api` requests to the backend.

## What works now

| Area | Implemented behaviour |
| --- | --- |
| Today | Honest trust check, five buy/five sell examples, full call drawer, previous results, money comparison, recent winning and losing days |
| Track record | Rolling direction accuracy, predicted vs observed confidence, monthly results, buy/sell and stock/index breakdowns, uncertain miss causes |
| Calls by day | Date navigation, direction and wrong-call filters, immutable details, morning/evening previews |
| Stock lookup | Search, all historical research calls, price with right/wrong dots, money vs simply buying |
| System health | Actual job records, quarantine count, source checks, unconnected-service states, current rule, zero-weight inactive helpers, improvement decisions persisted to the database |
| Scoring | Correct long and short math, constant costs, same-stock comparison, flat/pending states, cumulative results, drawdown, best/worst day |
| Data integrity | UTC-normalized publication and receipt cutoffs, frozen calls and results enforced with database triggers, separate raw and accepted imports |
| Imports | Explicit owner-supplied universe/price CSV and timestamped news JSON, deduplication, price quarantine, 2,000-character news cap |
| Baselines | Fixed 0.53 always-up and five-day momentum predictions stored for every instrument with enough history |
| Optional research | LightGBM walk-forward report with full-session chronological splits; FinBERT CPU function; matched 60-day promotion predicate; atomic token-budget reservation |
| Delivery | Deterministic Telegram-sized templates, preview endpoints, separate opt-in CLI sending to one allowed chat, duplicate-attempt protection |
| Live services | Selectable Yahoo/Upstox quote/candle adapters, public RSS collection, source-specific display snapshots, actual receipt times, exchange-session checks, durable scheduled jobs, bounded retries, verified private-chat delivery |
| Hosting | Pages workflow, sign-in and exact-origin API access, Docker Compose/PostgreSQL, Caddy and systemd templates; infrastructure requires setup |

The current displayed rule **is the five-day momentum baseline**, deliberately. Comparing it with always-up provides a working measurement starting point; it is not an ML model with a demonstrated advantage. All extra AI helpers have zero influence until implemented and validated.

## The scorecard means exactly this

- The amount is **₹1,000 per stock call**, not ₹1,000 shared across ten calls. There can be up to ₹10,000 of daily theoretical exposure.
- Long: `amount × (close − open) / open − costs`.
- Short: `amount × (open − close) / open − costs`. The owner approved this correction to CONTEXT.md.
- The assumed round-trip cost is `amount × 0.0015`. This is a research constant, not a current broker quote. Personal income tax, data subscriptions, and infrastructure bills are excluded.
- Fractions of a share are allowed in this normalized comparison. It does not model executable whole-share sizing, stock borrowing, broker availability, margin, or fills.
- **Stops are informational alert levels.** The score uses open-to-close; daily candles cannot reconstruct the order of intraday target/stop touches or actual fills.
- Indices have direction scores but **no paper money result**. The same indices are excluded from both sides of the monetary comparison. No ETF proxy is silently assumed.
- A price-flat day is labelled Flat and excluded from direction-accuracy denominators; a stock trade still pays the assumed costs.
- Missing closes remain Pending. No zero return or guessed close is substituted.
- The range is a volatility-based research band, not a proven probability interval. Model confidence is explicitly uncalibrated.
- Sample data can never unlock F&O. Live F&O stays locked in this foundation until calibration, comparative profitability, and the full 60-day gate are implemented and validated.

The synthetic fixture intentionally includes losses. It has 24 illustrative instruments and weekday sessions; it is **not** historical Nifty 500 membership or an NSE holiday record. Symbol names and price paths are examples, not verified market data.

## Switching to real observations

Create `.env` from `.env.example`, set `APP_MODE=live`, a strong `OWNER_PASSWORD`, and a **new** database URL. Do not point live mode at the sample database. For SQLite use an absolute path such as `sqlite:////absolute/path/finance-stock-buddy/data/live.db`. For Neon/Supabase use a `postgresql+psycopg://...` URL and their required TLS settings. PostgreSQL support has a generated schema, but the local checks run on SQLite; test the target provider before deployment.

From `backend`:

```bash
../.venv/bin/python -m app.jobs init
../.venv/bin/python -m app.jobs import-universe --file /path/to/universe.csv
../.venv/bin/python -m app.jobs import-prices --file /path/to/prices.csv --source https://your-verified-archive.example/file.csv
../.venv/bin/python -m app.jobs import-news --file /path/to/news.json
../.venv/bin/python -m app.jobs predict
../.venv/bin/python -m app.jobs resolve --date YYYY-MM-DD
../.venv/bin/python -m app.jobs brief --period morning --date YYYY-MM-DD
```

Universe CSV: `symbol,name,sector,kind,member_from,member_to`. Kind is `stock` or `index`. Membership dates must be supplied from verified history; they are not inferred from today's constituents. The initial schema supports one membership interval per instrument; re-entry intervals require an extension before a full Nifty 500 historical study.

Price CSV: `symbol,date,open,high,low,close,volume,published_at`. Dates are ISO dates; publication times must include a timezone. The importer records the **actual receipt time**, so importing an old bar today does not make it available to a historical live forecast. Keep CSV rows chronological. Large unexplained moves are quarantined. The split-adjustment helper is unit-tested, but an authoritative corporate-action reconciliation pipeline is still needed before five-year training.

News JSON: a list of `{ "symbol": "...", "title": "...", "url": "https://...", "published_at": "...+05:30", "body": "..." }`. Its receipt time is also captured independently. Sentiment defaults to neutral until the optional sentiment step is used.

Before scheduling live calls, supply `data/nse-holidays.json` as an object mapping a year to verified NSE holiday dates, e.g. `{ "2026": ["YYYY-MM-DD", "..."] }`. No calendar is bundled as a claimed authoritative list. Unknown years fail closed. Live forecasts reject backdating and execution after 09:00 IST. A day with fewer than five supported calls in either direction fails visibly rather than inventing a direction.

For Telegram, configure the bot token and one chat ID, then explicitly enable `TELEGRAM_ENABLED=true`. Preview first. Only the separate `app.jobs send --period morning|evening` command sends; visiting the website never does. Delivery has not been exercised against an actual bot.

## Optional model research

Install `backend/requirements-ml.txt` only when needed. LightGBM on macOS may require the OpenMP runtime; use its official installation instructions. FinBERT's weights are downloaded only when its function is called, not at startup.

```bash
cd backend
../.venv/bin/python -m app.research --output ../data/research-challenger.json
```

The report requires at least **100 resolved days**: 40 initial training days and 60 subsequent evaluation days. Each evaluation day trains on earlier dates across all stocks; outcomes from the current date never enter training. `--allow-sample` explicitly permits experiments on generated history, but such reports never establish live performance. This job produces a report only, with no automatic replacement. The optional ML dependencies and downloaded models have not been installed or validated in this local build.

## Remaining work from the full brief

The following are **not running** and must not be presented as complete:

1. Production verification of the Upstox adapter/calendar and supplied universe, five-year backfill, full historical constituent membership with re-entries, corporate-action reconciliation, and authoritative exchange archive reconciliation.
2. Global/context feeds, company-event tagging, fundamentals, and scheduled FinBERT sentiment. Public RSS collection is now implemented; it does not yet change predictions.
3. A configured and evaluated LLM provider; strict per-agent JSON validation and provenance; scored helper weights; automatic safe fallback and actual spend accounting. Token reservation and the future writer contract are supplied, but no provider call is active.
4. A trained/calibrated champion, weekly retraining and promotion integrated into daily forecasts, reliable event-conditioned scorecards, and validated confidence thresholds.
5. Deployment of the implemented API/worker schedule, Telegram credentials and actual delivery test, VM provisioning, PostgreSQL startup, private HTTPS, and backups. See DEPLOYMENT.md.
6. F&O analysis after the cash gate passes. **No live-order integration is present or planned for this educational version.**

## Checks

```bash
cd backend
../.venv/bin/python -m pytest -q
cd ../frontend
npm run build
npm run test:e2e
```

Browser checks require Google Chrome and the API at port 8000. They exercise page navigation, saved-call details, date and wrong-call filters, stock search, note previews, and responsive layouts. Screenshots are saved to `data/screenshot-desktop.png` and `data/screenshot-mobile.png`.

Verified locally: **58 backend tests and the two hosted-page browser checks passed after adding public data; the production frontend build passed.** The three original journal browser checks passed in the foundation build. See PUBLIC_DATA.md for real-source verification. The browser checks include a nested Pages path, cross-origin sign-in, authenticated export and stale quote display. Run `.venv/bin/python scripts/check_pages.py` from the root for the two isolated hosted-page checks. The optional ML runtime and PostgreSQL deployment are not covered by those checks.

The frozen ten-day integration fixture expects **−₹150** for the model and **+₹850** for simply buying, with **50 of 100** calls right. This known losing example checks selection, resolution, costs, direction scoring, and message generation through the same functions used by the app.

## Project map

- `CONTEXT.md` — original requirements and approved clarifications.
- `frontend/src/App.tsx`, `styles.css` — all five pages and responsive design.
- `backend/app/engine.py` — cutoff readers, calls, outcomes, P&L and promotion gate.
- `backend/app/analytics.py` — the common source for website scorecards.
- `backend/app/models.py`, `db.py`, `schema.sql` — database and immutability controls.
- `backend/app/ingest.py`, `jobs.py` — explicit import and job boundary.
- `backend/app/learning.py`, `research.py` — optional model research.
- `backend/app/briefs.py`, `telegram_templates.md`, `brief_prompt.md` — messages and future writer contract.
- `deploy/` — reviewable hosting templates; not installed services.

Keep this private. Use `.env` for secrets and never add it to version control. The local server binds to loopback. For remote use, complete authentication and HTTPS setup before exposing it.
