import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        prices[sym] += random.uniform(-0.5, 0.5)
        tick = {
            "type": "tick",
            "symbol": sym,
            "price": prices[sym],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # 2. Prediction (every 5 seconds roughly)
        if random.random() < 0.4:
            pred = {
                "type": "prediction",
                "symbol": sym,
                "probability_up": random.uniform(0.1, 0.9),
                "probability_down": random.uniform(0.1, 0.9),
                "confidence_score": random.uniform(0.5, 0.95),
                "gemini_prob": random.uniform(-1, 1),
                "final_score": random.uniform(-1, 1),
                "direction": "BUY" if random.random() > 0.5 else "SELL",
                "reasoning": "Market sentiment implies high volatility. AI confirms trend.",
                "expected_volatility": random.uniform(0, 0.05),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            tick = pred # just send pred instead
            
        msg = json.dumps(tick)
        for c in list(clients):
            try:
                await c.send_text(msg)
            except Exception:
                clients.remove(c)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
