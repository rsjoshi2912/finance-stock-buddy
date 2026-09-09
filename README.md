# Nifty Signal

A private market learning journal for Ravi. Up to ten available daily direction calls, every result kept, and a comparison with simply buying the same stocks. Fewer calls and one-sided days are valid. The interface uses plain English and works on desktop and mobile.

**This is a working local research foundation. It does not place orders, generate validated live investment advice, or promise profits. The default history is synthetic and labelled throughout.**

**Public data:** [PUBLIC_DATA.md](PUBLIC_DATA.md) covers Yahoo prices and ET Markets, LiveMint and RBI news without a broker key. Real-data imports have been verified locally. Collected articles that name a tracked company now get a frozen event note and, later, a measured reaction; a news learning model that could change a call is still pending.

**Live hosting:** [DEPLOYMENT.md](DEPLOYMENT.md) covers the GitHub Pages frontend, authenticated backend, Upstox price adapter, persistent scheduler, on-demand prices/news refresh and private Telegram setup. Oracle and Pages were deployed and Telegram configured in the prior checkpoints. See [MEMORY.md](MEMORY.md) for the last recorded deployed revision, current local changes and checks; a local build does not update the running site.

**Prediction knowledge:** [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md) defines the news, company-event and historical-reaction layer, including how we will test whether it improves the price-only baseline. Its record-keeping half (event notes, reactions, comparable history) is running; the evaluated challenger that could earn influence is not.

**Resume work:** [MEMORY.md](MEMORY.md) records the latest handoff; [AGENTS.md](AGENTS.md) is the agent entry point. [INDEX_PLAN.md](INDEX_PLAN.md) covers the index paper-signal rule, option-feed gates and remaining validation.

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
| Today | Available calls first, actual Buy/Sell counts and stock allocation, ranges and alerts, current or previous results, compact market prices/news; one sample/paper label |
| Track record | Net result and same-stock comparison, cumulative chart and monthly table; accuracy, rule-score and direction/instrument breakdowns on demand |
| Calls by day | Date navigation, direction and wrong-call filters, immutable details; collapsed morning/evening previews |
| Stock lookup | Search, price with right/wrong dots, company news and measured reactions; historical calls, comparisons and provenance on demand |
| Index lab | Current Nifty/Bank Nifty checks, option/feed/expiry status, optional one-lot calculator, method/source details and saved assessments |
| System health | Actual job records, quarantine/cutoff checks, feed and scheduler status, notification delivery; method and queued experiments on demand, without inactive AI/F&O cards |
| Scoring | Correct long and short math, constant costs, same-stock comparison, flat/pending states, cumulative results, drawdown, best/worst day |
| Data integrity | UTC-normalized publication and receipt cutoffs, frozen calls and results enforced with database triggers, separate raw and accepted imports |
| Imports | Explicit owner-supplied universe/price CSV and timestamped news JSON, deduplication, price quarantine, 2,000-character news cap |
| Baselines | Fixed 0.53 always-up and five-day momentum predictions stored for every eligible instrument; selected names retain the same ranks in each baseline |
| Optional research | LightGBM walk-forward report with full-session chronological splits; FinBERT CPU function; matched 60-day promotion predicate; atomic token-budget reservation |
| Delivery | Deterministic Telegram-sized templates, any nonempty call count, empty-day status notes, read-only previews, opt-in scheduled/CLI delivery to one verified private chat, duplicate-attempt protection |
| Live services | Selectable Yahoo/Upstox quote/candle adapters, public RSS collection, source-specific display snapshots, actual receipt times, exchange-session checks, durable scheduled jobs, bounded retries, verified private-chat delivery |
| Event notes | One frozen note per collected article and named company: event type plus Positive / Negative / Neutral / Mixed / Unclear from conservative keyword rules; owner notes saved as new versions; the reaction session derived from publication time and the NSE calendar; gap, open-to-close and five-session reactions written once when bars exist; "what happened before" limited to reactions known when the note was written; syndicated copies counted as one event; shown on the stock page and in the news list; zero influence on calls |
| Hosting | Pages workflow, sign-in and exact-origin API access, Docker Compose/PostgreSQL, Caddy and systemd templates; infrastructure requires setup |

The current displayed rule **is the five-day momentum baseline**, deliberately. Comparing it with always-up provides a working measurement starting point; it is not an ML model with a demonstrated advantage. All extra AI helpers have zero influence until implemented and validated.

Selection approved on 2026-09-09: rank eligible candidates by the existing score across both directions and select the first ten, or all candidates when fewer qualify. Ties use the symbol. No direction is forced and no five-per-direction minimum remains. New batches record the separate `ranked_available_v1` selection policy and candidate/selected counts. All eligible predictions and both baselines are still saved. Existing days retain their original ranks and outcomes; the September 9 skipped record is not backfilled.

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

The provider-aware worker uses a source-linked 2026 NSE calendar and reviewed overrides; unknown years and unconfirmed session hours fail closed. See [PUBLIC_DATA.md](PUBLIC_DATA.md). Scheduled forecasts run 07:20–08:25 IST on verified regular sessions, using observations published and received by 07:00. The legacy import/predict CLI above separately requires an explicit holiday file and rejects backdating or execution after 09:00. Any positive eligible candidate count is valid; an empty set produces a recorded no-calls reason. Later imports cannot create a missed morning batch.

For Telegram, configure the bot token and one private chat ID, verify the chat, then explicitly enable `TELEGRAM_ENABLED=true`. Preview first. Delivery runs through the worker's message windows or the explicit sending CLI; visiting the website and requesting a preview never send. The sender records its attempt before network I/O and does not retry an ambiguous delivery. Prior real delivery is recorded in [MEMORY.md](MEMORY.md); automated checks use mocks.

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
2. Global/context feeds, fundamentals, exchange-filing connectors, expectation data and scheduled FinBERT sentiment. Public RSS collection and keyword-rule event notes with measured reactions are implemented; neither changes predictions, and the keyword rules are a deliberately narrow placeholder for an evaluated extractor.
3. A configured and evaluated LLM provider; strict per-agent JSON validation and provenance; scored helper weights; automatic safe fallback and actual spend accounting. Token reservation and the future writer contract are supplied, but no provider call is active.
4. A trained/calibrated champion, weekly retraining and promotion integrated into daily forecasts, reliable event-conditioned scorecards, and validated confidence thresholds.
5. Backup retention/recovery rehearsal, continued resource monitoring, PostgreSQL verification and delivery monitoring. The SQLite VM API/worker, Telegram configuration, HTTPS and Pages are deployed. See DEPLOYMENT.md.
6. Validated intraday F&O signals and an option-price simulator. Index lab provides unvalidated opening-range/retest direction checks, a separate optional Call/Put paper gate and a one-lot calculator. Option entries stay Skip without a verified quote source; a cash gate cannot validate options. **No live-order integration is present or planned for this educational version.**

## Checks

```bash
cd backend
../.venv/bin/python -m pytest -q
cd ../frontend
npm run build
npm run test:e2e
```

Browser checks require Google Chrome and a sample-data API at port 8000 by default; set `JOURNAL_BASE_URL` to use an isolated local port without disturbing another server. They exercise all six pages, saved-call details, keyboard focus, date and wrong-call filters, stock search, optional details, note previews, and desktop/390px layouts. Screenshots stay in the ignored project data directory.

Verified for the flexible-selection/interface update: **129 backend tests, 14 isolated hosted browser checks, three journal browser checks and the production frontend build passed.** Selection checks cover 1/4/10-call batches, one-sided days, deterministic ranks, unchanged saved records, empty diagnostics and once-only mock delivery. Browser checks cover actual counts, partial/empty results, nested Pages hosting, cross-origin sign-in, private export, source freshness, calculator limits and expired/disconnected index actions. Event tests retain recording-time cutoffs, missing-session rules, corrected articles, negation, expectation gaps and zero influence on daily calls. Run `.venv/bin/python scripts/check_pages.py` from the root for hosted checks. See [MEMORY.md](MEMORY.md) for the handoff and deployment status; optional ML runtime and PostgreSQL deployment are not covered.

The frozen ten-day integration fixture expects **−₹150** for the model and **+₹850** for simply buying, with **50 of 100** calls right. This known losing example checks selection, resolution, costs, direction scoring, and message generation through the same functions used by the app.

## Project map

- `CONTEXT.md` — original requirements and approved clarifications.
- `frontend/src/App.tsx`, `styles.css` — journal pages and responsive design; `IndexLab.tsx` and `IndexSignals.tsx` add the index checks and calculator.
- `backend/app/engine.py` — cutoff readers, calls, outcomes, P&L and promotion gate.
- `backend/app/analytics.py` — the common source for website scorecards.
- `backend/app/models.py`, `db.py`, `schema.sql` — database and immutability controls.
- `backend/app/ingest.py`, `jobs.py` — explicit import and job boundary.
- `backend/app/news.py`, `events.py` — public feed collection; frozen event notes, measured reactions and cutoff-safe comparisons.
- `backend/app/learning.py`, `research.py` — optional model research.
- `backend/app/briefs.py`, `telegram_templates.md`, `brief_prompt.md` — messages and future writer contract.
- `deploy/` — reviewable hosting templates; not installed services.

The repository is public; the running journal is authenticated. Keep credentials and databases private and out of version control. The local server binds to loopback. Remote use requires authentication and HTTPS.

Index paper research: see INDEX_PLAN.md for strategy `index_orb_retest_v1`, timing and risk assumptions. Yahoo index checks need no broker key. The default `INDEX_OPTION_PROVIDER=none` deliberately leaves option entries at Skip. `backend/app/index_sources.py`, `index_research.py`, `index_options.py` and `index_jobs.py` own this workflow independently of daily cash predictions. Current implementation does not track executed positions or resolve option outcomes.
