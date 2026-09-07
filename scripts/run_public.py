"""Run the private public-data preview or worker using project-local credentials."""
import argparse
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('service', choices=['web', 'worker'])
parser.add_argument('--port', type=int, default=8001)
args = parser.parse_args()
config = root / '.secrets/public.env'
if not config.exists(): raise SystemExit('Create .secrets/public.env as described in PUBLIC_DATA.md first.')
values = dotenv_values(config)
if values.get('APP_MODE') != 'live' or not values.get('OWNER_PASSWORD'):
    raise SystemExit('The public-data preview requires live mode, a separate database and an owner password.')
os.environ.update({key: value for key, value in values.items() if value is not None})
os.chdir(root / 'backend')
command = [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.port)] if args.service == 'web' else [sys.executable, '-m', 'app.scheduler']
os.execv(sys.executable, command)
