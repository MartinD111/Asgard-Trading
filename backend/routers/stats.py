import os
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db

router = APIRouter()

@router.get("/market/history")
async def get_market_history(
    request: Request,
    symbol: str = Query(..., description="E.g. BTCUSDT, EUR_USD, AAPL"),
    range_query: str = Query("1D", alias="range", description="1M, 1H, 1D, 1W, 3M, 1Y")
):
    """
    Returns historical OHLCV data to paint accurate past charts.
    Uses cached provider abstraction (Redis + external + synthetic fallback).
    Contract: never returns an empty array.
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")

    from services.market_history_service import MarketHistoryService

    svc = MarketHistoryService(redis=redis)
    data = await svc.get_history(symbol=symbol, range_query=range_query)
    return data

@router.get("/history")
async def get_history(
    timeframe: Optional[str] = Query(None, description="short, medium, or long"),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db)
):
    query = """
        SELECT pl.timestamp, pl.symbol, pl.direction, pl.agent_used, pl.reasoning,
               p.entry_price, p.close_price, p.realized_pnl, p.status, pl.is_what_if
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
            "status": row[8],
            "is_what_if": bool(row[9]) if row[9] is not None else False
        })
    return history


@router.get("/what_if")
async def get_what_if_stats(
    request: Request,
    timeframe: str = Query("short", description="short, medium, long"),
    days: int = Query(30),
    symbol: str = Query("BTCUSDT", description="Trading asset symbol, e.g., BTCUSDT, ETHUSDT"),
    db: AsyncSession = Depends(get_db)
):
    agents_map = {
        "short": ["math", "patterns", "loki", "loki_pro"],
        "medium": ["math", "patterns", "thor", "thor_pro"],
        "long": ["math", "patterns", "odin", "odin_pro"]
    }
    tf_agents = agents_map.get(timeframe, ["math"])
    
    output = {
        "price_history": [],
        "cumulative_pnl": {},
        "trades": {agent: [] for agent in tf_agents}
    }
    
    # 1. Fetch historical prices (prefer external; fallback to cached/synthetic)
    try:
        from binance import AsyncClient
        client = await AsyncClient.create()
        # Convert days to hours for limit
        klines = await client.get_klines(
            symbol=symbol.upper(),
            interval=AsyncClient.KLINE_INTERVAL_1HOUR,
            limit=24 * days
        )
        for k in klines:
            dt = datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc)
            output["price_history"].append({
                "time": dt.isoformat(),
                "price": float(k[4]) # Close price
            })
    except Exception as e:
        import logging
        logging.error(f"Failed to fetch real klines for what_if: {e}")
        # Fallback: use cached history abstraction.
        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            from services.market_history_service import MarketHistoryService
            svc = MarketHistoryService(redis=redis)
            if days <= 1:
                rq = "1D"
            elif days <= 7:
                rq = "1W"
            elif days <= 90:
                rq = "3M"
            else:
                rq = "1Y"
            hist = await svc.get_history(symbol=symbol.upper(), range_query=rq)
            output["price_history"] = [{"time": d["time"], "price": float(d["close"])} for d in hist]
        else:
            output["price_history"] = []
        
    base_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # 2. Fetch real trades from DB instead of mocking
    query = text("""
        SELECT pl.timestamp, pl.agent_used, p.entry_price, p.close_price, p.closed_at, pl.direction, p.realized_pnl
        FROM prediction_logs pl
        JOIN positions p ON pl.position_id = p.id
        WHERE pl.symbol = :sym
          AND p.status = 'CLOSED'
          AND pl.timestamp >= :date
    """)
    result = await db.execute(query, {"sym": symbol.upper(), "date": base_date})
    rows = result.fetchall()
    
    for row in rows:
        agent = row[1]
        if agent in tf_agents:
            entry_price = float(row[2])
            exit_price = float(row[3])
            direction = row[5]
            pnl_eur = float(row[6])
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            if direction == "SHORT":
                pnl_pct = -pnl_pct
                
            output["trades"][agent].append({
                "entry_time": row[0].isoformat(),
                "exit_time": row[4].isoformat() if row[4] else row[0].isoformat(),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "direction": direction,
                "pnl_pct": round(pnl_pct, 4),
                "pnl_eur": round(pnl_eur, 2)
            })
            
    # 3. Cumulative PNL map based on REAL trades (flattening to days)
    for agent in tf_agents:
        agent_data = []
        cumulative = 0.0
        
        # We will iterate through days and sum up
        daily_pnls = {}
        for trade in output["trades"][agent]:
            t_date = datetime.fromisoformat(trade["exit_time"]).date()
            daily_pnls[t_date] = daily_pnls.get(t_date, 0.0) + trade["pnl_eur"]
            
        for i in range(days + 1):
            dt = (base_date + timedelta(days=i)).date()
            cumulative += daily_pnls.get(dt, 0.0)
            agent_data.append({
                "date": dt.strftime("%Y-%m-%d"),
                "pnl": round(cumulative, 2)
            })
        output["cumulative_pnl"][agent] = agent_data

    return output

@router.get("/daily_contribution")
async def get_daily_contribution(db: AsyncSession = Depends(get_db)):
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))

    # Get current equity
    acc = await db.execute(text("SELECT equity FROM virtual_accounts WHERE user_id='default'"))
    row = acc.fetchone()
    equity = float(row[0]) if row else 100000.0

    today = datetime.now(timezone.utc).date()
    
    query = text("""
        SELECT pl.agent_used, SUM(p.realized_pnl)
        FROM prediction_logs pl
        JOIN positions p ON pl.position_id = p.id
        WHERE p.status = 'CLOSED' 
          AND pl.agent_used LIKE '%_pro'
          AND DATE(p.closed_at) = :today
        GROUP BY pl.agent_used
    """)
    result = await db.execute(query, {"today": today})
    rows = result.fetchall()
    
    agents = {"loki_pro": 0.0, "thor_pro": 0.0, "odin_pro": 0.0}
    total_pnl = 0.0
    
    for r in rows:
        agent = str(r[0])
        pnl = float(r[1]) if r[1] else 0.0
        agents[agent] = pnl
        total_pnl += pnl
        
    total_pct = (total_pnl / equity) * 100 if equity > 0 else 0.0
    agents_pct = {k: (v / equity) * 100 for k, v in agents.items()}
    
    # Check if learning is blocked
    blocked_raw = await redis_client.get("algo:learning_blocked")
    is_blocked = (blocked_raw and blocked_raw.decode() == "true")
    
    return {
        "agents_pnl": agents,
        "agents_pct": agents_pct,
        "total_pnl": total_pnl,
        "total_pct": total_pct,
        "learning_blocked": is_blocked is True
    }

