import asyncio
from sqlalchemy import text
from backend.db.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT COUNT(*) FROM prediction_logs"))
        row = res.fetchone()
        print(f"Total Prediction Logs: {row[0] if row else 0}")
        
        res = await db.execute(text("SELECT COUNT(*) FROM positions"))
        row = res.fetchone()
        print(f"Total Positions: {row[0] if row else 0}")
        
        res = await db.execute(text("SELECT COUNT(*) FROM positions WHERE status='CLOSED'"))
        row = res.fetchone()
        print(f"Total CLOSED Positions: {row[0] if row else 0}")
        
        res = await db.execute(text("SELECT agent_used, COUNT(*) FROM prediction_logs GROUP BY agent_used"))
        print(f"Agents: {res.fetchall()}")

asyncio.run(check())
