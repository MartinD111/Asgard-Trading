"""
Historical backfill — fetches M5 candles from broker REST APIs and
persists them into the `candles` table via candle_store.upsert_candles().

Brokers:
  - OANDA v20  → EUR_USD, XAU_USD, XAG_USD
  - Binance    → BTCUSDT  (public klines, no key needed)
  - Coinbase   → BTCUSDT fallback if Binance is unavailable

Called once at startup from main.py lifespan so the engine always has
at least BACKFILL_DAYS of M5 history, even after a cold restart.
Also callable as a standalone script: python -m services.historical_backfill
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from services.candle_store import upsert_candles, latest_candle_ts

logger = logging.getLogger(__name__)

BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "30"))

# OANDA granularity = M5; max 5000 candles per request
OANDA_GRANULARITY = "M5"
OANDA_MAX_COUNT = 4000
OANDA_INSTRUMENTS = ["EUR_USD", "XAU_USD", "XAG_USD"]

# Binance interval = 5m; max 1000 candles per request
BINANCE_INTERVAL = "5m"
BINANCE_MAX_LIMIT = 1000
BINANCE_PAIRS = {"BTCUSDT": "BTCUSDT"}


# ─── OANDA ──────────────────────────────────────────────────────────────────

async def _oanda_candles(
    client: httpx.AsyncClient,
    instrument: str,
    api_key: str,
    account_env: str,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict]:
    base = (
        "https://api-fxtrade.oanda.com"
        if account_env == "live"
        else "https://api-fxpractice.oanda.com"
    )
    url = f"{base}/v3/instruments/{instrument}/candles"
    headers = {"Authorization": f"Bearer {api_key}"}

    candles: list[dict] = []
    cursor = from_dt

    while cursor < to_dt:
        end = min(cursor + timedelta(minutes=5 * OANDA_MAX_COUNT), to_dt)
        params = {
            "from": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "granularity": OANDA_GRANULARITY,
            "price": "M",
        }
        try:
            resp = await client.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            batch = [
                {
                    "time": c["time"],
                    "open": float(c["mid"]["o"]),
                    "high": float(c["mid"]["h"]),
                    "low": float(c["mid"]["l"]),
                    "close": float(c["mid"]["c"]),
                    "volume": float(c.get("volume", 0)),
                    "source": "oanda",
                }
                for c in data.get("candles", [])
                if c.get("complete", True)
            ]
            candles.extend(batch)
            if not batch:
                break
        except Exception as e:
            logger.warning(f"OANDA backfill {instrument} error: {e}")
            break
        cursor = end

    return candles


# ─── Binance ─────────────────────────────────────────────────────────────────

async def _binance_candles(
    client: httpx.AsyncClient,
    symbol: str,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict]:
    url = "https://api.binance.com/api/v3/klines"
    candles: list[dict] = []
    cursor_ms = int(from_dt.timestamp() * 1000)
    end_ms = int(to_dt.timestamp() * 1000)

    while cursor_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": BINANCE_INTERVAL,
            "startTime": cursor_ms,
            "endTime": end_ms,
            "limit": BINANCE_MAX_LIMIT,
        }
        try:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            batch_raw = resp.json()
            if not batch_raw:
                break
            batch = [
                {
                    "time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).isoformat(),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "source": "binance",
                }
                for row in batch_raw
            ]
            candles.extend(batch)
            last_open_ms = batch_raw[-1][0]
            cursor_ms = last_open_ms + 5 * 60 * 1000  # advance one candle
        except Exception as e:
            logger.warning(f"Binance backfill {symbol} error: {e}")
            break

    return candles


# ─── Coinbase fallback ────────────────────────────────────────────────────────

async def _coinbase_candles(
    client: httpx.AsyncClient,
    cb_product: str,
    our_symbol: str,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict]:
    """Coinbase Advanced Trade / Exchange candles (granularity=300s = M5)."""
    url = f"https://api.exchange.coinbase.com/products/{cb_product}/candles"
    candles: list[dict] = []
    cursor = from_dt
    # Coinbase returns max 300 candles per request
    window = timedelta(seconds=300 * 300)

    while cursor < to_dt:
        end = min(cursor + window, to_dt)
        params = {
            "granularity": 300,
            "start": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            # Returns [[time, low, high, open, close, volume], ...] newest first
            batch_raw = resp.json()
            if not isinstance(batch_raw, list) or not batch_raw:
                break
            batch = [
                {
                    "time": datetime.fromtimestamp(row[0], tz=timezone.utc).isoformat(),
                    "open": float(row[3]),
                    "high": float(row[2]),
                    "low": float(row[1]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "source": "coinbase",
                }
                for row in batch_raw
            ]
            candles.extend(batch)
        except Exception as e:
            logger.warning(f"Coinbase backfill {cb_product} error: {e}")
            break
        cursor = end

    return candles


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def run_backfill(days: int = BACKFILL_DAYS) -> None:
    """
    Fetch and persist missing M5 candle history for all tracked symbols.
    Skips symbols that already have recent data (< 2 candle-widths stale).
    """
    now = datetime.now(timezone.utc)
    default_from = now - timedelta(days=days)

    # Read config from DB (same pattern as MarketDataService)
    api_key = ""
    account_id = ""
    account_env = "practice"
    try:
        from db.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            res = await db.execute(text("SELECT key, value FROM system_config"))
            cfg = {r[0]: r[1] for r in res.fetchall()}
        api_key = cfg.get("OANDA_API_KEY") or os.getenv("OANDA_API_KEY", "")
        account_id = cfg.get("OANDA_ACCOUNT_ID") or os.getenv("OANDA_ACCOUNT_ID", "")
        account_env = cfg.get("OANDA_ENVIRONMENT") or os.getenv("OANDA_ENVIRONMENT", "practice")
    except Exception as e:
        logger.warning(f"Could not read config from DB: {e}")

    async with httpx.AsyncClient() as client:
        # ── OANDA instruments ────────────────────────────────────────
        if api_key:
            for instr in OANDA_INSTRUMENTS:
                latest = await latest_candle_ts(instr)
                from_dt = (latest + timedelta(minutes=5)) if latest else default_from
                if from_dt >= now - timedelta(minutes=10):
                    logger.info(f"[backfill] {instr} already up to date, skipping.")
                    continue
                logger.info(f"[backfill] Fetching OANDA {instr} from {from_dt.date()} ...")
                candles = await _oanda_candles(client, instr, api_key, account_env, from_dt, now)
                n = await upsert_candles(candles, instr, source="oanda")
                logger.info(f"[backfill] {instr}: stored {n} candles.")
        else:
            logger.warning("[backfill] OANDA_API_KEY not set — skipping forex/metals backfill.")

        # ── Binance crypto ───────────────────────────────────────────
        for our_sym, bin_sym in BINANCE_PAIRS.items():
            latest = await latest_candle_ts(our_sym)
            from_dt = (latest + timedelta(minutes=5)) if latest else default_from
            if from_dt >= now - timedelta(minutes=10):
                logger.info(f"[backfill] {our_sym} already up to date, skipping.")
                continue
            logger.info(f"[backfill] Fetching Binance {bin_sym} from {from_dt.date()} ...")
            candles = await _binance_candles(client, bin_sym, from_dt, now)
            if not candles:
                # Fallback to Coinbase
                logger.info(f"[backfill] Binance empty, falling back to Coinbase for {our_sym}.")
                candles = await _coinbase_candles(client, "BTC-USD", our_sym, from_dt, now)
            n = await upsert_candles(candles, our_sym, source=candles[0]["source"] if candles else "unknown")
            logger.info(f"[backfill] {our_sym}: stored {n} candles.")


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=logging.INFO)
    asyncio.run(run_backfill())
