"""
Account router — canonical source of business state for the UI.

Frontend must hydrate from here (never from WebSocket).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db

router = APIRouter()


@router.get("/account")
async def get_account(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("SELECT balance, equity, peak_equity, drawdown FROM virtual_accounts WHERE user_id='default'")
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "mode": "real",
        "balance": float(row[0]),
        "equity": float(row[1]),
        "peak_equity": float(row[2]),
        "drawdown": float(row[3]),
    }

