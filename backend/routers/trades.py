"""
API routers — trades, portfolio, prediction logs.
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
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    acc = await db.execute(
        text("SELECT balance, equity, peak_equity, drawdown FROM virtual_accounts WHERE user_id='default'")
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
async def get_positions(status: str = "OPEN", db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM positions WHERE status=:s ORDER BY opened_at DESC LIMIT 50"),
        {"s": status},
    )
    cols = result.keys()
    rows = result.fetchall()
    return [dict(zip(cols, r)) for r in rows]


@router.delete("/positions/{position_id}")
async def close_position(position_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("UPDATE positions SET status='CLOSED', closed_at=NOW() WHERE id=:id"),
        {"id": position_id},
    )
    return {"status": "closed"}


# ─── Manual Trade ────────────────────────────────────────────
@router.post("/manual-trade")
async def manual_trade(req: ManualTradeRequest, db: AsyncSession = Depends(get_db)):
    if req.direction not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="direction must be BUY or SELL")

    result = await db.execute(
        text(
            """INSERT INTO positions
            (symbol, side, quantity, entry_price, current_price, stop_loss, take_profit, status, final_score)
            VALUES (:sym, :side, :qty, :ep, :ep, :sl, :tp, 'OPEN', 0.0)
            RETURNING id"""
        ),
        {
            "sym": req.symbol,
            "side": req.direction,
            "qty": req.quantity,
            "ep": req.entry_price,
            "sl": req.stop_loss,
            "tp": req.take_profit,
        },
    )
    row = result.fetchone()
    return {"position_id": str(row[0]), "status": "opened"}


# ─── Prediction Logs ─────────────────────────────────────────
@router.get("/prediction-logs")
async def prediction_logs(
    symbol: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    if symbol:
        result = await db.execute(
            text(
                "SELECT * FROM prediction_logs WHERE symbol=:s ORDER BY timestamp DESC LIMIT :l"
            ),
            {"s": symbol, "l": limit},
        )
    else:
        result = await db.execute(
            text("SELECT * FROM prediction_logs ORDER BY timestamp DESC LIMIT :l"),
            {"l": limit},
        )
    cols = result.keys()
    rows = result.fetchall()
    return [dict(zip(cols, r)) for r in rows]


# ─── Correlations ────────────────────────────────────────────
@router.get("/correlations")
async def get_correlations():
    """Returns static correlation matrix (will be dynamic with GNN model)."""
    matrix = {
        "XAU_USD": {"XAG_USD": 0.85, "EUR_USD": 0.40, "BTCUSDT": 0.30},
        "XAG_USD": {"XAU_USD": 0.85, "EUR_USD": 0.35, "BTCUSDT": 0.28},
        "EUR_USD": {"XAU_USD": 0.40, "XAG_USD": 0.35, "BTCUSDT": 0.20},
        "BTCUSDT": {"XAU_USD": 0.30, "AAPL": 0.25, "EUR_USD": 0.20},
        "AAPL": {"BTCUSDT": 0.25, "SPY": 0.78},
    }
    return matrix
