# Index option research plan

Updated 2026-09-08. The Index lab is an implemented learning screen and one-lot calculator. It does not fetch an option chain, produce entry signals, execute orders or send option alerts.

Start with Nifty 50; add Bank Nifty only after independently testing it. Other indices need an explicitly verified exchange contract and data adapter. Index points and option premiums are separate series: an index rising does not establish that a particular call will profit. Time remaining, volatility and the bid/ask spread matter. Contract expiry, tick and lot size must come from the current contract master, not a permanent constant. [NSE contract information](https://www.nseindia.com/static/products-services/equity-derivatives-contract-information), [Nifty contract and pricing information](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50).

## Capital and expectations

₹2,000–₹5,000 from ₹5,000–₹10,000 is 20%–100% in one day. Occasional trades can do this; the application cannot make it dependable or ensure profitable months. A daily target must never force an entry or increase size. The calculator uses an illustrative 1% account loss budget per trade and 2% per day. These are proposed learning limits, not a validated optimal sizing rule or guaranteed stop protection.

For example only, one 65-unit lot bought at ₹80 costs ₹5,200 before charges. An exit at ₹70 loses ₹650 before charges; an exit at ₹100 gains ₹1,300. With an assumed ₹60 round-trip fees/slippage buffer, those become ₹710 loss or ₹1,240 gain. A ₹10,000 account's illustrative 1% limit is ₹100, so this trade is rejected by the calculator even though the premium is affordable. The entire premium can be lost. None of these prices or the example lot size is a current trading recommendation. Fees must eventually be calculated for the exact broker, exchange, product and date.

## A candidate to test, not a proven method

Define one research rule before evaluating it: after the 09:15–09:30 IST opening range, require a completed five-minute candle beyond that range and a subsequent retest that holds in the same direction. Use a defined trend filter, such as five-minute EMA 20 vs EMA 50 and the direction of EMA 20. Calls study upside breaks; puts study downside breaks. Do not use spot-index volume to calculate VWAP: an index itself has no traded volume. A futures or ETF proxy requires a clearly identified series and basis check.

Initially exclude expiry sessions, wide spreads, stale/crossed quotes, unknown calendars and major scheduled announcements. Avoid short option writing, averaging a losing position and chasing a cheap far-out-of-the-money premium. Specify the spread limit, time of last entry, retest tolerance, time exit and maximum trades in the experiment record; test those choices chronologically rather than tuning to the same evaluation sample. This is a candidate design, not implemented signal logic.

## Data and controls before alerts

1. A permitted feed supplies timestamped index candles plus option bid/ask/depth, volume, open interest and contract identity (exchange, symbol, expiry, strike, CE/PE, lot size and tick). Keep publication, exchange and receipt times. Display partial/stale data and skip when required data is absent. Yahoo daily prices and five-minute polling of last-price snapshots cannot stand in for this.
2. Save option-chain snapshots, entry conditions, invalidation, intended exit, actual available quote and why a trade was skipped. Score option premiums: a spot-index backtest is insufficient. Conservative buy-at-ask/sell-at-bid assumptions, fees, slippage, latency, incomplete candles and non-fills must be included.
3. Keep an immutable option experiment journal separate from daily cash calls and model scores. Never rewrite existing cash forecasts. Record losses and no-trade sessions. Do not interpret the cash model's percentage as option win probability.
4. Test on later sessions and different market conditions, with contract rolls, expiries, changing lots and unavailable history handled explicitly. Then forward paper-test. Evaluate net expectancy, total drawdown, losing streaks, risk of account depletion and stability, not just win rate. A 60-session cash checkpoint does not validate an option strategy.
5. A future Telegram alert should fit on one phone screen: PAPER / LIVE status, exact contract, quote time, Call / Put / Skip, entry condition, invalidation, exit plan, whole lots, premium required, planned loss, full-premium exposure and a short reason. Sending one requires the option data and validation checks to pass. Missing data means Skip.

Broker adapters remain a later integration, as requested. Choose one whose permissions and live data terms cover these inputs; keep order execution a separate explicit scope.
