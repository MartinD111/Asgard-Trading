import asyncio
import os
import redis.asyncio as aioredis

async def flush_balance():
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    await redis_client.delete("real_portfolio_balance")
    print("Deleted 'real_portfolio_balance' from Redis.")
    await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(flush_balance())
