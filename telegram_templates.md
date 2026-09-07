# Message templates

Executable templates live in `backend/app/briefs.py`; both are limited to 4,000 characters and use saved records only. Sample messages always begin with `SAMPLE DATA`. Previewing a message does not send it.

Morning: date, market read, five buys, five sells, each call's confidence, expected closing range, stop, short reason, past right/total count, source tags, what could go wrong, previous result versus simply buying, assumptions.

Evening: results pending if the close is missing; otherwise paper money, simply buying, right/wrong/flat, all calls including losses, uncertain causes clearly stated, cumulative result, best/worst day, largest fall, improvement-review reminder.

Runtime delivery is a separate opt-in CLI job restricted to the single environment-configured chat ID. Duplicate delivery attempts are blocked even if a network failure leaves the status uncertain. Inspect Telegram before any manual retry. Messages are plain text, so imported content cannot inject Telegram Markdown.
