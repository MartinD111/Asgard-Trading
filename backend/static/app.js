// ── VIEW ROUTING ──
function sv(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('on'));
  document.querySelectorAll('.nb').forEach(b => b.classList.remove('on'));
  const el = document.getElementById('v-' + name);
  el.classList.add('on');
  el.style.opacity = '1';
  document.querySelector('[data-v="' + name + '"]').classList.add('on');
}

// ── TICKER SELECT ──
function selTick(el, be) {
  document.querySelectorAll('.tick').forEach(t => t.classList.remove('on'));
  el.classList.add('on');
  window._selBE = be;
  const disp = (typeof SYM_MAP !== 'undefined' && SYM_MAP[be]) ? SYM_MAP[be] : be;
  document.getElementById('csym').innerHTML = disp.replace('/', '') + ' <span>Market Sentiment</span>';
  const buf = window._buf && window._buf[be];
  if (buf && buf.length > 2) {
    const last = window._last[be] != null ? window._last[be] : buf[buf.length - 1];
    const open = window._open[be] || last;
    const up = last >= open;
    document.getElementById('cprice').textContent = fmtPrice(last);
    document.getElementById('cprice').style.color = up ? 'var(--gr)' : 'var(--re)';
    const pct = open ? (last - open) / open * 100 : 0;
    const pctEl = document.getElementById('cpct');
    pctEl.textContent = (up ? '▲ ' : '▼ ') + Math.abs(pct).toFixed(2) + '%';
    pctEl.style.color = up ? 'var(--gr)' : 'var(--re)';
    renderSelected();
  } else {
    document.getElementById('cprice').textContent = '—';
    document.getElementById('cpct').textContent = '';
    loadHistory(be, window._range);
  }
}

// ── TIMEFRAME ──
function setTF(btn) {
  document.querySelectorAll('.tf').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  const range = (btn.textContent || '1D').trim().toUpperCase();
  window._range = range;
  const be = window._selBE;
  if (be) loadHistory(be, range);
}

// ── CHART TYPE TOGGLE ──
window._chartType = 'line';
function setChartType(type) {
  window._chartType = type;
  document.getElementById('ct-line').classList.toggle('on', type === 'line');
  document.getElementById('ct-candle').classList.toggle('on', type === 'candle');
  const be = window._selBE;
  if (type === 'candle') {
    const ohlc = window._ohlc && window._ohlc[be];
    if (ohlc && ohlc.length > 1) { renderCandleChart(ohlc); return; }
    const buf = window._buf && window._buf[be];
    if (buf && buf.length > 2) { renderCandleChart(buildOHLCFromCloses(buf)); return; }
  }
  if (window._buf && window._buf[be] && window._buf[be].length > 2) renderSelected();
  else clearChart();
}

// ── CHART ──
// Empty state — never fabricate price data client-side.
function clearChart() {
  ['cline', 'carea', 'ccurr'].forEach(id => { const el = document.getElementById(id); if (el) el.setAttribute('d', ''); });
  const cc = document.getElementById('ccandles'); if (cc) cc.innerHTML = '';
  const yg = document.getElementById('cylbls'); if (yg) yg.innerHTML = '';
  window._cd = null;
  const cp = document.getElementById('cprice'); if (cp) { cp.textContent = '—'; cp.style.color = 'var(--t2)'; }
  const pc = document.getElementById('cpct'); if (pc) pc.textContent = '';
}

function buildOHLCFromCloses(closes) {
  return closes.map((c, i) => {
    const o = i > 0 ? closes[i - 1] : c;
    const spread = Math.abs(c - o);
    const pad = c * 0.0015;
    const h = Math.max(o, c) + spread * 0.35 + pad;
    const l = Math.min(o, c) - spread * 0.35 - pad;
    return { o, h, l, c };
  });
}


function drawTradeMarkers(xs, pT, cH) {
  const g = document.getElementById('ctrades');
  g.innerHTML = '';
  window._tradeMarkers.forEach(m => {
    const i = xs.length - 1 - m.offset;
    if (i < 0 || i >= xs.length) return;
    const x = xs[i];
    const color = m.dir === 'BUY' ? '#22C55E' : '#F43F5E';
    const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    ln.setAttribute('x1', x); ln.setAttribute('y1', pT);
    ln.setAttribute('x2', x); ln.setAttribute('y2', pT + cH);
    ln.setAttribute('stroke', color); ln.setAttribute('stroke-width', '1.5');
    ln.setAttribute('stroke-dasharray', '4,3'); ln.setAttribute('opacity', '0.8');
    g.appendChild(ln);
    const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    lbl.setAttribute('x', x + 3); lbl.setAttribute('y', pT + 11);
    lbl.setAttribute('font-size', '9'); lbl.setAttribute('font-family', 'Outfit,sans-serif');
    lbl.setAttribute('font-weight', '700'); lbl.setAttribute('fill', color);
    lbl.textContent = m.dir === 'BUY' ? '▲' : '▼';
    g.appendChild(lbl);
  });
}

function renderChart(prices) {
  if (!prices || prices.length < 2) return;
  // dispatch to candle if mode is set and we have OHLC
  if (window._chartType === 'candle') {
    const be = window._selBE;
    const ohlc = (window._ohlc && window._ohlc[be] && window._ohlc[be].length > 1)
      ? window._ohlc[be]
      : buildOHLCFromCloses(prices);
    renderCandleChart(ohlc);
    return;
  }

  window._curPrice = prices[prices.length - 1];
  const W = 900, H = 260, pL = 8, pR = 52, pT = 18, pB = 28;
  const cW = W - pL - pR, cH = H - pT - pB;
  const mn = Math.min(...prices) * 0.9998, mx = Math.max(...prices) * 1.0002;
  const rng = mx - mn;
  const xs = prices.map((_, i) => pL + (i / (prices.length - 1)) * cW);
  const ys = prices.map(p => pT + (1 - (p - mn) / rng) * cH);

  const lp = prices.map((p, i) => (i === 0 ? 'M' : 'L') + xs[i].toFixed(1) + ' ' + ys[i].toFixed(1)).join(' ');
  const ap = lp + ` L ${xs[xs.length-1].toFixed(1)} ${pT+cH} L ${xs[0].toFixed(1)} ${pT+cH} Z`;

  document.getElementById('cline').setAttribute('d', lp);
  document.getElementById('carea').setAttribute('d', ap);
  document.getElementById('ccandles').innerHTML = '';

  const ly = ys[ys.length - 1];
  const cl = document.getElementById('ccurr');
  cl.setAttribute('x1', pL); cl.setAttribute('y1', ly);
  cl.setAttribute('x2', W - pR); cl.setAttribute('y2', ly);

  const yg = document.getElementById('cylbls'); yg.innerHTML = '';
  for (let i = 0; i <= 4; i++) {
    const frac = i / 4;
    const yp = pT + frac * cH;
    const pv = mx - frac * rng;
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', W - pR + 4); t.setAttribute('y', yp + 3); t.setAttribute('text-anchor', 'start');
    t.textContent = pv >= 1000 ? '$' + (pv / 1000).toFixed(1) + 'k' : pv.toFixed(2);
    yg.appendChild(t);
  }

  const gg = document.getElementById('cgrid'); gg.innerHTML = '';
  for (let i = 1; i < 4; i++) {
    const yp = pT + (i / 4) * cH;
    const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    ln.setAttribute('x1', pL); ln.setAttribute('y1', yp); ln.setAttribute('x2', W - pR); ln.setAttribute('y2', yp);
    ln.setAttribute('stroke', 'rgba(255,255,255,0.04)'); ln.setAttribute('stroke-width', '1');
    gg.appendChild(ln);
  }

  window._cd = { xs, ys, prices, W, H, pL, pR, pT, pB, cW, cH };
  drawTradeMarkers(xs, pT, cH);
}

function renderCandleChart(ohlc) {
  if (!ohlc || ohlc.length < 2) return;
  const W = 900, H = 260, pL = 8, pR = 52, pT = 18, pB = 28;
  const cW = W - pL - pR, cH = H - pT - pB;
  const allH = ohlc.map(c => c.h), allL = ohlc.map(c => c.l);
  const mn = Math.min(...allL) * 0.9998, mx = Math.max(...allH) * 1.0002;
  const rng = mx - mn;
  const n = ohlc.length;
  const step = cW / n;
  const candW = Math.max(2, step * 0.65);
  const toY = v => pT + (1 - (v - mn) / rng) * cH;
  const toX = i => pL + (i + 0.5) * step;

  document.getElementById('cline').setAttribute('d', '');
  document.getElementById('carea').setAttribute('d', '');

  const cg = document.getElementById('ccandles');
  cg.innerHTML = '';

  const xs = ohlc.map((_, i) => toX(i));

  ohlc.forEach((c, i) => {
    const x = xs[i];
    const bullish = c.c >= c.o;
    const color = bullish ? '#22C55E' : '#F43F5E';
    const wick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    wick.setAttribute('x1', x); wick.setAttribute('x2', x);
    wick.setAttribute('y1', toY(c.h).toFixed(1)); wick.setAttribute('y2', toY(c.l).toFixed(1));
    wick.setAttribute('stroke', color); wick.setAttribute('stroke-width', '1.2');
    cg.appendChild(wick);
    const bodyTop = toY(Math.max(c.o, c.c));
    const bodyH = Math.max(1, Math.abs(toY(c.o) - toY(c.c)));
    const body = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    body.setAttribute('x', (x - candW / 2).toFixed(1));
    body.setAttribute('y', bodyTop.toFixed(1));
    body.setAttribute('width', candW.toFixed(1));
    body.setAttribute('height', bodyH.toFixed(1));
    body.setAttribute('fill', color);
    body.setAttribute('rx', '0.5');
    cg.appendChild(body);
  });

  const lastC = ohlc[ohlc.length - 1].c;
  const ly = toY(lastC);
  const cl = document.getElementById('ccurr');
  cl.setAttribute('x1', pL); cl.setAttribute('y1', ly);
  cl.setAttribute('x2', W - pR); cl.setAttribute('y2', ly);

  const yg = document.getElementById('cylbls'); yg.innerHTML = '';
  for (let i = 0; i <= 4; i++) {
    const frac = i / 4;
    const yp = pT + frac * cH;
    const pv = mx - frac * rng;
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', W - pR + 4); t.setAttribute('y', yp + 3); t.setAttribute('text-anchor', 'start');
    t.textContent = pv >= 1000 ? '$' + (pv / 1000).toFixed(1) + 'k' : pv.toFixed(2);
    yg.appendChild(t);
  }

  const gg = document.getElementById('cgrid'); gg.innerHTML = '';
  for (let i = 1; i < 4; i++) {
    const yp = pT + (i / 4) * cH;
    const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    ln.setAttribute('x1', pL); ln.setAttribute('y1', yp); ln.setAttribute('x2', W - pR); ln.setAttribute('y2', yp);
    ln.setAttribute('stroke', 'rgba(255,255,255,0.04)'); ln.setAttribute('stroke-width', '1');
    gg.appendChild(ln);
  }

  const ys = ohlc.map(c => toY(c.c));
  const prices = ohlc.map(c => c.c);
  window._cd = { xs, ys, prices, W, H, pL, pR, pT, pB, cW, cH };
  drawTradeMarkers(xs, pT, cH);
}

// Chart hover
const csvg = document.getElementById('csvg');
csvg.addEventListener('mousemove', function(e) {
  if (!window._cd) return;
  const { xs, ys, prices, W } = window._cd;
  const rect = this.getBoundingClientRect();
  const mx = (e.clientX - rect.left) / rect.width * W;
  let bi = 0, bd = Infinity;
  xs.forEach((x, i) => { const d = Math.abs(x - mx); if (d < bd) { bd = d; bi = i; } });
  const x = xs[bi], y = ys[bi], p = prices[bi];
  const setA = (id, a, v) => document.getElementById(id).setAttribute(a, v);
  const rmD = id => document.getElementById(id).removeAttribute('display');
  setA('cvl','x1',x); setA('cvl','y1',0); setA('cvl','x2',x); setA('cvl','y2',260); rmD('cvl');
  setA('chl','x1',0); setA('chl','y1',y); setA('chl','x2',900); setA('chl','y2',y); rmD('chl');
  setA('cdot','cx',x); setA('cdot','cy',y); rmD('cdot');
  // Use the real candle timestamp for this point when available; otherwise fall back.
  const times = window._times && window._times[window._selBE];
  let label;
  if (times && times.length === prices.length && times[bi]) {
    label = new Date(times[bi]).toLocaleString('en',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
  } else {
    label = new Date(Date.now() - (prices.length - 1 - bi) * 3600000).toLocaleString('en',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
  }
  document.getElementById('ctipd').textContent = label;
  document.getElementById('ctipp').textContent = p > 999 ? '$' + p.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2}) : '$' + p.toFixed(4);
  document.getElementById('ctip').classList.add('on');
});
csvg.addEventListener('mouseleave', function() {
  ['cvl','chl','cdot'].forEach(id => document.getElementById(id).setAttribute('display','none'));
  document.getElementById('ctip').classList.remove('on');
});

// ── STATS CHART ──
// ── BACKTEST RUNNER ──
async function runBacktest() {
  const btn = document.getElementById('bt-run');
  const status = document.getElementById('bt-status');
  const payload = {
    symbol: document.getElementById('bt-symbol').value,
    agent: document.getElementById('bt-agent').value,
    days: Number(document.getElementById('bt-days').value || 90),
    initial_capital: Number(document.getElementById('bt-capital').value || 10000),
  };
  btn.disabled = true; btn.textContent = 'Running…';
  status.textContent = 'Running backtest — this may take a few seconds…';
  status.style.color = 'var(--t2)';
  try {
    const r = await authFetch('/api/backtest/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.detail || 'Backtest failed'); }
    const d = await r.json();
    renderBacktest(d);
    document.getElementById('bt-results').classList.remove('hide');
    status.textContent = `${d.symbol} · ${d.period || payload.days + 'd'} · ${d.trade_count} trades`;
  } catch (e) {
    status.textContent = String(e.message || e);
    status.style.color = 'var(--re)';
  } finally { btn.disabled = false; btn.textContent = 'Run'; }
}

function renderBacktest(d) {
  const ret = Number(d.total_return_pct || 0);
  const retEl = document.getElementById('bt-return');
  retEl.textContent = (ret >= 0 ? '+' : '') + ret.toFixed(2) + '%';
  retEl.className = 'kv ' + (ret >= 0 ? 'g' : 'r');
  document.getElementById('bt-sharpe').textContent = Number(d.sharpe_ratio || 0).toFixed(2);
  document.getElementById('bt-dd').textContent = '−' + Math.abs(Number(d.max_drawdown_pct || 0)).toFixed(2) + '%';
  document.getElementById('bt-wr').textContent = Number(d.win_rate_pct || 0).toFixed(1) + '%';
  document.getElementById('bt-pf').textContent = Number(d.profit_factor || 0).toFixed(2) + '×';
  document.getElementById('bt-trades').textContent = d.trade_count != null ? d.trade_count : '—';
  // equity curve
  const curve = Array.isArray(d.equity_curve) ? d.equity_curve : [];
  const W = 600, H = 160, pL = 6, pR = 6, pT = 10, pB = 10, cW = W - pL - pR, cH = H - pT - pB;
  if (curve.length < 2) { document.getElementById('bt-line').setAttribute('d', ''); document.getElementById('bt-area').setAttribute('d', ''); return; }
  const mn = Math.min(...curve), mx = Math.max(...curve), rng = (mx - mn) || 1;
  const pts = curve.map((v, i) => ({ x: pL + (i / (curve.length - 1)) * cW, y: pT + (1 - (v - mn) / rng) * cH }));
  const lp = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' ');
  document.getElementById('bt-line').setAttribute('d', lp);
  document.getElementById('bt-area').setAttribute('d', lp + ` L ${pts[pts.length - 1].x.toFixed(1)} ${pT + cH} L ${pts[0].x.toFixed(1)} ${pT + cH} Z`);
}

// ── STATS PAGE — real data from /api/stats ──
function agentGroup(id) {
  if (!id) return null;
  if (id.startsWith('loki')) return 'loki';
  if (id === 'thor') return 'thor';
  if (id === 'odin') return 'odin';
  return null;
}

function renderStatsChart(series) {
  // series: { loki:[cum...], thor:[cum...], odin:[cum...] } aligned to a shared timeline
  const ids = { loki: 'sl1', thor: 'sl2', odin: 'sl3' };
  const all = [].concat(series.loki || [], series.thor || [], series.odin || []);
  const empty = document.getElementById('stats-empty');
  if (!all.length) {
    ['sl1', 'sl2', 'sl3', 'sla'].forEach(id => document.getElementById(id).setAttribute('d', ''));
    if (empty) empty.classList.remove('hide');
    return;
  }
  if (empty) empty.classList.add('hide');
  let mn = Math.min(0, ...all), mx = Math.max(0, ...all);
  if (mn === mx) { mn -= 1; mx += 1; }
  const rng = mx - mn;
  const W = 600, H = 180, pL = 6, pR = 6, pT = 12, pB = 12, cW = W - pL - pR, cH = H - pT - pB;
  const path = arr => {
    if (!arr || arr.length === 0) return '';
    const n = arr.length === 1 ? 2 : arr.length;
    return arr.map((v, i) => {
      const x = pL + (i / (n - 1)) * cW, y = pT + (1 - (v - mn) / rng) * cH;
      return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y.toFixed(1);
    }).join(' ');
  };
  Object.keys(ids).forEach(g => document.getElementById(ids[g]).setAttribute('d', path(series[g])));
  const lk = series.loki || [];
  if (lk.length) {
    const lp = path(lk);
    const lastX = pL + ((lk.length - 1) / (Math.max(2, lk.length) - 1)) * cW;
    document.getElementById('sla').setAttribute('d', lp + ` L ${lastX.toFixed(1)} ${pT + cH} L ${pL} ${pT + cH} Z`);
  } else document.getElementById('sla').setAttribute('d', '');
}

function renderAgentBreakdown(groups) {
  const box = document.getElementById('agent-breakdown');
  if (!box) return;
  const order = [['loki', 'Loki', 'var(--blue)'], ['thor', 'Thor', 'var(--pu)'], ['odin', 'Odin', 'var(--gold)']];
  const maxAbs = Math.max(1, ...order.map(([k]) => Math.abs(groups[k] ? groups[k].pnl : 0)));
  box.innerHTML = order.map(([k, label, color]) => {
    const g = groups[k] || { pnl: 0, count: 0, wins: 0 };
    const wr = g.count ? (g.wins / g.count * 100) : 0;
    const w = Math.min(100, Math.abs(g.pnl) / maxAbs * 100);
    const pos = g.pnl >= 0;
    return `<div class="ai"><div class="atop"><span class="aname" style="color:${color}">${label}</span>
      <span class="apnl" style="color:${pos ? 'var(--gr)' : 'var(--re)'}">${pos ? '+' : ''}$${g.pnl.toFixed(2)}</span></div>
      <div class="btrack"><div class="bfill" style="width:${w}%;background:${color}"></div></div>
      <div class="asub">Win rate ${wr.toFixed(1)}% · ${g.count} trade${g.count === 1 ? '' : 's'}</div></div>`;
  }).join('');
}

async function loadStats() {
  try {
    const hist = await (await authFetch('/api/stats/history?limit=500')).json();
    const closed = (Array.isArray(hist) ? hist : []).filter(t => t.status === 'CLOSED' && !t.is_what_if);
    closed.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // KPIs
    let wins = 0, grossWin = 0, grossLoss = 0;
    const groups = { loki: { pnl: 0, count: 0, wins: 0 }, thor: { pnl: 0, count: 0, wins: 0 }, odin: { pnl: 0, count: 0, wins: 0 } };
    const series = { loki: [], thor: [], odin: [] };
    const running = { loki: 0, thor: 0, odin: 0 };
    closed.forEach(t => {
      const pnl = Number(t.realized_pnl || 0);
      if (pnl > 0) { wins++; grossWin += pnl; } else { grossLoss += Math.abs(pnl); }
      const g = agentGroup(t.agent_used);
      if (g) {
        groups[g].pnl += pnl; groups[g].count++; if (pnl > 0) groups[g].wins++;
        running[g] += pnl;
      }
      // push the running totals for all groups at each closed trade (shared timeline)
      ['loki', 'thor', 'odin'].forEach(k => series[k].push(running[k]));
    });
    const total = closed.length;
    const winRate = total ? (wins / total * 100) : 0;
    const pf = grossLoss > 0 ? (grossWin / grossLoss) : (grossWin > 0 ? Infinity : 0);

    // daily contribution + drawdown
    let daily = null, acc = null;
    try { daily = await (await authFetch('/api/stats/daily_contribution')).json(); } catch (e) {}
    try { acc = await (await authFetch('/api/account')).json(); } catch (e) {}

    const profitEl = document.getElementById('kpi-profit');
    if (daily) {
      const tp = Number(daily.total_pnl || 0);
      profitEl.textContent = (tp >= 0 ? '+$' : '-$') + Math.abs(tp).toFixed(2);
      profitEl.className = 'kv ' + (tp >= 0 ? 'g' : 'r');
      document.getElementById('kpi-profit-sub').textContent = (Number(daily.total_pct || 0)).toFixed(2) + '% equity today';
    } else { profitEl.textContent = '—'; }

    document.getElementById('kpi-winrate').textContent = total ? winRate.toFixed(1) + '%' : '—';
    document.getElementById('kpi-winrate-sub').textContent = total + ' closed trade' + (total === 1 ? '' : 's');
    document.getElementById('kpi-pf').textContent = total ? (pf === Infinity ? '∞' : pf.toFixed(2) + '×') : '—';

    const ddEl = document.getElementById('kpi-dd');
    if (acc && acc.drawdown != null) {
      const dd = Number(acc.drawdown);
      ddEl.textContent = '−' + Math.abs(dd * (Math.abs(dd) <= 1 ? 100 : 1)).toFixed(2) + '%';
    } else ddEl.textContent = '—';

    renderStatsChart(series);
    renderAgentBreakdown(groups);

    const macro = document.getElementById('macro-status');
    const macroCard = document.getElementById('macro-card');
    const macroLabel = document.getElementById('macro-label');
    if (daily && daily.learning_blocked) {
      if (macro) macro.textContent = 'Odin self-learning is paused — weights frozen (macro risk gate active).';
      if (macroCard) { macroCard.style.background = 'var(--re-bg)'; macroCard.style.borderColor = 'var(--re-bd)'; }
      if (macroLabel) macroLabel.style.color = 'var(--re)';
    } else {
      if (macro) macro.textContent = 'Self-learning loops operating at standard capacity.';
      if (macroCard) { macroCard.style.background = 'var(--gr-bg)'; macroCard.style.borderColor = 'var(--gr-bd)'; }
      if (macroLabel) macroLabel.style.color = 'var(--gr)';
    }
  } catch (e) {
    renderStatsChart({ loki: [], thor: [], odin: [] });
    const box = document.getElementById('agent-breakdown');
    if (box) box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:6px 0;">Sign in to view performance.</div>';
  }
}

// ════════════════════════════════════════════════════════════
//  LIVE DATA — FastAPI backend (REST seed + /ws/live stream)
// ════════════════════════════════════════════════════════════
const SYM_MAP = { BTCUSDT: 'BTC/USDT', ETHUSDT: 'ETH/USDT', SOLUSDT: 'SOL/USD', EUR_USD: 'EUR/USD', XAU_USD: 'XAU/USD', XAG_USD: 'XAG/USD' };
window._selBE = 'BTCUSDT';
window._buf = {};
window._open = {};
window._ohlc = {};
window._tradeMarkers = [];

function fmtPrice(p) {
  if (p > 999) return '$' + p.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 10) return '$' + p.toFixed(2);
  return p.toFixed(4);
}

window._hilo = {};
function updateTicker(be, price) {
  const card = document.getElementById('tk-' + be);
  if (!card) return;
  const pEl = card.querySelector('.tick-price');
  if (pEl) pEl.textContent = fmtPrice(price);
  // maintain session high/low
  const hl = window._hilo[be] || (window._hilo[be] = { h: price, l: price });
  if (price > hl.h) hl.h = price;
  if (price < hl.l) hl.l = price;
  const hEl = card.querySelector('.tk-h'), lEl = card.querySelector('.tk-l');
  if (hEl) hEl.textContent = 'H: ' + fmtPrice(hl.h);
  if (lEl) lEl.textContent = 'L: ' + fmtPrice(hl.l);
  const open = window._open[be];
  if (open) {
    const pct = (price - open) / open * 100;
    const chg = card.querySelector('.chg');
    if (chg) { chg.className = 'chg ' + (pct >= 0 ? 'up' : 'dn'); chg.textContent = (pct >= 0 ? '▲ ' : '▼ ') + Math.abs(pct).toFixed(2) + '%'; }
  }
}

window._times = {};   // ISO timestamps aligned to _buf[be] (per loaded range)
window._last = {};    // latest live price per symbol
window._range = window._range || '1D';

// Render the selected symbol's historical series for the current range,
// with the final point tracking the latest live price (so the chart still "moves"
// without live ticks overwriting the timeframe shape).
function renderSelected() {
  const be = window._selBE;
  const hist = window._buf[be];
  if (!hist || hist.length < 2) { clearChart(); return; }
  if (window._chartType === 'candle') { renderChart(hist); return; } // candle path reads _ohlc internally
  const series = hist.slice();
  const live = window._last[be];
  if (Number.isFinite(live)) series[series.length - 1] = live;
  renderChart(series);
}

async function loadHistory(be, range) {
  range = range || window._range || '1D';
  try {
    const r = await fetch('/api/stats/market/history?symbol=' + encodeURIComponent(be) + '&range=' + encodeURIComponent(range));
    if (!r.ok) throw 0;
    const c = await r.json();
    if (Array.isArray(c) && c.length > 1) {
      window._buf[be] = c.map(x => x.close).slice(-120);
      window._times[be] = c.map(x => x.time || null).slice(-120);
      window._ohlc[be] = c.map(x => ({
        o: x.open  != null ? x.open  : x.close,
        h: x.high  != null ? x.high  : x.close,
        l: x.low   != null ? x.low   : x.close,
        c: x.close
      })).slice(-80);
      window._open[be] = c[0].open != null ? c[0].open : window._buf[be][0];
      // seed session high/low from history range
      const highs = window._ohlc[be].map(x => x.h), lows = window._ohlc[be].map(x => x.l);
      window._hilo[be] = { h: Math.max(...highs), l: Math.min(...lows) };
      const last = window._last[be] != null ? window._last[be] : window._buf[be][window._buf[be].length - 1];
      updateTicker(be, last);
      if (be === window._selBE) renderSelected();
      return;
    }
  } catch (e) { /* no data — show empty state, never fabricate */ }
  if (be === window._selBE) clearChart();
}

function onTick(be, price) {
  if (!Number.isFinite(price) || price <= 0) return;
  if (!window._open[be]) window._open[be] = price;
  window._last[be] = price;
  // age out trade markers as new ticks arrive
  window._tradeMarkers.forEach(m => m.offset++);
  window._tradeMarkers = window._tradeMarkers.filter(m => m.offset < 118);
  updateTicker(be, price);
  if (be === window._selBE) {
    const up = price >= (window._open[be] || price);
    const cp = document.getElementById('cprice');
    cp.textContent = fmtPrice(price); cp.style.color = up ? 'var(--gr)' : 'var(--re)';
    renderSelected();
  }
}

const SIGS = [];
const SIG_ERR = /prediction unavailable|api[_ ]?key|not valid|api_key_invalid|invalid_argument|quota|permission denied|\b[45]\d\d\b/i;
function addSignal(p) {
  const reason = p.reasoning || p.reason || '';
  if (SIG_ERR.test(reason)) return;
  const conf = Math.round((p.confidence_score || p.confidence || 0) * 100);
  if (!conf) return;
  const disp = SYM_MAP[p.symbol] || p.symbol || '';
  const parts = disp.includes('/') ? disp.split('/') : [disp, ''];
  SIGS.unshift({ base: parts[0], quote: parts[1], dir: (p.direction || 'BUY').toUpperCase(), conf, reason });
  if (SIGS.length > 6) SIGS.pop();
  renderSignals();
}
function renderSignals() {
  const box = document.getElementById('sigbox');
  if (!box || SIGS.length === 0) return;
  box.innerHTML = SIGS.map(s => `
    <div class="si">
      <div class="si-top">
        <div><div class="sisym">${s.base}<small>/${s.quote}</small></div><div class="dir ${s.dir === 'BUY' ? 'buy' : 'sell'}">${s.dir}</div></div>
        <div class="siconf">${s.conf}%<small>Confidence</small></div>
      </div>
      <div class="cbar"><div class="cfill" style="width:${s.conf}%"></div></div>
      <div class="sreason">"${String(s.reason).replace(/</g, '&lt;').replace(/"/g, '&quot;')}"</div>
    </div>`).join('');
}

function setLiveStatus(state) {
  // state: 'live' | 'reconnecting' | 'offline'
  const dot = document.getElementById('ldot');
  const lbl = document.getElementById('live-lbl');
  const map = { live: ['var(--gr)', 'Live'], reconnecting: ['var(--gold)', 'Reconnecting'], offline: ['var(--re)', 'Offline'] };
  const [color, text] = map[state] || map.offline;
  if (dot) { dot.style.background = color; dot.style.boxShadow = '0 0 6px ' + color; }
  if (lbl) lbl.textContent = text;
}

function connectWS() {
  if (window._wsStarted) return;
  window._wsStarted = true;
  window._wsBackoff = 1000;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  function go() {
    const t = getToken();
    // NOTE: browsers cannot set Authorization headers on WebSocket; the token is
    // passed as a query param. Backend should prefer a short-lived WS ticket/cookie.
    const url = proto + '//' + location.host + '/ws/live' + (t ? ('?token=' + encodeURIComponent(t)) : '');
    let ws;
    try { ws = new WebSocket(url); } catch (_) { scheduleReconnect(); return; }
    ws.onopen = () => { window._wsBackoff = 1000; setLiveStatus('live'); };
    ws.onmessage = (ev) => {
      let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
      if (d.type === 'tick' && d.symbol) onTick(d.symbol, Number(d.price));
      else if (d.type === 'prediction' || d.type === 'GEMINI_UPDATE') addSignal(d.payload || d);
      else if (d.type === 'PORTFOLIO_UPDATE' && d.payload) {
        if (d.payload.equity != null) document.getElementById('hdr-equity').textContent = fmtPrice(Number(d.payload.equity));
        if (d.payload.balance != null) document.getElementById('hdr-balance').textContent = fmtPrice(Number(d.payload.balance));
      }
    };
    ws.onclose = () => scheduleReconnect();
    ws.onerror = () => { try { ws.close(); } catch (_) {} };
  }
  function scheduleReconnect() {
    setLiveStatus('reconnecting');
    const delay = Math.min(window._wsBackoff, 30000);
    window._wsBackoff = Math.min(delay * 2, 30000);
    setTimeout(go, delay);
  }
  go();
}

// ════════════════════════════════════════════════════════════
//  AUTH LAYER
// ════════════════════════════════════════════════════════════
function getToken() { return localStorage.getItem('asgard_token'); }
function setToken(t) { localStorage.setItem('asgard_token', t); }
function clearToken() { localStorage.removeItem('asgard_token'); }
window._me = null;

async function authFetch(url, opts = {}) {
  opts.headers = Object.assign({}, opts.headers || {});
  const t = getToken();
  if (t) opts.headers['Authorization'] = 'Bearer ' + t;
  const r = await fetch(url, opts);
  if (r.status === 401) { showLogin(); throw new Error('unauthorized'); }
  return r;
}

function showLogin() {
  document.getElementById('login-overlay').style.display = 'flex';
  setTimeout(() => { const u = document.getElementById('login-user'); if (u) u.focus(); }, 60);
}
function hideLogin() { document.getElementById('login-overlay').style.display = 'none'; }

async function doLogin() {
  const user = document.getElementById('login-user').value.trim();
  const pass = document.getElementById('login-pass').value;
  const err  = document.getElementById('login-err');
  err.textContent = '';
  if (!user || !pass) { err.textContent = 'Enter username and password.'; return; }
  try {
    const body = new URLSearchParams({ username: user, password: pass });
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!r.ok) { err.textContent = 'Invalid username or password.'; return; }
    const d = await r.json();
    setToken(d.access_token || d.token);
    document.getElementById('login-pass').value = '';
    hideLogin();
    boot();
  } catch (e) { err.textContent = 'Login failed. Please try again.'; }
}

function logout() { clearToken(); closeProfileMenu(); location.reload(); }

// ── PROFILE DROPDOWN ──
function toggleProfileMenu(e) { e.stopPropagation(); document.getElementById('pmenu').classList.toggle('on'); }
function closeProfileMenu() { document.getElementById('pmenu').classList.remove('on'); }
document.addEventListener('click', (e) => {
  if (!e.target.closest('.profile-wrap')) { closeProfileMenu(); closeNotif(); }
});

// ── NOTIFICATIONS (driven by audit log) ──
function toggleNotif(e) {
  e.stopPropagation();
  document.getElementById('notif-menu').classList.toggle('on');
  document.getElementById('notif-dot').classList.add('hide'); // mark as seen
}
function closeNotif() { const m = document.getElementById('notif-menu'); if (m) m.classList.remove('on'); }

function renderNotifications(list) {
  const box = document.getElementById('notif-list');
  if (!box) return;
  const items = (list || []).filter(e => /KILL|REJECT|HALT|ORDER/.test(e.event_type || '')).slice(0, 12);
  const dot = document.getElementById('notif-dot');
  const danger = (list || []).some(e => /KILL|REJECT|HALT/.test(e.event_type || ''));
  if (dot) dot.classList.toggle('hide', !danger);
  if (!items.length) { box.innerHTML = '<div style="padding:11px;font-size:11px;color:var(--t3);">No notifications.</div>'; return; }
  box.innerHTML = items.map(e => {
    const time = e.created_at ? new Date(e.created_at).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
    const label = (typeof AUDIT_LABELS !== 'undefined' && AUDIT_LABELS[e.event_type]) || e.event_type || '—';
    const danger = /KILL|REJECT|HALT/.test(e.event_type || '');
    return `<div class="pmenu-item" style="cursor:default;flex-direction:column;align-items:flex-start;gap:2px;">
      <span style="font-weight:700;color:${danger ? 'var(--re)' : 'var(--t1)'}">${label}</span>
      <span style="font-size:10px;color:var(--t3)">${time}${e.symbol ? ' · ' + (SYM_MAP[e.symbol] || e.symbol) : ''}</span>
    </div>`;
  }).join('');
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(window._toastT);
  window._toastT = setTimeout(() => t.classList.remove('on'), 2400);
}

// ════════════════════════════════════════════════════════════
//  AI AGENT CONTROL (single active agent)
// ════════════════════════════════════════════════════════════
const AGENT_META = {
  loki_m: { label: 'Loki · Math',     short: 'Loki-M', color: 'var(--blue)', bg: 'var(--blue-bg)', bd: 'var(--blue-bd)' },
  loki_p: { label: 'Loki · Patterns', short: 'Loki-P', color: 'var(--blue)', bg: 'var(--blue-bg)', bd: 'var(--blue-bd)' },
  loki_t: { label: 'Loki · Trends',   short: 'Loki-T', color: 'var(--blue)', bg: 'var(--blue-bg)', bd: 'var(--blue-bd)' },
  thor:   { label: 'Thor',            short: 'Thor',   color: 'var(--pu)',   bg: 'var(--pu-bg)',   bd: 'var(--pu-bd)' },
  odin:   { label: 'Odin',            short: 'Odin',   color: 'var(--gold)', bg: 'var(--gold-bg)', bd: 'var(--gold-bd)' },
};

window._activeAgent  = null;     // currently live agent id (e.g. 'loki_m')
window._engineOn     = false;
window._lokiPillar   = 'loki_m'; // selected Loki sub-pillar
window._pendingPin   = null;
window._pendingAgent = null;

function selectLokiPillar(id) {
  window._lokiPillar = id;
  document.querySelectorAll('.loki-pill').forEach(p => p.classList.toggle('on', p.dataset.pillar === id));
}

function requestActivateLoki() { requestActivate(window._lokiPillar); }

function requestActivate(agent) {
  // Clicking the already-live agent deactivates (turns the engine off).
  if (window._engineOn && window._activeAgent === agent) { deactivate(); return; }
  window._pendingAgent = agent;
  window._pendingPin   = String(Math.floor(1000 + Math.random() * 9000));
  const meta = AGENT_META[agent];
  const tag  = document.getElementById('pin-agent-tag');
  tag.textContent = meta.label;
  tag.style.background = meta.bg;
  tag.style.border = '1px solid ' + meta.bd;
  tag.style.color  = meta.color;
  document.getElementById('pin-display').textContent = window._pendingPin;
  document.getElementById('pin-input').value = '';
  document.getElementById('pin-err').textContent = '';
  document.getElementById('pin-modal').style.display = 'flex';
  setTimeout(() => document.getElementById('pin-input').focus(), 80);
}

function closePinModal() {
  document.getElementById('pin-modal').style.display = 'none';
  window._pendingPin = null; window._pendingAgent = null;
}

function confirmPin() {
  const entered = document.getElementById('pin-input').value.trim();
  if (entered === window._pendingPin) {
    applyAgent(window._pendingAgent);
    closePinModal();
  } else {
    document.getElementById('pin-err').textContent = 'Incorrect PIN — please try again.';
    document.getElementById('pin-input').value = '';
    document.getElementById('pin-input').focus();
  }
}

async function applyAgent(agent) {
  try {
    await authFetch('/api/config/algorithms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active_agent: agent, engine_active: true, auto_kelly: true, kelly_percent: 1.0 }),
    });
    window._activeAgent = agent; window._engineOn = true;
    if (agent.startsWith('loki_')) selectLokiPillar(agent);
    refreshAgentUI();
    document.getElementById('set-engine').checked = true;
    toast(AGENT_META[agent].label + ' is now live');
  } catch (e) { toast('Failed to activate agent'); }
}

async function deactivate() {
  try {
    await authFetch('/api/config/algorithms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active_agent: window._activeAgent || 'loki_m', engine_active: false, auto_kelly: true, kelly_percent: 1.0 }),
    });
    window._engineOn = false;
    refreshAgentUI();
    document.getElementById('set-engine').checked = false;
    toast('Engine paused');
  } catch (e) { toast('Failed to pause engine'); }
}

function refreshAgentUI() {
  ['loki', 'thor', 'odin'].forEach(group => {
    const isLoki = group === 'loki';
    const live = window._engineOn && window._activeAgent &&
      (isLoki ? window._activeAgent.startsWith('loki_') : window._activeAgent === group);
    const status = document.getElementById('status-' + group);
    const btn = document.getElementById('actbtn-' + group);
    const row = document.getElementById('row-' + group);
    if (live) {
      status.className = 'agent-status active';
      status.innerHTML = '<span class="asdot"></span>ACTIVE';
      btn.className = 'act-btn active'; btn.textContent = 'Deactivate';
      row.classList.add('selected');
    } else {
      status.className = 'agent-status inactive'; status.textContent = 'INACTIVE';
      btn.className = 'act-btn inactive'; btn.textContent = 'Activate';
      row.classList.remove('selected');
    }
  });
}

async function refreshAgentState() {
  try {
    const d = await (await authFetch('/api/config/algorithms')).json();
    window._activeAgent = d.active_agent || 'loki_m';
    window._engineOn = !!d.engine_active;
    if (window._activeAgent.startsWith('loki_')) selectLokiPillar(window._activeAgent);
    document.getElementById('set-engine').checked = window._engineOn;
    refreshAgentUI();
  } catch (e) { /* not authed yet */ }
}

// ════════════════════════════════════════════════════════════
//  REAL DASHBOARD DATA
// ════════════════════════════════════════════════════════════
async function loadAccount() {
  try {
    const a = await (await authFetch('/api/account')).json();
    const eq = Number(a.equity || 0), bal = Number(a.balance || 0);
    document.getElementById('hdr-equity').textContent = fmtPrice(eq);
    document.getElementById('hdr-balance').textContent = fmtPrice(bal);
  } catch (e) { /* ignore */ }
}

function renderTradeHistory(list) {
  const body = document.getElementById('trade-hist-body');
  if (!body) return;
  if (!list || list.length === 0) {
    body.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:12px 0;text-align:center;">No trades yet. Activate an agent to begin.</div>';
    return;
  }
  body.innerHTML = list.slice(0, 10).map(t => {
    const meta = AGENT_META[t.agent_used] || { short: (t.agent_used || '—'), color: 'var(--t2)' };
    const sym = SYM_MAP[t.symbol] || t.symbol || '';
    const time = t.timestamp ? new Date(t.timestamp).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
    const pnl = Number(t.realized_pnl || 0);
    return `
    <div class="trade-row">
      <div class="trade-meta">
        <span class="mono f10 t3" style="flex-shrink:0;">${time}</span>
        <span class="fw7" style="font-size:11px;">${sym}</span>
        <span class="dir ${t.direction === 'BUY' ? 'buy' : 'sell'}" style="font-size:8px;padding:1px 6px;margin-bottom:0;">${t.direction || ''}</span>
        <span style="color:${meta.color};font-size:9px;font-weight:700;text-transform:uppercase;">${meta.short}</span>
        <span class="mono fw7" style="font-size:10px;margin-left:auto;flex-shrink:0;color:${pnl >= 0 ? 'var(--gr)' : 'var(--re)'};">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</span>
      </div>
      <div class="trade-reason">"${String(t.reasoning || '').replace(/</g, '&lt;').slice(0, 60)}"</div>
    </div>`;
  }).join('');
}

window._completed = [];
async function loadTradeHistory() {
  try {
    const r = await (await authFetch('/api/stats/history?limit=100')).json();
    const list = Array.isArray(r) ? r : [];
    renderTradeHistory(list);
    window._completed = list.filter(t => t.status === 'CLOSED');
    applyHistFilter();
  } catch (e) { renderTradeHistory([]); window._completed = []; renderCompleted([]); }
}

function applyHistFilter() {
  const q = (document.getElementById('hist-search')?.value || '').trim().toLowerCase();
  const ag = document.getElementById('hist-agent')?.value || '';
  let list = window._completed || [];
  if (q) list = list.filter(t => ((SYM_MAP[t.symbol] || t.symbol || '').toLowerCase().includes(q)));
  if (ag) list = list.filter(t => (t.agent_used || '').startsWith(ag));
  renderCompleted(list);
}

function renderCompleted(list) {
  const body = document.getElementById('completed-body');
  if (!body) return;
  if (!list.length) { body.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--t3);font-size:11px;padding:14px 0;">No completed trades yet.</td></tr>'; return; }
  body.innerHTML = list.slice(0, 30).map(t => {
    const meta = AGENT_META[t.agent_used] || { short: (t.agent_used || '—'), color: 'var(--t2)' };
    const sym = SYM_MAP[t.symbol] || t.symbol || '';
    const time = t.timestamp ? new Date(t.timestamp).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
    const pnl = Number(t.realized_pnl || 0);
    return `<tr>
      <td class="mono t2 f10">${time}</td>
      <td class="fw7">${sym}</td>
      <td><span class="sp ${t.direction === 'BUY' ? 'buy' : 'sell'}">${t.direction || ''}</span></td>
      <td style="color:${meta.color};font-size:10px;font-weight:700;text-transform:uppercase">${meta.short}</td>
      <td class="mono">${t.entry_price != null ? Number(t.entry_price).toLocaleString() : '—'}</td>
      <td class="mono">${t.close_price != null ? Number(t.close_price).toLocaleString() : '—'}</td>
      <td class="mono fw7" style="text-align:right;color:${pnl >= 0 ? 'var(--gr)' : 'var(--re)'}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</td>
    </tr>`;
  }).join('');
}

async function loadOpenPositions() {
  const body = document.getElementById('open-pos-body');
  if (!body) return;
  try {
    const list = await (await authFetch('/api/trades/positions?status=OPEN')).json();
    if (!Array.isArray(list) || !list.length) { body.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--t3);font-size:11px;padding:14px 0;">No open positions.</td></tr>'; return; }
    body.innerHTML = list.map(p => {
      const sym = SYM_MAP[p.symbol] || p.symbol || '';
      const pnl = Number(p.unrealized_pnl || 0);
      return `<tr>
        <td class="fw7">${sym}</td>
        <td><span class="sp ${p.side === 'BUY' ? 'buy' : 'sell'}">${p.side}</span></td>
        <td class="mono">${Number(p.quantity).toFixed(4)}</td>
        <td class="mono">${Number(p.entry_price).toLocaleString()}</td>
        <td class="mono">${p.current_price != null ? Number(p.current_price).toLocaleString() : '—'}</td>
        <td class="mono fw7" style="color:${pnl >= 0 ? 'var(--gr)' : 'var(--re)'}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</td>
        <td><button class="cbtn" onclick="closePosition('${p.id}')">Close</button></td>
      </tr>`;
    }).join('');
  } catch (e) { body.innerHTML = ''; }
}

async function closePosition(id) {
  try { await authFetch('/api/trades/positions/' + id, { method: 'DELETE' }); toast('Position closed'); loadOpenPositions(); loadTradeHistory(); loadAccount(); }
  catch (e) { toast('Failed to close position'); }
}

const AUDIT_LABELS = {
  ORDER: 'Order placed', ORDER_FILLED: 'Order filled', ORDER_REJECTED: 'Order rejected',
  KILL_SWITCH: 'Kill switch engaged', KILL_SWITCH_CLEARED: 'Kill switch cleared',
  KILL_SWITCH_GLOBAL: 'Global kill engaged', KILL_SWITCH_GLOBAL_CLEARED: 'Global kill cleared',
  DRAWDOWN_HALT: 'Drawdown auto-halt',
};
async function loadAuditLog() {
  const body = document.getElementById('audit-body');
  if (!body) return;
  try {
    const list = await (await authFetch('/api/trades/audit-log?limit=50')).json();
    renderNotifications(Array.isArray(list) ? list : []);
    if (!Array.isArray(list) || !list.length) {
      body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--t3);font-size:11px;padding:14px 0;">No audit events yet.</td></tr>';
      return;
    }
    body.innerHTML = list.map(e => {
      const time = e.created_at ? new Date(e.created_at).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
      const label = AUDIT_LABELS[e.event_type] || e.event_type || '—';
      const danger = /KILL|REJECT|HALT/.test(e.event_type || '');
      let detail = '';
      if (e.payload) { try { detail = typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload); } catch (_) {} }
      detail = String(detail).replace(/[{}"]/g, '').slice(0, 48);
      return `<tr>
        <td class="mono t2 f10">${time}</td>
        <td style="font-weight:700;color:${danger ? 'var(--re)' : 'var(--t1)'}">${label}</td>
        <td class="t2 f11">${e.broker || '—'}</td>
        <td class="mono f11">${e.symbol ? (SYM_MAP[e.symbol] || e.symbol) : '—'}</td>
        <td class="t3 f10">${detail || '—'}</td>
      </tr>`;
    }).join('');
  } catch (e) { body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--t3);font-size:11px;padding:14px 0;">Unable to load audit log.</td></tr>'; }
}

// ════════════════════════════════════════════════════════════
//  SETTINGS — wired to backend
// ════════════════════════════════════════════════════════════
async function loadFlags() {
  try {
    const cfg = await (await authFetch('/api/config/')).json();
    document.getElementById('set-auto').checked = String(cfg.auto_mode).toLowerCase() === 'true';
  } catch (e) { /* ignore */ }
}
async function toggleAuto() { try { await authFetch('/api/config/toggle-auto', { method: 'POST' }); toast('Auto mode updated'); } catch (e) {} }
async function toggleEngine() {
  const on = document.getElementById('set-engine').checked;
  if (on) { await applyAgent(window._activeAgent || window._lokiPillar); } else { await deactivate(); }
}

async function loadKeys() {
  try {
    const k = await (await authFetch('/api/config/keys')).json();
    const set = (id, ok) => { const el = document.getElementById(id); el.className = 'kbadge ' + (ok ? 'ok' : 'no'); el.textContent = ok ? 'Configured' : 'Not set'; };
    set('kb-gemini', k.gemini && k.gemini.configured);
    set('kb-crypto', k.crypto && k.crypto.configured);
    set('kb-forex', k.forex && k.forex.configured);
    if (k.forex && k.forex.account_id) document.getElementById('key-oanda-acc').placeholder = k.forex.account_id;
    if (k.forex && k.forex.environment) document.getElementById('key-oanda-env').value = k.forex.environment;
  } catch (e) { /* non-admin: endpoint 403 — keys card still usable via brokers */ }
}

async function saveKeys() {
  const v = id => document.getElementById(id).value.trim();
  const payload = {};
  if (v('key-gemini')) payload.gemini_api_key = v('key-gemini');
  if (v('key-binance')) payload.binance_api_key = v('key-binance');
  if (v('key-binance-secret')) payload.binance_secret_key = v('key-binance-secret');
  if (v('key-oanda')) payload.oanda_api_key = v('key-oanda');
  if (v('key-oanda-acc')) payload.oanda_account_id = v('key-oanda-acc');
  payload.oanda_environment = document.getElementById('key-oanda-env').value;
  try {
    await authFetch('/api/config/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    ['key-gemini', 'key-binance', 'key-binance-secret', 'key-oanda', 'key-oanda-acc'].forEach(id => document.getElementById(id).value = '');
    toast('API keys saved'); loadKeys();
  } catch (e) { toast('Failed to save keys (admin only)'); }
}

async function loadUsers() {
  try {
    const users = await (await authFetch('/api/admin/users')).json();
    const box = document.getElementById('user-list');
    box.innerHTML = users.map(u => `
      <div class="user-row">
        <div><div style="font-size:12.5px;font-weight:700;">${u.username}</div>
        <div style="font-size:9.5px;color:${u.is_admin ? 'var(--gold)' : 'var(--t3)'};text-transform:uppercase;letter-spacing:.05em;">${u.is_admin ? 'Admin' : 'User'}</div></div>
        ${window._me && window._me.username === u.username ? '' : `<button class="cbtn" onclick="deleteUser('${u.id}')">Remove</button>`}
      </div>`).join('') || '<div style="font-size:11px;color:var(--t3);">No users.</div>';
  } catch (e) { /* non-admin */ }
}

async function createUser() {
  const username = document.getElementById('nu-name').value.trim();
  const password = document.getElementById('nu-pass').value;
  const is_admin = document.getElementById('nu-admin').checked;
  if (!username || !password) { toast('Enter username and password'); return; }
  try {
    await authFetch('/api/admin/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password, is_admin }) });
    document.getElementById('nu-name').value = ''; document.getElementById('nu-pass').value = ''; document.getElementById('nu-admin').checked = false;
    toast('User created'); loadUsers();
  } catch (e) { toast('Failed to create user'); }
}

async function deleteUser(id) {
  try { await authFetch('/api/admin/users/' + id, { method: 'DELETE' }); toast('User removed'); loadUsers(); }
  catch (e) { toast('Failed to remove user'); }
}

async function loadGeminiUsage() {
  try {
    const u = await (await authFetch('/api/config/gemini-usage')).json();
    document.getElementById('usage-calls').textContent = u.calls_today;
    document.getElementById('usage-cap-lbl').textContent = u.cap;
    document.getElementById('usage-fill').style.width = Math.min(100, (u.calls_today / Math.max(1, u.cap)) * 100) + '%';
    document.getElementById('cfg-cap').value = u.cap;
    document.getElementById('cfg-interval').value = u.min_interval;
    document.getElementById('cfg-news').value = u.news_interval;
  } catch (e) { /* non-admin */ }
}

async function saveLimits() {
  const items = [
    ['gemini_daily_cap', document.getElementById('cfg-cap').value],
    ['gemini_min_interval_seconds', document.getElementById('cfg-interval').value],
    ['news_scan_interval_seconds', document.getElementById('cfg-news').value],
  ];
  try {
    for (const [key, value] of items) {
      await authFetch('/api/config/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key, value: String(value) }) });
    }
    toast('Limits saved'); loadGeminiUsage();
  } catch (e) { toast('Failed to save limits (admin only)'); }
}

async function resetWallet() {
  const amount = Number(document.getElementById('reset-amount') ? document.getElementById('reset-amount').value : 100000);
  if (!amount || amount < 1000) { toast('Enter a valid amount'); return; }
  try {
    await authFetch('/api/config/wallet/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount }) });
    toast('Wallet reset'); loadAccount();
  } catch (e) { toast('Failed to reset wallet'); }
}

// ── GDPR / data controls ──
async function exportData() {
  try {
    const d = await (await authFetch('/api/account/export')).json();
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'asgard-data-export.json';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast('Data export downloaded');
  } catch (e) { toast('Failed to export data'); }
}

async function deleteAccount() {
  if (!confirm('Permanently delete your account? This removes broker keys, closes paper positions, and anonymises your profile. This CANNOT be undone.')) return;
  const typed = prompt('Type DELETE to confirm permanent erasure of your account:');
  if (typed !== 'DELETE') { toast('Deletion cancelled'); return; }
  try {
    await authFetch('/api/account', { method: 'DELETE' });
    toast('Account deleted');
    clearToken();
    setTimeout(() => location.reload(), 1200);
  } catch (e) { toast('Failed to delete account'); }
}

function launchSimulator() {
  const capital = Number(document.getElementById('sim-capital').value || 100000);
  const token = getToken();
  const url = '/simulator?capital=' + capital + (token ? '&token=' + encodeURIComponent(token) : '');
  window.open(url, '_blank');
}

// ════════════════════════════════════════════════════════════
//  SAFETY CONTROLS — kill switch + live mode
// ════════════════════════════════════════════════════════════
window._safety = { user_halted: false, global_halted: false };

function renderSafetyBanner() {
  const b = document.getElementById('safety-banner');
  if (!b) return;
  const msgs = [];
  if (window._safety.global_halted) msgs.push('Global kill switch is ACTIVE — real-money execution is halted platform-wide.');
  if (window._safety.user_halted)   msgs.push('Your kill switch is ACTIVE — automated trading is halted for your account.');
  if (msgs.length) { b.classList.remove('hide'); b.innerHTML = msgs.join('<br>'); }
  else b.classList.add('hide');
}

async function loadSafety() {
  try {
    const s = await (await authFetch('/api/trades/kill-switch')).json();
    window._safety.user_halted   = !!s.user_halted;
    window._safety.global_halted = !!s.global_halted;
    const u = document.getElementById('set-killswitch');
    const g = document.getElementById('set-globalkill');
    if (u) u.checked = !!s.user_halted;
    if (g) g.checked = !!s.global_halted;
    renderSafetyBanner();
  } catch (e) { /* not authed */ }
}

async function toggleKillSwitch(e) {
  const on = e.target.checked;
  try {
    await authFetch('/api/trades/kill-switch', { method: on ? 'POST' : 'DELETE' });
    window._safety.user_halted = on;
    renderSafetyBanner();
    toast(on ? 'Kill switch engaged — trading halted' : 'Kill switch cleared — trading resumed');
  } catch (err) { e.target.checked = !on; toast('Failed to update kill switch'); }
}

async function toggleGlobalKill(e) {
  const halt = e.target.checked;
  if (halt && !confirm('Halt real-money execution for ALL users on the platform?')) { e.target.checked = false; return; }
  try {
    await authFetch('/api/trades/kill-switch/global?halt=' + (halt ? 'true' : 'false'), { method: 'POST' });
    window._safety.global_halted = halt;
    renderSafetyBanner();
    toast(halt ? 'Global kill switch engaged' : 'Global kill switch cleared');
  } catch (err) { e.target.checked = !halt; toast('Failed (admin only)'); }
}

async function loadLiveMode() {
  try {
    const d = await (await authFetch('/api/account/live-mode')).json();
    const el = document.getElementById('set-livemode');
    if (el) el.checked = !!d.live_mode;
  } catch (e) { /* ignore */ }
}

async function toggleLiveMode(e) {
  const on = e.target.checked;
  if (on && !confirm('Enable LIVE mode? Orders will be sent to your connected broker using REAL funds. Make sure you understand the risk.')) {
    e.target.checked = false; return;
  }
  try {
    const r = await authFetch('/api/account/live-mode', { method: 'POST' });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      e.target.checked = !on;
      toast(err.detail || 'Failed to change live mode');
      return;
    }
    const d = await r.json();
    e.target.checked = !!d.live_mode;
    toast(d.live_mode ? 'LIVE mode enabled — real funds active' : 'LIVE mode disabled — paper trading');
  } catch (err) { e.target.checked = !on; toast('Failed to change live mode'); }
}

// ════════════════════════════════════════════════════════════
//  BROKER CONNECTIONS (per-user)
// ════════════════════════════════════════════════════════════
const BROKER_META = {
  oanda:    { label: 'OANDA',    color: 'var(--blue)' },
  binance:  { label: 'Binance',  color: 'var(--gold)' },
  coinbase: { label: 'Coinbase', color: 'var(--pu)' },
};

function onBrokerSelect() {
  const b = document.getElementById('bk-broker').value;
  // OANDA uses token + account_id (no secret); crypto uses key + secret (no account id)
  document.getElementById('bk-secret-wrap').classList.toggle('hide', b === 'oanda');
  document.getElementById('bk-acc-wrap').classList.toggle('hide', b !== 'oanda');
}

function renderBrokers(list) {
  const box = document.getElementById('broker-list');
  if (!box) return;
  if (!Array.isArray(list) || !list.length) {
    box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:6px 0;">No broker connections yet.</div>';
    return;
  }
  box.innerHTML = list.map(c => {
    const meta = BROKER_META[c.broker] || { label: c.broker, color: 'var(--t2)' };
    const isEnv = String(c.id).startsWith('env-');
    const acc = c.account_id && c.account_id !== 'ENV' ? c.account_id : '';
    return `<div class="user-row">
      <div><div style="font-size:12.5px;font-weight:700;color:${meta.color}">${meta.label}<span class="t3" style="font-weight:500;font-size:10px;margin-left:6px;text-transform:uppercase;">${c.environment}</span></div>
      <div style="font-size:9.5px;color:var(--t3);">${acc ? acc + ' · ' : ''}${isEnv ? 'system key' : 'your key'} ${c.is_active ? '· <span style="color:var(--gr)">active</span>' : ''}</div></div>
      ${isEnv ? '' : `<button class="cbtn" onclick="deleteBroker('${c.id}')">Remove</button>`}
    </div>`;
  }).join('');
}

async function loadBrokers() {
  try {
    const list = await (await authFetch('/api/brokers')).json();
    renderBrokers(list);
  } catch (e) { renderBrokers([]); }
}

async function saveBroker() {
  const broker = document.getElementById('bk-broker').value;
  const environment = document.getElementById('bk-env').value;
  const api_key = document.getElementById('bk-key').value.trim();
  if (!api_key) { toast('Enter an API key'); return; }
  const payload = { broker, environment, api_key };
  if (broker === 'oanda') {
    const acc = document.getElementById('bk-acc').value.trim();
    if (acc) payload.account_id = acc;
  } else {
    const sec = document.getElementById('bk-secret').value.trim();
    if (sec) payload.api_secret = sec;
  }
  try {
    const r = await authFetch('/api/brokers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!r.ok) { const err = await r.json().catch(() => ({})); toast(err.detail || 'Failed to save connection'); return; }
    ['bk-key', 'bk-secret', 'bk-acc'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    toast('Broker connection saved'); loadBrokers();
  } catch (e) { toast('Failed to save connection'); }
}

async function deleteBroker(id) {
  if (!confirm('Remove this broker connection? Live mode will be disabled if this was your only active connection.')) return;
  try {
    await authFetch('/api/brokers/' + encodeURIComponent(id), { method: 'DELETE' });
    toast('Connection removed'); loadBrokers(); loadLiveMode();
  } catch (e) { toast('Failed to remove connection'); }
}

// PIN input — Enter key shortcut
document.getElementById('pin-input').addEventListener('keydown', e => { if (e.key === 'Enter') confirmPin(); });
document.getElementById('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });

// Global ESC — close transient overlays/menus (never the login gate)
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const pin = document.getElementById('pin-modal');
  if (pin && pin.style.display === 'flex') { closePinModal(); return; }
  closeProfileMenu(); closeNotif();
});

// ════════════════════════════════════════════════════════════
//  BOOT
// ════════════════════════════════════════════════════════════
async function boot() {
  if (!getToken()) { showLogin(); return; }
  let me;
  try { me = await (await authFetch('/api/auth/me')).json(); }
  catch (e) { showLogin(); return; }
  window._me = me;
  hideLogin();
  document.getElementById('pmenu-name').textContent = me.username;
  document.getElementById('pmenu-role').textContent = me.is_admin ? 'Administrator' : 'User';
  if (me.is_admin) {
    document.getElementById('card-usermgmt').classList.remove('hide');
    document.getElementById('card-gemini').classList.remove('hide');
    document.getElementById('row-global-kill').classList.remove('hide');
  }
  // Charts seed (unauthenticated history endpoint)
  loadStats();
  loadHistory('BTCUSDT', window._range);
  ['ETHUSDT', 'EUR_USD', 'XAU_USD'].forEach(s => loadHistory(s, window._range));
  // Authenticated data
  loadAccount();
  loadTradeHistory();
  loadOpenPositions();
  refreshAgentState();
  loadFlags();
  loadKeys();
  loadGeminiUsage();
  loadUsers();
  loadSafety();
  loadLiveMode();
  loadBrokers();
  onBrokerSelect();
  loadAuditLog();
  connectWS();
  // Periodic refresh of live account + trades
  clearInterval(window._pollT);
  window._pollT = setInterval(() => { loadAccount(); loadTradeHistory(); loadOpenPositions(); loadStats(); loadAuditLog(); }, 15000);
}

boot();
