"""
Broker reconciliation loop.

Polls the `orders` table every POLL_INTERVAL seconds for PENDING rows and
syncs actual broker fill state back to the DB:

  FILLED   → update orders + positions with real fill price / qty
  CANCELLED/REJECTED → close the position stub with 0 PnL, write audit entry
  still PENDING + older than TIMEOUT → treat as cancelled (broker unreachable)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30          # seconds between reconciliation passes
PENDING_TIMEOUT = timedelta(minutes=5)  # max time before a PENDING order is cancelled


async def run_reconciliation_loop(redis) -> None:
    while True:
        try:
            await _reconcile(redis)
        except Exception:
            logger.error("reconciliation_loop_error", exc_info=True)
        await asyncio.sleep(POLL_INTERVAL)


async def _reconcile(redis) -> None:
    from sqlalchemy import text
    from db.database import AsyncSessionLocal
    from brokers.router import get_broker_for_user

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text("""
                SELECT id, user_id, position_id, broker, broker_order_id,
                       symbol, quantity, created_at
                FROM orders
                WHERE status = 'PENDING'
                  AND created_at < :cutoff
                ORDER BY created_at ASC
                LIMIT 50
            """),
            {"cutoff": cutoff},
        )
        rows = res.fetchall()

    if not rows:
        return

    logger.info(f"[reconcile] Checking {len(rows)} PENDING order(s)")

    for row in rows:
        order_id        = str(row[0])
        user_id         = str(row[1]) if row[1] else None
        position_id     = str(row[2]) if row[2] else None
        broker_name     = row[3]
        broker_order_id = row[4]
        symbol          = row[5]
        quantity        = float(row[6])
        created_at      = row[7]

        # Ensure timezone-aware for arithmetic
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        # Paper orders always fill instantly — shouldn't be pending, handle defensively
        if broker_name == "paper" or not broker_order_id:
            await _mark_order(order_id, "FILLED", 0.0, quantity, None)
            continue

        # Hard timeout: broker took too long, treat as cancelled
        if datetime.now(timezone.utc) - created_at > PENDING_TIMEOUT:
            logger.warning(f"[reconcile] Order {order_id} timed out after {PENDING_TIMEOUT}")
            await _mark_order(order_id, "CANCELLED", 0.0, 0.0, "Broker order timeout")
            if position_id:
                await _close_position_stub(position_id, order_id, "Broker order timeout")
            continue

        # Poll broker for current status
        try:
            async with AsyncSessionLocal() as db:
                broker = await get_broker_for_user(user_id or "", symbol, db, redis)
            result = await broker.get_order_status(broker_order_id, symbol)
        except Exception as exc:
            logger.warning(f"[reconcile] Could not check order {order_id}: {exc}")
            continue

        if result.status == "FILLED":
            await _mark_order(order_id, "FILLED", result.filled_price, result.filled_qty, None)
            if position_id and result.filled_price > 0:
                await _update_position_fill(position_id, result.filled_price, result.filled_qty)
            logger.info(
                f"[reconcile] Order {order_id} FILLED @ {result.filled_price} qty={result.filled_qty}"
            )

        elif result.status in ("CANCELLED", "REJECTED"):
            await _mark_order(order_id, result.status, 0.0, 0.0, result.error)
            if position_id:
                await _close_position_stub(position_id, order_id, f"Broker {result.status.lower()}")
            logger.info(f"[reconcile] Order {order_id} {result.status}: {result.error}")
        # else still PENDING — leave for next pass


async def _mark_order(
    order_id: str,
    status: str,
    filled_price: float,
    filled_qty: float,
    error: str | None,
) -> None:
    from sqlalchemy import text
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                UPDATE orders
                SET status = :st,
                    filled_price = :fp,
                    filled_qty   = :fq,
                    error_message = :err,
                    updated_at   = NOW()
                WHERE id = :id
            """),
            {"st": status, "fp": filled_price, "fq": filled_qty, "err": error, "id": order_id},
        )
        await db.commit()


async def _update_position_fill(position_id: str, fill_price: float, fill_qty: float) -> None:
    """Overwrite the optimistic fill estimate with the actual broker fill."""
    from sqlalchemy import text
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                UPDATE positions
                SET entry_price   = :fp,
                    current_price = :fp,
                    quantity      = :fq
                WHERE id = :id AND status = 'OPEN'
            """),
            {"fp": fill_price, "fq": fill_qty, "id": position_id},
        )
        await db.commit()


async def _close_position_stub(position_id: str, order_id: str, reason: str) -> None:
    """Mark an unfilled position as CLOSED with 0 PnL and log to audit_log."""
    from sqlalchemy import text
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                UPDATE positions
                SET status = 'CLOSED', realized_pnl = 0, closed_at = NOW()
                WHERE id = :id AND status = 'OPEN'
            """),
            {"id": position_id},
        )
        await db.execute(
            text("""
                INSERT INTO audit_log (event_type, order_id, symbol, payload)
                SELECT 'ORDER_REJECTED',
                       :oid::uuid,
                       symbol,
                       :payload::jsonb
                FROM orders WHERE id = :oid
            """),
            {"oid": order_id, "payload": json.dumps({"reason": reason})},
        )
        await db.commit()
