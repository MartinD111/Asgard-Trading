"""
Macro Risk Analyzer — Evaluates global news context using Gemini to
determine the overall market regime and risk appetite.
Produces a 'Global Risk Multiplier' stored in Redis.
"""
import os
import sys
import json
import time
import asyncio
import logging
import google.generativeai as genai
import redis.asyncio as aioredis

from services.news_monitor import NewsMonitor

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Chief Risk Officer for a quantitative hedge fund.
Analyze the provided global macro news headlines and determine the current Market Risk Regime, as well as the optimal allocation of funds across short, medium, and long-term trading strategies.
You MUST respond with ONLY a valid JSON object — strictly no markdown formatting.

Required JSON schema:
{
  "regime": "<'Risk-On' | 'Risk-Off' | 'Neutral' | 'High-Volatility-Panic'>",
  "risk_multiplier": <float 0.1 to 1.5>,
  "expected_global_volatility": <float, expected percentage swing>,
  "reasoning": "<Short explanation of why the market is in this regime>",
  "recommended_allocations": {
    "short_term": <integer percentage, e.g. 40>,
    "medium_term": <integer percentage, e.g. 40>,
    "long_term": <integer percentage, e.g. 20>
  }
}

The sum of recommended_allocations must always equal exactly 100.

Multiplier Guidelines:
- Risk-On: 1.0 to 1.5 (Expand position sizes, market is stable/growing)
- Neutral: 0.8 to 1.0 (Standard sizing)
- Risk-Off: 0.3 to 0.7 (Shrink positions, protect capital, fear in market)
- High-Volatility-Panic: 0.1 to 0.2 (Extreme caution, drastically reduce sizing)
"""

class MacroRiskAnalyzer:
    def __init__(self, redis_url: str = "redis://redis:6379", ws_manager=None):
        self.ws_manager = ws_manager
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
            
        self.model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            system_instruction=SYSTEM_PROMPT,
        )
        self.generation_config = genai.GenerationConfig(
            temperature=0.1,  # Keep reasoning highly deterministic
            response_mime_type="application/json",
        )
        self.news = NewsMonitor()
        try:
            self.redis = aioredis.from_url(redis_url)
        except Exception:
            self.redis = None # Allow fallback for local testing without redis

    async def analyze_global_risk(self) -> dict:
        """Fetches latest broad news and asks Gemini for the risk multiplier."""
        logger.info("Starting Global Macro Risk Analysis cycle.")
        
        # 1. Get broader news context (using a broad query)
        headlines = self.news.query_relevant("economy inflation fed interest rates geopolitics market crash rally", n_results=30)
        
        if not headlines:
            logger.warning("No news available for Macro Analysis. Defaulting to Neutral.")
            return self._default_risk_profile()

        news_str = "\n".join(f"- {h}" for h in headlines)
        prompt = f"### Recent Global Headlines:\n{news_str}\n\nDetermine the Global Risk Multiplier."

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=self.generation_config,
            )
            data = json.loads(response.text)
            
            regime = data.get("regime", "Neutral")
            multiplier = float(data.get("risk_multiplier", 1.0))
            volatility = float(data.get("expected_global_volatility", 1.0))
            reasoning = data.get("reasoning", "")
            allocations = data.get("recommended_allocations", {"short_term": 40, "medium_term": 40, "long_term": 20})

            # Ensure safe bounds
            multiplier = max(0.1, min(1.5, multiplier))

            result = {
                "regime": regime,
                "risk_multiplier": multiplier,
                "expected_global_volatility": volatility,
                "reasoning": reasoning,
                "recommended_allocations": allocations,
                "timestamp": time.time()
            }
            
            logger.info(f"Macro Risk Result: Regime={regime}, Multiplier={multiplier:.2f}, Auto-Allocations={allocations}")
            
            if self.redis:
                await self.redis.set("macro:risk_profile", json.dumps(result))
                # Expose specific values for fast access
                await self.redis.set("macro:risk_multiplier", str(multiplier))
                await self.redis.set("macro:expected_volatility", str(volatility))
                
                # Check if auto allocation is enabled
                auto_alloc_raw = await self.redis.get("config:algo:auto_allocation")
                if auto_alloc_raw and auto_alloc_raw.decode() == "true":
                    logger.info("Applying Gemini AI Auto-Allocations to algorithms")
                    await self.redis.set("config:algo:short_allocation", str(allocations.get("short_term", 40)))
                    await self.redis.set("config:algo:medium_allocation", str(allocations.get("medium_term", 40)))
                    await self.redis.set("config:algo:long_allocation", str(allocations.get("long_term", 20)))
                    
                    # Notify frontend about allocation changes
                    if self.ws_manager:
                        alloc_msg = {
                            "type": "ALLOCATION_UPDATE",
                            "payload": {
                                "short": allocations.get("short_term", 40),
                                "medium": allocations.get("medium_term", 40),
                                "long": allocations.get("long_term", 20)
                            }
                        }
                        await self.ws_manager.broadcast(json.dumps(alloc_msg))
                
            if self.ws_manager:
                gemini_msg = {
                    "type": "GEMINI_UPDATE",
                    "payload": {
                        "score": 0.0, # Neutral score relative to an asset for macro
                        "probUp": 0.5,
                        "probDown": 0.5,
                        "confidence": 0.9,
                        "reasoning": f"[GLOBAL MACRO - {regime}] {reasoning} (Risk Multiplier: {multiplier}x)"
                    }
                }
                await self.ws_manager.broadcast(json.dumps(gemini_msg))
                
            return result

        except Exception as e:
            logger.error(f"Failed to generate Macro Risk analysis: {e}")
            return self._default_risk_profile()

    def _default_risk_profile(self) -> dict:
        return {
            "regime": "Neutral",
            "risk_multiplier": 1.0,
            "expected_global_volatility": 1.0,
            "reasoning": "Fallback to neutral due to system constraints or lack of data.",
            "timestamp": time.time()
        }

    async def run_loop(self, interval: int = 3600):
        """Async loop — updates global risk profile every hour."""
        while True:
            try:
                await self.analyze_global_risk()
            except Exception as e:
                logger.error(f"MacroRiskAnalyzer loop error: {e}")
            await asyncio.sleep(interval)


if __name__ == "__main__" or (len(sys.argv) > 1 and "--standalone" in sys.argv):
    analyzer = MacroRiskAnalyzer(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"))
    asyncio.run(analyzer.run_loop())
