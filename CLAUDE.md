# Engineering brief

Read AGENTS.md and MEMORY.md to resume, then CONTEXT.md and README.md. The owner approved the standard short-position profit formula on 2026-09-06. See the clarification appended to CONTEXT.md.

- React + TypeScript + Vite frontend; FastAPI + SQLAlchemy backend. SQLite for local demo; PostgreSQL driver and schema support for deployment.
- One immutable prediction row; its one-time outcome is a separate immutable row. Database triggers enforce both protections.
- All feature queries pass through explicit cutoff readers. Compare both publication and actual arrival timestamps in normalized UTC. Do not backdate observations to create apparent historical live results.
- Every screen must identify generated data. Do not enable F&O or claim a trained model, calibrated confidence, or live service merely because sample statistics look good.
- `momentum_research_v1` is an uncalibrated research rule. `baseline_always_up` is a fixed 0.53 reference. Neither is an established success rate.
- No real-order API exists. Telegram delivery is separately disabled by default. No setup command should send messages or provision cloud infrastructure.
- Approved improvement ideas are queued, not applied. Existing forecasts do not change.
- Keep interface text simple. Prefer explaining a result over exposing statistical jargon.
- Owner approval 2026-09-09: use up to ten ranked available daily candidates overall, with no five-per-direction minimum. Fewer calls and one-sided days are valid; never rerank or backfill existing days.
- Keep the interface data-focused: one paper/sample label, actionable status, optional method/source details. Remove repetitive investment warnings and inactive placeholders, not data-quality checks.
- Backend checks: `cd backend && ../.venv/bin/python -m pytest -q`.
- Frontend checks: `cd frontend && npm run build && npm run test:e2e` (requires API on port 8000 and Chrome).
