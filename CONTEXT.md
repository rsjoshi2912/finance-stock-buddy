# Nifty Signal — full context for any agent working on this project

Read this first. It is the single source of truth for what is being built and why. Companion files: `CLAUDE.md` (engineering brief), `schema.sql`, `telegram_templates.md`, `brief_prompt.md`, `site-design.html` (visual spec), `README.md`.

## 1. Who and why

- Owner: Ravi. Senior full-stack developer (Java, JavaScript, Python, AEM). Comfortable with Postgres, Linux, APIs, React. New to ML in production.
- Purpose: a personal, educational tool to learn how far Indian stock-market prediction can actually go, by making daily calls and scoring them without mercy.
- Single user. Not a product. Not for sharing. Not investment advice. (Sharing buy/sell calls with others would require SEBI RIA/RA registration; this is why it stays private.)
- Owner's stated preference for all communication: blunt, direct, no sugar-coating.

## 2. The one-paragraph summary

Every trading morning at 8:30 IST the system sends a Telegram message with 5 buy calls and 5 sell calls for that day (Nifty 500 stocks plus Nifty 50 and Bank Nifty), each with a confidence %, an expected price range, a stop level, a one-line reason with sources, and the model's own past accuracy on that stock. Every evening after close it sends what would have happened if ₹1,000 had been placed on each call, plus which calls were right and wrong and why. A local website shows the same plus full history and analytics. The system retrains itself weekly, but a new model only takes over if it measurably beats the current one. Everything is scored against a "simply buy everything" baseline so the owner can see whether the model has any real edge.

## 3. Honest expectations (agents must not overpromise)

- Daily direction prediction in liquid markets tops out around 55–58% accuracy in published research. "Always up" is right ~53% of days on Nifty. This is the bar.
- Exact price targets are not possible and must never be shown. Only ranges.
- LLM agents reading charts or news do not create edge on their own. They are used for interpreting text into structured signals, writing explanations, and post-mortems. Every agent's opinion is scored; an agent that does not beat the baseline gets zero weight.
- A positive hit rate can still lose money after costs. Money after costs is the real scorecard.
- The system is allowed to conclude "this does not work". That is a valid, useful outcome.

## 4. Functional requirements

### 4.1 Universe and horizon
- Instruments: Nifty 500 constituents (historical membership kept; delisted names retained), Nifty 50 index, Bank Nifty index.
- Horizon: one trading day. Entry at 09:15 open, exit at 15:30 close. Config option to use previous close → close instead.
- Options / F&O: phase 2 only, gated behind the cash scorecard beating baseline for 60 trading days.

### 4.2 Daily pipeline (IST, NSE trading days only; use NSE holiday calendar)
| Time | Job | Notes |
|---|---|---|
| 06:00 | ingest_prices | Previous day's NSE bhavcopy; apply split/bonus adjustments |
| 06:10 | ingest_context | Gift Nifty (best effort), US close, India VIX, USD-INR, Brent, FII/DII |
| 06:20 | ingest_events | NSE/BSE announcements, corporate actions, bulk deals, results calendar |
| 06:30 | ingest_news + sentiment | RSS feeds; FinBERT sentiment locally; dedupe |
| 07:00 | features | Technicals, fundamentals, event flags, sentiment aggregates. **Data cutoff = 07:00.** |
| 07:10 | agents | regime, event_analyst (only stocks with fresh events) |
| 07:20 | predict | Every registered model produces prob_up for every instrument |
| 07:25 | judge | Combines model + weighted agents → final prob, range, stop, rationale, sources |
| 07:30 | resolve_yesterday | Fill outcomes for yesterday's rows if not already done |
| 08:00 | brief_writer | Morning Telegram text from judge output; no new facts allowed |
| 08:30 | send | Telegram morning message |
| 15:45→19:30 | ingest_prices (poll) | Today's EOD once bhavcopy is published |
| 18:30 | resolve_today + pnl + postmortem | Score every call, compute ₹, write miss causes and improvement ideas |
| 19:00 | send | Telegram evening message |
| Sun 10:00 | retrain + champion/challenger | Weekly; promote only on 60-day Brier win |

### 4.3 Prediction rules (hard)
- A prediction row is immutable once written. Only resolution fields may be filled, once.
- Every run records `data_cutoff`; no feature, prompt or agent input may include data published/ingested after it. A test must fail if any feature query lacks the cutoff filter.
- Every prediction stores: instrument, date, horizon, direction, prob_up, expected_low, expected_high, invalidation (stop), ref_price, rank, rationale, model_version, and the list of sources used.
- Two baselines always run alongside: `baseline_always_up` (prob 0.53) and `baseline_momentum_5d`.

### 4.4 Ranking and selection
- Rank all instruments by confidence edge × expected move. Top 5 with direction UP become "Buy", top 5 with direction DOWN become "Sell". Index calls may occupy slots.
- Each pick shows the model's own hit rate on that specific instrument over the trailing 60 days, as "N of M".

### 4.5 Paper P&L (₹1,000 per call)
- BUY: 1000 × (exit/entry − 1). SELL: 1000 × (entry − exit) / entry. Costs 0.15% per call deducted (config constant). The owner approved correcting the original SELL formula on 2026-09-06.
- Track per call, per day, cumulative since inception, best day, worst day, max drawdown, count of winning vs losing days.
- Always compute the identical numbers for `baseline_always_up` on the same 10 tickers and show them side by side.

### 4.6 Self-learning rules
- Resolved outcomes become training rows nightly.
- Retrain weekly (not daily) with walk-forward validation. A challenger replaces the champion only if its Brier score over the trailing 60 trading days is lower.
- Agent weights recomputed weekly on the same basis. Below-baseline agents get weight 0.
- Post-mortem improvement ideas go to a backlog for owner approval. Nothing is auto-applied.

### 4.7 Agents (LLM-backed, strict JSON output, temperature 0)
| Agent | Input | Output | When |
|---|---|---|---|
| regime | Market context + 20-day index history | RISK_ON / RISK_OFF / NEUTRAL, prob_index_up, reasons, sources | Daily |
| event_analyst | Fresh announcements/news per stock | impact −2..+2, horizon, confidence, reasons, sources | Only stocks with fresh events (~30–80/day) |
| technical_analyst | Computed indicator features only | UP/DOWN/FLAT, confidence, pattern tags | Daily; expected to be weak; kept because it must be measured |
| judge | Model prob + weighted agent outputs + their recent accuracy | Final prob, direction, range, stop, ≤40-word rationale, sources | Daily; may not move ML prob more than ±0.15 unless event impact is ±2 |
| brief_writer | Judge output | Telegram text | Morning |
| postmortem | Resolved calls, intraday high/low, intraday events | Cause per miss (NEWS_SHOCK, REGIME_FLIP, MODEL_NOISE, DATA_ERROR, GAP_AND_REVERSE), improvement ideas | Evening |
| fno_analyst | Option chain: PCR, max pain, IV rank, OI change | Range refinement, premium bias | Phase 2, off by default |

Model choice: cheap/fast model for event_analyst; mid-tier model for regime, judge, brief, postmortem. Daily token cap with fallback to FinBERT-only mode (brief still sent, without AI commentary).

### 4.8 Telegram messages
- Morning (08:30): market read; 5 buys; 5 sells; each with confidence, range, stop, one-line reason, source tags, per-stock accuracy; "what would make today wrong"; yesterday's result; sources list; "signals, not advice". ≤4,000 chars.
- Evening (19:00): today's ₹ result and hit/miss count; same for simply-buying; cumulative, best/worst day, drawdown; list of hits; list of misses with cause; any new backlog idea; 60-day scorecard line.
- Exact layouts are in `telegram_templates.md`.

### 4.9 Website (visual spec: `site-design.html`)
Plain language throughout. Five tabs:
1. **Today** — verdict ("Should you trust the model yet?") with three checks: right more often than simply buying; confidence is honest (calibration); makes money after costs. Buy list, sell list, yesterday's rights and wrongs with ₹, equity curve model vs simply-buying vs zero, last-20-days win/miss strip.
2. **Track record** — how often right (rolling 30-day) vs simply buying; calibration chart; month-by-month table; why calls went wrong; where it does well/badly (buy vs sell, index, results day, fearful days).
3. **Calls by day** — all ten for any date with reason, stop, source links, result, ₹; filter to wrong calls.
4. **Look up a stock** — every call ever made on one stock, price chart with right/wrong markers, ₹ result vs simply buying.
5. **System health** — traffic-light checks (cutoff violations = 0, data loads, missing sources, AI spend vs cap); champion timeline; agent weights in plain words; evening review of misses; improvement backlog with Try it / Skip buttons.

Vocabulary on the site: "how often right" (not hit rate), "is its confidence honest" (not Brier/calibration), "simply buying" (not baseline), "Right / Wrong" (not hit/miss), "stop" (not invalidation). Wins and misses are always shown together; never hide misses.

## 5. Non-functional requirements

- Infra: Oracle Cloud Always Free ARM VM (2 OCPU / 12 GB, Mumbai region for an Indian IP — NSE blocks many foreign IPs), systemd timers, FastAPI + Caddy, React (Vite) static build. Postgres on Neon or Supabase free tier (keep under ~400 MB: 5 years daily prices, news bodies capped at 2,000 chars).
- Cost ceiling for LLM usage: roughly $5–15/month; hard daily token cap enforced in code. Build work happens in Claude Code under the owner's subscription; runtime API calls need a separate API key with prepaid credit.
- Data quality: dedupe news by URL and near-duplicate title; quarantine price ticks moving >25% with no matching corporate action; keep raw and clean tables separate; log every ingest run with row counts and status.
- Testing: unit tests for cutoff filter presence, split adjustment, P&L math for buy and sell, message length; integration test running the whole pipeline on a frozen 10-day fixture with golden-file scorecard numbers.
- Security: single owner; site behind basic auth or Tailscale; Telegram bot restricted to one chat_id; secrets in env only.

## 6. Data sources (all free)
| Data | Source |
|---|---|
| EOD prices, delivery % | NSE bhavcopy archives (jugaad-data / nsepython); yfinance `.NS` as backup |
| Announcements, corporate actions, bulk deals, FII/DII | NSE and BSE public feeds |
| Index, VIX, global, FX, crude | yfinance: ^NSEI ^NSEBANK ^INDIAVIX ^GSPC ^IXIC BZ=F INR=X |
| Fundamentals | Screener.in export |
| News | RSS: Moneycontrol, ET Markets, LiveMint, Business Standard |
| Sentiment | FinBERT (`ProsusAI/finbert`) on CPU |
| Option chain (phase 2) | NSE option chain endpoint |

## 7. Build order
- W1: VM, DB, systemd, schema, price ingest + 5-year backfill, context ingest. Verify a known split.
- W2: events, news, FinBERT, features, resolve, scorecard, baselines running LIVE. Ship the morning Telegram from the baseline model only. (Prediction history must start accumulating as early as possible.)
- W3: LightGBM walk-forward model, regime + event_analyst + judge, agent scoring, evening P&L message.
- W4: website tabs 1–3, brief_writer, postmortem + backlog.
- W5: tabs 4–5, champion/challenger job, token cap, holiday handling, HTTPS.
- W9+: fno_analyst only if the scorecard justifies it.

## 8. Decisions already made (do not reopen without the owner)
- Horizon is one day, open→close. Not intraday, not multi-day, for now.
- Top 5 buy + top 5 sell every day, always, even on low-confidence days (the scorecard needs the rows). Confidence is shown so the owner can ignore weak days.
- Baseline comparison is mandatory on every screen and message.
- Predictions are immutable. No exceptions, including data-error days (mark cause DATA_ERROR instead).
- Agents never override the ML model by more than ±0.15 probability unless a ±2 event exists.
- Improvements are never auto-applied.
- No exact price targets anywhere.

## 9. Open questions for the owner
- Entry at 09:15 open vs 09:30 (opening spikes hurt buy calls in the sample analysis).
- Whether index calls should be paper-traded via a proxy (e.g. NIFTYBEES) or left as "not traded".
- Which LLM provider to use if API spend becomes an issue (free-tier alternatives exist at lower quality).

## 10. Glossary (for message and site copy)
- Right / Wrong: the direction call matched the open→close move.
- How often right: share of calls that were right over a window.
- Simply buying: placing the same ₹ on "buy" for every pick regardless of the model's call.
- Confidence: the model's stated probability that the call is right.
- Confidence is honest: calls labelled X% are right about X% of the time.
- Stop: the price beyond which the call is considered wrong.
- Range: the band the close is expected to land in, derived from recent volatility and VIX.
- Cutoff: 07:00 IST; the last moment any data may be used for that day's calls.

## 11. Implementation clarifications (2026-09-06)

- Owner approved standard fixed-notional short P&L, using entry price as denominator. This corrects the original formula rather than silently reporting distorted sell results.
- Open-to-close remains the default. Stops are displayed as alert levels; the daily scorecard does not claim to simulate their execution from daily candles.
- Index calls are scored for direction and marked "not traded" until an explicit proxy is chosen. Both model and simply-buying money exclude them identically.
- The 0.53 baseline and background accuracy figures above are assumptions to investigate, not a universal published ceiling or verified performance of this system.
- The runnable local version uses clearly labelled generated data. See README.md for implemented features and the remaining live-data, model, and deployment work.

## 12. News and reaction knowledge (2026-09-07)

The owner clarified that prediction must investigate latest news alongside historical prices, identify positive and negative effects, and learn from how comparable past events were followed by stock movements. [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md) defines this next layer, its source requirements, event categories, time controls, evaluation and implementation order.

- Keep news sentiment, expected company-specific impact and actual later price reaction separate. Include Neutral, Mixed and Unclear; positive wording does not establish a profitable Buy call.
- Record expectations when available, company/sector context, independent event counts and source/arrival times. Compare the overnight gap separately from our open-to-close trading result.
- Later news can inform monitoring and the evening review, but never rewrite a morning prediction. Historical comparisons may use only outcomes available at the evaluated forecast time.
- Public RSS collection is now implemented and locally verified. Event-conditioned learning remains planned. The current daily rule remains the momentum research baseline until additional signals have been tested.
- Source access and historical coverage must be verified; the "all free" source list above is an initial aspiration, not confirmed availability of every feed or archive.

## 13. Public data first (2026-09-07)

The owner requested free public sources now, with multiple broker APIs later. Yahoo Finance via yfinance is the default price provider; Upstox remains optional. ET Markets, LiveMint Markets/Companies and RBI provide the initial public news collection. See PUBLIC_DATA.md for verified access, polling, observed timestamps, source gaps, the small starter watchlist and the remaining prediction work. No broker token is required for public mode.

## 14. On-demand collection (2026-09-07)

The owner requested an on-demand trigger for the latest data. The live Today page now has Fetch latest for quote snapshots and news. It reports background progress and source outcomes, prevents overlapping manual requests, and uses the same source lock as scheduled collection. Morning predictions and their results remain immutable. See PUBLIC_DATA.md for endpoint behaviour and recovery limits.

## 15. Event notes and measured reactions (2026-09-07)

Step 2 of KNOWLEDGE_PLAN.md is implemented. Each collected article that names a tracked company gets a frozen note (event type; Positive / Negative / Neutral / Mixed / Unclear; wording, reliability, evidence hash; the first session whose open follows publication). Labels come from narrow keyword rules that leave the unmatched as Unclear and never judge an earnings or guidance figure without its expectation. The owner can add their own note; it is a new version, never an edit. Gap, open-to-close and five-session reactions are written once when bars exist. Comparable history uses only reactions known when a note was written, counts syndicated copies once, and reports "Not enough history" below five cases. Notes and reactions are immutable in the database, and a test fails if the daily rule ever reads them. Decision kept: news has zero influence on calls until an evaluated challenger passes the gate in KNOWLEDGE_PLAN.md.

## 16. Review, options research and handoff (2026-09-08)

The owner requested review of the intervening agent’s work, concise formatted Telegram notes and a simple index-option workflow. See MEMORY.md for the durable handoff, telegram_templates.md for the implemented HTML message contract and INDEX_PLAN.md for proposed Nifty/Bank Nifty research. The Index lab calculator is educational; no real-time call/put strategy, income guarantee or order execution is enabled. News comparison and calendar bugs found in review were corrected without rewriting earlier notes or calls.
