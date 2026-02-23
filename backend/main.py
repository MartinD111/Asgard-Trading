"""
FastAPI application — entry point.
"""
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from db.database import init_db
from routers import trades, paypal, config, stats, auth, admin
from websocket.manager import ws_router, ConnectionManager
from services.market_data import MarketDataService
from services.decision_engine import DecisionEngine
from services.gemini_predictor import GeminiPredictor
from services.macro_risk_analyzer import MacroRiskAnalyzer
from services.weight_optimizer import AgentOptimizer
from services.position_manager import PositionManager

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
                acc = await db.execute(
                    text("SELECT balance, equity FROM virtual_accounts WHERE user_id='default'")
                )
                row = acc.fetchone()
                if row:
                    balance = float(row[0])
                    equity = float(row[1])
                    
                    # Fetch basic position data for UI
                    pos_res = await db.execute(
                        text("SELECT symbol, side, quantity, entry_price, current_price FROM positions WHERE status='OPEN'")
                    )
                    positions = [
                        {
                            "symbol": p[0],
                            "side": p[1],
                            "size": float(p[2]),
                            "entryPrice": float(p[3]),
                            "currentPrice": float(p[4]),
                            "unrealizedPnl": (float(p[4]) - float(p[3])) * float(p[2]) * (1 if p[1] == 'BUY' else -1)
                        }
                        for p in pos_res.fetchall()
                    ]
                    
                    payload = json.dumps({
                        "type": "PORTFOLIO_UPDATE",
                        "payload": {
                            "balance": balance,
                            "equity": equity,
                            "positions": positions
                        }
                    }, default=default_serializer)
                    
                    await ws_man.broadcast(payload)
                    
        except Exception as e:
            print(f"Portfolio broadcast error: {e}")
            
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, market_service

    # Init DB schema
    await init_db()

    # Redis
    redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    app.state.redis = redis_client

    # Services
    predictor = GeminiPredictor()
    engine = DecisionEngine(predictor=predictor, redis=redis_client, ws_manager=manager)
    market_service = MarketDataService(redis=redis_client, ws_manager=manager)
    macro_risk = MacroRiskAnalyzer(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"), ws_manager=manager)
    optimizer = AgentOptimizer(redis_client=redis_client)
    pos_manager = PositionManager(redis_client=redis_client)

    # Background tasks
    tasks = [
        asyncio.create_task(market_service.start()),
        asyncio.create_task(engine.run_loop()),
        asyncio.create_task(macro_risk.run_loop()),
        asyncio.create_task(broadcast_portfolio_loop(manager)),
        asyncio.create_task(optimizer.run_loop()),
        asyncio.create_task(pos_manager.run_loop()),
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ────────────────────────────────────────────────
app.include_router(trades.router, prefix="/api", tags=["Trades"])
app.include_router(paypal.router, prefix="/api/paypal", tags=["PayPal"])
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(stats.router, prefix="/api/stats", tags=["Stats"])
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": os.getenv("TRADING_MODE", "PAPER")}
