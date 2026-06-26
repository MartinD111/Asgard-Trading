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
from services.optimizer_core import DEFAULT_WEIGHTS
from services.risk_manager import RiskManager
from services.news_monitor import NewsMonitor
from services.signals import compute_signal, SELECTABLE_AGENTS, DEFAULT_AGENT as _DEFAULT_AGENT
from brokers.router import get_broker_for_user

logger = logging.getLogger(__name__)

# Base Score weights (dynamically adjusted per timeframe)
BASE_W_TECHNICAL = 0.40
BASE_W_GEMINI = 0.45
BASE_W_CORRELATION = 0.15

FINAL_SCORE_THRESHOLD = float(os.getenv("FINAL_SCORE_THRESHOLD", "0.85"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))

# Single continuous evaluation cadence. Trading is no longer time-restricted —
# the engine evaluates frequently and executes whenever a signal qualifies.
EVAL_INTERVAL = int(os.getenv("EVAL_INTERVAL", "60"))

# Selectable agents (one is active at a time, the rest run as what-if).
# Loki is split into three single-pillar variants: Math / Patterns / Trends.
AGENTS = list(SELECTABLE_AGENTS)
DEFAULT_AGENT = _DEFAULT_AGENT

ALL_SYMBOLS = ["EUR_USD", "XAU_USD", "XAG_USD", "BTCUSDT"]

# Simple correlation matrix (static, will be updated by GNN model later)
CORRELATION_MATRIX = {
    "XAU_USD": {"XAG_USD": 0.85, "EUR_USD": 0.40, "BTCUSDT": 0.30},
    "XAG_USD": {"XAU_USD": 0.85, "EUR_USD": 0.35, "BTCUSDT": 0.28},
    "EUR_USD": {"XAU_USD": 0.40, "XAG_USD": 0.35, "BTCUSDT": 0.20},
    "BTCUSDT": {"XAU_USD": 0.30},
}


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
        logger.info("DecisionEngine starting (single continuous engine)...")
        logger.info(f"Started continuous engine (Interval: {EVAL_INTERVAL}s)")
        while True:
            try:
                await self._cycle()
            except Exception as e:
                logger.error(f"DecisionEngine cycle error: {e}")
            await asyncio.sleep(EVAL_INTERVAL)

    async def _cycle(self):
        """Continuous analysis cycle over all symbols for the active agent."""
        # Hard execution gate (used to "freeze" real trading during simulation).
        # When disabled, the real engine does not analyse, broadcast or execute.
        if self.ws_channel == "real":
            raw_enabled = await self.redis.get("execution:real_enabled")
            if (raw_enabled or b"true").decode() != "true":
                return

        # 0. Check if the engine is enabled in frontend settings
        raw_config = await self.redis.get("config:engine_enabled")
        is_enabled = (raw_config or b"true").decode() == "true"

        if not is_enabled:
            logger.debug("Engine disabled by user. Skipping cycle.")
            return

        # Load global macro risk multiplier
        raw_macro = await self.redis.get("macro:risk_multiplier")
        global_risk = float(raw_macro or "1.0")

        # Which agent is live? The others are evaluated as what-if for comparison.
        raw_agent = await self.redis.get("config:active_agent")
        active_agent = (raw_agent or DEFAULT_AGENT.encode()).decode()
        if active_agent not in AGENTS:
            active_agent = DEFAULT_AGENT

        for symbol in ALL_SYMBOLS:
            await self._analyse_symbol(
                symbol=symbol,
                global_risk=global_risk,
                active_agent=active_agent,
            )

        # Cycle complete — engine is idle until the next evaluation tick.
        await self._broadcast_activity("", active_agent, "idle", "Engine idle — waiting for next evaluation")

    async def _broadcast_activity(self, symbol: str, agent: str, stage: str, detail: str):
        """Emit a live, granular view of what the engine is doing right now."""
        msg = {
            "type": "AGENT_ACTIVITY",
            "payload": {
                "symbol": symbol,
                "agent": agent,
                "stage": stage,
                "detail": detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        await self.ws_manager.broadcast(json.dumps(msg), channel=self.ws_channel)

    async def _analyse_symbol(
        self, symbol: str, global_risk: float, active_agent: str
    ):
        # 1. Get candles from Redis
        await self._broadcast_activity(symbol, active_agent, "fetching_candles", f"Loading {symbol} price candles")
        raw = await self.redis.get(f"candles:{symbol}")
        candles = json.loads(raw) if raw else []

        # 2. Get relevant news via RAG
        await self._broadcast_activity(symbol, active_agent, "analyzing_news", f"Scanning market news for {symbol}")
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
        await self._broadcast_activity(symbol, active_agent, "querying_gemini", f"Querying Gemini AI for {symbol} outlook")
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

        # 4–6. Compute signal + correlation, then evaluate each agent
        await self._broadcast_activity(symbol, active_agent, "evaluating_correlation", f"Evaluating cross-asset correlation for {symbol}")
        correlation_contribution = _calculate_correlation_boost(symbol, self._symbol_scores)

        await self._broadcast_activity(symbol, active_agent, "computing_score", f"Computing final BUY/SELL score for {symbol}")
        for strategy in AGENTS:
            is_what_if = strategy != active_agent

            # Odin reads dynamic weights from Redis (set by the weight optimizer).
            # Loki and Thor use the presets defined in signals.AGENT_WEIGHTS.
            weights: dict | None = None
            if strategy == "odin":
                raw_w = await self.redis.get("agent:weights:odin")
                weights = json.loads(raw_w) if raw_w else DEFAULT_WEIGHTS.copy()

            # compute_signal() is now the single source of truth for all agents:
            # RSI/MACD/ATR technical composite + pattern recognizer + Gemini blend.
            signal = compute_signal(
                candles,
                symbol=symbol,
                gemini_prob=prediction.gemini_prob,
                weights=weights,
                agent=strategy,
            )

            # Thor is a clean equal blend of the three pillars (computed in
            # compute_signal). Correlation is still logged for analytics but no
            # longer overrides the score.
            final_score = signal.final_score

            if not is_what_if:
                self._symbol_scores[symbol] = final_score
                # Annotate Gemini reasoning with any detected pattern for broadcast
                if signal.pattern_name != "None":
                    prediction.reasoning = (
                        f"[PATTERN: {signal.pattern_name} conf={abs(signal.pattern_score):.2f}] "
                        + prediction.reasoning
                    )

            direction = "BUY" if final_score > 0 else "SELL"

            # 7. Log prediction to DB
            log_id = await self._log_prediction(
                symbol, prediction,
                signal.technical_score, signal.pattern_score, correlation_contribution,
                final_score, strategy, is_what_if,
            )

            # 8. Push to WebSocket & Execute Trade
            payload = {
                "type": "prediction",
                "symbol": symbol,
                "agent": strategy,
                "probability_up": prediction.probability_up,
                "probability_down": prediction.probability_down,
                "confidence_score": prediction.confidence_score,
                "gemini_prob": prediction.gemini_prob,
                "final_score": final_score,
                "direction": direction,
                "reasoning": prediction.reasoning,
                "expected_volatility": prediction.expected_volatility,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detected_pattern": signal.pattern_name,
            }
            await self.ws_manager.broadcast(json.dumps(payload), channel=self.ws_channel)

            if not is_what_if:
                score_msg = {
                    "type": "AGENT_SCORE",
                    "payload": {
                        "symbol": symbol,
                        "agent": active_agent,
                        "final_score": final_score,
                        "direction": direction,
                        "confidence": signal.confidence,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }
                await self.ws_manager.broadcast(json.dumps(score_msg), channel=self.ws_channel)

                auto_mode = await self.redis.get("config:auto_mode")
                should_auto = (auto_mode or b"false").decode() == "true"

                if (
                    abs(final_score) > FINAL_SCORE_THRESHOLD
                    and signal.confidence > CONFIDENCE_THRESHOLD
                    and should_auto
                ):
                    await self._execute_trade(
                        symbol, direction, prediction, final_score, log_id, global_risk
                    )

            logger.info(
                f"[{symbol}] ({strategy}) final={final_score:.3f} gemini={prediction.gemini_prob:.3f} "
                f"tech={signal.technical_score:.3f} conf={signal.confidence:.3f} macro_risk={global_risk:.2f}"
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

    async def _get_active_user_ids(self) -> list[str]:
        """Return all user IDs that have a virtual account (eligible for trading)."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(text("SELECT user_id FROM virtual_accounts"))
            return [str(row[0]) for row in res.fetchall()]

    async def _audit(
        self,
        user_id: str | None,
        event_type: str,
        order_id: str | None = None,
        broker: str | None = None,
        symbol: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Write one row to the append-only audit_log. Never raises."""
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text(
                        "INSERT INTO audit_log "
                        "(user_id, event_type, order_id, broker, symbol, payload) "
                        "VALUES (:uid, :et, :oid, :broker, :sym, :payload::jsonb)"
                    ),
                    {
                        "uid":     user_id,
                        "et":      event_type,
                        "oid":     order_id,
                        "broker":  broker,
                        "sym":     symbol,
                        "payload": json.dumps(payload) if payload else None,
                    },
                )
                await db.commit()
        except Exception as exc:
            logger.error(f"Audit log write failed ({event_type}): {exc}")

    async def _execute_trade(
        self,
        symbol: str,
        direction: str,
        prediction,
        final_score: float,
        log_id: str,
        global_risk: float,
    ):
        """
        Executes a trade for every user with a virtual account.

        For each user the flow is:
          1. Per-user kill-switch check (skip if halted)
          2. Drawdown check — auto-halt and write DRAWDOWN_HALT on breach
          3. Route to the appropriate ExecutionBroker (Paper / OANDA / Coinbase)
          4. Write ORDER_INTENT to audit_log
          5. Call broker.place_order()
          6. On fill: insert position + orders row, write BROKER_RESPONSE
          7. On reject: write ORDER_REJECTED, skip position creation
        """
        user_ids = await self._get_active_user_ids()
        if not user_ids:
            return

        # Shared market data — fetched once for all users in this cycle
        price_raw = await self.redis.get(f"last_price:{symbol}")
        entry_price = float(price_raw or 1.0)
        atr = entry_price * 0.005
        stop_loss = self.risk.calculate_stop_loss(direction, entry_price, atr)
        take_profit = self.risk.calculate_take_profit(direction, entry_price, stop_loss)
        win_prob = prediction.probability_up if direction == "BUY" else prediction.probability_down

        first_pos_id: str | None = None
        first_qty: float = 0.0

        for uid in user_ids:
            # ── 1. Per-user kill switch ──────────────────────────────────────
            ks_raw = await self.redis.get(f"kill_switch:user:{uid}")
            if (ks_raw or b"false").decode() == "true":
                logger.info(f"Trade skipped for {symbol} (user {uid}) — kill switch active.")
                continue

            async with AsyncSessionLocal() as db:
                # ── 2. Equity + drawdown check ───────────────────────────────
                acc = await db.execute(
                    text("SELECT equity FROM virtual_accounts WHERE user_id = :uid"),
                    {"uid": uid},
                )
                row = acc.fetchone()
                if not row:
                    continue
                equity = float(row[0])

                if self.risk.check_drawdown(equity):
                    logger.warning(
                        f"Trade blocked for {symbol} (user {uid}) — max drawdown. Auto-halting."
                    )
                    await self.redis.set(f"kill_switch:user:{uid}", "true")
                    await self._audit(uid, "DRAWDOWN_HALT", symbol=symbol,
                                      payload={"equity": equity, "symbol": symbol})
                    continue

                qty = self.risk.position_size(
                    equity, entry_price, stop_loss, win_prob,
                    global_risk_multiplier=global_risk,
                )
                if qty <= 0:
                    continue
                kelly = self.risk.kelly_fraction(win_prob, global_risk_multiplier=global_risk)

                # ── 3. Select broker ─────────────────────────────────────────
                broker = await get_broker_for_user(uid, symbol, db, self.redis)
                broker_name = type(broker).__name__.replace("Broker", "").lower()

                # ── 4. Audit intent ──────────────────────────────────────────
                await self._audit(uid, "ORDER_INTENT", broker=broker_name, symbol=symbol,
                                  payload={"direction": direction, "quantity": qty,
                                           "entry_price": entry_price,
                                           "stop_loss": stop_loss, "take_profit": take_profit})

                # ── 5. Place order ───────────────────────────────────────────
                result = await broker.place_order(
                    symbol=symbol, side=direction, quantity=qty,
                    stop_loss=stop_loss, take_profit=take_profit,
                )

                if not result.ok:
                    await self._audit(uid, "ORDER_REJECTED", broker=broker_name, symbol=symbol,
                                      payload={"error": result.error, "status": result.status})
                    logger.warning(
                        f"Order rejected for user {uid} on {symbol} via {broker_name}: {result.error}"
                    )
                    continue

                # ── 6. Record fill ───────────────────────────────────────────
                fill_price = result.filled_price or entry_price
                fill_qty   = result.filled_qty   or qty

                pos_result = await db.execute(
                    text(
                        "INSERT INTO positions "
                        "(symbol, side, quantity, entry_price, current_price, stop_loss, take_profit, "
                        " final_score, kelly_fraction, status, user_id) "
                        "VALUES (:sym, :side, :qty, :ep, :ep, :sl, :tp, :fs, :k, 'OPEN', :uid) "
                        "RETURNING id"
                    ),
                    {
                        "sym": symbol, "side": direction, "qty": fill_qty, "ep": fill_price,
                        "sl": stop_loss, "tp": take_profit, "fs": final_score,
                        "k": kelly, "uid": uid,
                    },
                )
                pos_row = pos_result.fetchone()
                pos_id  = str(pos_row[0]) if pos_row else None

                ord_result = await db.execute(
                    text(
                        "INSERT INTO orders "
                        "(user_id, position_id, broker, broker_order_id, symbol, side, quantity, "
                        " requested_price, filled_price, filled_qty, status, stop_loss, take_profit) "
                        "VALUES (:uid, :pid, :broker, :bid, :sym, :side, :qty, "
                        "        :rp, :fp, :fq, :st, :sl, :tp) "
                        "RETURNING id"
                    ),
                    {
                        "uid": uid, "pid": pos_id, "broker": broker_name,
                        "bid": result.broker_order_id, "sym": symbol, "side": direction,
                        "qty": fill_qty, "rp": entry_price, "fp": fill_price,
                        "fq": fill_qty, "st": result.status, "sl": stop_loss, "tp": take_profit,
                    },
                )
                ord_row = ord_result.fetchone()
                ord_id  = str(ord_row[0]) if ord_row else None
                await db.commit()

                await self._audit(uid, "BROKER_RESPONSE", order_id=ord_id,
                                  broker=broker_name, symbol=symbol,
                                  payload={"broker_order_id": result.broker_order_id,
                                           "filled_price": fill_price,
                                           "filled_qty": fill_qty,
                                           "status": result.status})

                if pos_id and first_pos_id is None:
                    first_pos_id = pos_id
                    first_qty    = fill_qty

        # Link prediction log to the first created position
        if log_id and first_pos_id:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("UPDATE prediction_logs SET trade_executed=true, position_id=:pid WHERE id=:lid"),
                    {"pid": first_pos_id, "lid": log_id},
                )
                await db.commit()

        if first_pos_id:
            logger.info(
                f"[TRADE] {direction} {symbol} qty≈{first_qty:.4f} @ {entry_price:.5f} "
                f"SL={stop_loss:.5f} TP={take_profit:.5f} ({len(user_ids)} user(s))"
            )
            await self.ws_manager.broadcast(
                json.dumps({
                    "type":        "trade_executed",
                    "symbol":      symbol,
                    "direction":   direction,
                    "quantity":    first_qty,
                    "entry_price": entry_price,
                    "stop_loss":   stop_loss,
                    "take_profit": take_profit,
                    "position_id": first_pos_id,
                }),
                channel=self.ws_channel,
            )
