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

@router.post("/users")
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db), admin: dict = Depends(get_current_admin)):
    hashed_pw = get_password_hash(user.password)
    try:
        await db.execute(
            text("""
            INSERT INTO users (username, password_hash, is_admin, avatar_id) 
            VALUES (:u, :p, :a, :av)
            """),
            {"u": user.username, "p": hashed_pw, "a": user.is_admin, "av": user.avatar_id}
        )
        await db.commit()
        return {"message": "User created successfully"}
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
    # Calculate 24h and 7d PnL by querying positions table for each user account.
    # Currently virtual_accounts and positions do not explicitly tie to users yet, 
    # but we can return mocked or placeholder stats until the virtual account user_id binding is fully unified.
    # We will simulate a simple PnL query for demo purposes.
    result = await db.execute(text("SELECT id, username FROM users"))
    users = result.fetchall()
    
    stats = []
    for u in users:
        # PnL logic can be aggregated from positions or prediction_logs.
        # For this example, we mock the daily and weekly % for now.
        stats.append({
            "user_id": str(u._mapping["id"]),
            "username": u._mapping["username"],
            "pnl_24h": round(1.2 + (len(u._mapping["username"]) % 5) * 0.5, 2), # mocked pseudo-random positive/negative PnL
            "pnl_7d": round(4.5 + (len(u._mapping["username"]) % 7) * 1.5, 2)
        })
    return stats
