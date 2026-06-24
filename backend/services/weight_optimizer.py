"""
Heuristic weight optimizer for 'Odin' — the self-tuning agent.

Evaluates closed trades and nudges per-component weights toward components
that correctly predicted the outcome, away from those that didn't.

Score conventions (all components in [-1, +1]):
  tech      technical composite (RSI/MACD/ATR)
  pattern   pattern-recognizer contribution
  gemini    Gemini LLM directional probability, remapped to [-1, +1]

Agreement logic: for a BUY trade, a positive score means the component
agreed with the entry; for a SELL, a negative score means agreement.
The optimizer rewards agreement on wins, disagreement on losses.
"""
import asyncio
import json
import logging
from sqlalchemy import text
from db.database import AsyncSessionLocal
import redis.asyncio as aioredis

from services.optimizer_core import (
    apply_reward, DEFAULT_WEIGHTS, LEARNING_RATE,
    MAX_WEIGHT, MIN_WEIGHT, AGREEMENT_THRESHOLD,
)

logger = logging.getLogger(__name__)


class AgentOptimizer:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._running = False

    async def get_agent_weights(self, agent_name: str) -> dict:
        """Fetch current dynamic weights for an agent from Redis."""
        key = f"agent:weights:{agent_name}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        
        # Initialize if not present
        await self.redis.set(key, json.dumps(DEFAULT_WEIGHTS))
        return DEFAULT_WEIGHTS

    async def _save_agent_weights(self, agent_name: str, weights: dict):
        """Save normalized weights back to Redis."""
        # Normalize weights so they sum to 1.0 (or close to it)
        total = sum(weights.values())
        if total > 0:
            normalized = {k: round(v / total, 4) for k, v in weights.items()}
        else:
            normalized = DEFAULT_WEIGHTS.copy()
            
        await self.redis.set(f"agent:weights:{agent_name}", json.dumps(normalized))
        logger.info(f"Updated weights for {agent_name}: {normalized}")

    async def evaluate_past_predictions(self):
        """
        Analyzes closed trades or expired predictions to reward/punish internal model weights.
        Realistically this matches prediction_logs against market movement.
        For this simulation, we analyze closed positions tied to predictions.
        """
        async with AsyncSessionLocal() as db:
            from datetime import datetime, timezone
            # 1. First calculate total daily contribution to see if learning should be blocked.
            # Use total platform equity as the denominator so the threshold scales with user count.
            acc = await db.execute(text("SELECT COALESCE(SUM(equity), 100000.0) FROM virtual_accounts"))
            row = acc.fetchone()
            equity = float(row[0]) if row else 100000.0

            today = datetime.now(timezone.utc).date()
            pnl_query = text("""
                SELECT SUM(p.realized_pnl)
                FROM prediction_logs pl
                JOIN positions p ON pl.position_id = p.id
                WHERE p.status = 'CLOSED'
                  AND pl.agent_used = 'odin'
                  AND DATE(p.closed_at) = :today
            """)
            res = await db.execute(pnl_query, {"today": today})
            r = res.fetchone()
            total_pnl = float(r[0]) if r and r[0] else 0.0
            
            total_pct = (total_pnl / equity) * 100 if equity > 0 else 0.0
            
            # Check active blocked status
            blocked_raw = await self.redis.get("algo:learning_blocked")
            is_blocked = (blocked_raw and blocked_raw.decode() == "true")
            
            if total_pct >= 1.0 and not is_blocked:
                await self.redis.set("algo:learning_blocked", "true")
                logger.info(f"Odin daily contribution reached {total_pct:.2f}%. Learning BLOCKED.")
                is_blocked = True
            elif total_pct <= 0.5 and is_blocked:
                await self.redis.set("algo:learning_blocked", "false")
                logger.info(f"Odin daily contribution dropped to {total_pct:.2f}%. Learning RESUMED.")
                is_blocked = False

            # 2. Find recent CLOSED Odin positions with an associated prediction log
            query = text("""
                SELECT
                    pl.id, pl.agent_used, pl.direction, pl.technical_score,
                    pl.pattern_score, pl.gemini_prob,
                    p.entry_price, p.close_price, p.side, p.realized_pnl
                FROM prediction_logs pl
                JOIN positions p ON pl.position_id = p.id
                WHERE p.status = 'CLOSED'
                  AND pl.agent_used = 'odin'
                  AND pl.outcome IS NULL -- Mark outcome so we don't double count
                ORDER BY p.closed_at ASC LIMIT 50
            """)
            result = await db.execute(query)
            closed_trades = result.fetchall()

            if not closed_trades:
                return

            # Group evaluations by agent to batch update
            agent_updates = {}

            for trade in closed_trades:
                (log_id, agent, direction, tech_s, pat_s, gem_s, 
                 entry_p, close_p, side, pnl) = trade
                
                if agent not in agent_updates:
                    agent_updates[agent] = await self.get_agent_weights(agent)
                
                weights = agent_updates[agent]

                is_win = float(pnl) > 0

                # gemini_prob stored as raw [0,1] probability; remap to [-1,+1]
                raw_gem = float(gem_s) if gem_s is not None else 0.0
                scores = {
                    "tech":    float(tech_s) if tech_s is not None else 0.0,
                    "pattern": float(pat_s)  if pat_s  is not None else 0.0,
                    "gemini":  (raw_gem - 0.5) * 2,
                }

                if not is_blocked:
                    apply_reward(weights, scores, str(side), is_win)

                # Mark log as evaluated (mock outcome)
                outcome_str = 'WIN' if is_win else 'LOSS'
                if is_blocked:
                    outcome_str += '_SKIPPED_LEARNING'
                await db.execute(
                    text("UPDATE prediction_logs SET outcome = :o WHERE id = :id"),
                    {"o": outcome_str, "id": log_id}
                )
            
            await db.commit()
            
            # Save updated weights back
            for agent, new_weights in agent_updates.items():
                await self._save_agent_weights(agent, new_weights)

    async def run_loop(self):
        """Background process to continuously optimize active agents."""
        self._running = True
        logger.info("Agent Weight Optimizer Engine Started.")
        while self._running:
            try:
                await self.evaluate_past_predictions()
            except Exception as e:
                logger.error(f"Error in AgentOptimizer: {e}")
            
            # Run evaluation every 60 seconds
            await asyncio.sleep(60)

    def stop(self):
        self._running = False
