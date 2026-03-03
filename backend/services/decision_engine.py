"""
Decision Engine — runs every 5 minutes, computes Final_Score and fires trades.

Final_Score = (W_t × Technical) + (W_g × Gemini_Prob) + (W_c × Correlation)
Execute when |Final_Score| > 0.85 AND confidence > 0.70 AND mode = AUTO
"""
import os
import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import text

from db.database import AsyncSessionLocal
from services.gemini_predictor import GeminiPredictor
from services.risk_manager import RiskManager
from services.news_monitor import NewsMonitor
from services.pattern_recognizer import analyze_patterns

logger = logging.getLogger(__name__)

# Base Score weights (dynamically adjusted per timeframe)
BASE_W_TECHNICAL = 0.40
BASE_W_GEMINI = 0.45
BASE_W_CORRELATION = 0.15

FINAL_SCORE_THRESHOLD = float(os.getenv("FINAL_SCORE_THRESHOLD", "0.85"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
CYCLE_SECONDS = 300  # 5 minutes

ALL_SYMBOLS = ["EUR_USD", "XAU_USD", "XAG_USD", "AAPL", "BTCUSDT"]

# Simple correlation matrix (static, will be updated by GNN model later)
CORRELATION_MATRIX = {
    "XAU_USD": {"XAG_USD": 0.85, "EUR_USD": 0.40, "BTCUSDT": 0.30},
    "XAG_USD": {"XAU_USD": 0.85, "EUR_USD": 0.35, "BTCUSDT": 0.28},
    "EUR_USD": {"XAU_USD": 0.40, "XAG_USD": 0.35, "BTCUSDT": 0.20},
    "BTCUSDT": {"XAU_USD": 0.30, "AAPL": 0.25},
    "AAPL": {"BTCUSDT": 0.25},
}


def _calculate_technical_score(candles: list[dict]) -> float:
    """
    Simple technical score: combines RSI-like momentum and trend alignment.
    Returns value in [-1, +1].
    """
    if len(candles) < 14:
        return 0.0

    closes = [c["close"] for c in candles]
    # Momentum: last close vs 20-period SMA
    sma20 = sum(closes[-20:]) / min(20, len(closes))
    last = closes[-1]
    momentum = (last - sma20) / sma20

    # Volatility-normalise
    score = max(-1.0, min(1.0, momentum * 100))
    return score


def _calculate_correlation_boost(symbol: str, scores: dict[str, float]) -> float:
    """
    Checks if correlated assets agree on direction.
    Returns a confirmation multiplier in [-1, +1].
    """
    related = CORRELATION_MATRIX.get(symbol, {})
    if not related:
        return 0.0
    weighted_sum = 0.0
    weight_total = 0.0
    for rel_sym, corr in related.items():
        if rel_sym in scores:
            weighted_sum += scores[rel_sym] * corr
            weight_total += corr
    return weighted_sum / max(weight_total, 0.001)


class DecisionEngine:
    def __init__(
        self,
        predictor: GeminiPredictor,
        redis: aioredis.Redis,
        ws_manager,
        ws_channel: str = "real",
    ):
        self.predictor = predictor
        self.redis = redis
        self.ws_manager = ws_manager
        self.ws_channel = ws_channel
        self.risk = RiskManager()
        self.news = NewsMonitor()
        self._symbol_scores: dict[str, float] = {}

    async def run_loop(self):
        logger.info("DecisionEngine loops starting...")
        
        # Run three separate timeframe loops concurrently
        await asyncio.gather(
            self._timeframe_loop("short", 300),    # 5 minutes
            self._timeframe_loop("medium", 3600),  # 1 hour
            self._timeframe_loop("long", 86400),   # 24 hours
        )

    async def _timeframe_loop(self, timeframe: str, interval: int):
        logger.info(f"Started {timeframe.upper()} term engine (Interval: {interval}s)")
        while True:
            try:
                await self._cycle(timeframe)
            except Exception as e:
                logger.error(f"DecisionEngine cycle error ({timeframe}): {e}")
            await asyncio.sleep(interval)

    async def _cycle(self, timeframe: str):
        """Analysis cycle over all symbols, customized per timeframe."""
        # Hard execution gate (used to "freeze" real trading during simulation).
        # When disabled, the real engine does not analyse, broadcast or execute.
        if self.ws_channel == "real":
            raw_enabled = await self.redis.get("execution:real_enabled")
            if (raw_enabled or b"true").decode() != "true":
                return

        # 0. Check if timeframe is enabled in frontend settings
        raw_config = await self.redis.get(f"config:algo:{timeframe}_enabled")
        is_enabled = (raw_config or b"true").decode() == "true"
        
        if not is_enabled:
            logger.debug(f"[{timeframe.upper()}] Strategy disabled by user. Skipping cycle.")
            return
            
        # Get allocation percentage for this timeframe
        raw_alloc = await self.redis.get(f"config:algo:{timeframe}_allocation")
        allocation_pct = float(raw_alloc or "33.3") / 100.0

        # Load global macro risk multiplier
        raw_macro = await self.redis.get("macro:risk_multiplier")
        global_risk = float(raw_macro or "1.0")
        
        raw_strategy = await self.redis.get(f"config:algo:{timeframe}_strategy")
        active_strategy = (raw_strategy or b"math").decode()
        
        if timeframe == "short":
            timeframe_strategies = ["math", "patterns", "loki", "loki_pro"]
        elif timeframe == "medium":
            timeframe_strategies = ["math", "patterns", "thor", "thor_pro"]
        elif timeframe == "long":
            timeframe_strategies = ["math", "patterns", "odin", "odin_pro"]
        else:
            timeframe_strategies = ["math"]

        for symbol in ALL_SYMBOLS:
            await self._analyse_symbol(
                symbol=symbol, 
                timeframe=timeframe, 
                allocation_pct=allocation_pct, 
                global_risk=global_risk, 
                active_strategy=active_strategy,
                timeframe_strategies=timeframe_strategies
            )

    async def _analyse_symbol(
        self, symbol: str, timeframe: str, allocation_pct: float, 
        global_risk: float, active_strategy: str, timeframe_strategies: list[str]
    ):        # 1. Get candles from Redis
        raw = await self.redis.get(f"candles:{symbol}")
        candles = json.loads(raw) if raw else []

        # 2. Get relevant news via RAG
        news_items = self.news.query_relevant(symbol, n_results=10)
        
        # Broadcast news to GeminiHubView
        if news_items:
            news_msgs = [
                {"type": "NEWS_UPDATE", "payload": {"news": f"[{symbol}] {item}"}}
                for item in news_items[:3] # Send top 3 news to UI
            ]
            for msg in news_msgs:
                await self.ws_manager.broadcast(json.dumps(msg), channel=self.ws_channel)

        # 3. Gemini prediction
        prediction = await self.predictor.predict(symbol, candles, news_items)
        
        # Broadcast Gemini Chain of Thought to GeminiHubView
        if prediction.reasoning:
             gemini_msg = {
                 "type": "GEMINI_UPDATE",
                 "payload": {
                     "score": prediction.gemini_prob,
                     "probUp": prediction.probability_up,
                     "probDown": prediction.probability_down,
                     "confidence": prediction.confidence_score,
                     "reasoning": f"[{symbol}] {prediction.reasoning}"
                 }
             }
             await self.ws_manager.broadcast(json.dumps(gemini_msg), channel=self.ws_channel)

        # 4. Technical score
        tech_score = _calculate_technical_score(candles)

        # 5. Pattern Assessment (Base)
        pattern_data = analyze_patterns(candles)
        pattern_contribution = 0.0
        if pattern_data["pattern"] != "None":
            pat_dir_mult = 1.0 if pattern_data["direction"] == "BUY" else -1.0
            pattern_contribution = pattern_data["confidence"] * pat_dir_mult
                
            # Append pattern to Gemini reasoning for WebSocket
            prediction.reasoning = f"[PATTERN DETECTED: {pattern_data['pattern']} CONFIDENCE: {pattern_data['confidence']:.2f}] " + prediction.reasoning

        gemini_contribution = prediction.gemini_prob
        correlation_contribution = _calculate_correlation_boost(symbol, self._symbol_scores)

        # 6. Evaluate all timeframe strategies
        for strategy in timeframe_strategies:
            is_what_if = strategy != active_strategy
            
            w_tech, w_gem, w_corr, w_pat = 0.0, 0.0, 0.0, 0.0
            
            if strategy == "math":
                if timeframe == "short":
                    w_tech, w_gem, w_corr, w_pat = 0.70, 0.20, 0.10, 0.0
                elif timeframe == "medium":
                    w_tech, w_gem, w_corr, w_pat = 0.30, 0.60, 0.10, 0.0
                else:
                    w_tech, w_gem, w_corr, w_pat = 0.20, 0.30, 0.50, 0.0
            elif strategy == "patterns":
                w_tech, w_gem, w_corr, w_pat = 0.0, 0.0, 0.0, 1.0
            elif strategy in ["loki", "thor", "odin"]:
                w_tech, w_gem, w_corr, w_pat = 0.40, 0.20, 0.0, 0.40
            elif strategy.endswith("_pro"):
                key = f"agent:weights:{strategy}"
                data = await self.redis.get(key)
                if data:
                    dyn_weights = json.loads(data)
                else:
                    from services.weight_optimizer import DEFAULT_WEIGHTS
                    dyn_weights = DEFAULT_WEIGHTS
                    
                w_tech = dyn_weights.get("math", 0.33)
                w_gem = dyn_weights.get("gemini", 0.34)
                w_pat = dyn_weights.get("pattern", 0.33)
                w_corr = 0.0
            
            final_score = (
                w_tech * tech_score
                + w_gem * gemini_contribution
                + w_pat * pattern_contribution
                + w_corr * correlation_contribution
            )
            
            if not is_what_if:
                self._symbol_scores[symbol] = final_score

            direction = "BUY" if final_score > 0 else "SELL"

            # 7. Log prediction to DB
            log_id = await self._log_prediction(
                symbol, prediction, tech_score, pattern_contribution, correlation_contribution, final_score, strategy, is_what_if
            )

            # 8. Push to WebSocket & Execute Trade (Only for active strategy)
            if not is_what_if:
                payload = {
                    "type": "prediction",
                    "symbol": symbol,
                    "probability_up": prediction.probability_up,
                    "probability_down": prediction.probability_down,
                    "confidence_score": prediction.confidence_score,
                    "gemini_prob": prediction.gemini_prob,
                    "final_score": final_score,
                    "direction": direction,
                    "reasoning": prediction.reasoning,
                    "expected_volatility": prediction.expected_volatility,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detected_pattern": pattern_data["pattern"],
                }
                await self.ws_manager.broadcast(json.dumps(payload), channel=self.ws_channel)

                # Check execution conditions
                auto_mode = await self.redis.get("config:auto_mode")
                should_auto = (auto_mode or b"false").decode() == "true"

                if (
                    abs(final_score) > FINAL_SCORE_THRESHOLD
                    and prediction.confidence_score > CONFIDENCE_THRESHOLD
                    and should_auto
                ):
                    await self._execute_paper_trade(
                        symbol, direction, prediction, final_score, log_id, allocation_pct, global_risk, timeframe
                    )

                logger.info(
                    f"[{timeframe.upper()}] [{symbol}] ({strategy}) final={final_score:.3f} gemini={prediction.gemini_prob:.3f} "
                    f"tech={tech_score:.3f} conf={prediction.confidence_score:.3f} macro_risk={global_risk:.2f}"
                )

    async def _log_prediction(
        self, symbol, prediction, tech_score, pat_score, corr_score, final_score, agent_used, is_what_if
    ) -> str:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    """INSERT INTO prediction_logs
                    (symbol, probability_up, probability_down, confidence_score,
                     expected_volatility, gemini_prob, technical_score, pattern_score, correlation_score,
                     final_score, direction, agent_used, reasoning, is_what_if)
                    VALUES (:sym, :pu, :pd, :conf, :vol, :gp, :ts, :ps, :cs, :fs, :dir, :agent, :reason, :whatif)
                    RETURNING id"""
                ),
                {
                    "sym": symbol,
                    "pu": prediction.probability_up,
                    "pd": prediction.probability_down,
                    "conf": prediction.confidence_score,
                    "vol": prediction.expected_volatility,
                    "gp": prediction.gemini_prob,
                    "ts": tech_score,
                    "ps": pat_score,
                    "cs": corr_score,
                    "fs": final_score,
                    "dir": "BUY" if final_score > 0 else "SELL",
                    "agent": agent_used,
                    "reason": prediction.reasoning,
                    "whatif": is_what_if
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else ""

    async def _execute_paper_trade(
        self, symbol: str, direction: str, prediction, final_score: float, log_id: str,
        allocation_pct: float, global_risk: float, timeframe: str
    ):
        """Simulates a trade in the virtual wallet."""
        async with AsyncSessionLocal() as db:
            # Get equity
            acc = await db.execute(
                text("SELECT equity FROM virtual_accounts WHERE user_id='default'")
            )
            row = acc.fetchone()
            if not row:
                return
            equity = float(row[0])

            # Drawdown check
            if self.risk.check_drawdown(equity):
                logger.warning(f"Trade blocked for {symbol} — max drawdown reached.")
                return

            # Pricing
            price_raw = await self.redis.get(f"last_price:{symbol}")
            entry_price = float(price_raw or 1.0)

            # ATR placeholder (use 0.5% of price)
            atr = entry_price * 0.005
            stop_loss = self.risk.calculate_stop_loss(direction, entry_price, atr)
            take_profit = self.risk.calculate_take_profit(direction, entry_price, stop_loss)

            win_prob = prediction.probability_up if direction == "BUY" else prediction.probability_down
            
            # Apply frontend strategy allocation limit to usable equity
            usable_equity = equity * allocation_pct
            
            # Pass the global_risk multiplier to the risk manager
            qty = self.risk.position_size(usable_equity, entry_price, stop_loss, win_prob, global_risk_multiplier=global_risk)

            if qty <= 0:
                return

            kelly = self.risk.kelly_fraction(win_prob, global_risk_multiplier=global_risk)

            # Insert position
            pos_result = await db.execute(
                text(
                    """INSERT INTO positions
                    (symbol, side, quantity, entry_price, current_price, stop_loss, take_profit,
                     final_score, kelly_fraction, status)
                    VALUES (:sym, :side, :qty, :ep, :ep, :sl, :tp, :fs, :k, 'OPEN')
                    RETURNING id"""
                ),
                {
                    "sym": symbol,
                    "side": direction,
                    "qty": qty,
                    "ep": entry_price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "fs": final_score,
                    "k": kelly,
                },
            )
            pos_row = pos_result.fetchone()
            pos_id = str(pos_row[0]) if pos_row else None

            # Update prediction log
            if log_id and pos_id:
                await db.execute(
                    text(
                        "UPDATE prediction_logs SET trade_executed=true, position_id=:pid WHERE id=:lid"
                    ),
                    {"pid": pos_id, "lid": log_id},
                )

        logger.info(
            f"[PAPER TRADE] {direction} {symbol} qty={qty:.4f} @ {entry_price:.5f} "
            f"SL={stop_loss:.5f} TP={take_profit:.5f}"
        )
        trade_msg = json.dumps({
            "type": "trade_executed",
            "symbol": symbol,
            "direction": direction,
            "quantity": qty,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_id": pos_id,
        })
        await self.ws_manager.broadcast(trade_msg, channel=self.ws_channel)
