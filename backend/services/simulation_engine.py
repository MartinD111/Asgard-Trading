"""
Simulation Engine — live paper-trading for simulation sessions.

For every RUNNING row in `simulation_sessions` this engine:
  1. Evaluates each tradable symbol using REAL technical + chart-pattern signals
     computed from live market candles (the same scoring helpers the real
     DecisionEngine uses).
  2. Opens simulated positions into `simulation_trades` when a signal qualifies
     and the session has no open position on that symbol yet.
  3. Monitors open positions against the latest price and closes them at their
     stop-loss / take-profit, settling realised P&L into `simulation_accounts`.
  4. Records a human-readable reason for every open/close into `simulation_logs`.

Nothing here is fabricated: prices come from Redis (`last_price:*`, `candles:*`),
which the MarketDataService populates from live exchange feeds. Win rate is a
property of the closed trades, not a hardcoded number.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import text

from db.database import AsyncSessionLocal
from services.indicators import technical_score as _calculate_technical_score
from services.decision_engine import ALL_SYMBOLS
from services.pattern_recognizer import analyze_patterns

logger = logging.getLogger(__name__)

# How often the engine evaluates open sessions (seconds).
SIM_INTERVAL = 5

# A blended signal must clear this magnitude before a simulated trade is opened.
# Kept modest so live data actually produces trades, but high enough that the
# engine is selective rather than trading every tick.
SIM_SCORE_THRESHOLD = 0.25

# Risk framing per simulated trade.
NOTIONAL_FRACTION = 0.10   # deploy 10% of balance as notional per position
STOP_LOSS_PCT = 0.004      # 0.4% stop
TAKE_PROFIT_PCT = 0.008    # 0.8% target (1:2 risk/reward)


class SimulationEngine:
    def __init__(self, redis: aioredis.Redis, ws_manager, interval: int = SIM_INTERVAL):
        self.redis = redis
        self.ws_manager = ws_manager
        self.interval = interval

    async def run_loop(self):
        logger.info(f"SimulationEngine started (interval: {self.interval}s)")
        while True:
            try:
                await self._cycle()
            except Exception as e:
                logger.error(f"SimulationEngine cycle error: {e}")
            await asyncio.sleep(self.interval)

    async def _cycle(self):
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                text("SELECT id FROM simulation_sessions WHERE status='RUNNING'")
            )
            session_ids = [str(r[0]) for r in res.fetchall()]

        for sid in session_ids:
            try:
                await self._manage_open_trades(sid)
                await self._look_for_entries(sid)
                await self._refresh_equity(sid)
            except Exception as e:
                logger.error(f"SimulationEngine session {sid} error: {e}")

    # ─── Pricing helpers ────────────────────────────────────────
    async def _last_price(self, symbol: str) -> float | None:
        raw = await self.redis.get(f"last_price:{symbol}")
        if raw is None:
            return None
        try:
            price = float(raw)
            return price if price > 0 else None
        except (TypeError, ValueError):
            return None

    async def _candles(self, symbol: str) -> list[dict]:
        raw = await self.redis.get(f"candles:{symbol}")
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    def _signal(self, candles: list[dict]) -> tuple[float, str, str]:
        """Return (blended_score, dominant_signal, pattern_name)."""
        tech = _calculate_technical_score(candles)
        pattern = analyze_patterns(candles)
        pat_contrib = 0.0
        if pattern.get("pattern", "None") != "None":
            direction_mult = 1.0 if pattern.get("direction") == "BUY" else -1.0
            pat_contrib = pattern.get("confidence", 0.0) * direction_mult
        blended = 0.6 * tech + 0.4 * pat_contrib
        dominant = "pattern" if abs(pat_contrib) > abs(tech) else "momentum"
        return blended, dominant, pattern.get("pattern", "None")

    # ─── Entries ────────────────────────────────────────────────
    async def _look_for_entries(self, sid: str):
        async with AsyncSessionLocal() as db:
            acc = await db.execute(
                text("SELECT balance FROM simulation_accounts WHERE session_id=:sid"),
                {"sid": sid},
            )
            row = acc.fetchone()
            if not row:
                return
            balance = float(row[0])
            if balance <= 0:
                return

            open_res = await db.execute(
                text(
                    "SELECT symbol FROM simulation_trades "
                    "WHERE session_id=:sid AND status='OPEN'"
                ),
                {"sid": sid},
            )
            open_symbols = {r[0] for r in open_res.fetchall()}

            for symbol in ALL_SYMBOLS:
                if symbol in open_symbols:
                    continue
                price = await self._last_price(symbol)
                if price is None:
                    continue  # no live data for this symbol (e.g. no broker key)

                candles = await self._candles(symbol)
                score, dominant, pattern_name = self._signal(candles)
                if abs(score) < SIM_SCORE_THRESHOLD:
                    continue

                side = "BUY" if score > 0 else "SELL"
                notional = balance * NOTIONAL_FRACTION
                qty = notional / price
                if qty <= 0:
                    continue

                if side == "BUY":
                    stop_loss = price * (1 - STOP_LOSS_PCT)
                    take_profit = price * (1 + TAKE_PROFIT_PCT)
                else:
                    stop_loss = price * (1 + STOP_LOSS_PCT)
                    take_profit = price * (1 - TAKE_PROFIT_PCT)

                reason = self._entry_reason(symbol, side, score, dominant, pattern_name)

                await db.execute(
                    text(
                        """INSERT INTO simulation_trades
                        (session_id, symbol, side, quantity, entry_price, current_price,
                         stop_loss, take_profit, status)
                        VALUES (:sid, :sym, :side, :qty, :ep, :ep, :sl, :tp, 'OPEN')"""
                    ),
                    {
                        "sid": sid,
                        "sym": symbol,
                        "side": side,
                        "qty": qty,
                        "ep": price,
                        "sl": stop_loss,
                        "tp": take_profit,
                    },
                )
                await self._log(db, sid, "TRADE", reason)
                logger.info(f"[SIM {sid[:8]}] OPEN {side} {symbol} qty={qty:.6f} @ {price:.4f}")

            await db.commit()

    def _entry_reason(self, symbol, side, score, dominant, pattern_name) -> str:
        if dominant == "pattern" and pattern_name != "None":
            return (
                f"{side} {symbol} — {pattern_name} pattern detected "
                f"(signal {score:+.2f})"
            )
        trend = "upward" if side == "BUY" else "downward"
        return f"{side} {symbol} — {trend} momentum confirmed (signal {score:+.2f})"

    # ─── Manage / close ─────────────────────────────────────────
    async def _manage_open_trades(self, sid: str):
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                text(
                    """SELECT id, symbol, side, quantity, entry_price, stop_loss, take_profit
                    FROM simulation_trades
                    WHERE session_id=:sid AND status='OPEN'"""
                ),
                {"sid": sid},
            )
            open_trades = res.fetchall()
            if not open_trades:
                return

            for t in open_trades:
                trade_id = str(t[0])
                symbol, side = t[1], t[2]
                qty = float(t[3])
                entry = float(t[4])
                stop_loss = float(t[5]) if t[5] is not None else None
                take_profit = float(t[6]) if t[6] is not None else None

                price = await self._last_price(symbol)
                if price is None:
                    continue

                if side == "BUY":
                    unrealized = (price - entry) * qty
                else:
                    unrealized = (entry - price) * qty

                await db.execute(
                    text(
                        "UPDATE simulation_trades SET current_price=:cp, unrealized_pnl=:u "
                        "WHERE id=:id"
                    ),
                    {"cp": price, "u": unrealized, "id": trade_id},
                )

                close, reason = False, ""
                if side == "BUY":
                    if stop_loss and price <= stop_loss:
                        close, reason = True, "STOP_LOSS"
                    elif take_profit and price >= take_profit:
                        close, reason = True, "TAKE_PROFIT"
                else:
                    if stop_loss and price >= stop_loss:
                        close, reason = True, "STOP_LOSS"
                    elif take_profit and price <= take_profit:
                        close, reason = True, "TAKE_PROFIT"

                if close:
                    await self._close_trade(
                        db, sid, trade_id, symbol, side, qty, entry, price, reason
                    )

            await db.commit()

    async def _close_trade(self, db, sid, trade_id, symbol, side, qty, entry, exit_price, reason):
        if side == "BUY":
            realized = (exit_price - entry) * qty
        else:
            realized = (entry - exit_price) * qty

        await db.execute(
            text(
                """UPDATE simulation_trades
                SET status='CLOSED', closed_at=NOW(), close_price=:xp,
                    current_price=:xp, realized_pnl=:r, unrealized_pnl=0
                WHERE id=:id"""
            ),
            {"xp": exit_price, "r": realized, "id": trade_id},
        )
        await db.execute(
            text(
                """UPDATE simulation_accounts
                SET balance = balance + :r,
                    peak_equity = GREATEST(peak_equity, balance + :r),
                    updated_at = NOW()
                WHERE session_id=:sid"""
            ),
            {"r": realized, "sid": sid},
        )

        outcome = "WIN" if realized > 0 else "LOSS"
        verb = "took profit on" if reason == "TAKE_PROFIT" else "stopped out of"
        await self._log(
            db, sid, "TRADE",
            f"{outcome}: {verb} {side} {symbol} @ {exit_price:.4f} "
            f"(P&L {realized:+.2f})",
        )
        logger.info(f"[SIM {sid[:8]}] CLOSE {symbol} {reason} P&L={realized:+.2f}")

    async def _refresh_equity(self, sid: str):
        """equity = balance + sum(unrealized of open trades); track drawdown."""
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    """UPDATE simulation_accounts a
                    SET equity = a.balance + COALESCE((
                            SELECT SUM(unrealized_pnl) FROM simulation_trades
                            WHERE session_id=:sid AND status='OPEN'
                        ), 0),
                        updated_at = NOW()
                    WHERE a.session_id=:sid"""
                ),
                {"sid": sid},
            )
            await db.execute(
                text(
                    """UPDATE simulation_accounts
                    SET peak_equity = GREATEST(peak_equity, equity),
                        drawdown = CASE WHEN peak_equity > 0
                            THEN (peak_equity - equity) / peak_equity ELSE 0 END
                    WHERE session_id=:sid"""
                ),
                {"sid": sid},
            )
            await db.commit()

    async def _log(self, db, sid: str, level: str, message: str):
        await db.execute(
            text(
                "INSERT INTO simulation_logs (session_id, level, message) "
                "VALUES (:sid, :lvl, :msg)"
            ),
            {"sid": sid, "lvl": level, "msg": message},
        )
