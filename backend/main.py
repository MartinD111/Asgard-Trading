"""
FastAPI application — entry point.
"""
import logging
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from services.logging_config import setup_logging

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _require_env(*names: str) -> None:
    """Fail fast at startup if any required environment variable is missing."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise RuntimeError(
            f"Required environment variables not set: {', '.join(missing)}. "
            "Check your .env file or deployment config."
        )

from db.database import init_db
from routers import trades, config, stats, auth, admin, account, simulation, brokers, backtest
from sockets.manager import ws_router, ConnectionManager
from services.market_data import MarketDataService
from services.decision_engine import DecisionEngine
from services.gemini_predictor import GeminiPredictor
from services.macro_risk_analyzer import MacroRiskAnalyzer
from services.weight_optimizer import AgentOptimizer
from services.position_manager import PositionManager
from services.simulation_engine import SimulationEngine
from services.reconciliation import run_reconciliation_loop

manager = ConnectionManager()
redis_client: aioredis.Redis | None = None
market_service: MarketDataService | None = None

async def broadcast_portfolio_loop(ws_man):
    from sqlalchemy import text
    from db.database import AsyncSessionLocal
    import json
    from datetime import datetime

    def default_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Query all users with virtual accounts and broadcast per-user portfolio updates.
                # Per-user channels ("user:{uid}") are consumed by authenticated WS connections (M5).
                # The legacy "real" channel receives the last user's payload for backwards compat.
                users_res = await db.execute(
                    text("SELECT user_id, balance, equity FROM virtual_accounts")
                )
                users = users_res.fetchall()

                for user_row in users:
                    uid = str(user_row[0])
                    balance = float(user_row[1])
                    equity = float(user_row[2])

                    pos_res = await db.execute(
                        text(
                            "SELECT symbol, side, quantity, entry_price, current_price "
                            "FROM positions WHERE status='OPEN' AND user_id = :uid"
                        ),
                        {"uid": uid},
                    )
                    positions = [
                        {
                            "symbol": p[0],
                            "side": p[1],
                            "size": float(p[2]),
                            "entryPrice": float(p[3]),
                            "currentPrice": float(p[4]),
                            "unrealizedPnl": (float(p[4]) - float(p[3])) * float(p[2]) * (1 if p[1] == "BUY" else -1),
                        }
                        for p in pos_res.fetchall()
                    ]

                    payload = json.dumps(
                        {
                            "type": "PORTFOLIO_UPDATE",
                            "payload": {"balance": balance, "equity": equity, "positions": positions},
                        },
                        default=default_serializer,
                    )

                    await ws_man.broadcast(payload, channel=f"user:{uid}")

                # Broadcast active simulation portfolios to their own channels
                sim_res = await db.execute(
                    text(
                        """
                        SELECT s.id, a.balance, a.equity
                        FROM simulation_sessions s
                        JOIN simulation_accounts a ON a.session_id = s.id
                        WHERE s.status='RUNNING'
                        """
                    )
                )
                for sim_row in sim_res.fetchall():
                    sim_id = str(sim_row[0])
                    sim_balance = float(sim_row[1])
                    sim_equity = float(sim_row[2])

                    pos_res = await db.execute(
                        text(
                            """
                            SELECT symbol, side, quantity, entry_price, current_price
                            FROM simulation_trades
                            WHERE session_id=:sid AND status='OPEN'
                            """
                        ),
                        {"sid": sim_id},
                    )
                    sim_positions = [
                        {
                            "symbol": p[0],
                            "side": p[1],
                            "size": float(p[2]),
                            "entryPrice": float(p[3]),
                            "currentPrice": float(p[4]) if p[4] is not None else float(p[3]),
                            "unrealizedPnl": ((float(p[4]) if p[4] is not None else float(p[3])) - float(p[3]))
                            * float(p[2])
                            * (1 if p[1] == "BUY" else -1),
                        }
                        for p in pos_res.fetchall()
                    ]

                    sim_payload = json.dumps(
                        {
                            "type": "PORTFOLIO_UPDATE",
                            "payload": {
                                "balance": sim_balance,
                                "equity": sim_equity,
                                "positions": sim_positions,
                            },
                        },
                        default=default_serializer,
                    )
                    await ws_man.broadcast(sim_payload, channel=f"sim:{sim_id}")
                    
        except Exception as e:
            logger.error("portfolio_broadcast_error", exc_info=True)

        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, market_service

    # Fail fast on missing required secrets — do not start with defaults
    _require_env("JWT_SECRET_KEY", "DATABASE_URL", "REDIS_URL", "FERNET_KEY", "ADMIN_PASSWORD")

    # Init DB schema
    await init_db()

    # Seed admin password from env (replaces the placeholder_hash from schema.sql)
    from sqlalchemy import text as _text
    from db.database import AsyncSessionLocal as _Session
    from services.auth_service import get_password_hash as _hash
    async with _Session() as _db:
        _admin_hash = _hash(os.environ["ADMIN_PASSWORD"])
        await _db.execute(
            _text("UPDATE users SET password_hash = :h WHERE username = 'admin'"),
            {"h": _admin_hash},
        )
        await _db.commit()

    # Redis & WS
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    app.state.redis = redis_client
    app.state.ws_manager = manager
    # Default execution state: real enabled
    await redis_client.set("execution:real_enabled", "true")
    # Sync DB auto_mode -> Redis (DecisionEngine reads from Redis)
    try:
        from sqlalchemy import text
        from db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            res = await db.execute(text("SELECT value FROM system_config WHERE key='auto_mode'"))
            row = res.fetchone()
            if row:
                await redis_client.set("config:auto_mode", str(row[0]).lower())
    except Exception:
        pass

    # Warm-start: backfill historical candles then seed Redis candle buffers
    try:
        from services.historical_backfill import run_backfill
        from services.candle_store import get_candles
        from services.decision_engine import ALL_SYMBOLS
        import json as _json
        await run_backfill()
        for _sym in ALL_SYMBOLS:
            _hist = await get_candles(_sym, limit=500)
            if _hist:
                await redis_client.set(f"candles:{_sym}", _json.dumps(_hist))
                await redis_client.set(f"last_price:{_sym}", _hist[-1]["close"])
                logger.info(f"Warm-started {_sym} with {len(_hist)} candles from DB.")
    except Exception as _e:
        logger.warning(f"Backfill/warm-start error (non-fatal): {_e}")

    # Services
    predictor = GeminiPredictor()
    engine = DecisionEngine(predictor=predictor, redis=redis_client, ws_manager=manager, ws_channel="real")
    market_service = MarketDataService(redis=redis_client, ws_manager=manager)
    macro_risk = MacroRiskAnalyzer(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"), ws_manager=manager)
    optimizer = AgentOptimizer(redis_client=redis_client)
    pos_manager = PositionManager(redis_client=redis_client)
    sim_engine = SimulationEngine(redis=redis_client, ws_manager=manager)

    from services.broker_balances import fetch_real_balances
    
    # Background tasks
    tasks = [
        asyncio.create_task(market_service.start()),
        asyncio.create_task(engine.run_loop()),
        asyncio.create_task(macro_risk.run_loop()),
        asyncio.create_task(broadcast_portfolio_loop(manager)),
        asyncio.create_task(optimizer.run_loop()),
        asyncio.create_task(pos_manager.run_loop()),
        asyncio.create_task(sim_engine.run_loop()),
        asyncio.create_task(run_reconciliation_loop(redis_client)),
        # asyncio.create_task(fetch_real_balances()),
    ]

    yield

    # Cleanup
    for t in tasks:
        t.cancel()
    if redis_client:
        await redis_client.aclose()


app = FastAPI(
    title="AI Trading System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: read allowed origins from env (comma-separated). Never use "*" with credentials.
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ────────────────────────────────────────────────
app.include_router(trades.router, prefix="/api", tags=["Trades"])
app.include_router(account.router, prefix="/api", tags=["Account"])
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(stats.router, prefix="/api/stats", tags=["Stats"])
app.include_router(simulation.router, prefix="/api", tags=["Simulation"])
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(brokers.router)
app.include_router(backtest.router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    """Liveness + readiness probe — checks Redis and DB connectivity."""
    checks: dict = {"status": "ok", "mode": os.getenv("TRADING_MODE", "PAPER")}

    # Redis ping
    try:
        r = getattr(app.state, "redis", None)
        if r:
            await r.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_initialized"
    except Exception:
        checks["redis"] = "error"
        checks["status"] = "degraded"

    # DB connectivity
    try:
        from db.database import AsyncSessionLocal
        from sqlalchemy import text as _t
        async with AsyncSessionLocal() as _db:
            await _db.execute(_t("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"
        checks["status"] = "degraded"

    return checks
