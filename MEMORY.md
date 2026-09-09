# Project handoff

## Latest repair checkpoint — 2026-09-09 (daily status and Telegram fixed)

**Current deployed application revision: b0de042e9022abdc4e8e805c2d003d1954ae1dfc** (notification logic from fc50d0f; final frontend spacing correction), pushed to main and live on Oracle and Pages. This section supersedes the older b645625 deployment checkpoint below. The owner reported no calls or Telegram notification today; live records confirmed zero September 9 forecasts and no delivery attempt because only 3 Buy / 17 Sell candidates qualified versus the strict five per direction requirement.

Fixed: a controlled InsufficientCandidates exception retains both counts; scheduler saves a separate `daily_calls:YYYY-MM-DD` diagnostic and readable failure detail. Live Today and undated brief previews use the actual IST date, so yesterday’s calls are not presented as today’s. The site shows a prominent No stock calls today banner above live feeds, plus Telegram delivery state. Prior calls remain in Calls by day. System health distinguishes today’s call availability, notification delivery and general bot configuration. Morning/evening jobs now send a short no-calls status note if a full batch is absent, using the existing verified private chat and once-only period/day claim. An empty evening no longer falsely says closing results are pending. The five-Buy/five-Sell rule, source cutoff, daily P&L and immutable forecasts are unchanged.

**Actual Telegram action completed:** on the owner’s notification repair request, one late, clearly labelled STATUS UPDATE was sent for September 9. It explains the 3 Buy / 17 Sell shortfall and missed 08:30 brief; it contains no trading calls. Telegram confirmed delivery and `telegram:morning:2026-09-09` is `sent`. A new `morning status recovery` JobRun records this action. DO NOT resend this note or clear the delivery claim. The original failed morning/prediction jobs were preserved. Today’s diagnostic was recorded at the actual repair time from read-only `daily_candidates` evaluation of pre-cutoff data; no backdated forecast or partial batch was created. Prepared note is in ignored server data/no-calls-2026-09-09.html; SHA256 07099c09c740c1f672111b7201c1f9842e01ad6a735c40ce67fbde31a48459c8.

Verification: **112 backend tests, six isolated browser tests, production frontend build and live Pages browser check all passed.** The initial backend run found an old test that relied on a fixed health-card position; changed it to assert the Event notes check by name. Mock tests prove a shortfall creates zero forecasts, retains its reason after the failed job, and sends only one no-calls note. Existing ambiguous-delivery protection tests still pass. Live checks confirmed September 9 has zero calls, the correct shortfall and sent status, formatted preview, 390px mobile layout and intact September 8 history. The previous ten calls matched their saved SHA256 fingerprint exactly. Screenshots: ignored data/no-calls-live-desktop.png and data/no-calls-live-mobile.png. Graph updated: 1,273 nodes / 4,141 edges / 37 communities.

Release SHA256: **637ee4dbaa3efaf81b7d77c7b5acbf73a3573bde1c89315607c665051f159ad2**. Consistent SQLite backup and previous code: server **data/backups/before-fc50d0f-20260909T054017Z**; integrity_check passed. API/worker/proxy active after deployment. Server data/deployed-revision.txt records b0de042 after the frontend-only spacing correction. The final bundle SHA256 is f2f5fa17ef44a0f7e4372b1d2530e37d2569ab64fd906cb780da40ae000e7052. A newer consistent SQLite backup under data/backups/after-status-send-20260909T054540Z includes the confirmed Telegram delivery claim and passed integrity_check; preserve that claim during recovery. This final CSS update did not restart the services. Pages run 34316125105 passed for b0de042; the backend/build workflow was still running at this checkpoint. The live browser check passed again after the spacing change. Final graph: 1,274 nodes / 4,141 edges / 36 communities. GitHub Check journal **34315775177** and Pages **34315774993** passed. New code: backend/app/daily_status.py and tests/test_daily_status.py; other changes are in engine, scheduler, briefs, analytics, main and frontend Today/types/styles/tests. No secrets were staged. This handoff is a later documentation-only commit.

Remaining: the small universe can still fail the strict daily selection quota; this repair makes that outcome explicit and not silent. Expand a verified universe or change the quota only within the owner’s agreed experiment rules; never force directions or manufacture morning calls later in the day. Index paper checks remain separate with option provider none, so Call/Put entries remain Skip pending a verified feed and evaluation. Keep memory checkpointed during future work.

## Latest checkpoint — 2026-09-09 (index paper signals deployed)

The owner explicitly requested frequent file-based handoffs before session limits. Save this document after major checkpoints; an abrupt quota limit cannot be predicted. All local files must remain in this project directory. The earlier usage-limit approval rejection was resolved when the owner resumed this session.

**Deployed application revision: b645625fcbb87c7e601ba3d1207bce09713ae63d.** It is pushed to main and live on both Oracle and GitHub Pages. This handoff is a subsequent documentation-only change. Read current Git status before continuing; no unfinished index implementation is being left in the working tree.

Implemented: Nifty / Bank Nifty Up, Down or Skip research checks; a separate Buy Call / Buy Put / Skip paper gate; immutable five-minute candles and assessments; owner-only on-demand refresh; a five-minute worker schedule; formatted Telegram preview with IST times (no automatic index send); and the Index lab interface. See index_sources.py, index_research.py, index_options.py, index_jobs.py, IndexSignals.tsx and test_indices.py. The rule uses a completed 15-minute opening range, immediate breakout/retest and EMA20/50 with 150 consecutive verified candles. Missing, stale or out-of-session inputs give Skip. Later provider revisions, including a reversion A → B → A, append a new observation. Invalid option fields cannot break saved Skip assessments. There is no proven accuracy, fill simulation, scored option outcome or order execution.

Yahoo supplies real five-minute index candles. The optional Upstox contract/full-quote adapter is tested with mocks only and needs production verification, including contract tick units. **Live INDEX_OPTION_PROVIDER is none**, so Call/Put entries stay Skip. Default paper capital is ₹10,000, the planned-loss budget is 1%, and assumed costs are ₹60. Identity, expiry, actual lot size, quote age, spread, depth, funding and risk must all pass. The calculator does not change these server settings. News and scheduled announcements are not used by this index strategy. INDEX_PLAN.md specifies the rule and missing validation.

Verification: 107 backend tests, five isolated hosted browser checks and production frontend build passed. The final backend run includes the candle-reversion fix. Actual September 9 collection saved 636 candles (318 each) in an isolated DB and returned Skip because no setup was present. graphify update completed: 1,252 nodes / 4,034 edges / 36 communities. Staged files were checked for private config values and key material; the 58-file release bundle excludes private config and databases. Git whitespace checks passed.

Deployment: release SHA-256 **40108285923dd02110e83fa82df2734e5bc8fb15db5c72886dc2388a5c8e559f**, local ignored data/oracle-release.tar.gz; remote data/release-b645625.tar.gz. Prior code plus a consistent SQLite backup are under **data/backups/before-b645625-20260909T052012Z** on Oracle. integrity_check passed. API, worker and proxy are active. data/deployed-revision.txt records b645625. Existing cash calls were fingerprinted before and after deployment and remained identical. No real Telegram message or order was sent during verification.

Live verification: Pages sign-in, both index cards, one owner-triggered refresh, escaped/bold Telegram preview with IST timestamps, and 390px mobile layout passed. Screenshots: ignored data/index-signals-live-desktop.png and data/index-signals-live-mobile.png. Local fixture screenshots are data/index-signals-desktop.png and data/index-signals-mobile.png. The worker saved successful indices:5963104 at 05:20:21 UTC; manual refresh completed afterward. Four saved checks were visible at the final HTTP check, with both options at Skip and candle end 05:20 UTC. This is a timestamped observation, not a permanent health claim. GitHub Check journal **34314366602** and Pages **34314366601** both passed for b645625.

**Existing cash limitation found during final verification:** no September 9 cash calls or morning Telegram brief were produced. The pre-cutoff price data were complete and non-synthetic, but the existing 20-stock universe gave only **3 Up / 17 Down** candidates. make_daily_calls requires five in each direction, so it raised ValueError; the scheduler currently stores only a generic ValueError detail. The missed message was correctly blocked because ten saved calls did not exist. A read-only reconstruction confirmed this; no forecasts were created after the morning window, no past job record was rewritten, and no message was replayed. The latest saved cash day remains September 8. A larger verified universe and a clear insufficient-candidates health message are useful follow-ups; never fabricate directions to meet the quota.

Next work: production option-feed verification when the owner supplies/chooses permitted access; quote history, conservative fill/exit simulation and immutable outcomes; later-session evaluation before any accuracy/profit claim; event/news challenger validation; and the cash coverage/diagnostic improvements above. No automatic index Telegram alerts are enabled. Do not treat the cash scorecard as options validation. Preserve all frozen records and configuration.

The sections below retain the previous review and operating context. This checkpoint supersedes any earlier calculator-only or deployment status. See CONTEXT.md for original requirements and later approvals; DEPLOYMENT.md for infrastructure notes. This document contains no secrets.

## Purpose and owner decisions

- India first, US later. Personal educational paper journal, modern simple interface. No guaranteed win rate, daily income or profitable month; no real-order API.
- Original cash experiment: five Buy and five Sell calls; ₹1,000 per selected stock, not ₹1,000 across the whole day; open-to-close horizon, 07:00 IST information cutoff. Short result is ₹1,000 × (entry − exit) / entry minus costs. Round-trip 0.15% is an assumption, not a broker quote.
- Predictions and one-time resolutions are immutable. Check both publication and actual receipt times. Historical imports must not fabricate prior live calls. Index calls get direction scores, no pretend stock-position money. Stops are alerts, not simulated fills.
- Free/public data first. Yahoo via yfinance; ET Markets, LiveMint Markets/Companies and RBI RSS. Upstox adapter exists but is not production-verified. Other broker APIs later.
- The five-day momentum rule is uncalibrated. News records and keyword labels have zero influence on daily probabilities. Optional LightGBM/FinBERT code is not an evaluated model or installed production runtime.
- New request: review another agent's changes, improve Telegram formatting and usability, and examine Nifty/Bank Nifty options with small capital. `INDEX_PLAN.md` explains the proposed experiment. The prior deployed Index lab was a calculator; the active checkpoint above covers its newly approved paper engine.

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

1. No proven profitability, trained champion, production-verified option feed, option execution simulator, scored option outcomes or automatic option Telegram alerts. The cash 60-day checkpoint does not validate F&O. See INDEX_PLAN.md for contract/data/validation requirements.
2. Current real starter universe is 20 stocks, not the full historically verified Nifty 500. Historical membership/re-entries, corporate-action reconciliation, long history and official exchange archives are still needed.
3. News extraction is a conservative keyword placeholder, and story grouping is coarse. Expectations, official filings, intraday event studies and an evaluated news-plus-price challenger remain pending. Historical reaction is association, not proof of cause or tradable knowledge at publication.
4. Ongoing monitoring, backup retention and recovery rehearsal need operational work. Keep heavy model work local. PostgreSQL and optional ML runtime remain unverified.
5. Keep this handoff current after verification/deployment. Never substitute a handoff's claim for checking the current services, Git revision and test results.

## Review verification

80 backend tests and four isolated hosted-page browser checks passed on 2026-09-08. Browser checks include exact one-lot calculations, changing the daily goal without enlarging exposure, invalid/empty inputs, mobile width, safe formatted Telegram previews, cross-origin authentication and on-demand refresh. The knowledge graph was updated (1,184 nodes / 3,776 edges). Actual Telegram delivery was not triggered by this review. Commit `f3de0b7` was deployed to Oracle and published by Pages. GitHub Check journal run `34261993170` and Pages run `34261993080` passed. The release SHA-256 is `28cb2c1e2d29d76dc5d916618de60aaec9a1d734634cc74191e400f35b5354ac`. A consistent SQLite backup and prior code archive were saved on the VM under `data/backups/before-f3de0b7-*`; integrity_check passed. API/worker/proxy are active and the formatted API preview was verified without sending. The deployed code revision is recorded on the VM in `data/deployed-revision.txt`.

Final live browser smoke check passed: real Pages sign-in, ten saved calls, bold Telegram preview, the ₹710 example loss, Skip state and mobile layout. Screenshots are in ignored `data/telegram-live-preview.png`, `data/index-lab-live-desktop.png` and `data/index-lab-live-mobile.png`. No real Telegram message or order was sent during this review.
