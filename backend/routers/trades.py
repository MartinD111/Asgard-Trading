"""
API routers — trades, portfolio, prediction logs.
All endpoints require authentication; data is scoped to the requesting user.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from routers.auth import get_current_user, get_current_admin

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────
class ManualTradeRequest(BaseModel):
    symbol: str
    direction: str  # BUY or SELL
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


# ─── Portfolio ───────────────────────────────────────────────
@router.get("/portfolio")
async def get_portfolio(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user["id"])
    acc = await db.execute(
        text("SELECT balance, equity, peak_equity, drawdown FROM virtual_accounts WHERE user_id=:uid"),
        {"uid": uid},
    )
    row = acc.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "balance": float(row[0]),
        "equity": float(row[1]),
        "peak_equity": float(row[2]),
        "drawdown": float(row[3]),
    }


# ─── Open Positions ──────────────────────────────────────────
@router.get("/positions")
async def get_positions(
    status: str = "OPEN",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user["id"])
    result = await db.execute(
        text(
            "SELECT * FROM positions WHERE user_id=:uid AND status=:s ORDER BY opened_at DESC LIMIT 50"
        ),
        {"uid": uid, "s": status},
    )
    cols = result.keys()
    rows = result.fetchall()
    return [dict(zip(cols, r)) for r in rows]


@router.delete("/positions/{position_id}")
async def close_position(
    position_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user["id"])
    result = await db.execute(
        text(
            "UPDATE positions SET status='CLOSED', closed_at=NOW() "
            "WHERE id=:id AND user_id=:uid RETURNING id"
        ),
        {"id": position_id, "uid": uid},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Position not found")
    await db.commit()
    return {"status": "closed"}


# ─── Manual Trade ────────────────────────────────────────────
@router.post("/manual-trade")
async def manual_trade(
    req: ManualTradeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.direction not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="direction must be BUY or SELL")

    uid = str(current_user["id"])
    result = await db.execute(
        text(
            """INSERT INTO positions
            (user_id, symbol, side, quantity, entry_price, current_price,
             stop_loss, take_profit, status, final_score)
            VALUES (:uid, :sym, :side, :qty, :ep, :ep, :sl, :tp, 'OPEN', 0.0)
            RETURNING id"""
        ),
        {
            "uid": uid,
            "sym": req.symbol,
            "side": req.direction,
            "qty": req.quantity,
            "ep": req.entry_price,
            "sl": req.stop_loss,
            "tp": req.take_profit,
        },
    )
    row = result.fetchone()
    await db.commit()
    return {"position_id": str(row[0]), "status": "opened"}


# ─── Prediction Logs ─────────────────────────────────────────
@router.get("/prediction-logs")
async def prediction_logs(
    symbol: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user["id"])
    if symbol:
        result = await db.execute(
            text(
                "SELECT * FROM prediction_logs "
                "WHERE (user_id IS NULL OR user_id=:uid) AND symbol=:s ORDER BY timestamp DESC LIMIT :l"
            ),
            {"uid": uid, "s": symbol, "l": limit},
        )
    else:
        result = await db.execute(
            text(
                "SELECT * FROM prediction_logs "
                "WHERE (user_id IS NULL OR user_id=:uid) ORDER BY timestamp DESC LIMIT :l"
            ),
            {"uid": uid, "l": limit},
        )
    cols = result.keys()
    rows = result.fetchall()
    return [dict(zip(cols, r)) for r in rows]


# ─── Kill Switch ─────────────────────────────────────────────
@router.get("/kill-switch")
async def get_kill_switch_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return kill-switch state for the calling user + the global gate."""
    uid = str(current_user["id"])
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")
    global_raw = await redis.get("execution:real_enabled")
    user_raw   = await redis.get(f"kill_switch:user:{uid}")
    return {
        "global_halted": (global_raw or b"true").decode() != "true",
        "user_halted":   (user_raw  or b"false").decode() == "true",
    }


@router.post("/kill-switch")
async def activate_kill_switch(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Halt automated trading for the calling user."""
    uid = str(current_user["id"])
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")
    await redis.set(f"kill_switch:user:{uid}", "true")
    await db.execute(
        text(
            "INSERT INTO audit_log (user_id, event_type, payload) "
            "VALUES (:uid, 'KILL_SWITCH', '{\"source\":\"user_request\"}'::jsonb)"
        ),
        {"uid": uid},
    )
    await db.commit()
    return {"status": "halted", "user_id": uid}


@router.delete("/kill-switch")
async def deactivate_kill_switch(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume automated trading for the calling user."""
    uid = str(current_user["id"])
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")
    await redis.set(f"kill_switch:user:{uid}", "false")
    await db.execute(
        text(
            "INSERT INTO audit_log (user_id, event_type, payload) "
            "VALUES (:uid, 'KILL_SWITCH_CLEARED', '{\"source\":\"user_request\"}'::jsonb)"
        ),
        {"uid": uid},
    )
    await db.commit()
    return {"status": "resumed", "user_id": uid}


@router.post("/kill-switch/global")
async def global_kill_switch(
    request: Request,
    halt: bool = True,
    _: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: halt or resume all real-money execution globally."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")
    await redis.set("execution:real_enabled", "false" if halt else "true")
    event = "KILL_SWITCH_GLOBAL" if halt else "KILL_SWITCH_GLOBAL_CLEARED"
    await db.execute(
        text(
            "INSERT INTO audit_log (event_type, payload) "
            "VALUES (:et, :p::jsonb)"
        ),
        {"et": event, "p": '{"source":"admin_request"}'},
    )
    await db.commit()
    return {"status": "halted" if halt else "resumed", "global": True}


@router.get("/audit-log")
async def get_audit_log(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return recent audit log entries for the calling user."""
    uid = str(current_user["id"])
    result = await db.execute(
        text(
            "SELECT id, event_type, broker, symbol, payload, created_at "
            "FROM audit_log WHERE user_id = :uid "
            "ORDER BY created_at DESC LIMIT :limit"
        ),
        {"uid": uid, "limit": limit},
    )
    cols = result.keys()
    return [dict(zip(cols, r)) for r in result.fetchall()]


# ─── Correlations ────────────────────────────────────────────
@router.get("/correlations")
async def get_correlations():
    """Returns static correlation matrix."""
    return {
        "XAU_USD": {"XAG_USD": 0.85, "EUR_USD": 0.40, "BTCUSDT": 0.30},
        "XAG_USD": {"XAU_USD": 0.85, "EUR_USD": 0.35, "BTCUSDT": 0.28},
        "EUR_USD": {"XAU_USD": 0.40, "XAG_USD": 0.35, "BTCUSDT": 0.20},
        "BTCUSDT": {"XAU_USD": 0.30, "AAPL": 0.25, "EUR_USD": 0.20},
        "AAPL": {"BTCUSDT": 0.25, "SPY": 0.78},
    }
