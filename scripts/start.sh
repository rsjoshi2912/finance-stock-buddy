#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo 'Create .venv and install backend/requirements.txt first. See README.md.' >&2
  exit 1
fi
if [[ ! -f "$PROJECT_DIR/frontend/dist/index.html" ]]; then
  echo 'Run npm install and npm run build in frontend first.' >&2
  exit 1
fi
cd "$PROJECT_DIR/backend"
exec "$PROJECT_DIR/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
