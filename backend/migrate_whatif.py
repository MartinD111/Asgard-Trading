import asyncio
from sqlalchemy import text
from db.database import AsyncSessionLocal

async def run():
    async with AsyncSessionLocal() as db:
        await db.execute(text("ALTER TABLE prediction_logs ADD COLUMN IF NOT EXISTS is_what_if BOOLEAN DEFAULT FALSE;"))
        await db.commit()
    print("Migration successful")

if __name__ == "__main__":
    asyncio.run(run())
