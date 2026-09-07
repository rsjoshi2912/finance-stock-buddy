# News and market knowledge plan

Status: design requirements, not a claim of implemented news prediction. Updated 2026-09-07 after the owner's request to learn how past news relates to positive and negative stock reactions.

## What exists today

The daily rule uses five-day price momentum. The app can import timestamped news, save sources with a call, and filter evidence by publication and receipt time. An optional FinBERT function and a sentiment feature exist in the research module. Public RSS collection is now implemented with source health, dated revisions and conservative company-name matching; see PUBLIC_DATA.md. Event classification, historical event comparisons and a validated combined model are still to be built. Attaching a news source to a call does not mean that news influenced its probability.

## What the system should remember

| Knowledge | What we save | What it helps us investigate |
| --- | --- | --- |
| Prices and trading activity | Adjusted daily prices, volume, volatility, index and sector moves; later intraday bars and spreads from a suitable provider | Trends, liquidity and the movement available after entry |
| Company announcements | Results, outlook, orders, cancellations, financing, debt, management changes, investigations, corporate actions and their original documents | What changed for this company and how material it was |
| Latest news | Source, permitted text or excerpt, publication time, first receipt time, revisions and affected companies | New information, confirmation, conflicting reports and continuing stories |
| Company background | Sector, revenue exposure, debt, margins, previous results and guidance, all with release dates | Why the same event may affect companies differently |
| Wider market | Nifty and sector indices, India VIX, RBI releases, inflation, currency, oil, global markets and published institutional flows | Conditions surrounding a company event |
| Past events and results | Frozen event assessments, comparable earlier cases, subsequent price paths and simulated results after costs | Whether a type of information adds predictive value |

These are separate linked records in the existing database. A searchable document collection can support explanations, but retrieving similar articles is not itself a trading model. Avoid adding a separate vector database until retrieval needs justify it.

## Sources and availability

Start with exchange disclosures and company investor-relations releases. NSE provides a [corporate announcements page](https://www.nseindia.com/companies-listing/corporate-filings-announcements). Use [RBI releases](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx) for relevant policy facts. Add BSE/company documents and permitted publisher feeds as each connector is verified. The publishers named in CONTEXT.md are candidates, not confirmed working integrations.

Verify automated access, usage rights, timestamps, archive coverage and update delays for each source before enabling it. A public web page is not a promise of a stable free API or a complete historical archive. Upstox price access does not supply all of this knowledge. Some archives or expectation datasets may need a separate subscription; no purchase is authorized by this plan.

For each source, expose last successful collection, latest item time, coverage and failures in System health. Missing news must be shown as unknown coverage, not interpreted as neutral news. Missing expectations must remain unknown rather than be inferred from the later price reaction.

## Classify an event in two separate ways

First record **what happened**: earnings, guidance, order/contract, debt/credit, regulation/legal, management/governance, merger/financing, corporate action, commodity/currency, policy, or other. A story can contain more than one event.

Then record the **expected effect for each affected company and horizon**: Positive, Negative, Neutral, Mixed, or Unclear. Preserve the supporting facts, material size relative to the company, whether it was expected, whether it is new, and source reliability. A reported claim and an exchange-confirmed event are different evidence states. One article can imply different effects for different companies.

Keep three quantities separate:

- Text sentiment: whether the wording sounds positive, negative or neutral.
- Event assessment: a hypothesis about the company's business or stock, with an explicit horizon.
- Price probability: the separately tested model's estimate for the chosen trade horizon.

[FinBERT's model card](https://huggingface.co/ProsusAI/finbert) describes financial-text classification with positive, negative and neutral outputs. Its label confidence is not a stock-return probability. Mixed and Unclear require explicit event logic or a separately evaluated extractor. English-only text processing must expose unsupported languages and any translation step.

Example, for illustration only: a company reports profit growth of 20%. The growth is a positive accounting fact, but an available pre-release expectation of 30% would make it a disappointment. If no reliable expectation was available, the system must say so. Even a positive surprise may have been reflected in the opening price before our paper entry.

## Link news to measured reactions

For every eligible event, save the assessment before the outcome. Later attach observed results without rewriting that assessment:

- Overnight gap: previous close to next open. This is separate from the current strategy's open-to-close profit.
- Trading-session move: open to close, matching the existing daily scorecard.
- One- and five-session changes for longer reaction studies, labelled as separate research horizons.
- Moves relative to the broad market and the company's sector, with the chosen benchmark and method recorded.
- Intraday reaction windows only when verified intraday history is available. Daily bars cannot establish a 15-minute reaction or the sequence of stop/target touches.

An after-close release belongs to the next eligible session; a release during trading needs a post-release window, not the entire day's return. Save event publication, receipt, assessment, prediction and outcome-availability times separately. Concurrent announcements and other market news are potential alternative explanations. Describe these as observed reactions or possible explanations, not proof that an article caused a move.

Find earlier comparisons using event type, surprise size, company/sector, liquidity, market conditions and comparable entry timing. Prefer the same company when enough cases exist; show clearly when the comparison broadens to its sector or other companies. Do not use headline similarity alone.

Show the number of independent earlier events, date span, median return, downside, range of outcomes, and the share positive after costs for a defined simulated trade. Deduplicate syndicated reports into one underlying event; 30 copied headlines are not 30 confirmations. Few cases should produce an explicit "Not enough history" label and conservative model influence. A historical percentage is not automatically a calibrated probability for today's stock.

Learn from neutral events, failures and unselected eligible stocks too. Avoid constructing the dataset only from memorable news or the ten selected calls.

## Prevent hindsight

Morning inputs must satisfy both publication and actual receipt at or before 07:00 IST. Save each article revision and its own arrival time; never overwrite a morning version with an evening correction. Keep the extractor/model version and exact evidence snapshot used for each assessment. Automated extractors must base facts on supplied documents and preserve source references, not fill gaps from model memory.

An archive downloaded today can support a clearly labelled historical research study with documented timestamp limitations. It cannot become evidence that our system received an article in the past. Keep those studies distinct from the growing live paper record.

Comparable cases and training outcomes must have finished and been available before the forecast being evaluated. Five-session outcomes need an appropriate gap before a later training/evaluation boundary. Reuse neither later outcomes nor later expectation revisions in earlier features. Training and evaluation split whole dates across all stocks; the same news cluster must not leak between them.

Collect later news for monitoring and the evening review. News received after 07:00 cannot change that morning's saved calls. A future intraday call would need its own timestamp, entry assumption, outcome and evaluation; it is not part of the current open-to-close strategy.

## How we decide whether news helps

Compare the existing price-only rule, a news-only research model and a combined model on the same eligible universe, periods, horizons and cost assumptions. Evaluate predictions across the common universe; also compare each strategy's selected portfolio and retain the existing always-buy comparison on the exact selected names.

Check probability reliability, performance after costs, drawdown, coverage, and results by event category and market condition. Reserve later unseen dates and then collect forward paper results. Set selection and promotion criteria before looking at the reserved outcomes. Do not tune categories repeatedly against the final test period.

The existing 60-day comparison is a minimum project checkpoint, not proof of a profitable strategy or adequate samples in every event category. News features only gain influence after an evaluated challenger passes the applicable gate. If they do not improve results, keep their influence at zero. No fixed news/price weighting, 80% accuracy claim or daily profit guarantee is justified in advance.

The existing requirement to record five Buy and five Sell research calls remains. Low-confidence calls must stay visible as such; a missing feed or weak evidence must never create a fabricated high-confidence reason.

## What the owner sees

Add plain-language details inside the existing stock/call view:

- **What happened** — short factual summary and original sources.
- **Possible effect** — Positive / Negative / Neutral / Mixed / Unclear, for this company and horizon.
- **Why it matters** — material facts, what was expected if known, and alternative explanations.
- **What happened before** — comparable-event count, scope and measured outcomes; "Not enough history" when appropriate.
- **Already moved?** — movement observed before that assessment, with its timestamp. Never insert the later opening gap into a 07:00 forecast.
- **What we don't know** — missing sources, expectations, conflicting reports or limited examples.

The evening view keeps the original assessment beside the actual result. It can say "Positive news, but the stock fell after opening" without altering the original record or inventing a certain cause.

## Build sequence

1. Collect timestamped official events and permitted news; implement source health, revisions, event deduplication and company mapping. Keep the price baseline in control.
2. Add versioned event assessments and matched outcome records. Test late/corrected news, duplicate headlines, ambiguous companies, missing expectations, cutoff boundaries, and gap versus open-to-close outcomes.
3. Build historical comparison pages and a labelled research dataset with explicit archive limitations. Begin forward collection immediately once feeds are ready.
4. Evaluate text/event extraction and a combined challenger using chronological testing and probability checks. Add influence only when measured results justify it.
5. Add intraday event studies and F&O inputs only as separate, validated extensions. A cash-stock direction model is insufficient to assess option premium changes, spread, volatility or expiry effects.

The observed Oracle VM has approximately 1 GB RAM. Until measured otherwise, keep web serving and collection lightweight and run model training/text batches on a separate suitable machine. Do not assume the original brief's larger ARM VM resources are available.
