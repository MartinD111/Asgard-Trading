"""
Performance metrics computed from a completed backtest run.

All functions are pure — they take lists of numbers and return numbers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class BacktestMetrics:
    symbol: str
    timeframe: str
    date_from: str
    date_to: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    expectancy: float          # average $ PnL per trade after costs
    total_costs: float         # total transaction costs paid
    equity_curve: list[float] = field(default_factory=list)
    trade_log: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "period": f"{self.date_from} → {self.date_to}",
            "initial_capital": round(self.initial_capital, 2),
            "final_equity": round(self.final_equity, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": round(self.annualized_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "win_rate_pct": round(self.win_rate_pct, 1),
            "profit_factor": round(self.profit_factor, 3),
            "trade_count": self.trade_count,
            "expectancy": round(self.expectancy, 4),
            "total_costs": round(self.total_costs, 4),
        }


def _annualized_factor(candle_count: int, timeframe_minutes: int = 5) -> float:
    """How many candle-periods fit in one trading year (252 days × 24h for crypto)."""
    minutes_per_year = 252 * 24 * 60
    return minutes_per_year / max(timeframe_minutes, 1) / max(candle_count, 1)


def compute_metrics(
    symbol: str,
    timeframe: str,
    date_from: str,
    date_to: str,
    initial_capital: float,
    equity_curve: list[float],
    trade_log: list[dict],
    candle_count: int,
    timeframe_minutes: int = 5,
) -> BacktestMetrics:
    if not equity_curve:
        equity_curve = [initial_capital]

    final_equity = equity_curve[-1]
    total_return_pct = (final_equity - initial_capital) / max(initial_capital, 1e-9) * 100

    # Per-candle returns for Sharpe/Sortino
    returns: list[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        ret = (equity_curve[i] - prev) / max(abs(prev), 1e-9)
        returns.append(ret)

    # periods_per_year: how many M5 candles fit in a 252-day trading year (24h for crypto)
    periods_per_year = 252 * 24 * 60 / max(timeframe_minutes, 1)
    # scaling_factor: how many test-periods fit in one year (used for annualisation)
    scaling_factor = periods_per_year / max(candle_count, 1)

    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std_r = math.sqrt(variance) if variance > 0 else 1e-9
        sharpe = (mean_r / std_r) * math.sqrt(periods_per_year)

        downside = [min(r, 0) for r in returns]
        down_var = sum(r ** 2 for r in downside) / max(len(downside), 1)
        down_std = math.sqrt(down_var) if down_var > 0 else 1e-9
        sortino = (mean_r / down_std) * math.sqrt(periods_per_year)
    else:
        sharpe = sortino = 0.0

    # Use log-space to avoid float64 overflow on large exponents
    try:
        ratio = final_equity / max(initial_capital, 1e-9)
        if ratio > 0 and scaling_factor > 0:
            ann_return = (math.exp(math.log(ratio) * scaling_factor) - 1) * 100
            ann_return = max(-100.0, min(ann_return, 1e6))  # sanity cap
        else:
            ann_return = 0.0
    except (ValueError, OverflowError):
        ann_return = 0.0

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / max(peak, 1e-9) * 100
        if dd > max_dd:
            max_dd = dd

    # Trade stats
    pnls = [t["pnl"] for t in trade_log]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    trade_count = len(pnls)
    win_rate = len(wins) / max(trade_count, 1) * 100
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / max(gross_loss, 1e-9)
    avg_win = sum(wins) / max(len(wins), 1)
    avg_loss = sum(losses) / max(len(losses), 1)
    expectancy = sum(pnls) / max(trade_count, 1)
    total_costs = sum(t.get("cost", 0) for t in trade_log)

    return BacktestMetrics(
        symbol=symbol,
        timeframe=timeframe,
        date_from=date_from,
        date_to=date_to,
        initial_capital=initial_capital,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        annualized_return_pct=ann_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd,
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        trade_count=trade_count,
        winning_trades=len(wins),
        losing_trades=len(losses),
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        total_costs=total_costs,
        equity_curve=equity_curve,
        trade_log=trade_log,
    )
