"""Private local defaults. External services require explicit configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "data" / "nifty-signal.db"}')
MODE = os.getenv('APP_MODE', 'demo')
if MODE not in ('demo', 'live'):
    raise ValueError('APP_MODE must be demo or live')
ALLOCATION = 1000.0
COST_RATE = 0.0015
TIMEZONE = 'Asia/Kolkata'
