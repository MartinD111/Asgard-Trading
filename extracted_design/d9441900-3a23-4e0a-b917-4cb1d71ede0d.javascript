// Mock market + portfolio data for the Asgard terminal UI kit.
window.ASGARD_DATA = {
  tickers: [
    { symbol: 'BTCUSDT', base: 'BTC', quote: 'USDT', price: 67482.10, changePercent: 2.41, high: 68120, low: 66540 },
    { symbol: 'ETHUSDT', base: 'ETH', quote: 'USDT', price: 3512.40, changePercent: -1.08, high: 3640, low: 3480 },
    { symbol: 'XAUUSD',  base: 'XAU', quote: 'USD',  price: 2356.80, changePercent: 0.62, high: 2371, low: 2342 },
    { symbol: 'EURUSD',  base: 'EUR', quote: 'USD',  price: 1.0842, changePercent: -0.18, high: 1.0871, low: 1.0829 },
  ],
  signals: [
    { id: 1, symbol: 'BTCUSDT', base: 'BTC', quote: 'USDT', direction: 'BUY', confidence: 82, reason: 'Momentum breakout confirmed by rising volume and bullish MACD cross.' },
    { id: 2, symbol: 'XAUUSD', base: 'XAU', quote: 'USD', direction: 'SELL', confidence: 67, reason: 'Overbought RSI with bearish divergence on the 4H timeframe.' },
    { id: 3, symbol: 'ETHUSDT', base: 'ETH', quote: 'USDT', direction: 'BUY', confidence: 74, reason: 'Reclaimed key support; correlation with BTC strengthening.' },
    { id: 4, symbol: 'EURUSD', base: 'EUR', quote: 'USD', direction: 'SELL', confidence: 58, reason: 'Dollar strength ahead of CPI; range resistance holding.' },
  ],
  kpis: [
    { label: 'Total Profit (Daily)', value: '+$1,204.50', sub: '+1.21% equity growth', accent: 'green' },
    { label: 'Avg Win Rate', value: '61.4%', sub: 'Across active agents', accent: 'blue' },
    { label: 'Profit Factor', value: '1.84×', sub: 'High efficiency zone', accent: 'purple' },
    { label: 'Max Drawdown', value: '−4.20%', sub: 'Below risk ceiling', accent: 'red' },
  ],
  agents: [
    { key: 'loki', name: 'Loki', pnl: 642.10, winrate: 64, trades: 38, color: 'var(--blue)' },
    { key: 'thor', name: 'Thor', pnl: 388.40, winrate: 59, trades: 27, color: 'var(--pu)' },
    { key: 'odin', name: 'Odin', pnl: 174.00, winrate: 57, trades: 19, color: 'var(--gold)' },
  ],
  history: [
    { time: 'Jun 24, 14:02', base: 'BTC', quote: 'USDT', side: 'BUY', agent: 'LOKI', entry: 66980, close: 67410, pnl: 430.00 },
    { time: 'Jun 24, 11:48', base: 'ETH', quote: 'USDT', side: 'SELL', agent: 'THOR', entry: 3548, close: 3585, pnl: -37.00 },
    { time: 'Jun 24, 09:15', base: 'XAU', quote: 'USD', side: 'BUY', agent: 'ODIN', entry: 2341, close: 2356, pnl: 150.00 },
    { time: 'Jun 23, 22:30', base: 'EUR', quote: 'USD', side: 'SELL', agent: 'LOKI', entry: 1.0871, close: 1.0842, pnl: 29.00 },
    { time: 'Jun 23, 18:04', base: 'BTC', quote: 'USDT', side: 'BUY', agent: 'MANUAL', entry: 66500, close: 66120, pnl: -380.00 },
  ],
  portfolio: { equity: 11204.50, balance: 8420.30 },
  // a soft random-walk price series for the chart
  chart: (() => {
    const pts = []; let v = 66000;
    for (let i = 0; i < 60; i++) { v += (Math.sin(i / 4) * 120) + (Math.random() - 0.45) * 180; pts.push(v); }
    return pts;
  })(),
};
