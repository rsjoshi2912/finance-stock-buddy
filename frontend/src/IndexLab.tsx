import { useState } from 'react';
import IndexSignals from './IndexSignals';
import { ArrowDownRight, ArrowUpRight, Calculator, CirclePause, Info } from 'lucide-react';

const rupees = (value: number) => `₹${value.toLocaleString('en-IN', {maximumFractionDigits: 2, minimumFractionDigits: 2})}`;
const number = (value: string) => value.trim() === '' ? NaN : Number(value);
const cents = (value: number) => Math.round(value * 100);

export default function IndexLab() {
  const [capital, setCapital] = useState('10000'), [goal, setGoal] = useState('2000');
  const [entry, setEntry] = useState(''), [stop, setStop] = useState(''), [target, setTarget] = useState('');
  const [lot, setLot] = useState(''), [cost, setCost] = useState('60');
  const [side, setSide] = useState('Call (CE)'), [index, setIndex] = useState('Nifty 50');
  const [example, setExample] = useState(false);
  const capitalN = number(capital), goalN = number(goal), lotN = number(lot);
  const values = [capitalN, number(entry), number(stop), number(target), lotN, number(cost)];
  const valid = values.every(Number.isFinite) && values.every(x => x >= 0 && x <= 1e8)
    && capitalN > 0 && number(entry) > number(stop) && number(target) > number(entry)
    && lotN > 0 && lotN <= 100000 && Number.isInteger(lotN) && cents(number(entry)) > cents(number(stop))
    && cents(number(target)) > cents(number(entry));
  const budget = Math.floor(cents(capitalN) * .01) / 100;
  const entryN = cents(number(entry)) / 100, stopN = cents(number(stop)) / 100;
  const targetN = cents(number(target)) / 100, costN = cents(number(cost)) / 100;
  const funding = valid ? (cents(entryN) * lotN + cents(costN)) / 100 : 0;
  const plannedLoss = valid ? ((cents(entryN) - cents(stopN)) * lotN + cents(costN)) / 100 : 0;
  const targetProfit = valid ? ((cents(targetN) - cents(entryN)) * lotN - cents(costN)) / 100 : 0;
  const fits = valid && funding <= capitalN && plannedLoss <= budget;
  const validGoal = Number.isFinite(goalN) && goalN > 0 && goalN <= 1e8;
  const validCapital = Number.isFinite(capitalN) && capitalN > 0 && capitalN <= 1e8;
  const inputs = [
    {label: 'Entry premium (₹ per unit)', value: entry, change: setEntry},
    {label: 'Exit if wrong (₹ per unit)', value: stop, change: setStop},
    {label: 'Exit if right (₹ per unit)', value: target, change: setTarget},
    {label: 'Units in one lot', value: lot, change: setLot, integer: true},
    {label: 'Fees + slippage buffer (₹ per lot, round trip)', value: cost, change: setCost},
  ];
  return <div className="index-lab"><IndexSignals/>
    <section className="panel index-status"><div><span className="badge amber"><CirclePause size={13}/> Understand the method</span>
      <h2>Study the trade before risking the money.</h2><p>Start with Nifty 50. A rise in the index does not guarantee a profit on a call: its price also changes with time, volatility and the buy/sell spread.</p></div>
      <p className="index-status-note">The index rule runs on completed five-minute candles. Option candidates also need a current contract and quote. Today’s stock calls do not trigger option trades.</p></section>
    <div className="two-columns index-methods">
      <section className="panel"><h3><ArrowUpRight size={18}/> Call idea to test</h3><p>After 09:40 IST, study a break above the first 15 minutes’ high, followed by a retest that holds. Require a rising short-term trend and a liquid option near the index level.</p></section>
      <section className="panel"><h3><ArrowDownRight size={18}/> Put idea to test</h3><p>Study a break below the first 15 minutes’ low, followed by a retest that fails to recover. Require a falling short-term trend. Skip sideways markets, wide spreads and stale prices.</p></section>
    </div>
    <p className="quote-note">The paper rule checks an opening-range break and the immediately following five-minute retest, with a matching 20/50-period trend. It is not a proven method. Expiry sessions and major scheduled news need separate testing.</p>
    <section className="panel"><div className="panel-head"><div><h2><Calculator size={17}/> Does one lot fit?</h2><p>Buying a call or put only. All prices below are your assumptions.</p></div>
      <button className="button secondary small" onClick={() => {setEntry('80'); setStop('70'); setTarget('100'); setLot('65'); setCost('60'); setExample(true);}}>Try an example</button></div>
      <div className="index-calculator">
        <div className="index-inputs">
          <label>Account capital (₹)<input type="number" min="1" max="100000000" value={capital} onChange={e => setCapital(e.target.value)}/></label>
          <label>Daily goal to examine (₹)<input type="number" min="1" max="100000000" value={goal} onChange={e => setGoal(e.target.value)}/></label>
          <label>Index to study<select value={index} onChange={e => {setIndex(e.target.value); setLot(''); setEntry(''); setStop(''); setTarget(''); setExample(false);}}>{['Nifty 50', 'Bank Nifty'].map(x => <option key={x}>{x}</option>)}</select></label>
          <label>Option to study<select value={side} onChange={e => setSide(e.target.value)}><option>Call (CE)</option><option>Put (PE)</option></select></label>
          {inputs.map(x => <label key={x.label}>{x.label}<input type="number" min="0" max="100000000" step={x.integer ? '1' : '.01'} value={x.value} onChange={e => x.change(e.target.value)}/></label>)}
          <p className="small-text">{example ? 'Example assumptions loaded, not market quotes. ' : ''}Confirm the lot size for the exact expiry in the <a href="https://www.nseindia.com/static/products-services/equity-derivatives-contract-information" target="_blank" rel="noreferrer">NSE contract file</a>. The buffer is an estimate, not a broker charge quote.</p>
        </div>
        <div className="index-results" aria-live="polite">
          <span className={`badge ${fits ? 'blue' : 'amber'}`}>{fits ? 'Fits the example limits · paper only' : valid ? 'Skip: one lot exceeds a limit' : 'Enter prices and a verified lot size'}</span>
          <h3>{index} · {side}</h3>
          {validCapital && <p>Learning limits: {rupees(budget)} per trade (1%) and {rupees(budget * 2)} per day (2%). These are loss limits, not income targets.</p>}
          {validGoal && validCapital && <p className="goal-context">Your goal needs <strong>{(goalN / capitalN * 100).toFixed(1)}% in a day</strong>. Changing the goal never increases the position size. Profit is not assured.</p>}
          {valid ? <dl>
            <div><dt>Cash needed for one lot + buffer</dt><dd data-testid="option-funding">{rupees(funding)}</dd></div>
            <div><dt>Loss if the planned exit fills</dt><dd data-testid="option-stop-loss">{rupees(plannedLoss)}</dd></div>
            <div><dt>Possible full premium loss + buffer</dt><dd>{rupees(funding)}</dd></div>
            <div><dt>Net result if the target exit fills</dt><dd data-testid="option-target" className={targetProfit > 0 ? 'positive' : 'negative'}>{rupees(targetProfit)}</dd></div>
            {validGoal && <div><dt>Exit premium needed for your daily goal in one lot</dt><dd>{rupees(entryN + (goalN + costN) / lotN)}</dd></div>}
          </dl> : <p>Use a positive entry, an exit-if-wrong below entry, an exit-if-right above it, and a whole-number lot size. Empty or invalid inputs do not create a result.</p>}
          <p className="index-warning"><Info size={16}/>A stop may fill late or at a worse price. The entire premium can be lost. A cheap option can still exceed the amount you can afford to lose.</p>
        </div>
      </div>
    </section>
    <section className="panel index-next"><h3>Before considering real-money trading</h3><ol>
      <li>Connect fresh index candles and a permitted option feed with bid, ask, volume, expiry and current lot sizes.</li>
      <li>Record each paper entry and exit using option prices, including costs and worse fills. Keep skipped trades and losses.</li>
      <li>Test on later sessions the rule has never seen. Compare net profit, drawdown and losing streaks, then forward-test.</li>
    </ol><p>Free Yahoo prices remain useful for research. The current delayed snapshots are not enough to time an option entry.</p></section>
  </div>;
}
