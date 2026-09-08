# Project handoff

Updated 2026-09-08, following review of the second agent's work. Read current Git status and `DEPLOYMENT.md` before resuming. This document contains no secrets. See `CONTEXT.md` for the full original brief and subsequent decisions.

## Purpose and owner decisions

- India first, US later. Personal educational paper journal, modern simple interface. No guaranteed win rate, daily income or profitable month; no real-order API.
- Original cash experiment: five Buy and five Sell calls; ₹1,000 per selected stock, not ₹1,000 across the whole day; open-to-close horizon, 07:00 IST information cutoff. Short result is ₹1,000 × (entry − exit) / entry minus costs. Round-trip 0.15% is an assumption, not a broker quote.
- Predictions and one-time resolutions are immutable. Check both publication and actual receipt times. Historical imports must not fabricate prior live calls. Index calls get direction scores, no pretend stock-position money. Stops are alerts, not simulated fills.
- Free/public data first. Yahoo via yfinance; ET Markets, LiveMint Markets/Companies and RBI RSS. Upstox adapter exists but is not production-verified. Other broker APIs later.
- The five-day momentum rule is uncalibrated. News records and keyword labels have zero influence on daily probabilities. Optional LightGBM/FinBERT code is not an evaluated model or installed production runtime.
- New request: review another agent's changes, improve Telegram formatting and usability, and examine Nifty/Bank Nifty options with small capital. `INDEX_PLAN.md` explains the proposed experiment. The implemented Index lab is a calculator and research explanation, not an option-signal engine.

## Work inherited and reviewed

Last committed base on arrival was `0efeadf` (on-demand fetch). The other agent's event-news changes and deployment notes were uncommitted locally; the VM had those changes while Pages still built the older commit. Preserve and publish the reviewed changes together rather than discard them.

The other agent added `backend/app/events.py`, immutable EventAssessment/EventOutcome tables, owner-added notes, event labels in news, stock-page event history, scheduler collection hooks and tests. They deployed the VM, connected Telegram, enabled public GitHub Pages and addressed a VM memory incident. At review start, 74 backend tests passed.

Review corrections now implemented:

- Past event views require the article, note and reaction's own recording timestamp to be known at the cutoff. Later-computed reactions do not silently rewrite earlier views.
- Session reactions require the actual prior exchange session; five-session reactions require all five consecutive verified sessions. Missing bars are not replaced by later days. Benchmark prices must also be available when a reaction is recorded.
- New `rules_v2` notes leave negated/uncertain wording and multiple-company articles Unclear. Existing `rules_v1` notes remain frozen; no backdated relabelling.
- Event history does not show a success percentage below five cases. Three-day grouping is explicitly a heuristic that can merge different events, not verified story identity.
- Manual fetch keeps its provider open until event calendar lookups finish. Owner-note requests close their provider afterward.
- Telegram uses escaped HTML, bold headings and concise saved-call rows; the API supplies plain text plus HTML and the browser renders a tag allowlist as React elements. Preview does not send; duplicate-attempt protection remains.
- Index lab is a sixth page. Nifty/Bank Nifty, CE/PE explanations, user-entered premiums/lot size, one-lot funding, stop loss, possible full-premium loss, net target and daily-goal arithmetic. Illustrative 1% trade / 2% daily loss budgets; a goal never increases size. Example prices are explicitly invented, not a live chain. No option alerts/orders.

## Live environment

- Site: https://rsjoshi2912.github.io/finance-stock-buddy/
- Authenticated API and same-origin site: https://130.210.23.30
- Repository: https://github.com/rsjoshi2912/finance-stock-buddy, public after the owner chose this for Free-plan Pages (per the other agent's deployment notes). Never upload secret configuration, data or private tokens. Repo-local Git identity is the personal GitHub account, not the global work identity.
- VM: Oracle Linux 9 x86_64, about 945 MB RAM, 944 MB swap, user `opc`. Application `/opt/finance-stock-buddy`, SQLite `data/live.db`, config `.env`; `nifty-api`, `nifty-worker`, `nifty-proxy` systemd services. Standalone Python and Caddy in `.runtime`; leave system Python alone.
- Local ignored SSH key/known hosts: `.secrets/ssh/`. Local copy of server configuration: `.secrets/oracle.env`. Never put their values in chat, documentation, logs or Git.
- Telegram is enabled on the VM and the private chat verified. Setup did not send messages. Check delivery records before any retry; ambiguous failures must not trigger duplicate messages. Template checks use HTTP mocks only.
- At 2026-09-08 review: API authenticated checks returned 200, ten Sept 8 calls existed, one day was resolved, 21 event notes / 14 session reactions existed, all three services were active, worker heartbeat was current. Feed freshness warnings were visible late at night. These counts and health are observations, not permanent facts.
- A dnf cache job previously consumed most memory and caused the morning Telegram window to be missed. `dnf-makecache.timer` was confirmed disabled. Do not run dependency builds/ML research on this VM. Missed morning messages are not replayed automatically.
- HTTPS on the IP requires Caddy `default_sni 130.210.23.30` behind Oracle NAT. Short-lived certificates renew automatically. Ingress/firewall ports 80/443 are configured. Do not re-provision an already-running service.

## Local environment and commands

Project directory: `/Users/ravjoshi/Desktop/codebases/finance-stock-buddy`. The coding tool may start in sibling `Avaya`; that is not the project. Ask sandbox escalation through the execution tool when needed for this folder; keep generated files here.

- `.venv` uses Python 3.13. Frontend uses Node/npm, React/TypeScript/Vite. Dependencies are locked.
- `scripts/run_public.py web` / `worker`, invoked with `.venv/bin/python`, load `.secrets/public.env`, run real-data preview on 127.0.0.1:8001 and use `data/public-live.db`. Root `.env` is a different local/demo configuration. Do not overwrite the server DB/config with local preview state.
- Port 8000 may have an older local demo process. Verify process ownership and command before stopping or restarting; saved PIDs are not reliable across sessions.
- Backend: from `backend`, `../.venv/bin/python -m pytest -q --basetemp=../data/pytest-review-final`.
- Hosted browser checks: from root, `.venv/bin/python scripts/check_pages.py`; isolated servers on 18001/14173, fixture credentials, screenshots in ignored `data/`. This covers cross-origin login, saved calls, on-demand fetch, index calculator, mobile width and HTML preview.
- Production frontend: from `frontend`, `npm run build`. Then root `.venv/bin/python scripts/package_release.py` produces allowlisted `data/oracle-release.tar.gz` without secrets/databases.
- Deploy only the release bundle, preserve `.env`/DB/runtimes, then restart API and worker. Build locally. Keep a prior code bundle and consistent SQLite backup for recovery. Pages auto-builds frontend changes on main using repo variable `VITE_API_BASE_URL=https://130.210.23.30`.

## Important file map and boundaries

`backend/app/engine.py`: immutable daily forecast and paper P&L. `analytics.py`: shared scorecards/health. `market.py`, `public_data.py`, `news.py`: provider observations, real receipt times, source health. `events.py`: frozen keyword notes, reactions and comparisons. `scheduler.py`: verified-calendar jobs and heartbeat. `refresh.py`, `fetch_lock.py`: owner-only background price/news fetch, shared process lock, 60-second cooldown, partial failures and interrupted-run recovery. The task runs in the API process; it is not a durable external queue and needs retry after interruption. It never regenerates calls, resolves trades or sends Telegram.

`briefs.py` and `telegram_templates.md`: formatted messages. `frontend/src/IndexLab.tsx`, `INDEX_PLAN.md`: options research and arithmetic. `PUBLIC_DATA.md`, `KNOWLEDGE_PLAN.md`, `DEPLOYMENT.md`: data limitations, planned evaluation and operations. `CLAUDE.md`: engineering rules. `schema.sql`: PostgreSQL reference; actual deployment/tests use SQLite.

## Remaining work

1. No proven profitability, trained champion, option feed, intraday signal engine, option execution simulator or option Telegram alerts. The cash 60-day checkpoint does not validate F&O. See INDEX_PLAN.md for contract/data/validation requirements.
2. Current real starter universe is 20 stocks, not the full historically verified Nifty 500. Historical membership/re-entries, corporate-action reconciliation, long history and official exchange archives are still needed.
3. News extraction is a conservative keyword placeholder, and story grouping is coarse. Expectations, official filings, intraday event studies and an evaluated news-plus-price challenger remain pending. Historical reaction is association, not proof of cause or tradable knowledge at publication.
4. Ongoing monitoring, backup retention and recovery rehearsal need operational work. Keep heavy model work local. PostgreSQL and optional ML runtime remain unverified.
5. Keep this handoff current after verification/deployment. Never substitute a handoff's claim for checking the current services, Git revision and test results.

## Review verification

80 backend tests and four isolated hosted-page browser checks passed on 2026-09-08. Browser checks include exact one-lot calculations, changing the daily goal without enlarging exposure, invalid/empty inputs, mobile width, safe formatted Telegram previews, cross-origin authentication and on-demand refresh. The knowledge graph was updated (1,184 nodes / 3,776 edges). Actual Telegram delivery was not triggered by this review. Deployment confirmation follows after the release is applied.
