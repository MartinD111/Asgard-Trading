import os
import json
import logging
import asyncio
import time
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from sqlalchemy import text

# Import db session securely
from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Global rate limiter to ensure we do not exceed 1500 requests per 24 hours.
# 24 hours = 86400 seconds. 86400 / 1500 = 57.6 seconds per request.
# We use 58.0 seconds to be safe. This creates a perfectly spaced "always-on" prediction queue.
class RateLimiter:
    def __init__(self, interval_seconds: float):
        self.interval = interval_seconds
        self.last_call = 0.0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self.last_call = time.time()

global_gemini_limiter = RateLimiter(58.0)

SYSTEM_PROMPT = """You are an expert quantitative analyst and market predictor.
You will receive a market context window containing OHLCV data, recent news headlines, and macro indicators.
You MUST respond with ONLY a valid JSON object — no markdown, no explanation outside the JSON.

Required JSON schema:
{
  "probability_up": <float 0.0-1.0>,
  "probability_down": <float 0.0-1.0>,
  "confidence_score": <float 0.0-1.0>,
  "expected_volatility": <float, percentage>,
  "reasoning": "<Chain-of-Thought explanation, max 300 words>"
}

Rules:
- probability_up + probability_down must equal 1.0
- confidence_score reflects how certain you are given data quality and market clarity
- expected_volatility is the predicted % price swing in the next 4 hours
- reasoning must reference specific candle patterns, news events, or macro factors
"""


@dataclass
class GeminiPrediction:
    probability_up: float
    probability_down: float
    confidence_score: float
    expected_volatility: float
    reasoning: str
    gemini_prob: float  # = (prob_up - prob_down) * confidence


class GeminiPredictor:
    def __init__(self):
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.generation_config = genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=1024,
            response_mime_type="application/json",
        )

    def _build_context(
        self,
        symbol: str,
        candles: list[dict],
        news_items: list[str],
        macro: dict | None = None,
    ) -> str:
        candle_str = "\n".join(
            f"  {c['time']} O:{c['open']:.5f} H:{c['high']:.5f} L:{c['low']:.5f} C:{c['close']:.5f} V:{c.get('volume', 0):.0f}"
            for c in candles[-50:]
        )
        news_str = "\n".join(f"  - {n}" for n in news_items[:20]) or "  No recent news."
        macro_str = json.dumps(macro or {}, indent=2)

        return f"""## Market Context — {symbol}

### Last 50 OHLCV Candles (M5):
{candle_str}

### Recent News Headlines:
{news_str}

### Macro Indicators:
{macro_str}

Analyse this context and return your probability assessment JSON."""

    async def predict(
        self,
        symbol: str,
        candles: list[dict],
        news_items: list[str] | None = None,
        macro: dict | None = None,
    ) -> GeminiPrediction:
        # Fetch API key dynamically from DB
        api_key = ""
        async with AsyncSessionLocal() as db:
            res = await db.execute(text("SELECT value FROM system_config WHERE key='GEMINI_API_KEY'"))
            row = res.fetchone()
            if row:
                api_key = row[0]

        if not api_key:
            return GeminiPrediction(
                probability_up=0.5,
                probability_down=0.5,
                confidence_score=0.0,
                expected_volatility=1.0,
                reasoning="Sistemska napaka: GEMINI_API_KEY ni nastavljen v Admin nastavitvah. AI analize so začasno onemogočene.",
                gemini_prob=0.0,
            )

        # Configure GenerativeModel with the fetched key
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=SYSTEM_PROMPT,
        )

        context = self._build_context(symbol, candles, news_items or [], macro)
        
        try:
            # Enforce strict 58s global rate limit to spread queries exactly over 24h
            logger.info(f"[{symbol}] GeminiPredictor v čakalni vrsti za RateLimit (max 1500/dan, 1 na 58s)...")
            await global_gemini_limiter.wait()
            logger.info(f"[{symbol}] GeminiPredictor začenja API klic...")

            response = await model.generate_content_async(
                context,
                generation_config=self.generation_config,
            )
            data: dict[str, Any] = json.loads(response.text)

            prob_up = float(data.get("probability_up", 0.5))
            prob_down = float(data.get("probability_down", 0.5))
            confidence = float(data.get("confidence_score", 0.5))
            volatility = float(data.get("expected_volatility", 1.0))
            reasoning = str(data.get("reasoning", ""))

            # Normalise probabilities if they don't sum to 1
            total = prob_up + prob_down
            if total > 0:
                prob_up /= total
                prob_down /= total

            gemini_prob = (prob_up - prob_down) * confidence

            return GeminiPrediction(
                probability_up=prob_up,
                probability_down=prob_down,
                confidence_score=confidence,
                expected_volatility=volatility,
                reasoning=reasoning,
                gemini_prob=gemini_prob,
            )

        except Exception as e:
            logger.error(f"GeminiPredictor error for {symbol}: {e}")
            # Return neutral fallback
            return GeminiPrediction(
                probability_up=0.5,
                probability_down=0.5,
                confidence_score=0.0,
                expected_volatility=1.0,
                reasoning=f"Prediction unavailable: {str(e)}",
                gemini_prob=0.0,
            )
