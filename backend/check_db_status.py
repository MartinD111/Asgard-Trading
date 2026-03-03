import asyncio
from sqlalchemy import text
from db.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT balance, equity FROM virtual_accounts WHERE user_id='default'"))
        row = res.fetchone()
        print("Virtual Account:", row)
        
        res = await db.execute(text("SELECT key, value FROM system_config WHERE key='auto_mode'"))
        row = res.fetchone()
        print("Auto mode config:", row)

if __name__ == '__main__':
    asyncio.run(check())
