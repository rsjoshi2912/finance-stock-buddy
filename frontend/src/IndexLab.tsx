import { useState } from 'react';
import IndexSignals from './IndexSignals';
import { Calculator } from 'lucide-react';

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
    {label: 'Stop premium (₹ per unit)', value: stop, change: setStop},
    {label: 'Target premium (₹ per unit)', value: target, change: setTarget},
    {label: 'Units in one lot', value: lot, change: setLot, integer: true},
    {label: 'Fees + slippage buffer (₹ per lot, round trip)', value: cost, change: setCost},
  ];
  return <div className="index-lab"><IndexSignals/>
    <details className="panel section-disclosure option-calculator"><summary><Calculator size={17}/> One-lot calculator</summary>
      <div className="panel-head"><div><h2>Position sizing</h2><p>User-entered premiums · separate from signal settings</p></div>
      <button className="button secondary small" onClick={() => {setEntry('80'); setStop('70'); setTarget('100'); setLot('65'); setCost('60'); setExample(true);}}>Try an example</button></div>
      <div className="index-calculator">
        <div className="index-inputs">
          <label>Account capital (₹)<input type="number" min="1" max="100000000" value={capital} onChange={e => setCapital(e.target.value)}/></label>
          <label>Index<select value={index} onChange={e => {setIndex(e.target.value); setLot(''); setEntry(''); setStop(''); setTarget(''); setExample(false);}}>{['Nifty 50', 'Bank Nifty'].map(x => <option key={x}>{x}</option>)}</select></label>
          <label>Option<select value={side} onChange={e => setSide(e.target.value)}><option>Call (CE)</option><option>Put (PE)</option></select></label>
          {inputs.map(x => <label key={x.label}>{x.label}<input type="number" min="0" max="100000000" step={x.integer ? '1' : '.01'} value={x.value} onChange={e => x.change(e.target.value)}/></label>)}
          <p className="small-text">{example ? 'Example inputs · not market quotes. ' : ''}<a href="https://www.nseindia.com/static/products-services/equity-derivatives-contract-information" target="_blank" rel="noreferrer">Check the contract lot size</a></p>
        </div>
        <div className="index-results" aria-live="polite">
          <span className={`badge ${fits ? 'blue' : 'neutral'}`}>{fits ? 'Within the limit' : valid ? 'Exceeds the limit' : 'Enter premiums and lot size'}</span>
          <h3>{index} · {side}</h3>
          {validCapital && <p>Planned-loss limit: {rupees(budget)} (1% of capital).</p>}
          {valid ? <dl>
            <div><dt>Premium + costs · maximum exposure</dt><dd data-testid="option-funding">{rupees(funding)}</dd></div>
            <div><dt>Planned loss at stop</dt><dd data-testid="option-stop-loss">{rupees(plannedLoss)}</dd></div>
            <div><dt>Net result at target</dt><dd data-testid="option-target" className={targetProfit > 0 ? 'positive' : 'negative'}>{rupees(targetProfit)}</dd></div>
          </dl> : <p>Enter a positive premium, stop below entry, target above entry, and a whole-number lot size.</p>}
          <details className="goal-details"><summary>Goal comparison</summary>
            <label>Daily goal to examine (₹)<input type="number" min="1" max="100000000" value={goal} onChange={e => setGoal(e.target.value)}/></label>
            {validGoal && validCapital && <p><strong>{(goalN / capitalN * 100).toFixed(1)}% in a day</strong> · one-lot sizing unchanged</p>}
            {valid && validGoal && <p>Required exit premium: {rupees(entryN + (goalN + costN) / lotN)}</p>}
          </details>
        </div>
      </div>
      <p className="calculator-note">Calculations assume the entered exits and costs, not actual fills. Maximum exposure includes the full premium. Inputs do not change server limits.</p>
    </details>
  </div>;
}
