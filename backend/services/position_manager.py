import asyncio
import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from db.database import AsyncSessionLocal
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

class PositionManager:
    """
    Paper Trading Position Manager:
    Continuously monitors OPEN positions in the `positions` table.
    Matches them against the latest prices from Redis.
    Executes SL/TP logic and settles PnL into `virtual_accounts`.
    """

    def __init__(self, redis_client: aioredis.Redis, check_interval: int = 5):
        self.redis = redis_client
        self.interval = check_interval

    async def run_loop(self):
        logger.info(f"PositionManager started (Interval: {self.interval}s)")
        while True:
            try:
                await self._check_positions()
            except Exception as e:
                logger.error(f"Error in PositionManager cycle: {e}")
            await asyncio.sleep(self.interval)

    async def _check_positions(self):
        async with AsyncSessionLocal() as db:
            # 1. Fetch all OPEN positions
            result = await db.execute(
                text("SELECT id, symbol, side, quantity, entry_price, stop_loss, take_profit FROM positions WHERE status='OPEN'")
            )
            open_positions = result.fetchall()

            if not open_positions:
                return

            for position in open_positions:
                pos_id = str(position[0])
                symbol = position[1]
                side = position[2]
                quantity = float(position[3])
                entry_price = float(position[4])
                stop_loss = float(position[5]) if position[5] else None
                take_profit = float(position[6]) if position[6] else None

                # 2. Get latest price from Redis
                raw_price = await self.redis.get(f"last_price:{symbol}")
                if not raw_price:
                    continue
                current_price = float(raw_price)

                # 3. Calculate Unrealized PnL strictly for potential broadcast/logging
                if side == "BUY":
                    unrealized_pnl = (current_price - entry_price) * quantity
                else:
                    unrealized_pnl = (entry_price - current_price) * quantity

                # Update current price tracking in the DB (for UI purposes)
                await db.execute(
                    text("UPDATE positions SET current_price = :cp, unrealized_pnl = :upnl WHERE id = :id"),
                    {"cp": current_price, "upnl": unrealized_pnl, "id": pos_id}
                )

                # 4. Check SL / TP conditions
                close_trade = False
                close_reason = ""

                if side == "BUY":
                    if stop_loss and current_price <= stop_loss:
                        close_trade = True
                        close_reason = "STOP_LOSS"
                    elif take_profit and current_price >= take_profit:
                        close_trade = True
                        close_reason = "TAKE_PROFIT"
                elif side == "SELL":
                    if stop_loss and current_price >= stop_loss:
                        close_trade = True
                        close_reason = "STOP_LOSS"
                    elif take_profit and current_price <= take_profit:
                        close_trade = True
                        close_reason = "TAKE_PROFIT"

                # 5. Execute Trade Closure and Settle Account
                if close_trade:
                    await self._close_position(db, pos_id, symbol, side, quantity, entry_price, current_price, close_reason)

            await db.commit()

    async def _close_position(self, db, pos_id: str, symbol: str, side: str, quantity: float, entry_price: float, exit_price: float, reason: str):
        # Calculate Realized PnL
        if side == "BUY":
            realized_pnl = (exit_price - entry_price) * quantity
        else:
            realized_pnl = (entry_price - exit_price) * quantity

        # 1. Update Position Record
        await db.execute(
            text("""
                UPDATE positions 
                SET status = 'CLOSED', closed_at = NOW(), close_price = :ep, realized_pnl = :rpnl 
                WHERE id = :id
            """),
            {"ep": exit_price, "rpnl": realized_pnl, "id": pos_id}
        )
        
        # 2. Update Prediction Log Outcome
        outcome_str = "WIN" if realized_pnl > 0 else "LOSS"
        await db.execute(
            text("UPDATE prediction_logs SET outcome = :o WHERE position_id = :id"),
            {"o": outcome_str, "id": pos_id}
        )

        # 3. Settle Virtual Account Balance
        await db.execute(
            text("""
                UPDATE virtual_accounts 
                SET 
                    balance = balance + :pnl,
                    equity = equity + :pnl,
                    peak_equity = GREATEST(peak_equity, equity + :pnl)
                WHERE user_id = 'default'
            """),
            {"pnl": realized_pnl}
        )
        
        # Determine strict drawdown logic
        await db.execute(
            text("""
                UPDATE virtual_accounts
                SET drawdown = CASE 
                    WHEN peak_equity > 0 THEN (peak_equity - equity) / peak_equity
                    ELSE 0.0 END
                WHERE user_id = 'default'
            """)
        )

        logger.info(f"[PAPER TRADE SETTLED] {symbol} {side} Closed at {exit_price} ({reason}) | PnL: {realized_pnl:.4f}")
