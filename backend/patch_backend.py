import re
import os

def run():
    backend_dir = r"c:\Users\marti\.gemini\antigravity\scratch\Asgard Trading\backend"
    
    # 1. Update stats.py to use KuCoin
    stats_path = os.path.join(backend_dir, "routers", "stats.py")
    with open(stats_path, 'r', encoding='utf-8') as f:
        stats_content = f.read()
        
    old_binance_block = """    # 2. If crypto, attempt binance public API
    if symbol.upper() in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        try:
            from binance import AsyncClient
            client = await AsyncClient.create()
            klines = await client.get_klines(
                symbol=symbol.upper(),
                interval=interval,
                limit=limit_points
            )
            await client.close_connection()
            result = []
            for k in klines:
                result.append({
                    "time": datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc).isoformat(),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                })
            return result
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch real klines for {symbol}: {e}")
            pass # fallthrough to synthetic"""

    new_kucoin_block = """    # 2. If crypto, attempt KuCoin public API (no keys needed)
    if symbol.upper() in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        try:
            import httpx
            # KuCoin expects BTC-USDT
            k_symbol = symbol.upper().replace('USDT', '-USDT')
            
            # map binance interval to kucoin type
            # KuCoin supports: 1min, 3min, 15min, 30min, 1hour, 2hour, 4hour, 6hour, 8hour, 12hour, 1day, 1week
            interval_map = {
                "1m": "1min", "15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"
            }
            k_interval = interval_map.get(interval, "1hour")
            
            url = f"https://api.kucoin.com/api/v1/market/candles?type={k_interval}&symbol={k_symbol}"
            
            async with httpx.AsyncClient() as client:
                res = await client.get(url, timeout=5.0)
                data = res.json()
                
            if data and data.get("code") == "200000" and data.get("data"):
                k_data = data["data"]
                # KuCoin returns data ordered from newest to oldest. We need oldest to newest.
                k_data = sorted(k_data, key=lambda x: float(x[0]))
                
                # We need only the last 'limit_points'
                k_data = k_data[-limit_points:]
                
                result = []
                for k in k_data:
                    result.append({
                        "time": datetime.fromtimestamp(float(k[0]), tz=timezone.utc).isoformat(),
                        "open": float(k[1]),
                        "high": float(k[3]), # high is idx 3
                        "low": float(k[4]),  # low is idx 4
                        "close": float(k[2]), # close is idx 2
                        "volume": float(k[5])
                    })
                return result
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch real klines for {symbol}: {e}")
            pass # fallthrough to synthetic"""

    stats_content = stats_content.replace(old_binance_block, new_kucoin_block)
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write(stats_content)
        
    print("Updated stats.py")

    # 2. Update market_data.py to use Coinbase Websocket
    md_path = os.path.join(backend_dir, "services", "market_data.py")
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
        
    old_binance_ws = """    # ─── Binance WebSocket ──────────────────────────────────────
    async def _binance_feed(self):
        \"\"\"Stream trades from Binance.\"\"\"
        try:
            from binance import AsyncClient, BinanceSocketManager

            config = await self._get_db_config()
            api_key = config.get("BINANCE_API_KEY") or os.getenv("BINANCE_API_KEY", "")
            secret = config.get("BINANCE_SECRET_KEY") or os.getenv("BINANCE_SECRET_KEY", "")

            # Binance public WebSocket streams do not require API keys for trade/kline data.
            client = await AsyncClient.create(api_key, secret) if api_key else await AsyncClient.create()
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
            logger.error(f"Binance feed error: {e}.")
            # Fallback to simulation only on complete failure
            base_prices = {"BTCUSDT": 65420.0, "ETHUSDT": 3450.0, "SOLUSDT": 145.0}
            drifts = {"BTCUSDT": 0.0001, "ETHUSDT": 0.0002, "SOLUSDT": 0.0004}
            await self._simulate_feed(BINANCE_PAIRS, base_prices=base_prices, drifts=drifts)"""

    new_coinbase_ws = """    # ─── Coinbase WebSocket (Replaced Binance) ──────────────────────────────────────
    async def _binance_feed(self):
        \"\"\"Stream trades from Coinbase as reliable public alternative to Binance.\"\"\"
        try:
            import websockets
            
            # Map our symbols to Coinbase product IDs
            symbol_map = {"BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD", "SOLUSDT": "SOL-USD"}
            reverse_map = {v: k for k, v in symbol_map.items()}
            
            uri = "wss://ws-feed.exchange.coinbase.com"
            async with websockets.connect(uri) as websocket:
                subscribe_msg = {
                    "type": "subscribe",
                    "product_ids": list(symbol_map.values()),
                    "channels": ["ticker"]
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                while self._running:
                    msg_str = await websocket.recv()
                    data = json.loads(msg_str)
                    
                    if data.get("type") == "ticker":
                        cb_symbol = data.get("product_id")
                        if cb_symbol in reverse_map:
                            our_symbol = reverse_map[cb_symbol]
                            price = float(data.get("price", 0.0))
                            qty = float(data.get("last_size", 0.0))
                            if price > 0:
                                await self._on_tick(our_symbol, price, qty)

        except Exception as e:
            logger.error(f"Coinbase feed error: {e}.")
            # Fallback to simulation only on complete failure
            base_prices = {"BTCUSDT": 65420.0, "ETHUSDT": 3450.0, "SOLUSDT": 145.0}
            drifts = {"BTCUSDT": 0.0001, "ETHUSDT": 0.0002, "SOLUSDT": 0.0004}
            await self._simulate_feed(BINANCE_PAIRS, base_prices=base_prices, drifts=drifts)"""

    md_content = md_content.replace(old_binance_ws, new_coinbase_ws)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print("Updated market_data.py")

if __name__ == "__main__":
    run()
