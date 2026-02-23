import os
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db

router = APIRouter()

@router.get("/history")
async def get_history(
    timeframe: Optional[str] = Query(None, description="short, medium, or long"),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db)
):
    query = """
        SELECT pl.timestamp, pl.symbol, pl.direction, pl.agent_used, pl.reasoning,
               p.entry_price, p.close_price, p.realized_pnl, p.status
        FROM prediction_logs pl
        JOIN positions p ON pl.position_id = p.id
        WHERE pl.trade_executed = TRUE
    """
    params = {"limit": limit}
    
    if timeframe == "short":
        query += " AND pl.agent_used IN ('math', 'patterns', 'loki', 'loki_pro')"
    elif timeframe == "medium":
        query += " AND pl.agent_used IN ('math', 'patterns', 'thor', 'thor_pro')"
    elif timeframe == "long":
        query += " AND pl.agent_used IN ('math', 'patterns', 'odin', 'odin_pro')"
        
    query += " ORDER BY pl.timestamp DESC LIMIT :limit"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    history = []
    for row in rows:
        history.append({
            "timestamp": row[0].isoformat(),
            "symbol": row[1],
            "direction": row[2],
            "agent_used": row[3],
            "reasoning": row[4],
            "entry_price": float(row[5]) if row[5] else None,
            "close_price": float(row[6]) if row[6] else None,
            "realized_pnl": float(row[7]) if row[7] else 0.0,
            "status": row[8]
        })
    return history


@router.get("/what_if")
async def get_what_if_stats(
    timeframe: str = Query("short", description="short, medium, long"),
    days: int = Query(30),
    db: AsyncSession = Depends(get_db)
):
    agents_map = {
        "short": ["math", "patterns", "loki", "loki_pro"],
        "medium": ["math", "patterns", "thor", "thor_pro"],
        "long": ["math", "patterns", "odin", "odin_pro"]
    }
    tf_agents = agents_map.get(timeframe, ["math"])
    
    # Mock visual cumulative PNL data for the "What-If" charts
    # In production, a background worker would simulate virtual trades and store realized PNls per model.
    output = {}
    base_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    for agent in tf_agents:
        agent_data = []
        cumulative = 0.0
        
        # Determine drift trend (Pro agents slightly better)
        if "pro" in agent:
            base_drift = random.uniform(-0.1, 0.4)
        elif agent in ["loki", "thor", "odin"]:
            base_drift = random.uniform(-0.1, 0.3)
        else:
            base_drift = random.uniform(-0.3, 0.2)
            
        for i in range(days + 1):
            dt = base_date + timedelta(days=i)
            daily_pnl = base_drift + random.uniform(-1.5, 1.5)
            cumulative += daily_pnl
            agent_data.append({
                "date": dt.strftime("%Y-%m-%d"),
                "pnl": round(cumulative, 2)
            })
        output[agent] = agent_data
        
    return output
