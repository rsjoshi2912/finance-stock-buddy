"""Concise Telegram HTML made only from saved journal records."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from html import escape
from html.parser import HTMLParser


def money(value):
    return ('−' if value < 0 else '+') + f'₹{abs(value):,.2f}'


def clean(value, limit=100):
    text = ' '.join(str(value or '').split())
    return escape(text if len(text) <= limit else text[:limit - 1] + '…', quote=False)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(message):
    parser = PlainText()
    parser.feed(message)
    return ''.join(parser.parts)


def validate(message):
    # Telegram counts parsed text. UTF-16 units also leave room for emoji.
    if not 0 < len(plain_text(message).encode('utf-16-le')) // 2 <= 4000:
        raise ValueError('Telegram message exceeds its text budget')
    return message


def header(data, period):
    day = date.fromisoformat(data['date']).strftime('%d %b %Y') if data.get('date') else 'No saved date'
    return [f'<b>NIFTY SIGNAL · {period}</b>', day + ' · IST',
            '<b>SAMPLE DATA · generated examples</b>' if data['mode'] == 'demo' else 'Paper journal · no real orders', '']


def morning(data):
    lines = header(data, 'MORNING')
    lines += ['Open → close · information received by 07:00 IST',
              'Five-day price rule. Scores are unverified; news does not change these calls.', '']
    if not data['calls']:
        return validate('\n'.join(lines + ['<b>No saved calls</b>', 'Nothing to act on. Check System health for the next scheduled run.']))
    for direction, label in [('UP', '↑ BUY WATCHLIST'), ('DOWN', '↓ SELL WATCHLIST')]:
        selected = [x for x in data['calls'] if x['direction'] == direction]
        lines.append(f'<b>{label} · {len(selected)}</b>')
        for p in selected:
            unit = '' if p.get('kind') == 'index' else '₹'
            lines += [f'<b>{clean(p["symbol"], 30)}</b> · rule score {p["confidence"]}%',
                      f'Close range {unit}{p["expected_low"]:,.0f}–{p["expected_high"]:,.0f} · alert {unit}{p["stop"]:,.0f}',
                      f'{clean(p["reason"], 85)} Past: {p["past_right"]}/{p["past_total"]} right.']
        lines.append('')
    previous = data['yesterday_summary']
    lines += ['<b>PREVIOUS RESULT</b>',
              f'Our calls {money(previous["pnl"])} · simply buying {money(previous["baseline_pnl"])}' if previous.get('days', 0)
              else 'No completed previous session yet.', '',
              '<b>KEEP IN MIND</b>', 'Opening gaps, reversals and later news can change the picture.',
              '₹1,000 per stock call · 0.15% assumed costs. Alerts are not guaranteed stop fills.',
              'Indices: direction only, no call/put entry. Prices and source links are in the journal.']
    return validate('\n'.join(lines))


def evening(data):
    lines = header(data, 'EVENING')
    calls = [x for x in data['calls'] if x['result'] != 'Pending']
    pending = [clean(x['symbol'], 30) for x in data['calls'] if x['result'] == 'Pending']
    if not calls:
        return validate('\n'.join(lines + ['<b>Results pending</b>', 'Closing prices are not ready. Nothing has been scored yet.']))
    pnl = sum(x['pnl'] or 0 for x in calls)
    baseline = sum(x['baseline_pnl'] or 0 for x in calls)
    lines += [f'<b>PAPER RESULT {money(pnl)}</b>', f'Simply buying {money(baseline)} · difference {money(pnl - baseline)}',
              ' · '.join(f'{sum(x["result"] == label for x in calls)} {label.lower()}' for label in ('Right', 'Wrong', 'Flat')), '']
    if pending:
        lines += [f'Partial results: {len(pending)} still pending ({", ".join(pending)}). Totals may change.', '']
    for label, icon in [('Right', '✓'), ('Wrong', '✗'), ('Flat', '—')]:
        selected = [x for x in calls if x['result'] == label]
        if not selected:
            continue
        lines.append(f'<b>{label.upper()}</b>')
        for call in selected:
            result = money(call['pnl']) if call['pnl'] is not None else 'Index: direction only'
            lines.append(f'{icon} <b>{clean(call["symbol"], 30)}</b> · {result}')
            if label == 'Wrong':
                lines.append(clean(call.get('explanation') or 'Cause not established.', 100))
        lines.append('')
    summary = data['summary']
    lines += ['<b>SINCE START</b>', f'Our calls {money(summary["pnl"])} · simply buying {money(summary["baseline_pnl"])}',
              f'Best day {money(summary["best_day"])} · worst {money(summary["worst_day"])}',
              f'Largest fall from a peak ₹{summary["max_drawdown"]:,.2f}', '',
              'Paper results after assumed costs; personal income tax excluded.',
              'A right direction can still lose after costs. No rule changes were applied.']
    return validate('\n'.join(lines))


def indices(data):
    lines=['<b>NIFTY SIGNAL · INDEX CHECK</b>', 'Paper research · unvalidated · no orders', '']
    for row in data['indices']:
        direction={'UP':'UP BIAS','DOWN':'DOWN BIAS','SKIP':'SKIP'}[row['direction']]
        option=row['option']
        action={'BUY_CALL':'BUY CALL · PAPER','BUY_PUT':'BUY PUT · PAPER','SKIP':'SKIP OPTION'}[option['action']]
        checked = datetime.fromisoformat(row['assessed_at']).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %H:%M:%S IST') if row.get('assessed_at') else 'No saved check'
        lines += [f'<b>{clean(row["name"])} · {direction}</b>',clean(row['reason'],200),
                  f'Checked: {clean(checked,40)}',
                  f'<b>{action}</b>',clean(option['reason'],200)]
        if option.get('contract'):
            lines.append(clean(option['contract']['name'],100))
        if option.get('entry') is not None:
            lines += [f'Paper entry ₹{option["entry"]:,.2f} · stop ₹{option["stop"]:,.2f} · target ₹{option["target"]:,.2f}',
                      f'1 lot · planned loss ₹{option["planned_loss"]:,.2f} · full premium + buffer ₹{option["premium_at_risk"]:,.2f}']
        lines.append('')
    lines += ['Source: Yahoo five-minute candles; may be delayed. News is not used by this rule.',
              'An index direction is not a guaranteed option profit. Stops can fill worse than planned.',
              'Snapshot only. Open Index lab for current expiry and source status.']
    return validate('\n'.join(lines))
