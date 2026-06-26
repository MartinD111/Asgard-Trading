// Asgard Terminal — main views (Trade / Stats / Activity).
const DSV = window.AsgardDesignSystem_d84b02;
const KIT = window.ASGARD_KIT;
const D = window.ASGARD_DATA;

function ViewHead({ title, em, sub }) {
  return (
    <div style={{ marginBottom: 16 }} className="animate-slide-up">
      <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--t1)' }}>
        {title} <em style={{ fontStyle: 'normal', color: 'var(--blue)' }}>{em}</em>
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--t2)', marginTop: 3 }}>{sub}</div>
    </div>
  );
}

// ───────────────────────── Trade ─────────────────────────
function TradeView() {
  const { Card, Badge, Input, Ticker, SignalCard, Button } = DSV;
  const { PriceChart, Icon, fmtPrice, fmtHL } = KIT;
  const [sym, setSym] = React.useState('BTCUSDT');
  const [side, setSide] = React.useState('BUY');
  const [tf, setTf] = React.useState('1D');
  const [qty, setQty] = React.useState('0.1');
  const sel = D.tickers.find(t => t.symbol === sym) || D.tickers[0];
  const up = sel.changePercent >= 0;

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '18px 22px' }} className="custom-scrollbar">
      <ViewHead title="System" em="Intelligence" sub="AI-powered market analysis — monitoring global assets with sub-second precision." />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 9, marginBottom: 13 }}>
        {D.tickers.map(t => (
          <Ticker key={t.symbol} base={t.base} quote={t.quote} price={fmtPrice(t.price)} changePercent={t.changePercent}
            high={fmtHL(t.high)} low={fmtHL(t.low)} active={t.symbol === sym} onClick={() => setSym(t.symbol)} />
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 12, alignItems: 'start' }}>
        <Card style={{ padding: '16px 18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)' }}>{sym} <span style={{ fontSize: 11, color: 'var(--t2)', fontWeight: 500, marginLeft: 4 }}>Market Sentiment</span></div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 3 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: up ? 'var(--gr)' : 'var(--re)' }}>{fmtPrice(sel.price)}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: up ? 'var(--gr)' : 'var(--re)' }}>{up ? '▲' : '▼'} {Math.abs(sel.changePercent).toFixed(2)}%</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 2, padding: 3, background: 'var(--s2)', border: '1px solid var(--bd)', borderRadius: 'var(--rs)' }}>
              {['1H', '1D', '1W'].map(t => (
                <button key={t} onClick={() => setTf(t)} style={{ padding: '4px 11px', fontSize: 11, fontWeight: 600, borderRadius: 5, border: 'none', cursor: 'pointer', background: tf === t ? 'var(--blue)' : 'transparent', color: tf === t ? '#fff' : 'var(--t2)' }}>{t}</button>
              ))}
            </div>
          </div>
          <PriceChart series={D.chart} />
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card title="Manual Trade" accent="blue" icon={<Icon name="Wallet" size={12} />}>
            <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--s2)', border: '1px solid var(--bd)', borderRadius: 'var(--rp)', marginBottom: 13 }}>
              {['BUY', 'SELL'].map(s => (
                <button key={s} onClick={() => setSide(s)} style={{ flex: 1, padding: '8px 0', fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', borderRadius: 'var(--rp)', border: 'none', cursor: 'pointer',
                  background: side === s ? (s === 'BUY' ? 'var(--gr)' : 'var(--re)') : 'transparent', color: side === s ? '#fff' : 'var(--t2)',
                  boxShadow: side === s ? (s === 'BUY' ? 'var(--glow-gr)' : 'var(--glow-re)') : 'none' }}>{s}</button>
              ))}
            </div>
            <div style={{ marginBottom: 10 }}><Input label={`Order Size (${sel.base})`} type="number" value={qty} onChange={(e) => setQty(e.target.value)} /></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
              <Input label="Stop Loss ($)" placeholder="None" />
              <Input label="Take Profit ($)" placeholder="None" />
            </div>
            <div style={{ background: 'var(--s2)', border: '1px solid var(--bd)', borderRadius: 'var(--rs)', padding: '8px 12px', marginBottom: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' }}>
                <span style={{ color: 'var(--t2)' }}>Order Cost</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--blue)', fontSize: 14 }}>${(sel.price * (parseFloat(qty) || 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              </div>
            </div>
            <Button variant={side === 'BUY' ? 'buy' : 'sell'} icon={<span>→</span>} style={{ width: '100%' }}>Execute {side}</Button>
          </Card>

          <Card title="AI Signals" accent="purple" icon={<Icon name="Cpu" size={12} />} action={<Badge tone="purple" dot>Live</Badge>}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }} className="custom-scrollbar">
              {D.signals.map(s => <SignalCard key={s.id} base={s.base} quote={s.quote} direction={s.direction} confidence={s.confidence} reason={s.reason} onClick={() => setSym(s.symbol)} />)}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── Stats ─────────────────────────
function StatsView() {
  const { Card, KpiStat } = DSV;
  const { Icon } = KIT;
  const max = Math.max(...D.agents.map(a => Math.abs(a.pnl)), 1);
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '18px 22px' }} className="custom-scrollbar">
      <ViewHead title="Performance" em="Stats" sub="Historical equity curves, win rates, and per-agent contribution." />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 9, marginBottom: 13 }}>
        {D.kpis.map(k => <KpiStat key={k.label} {...k} />)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 290px', gap: 12, alignItems: 'start' }}>
        <Card title="Comparative Backtest — 30D (BTCUSDT)" accent="blue" icon={<Icon name="Activity" size={12} />}>
          <div style={{ display: 'flex', gap: 14, marginBottom: 12, fontSize: 11, color: 'var(--t2)' }}>
            {D.agents.map(a => <span key={a.key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}><span style={{ width: 18, height: 2, borderRadius: 2, background: a.color }} />{a.name}</span>)}
          </div>
          <StatsChart />
        </Card>
        <Card title="Agent Breakdown" accent="green" icon={<Icon name="Calendar" size={12} />}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {D.agents.map(a => (
              <div key={a.key} style={{ background: 'var(--s2)', border: '1px solid var(--bd)', borderRadius: 'var(--rs)', padding: '11px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: a.color }}>{a.name}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: a.pnl >= 0 ? 'var(--gr)' : 'var(--re)' }}>{a.pnl >= 0 ? '+' : ''}${a.pnl.toFixed(2)}</span>
                </div>
                <div style={{ height: 3, background: 'var(--s1)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 2, width: `${(Math.abs(a.pnl) / max) * 100}%`, background: a.color }} />
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--t3)', marginTop: 4 }}>Win rate {a.winrate}% · {a.trades} trades</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function StatsChart() {
  const W = 600, H = 180, pad = 12;
  const series = { loki: '#4B9DFF', thor: '#9B72FF', odin: '#F0A500' };
  const gen = (seed) => { const a = []; let v = 0; for (let i = 0; i < 30; i++) { v += (Math.random() - 0.4 + seed) * 8; a.push(v); } return a; };
  const data = { loki: gen(0.25), thor: gen(0.15), odin: gen(0.08) };
  const all = [].concat(...Object.values(data));
  const mn = Math.min(...all) - 4, mx = Math.max(...all) + 4, rng = mx - mn || 1;
  const path = (arr) => arr.map((v, i) => `${i === 0 ? 'M' : 'L'} ${(pad + (i / (arr.length - 1)) * (W - pad * 2)).toFixed(1)} ${(pad + (1 - (v - mn) / rng) * (H - pad * 2)).toFixed(1)}`).join(' ');
  return (
    <svg viewBox="0 0 600 180" preserveAspectRatio="none" style={{ width: '100%', display: 'block' }}>
      {[45, 90, 135].map(y => <line key={y} x1="0" y1={y} x2="600" y2={y} stroke="rgba(255,255,255,0.04)" />)}
      {Object.entries(series).map(([k, c]) => <path key={k} d={path(data[k])} fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" />)}
    </svg>
  );
}

// ───────────────────────── Activity ─────────────────────────
function ActivityView() {
  const { Card, Badge } = DSV;
  const { Icon } = KIT;
  const AGENT_COLOR = { LOKI: 'var(--blue)', THOR: 'var(--pu)', ODIN: 'var(--gold)', MANUAL: 'var(--t2)' };
  const th = { fontSize: 9, fontWeight: 600, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.07em', padding: '0 0 9px', textAlign: 'left', borderBottom: '1px solid var(--bd)' };
  const td = { padding: '11px 0', fontSize: 12, borderBottom: '1px solid var(--bd)', fontFamily: 'var(--font-mono)', color: 'var(--t1)' };
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '18px 22px' }} className="custom-scrollbar">
      <ViewHead title="Live" em="Activity" sub="Currently open positions and real-time trade logs." />
      <Card title="Completed Trade History" accent="blue" icon={<Icon name="FileText" size={12} />}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            <th style={th}>Time</th><th style={th}>Asset</th><th style={th}>Side</th><th style={th}>Agent</th>
            <th style={th}>Entry</th><th style={th}>Close</th><th style={{ ...th, textAlign: 'right' }}>Net PnL</th>
          </tr></thead>
          <tbody>
            {D.history.map((h, i) => {
              const win = h.pnl >= 0;
              return (
                <tr key={i}>
                  <td style={{ ...td, color: 'var(--t2)', fontSize: 10 }}>{h.time}</td>
                  <td style={{ ...td, fontFamily: 'var(--font-sans)', fontWeight: 700 }}>{h.base}<small style={{ color: 'var(--t3)' }}>/{h.quote}</small></td>
                  <td style={td}><Badge tone={h.side === 'BUY' ? 'green' : 'red'} bordered={false}>{h.side}</Badge></td>
                  <td style={{ ...td, fontFamily: 'var(--font-sans)', fontSize: 10, fontWeight: 700, color: AGENT_COLOR[h.agent] }}>{h.agent}</td>
                  <td style={td}>{h.entry > 999 ? '$' + h.entry.toLocaleString() : h.entry}</td>
                  <td style={td}>{h.close > 999 ? '$' + h.close.toLocaleString() : h.close}</td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 700, color: win ? 'var(--gr)' : 'var(--re)' }}>{win ? '+' : '−'}${Math.abs(h.pnl).toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ───────────────────────── Settings ─────────────────────────
function SettingsView() {
  const { Card, Toggle, Button } = DSV;
  const { Icon } = KIT;
  const [auto, setAuto] = React.useState(true);
  const [live, setLive] = React.useState(false);
  const [active, setActive] = React.useState('loki');
  const row = (title, desc, val, set) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', background: 'var(--s2)', border: '1px solid var(--bd)', borderRadius: 'var(--rs)', marginBottom: 9 }}>
      <div><div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>{title}</div><div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 2 }}>{desc}</div></div>
      <Toggle checked={val} onChange={set} />
    </div>
  );
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '18px 22px' }} className="custom-scrollbar">
      <ViewHead title="System" em="Settings" sub="Strategy, broker connections, safety controls, and API keys." />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 12, alignItems: 'start' }}>
        <Card title="Active Strategy" accent="blue" icon={<Icon name="Clock" size={12} />}>
          <p style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.6, marginTop: 0, marginBottom: 12 }}>One strategy trades live at a time. The other two are still evaluated for comparison.</p>
          {D.agents.map(a => {
            const on = active === a.key;
            return (
              <button key={a.key} onClick={() => setActive(a.key)} style={{ width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 12, padding: '12px 15px', marginBottom: 8, borderRadius: 'var(--rs)', cursor: 'pointer',
                border: `1px solid ${on ? 'var(--bd-h)' : 'var(--bd)'}`, background: on ? 'var(--s2)' : 'transparent', boxShadow: on ? `inset 3px 0 0 ${a.color}` : 'none' }}>
                <span style={{ width: 12, height: 12, borderRadius: '50%', background: on ? a.color : 'var(--s3)' }} />
                <span style={{ flex: 1 }}>
                  <span style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: a.color }}>{a.name}</span>
                  <span style={{ display: 'block', fontSize: 10, color: 'var(--t3)' }}>{a.key === 'loki' ? 'Quant Signals — pure math, AI trends & patterns' : a.key === 'thor' ? 'Balanced Blend — every signal source weighted equally' : 'Self-Learning — reinforcement-learning engine'}</span>
                </span>
                {on && <Icon name="Check" size={14} color={a.color} />}
              </button>
            );
          })}
          <Button variant="primary" style={{ width: '100%', marginTop: 4 }}>Save Configuration</Button>
        </Card>
        <Card title="Safety Controls" accent="green" icon={<Icon name="Shield" size={12} />}>
          {row('System Auto Mode', "Trades fire automatically on qualifying signals.", auto, setAuto)}
          {row('Live Mode', live ? 'LIVE — real orders on your broker' : 'Paper trading — no real orders', live, setLive)}
          {live && <p style={{ fontSize: 10, color: 'var(--gold)', lineHeight: 1.5, marginTop: 8 }}>Live mode is active. Orders will be placed on your connected broker using real funds.</p>}
        </Card>
      </div>
    </div>
  );
}

window.ASGARD_VIEWS = { TradeView, StatsView, ActivityView, SettingsView };
