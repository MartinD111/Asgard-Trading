"""
Market Data Service — unified WebSocket feeds for OANDA, Alpaca, Binance.
Normalises ticks into OHLCV candles and publishes to Redis pub/sub.
"""
import os
import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Instruments to track
OANDA_INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD", "XAG_USD"]
ALPACA_SYMBOLS = ["AAPL", "MSFT", "SPY", "QQQ", "TSLA"]
BINANCE_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

CANDLE_INTERVAL_SECONDS = 300  # 5-minute candles


class OHLCV:
    def __init__(self, symbol: str, ts: int):
        self.symbol = symbol
        self.ts = ts
        self.open = self.high = self.low = self.close = 0.0
        self.volume = 0.0
        self.tick_count = 0

    def update(self, price: float, volume: float = 0.0):
        if self.tick_count == 0:
            self.open = self.high = self.low = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        self.tick_count += 1

    def to_dict(self) -> dict:
        return {
            "time": datetime.fromtimestamp(self.ts, tz=timezone.utc).isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class CandleBuffer:
    """Maintains a rolling 50-candle buffer per symbol."""

    def __init__(self):
        self._candles: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=50))
        self._current: dict[str, OHLCV] = {}

    def _bucket(self) -> int:
        now = int(datetime.now(timezone.utc).timestamp())
        return (now // CANDLE_INTERVAL_SECONDS) * CANDLE_INTERVAL_SECONDS

    def update(self, symbol: str, price: float, volume: float = 0.0) -> dict | None:
        """Returns completed candle if a new bucket started."""
        bucket = self._bucket()
        current = self._current.get(symbol)
        completed = None

        if current is None or current.ts != bucket:
            if current is not None:
                completed = current.to_dict()
                self._candles[symbol].append(completed)
            self._current[symbol] = OHLCV(symbol, bucket)

        self._current[symbol].update(price, volume)
        return completed

    def get_candles(self, symbol: str) -> list[dict]:
        candles = list(self._candles[symbol])
        if symbol in self._current:
            candles.append(self._current[symbol].to_dict())
        return candles[-50:]

    def get_last_price(self, symbol: str) -> float:
        if symbol in self._current:
            return self._current[symbol].close
        return 0.0


class MarketDataService:
    def __init__(self, redis: aioredis.Redis, ws_manager: Any):
        self.redis = redis
        self.ws_manager = ws_manager
        self.buffer = CandleBuffer()
        self._running = False

    async def start(self):
        self._running = True
        logger.info("MarketDataService starting...")
        tasks = [
            self._oanda_feed(),
            self._alpaca_feed(),
            self._binance_feed(),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    # ─── DB Config Fetcher ──────────────────────────────────────
    async def _get_db_config(self) -> dict:
        from db.database import AsyncSessionLocal
        from sqlalchemy import text
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(text("SELECT key, value FROM system_config"))
                return {row[0]: row[1] for row in result.fetchall()}
        except Exception as e:
            logger.error(f"Failed to fetch config from DB: {e}")
            return {}

    # ─── OANDA WebSocket ────────────────────────────────────────
    async def _oanda_feed(self):
        """Stream pricing from OANDA v20 streaming API."""
        try:
            import oandapyV20
            import oandapyV20.endpoints.pricing as pricing

            config = await self._get_db_config()
            api_key = config.get("OANDA_API_KEY") or os.getenv("OANDA_API_KEY", "")
            account_id = config.get("OANDA_ACCOUNT_ID") or os.getenv("OANDA_ACCOUNT_ID", "")
            env = config.get("OANDA_ENVIRONMENT") or os.getenv("OANDA_ENVIRONMENT", "practice")

            if not api_key:
                logger.warning("OANDA_API_KEY not set — using simulated data")
                await self._simulate_feed(OANDA_INSTRUMENTS)
                return

            client = oandapyV20.API(access_token=api_key, environment=env)
            params = {"instruments": ",".join(OANDA_INSTRUMENTS)}
            r = pricing.PricingStream(accountID=account_id, params=params)

            for tick in client.request(r):
                if not self._running:
                    break
                if tick.get("type") == "PRICE":
                    symbol = tick["instrument"]
                    bid = float(tick["bids"][0]["price"])
                    ask = float(tick["asks"][0]["price"])
                    mid = (bid + ask) / 2
                    await self._on_tick(symbol, mid)
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"OANDA feed error: {e}. Falling back to simulation.")
            await self._simulate_feed(OANDA_INSTRUMENTS)

    # ─── Alpaca WebSocket ───────────────────────────────────────
    async def _alpaca_feed(self):
        """Stream trades from Alpaca."""
        try:
            from alpaca.data.live import StockDataStream

            config = await self._get_db_config()
            api_key = config.get("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY", "")
            secret = config.get("ALPACA_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY", "")

            if not api_key:
                logger.warning("ALPACA_API_KEY not set — using simulated data")
                await self._simulate_feed(ALPACA_SYMBOLS, base_price=150.0, drift=0.0001)
                return

            stream = StockDataStream(api_key, secret)

            async def on_trade(data):
                await self._on_tick(data.symbol, float(data.price), float(getattr(data, "size", 0)))

            stream.subscribe_trades(on_trade, *ALPACA_SYMBOLS)
            await stream.run()

        except Exception as e:
            logger.error(f"Alpaca feed error: {e}. Falling back to simulation.")
            await self._simulate_feed(ALPACA_SYMBOLS, base_price=150.0, drift=0.0001)

    # ─── Binance WebSocket ──────────────────────────────────────
    async def _binance_feed(self):
        """Stream trades from Binance."""
        try:
            from binance import AsyncClient, BinanceSocketManager

            config = await self._get_db_config()
            api_key = config.get("BINANCE_API_KEY") or os.getenv("BINANCE_API_KEY", "")
            secret = config.get("BINANCE_SECRET_KEY") or os.getenv("BINANCE_SECRET_KEY", "")

            if not api_key:
                logger.warning("BINANCE_API_KEY not set — using simulated data")
                await self._simulate_feed(BINANCE_PAIRS, base_price=50000.0, drift=0.0002)
                return

            client = await AsyncClient.create(api_key, secret)
            bm = BinanceSocketManager(client)

            async with bm.multiplex_socket(
                [f"{p.lower()}@trade" for p in BINANCE_PAIRS]
            ) as stream:
                while self._running:
                    msg = await stream.recv()
                    data = msg.get("data", {})
                    if data.get("e") == "trade":
                        symbol = data["s"]
                        price = float(data["p"])
                        qty = float(data["q"])
                        await self._on_tick(symbol, price, qty)

        except Exception as e:
            logger.error(f"Binance feed error: {e}. Falling back to simulation.")
            await self._simulate_feed(BINANCE_PAIRS, base_price=50000.0, drift=0.0002)

    # ─── Simulation fallback ────────────────────────────────────
    async def _simulate_feed(
        self,
        symbols: list[str],
        base_price: float = 1.1000,
        drift: float = 0.00005,
        interval: float = 1.0,
    ):
        """Generates synthetic random-walk prices when APIs are unavailable."""
        import random
        prices = {s: base_price * (1 + random.uniform(-0.05, 0.05)) for s in symbols}
        while self._running:
            for sym in symbols:
                change = prices[sym] * random.gauss(drift, 0.0005)
                prices[sym] = max(prices[sym] + change, 0.0001)
                await self._on_tick(sym, prices[sym], abs(random.gauss(1000, 200)))
            await asyncio.sleep(interval)

    # ─── Tick handler ───────────────────────────────────────────
    async def _on_tick(self, symbol: str, price: float, volume: float = 0.0):
        self.buffer.update(symbol, price, volume)
        tick_msg = json.dumps({"type": "tick", "symbol": symbol, "price": price})
        await self.redis.publish("market:ticks", tick_msg)
        await self.ws_manager.broadcast(tick_msg)
