import asyncio
import json
import random
import logging
import math
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_backend")

app = FastAPI(title="Asgard Trading Dev Mock Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Databases ---
portfolio_offset = 3237.13

db_config = {
    "auto_mode": "true",
    "risk_level": "medium",
    "learning_blocked": "false"
}

db_algo_settings = {
    "short_term_active": True,
    "medium_term_active": True,
    "long_term_active": False,
    "short_allocation": 40.0,
    "medium_allocation": 40.0,
    "long_allocation": 20.0,
    "short_strategy": "loki_pro",
    "medium_strategy": "thor_pro",
    "long_strategy": "odin_pro",
    "auto_allocation": False,
    "auto_kelly": True,
    "kelly_percent": 1.0
}

db_portfolio = {
    "balance": 8920.45,
    "equity": 12480.22,
    "peak_equity": 12480.22,
    "drawdown": 0.0
}

db_positions = [
    {
        "id": "pos_1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "size": 0.15,
        "entryPrice": 65820.00,
        "currentPrice": 67420.50,
        "stop_loss": 66080.0,
        "take_profit": 70790.0,
        "unrealizedPnl": 240.08,
        "opened_at": "2026-06-06T14:14:00+02:00"
    },
    {
        "id": "pos_2",
        "symbol": "ETHUSDT",
        "side": "BUY",
        "size": 1.20,
        "entryPrice": 3180.00,
        "currentPrice": 3248.80,
        "stop_loss": 3100.0,
        "take_profit": 3400.0,
        "unrealizedPnl": 82.56,
        "opened_at": "2026-06-06T15:14:00+02:00"
    }
]

db_trades_history = [
    {
        "timestamp": "2026-06-06T09:14:00+02:00",
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "agent_used": "loki_pro",
        "reasoning": "Short-term trend shift detected. RSI divergence confirmed on 15m. Momentum aligning.",
        "entry_price": 65280.00,
        "close_price": 66888.00,
        "realized_pnl": 168.00,
        "status": "CLOSED",
        "is_what_if": False
    },
    {
        "timestamp": "2026-06-06T07:42:00+02:00",
        "symbol": "ETHUSDT",
        "direction": "SELL",
        "agent_used": "thor_pro",
        "reasoning": "Dual-momentum crossover on 4h timeframe. Volume profile supports correction.",
        "entry_price": 3348.00,
        "close_price": 3260.00,
        "realized_pnl": 96.00,
        "status": "CLOSED",
        "is_what_if": False
    },
    {
        "timestamp": "2026-06-06T04:18:00+02:00",
        "symbol": "XAU_USD",
        "direction": "BUY",
        "agent_used": "odin_pro",
        "reasoning": "Macro risk hedges and gold correlation confirmation.",
        "entry_price": 2298.00,
        "close_price": 2312.00,
        "realized_pnl": 42.00,
        "status": "CLOSED",
        "is_what_if": False
    },
    {
        "timestamp": "2026-06-05T22:55:00+02:00",
        "symbol": "BTCUSDT",
        "direction": "SELL",
        "agent_used": "loki_pro",
        "reasoning": "Resistance zone rejection on high volume.",
        "entry_price": 68100.00,
        "close_price": 67280.00,
        "realized_pnl": 98.00,
        "status": "CLOSED",
        "is_what_if": False
    },
    {
        "timestamp": "2026-06-05T19:30:00+02:00",
        "symbol": "EUR_USD",
        "direction": "BUY",
        "agent_used": "manual",
        "reasoning": "Manual trade closed by user.",
        "entry_price": 1.0845,
        "close_price": 1.0812,
        "realized_pnl": -33.00,
        "status": "CLOSED",
        "is_what_if": False
    }
]

# Symbols & initial prices
symbols = ["BTCUSDT", "ETHUSDT", "EUR_USD", "XAU_USD"]
prices = {
    "BTCUSDT": 67420.50,
    "ETHUSDT": 3248.80,
    "EUR_USD": 1.0812,
    "XAU_USD": 2318.40
}

# WebSocket Clients
clients = set()

# --- Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    avatar_id: str

class ConfigUpdate(BaseModel):
    key: str
    value: str

class AlgorithmSettings(BaseModel):
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

class ManualTradeRequest(BaseModel):
    symbol: str
    direction: str  # BUY or SELL
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class WalletResetRequest(BaseModel):
    amount: float

# --- Authentication ---
@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    return {
        "access_token": f"mock_token_{form_data.username}",
        "token_type": "bearer"
    }

@app.get("/api/auth/me", response_model=UserResponse)
async def read_users_me():
    return UserResponse(
        id="default_user",
        username="admin",
        is_admin=True,
        avatar_id="avatar_1"
    )

# --- Config Routers ---
@app.get("/api/config")
async def get_all_config():
    return db_config

@app.post("/api/config")
async def update_config(update: ConfigUpdate):
    db_config[update.key] = update.value
    return {"status": "updated", "key": update.key, "value": update.value}

@app.post("/api/config/toggle-auto")
async def toggle_auto():
    current = db_config.get("auto_mode", "true").lower() == "true"
    new_val = "false" if current else "true"
    db_config["auto_mode"] = new_val
    return {"auto_mode": new_val == "true"}

@app.get("/api/config/algorithms")
async def get_algorithm_settings():
    return db_algo_settings

@app.post("/api/config/algorithms")
async def update_algorithm_settings(settings: AlgorithmSettings):
    global db_algo_settings
    db_algo_settings = settings.dict()
    return {"status": "success", "message": "Algorithm configuration saved successfully."}

@app.get("/api/config/agent/stats")
async def get_agent_stats():
    return {
        "loki_pro": {
            "name": "Loki Pro",
            "weights": {"rsi": 0.4, "macd": 0.3, "bollinger": 0.3},
            "total_trades": 48,
            "winrate": 74.2
        },
        "thor_pro": {
            "name": "Thor Pro",
            "weights": {"trend": 0.5, "sentiment": 0.3, "volume": 0.2},
            "total_trades": 31,
            "winrate": 71.0
        },
        "odin_pro": {
            "name": "Odin Pro",
            "weights": {"macro": 0.6, "value": 0.3, "cycles": 0.1},
            "total_trades": 19,
            "winrate": 68.9
        }
    }

@app.post("/api/config/algorithms/auto-allocation")
async def toggle_auto_allocation():
    db_algo_settings["auto_allocation"] = not db_algo_settings["auto_allocation"]
    return {"auto_allocation": db_algo_settings["auto_allocation"]}

@app.post("/api/config/wallet/reset")
async def reset_wallet(req: WalletResetRequest):
    global db_positions, db_portfolio, portfolio_offset
    # Force close open positions and convert to closed trades
    for pos in db_positions:
        pnl = (pos["currentPrice"] - pos["entryPrice"]) * pos["size"] * (1 if pos["side"] == "BUY" else -1)
        db_trades_history.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": pos["symbol"],
            "direction": pos["side"],
            "agent_used": "manual",
            "reasoning": "Force closed due to capital reset.",
            "entry_price": pos["entryPrice"],
            "close_price": pos["currentPrice"],
            "realized_pnl": round(pnl, 2),
            "status": "CLOSED",
            "is_what_if": False
        })
    db_positions = []
    portfolio_offset = 0.0
    db_portfolio["balance"] = req.amount
    db_portfolio["equity"] = req.amount
    db_portfolio["peak_equity"] = req.amount
    db_portfolio["drawdown"] = 0.0
    
    await broadcast_portfolio()
    return {"status": "ok", "message": f"Wallet reset to {req.amount} (open trades force-closed)."}

# --- Trading & Account Routers ---
@app.get("/api/account")
@app.get("/api/portfolio")
async def get_portfolio_endpoint():
    # Recalculate equity
    unrealized = sum((p["currentPrice"] - p["entryPrice"]) * p["size"] * (1 if p["side"] == "BUY" else -1) for p in db_positions)
    db_portfolio["equity"] = round(db_portfolio["balance"] + unrealized + portfolio_offset, 2)
    if db_portfolio["equity"] > db_portfolio["peak_equity"]:
        db_portfolio["peak_equity"] = db_portfolio["equity"]
    if db_portfolio["peak_equity"] > 0:
        db_portfolio["drawdown"] = round(((db_portfolio["peak_equity"] - db_portfolio["equity"]) / db_portfolio["peak_equity"]) * 100, 2)
    return db_portfolio

@app.get("/api/positions")
async def get_positions(status: str = "OPEN"):
    if status == "OPEN":
        return db_positions
    return [t for t in db_trades_history if t["status"] == status]

@app.post("/api/manual-trade")
async def manual_trade(req: ManualTradeRequest):
    if req.direction not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="Direction must be BUY or SELL")
        
    pos_id = f"pos_{random.randint(100000, 999999)}"
    new_pos = {
        "id": pos_id,
        "symbol": req.symbol,
        "side": req.direction,
        "size": req.quantity,
        "entryPrice": req.entry_price,
        "currentPrice": req.entry_price,
        "stop_loss": req.stop_loss,
        "take_profit": req.take_profit,
        "unrealizedPnl": 0.0,
        "opened_at": datetime.now(timezone.utc).isoformat()
    }
    db_positions.append(new_pos)
    await broadcast_portfolio()
    return {"position_id": pos_id, "status": "opened"}

@app.delete("/api/positions/{position_id}")
async def close_position(position_id: str):
    global db_positions, db_portfolio
    pos_idx = next((i for i, p in enumerate(db_positions) if p["id"] == position_id), None)
    if pos_idx is None:
        raise HTTPException(status_code=404, detail="Position not found")
        
    pos = db_positions.pop(pos_idx)
    pnl = (pos["currentPrice"] - pos["entryPrice"]) * pos["size"] * (1 if pos["side"] == "BUY" else -1)
    
    # Update balance
    db_portfolio["balance"] = round(db_portfolio["balance"] + pnl, 2)
    unrealized = sum((p["currentPrice"] - p["entryPrice"]) * p["size"] * (1 if p["side"] == "BUY" else -1) for p in db_positions)
    db_portfolio["equity"] = round(db_portfolio["balance"] + unrealized + portfolio_offset, 2)
    
    # Store in history
    db_trades_history.insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": pos["symbol"],
        "direction": pos["side"],
        "agent_used": "manual",
        "reasoning": "Manual trade closed by user.",
        "entry_price": pos["entryPrice"],
        "close_price": pos["currentPrice"],
        "realized_pnl": round(pnl, 2),
        "status": "CLOSED",
        "is_what_if": False
    })
    
    await broadcast_portfolio()
    return {"status": "closed", "pnl": round(pnl, 2)}

@app.get("/api/prediction-logs")
async def prediction_logs(symbol: Optional[str] = None, limit: int = 50):
    logs = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol or "BTCUSDT",
            "direction": "BUY",
            "agent_used": "loki_pro",
            "reasoning": "Gemini identifies highly bullish reversal zone.",
            "trade_executed": True
        }
    ]
    return logs[:limit]

@app.get("/api/correlations")
async def get_correlations():
    return {
        "XAU_USD": {"XAG_USD": 0.85, "EUR_USD": 0.40, "BTCUSDT": 0.30},
        "XAG_USD": {"XAU_USD": 0.85, "EUR_USD": 0.35, "BTCUSDT": 0.28},
        "EUR_USD": {"XAU_USD": 0.40, "XAG_USD": 0.35, "BTCUSDT": 0.20},
        "BTCUSDT": {"XAU_USD": 0.30, "AAPL": 0.25, "EUR_USD": 0.20},
        "AAPL": {"BTCUSDT": 0.25, "SPY": 0.78},
    }

# --- Stats Routers ---
@app.get("/api/stats/market/history")
async def get_market_history(symbol: str = Query(...), range_val: str = Query("1D", alias="range")):
    now = datetime.now(timezone.utc)
    limit = 50
    if range_val == "1H":
        delta = timedelta(minutes=1.2)
    elif range_val == "1D":
        delta = timedelta(minutes=30)
    elif range_val == "1W":
        delta = timedelta(hours=3)
    else:
        delta = timedelta(days=1)
        
    base_price = prices.get(symbol.upper(), 100.0)
    current_time = now - (delta * limit)
    current_price = base_price * 0.95
    
    # Check if we should use a deterministic wave for BTCUSDT to match the screenshot shape
    if symbol.upper() == "BTCUSDT":
        history = []
        target_p = prices["BTCUSDT"]
        base_p = 62200.0
        for i in range(limit):
            dt = current_time + delta * i
            if i == limit - 1:
                cl = target_p
            else:
                frac = i / (limit - 1)
                cl = base_p + (target_p - base_p) * frac + 1300 * math.sin(frac * 8) - 500 * math.sin(frac * 20)
            
            op = cl - 100.0 if i == 0 else history[-1]["close"]
            hi = max(op, cl) + random.uniform(50, 150)
            lo = min(op, cl) - random.uniform(50, 150)
            
            history.append({
                "time": dt.isoformat(),
                "open": round(op, 2),
                "high": round(hi, 2),
                "low": round(lo, 2),
                "close": round(cl, 2),
                "volume": round(random.uniform(500, 2000), 2)
            })
        return history
        
    history = []
    for _ in range(limit):
        ch = random.uniform(-0.015, 0.015) * current_price
        op = current_price
        cl = current_price + ch
        hi = max(op, cl) + random.uniform(0, 0.005) * current_price
        lo = min(op, cl) - random.uniform(0, 0.005) * current_price
        
        history.append({
            "time": current_time.isoformat(),
            "open": round(op, 5),
            "high": round(hi, 5),
            "low": round(lo, 5),
            "close": round(cl, 5),
            "volume": round(random.uniform(100, 10000), 2)
        })
        current_price = cl
        current_time += delta
        
    return history

@app.get("/api/stats/history")
async def get_stats_history(timeframe: Optional[str] = None, limit: int = 50):
    return db_trades_history[:limit]

@app.get("/api/stats/what_if")
async def get_what_if_stats(timeframe: str = "short", days: int = 30, symbol: str = "BTCUSDT"):
    base_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    output = {
        "price_history": [],
        "cumulative_pnl": {},
        "trades": {}
    }
    
    # Price curve
    current_price = prices.get(symbol.upper(), 100.0) * 0.9
    for i in range(days):
        dt = base_date + timedelta(days=i)
        current_price *= (1 + random.uniform(-0.03, 0.035))
        output["price_history"].append({
            "time": dt.isoformat(),
            "price": round(current_price, 2)
        })
        
    # Cumulative PNL comparison
    agents = ["loki_pro", "thor_pro", "odin_pro"]
    for agent in agents:
        pnl_series = []
        for i in range(days):
            dt = base_date + timedelta(days=i)
            # Generate deterministic smooth upward curves with minor variations to match screenshot
            frac = i / (days - 1)
            if agent == "loki_pro":
                # Loki Pro (blue line) ends highest (~142.30 cumulative)
                c_pnl = 5.0 + 137.30 * frac + 10.0 * math.sin(frac * 7)
            elif agent == "thor_pro":
                # Thor Pro (purple line) ends middle (~118.44 cumulative)
                c_pnl = 3.0 + 115.44 * frac + 8.0 * math.sin(frac * 6)
            else: # odin_pro
                # Odin Pro (gold line) ends lowest (~81.44 cumulative)
                c_pnl = 2.0 + 79.44 * frac + 5.0 * math.sin(frac * 5)
            pnl_series.append({
                "date": dt.strftime("%Y-%m-%d"),
                "pnl": round(c_pnl, 2)
            })
        output["cumulative_pnl"][agent] = pnl_series
        
    return output

@app.get("/api/stats/daily_contribution")
async def get_daily_contribution():
    return {
        "agents_pnl": {
            "loki_pro": 142.30,
            "thor_pro": 118.44,
            "odin_pro": 81.44
        },
        "agents_pct": {
            "loki_pro": 1.14,
            "thor_pro": 0.95,
            "odin_pro": 0.65
        },
        "total_pnl": 342.18,
        "total_pct": 2.74,
        "learning_blocked": False
    }

# --- WebSockets ---
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    # Immediately push initial portfolio update to register current positions
    try:
        unrealized = sum((p["currentPrice"] - p["entryPrice"]) * p["size"] * (1 if p["side"] == "BUY" else -1) for p in db_positions)
        db_portfolio["equity"] = round(db_portfolio["balance"] + unrealized + portfolio_offset, 2)
        initial_payload = {
            "type": "PORTFOLIO_UPDATE",
            "payload": {
                "balance": db_portfolio["balance"],
                "equity": db_portfolio["equity"],
                "positions": db_positions
            }
        }
        await websocket.send_text(json.dumps(initial_payload))
    except Exception:
        pass
        
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)

async def broadcast_portfolio():
    if not clients:
        return
    unrealized = sum((p["currentPrice"] - p["entryPrice"]) * p["size"] * (1 if p["side"] == "BUY" else -1) for p in db_positions)
    db_portfolio["equity"] = round(db_portfolio["balance"] + unrealized + portfolio_offset, 2)
    
    payload = {
        "type": "PORTFOLIO_UPDATE",
        "payload": {
            "balance": db_portfolio["balance"],
            "equity": db_portfolio["equity"],
            "positions": db_positions
        }
    }
    
    json_payload = json.dumps(payload)
    for c in list(clients):
        try:
            await c.send_text(json_payload)
        except Exception:
            clients.remove(c)

async def simulation_loop():
    while True:
        await asyncio.sleep(2)
        if not clients:
            continue
            
        # 1. Update prices with randomized ticks
        sym = random.choice(symbols)
        change_pct = random.uniform(-0.005, 0.005)
        prices[sym] = round(prices[sym] * (1 + change_pct), 5)
        
        # 2. Update active positions in-memory
        positions_changed = False
        for pos in db_positions:
            if pos["symbol"] == sym:
                pos["currentPrice"] = prices[sym]
                pos["unrealizedPnl"] = round((prices[sym] - pos["entryPrice"]) * pos["size"] * (1 if pos["side"] == "BUY" else -1), 2)
                positions_changed = True
                
                # Check Auto-SL / Auto-TP hits
                if pos["stop_loss"] is not None:
                    is_hit = (pos["side"] == "BUY" and prices[sym] <= pos["stop_loss"]) or (pos["side"] == "SELL" and prices[sym] >= pos["stop_loss"])
                    if is_hit:
                        # Close position immediately
                        db_positions.remove(pos)
                        db_portfolio["balance"] = round(db_portfolio["balance"] + pos["unrealizedPnl"], 2)
                        db_trades_history.insert(0, {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "symbol": pos["symbol"],
                            "direction": pos["side"],
                            "agent_used": "auto_stop_loss",
                            "reasoning": "Stop Loss triggered automatically.",
                            "entry_price": pos["entryPrice"],
                            "close_price": prices[sym],
                            "realized_pnl": pos["unrealizedPnl"],
                            "status": "CLOSED",
                            "is_what_if": False
                        })
                        positions_changed = True
                        break
                if pos["take_profit"] is not None:
                    is_hit = (pos["side"] == "BUY" and prices[sym] >= pos["take_profit"]) or (pos["side"] == "SELL" and prices[sym] <= pos["take_profit"])
                    if is_hit:
                        # Close position immediately
                        db_positions.remove(pos)
                        db_portfolio["balance"] = round(db_portfolio["balance"] + pos["unrealizedPnl"], 2)
                        db_trades_history.insert(0, {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "symbol": pos["symbol"],
                            "direction": pos["side"],
                            "agent_used": "auto_take_profit",
                            "reasoning": "Take Profit triggered automatically.",
                            "entry_price": pos["entryPrice"],
                            "close_price": prices[sym],
                            "realized_pnl": pos["unrealizedPnl"],
                            "status": "CLOSED",
                            "is_what_if": False
                        })
                        positions_changed = True
                        break

        # Broadcast portfolio updates on position price shifts
        if positions_changed:
            await broadcast_portfolio()
            
        # 3. Stream Tick message to clients
        tick_msg = {
            "type": "tick",
            "symbol": sym,
            "price": prices[sym],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # 4. Stream Prediction message to clients (25% chance per loop)
        if random.random() < 0.25:
            direction = "BUY" if random.random() > 0.5 else "SELL"
            reasonings = [
                "Technical correction complete. Gemini signals high volume entry breakout.",
                "RSI overbought state and dual-momentum cross confirms localized top.",
                "Macro gold correlation indicates impending asset hedge flows.",
                "Volatility spikes are cooling down. Reversal pattern confirmed."
            ]
            pred_msg = {
                "type": "prediction",
                "symbol": sym,
                "probability_up": random.uniform(0.1, 0.9),
                "probability_down": random.uniform(0.1, 0.9),
                "confidence_score": random.uniform(0.65, 0.98),
                "gemini_prob": random.uniform(-1, 1),
                "final_score": random.uniform(-1, 1),
                "direction": direction,
                "reasoning": random.choice(reasonings),
                "expected_volatility": random.uniform(0.005, 0.04),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Broadcast prediction
            json_pred = json.dumps(pred_msg)
            for c in list(clients):
                try:
                    await c.send_text(json_pred)
                except Exception:
                    clients.remove(c)
                    
        # Broadcast standard tick to clients
        json_tick = json.dumps(tick_msg)
        for c in list(clients):
            try:
                await c.send_text(json_tick)
            except Exception:
                clients.remove(c)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Dev Mock Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
