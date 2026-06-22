import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


_RANGE_MAP: dict[str, tuple[timedelta, str, int]] = {
    "1M": (timedelta(minutes=1), "1m", 60),
    "1H": (timedelta(hours=1), "1m", 60),
    "1D": (timedelta(days=1), "15m", 96),
    "1W": (timedelta(days=7), "1h", 168),
    "3M": (timedelta(days=90), "4h", 540),
    "1Y": (timedelta(days=365), "1d", 365),
}

_TTL_SECONDS: dict[str, int] = {
    "1M": 15,
    "1H": 30,
    "1D": 120,
    "1W": 600,
    "3M": 3600,
    "1Y": 6 * 3600,
}


def _cache_key(symbol: str, range_query: str) -> str:
    return f"market_history:{symbol.upper()}:{range_query.upper()}"


@dataclass(frozen=True)
class MarketHistoryService:
    redis: aioredis.Redis

    async def get_history(self, symbol: str, range_query: str) -> list[dict[str, Any]]:
        """
        Returns OHLCV data.

        Contract (production — no fabricated data):
        - First tries Redis cache.
        - Otherwise fetches the real external provider (when applicable), stores result to Redis.
        - If external provider fails, returns last cached data if present.
        - If no real data is available, returns an EMPTY list. The UI shows a "no data" state.
        """
        sym = symbol.upper()
        rq = range_query.upper()
        cache_key = _cache_key(sym, rq)

        cached = await self.redis.get(cache_key)
        if cached:
            try:
                parsed = json.loads(cached)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except Exception:
                pass

        delta, interval, limit_points = _RANGE_MAP.get(rq, _RANGE_MAP["1D"])

        external: list[dict[str, Any]] | None = None

        # Crypto: use public KuCoin candles (no API keys needed).
        if sym in {"BTCUSDT", "ETHUSDT", "SOLUSDT"}:
            try:
                external = await self._fetch_kucoin(sym, interval, limit_points)
            except Exception as e:
                logger.warning(f"Market history provider failed for {sym} ({rq}): {e}")

        if external and len(external) > 0:
            ttl = _TTL_SECONDS.get(rq, 120)
            await self.redis.set(cache_key, json.dumps(external), ex=ttl)
            return external

        # External failed or not supported: return cache if it exists (race), else empty.
        cached2 = await self.redis.get(cache_key)
        if cached2:
            try:
                parsed = json.loads(cached2)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except Exception:
                pass

        logger.info(f"No real market history available for {sym} ({rq}); returning empty.")
        return []

    async def _fetch_kucoin(self, symbol: str, interval: str, limit_points: int) -> list[dict[str, Any]]:
        import httpx

        interval_map = {
            "1m": "1min",
            "15m": "15min",
            "1h": "1hour",
            "4h": "4hour",
            "1d": "1day",
        }
        k_interval = interval_map.get(interval, "1hour")
        k_symbol = symbol.replace("USDT", "-USDT")

        url = f"https://api.kucoin.com/api/v1/market/candles?type={k_interval}&symbol={k_symbol}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=5.0)
            data = res.json()

        if not data or data.get("code") != "200000" or not data.get("data"):
            raise RuntimeError(f"KuCoin returned no data (code={data.get('code') if data else None})")

        k_data = sorted(data["data"], key=lambda x: float(x[0]))
        k_data = k_data[-limit_points:]

        out: list[dict[str, Any]] = []
        for k in k_data:
            out.append(
                {
                    "time": datetime.fromtimestamp(float(k[0]), tz=timezone.utc).isoformat(),
                    "open": float(k[1]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "close": float(k[2]),
                    "volume": float(k[5]),
                }
            )
        return out

