"""
Backtester CLI.

Usage:
    python -m backtest --symbol XAU_USD --days 90
    python -m backtest --symbol BTCUSDT --days 30 --agent odin --capital 50000
    python -m backtest --symbol EUR_USD --days 60 --output results.json

Options:
    --symbol    Instrument to backtest (default: XAU_USD)
    --days      Look-back period in days (default: 90)
    --agent     Signal weight preset: loki | thor | odin (default: loki)
    --capital   Starting capital in USD (default: 10000)
    --threshold Minimum |final_score| to enter a trade (default: 0.35)
    --output    Optional path to write JSON results
    --all       Run all symbols sequentially and compare
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Allow running from repo root: python -m backtest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backtest.engine import run_backtest
from services.decision_engine import ALL_SYMBOLS


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Asgard Trading Backtester")
    p.add_argument("--symbol",    default="XAU_USD")
    p.add_argument("--days",      type=int,   default=90)
    p.add_argument("--agent",     default="loki", choices=["loki", "thor", "odin"])
    p.add_argument("--capital",   type=float, default=10_000.0)
    p.add_argument("--threshold", type=float, default=0.35)
    p.add_argument("--confidence",type=float, default=0.40)
    p.add_argument("--output",    default=None,  help="Path to write JSON results")
    p.add_argument("--all",       action="store_true", help="Run all symbols")
    return p.parse_args()


def _print_summary(m) -> None:
    s = m.summary()
    width = 46
    print("\n" + "─" * width)
    print(f"  Backtest: {s['symbol']}  ({s['period']})")
    print("─" * width)
    print(f"  Capital       {s['initial_capital']:>12,.2f}  →  {s['final_equity']:>12,.2f}")
    print(f"  Total return  {s['total_return_pct']:>+11.2f}%")
    print(f"  Ann. return   {s['annualized_return_pct']:>+11.2f}%")
    print(f"  Sharpe        {s['sharpe_ratio']:>12.3f}")
    print(f"  Sortino       {s['sortino_ratio']:>12.3f}")
    print(f"  Max drawdown  {s['max_drawdown_pct']:>11.2f}%")
    print(f"  Win rate      {s['win_rate_pct']:>11.1f}%")
    print(f"  Profit factor {s['profit_factor']:>12.3f}")
    print(f"  Trades        {s['trade_count']:>12d}")
    print(f"  Expectancy    {s['expectancy']:>+11.4f}")
    print(f"  Total costs   {s['total_costs']:>12.4f}")
    print("─" * width + "\n")


async def _main() -> None:
    args = _parse_args()

    # Require env to be set so DB/Redis imports don't explode
    for var in ("JWT_SECRET_KEY", "DATABASE_URL", "REDIS_URL", "FERNET_KEY", "ADMIN_PASSWORD"):
        if not os.getenv(var):
            print(f"ERROR: {var} not set. Copy .env.example to .env and fill in values.", file=sys.stderr)
            sys.exit(1)

    symbols = ALL_SYMBOLS if args.all else [args.symbol]
    results = []

    for sym in symbols:
        print(f"Running backtest for {sym} over {args.days} days (agent={args.agent}) ...")
        m = await run_backtest(
            symbol=sym,
            days=args.days,
            initial_capital=args.capital,
            agent=args.agent,
            score_threshold=args.threshold,
            confidence_threshold=args.confidence,
        )
        _print_summary(m)
        results.append(m.summary())

    if args.output:
        payload = {
            "results": results,
            "equity_curves": {
                sym: m.equity_curve
                for sym, m in zip(symbols, [
                    await run_backtest(s, days=args.days, initial_capital=args.capital,
                                       agent=args.agent, score_threshold=args.threshold,
                                       confidence_threshold=args.confidence)
                    for s in symbols
                ])
            } if args.all else {symbols[0]: results[0]} if results else {},
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"Results written to {args.output}")


if __name__ == "__main__":
    asyncio.run(_main())
