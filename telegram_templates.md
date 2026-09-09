# Telegram notes

The executable templates are in `backend/app/briefs.py`. Delivery uses Telegram `parse_mode=HTML`: bold headings, short rows, blank lines and one summary. Imported names, reasons and explanations are escaped before formatting. Messages remain within 4,000 UTF-16 text units after parsing, below Telegram's 4,096-character limit. The website renders only allowed tags as React elements; it never injects arbitrary HTML.

The preview endpoint provides both `text` (plain text) and `html`, plus `sent: false`. Opening a preview does not send anything. Scheduled delivery uses the same formatted message and retains private-chat verification and duplicate-attempt protection. A timeout is not permission to send again.

A morning note reads like this; the values are illustrative, not saved forecasts. The count is dynamic, up to ten, and empty direction sections are omitted:

```text
NIFTY SIGNAL · MORNING
DD Mon YYYY · IST
SAMPLE DATA · generated examples

2 calls · open → close · cutoff 07:00 IST
Five-day trend · uncalibrated rule scores

↑ BUY WATCHLIST · 2
RELIANCE · rule score 58%
Close range ₹1,350–1,390 · alert ₹1,330
Short price-based reason. Past: 0/0 right.
TCS · rule score 56%
Close range ₹3,280–3,360 · alert ₹3,250
Short price-based reason. Past: 0/0 right.

PREVIOUS RESULT
Our calls −₹18.00 · simply buying +₹12.00

₹1,000 per stock · 0.15% assumed costs · indices scored for direction only.
Details and sources in the journal.
```

An evening note leads with net paper result, simply-buying result and their difference. It then lists every right, wrong and flat call, includes concise explanations for misses, names pending results and labels incomplete totals. It ends with cumulative results, best/worst day and largest fall from a peak. A correct direction can still lose after costs. Sample notes prominently say SAMPLE DATA.

Index lab has a separate owner-only preview at `GET /api/indices/brief`: **INDEX CHECK**, paper status, Nifty / Bank Nifty direction, short reason, check time in IST and Call / Put / Skip. Validated contract details and research premium levels appear when available. Text is escaped and kept under the existing parsed-message limit. No automatic index alerts are sent. The optional one-lot calculator remains separate and uses user-entered assumptions. Live daily notes use one Paper journal label; sample notes retain SAMPLE DATA.

Formatting reference: [Telegram Bot API](https://core.telegram.org/bots/api#formatting-options).

## Empty batches and historical skipped days

Any nonempty list receives a regular morning/evening note, even with fewer than ten calls or only one direction. An empty daily list produces a short **NO CALLS TODAY** note at the usual schedule, with the recorded reason. Pending outcomes within a nonempty list are reported as pending, not as missing calls.

Both paths use the same verified private chat and once-only `telegram:{period}:{day}` claim. An ambiguous attempt is not automatically retried. A no-calls evening note does not claim that closing results are pending. Preview remains read-only. The historical September 9 3-Buy/17-Sell skip and confirmed status delivery remain unchanged; the later policy does not backfill forecasts or replay that message.
