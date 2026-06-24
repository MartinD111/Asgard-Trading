"""
PaperBroker — simulates instant market fill at the current Redis spot price.

No real broker account required. Used as the default when a user has no live
connection configured, or when the engine is in PAPER mode.
"""
from __future__ import annotations

import uuid
from typing import Optional

import redis.asyncio as aioredis

from brokers.base import ExecutionBroker, OrderResult


class PaperBroker(ExecutionBroker):
    """
    Fills orders immediately at the Redis last_price for the symbol.
    Position sizing and virtual-account settlement are the caller's responsibility;
    the broker only confirms the fill price.
    """

    def __init__(self, redis: aioredis.Redis, balance: float = 100_000.0):
        self._redis = redis
        self._balance = balance

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> OrderResult:
        raw = await self._redis.get(f"last_price:{symbol}")
        fill_price = float(raw) if raw else 0.0
        return OrderResult(
            broker_order_id=f"paper-{uuid.uuid4().hex[:12]}",
            status="FILLED",
            filled_price=fill_price,
            filled_qty=quantity,
        )

    async def close_position(
        self,
        broker_order_id: str,
        symbol: str,
        quantity: float,
    ) -> OrderResult:
        raw = await self._redis.get(f"last_price:{symbol}")
        fill_price = float(raw) if raw else 0.0
        return OrderResult(
            broker_order_id=f"paper-close-{uuid.uuid4().hex[:12]}",
            status="FILLED",
            filled_price=fill_price,
            filled_qty=quantity,
        )

    async def get_balance(self) -> float:
        return self._balance

    async def get_open_positions(self) -> list[dict]:
        return []

    async def get_order_status(self, broker_order_id: str, symbol: str) -> OrderResult:
        raw = await self._redis.get(f"last_price:{symbol}")
        fill_price = float(raw) if raw else 0.0
        return OrderResult(
            broker_order_id=broker_order_id,
            status="FILLED",
            filled_price=fill_price,
            filled_qty=0.0,
        )
