// Asgard Terminal — UI kit screens. Composes the design-system components
// (window.AsgardDesignSystem_d84b02) over mock data (window.ASGARD_DATA).
const DS = window.AsgardDesignSystem_d84b02;
const { Button, Card, Badge, Input, Toggle, Ticker, KpiStat, SignalCard, NavPills } = DS;

// ── lucide icon helper ──
function Icon({ name, size = 14, color = 'currentColor' }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current && window.lucide && window.lucide[name]) {
      ref.current.innerHTML = '';
      const el = window.lucide.createElement(window.lucide[name]);
      el.setAttribute('width', size); el.setAttribute('height', size);
      el.setAttribute('stroke', color);
      ref.current.appendChild(el);
    }
  }, [name, size, color]);
  return <span ref={ref} style={{ display: 'inline-flex' }} />;
}

const fmtPrice = (p) => p > 999 ? '$' + p.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : p.toFixed(4);
const fmtHL = (p) => p > 999 ? '$' + Math.round(p).toLocaleString('en') : p.toFixed(4);

// ───────────────────────── Header ─────────────────────────
function Header({ tab, setTab, onLogout, portfolio }) {
  const [menu, setMenu] = React.useState(false);
  const items = [
    { id: 'Trade', label: 'Trade', icon: <Icon name="TrendingUp" size={15} /> },
    { id: 'Stats', label: 'Stats', icon: <Icon name="BarChart3" size={15} /> },
    { id: 'Activity', label: 'Activity', icon: <Icon name="Activity" size={15} /> },
    { id: 'Settings', label: 'Settings', icon: <Icon name="Settings" size={15} /> },
  ];
  return (
    <header style={{ height: 58, flexShrink: 0, background: 'var(--s1)', borderBottom: '1px solid var(--bd)' }}>
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 22px', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 136, cursor: 'pointer' }} onClick={() => setTab('Trade')}>
          <img src={window.__resources.asgardLogo} alt="Asgard" style={{ width: 28, height: 28, objectFit: 'contain' }} />
          <div style={{ lineHeight: 1.05 }}>
            <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--gold)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Asgard</div>
            <div style={{ fontSize: 8, fontWeight: 600, color: 'var(--t3)', letterSpacing: '0.2em', textTransform: 'uppercase' }}>Intelligence</div>
          </div>
        </div>

        <NavPills items={items} value={tab} onChange={setTab} />

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12, minWidth: 136 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, fontWeight: 600, color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            <span className="ldot" /> Live
          </div>
          <div style={{ width: 1, height: 26, background: 'var(--bd)' }} />
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
            <span style={{ fontSize: 8.5, fontWeight: 600, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Total Equity</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>${portfolio.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
          </div>
          <div style={{ position: 'relative' }}>
            <button onClick={() => setMenu(!menu)} style={{ width: 32, height: 32, borderRadius: '50%', overflow: 'hidden', border: `2px solid ${menu ? 'var(--blue)' : 'var(--bd)'}`, cursor: 'pointer', background: 'var(--s2)', padding: 0 }}>
              <img src={window.__resources.avatarOdin} alt="User" style={{ width: '100%', height: '100%' }} />
            </button>
            {menu && (
              <div className="animate-slide-up" style={{ position: 'absolute', right: 0, marginTop: 12, width: 200, background: 'var(--s2)', border: '1px solid var(--bd)', borderRadius: 'var(--r)', boxShadow: 'var(--elev-3)', overflow: 'hidden', zIndex: 100 }}>
                <div style={{ padding: 16, borderBottom: '1px solid var(--bd)', textAlign: 'center', background: 'var(--s1)' }}>
                  <img src={window.__resources.avatarOdin} alt="" style={{ width: 48, height: 48, borderRadius: '50%', border: '2px solid var(--blue)' }} />
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)', marginTop: 6 }}>odin_trader</div>
                  <div style={{ fontSize: 10, color: 'var(--gold)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Admin</div>
                </div>
                <div style={{ padding: 8 }}>
                  <button onClick={() => { setMenu(false); onLogout(); }} style={{ width: '100%', textAlign: 'left', padding: '9px 11px', fontSize: 12, fontWeight: 600, color: 'var(--re)', background: 'none', border: 'none', borderRadius: 'var(--rs)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 9 }}>
                    <Icon name="LogOut" size={14} /> Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

// ───────────────────────── Login ─────────────────────────
function LoginScreen({ onLogin }) {
  const [u, setU] = React.useState('odin_trader');
  const [p, setP] = React.useState('••••••••');
  const [busy, setBusy] = React.useState(false);
  const submit = (e) => { e.preventDefault(); setBusy(true); setTimeout(onLogin, 650); };
  return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
      <div style={{ width: '100%', maxWidth: 360, padding: 16 }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <img src={window.__resources.asgardLogo} alt="Asgard" style={{ width: 64, height: 64, objectFit: 'contain', marginBottom: 12 }} />
          <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--t1)', letterSpacing: '-0.01em' }}>ASGARD <em style={{ fontStyle: 'normal', color: 'var(--blue)' }}>TRADING</em></div>
          <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.12em' }}>Algorithmic Execution Platform</div>
        </div>
        <Card title="Sign In" accent="blue">
          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Input label="Username" value={u} onChange={(e) => setU(e.target.value)} />
            <Input label="Password" type="password" value={p} onChange={(e) => setP(e.target.value)} />
            <Button variant="primary" type="submit" disabled={busy} style={{ width: '100%', marginTop: 4 }}>
              {busy ? 'Signing in…' : 'Sign In'}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}

// ───────────────────────── Price chart (SVG) ─────────────────────────
function PriceChart({ series }) {
  const W = 900, H = 240, pL = 8, pR = 52, pT = 18, pB = 28;
  const cW = W - pL - pR, cH = H - pT - pB;
  const min = Math.min(...series) * 0.9998, max = Math.max(...series) * 1.0002, range = max - min || 1;
  const pts = series.map((v, i) => ({ x: pL + (i / (series.length - 1)) * cW, y: pT + (1 - (v - min) / range) * cH }));
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const area = `${line} L ${pts[pts.length - 1].x.toFixed(1)} ${pT + cH} L ${pts[0].x.toFixed(1)} ${pT + cH} Z`;
  const lastY = pts[pts.length - 1].y;
  const yLabels = Array.from({ length: 5 }).map((_, i) => {
    const frac = i / 4, yp = pT + frac * cH, pv = max - frac * range;
    return { yp, label: '$' + (pv / 1000).toFixed(1) + 'k' };
  });
  return (
    <svg viewBox="0 0 900 240" preserveAspectRatio="none" style={{ width: '100%', display: 'block', overflow: 'visible' }}>
      <defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4B9DFF" stopOpacity="0.16" /><stop offset="85%" stopColor="#4B9DFF" stopOpacity="0" /></linearGradient></defs>
      {[1, 2, 3].map(i => { const yp = pT + (i / 4) * cH; return <line key={i} x1={pL} y1={yp} x2={W - pR} y2={yp} stroke="rgba(255,255,255,0.04)" />; })}
      <path d={area} fill="url(#cg)" />
      <path d={line} fill="none" stroke="#4B9DFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <line x1={pL} y1={lastY} x2={W - pR} y2={lastY} stroke="#22C55E" strokeWidth="1" strokeDasharray="5,4" opacity="0.45" />
      <g fontSize="9" fill="#445060" fontFamily="JetBrains Mono, monospace">
        {yLabels.map((l, i) => <text key={i} x={W - pR + 4} y={l.yp + 3}>{l.label}</text>)}
      </g>
    </svg>
  );
}

window.ASGARD_KIT = { Header, LoginScreen, PriceChart, Icon, fmtPrice, fmtHL };
