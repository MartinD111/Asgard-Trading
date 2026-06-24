"""
Account router — canonical source of business state for the UI.

Frontend must hydrate from here (never from WebSocket).
All endpoints require authentication; data is scoped to the requesting user.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from routers.auth import get_current_user

router = APIRouter()


@router.get("/account")
async def get_account(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user["id"])
    res = await db.execute(
        text("SELECT balance, equity, peak_equity, drawdown FROM virtual_accounts WHERE user_id=:uid"),
        {"uid": uid},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found — contact support")
    return {
        "mode": "real",
        "balance": float(row[0]),
        "equity": float(row[1]),
        "peak_equity": float(row[2]),
        "drawdown": float(row[3]),
    }


@router.get("/account/live-mode")
async def get_live_mode(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return whether this user has live (real-money) mode enabled."""
    uid = str(current_user["id"])
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")
    raw = await redis.get(f"user:{uid}:live_mode")
    return {"live_mode": (raw or b"false").decode() == "true"}


@router.get("/account/export")
async def export_account_data(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GDPR data export — return all personal data held for the calling user.
    Broker API keys are NOT included (they are write-only at rest).
    """
    uid = str(current_user["id"])

    acc = await db.execute(
        text("SELECT balance, equity, peak_equity, drawdown, created_at FROM virtual_accounts WHERE user_id=:uid"),
        {"uid": uid},
    )
    acc_row = acc.fetchone()

    pos = await db.execute(
        text("SELECT symbol, side, quantity, entry_price, status, opened_at, closed_at, realized_pnl FROM positions WHERE user_id=:uid ORDER BY opened_at DESC"),
        {"uid": uid},
    )
    positions = [dict(zip(pos.keys(), r)) for r in pos.fetchall()]

    al = await db.execute(
        text("SELECT event_type, broker, symbol, payload, created_at FROM audit_log WHERE user_id=:uid ORDER BY created_at DESC LIMIT 500"),
        {"uid": uid},
    )
    audit = [dict(zip(al.keys(), r)) for r in al.fetchall()]

    bc = await db.execute(
        text("SELECT broker, environment, account_id, is_active, created_at FROM broker_connections WHERE user_id=:uid"),
        {"uid": uid},
    )
    brokers = [dict(zip(bc.keys(), r)) for r in bc.fetchall()]

    return {
        "user": {"id": uid, "username": current_user["username"]},
        "account": dict(zip(acc_row._fields, acc_row)) if acc_row else None,
        "broker_connections": brokers,
        "positions": positions,
        "audit_log": audit,
    }


@router.delete("/account")
async def delete_account(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Right to erasure (GDPR Art. 17).

    - Deletes all broker_connections (removes encrypted keys)
    - Force-closes all open positions
    - Wipes prediction_logs
    - Anonymises the user row (username → deleted_{uid}, email → NULL)
    - Clears Redis live-mode and kill-switch keys

    The user row itself is retained as a tombstone so FK references in
    audit_log/orders remain intact (they ON DELETE SET NULL anyway, but the
    anonymised row is cleaner than a dangling uuid).
    """
    uid = str(current_user["id"])

    await db.execute(text("DELETE FROM broker_connections WHERE user_id=:uid"), {"uid": uid})
    await db.execute(text("UPDATE positions SET status='CLOSED', closed_at=NOW() WHERE user_id=:uid AND status='OPEN'"), {"uid": uid})
    await db.execute(text("DELETE FROM prediction_logs WHERE user_id=:uid"), {"uid": uid})
    await db.execute(
        text("UPDATE users SET username=:u, email=NULL, password_hash='DELETED', updated_at=NOW() WHERE id=:uid"),
        {"u": f"deleted_{uid[:8]}", "uid": uid},
    )
    await db.commit()

    redis = getattr(request.app.state, "redis", None)
    if redis:
        await redis.delete(f"user:{uid}:live_mode", f"kill_switch:user:{uid}")

    return {"status": "deleted", "user_id": uid}


@router.post("/account/live-mode")
async def set_live_mode(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Toggle live (real-money) mode for the calling user.

    Enabling live mode requires at least one active broker connection.
    Returns the new state.
    """
    uid = str(current_user["id"])
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=500, detail="Redis not initialised")

    raw = await redis.get(f"user:{uid}:live_mode")
    current = (raw or b"false").decode() == "true"

    if not current:
        # Enabling — verify at least one active broker connection exists
        res = await db.execute(
            text("SELECT COUNT(*) FROM broker_connections WHERE user_id = :uid AND is_active = TRUE"),
            {"uid": uid},
        )
        count = res.scalar() or 0
        if count == 0:
            raise HTTPException(
                status_code=400,
                detail="No active broker connection found. Add a broker connection before enabling live mode.",
            )

    new_state = not current
    await redis.set(f"user:{uid}:live_mode", "true" if new_state else "false")
    return {"live_mode": new_state}
