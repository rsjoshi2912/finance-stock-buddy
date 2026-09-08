# Telegram notes

The executable templates are in `backend/app/briefs.py`. Delivery uses Telegram `parse_mode=HTML`: bold headings, short rows, blank lines and one summary. Imported names, reasons and explanations are escaped before formatting. Messages remain within 4,000 UTF-16 text units after parsing, below Telegram's 4,096-character limit. The website renders only allowed tags as React elements; it never injects arbitrary HTML.

The preview endpoint provides both `text` (plain text) and `html`, plus `sent: false`. Opening a preview does not send anything. Scheduled delivery uses the same formatted message and retains private-chat verification and duplicate-attempt protection. A timeout is not permission to send again.

A morning note reads like this; the values here are illustrative:

```text
NIFTY SIGNAL · MORNING
08 Sep 2026 · IST
Paper journal · no real orders

Open → close · information received by 07:00 IST
Five-day price rule. Scores are unverified; news does not change these calls.

↑ BUY WATCHLIST · 5
RELIANCE · rule score 58%
Close range ₹1,350–1,390 · alert ₹1,330
Short price-based reason. Past: 0/0 right.
[Remaining saved names follow, including all five sell ideas.]

PREVIOUS RESULT
Our calls −₹18.00 · simply buying +₹12.00

KEEP IN MIND
Opening gaps, reversals and later news can change the picture.
₹1,000 per stock call · 0.15% assumed costs. Alerts are not guaranteed stop fills.
Indices: direction only, no call/put entry. Prices and source links are in the journal.
```

An evening note leads with net paper result, simply-buying result and their difference. It then lists every right, wrong and flat call, includes concise explanations for misses, names pending results and labels incomplete totals. It ends with cumulative results, best/worst day and largest fall from a peak. A correct direction can still lose after costs. Sample notes prominently say SAMPLE DATA.

No index-option alerts are sent by the Index lab. Its calculator uses user-entered assumptions, not a live contract feed.

Formatting reference: [Telegram Bot API](https://core.telegram.org/bots/api#formatting-options).
