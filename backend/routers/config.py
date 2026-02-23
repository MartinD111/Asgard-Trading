"""
Config router — read/write system configuration (auto mode toggle, thresholds).
"""
import os
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db

router = APIRouter()


class ConfigUpdate(BaseModel):
    key: str
    value: str

class AlgorithmSettings(BaseModel):
    short_term_active: bool
    medium_term_active: bool
    long_term_active: bool
    short_allocation: float
    medium_allocation: float
    long_allocation: float
    short_strategy: str = "loki_pro"
    medium_strategy: str = "thor_pro"
    long_strategy: str = "odin_pro"

@router.get("/")
async def get_all_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT key, value FROM system_config"))
    return {row[0]: row[1] for row in result.fetchall()}


@router.post("/")
async def update_config(update: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("UPDATE system_config SET value=:v, updated_at=NOW() WHERE key=:k"),
        {"k": update.key, "v": update.value},
    )
    return {"status": "updated", "key": update.key, "value": update.value}


@router.post("/toggle-auto")
async def toggle_auto(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT value FROM system_config WHERE key='auto_mode'"))
    row = result.fetchone()
    current = (row[0] if row else "false").lower() == "true"
    new_val = "false" if current else "true"
    await db.execute(
        text("UPDATE system_config SET value=:v WHERE key='auto_mode'"),
        {"v": new_val},
    )
    return {"auto_mode": new_val == "true"}


@router.post("/algorithms")
async def update_algorithm_settings(settings: AlgorithmSettings):
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    
    await redis_client.set("config:algo:short_enabled", "true" if settings.short_term_active else "false")
    await redis_client.set("config:algo:medium_enabled", "true" if settings.medium_term_active else "false")
    await redis_client.set("config:algo:long_enabled", "true" if settings.long_term_active else "false")
    
    await redis_client.set("config:algo:short_allocation", str(settings.short_allocation))
    await redis_client.set("config:algo:medium_allocation", str(settings.medium_allocation))
    await redis_client.set("config:algo:long_allocation", str(settings.long_allocation))
    
    await redis_client.set("config:algo:short_strategy", settings.short_strategy)
    await redis_client.set("config:algo:medium_strategy", getattr(settings, 'medium_strategy', 'thor_pro'))
    await redis_client.set("config:algo:long_strategy", getattr(settings, 'long_strategy', 'odin_pro'))
    
    return {"status": "success", "message": "Algorithm configuration saved to Redis."}

@router.get("/algorithms")
async def get_algorithm_settings():
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    
    s_active = await redis_client.get("config:algo:short_enabled")
    m_active = await redis_client.get("config:algo:medium_enabled")
    l_active = await redis_client.get("config:algo:long_enabled")
    
    s_alloc = await redis_client.get("config:algo:short_allocation")
    m_alloc = await redis_client.get("config:algo:medium_allocation")
    l_alloc = await redis_client.get("config:algo:long_allocation")
    
    s_strat = await redis_client.get("config:algo:short_strategy")
    m_strat = await redis_client.get("config:algo:medium_strategy")
    l_strat = await redis_client.get("config:algo:long_strategy")
    
    return {
        "short_term_active": s_active.decode() == "true" if s_active else True,
        "medium_term_active": m_active.decode() == "true" if m_active else True,
        "long_term_active": l_active.decode() == "true" if l_active else False,
        "short_allocation": float(s_alloc.decode()) if s_alloc else 40.0,
        "medium_allocation": float(m_alloc.decode()) if m_alloc else 40.0,
        "long_allocation": float(l_alloc.decode()) if l_alloc else 20.0,
        "short_strategy": s_strat.decode() if s_strat else "loki_pro",
        "medium_strategy": m_strat.decode() if m_strat else "thor_pro",
        "long_strategy": l_strat.decode() if l_strat else "odin_pro"
    }

@router.get("/agent/stats")
async def get_agent_stats(db: AsyncSession = Depends(get_db)):
    """Returns dynamic weights, total trades, and winrates for the RL agents."""
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    
    from services.weight_optimizer import DEFAULT_WEIGHTS
    
    agents = ["loki_pro", "thor_pro", "odin_pro"]
    stats = {}
    
    for agent in agents:
        key = f"agent:weights:{agent}"
        data = await redis_client.get(key)
        if data:
            weights = json.loads(data)
        else:
            weights = DEFAULT_WEIGHTS
            
        # Get winrate from DB
        query = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN p.realized_pnl > 0 THEN 1 ELSE 0 END) as wins
            FROM prediction_logs pl
            JOIN positions p ON pl.position_id = p.id
            WHERE p.status = 'CLOSED' AND pl.agent_used = :agent
        """)
        result = await db.execute(query, {"agent": agent})
        row = result.fetchone()
        
        total = row[0] if row else 0
        wins = row[1] if row and row[1] else 0
        winrate = round((wins / total) * 100, 2) if total > 0 else 0.0
        
        stats[agent] = {
            "name": agent.capitalize(),
            "weights": weights,
            "total_trades": total,
            "winrate": winrate
        }
        
class AlgorithmSettingsReset(BaseModel):
    amount: float

@router.post("/wallet/reset")
async def reset_wallet(req: AlgorithmSettingsReset, db: AsyncSession = Depends(get_db)):
    """
    Resets the paper trading virtual account to the requested simulation amount.
    Closes any existing open positions.
    """
    amount = req.amount
    
    # Force close all open positions
    await db.execute(
        text("UPDATE positions SET status='CLOSED', closed_at=NOW(), realized_pnl=0 WHERE status='OPEN'")
    )
    
    # Reset account balances
    await db.execute(
        text("""
            UPDATE virtual_accounts 
            SET balance = :amt, equity = :amt, peak_equity = :amt, drawdown = 0.0
            WHERE user_id = 'default'
        """),
        {"amt": amount}
    )
    return {"status": "ok", "message": f"Wallet reset to {amount} (open trades force-closed)."}
