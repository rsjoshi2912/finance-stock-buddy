def money(value):
    return ('−' if value<0 else '+')+f'₹{abs(value):,.2f}'

def morning(data):
    lines=[f'NIFTY SIGNAL · {data["date"]}', 'SAMPLE DATA — not real market calls' if data['mode']=='demo' else 'Personal paper journal',
        'Morning view: five-day price trends. Confidence is unverified.','']
    for direction,label in [('UP','BUY'),('DOWN','SELL')]:
        lines.append(label)
        for p in [x for x in data['calls'] if x['direction']==direction]:
            lines.append(f'{p["symbol"]} · {p["confidence"]}% · ₹{p["expected_low"]:,.0f}–{p["expected_high"]:,.0f} · stop ₹{p["stop"]:,.0f}')
            lines.append(f'{p["reason"][:145]} Past: {p["past_right"]} of {p["past_total"]} right. [Prices]')
        lines.append('')
    prev=data['yesterday_summary']
    lines += ['What could go wrong: news after 07:00, opening gaps, or a reversal.',
        f'Previous day: {money(prev["pnl"])} · simply buying {money(prev["baseline_pnl"])}.',
        'Sources: generated price history.' if data['mode']=='demo' else 'Sources: imported price history; full links in your local journal.',
        '₹1,000 per stock call; 0.15% assumed costs. Indices not traded. Stops are alerts, not simulated fills.',
        'Signals, not advice. No orders placed.']
    result='\n'.join(lines)
    if len(result)>4000:raise ValueError('Morning message exceeds Telegram budget')
    return result

def evening(data):
    calls=[x for x in data['calls'] if x['result']!='Pending']
    pending=[x['symbol'] for x in data['calls'] if x['result']=='Pending']
    lines=[f'NIFTY SIGNAL · EVENING · {data["date"]}', 'SAMPLE DATA' if data['mode']=='demo' else 'Personal paper journal']
    if not calls:return '\n'.join(lines+['Results pending. The closing price file is not ready. Nothing has been scored yet.'])
    pnl=sum(x['pnl'] or 0 for x in calls);base=sum(x['baseline_pnl'] or 0 for x in calls)
    lines += [f'Today: {money(pnl)} · simply buying: {money(base)}',
        f'{sum(x["result"]=="Right" for x in calls)} right · {sum(x["result"]=="Wrong" for x in calls)} wrong','']
    if pending:
        lines += [f'Partial results: {len(pending)} still pending ({", ".join(pending)}). Totals may change.','']
    for label in ['Right','Wrong','Flat']:
        for c in [x for x in calls if x['result']==label]:
            lines.append(f'{label}: {c["symbol"]} · {money(c["pnl"]) if c["pnl"] is not None else "Index: direction only"}')
            if label=='Wrong':lines.append(c['explanation'] or 'Cause not established.')
    s=data['summary']
    lines += ['',f'Since start: {money(s["pnl"])} · simply buying: {money(s["baseline_pnl"])}',
        f'Best: {money(s["best_day"])} · worst: {money(s["worst_day"])} · largest fall: ₹{s["max_drawdown"]:,.2f}',
        f'Last {min(s["days"],60)} sessions: see the matched scorecard in your journal.',
        'Improvement ideas need your review. No changes were applied.', 'Signals, not advice. Costs included; personal income tax excluded.']
    result='\n'.join(lines)
    if len(result)>4000:raise ValueError('Evening message exceeds Telegram budget')
    return result
