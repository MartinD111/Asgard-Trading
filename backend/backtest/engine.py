"""
Event-driven backtester.

Replays historical M5 candles through compute_signal() + RiskManager SL/TP
with a realistic cost model. The signal path is identical to the live engine
so backtest results directly predict live paper/real behaviour.

Usage (programmatic):
    from backtest.engine import run_backtest
    metrics = await run_backtest("XAU_USD", days=90)
    print(metrics.summary())

Usage (CLI):
    python -m backtest --symbol XAU_USD --days 90 --agent loki
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backtest.cost_model import get_cost_model
from backtest.metrics import BacktestMetrics, compute_metrics
from services.risk_manager import RiskManager
from services.signals import compute_signal, AGENT_WEIGHTS

logger = logging.getLogger(__name__)

# Minimum candles in the look-back window before we allow a signal
MIN_LOOKBACK = 50

# How many candles to feed as context per evaluation step
CONTEXT_WINDOW = 50


@dataclass
class _Position:
    side: str            # "BUY" | "SELL"
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_idx: int
    entry_time: str
    entry_cost: float


async def run_backtest(
    symbol: str,
    days: int = 90,
    initial_capital: float = 10_000.0,
    agent: str = "loki",
    weights: dict[str, float] | None = None,
    score_threshold: float = 0.35,
    confidence_threshold: float = 0.40,
    risk_per_trade: float = 0.01,
    max_drawdown_limit: float = 0.20,
    since: datetime | None = None,
    until: datetime | None = None,
    candles: list[dict] | None = None,
) -> BacktestMetrics:
    """
    Run a full backtest for `symbol` over the specified period.

    Parameters
    ----------
    candles : If provided, use these candles directly (skips DB fetch).
              Useful for unit tests or custom data injection.
    """
    # ── Load candles ────────────────────────────────────────────
    if candles is None:
        from services.candle_store import get_candles as _get
        now = until or datetime.now(timezone.utc)
        start = since or (now - timedelta(days=days))
        candles = await _get(symbol, timeframe="M5", limit=0, since=start, until=now)

    if len(candles) < MIN_LOOKBACK + 2:
        logger.warning(f"[backtest] {symbol}: only {len(candles)} candles, need {MIN_LOOKBACK + 2}+")
        return _empty_metrics(symbol, initial_capital)

    cost_model = get_cost_model(symbol)
    rm = RiskManager(initial_balance=initial_capital)
    w = weights or AGENT_WEIGHTS.get(agent, AGENT_WEIGHTS["loki"])

    equity = initial_capital
    equity_curve: list[float] = [initial_capital]
    trade_log: list[dict] = []
    position: _Position | None = None
    halted = False

    date_from = candles[0]["time"][:10]
    date_to = candles[-1]["time"][:10]

    for i in range(MIN_LOOKBACK, len(candles)):
        candle = candles[i]
        price = float(candle["close"])
        high = float(candle.get("high", price))
        low = float(candle.get("low", price))

        # ── Manage open position ────────────────────────────────
        if position is not None:
            # Check SL/TP on this candle's high/low (more realistic than close)
            hit_sl = hit_tp = False
            if position.side == "BUY":
                if low <= position.stop_loss:
                    hit_sl, exit_price = True, position.stop_loss
                elif high >= position.take_profit:
                    hit_tp, exit_price = True, position.take_profit
            else:
                if high >= position.stop_loss:
                    hit_sl, exit_price = True, position.stop_loss
                elif low <= position.take_profit:
                    hit_tp, exit_price = True, position.take_profit

            if hit_sl or hit_tp:
                exit_cost = cost_model.exit_cost(exit_price, position.quantity)
                if position.side == "BUY":
                    gross_pnl = (exit_price - position.entry_price) * position.quantity
                else:
                    gross_pnl = (position.entry_price - exit_price) * position.quantity
                net_pnl = gross_pnl - exit_cost - position.entry_cost
                equity += net_pnl
                trade_log.append({
                    "symbol": symbol,
                    "side": position.side,
                    "entry_time": position.entry_time,
                    "exit_time": candle["time"],
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "quantity": position.quantity,
                    "pnl": net_pnl,
                    "cost": exit_cost + position.entry_cost,
                    "reason": "TAKE_PROFIT" if hit_tp else "STOP_LOSS",
                })
                position = None
                equity_curve.append(equity)

                # Drawdown halt
                if rm.check_drawdown(equity):
                    halted = True
                    logger.warning(f"[backtest] {symbol}: drawdown limit reached at candle {i}. Halting.")
                    break
            else:
                equity_curve.append(equity)
            continue  # only one position at a time

        if halted:
            equity_curve.append(equity)
            continue

        # ── Evaluate signal ─────────────────────────────────────
        context = candles[max(0, i - CONTEXT_WINDOW):i]
        sig = compute_signal(context, symbol=symbol, gemini_prob=0.0, weights=w, agent=agent)

        if abs(sig.final_score) < score_threshold or sig.confidence < confidence_threshold:
            equity_curve.append(equity)
            continue

        # ── Size position ───────────────────────────────────────
        from services.risk_manager import RiskManager as _RM
        atr = _atr(context)
        sl = rm.calculate_stop_loss(sig.direction, price, atr=atr)
        tp = rm.calculate_take_profit(sig.direction, price, stop_loss=sl)
        qty = rm.position_size(equity, price, sl, win_probability=0.55,
                               global_risk_multiplier=1.0)
        if qty <= 0:
            equity_curve.append(equity)
            continue

        entry_cost = cost_model.entry_cost(price, qty)
        equity -= entry_cost  # deduct cost immediately

        position = _Position(
            side=sig.direction,
            entry_price=price,
            quantity=qty,
            stop_loss=sl,
            take_profit=tp,
            entry_idx=i,
            entry_time=candle["time"],
            entry_cost=entry_cost,
        )
        equity_curve.append(equity)

    # ── Force-close any open position at last candle ────────────
    if position is not None:
        last_price = float(candles[-1]["close"])
        exit_cost = cost_model.exit_cost(last_price, position.quantity)
        if position.side == "BUY":
            gross_pnl = (last_price - position.entry_price) * position.quantity
        else:
            gross_pnl = (position.entry_price - last_price) * position.quantity
        net_pnl = gross_pnl - exit_cost - position.entry_cost
        equity += net_pnl
        trade_log.append({
            "symbol": symbol,
            "side": position.side,
            "entry_time": position.entry_time,
            "exit_time": candles[-1]["time"],
            "entry_price": position.entry_price,
            "exit_price": last_price,
            "quantity": position.quantity,
            "pnl": net_pnl,
            "cost": exit_cost + position.entry_cost,
            "reason": "END_OF_DATA",
        })
        equity_curve.append(equity)

    return compute_metrics(
        symbol=symbol,
        timeframe="M5",
        date_from=date_from,
        date_to=date_to,
        initial_capital=initial_capital,
        equity_curve=equity_curve,
        trade_log=trade_log,
        candle_count=len(candles),
        timeframe_minutes=5,
    )


def _atr(candles: list[dict], period: int = 14) -> float:
    """Simple ATR over last `period` candles."""
    if len(candles) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, min(period + 1, len(candles))):
        c = candles[-i]
        prev_c = candles[-(i + 1)]
        high = float(c.get("high", c["close"]))
        low = float(c.get("low", c["close"]))
        prev_close = float(prev_c["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def _empty_metrics(symbol: str, capital: float) -> BacktestMetrics:
    from backtest.metrics import BacktestMetrics
    return BacktestMetrics(
        symbol=symbol, timeframe="M5", date_from="", date_to="",
        initial_capital=capital, final_equity=capital,
        total_return_pct=0.0, annualized_return_pct=0.0,
        sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown_pct=0.0,
        win_rate_pct=0.0, profit_factor=0.0, trade_count=0,
        winning_trades=0, losing_trades=0, avg_win=0.0, avg_loss=0.0,
        expectancy=0.0, total_costs=0.0,
    )
