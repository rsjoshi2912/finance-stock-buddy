# Public data, without a broker account

The default provider is now `yfinance`. Upstox remains selectable, and later brokers can implement the same read-only provider interface in `backend/app/market.py`. No trade or account endpoints are used. See [the yfinance project](https://github.com/ranaroussi/yfinance) for its personal research scope and Yahoo usage terms. It is an unofficial library, not a guaranteed exchange feed.

## What is connected

| Source | Use | Access |
| --- | --- | --- |
| Yahoo Finance via yfinance | Indian stock daily OHLC and recent price snapshots | No API key; may be delayed, limited or unavailable |
| ET Markets RSS | Market news | Public feed; dated articles and source links |
| LiveMint Markets and Companies RSS | Market and company news | Public feeds; dated articles and source links |
| RBI RSS | Policy and central-bank releases | Public feed; its timezone-free dates are explicitly interpreted as IST |
| NSE circulars | Published 2026 session calendar | Bundled source-linked dates and verified amendments; changes require review |

NSE announcements and Moneycontrol are optional RSS connectors. They are not enabled by default: NSE timed out from the tested machine, and Moneycontrol's successful response contained old articles. The importer reports unavailable/stale sources rather than claiming a successful current feed. Configure named feeds with `NEWS_FEEDS`; arbitrary fetch URLs are not exposed through the app.

Public RSS is not a complete historical news archive. Articles that name a tracked company receive a frozen keyword-rule event note when collected, and a measured reaction once the session bars arrive; the news list shows the label and the stock page shows the full note. These notes have no influence on the price rule. See [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md).

## Run with public observations

Install `backend/requirements-lock.txt` into the project virtual environment. In `.env`, set a **separate** live database, a strong owner password and:

```dotenv
APP_MODE=live
MARKET_DATA_PROVIDER=yfinance
NEWS_ENABLED=true
NEWS_FEEDS=et-markets,mint-markets,mint-companies,rbi
TELEGRAM_ENABLED=false
```

Keep `UPSTOX_ACCESS_TOKEN` empty. Supply your verified instrument CSV, or start with the explicit small watchlist:

```bash
cd backend
../.venv/bin/python -m app.live starter-universe
../.venv/bin/python -m app.live bootstrap
../.venv/bin/python -m app.live quotes
../.venv/bin/python -m app.live news
../.venv/bin/python -m app.scheduler
```

`starter-universe` verifies 20 named Indian companies against Yahoo and records membership from observation day. It is **not the full Nifty 500 or historical index membership**. Existing supplied instruments are preserved. `import-universe --file ...` supports the full owner-supplied CSV without requiring broker instrument keys in public mode. The official full constituent download did not respond from this machine; it is not claimed as connected.

`bootstrap` requests approximately 90 calendar days of daily bars through the previous verified session. Use `--end YYYY-MM-DD` for an explicit historical boundary when a session calendar is unavailable; that option imports observations and does not write forecasts. Actual receipt timestamps remain today. Importing history cannot create past live results.

The worker checks public prices every five minutes for today's selected names, or up to ten starter names when there are no saved calls. It collects the configured news feeds every five minutes between 06:00 and 20:00 IST. The browser reads saved observations; opening a page never directly requests Yahoo or triggers a Telegram message. Real-time accuracy is not claimed by a five-minute refresh label.

The 2026 calendar is in `backend/data/nse-calendar-2026.json`, sourced from NSE circulars. `data/nse-holidays.json` overrides it if present. Other years and unconfirmed special-session hours fail closed. News and weekday display checks can continue when hours are unconfirmed; morning calls and daily messages cannot. Recheck NSE amendments before extending the calendar. The generic older `app.jobs predict` CLI still requires its explicit `data/nse-holidays.json`; use the worker for the provider-aware schedule.

Daily prices retain Yahoo's returned OHLC with `auto_adjust=False` and `repair=False`; vendor revisions and split conventions still need reconciliation before a long historical study. Existing accepted bars are preserved. Large unexplained movements remain quarantined. Do not combine provider series without checking their adjustment and session conventions.

## Local verification and deployment

A real public-data run on 2026-09-07 verified 20 companies, imported 1,300 daily observations, saved ten recent quote snapshots and collected 130 dated articles across the four default feeds. These are observation counts, not validated predictions or profitability. The separate local database is `data/public-live.db`; its ignored credentials are in `.secrets/public.env`.

The Oracle VM was still timing out during SSH checks. These local imports do not mean the remote API, scheduler or GitHub Pages site has been deployed. Deployment instructions remain in [DEPLOYMENT.md](DEPLOYMENT.md).

When connecting a broker later, set `MARKET_DATA_PROVIDER=upstox`, configure its token and import its verified mappings. Additional broker adapters should expose source IDs, timestamped daily bars, quote timestamps, session times and polling limits. Switching providers must not relabel old observations or rewrite saved calls. Telegram still needs a private bot token and verified owner chat.

## Open the prepared local preview

The authenticated preview uses **http://127.0.0.1:8001**. Use `OWNER_USER` and `OWNER_PASSWORD` from the ignored `.secrets/public.env`; do not commit or share that file. The browser may show its native sign-in prompt.

To restart the preview or worker from the project root, in separate terminals:

```bash
.venv/bin/python scripts/run_public.py web
.venv/bin/python scripts/run_public.py worker
```

The worker runs only while this machine and process stay active. It is separate from the old sample preview on port 8000. Telegram is disabled in the prepared configuration. All caches, credentials, databases and test artifacts remain under this project.

## Fetch latest on demand

Use **Fetch latest** on the Today page to request fresh price snapshots and news immediately, including outside the scheduled collection window. The backend runs the request in the background, so the page stays usable. Progress is saved and survives a browser reload. Each source result is shown separately, and the price/news panels reload when the request finishes. Existing market timestamps remain visible even when a provider returns the same or delayed price.

One manual request can run at a time. Repeated clicks or a second browser tab join the existing request. There is a 60-second pause after completion before another manual request; this protects public-source request limits. Scheduled and manual collection use the same database-specific lock. If another collection already holds it, the manual result says so and keeps previous data. The News enabled setting is respected.

The owner-authenticated API is `POST /api/refresh` with an empty JSON object; it returns HTTP 202 and the saved request state. `GET /api/refresh` reports progress and the last result. This works without the scheduler process, as long as the API is running. A server restart can interrupt an in-process task; after ten minutes without progress it is shown as interrupted and can be retried. It does not automatically resume an interrupted fetch.

This action fetches display quotes and news only. It does not import daily history, change or resolve saved predictions, place orders, or send Telegram messages. New observations retain their actual receipt times and cannot enter an earlier morning call.

Verified: 65 backend tests and three hosted-page browser checks passed, including concurrent requests, partial failures, authentication, reload during progress and automatic panel updates. A real on-demand fetch was also exercised in the local preview.

## Separate index research (2026-09-09)

Index lab now collects actual five-minute Yahoo candles for Nifty 50 and Bank Nifty into their own immutable tables. A real access check returned 375 bars for each index through the September 8 close. This is observed availability, not a low-latency feed guarantee. Completed candle and receipt-time checks reject stale or missing inputs. Daily cash forecasts and the stock watchlist are unchanged.

`GET /api/indices` returns current research cards, original saved checks and refresh status. `POST /api/indices/refresh` starts or joins an authenticated background check with a 60-second cooldown; it shares the source lock with other collection. `GET /api/indices/brief` previews HTML and plain text without sending. The worker checks every five minutes during verified exchange hours when `INDEX_RESEARCH_ENABLED=true`. Background refresh is process-local; interruptions use the existing stale-job recovery rather than a durable queue.

No free option quote source has been production-verified. `INDEX_OPTION_PROVIDER=none` keeps entries at Skip. The optional existing Upstox adapter has mocked contract/quote tests, requires the owner's valid data access, and must be verified against real contract units before reliance. See INDEX_PLAN.md for the rule, configuration and remaining paper-outcome work.

Observed September 9 cash coverage: all 20 stocks had the required pre-cutoff prices, but the five-day rule yielded 3 Up and 17 Down candidates. The strict five-Buy/five-Sell requirement therefore skipped the entire daily batch and its morning message. Expanding the verified universe is still needed; the system does not relabel directions or backfill missed live forecasts to satisfy the quota. Index paper checks are separate and continued normally after deployment.
