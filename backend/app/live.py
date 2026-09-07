"""Explicit live setup commands. Credentials are never printed."""
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select

from .config import MODE
from .db import initialize, SessionLocal
from .market import IST, MarketError, create_provider, provider_id, mappings, import_mapping, ingest_daily, market_session, previous_session, refresh_quotes
from .models import InstrumentMapping, Instrument, JobRun, Setting
from .ingest import now, import_instruments
from .news import collect_news
from .scheduler import require_live

def telegram_chats(transport=None):
    token=os.getenv('TELEGRAM_BOT_TOKEN')
    if not token: raise MarketError('Save TELEGRAM_BOT_TOKEN in the project .env first.')
    try:
        with httpx.Client(timeout=20,transport=transport,follow_redirects=False) as client:
            response=client.get(f'https://api.telegram.org/bot{token}/getUpdates',params={'timeout':0,'limit':100})
            if response.status_code!=200: raise MarketError('Telegram could not list chats. Check the bot token.')
            payload=response.json()
            if not payload.get('ok'): raise MarketError('Telegram could not list chats.')
            ids=set()
            for update in payload['result']:
                message=update.get('message',{})
                chat=message.get('chat',{})
                if chat.get('type')=='private' and message.get('text','').startswith('/start'):
                    ids.add(str(chat['id']))
            return {'private_chat_ids':sorted(ids),'message_sent':False,
                'next_step':'Set TELEGRAM_CHAT_ID to your own chat ID, then run telegram-check.' if ids else 'Open your bot in Telegram and send /start, then retry.'}
    except (httpx.HTTPError,json.JSONDecodeError):
        raise MarketError('Telegram could not be reached. No message was sent.') from None

def telegram_check(transport=None):
    token, chat = os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat: raise MarketError('Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID on the server.')
    try:
        with httpx.Client(timeout=20, transport=transport, follow_redirects=False) as client:
            bot = client.get(f'https://api.telegram.org/bot{token}/getMe')
            target = client.get(f'https://api.telegram.org/bot{token}/getChat', params={'chat_id': chat})
            if bot.status_code != 200 or target.status_code != 200:
                raise MarketError('Telegram check failed. Confirm the bot token, chat ID, and that you sent /start to your bot.')
            b, t = bot.json(), target.json()
            if not b.get('ok') or not t.get('ok') or t['result'].get('type') != 'private':
                raise MarketError('Use a private chat with your own bot for this personal journal.')
            if str(t['result']['id']) != chat:
                raise MarketError('Telegram returned a different chat ID.')
            return {'bot_verified': True, 'private_chat_verified': True, 'message_sent': False}
    except (httpx.HTTPError, json.JSONDecodeError):
        raise MarketError('Telegram could not be reached. No message was sent.') from None

def doctor(session):
    required = ['OWNER_PASSWORD', 'FRONTEND_ORIGINS']
    if provider_id() == 'upstox': required.append('UPSTOX_ACCESS_TOKEN')
    configured = {key: bool(os.getenv(key)) for key in required}
    try: count = len(mappings(session, datetime.now(IST).date().isoformat(), provider_id()))
    except MarketError: count = 0
    mode = session.get(Setting, 'dataset_mode')
    ready = MODE == 'live' and all(configured.values()) and count >= 10 and (not mode or mode.value == 'live')
    return {'mode': MODE, 'market_provider': provider_id(), 'broker_key_required': provider_id() == 'upstox',
        'configured': configured, 'mapped_instruments': count,
        'telegram_configured': bool(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID')),
        'telegram_enabled': os.getenv('TELEGRAM_ENABLED') == 'true',
        'configuration_ready': ready, 'external_connections_verified': False}

def main():
    parser = argparse.ArgumentParser(description='Set up Nifty Signal live services')
    parser.add_argument('command', choices=['doctor', 'import-universe', 'bootstrap', 'quotes', 'news', 'starter-universe', 'telegram-check','telegram-chats'])
    parser.add_argument('--file')
    parser.add_argument('--end', help='Last daily candle date to request, inclusive; defaults to the previous verified session.')
    args = parser.parse_args(); initialize()
    if args.command=='telegram-chats': print(json.dumps(telegram_chats(),indent=2)); return
    with SessionLocal() as session:
        if args.command == 'doctor': print(json.dumps(doctor(session), indent=2)); return
        if args.command!='telegram-check': require_live(session)
        if args.command == 'telegram-check':
            result = telegram_check()
            verified = session.get(Setting, 'telegram_verified_at')
            if verified: verified.value = now()
            else: session.add(Setting(key='telegram_verified_at', value=now()))
            verified_chat = session.get(Setting, 'telegram_verified_chat_id')
            if verified_chat: verified_chat.value = os.environ['TELEGRAM_CHAT_ID']
            else: session.add(Setting(key='telegram_verified_chat_id', value=os.environ['TELEGRAM_CHAT_ID']))
        elif args.command == 'import-universe':
            if not args.file: raise MarketError('--file must point to a verified universe CSV.')
            result = (import_mapping if provider_id() == 'upstox' else import_instruments)(session, Path(args.file).read_text())
        elif args.command == 'starter-universe':
            from .public_data import starter_universe
            result = starter_universe(session)
        elif args.command == 'news':
            result = collect_news(session)
        else:
            provider = create_provider()
            try:
                day = datetime.now(IST).date().isoformat()
                if args.command == 'quotes':
                    try: market_session(session, provider, day, refresh=True)
                    except MarketError: pass  # The API explicitly shows unconfirmed hours.
                    result = refresh_quotes(session, provider)
                else:
                    end = args.end or previous_session(session, provider, day)
                    result = ingest_daily(session, provider, end)
            finally: provider.close()
        session.add(JobRun(job=args.command, status='ok', rows=0, detail=str(result), started_at=now()))
        session.commit(); print(result)

if __name__ == '__main__': main()
