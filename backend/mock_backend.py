import asyncio
import json
import random
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    avatar_id: str

# --- Mock Auth Endpoints ---
@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Allow admin:admin or any login for development purposes
    if form_data.username == "admin" and form_data.password == "admin":
        return {
            "access_token": "mock_token_admin",
            "token_type": "bearer"
        }
    else:
        # In mock mode, let's allow anything but check for admin/admin specifically if user wants it
        return {
            "access_token": f"mock_token_{form_data.username}",
            "token_type": "bearer"
        }

@app.get("/api/auth/me", response_model=UserResponse)
async def read_users_me():
    return UserResponse(
        id="123",
        username="admin",
        is_admin=True,
        avatar_id="avatar_1"
    )

# --- WebSocket Logic ---
clients = set()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)

async def simulation_loop():
    symbols = ["EUR_USD", "XAU_USD", "AAPL", "BTCUSDT"]
    prices = {s: 100.0 for s in symbols}
    
    while True:
        await asyncio.sleep(2)
        if not clients:
            continue
            
        # 1. Market Tick
        sym = random.choice(symbols)
        prices[sym] += random.uniform(-0.1, 0.1)
        tick = {
            "type": "tick",
            "symbol": sym,
            "price": round(prices[sym], 5),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Random Prediction
        if random.random() < 0.3:
            msg = {
                "type": "prediction",
                "symbol": sym,
                "probability_up": random.uniform(0.1, 0.9),
                "probability_down": random.uniform(0.1, 0.9),
                "confidence_score": random.uniform(0.5, 0.95),
                "gemini_prob": random.uniform(-1, 1),
                "final_score": random.uniform(-1, 1),
                "direction": "BUY" if random.random() > 0.5 else "SELL",
                "reasoning": "Mock: Analysis indicates market trend continuation based on RSI and Volume.",
                "expected_volatility": random.uniform(0, 0.02),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            msg = tick
            
        json_msg = json.dumps(msg)
        for c in list(clients):
            try:
                await c.send_text(json_msg)
            except Exception:
                clients.remove(c)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

if __name__ == "__main__":
    import uvicorn
    print("Starting MOCK Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
