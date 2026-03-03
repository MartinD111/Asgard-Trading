"""
Simulation router — isolated API namespace for simulation execution context.

All simulation state MUST live in simulation_* tables and must not mutate real tables.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db

router = APIRouter(prefix="/simulation")


class SimulationStartRequest(BaseModel):
    initial_balance: float = Field(..., gt=0)
    currency: str = Field("EUR", min_length=1, max_length=8)


class SimulationAlgorithmSettings(BaseModel):
    short_term_active: bool
    medium_term_active: bool
    long_term_active: bool
    short_allocation: float
    medium_allocation: float
    long_allocation: float
    short_strategy: str = "loki_pro"
    medium_strategy: str = "thor_pro"
    long_strategy: str = "odin_pro"
    auto_allocation: bool = False
    auto_kelly: bool = True
    kelly_percent: float = 1.0


@router.post("/start")
async def start_simulation(req: SimulationStartRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # 1) Create session
    res = await db.execute(
        text(
            """
            INSERT INTO simulation_sessions (user_id, initial_balance, currency, status)
            VALUES ('default', :bal, :cur, 'RUNNING')
            RETURNING id
            """
        ),
        {"bal": req.initial_balance, "cur": req.currency.upper()},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create simulation session")
    simulation_id = str(row[0])

    # 2) Create isolated account snapshot
    await db.execute(
        text(
            """
            INSERT INTO simulation_accounts (session_id, balance, equity, peak_equity, drawdown)
            VALUES (:sid, :bal, :bal, :bal, 0.0)
            """
        ),
        {"sid": simulation_id, "bal": req.initial_balance},
    )

    # 3) Trading freeze (real)
    # Preserve previous auto_mode so we can restore on exit.
    prev_res = await db.execute(text("SELECT value FROM system_config WHERE key='auto_mode'"))
    prev_row = prev_res.fetchone()
    prev_auto_mode = (prev_row[0] if prev_row else "false")

    # Ensure DB config reflects freeze too (UI reads it).
    await db.execute(text("UPDATE system_config SET value='false' WHERE key='auto_mode'"))

    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        # Freeze real loops
        await redis.set("execution:real_enabled", "false")
        # Force auto mode off (engine reads this)
        await redis.set("config:auto_mode", "false")
        await redis.set("execution:real_auto_mode_prev", str(prev_auto_mode).lower())

    return {"simulation_id": simulation_id}


@router.post("/{simulation_id}/stop")
async def stop_simulation(simulation_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text(
            """
            UPDATE simulation_sessions
            SET status='STOPPED', ended_at=NOW()
            WHERE id=:sid AND status='RUNNING'
            RETURNING id
            """
        ),
        {"sid": simulation_id},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found or already stopped")

    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        await redis.set("execution:real_enabled", "true")
        prev = await redis.get("execution:real_auto_mode_prev")
        if prev is not None:
            prev_val = prev.decode()
            await redis.set("config:auto_mode", prev_val)
            await db.execute(text("UPDATE system_config SET value=:v WHERE key='auto_mode'"), {"v": prev_val})

    return {"status": "ok"}


@router.get("/{simulation_id}/account")
async def get_simulation_account(simulation_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text(
            """
            SELECT s.id, s.initial_balance, s.currency, s.started_at, s.ended_at, s.status,
                   a.balance, a.equity, a.peak_equity, a.drawdown
            FROM simulation_sessions s
            JOIN simulation_accounts a ON a.session_id = s.id
            WHERE s.id = :sid
            """
        ),
        {"sid": simulation_id},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return {
        "mode": "simulation",
        "simulation_id": str(row[0]),
        "initial_balance": float(row[1]),
        "currency": str(row[2]),
        "started_at": row[3].isoformat() if row[3] else None,
        "ended_at": row[4].isoformat() if row[4] else None,
        "status": str(row[5]),
        "balance": float(row[6]),
        "equity": float(row[7]),
        "peak_equity": float(row[8]),
        "drawdown": float(row[9]),
    }


@router.get("/{simulation_id}/stats/market/history")
async def get_simulation_market_history(
    simulation_id: str,
    request: Request,
    symbol: str = Query(..., description="E.g. BTCUSDT, EUR_USD, AAPL"),
    range_query: str = Query("1D", alias="range", description="1M, 1H, 1D, 1W, 3M, 1Y"),
):
    """
    Simulation namespace wrapper around market history.
    Data source is shared/cached, but endpoint namespace stays simulation-scoped.
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")

    from services.market_history_service import MarketHistoryService

    svc = MarketHistoryService(redis=redis)
    return await svc.get_history(symbol=symbol, range_query=range_query)


@router.get("/{simulation_id}/stats/history")
async def get_simulation_trade_history(
    simulation_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Simulation-scoped trade history (isolated from real `positions` / `prediction_logs`).
    """
    res = await db.execute(
        text(
            """
            SELECT opened_at, symbol, side, entry_price, close_price, realized_pnl, status
            FROM simulation_trades
            WHERE session_id=:sid
            ORDER BY opened_at DESC
            LIMIT :limit
            """
        ),
        {"sid": simulation_id, "limit": limit},
    )
    rows = res.fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "timestamp": r[0].isoformat() if r[0] else None,
                "symbol": r[1],
                "direction": r[2],
                "agent_used": "simulation",
                "reasoning": "Simulation trade",
                "entry_price": float(r[3]) if r[3] is not None else None,
                "close_price": float(r[4]) if r[4] is not None else None,
                "realized_pnl": float(r[5]) if r[5] is not None else 0.0,
                "status": r[6],
                "is_what_if": True,
            }
        )
    return out


def _sim_key(simulation_id: str, suffix: str) -> str:
    return f"sim:{simulation_id}:{suffix}"


@router.get("/{simulation_id}/config/algorithms")
async def get_simulation_algorithm_settings(simulation_id: str, request: Request):
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")

    async def g(key: str):
        raw = await redis.get(key)
        return raw.decode() if raw else None

    s_active = await g(_sim_key(simulation_id, "config:algo:short_enabled"))
    m_active = await g(_sim_key(simulation_id, "config:algo:medium_enabled"))
    l_active = await g(_sim_key(simulation_id, "config:algo:long_enabled"))

    s_alloc = await g(_sim_key(simulation_id, "config:algo:short_allocation"))
    m_alloc = await g(_sim_key(simulation_id, "config:algo:medium_allocation"))
    l_alloc = await g(_sim_key(simulation_id, "config:algo:long_allocation"))

    s_strat = await g(_sim_key(simulation_id, "config:algo:short_strategy"))
    m_strat = await g(_sim_key(simulation_id, "config:algo:medium_strategy"))
    l_strat = await g(_sim_key(simulation_id, "config:algo:long_strategy"))

    auto_alloc = await g(_sim_key(simulation_id, "config:algo:auto_allocation"))
    auto_kel = await g(_sim_key(simulation_id, "config:algo:auto_kelly"))
    kel_pct = await g(_sim_key(simulation_id, "config:algo:kelly_percent"))

    return {
        "short_term_active": (s_active == "true") if s_active is not None else True,
        "medium_term_active": (m_active == "true") if m_active is not None else True,
        "long_term_active": (l_active == "true") if l_active is not None else False,
        "short_allocation": float(s_alloc) if s_alloc is not None else 40.0,
        "medium_allocation": float(m_alloc) if m_alloc is not None else 40.0,
        "long_allocation": float(l_alloc) if l_alloc is not None else 20.0,
        "short_strategy": s_strat or "loki_pro",
        "medium_strategy": m_strat or "thor_pro",
        "long_strategy": l_strat or "odin_pro",
        "auto_allocation": (auto_alloc == "true") if auto_alloc is not None else False,
        "auto_kelly": (auto_kel == "true") if auto_kel is not None else True,
        "kelly_percent": float(kel_pct) if kel_pct is not None else 1.0,
    }


@router.post("/{simulation_id}/config/algorithms")
async def update_simulation_algorithm_settings(
    simulation_id: str, request: Request, settings: SimulationAlgorithmSettings
):
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")

    await redis.set(_sim_key(simulation_id, "config:algo:short_enabled"), "true" if settings.short_term_active else "false")
    await redis.set(_sim_key(simulation_id, "config:algo:medium_enabled"), "true" if settings.medium_term_active else "false")
    await redis.set(_sim_key(simulation_id, "config:algo:long_enabled"), "true" if settings.long_term_active else "false")

    await redis.set(_sim_key(simulation_id, "config:algo:short_allocation"), str(settings.short_allocation))
    await redis.set(_sim_key(simulation_id, "config:algo:medium_allocation"), str(settings.medium_allocation))
    await redis.set(_sim_key(simulation_id, "config:algo:long_allocation"), str(settings.long_allocation))

    await redis.set(_sim_key(simulation_id, "config:algo:short_strategy"), settings.short_strategy)
    await redis.set(_sim_key(simulation_id, "config:algo:medium_strategy"), settings.medium_strategy)
    await redis.set(_sim_key(simulation_id, "config:algo:long_strategy"), settings.long_strategy)

    await redis.set(_sim_key(simulation_id, "config:algo:auto_allocation"), "true" if settings.auto_allocation else "false")
    await redis.set(_sim_key(simulation_id, "config:algo:auto_kelly"), "true" if settings.auto_kelly else "false")
    await redis.set(_sim_key(simulation_id, "config:algo:kelly_percent"), str(settings.kelly_percent))

    return {"status": "success"}


@router.post("/{simulation_id}/config/algorithms/auto-allocation")
async def toggle_simulation_auto_allocation(simulation_id: str, request: Request):
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")

    key = _sim_key(simulation_id, "config:algo:auto_allocation")
    current = await redis.get(key)
    is_auto = (current and current.decode() == "true")
    new_val = "false" if is_auto else "true"
    await redis.set(key, new_val)
    return {"auto_allocation": new_val == "true"}


@router.get("/{simulation_id}/config")
async def get_simulation_config(simulation_id: str, db: AsyncSession = Depends(get_db)):
    """
    Simulation-scoped config namespace.
    For now it mirrors global config (read-only), but keeps frontend within /api/simulation/*.
    """
    res = await db.execute(text("SELECT key, value FROM system_config"))
    return {row[0]: row[1] for row in res.fetchall()}


@router.get("/{simulation_id}/stats/what_if")
async def get_simulation_what_if(
    simulation_id: str,
    request: Request,
    timeframe: str = Query("short"),
    days: int = Query(30),
    symbol: str = Query("BTCUSDT"),
    db: AsyncSession = Depends(get_db),
):
    from routers.stats import get_what_if_stats

    return await get_what_if_stats(request=request, timeframe=timeframe, days=days, symbol=symbol, db=db)


@router.get("/{simulation_id}/stats/daily_contribution")
async def get_simulation_daily_contribution(simulation_id: str, db: AsyncSession = Depends(get_db)):
    from routers.stats import get_daily_contribution

    return await get_daily_contribution(db=db)

