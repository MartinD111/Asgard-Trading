"""
ExecutionRouter — selects the right ExecutionBroker for a (user, symbol) pair.

Routing rules:
  EUR_USD, XAU_USD, XAG_USD → OandaBroker
  BTCUSDT, ETHUSDT           → CoinbaseBroker
  anything else              → PaperBroker (fallback)

If the user has no live mode enabled or no broker connection configured for
the required broker, falls back to PaperBroker so the engine never hard-fails.
"""
from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from brokers.base import ExecutionBroker
from brokers.paper import PaperBroker

logger = logging.getLogger(__name__)

# Maps engine symbol → canonical broker name
SYMBOL_BROKER: dict[str, str] = {
    "EUR_USD": "oanda",
    "XAU_USD": "oanda",
    "XAG_USD": "oanda",
    "BTCUSDT": "coinbase",
    "ETHUSDT":  "coinbase",
}


async def get_broker_for_user(
    user_id: str,
    symbol: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> ExecutionBroker:
    """
    Returns the ExecutionBroker appropriate for this user + symbol.
    Always returns something — PaperBroker if no live connection is available.
    """
    required_broker = SYMBOL_BROKER.get(symbol)
    if not required_broker:
        logger.debug(f"No broker mapping for {symbol} — using PaperBroker")
        return PaperBroker(redis=redis)

    # Per-user live-mode gate.  Users must explicitly opt in.
    live_raw = await redis.get(f"user:{user_id}:live_mode")
    if (live_raw or b"false").decode() != "true":
        return PaperBroker(redis=redis)

    # Try to load decrypted keys; prefer live environment, fall back to practice.
    try:
        from services.broker_service import get_decrypted_keys

        for env in ("live", "practice"):
            keys = await get_decrypted_keys(db, user_id, required_broker, env)
            if not keys:
                continue

            if required_broker == "oanda":
                from brokers.oanda import OandaBroker
                return OandaBroker(
                    api_key=keys["api_key"],
                    account_id=keys.get("account_id") or "",
                    environment=env,
                )

            if required_broker == "coinbase":
                from brokers.coinbase import CoinbaseBroker
                return CoinbaseBroker(
                    api_key=keys["api_key"],
                    api_secret=keys.get("api_secret") or "",
                )

    except Exception as exc:
        logger.error(f"ExecutionRouter failed to load broker for user {user_id}: {exc}")

    logger.info(f"No live broker for user {user_id} / {required_broker} — falling back to PaperBroker")
    return PaperBroker(redis=redis)
