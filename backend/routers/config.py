"""
Config router — read/write system configuration (auto mode toggle, thresholds).
"""
import os
import json
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from routers.auth import get_current_user, get_current_admin

router = APIRouter()


class ConfigUpdate(BaseModel):
    key: str
    value: str

from services.signals import SELECTABLE_AGENTS as VALID_AGENTS, DEFAULT_AGENT

class AlgorithmSettings(BaseModel):
    active_agent: str = DEFAULT_AGENT   # loki_m | loki_p | loki_t | thor | odin
    engine_active: bool = True
    auto_kelly: bool = True
    kelly_percent: float = 1.0

@router.get("/")
async def get_all_config(
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("SELECT key, value FROM system_config"))
    return {row[0]: row[1] for row in result.fetchall()}


@router.post("/")
async def update_config(update: ConfigUpdate, _: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("""
            INSERT INTO system_config (key, value, updated_at)
            VALUES (:k, :v, NOW())
            ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()
        """),
        {"k": update.key, "v": update.value},
    )
    return {"status": "updated", "key": update.key, "value": update.value}


# ─── API Keys (Gemini / Forex / Crypto) ──────────────────────────────
class ApiKeysUpdate(BaseModel):
    # Any field left None is not modified. Empty string clears the key.
    gemini_api_key: str | None = None
    oanda_api_key: str | None = None
    oanda_account_id: str | None = None
    oanda_environment: str | None = None   # "practice" | "live"
    binance_api_key: str | None = None
    binance_secret_key: str | None = None


async def _get_cfg(db: AsyncSession, key: str) -> str:
    res = await db.execute(text("SELECT value FROM system_config WHERE key=:k"), {"k": key})
    row = res.fetchone()
    return row[0] if row and row[0] else ""


async def _set_cfg(db: AsyncSession, key: str, value: str):
    await db.execute(
        text("""
            INSERT INTO system_config (key, value, updated_at)
            VALUES (:k, :v, NOW())
            ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()
        """),
        {"k": key, "v": value},
    )


@router.get("/keys")
async def get_api_keys(_: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Returns masked presence of each key group — never the raw secrets."""
    gemini = (await _get_cfg(db, "GEMINI_API_KEY")) or os.getenv("GEMINI_API_KEY")
    oanda = (await _get_cfg(db, "OANDA_API_KEY")) or os.getenv("OANDA_API_KEY")
    oanda_acc = (await _get_cfg(db, "OANDA_ACCOUNT_ID")) or os.getenv("OANDA_ACCOUNT_ID")
    oanda_env = (await _get_cfg(db, "OANDA_ENVIRONMENT")) or os.getenv("OANDA_ENVIRONMENT")
    binance = (await _get_cfg(db, "BINANCE_API_KEY")) or os.getenv("BINANCE_API_KEY")
    binance_sec = (await _get_cfg(db, "BINANCE_SECRET_KEY")) or os.getenv("BINANCE_SECRET_KEY")

    def is_configured(val):
        return bool(val) and val.strip() != ""

    return {
        "gemini": {"configured": is_configured(gemini)},
        "forex": {
            "configured": is_configured(oanda),
            "account_id": oanda_acc if is_configured(oanda_acc) else "",
            "environment": oanda_env or "practice",
        },
        "crypto": {"configured": is_configured(binance) and is_configured(binance_sec)},
    }



@router.post("/keys")
async def save_api_keys(update: ApiKeysUpdate, _: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Persists provided secrets to system_config. Fields left null are untouched."""
    mapping = {
        "GEMINI_API_KEY": update.gemini_api_key,
        "OANDA_API_KEY": update.oanda_api_key,
        "OANDA_ACCOUNT_ID": update.oanda_account_id,
        "OANDA_ENVIRONMENT": update.oanda_environment,
        "BINANCE_API_KEY": update.binance_api_key,
        "BINANCE_SECRET_KEY": update.binance_secret_key,
    }
    updated = []
    for key, val in mapping.items():
        if val is not None:
            await _set_cfg(db, key, val)
            updated.append(key)
    return {"status": "saved", "updated": updated}


@router.post("/toggle-auto")
async def toggle_auto(request: Request, _: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT value FROM system_config WHERE key='auto_mode'"))
    row = result.fetchone()
    current = (row[0] if row else "false").lower() == "true"
    new_val = "false" if current else "true"
    await db.execute(
        text("UPDATE system_config SET value=:v WHERE key='auto_mode'"),
        {"v": new_val},
    )
    # Keep Redis config in sync (DecisionEngine reads from Redis).
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            await redis.set("config:auto_mode", new_val)
    except Exception:
        pass
    return {"auto_mode": new_val == "true"}


@router.post("/algorithms")
async def update_algorithm_settings(settings: AlgorithmSettings, _: dict = Depends(get_current_user)):
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))

    active_agent = settings.active_agent if settings.active_agent in VALID_AGENTS else DEFAULT_AGENT

    await redis_client.set("config:active_agent", active_agent)
    await redis_client.set("config:engine_enabled", "true" if settings.engine_active else "false")
    await redis_client.set("config:algo:auto_kelly", "true" if settings.auto_kelly else "false")
    await redis_client.set("config:algo:kelly_percent", str(settings.kelly_percent))

    return {"status": "success", "message": "Algorithm configuration saved to Redis."}

@router.get("/algorithms")
async def get_algorithm_settings(_: dict = Depends(get_current_user)):
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))

    agent = await redis_client.get("config:active_agent")
    engine_on = await redis_client.get("config:engine_enabled")
    auto_kel = await redis_client.get("config:algo:auto_kelly")
    kel_pct = await redis_client.get("config:algo:kelly_percent")

    return {
        "active_agent": agent.decode() if agent else DEFAULT_AGENT,
        "engine_active": engine_on.decode() == "true" if engine_on else True,
        "auto_kelly": auto_kel.decode() == "true" if auto_kel else True,
        "kelly_percent": float(kel_pct.decode()) if kel_pct else 1.0
    }

@router.get("/gemini-usage")
async def gemini_usage(_: dict = Depends(get_current_admin)):
    """Today's Gemini call count plus the configured cap and scan intervals."""
    from services.gemini_predictor import get_gemini_usage
    return await get_gemini_usage()


@router.get("/agent/stats")
async def get_agent_stats(_: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Returns total trades, and winrate for all three agents."""
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))

    from services.weight_optimizer import DEFAULT_WEIGHTS
    from services.signals import AGENT_WEIGHTS

    agents = list(VALID_AGENTS)
    res_data = {}

    for agent in agents:
        if agent == "odin":
            key = f"agent:weights:{agent}"
            data = await redis_client.get(key)
            weights = json.loads(data) if data else DEFAULT_WEIGHTS
        else:
            # Static presets (Loki M/P/T single-pillar, Thor equal blend).
            weights = AGENT_WEIGHTS.get(agent, {})

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

        res_data[agent] = {
            "name": agent.capitalize(),
            "weights": weights,
            "total_trades": total,
            "winrate": winrate
        }

    return res_data

class AlgorithmSettingsReset(BaseModel):
    amount: float

@router.post("/wallet/reset")
async def reset_wallet(
    req: AlgorithmSettingsReset,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resets the user's paper trading account and closes their open positions."""
    uid = str(current_user["id"])
    await db.execute(
        text("UPDATE positions SET status='CLOSED', closed_at=NOW(), realized_pnl=0 WHERE user_id=:uid AND status='OPEN'"),
        {"uid": uid},
    )
    await db.execute(
        text("""
            UPDATE virtual_accounts
            SET balance = :amt, equity = :amt, peak_equity = :amt, drawdown = 0.0
            WHERE user_id = :uid
        """),
        {"amt": req.amount, "uid": uid},
    )
    await db.commit()
    return {"status": "ok", "message": f"Wallet reset to {req.amount} (open trades force-closed)."}
