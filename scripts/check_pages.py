"""Isolated local Pages simulation: real API, cross-origin auth, nested static path."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = root / '.venv/bin/python'
env = {**os.environ, 'APP_MODE': 'demo', 'OWNER_USER': 'ravi',
    'OWNER_PASSWORD': 'pages-browser-fixture-only',
    'DATABASE_URL': f'sqlite:///{root / "data/pages-browser-test.db"}',
    'FRONTEND_ORIGINS': 'http://127.0.0.1:14173', 'VITE_API_BASE_URL': 'http://127.0.0.1:18001'}
subprocess.run(['npm', 'run', 'build', '--', '--outDir', '../data/pages-preview/site', '--emptyOutDir'],
    cwd=root / 'frontend', env=env, check=True)
processes = []
try:
    processes.append(subprocess.Popen([str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '18001'],
        cwd=root / 'backend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    processes.append(subprocess.Popen([str(python), '-m', 'http.server', '14173', '--bind', '127.0.0.1',
        '--directory', str(root / 'data/pages-preview')], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for _ in range(60):
        if any(p.poll() is not None for p in processes): raise RuntimeError('A Pages test server failed to start.')
        try:
            urllib.request.urlopen('http://127.0.0.1:18001/api/session', timeout=1)
        except urllib.error.HTTPError as error:
            if error.code == 401: break
        except OSError: pass
        time.sleep(.25)
    else: raise RuntimeError('The test API did not start.')
    subprocess.run(['npm', 'exec', 'playwright', 'test', '--', '--config', 'playwright.pages.config.ts'],
        cwd=root / 'frontend', env=env, check=True)
finally:
    for process in processes: process.terminate()
    for process in processes:
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
