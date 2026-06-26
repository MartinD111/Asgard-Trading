import asyncio
import json
import logging
import os
from sqlalchemy import text
from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def fetch_real_balances():
    """
    Fetches real balances from configured APIs (Binance, Alpaca, Oanda)
    and saves the total to Redis.
    """
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    while True:
        try:
            binance_bal = 0.0
            alpaca_bal = 0.0
            oanda_bal = 0.0
            has_any_keys = False

            async with AsyncSessionLocal() as db:
                res = await db.execute(text("SELECT key, value FROM system_config"))
                db_cfg = {row[0]: row[1] for row in res.fetchall()}

            def get_cfg(key):
                return db_cfg.get(key) or os.getenv(key)

            # Binance
            binance_key = get_cfg('BINANCE_API_KEY')
            binance_sec = get_cfg('BINANCE_SECRET_KEY')
            if binance_key and binance_sec:
                try:
                    from binance.client import AsyncClient
                    client = await AsyncClient.create(binance_key, binance_sec)
                    account = await client.get_account()
                    # Try to sum USDT and USDC in wallet
                    usdt = next((float(b['free']) + float(b['locked']) for b in account['balances'] if b['asset'] == 'USDT'), 0.0)
                    usdc = next((float(b['free']) + float(b['locked']) for b in account['balances'] if b['asset'] == 'USDC'), 0.0)
                    eur = next((float(b['free']) + float(b['locked']) for b in account['balances'] if b['asset'] == 'EUR'), 0.0) * 1.05 # rough conversion
                    binance_bal = usdt + usdc + eur
                    await client.close_connection()
                    has_any_keys = True
                except Exception as e:
                    logger.warning(f"Failed to fetch Binance balance: {e}")

            # Alpaca
            alpaca_key = get_cfg('ALPACA_API_KEY')
            alpaca_sec = get_cfg('ALPACA_SECRET_KEY')
            if alpaca_key and alpaca_sec:
                try:
                    from alpaca.trading.client import TradingClient
                    client = TradingClient(alpaca_key, alpaca_sec, paper=False)
                    acc = client.get_account()
                    alpaca_bal = float(acc.equity)
                    has_any_keys = True
                except Exception as e:
                    logger.warning(f"Failed to fetch Alpaca balance: {e}")

            # OANDA
            oanda_key = get_cfg('OANDA_API_KEY')
            oanda_acc = get_cfg('OANDA_ACCOUNT_ID')
            if oanda_key and oanda_acc:
                try:
                    import oandapyV20
                    import oandapyV20.endpoints.accounts as accounts
                    client = oandapyV20.API(access_token=oanda_key)
                    r = accounts.AccountSummary(oanda_acc)
                    client.request(r)
                    oanda_bal = float(r.response.get('account', {}).get('NAV', 0.0))
                    has_any_keys = True
                except Exception as e:
                    logger.warning(f"Failed to fetch OANDA balance: {e}")


            if has_any_keys:
                total_real = binance_bal + alpaca_bal + oanda_bal
                await redis_client.set("real_portfolio_balance", str(total_real))
            else:
                await redis_client.delete("real_portfolio_balance")

        except Exception as e:
            logger.error(f"Error in fetch_real_balances loop: {e}")
        
        await asyncio.sleep(60)  # Check every 60 seconds
