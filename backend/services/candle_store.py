"""
Candle store — async helpers to read/write OHLCV candles in Postgres.

Used by: live MarketDataService (persist on close), historical backfill,
DecisionEngine (warm-start), and the backtester.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# How many candles to warm-start the engine with on startup
WARMUP_LIMIT = 500


def _row_to_dict(row: Any) -> dict:
    return {
        "time": row[0].isoformat() if isinstance(row[0], datetime) else str(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
    }


async def upsert_candles(
    candles: list[dict],
    symbol: str,
    timeframe: str = "M5",
    source: str = "live",
) -> int:
    """Insert candles, ignoring duplicates (ON CONFLICT DO NOTHING). Returns count."""
    if not candles:
        return 0
    async with AsyncSessionLocal() as db:
        count = 0
        for c in candles:
            ts = c.get("time") or c.get("ts")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            await db.execute(
                text(
                    """
                    INSERT INTO candles (symbol, timeframe, ts, open, high, low, close, volume, source)
                    VALUES (:sym, :tf, :ts, :o, :h, :l, :c, :v, :src)
                    ON CONFLICT (symbol, timeframe, ts) DO NOTHING
                    """
                ),
                {
                    "sym": symbol,
                    "tf": timeframe,
                    "ts": ts,
                    "o": float(c["open"]),
                    "h": float(c["high"]),
                    "l": float(c["low"]),
                    "c": float(c["close"]),
                    "v": float(c.get("volume", 0)),
                    "src": source,
                },
            )
            count += 1
        await db.commit()
    return count


async def get_candles(
    symbol: str,
    timeframe: str = "M5",
    limit: int = WARMUP_LIMIT,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """
    Fetch candles from DB in ascending time order (oldest first).
    `since` and `until` are inclusive bounds.
    """
    async with AsyncSessionLocal() as db:
        conditions = ["symbol=:sym", "timeframe=:tf"]
        params: dict = {"sym": symbol, "tf": timeframe, "lim": limit}
        if since:
            conditions.append("ts >= :since")
            params["since"] = since
        if until:
            conditions.append("ts <= :until")
            params["until"] = until
        where = " AND ".join(conditions)

        if since or until:
            sql = f"""
                SELECT ts, open, high, low, close, volume FROM candles
                WHERE {where}
                ORDER BY ts ASC LIMIT :lim
            """
        else:
            # Fetch the N most-recent candles (DESC), then reverse to get ASC order
            sql = f"""
                SELECT ts, open, high, low, close, volume FROM (
                    SELECT ts, open, high, low, close, volume FROM candles
                    WHERE {where}
                    ORDER BY ts DESC LIMIT :lim
                ) sub ORDER BY ts ASC
            """

        res = await db.execute(text(sql), params)
        return [_row_to_dict(r) for r in res.fetchall()]


async def latest_candle_ts(symbol: str, timeframe: str = "M5") -> datetime | None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text("SELECT MAX(ts) FROM candles WHERE symbol=:sym AND timeframe=:tf"),
            {"sym": symbol, "tf": timeframe},
        )
        row = res.fetchone()
        return row[0] if row and row[0] else None


async def earliest_candle_ts(symbol: str, timeframe: str = "M5") -> datetime | None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text("SELECT MIN(ts) FROM candles WHERE symbol=:sym AND timeframe=:tf"),
            {"sym": symbol, "tf": timeframe},
        )
        row = res.fetchone()
        return row[0] if row and row[0] else None


async def candle_count(symbol: str, timeframe: str = "M5") -> int:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text("SELECT COUNT(*) FROM candles WHERE symbol=:sym AND timeframe=:tf"),
            {"sym": symbol, "tf": timeframe},
        )
        row = res.fetchone()
        return int(row[0]) if row else 0
