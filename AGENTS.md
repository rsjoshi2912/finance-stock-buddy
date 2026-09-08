# Start here

Read `MEMORY.md` for the latest handoff, then `CONTEXT.md` for the owner's requirements and `CLAUDE.md` for engineering constraints. The latest user instruction takes precedence over a stale handoff. Check Git status before changing files and preserve work left by another agent.

Keep all project edits, temporary files, test databases, screenshots and deployment archives inside `finance-stock-buddy`. Never print or commit `.env`, `.secrets`, databases or credentials. This repository is public; the running journal is authenticated.

Read `graphify-out/GRAPH_REPORT.md` before architecture work when available; use source code to verify inferred graph relationships. After code changes, run `graphify update .` locally. Do not run heavy research or builds on the small Oracle VM.

At the end of substantial work, update `MEMORY.md` with implemented behavior, checks actually run, deployment status and remaining tasks. Distinguish observations from assumptions. Do not claim automatic cross-chat recall: these repository files are the handoff.
