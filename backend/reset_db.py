import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine

# Must match backend/db/database.py Connection String
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://trading:trading_secret@localhost:5432/trading_ai")

async def reset_database():
    print(f"Connecting to database at {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        print("Truncating positions and prediction_logs...")
        # TRUNCATE CASCADE to drop all linked records and restart identity
        await conn.execute("TRUNCATE TABLE prediction_logs CASCADE;")
        await conn.execute("TRUNCATE TABLE positions CASCADE;")
        
        print("Resetting virtual_accounts to 0...")
        # User requested EVERYTHING to 0
        await conn.execute(
            "UPDATE virtual_accounts SET balance = 0.00, equity = 0.00, peak_equity = 0.00, drawdown = 0.0"
        )
        
    print("Database reset complete.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_database())
