"""
Reinforcement Learning Weight Optimizer for 'Loki_Pro', 'Thor_Pro', 'Odin_Pro'.
Periodically evaluates past trades and adjusts algorithm component weights to maximize win rate.
"""
import asyncio
import json
import logging
from sqlalchemy import text
from db.database import AsyncSessionLocal
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Default starting weights for the self-optimizing agents
DEFAULT_WEIGHTS = {
    "math": 0.33,
    "pattern": 0.33,
    "gemini": 0.34
}

LEARNING_RATE = 0.02  # How aggressively the agent shifts weights per evaluation
MAX_WEIGHT = 0.70     # Cap to avoid relying 100% on one component
MIN_WEIGHT = 0.05     # Floor to ensure components are never fully ignored

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
            # 1. First calculate total daily contribution to see if learning should be blocked
            acc = await db.execute(text("SELECT equity FROM virtual_accounts WHERE user_id='default'"))
            row = acc.fetchone()
            equity = float(row[0]) if row else 100000.0

            today = datetime.now(timezone.utc).date()
            pnl_query = text("""
                SELECT SUM(p.realized_pnl)
                FROM prediction_logs pl
                JOIN positions p ON pl.position_id = p.id
                WHERE p.status = 'CLOSED' 
                  AND pl.agent_used LIKE '%_pro'
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
                logger.info(f"Asgard Pro daily contribution reached {total_pct:.2f}%. Learning BLOCKED.")
                is_blocked = True
            elif total_pct <= 0.5 and is_blocked:
                await self.redis.set("algo:learning_blocked", "false")
                logger.info(f"Asgard Pro daily contribution dropped to {total_pct:.2f}%. Learning RESUMED.")
                is_blocked = False

            # 2. Find recent CLOSED positions that have an associated prediction log and an agent_used like '%+'
            query = text("""
                SELECT 
                    pl.id, pl.agent_used, pl.direction, pl.technical_score, 
                    pl.pattern_score, pl.gemini_prob,
                    p.entry_price, p.close_price, p.side, p.realized_pnl
                FROM prediction_logs pl
                JOIN positions p ON pl.position_id = p.id
                WHERE p.status = 'CLOSED' 
                  AND pl.agent_used LIKE '%%_pro'
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

                # Determine trade success based on Realized PNL
                is_win = float(pnl) > 0
                
                # Normalize component scores for fair comparison (assuming they are 0.0 to 1.0)
                scores = {
                    "math": float(tech_s) if tech_s else 0.5,
                    "pattern": float(pat_s) if pat_s else 0.5,
                    "gemini": float(gem_s) if gem_s else 0.5
                }
                
                # Identify which components contributed significantly to the decision
                # If component score > 0.6, it pushed for the trade. If < 0.4, it pushed against.
                
                for component, score in scores.items():
                    # Simplified RL reward logic:
                    # Only apply weight updates if we are NOT blocked from learning
                    if not is_blocked:
                        if is_win:
                            if score > 0.6: 
                                weights[component] += LEARNING_RATE # Reward
                            elif score < 0.4:
                                weights[component] -= LEARNING_RATE # Punish (it doubted a winning trade)
                        else:
                            if score > 0.6:
                                weights[component] -= LEARNING_RATE # Punish (it pushed a losing trade)
                            elif score < 0.4:
                                weights[component] += LEARNING_RATE # Reward (it correctly doubted a losing trade)
                                
                        # Clamp weights
                        weights[component] = max(MIN_WEIGHT, min(MAX_WEIGHT, weights[component]))

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
