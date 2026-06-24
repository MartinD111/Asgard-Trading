from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db.database import get_db
from pydantic import BaseModel
from typing import List, Optional
from routers.auth import get_current_admin
from services.auth_service import get_password_hash

router = APIRouter(prefix="/api/admin", tags=["admin"])

class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False
    avatar_id: Optional[str] = "odin"

class UserUpdate(BaseModel):
    password: Optional[str] = None
    avatar_id: Optional[str] = None

@router.get("/users")
async def get_all_users(db: AsyncSession = Depends(get_db), admin: dict = Depends(get_current_admin)):
    result = await db.execute(text("SELECT id, username, is_admin, avatar_id, created_at FROM users ORDER BY created_at DESC"))
    users = []
    for row in result.fetchall():
        users.append(dict(row._mapping))
    return users

@router.post("/users", status_code=201)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db), admin: dict = Depends(get_current_admin)):
    hashed_pw = get_password_hash(user.password)
    try:
        result = await db.execute(
            text("""
            INSERT INTO users (username, password_hash, is_admin, avatar_id)
            VALUES (:u, :p, :a, :av)
            RETURNING id, username, is_admin, avatar_id
            """),
            {"u": user.username, "p": hashed_pw, "a": user.is_admin, "av": user.avatar_id}
        )
        row = result.fetchone()
        user_id = str(row[0])
        await db.execute(
            text(
                "INSERT INTO virtual_accounts (user_id, balance, equity, peak_equity) "
                "VALUES (:uid, 100000, 100000, 100000) ON CONFLICT (user_id) DO NOTHING"
            ),
            {"uid": user_id},
        )
        await db.commit()
        return {"id": user_id, "username": row[1], "is_admin": bool(row[2]), "avatar_id": row[3]}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), admin: dict = Depends(get_current_admin)):
    await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    await db.commit()
    return {"message": "User deleted successfully"}

@router.get("/stats")
async def get_user_stats(db: AsyncSession = Depends(get_db), admin: dict = Depends(get_current_admin)):
    """
    Per-user 24h / 7d realized PnL.

    Positions are not yet bound to individual users (single shared 'default' virtual account),
    so until that binding exists we report the real shared realized PnL aggregated from the
    positions table. No fabricated/pseudo-random values.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    pnl_res = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(realized_pnl) FILTER (WHERE closed_at >= :day_ago), 0)  AS pnl_24h,
                COALESCE(SUM(realized_pnl) FILTER (WHERE closed_at >= :week_ago), 0) AS pnl_7d
            FROM positions
            WHERE status = 'CLOSED'
        """),
        {"day_ago": day_ago, "week_ago": week_ago},
    )
    prow = pnl_res.fetchone()
    pnl_24h = round(float(prow[0]), 2) if prow and prow[0] is not None else 0.0
    pnl_7d = round(float(prow[1]), 2) if prow and prow[1] is not None else 0.0

    result = await db.execute(text("SELECT id, username FROM users"))
    users = result.fetchall()

    stats = []
    for u in users:
        stats.append({
            "user_id": str(u._mapping["id"]),
            "username": u._mapping["username"],
            "pnl_24h": pnl_24h,
            "pnl_7d": pnl_7d,
        })
    return stats
