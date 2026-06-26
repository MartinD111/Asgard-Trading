import os
import json
import logging
import asyncio
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
import redis.asyncio as aioredis
from sqlalchemy import text

# Import db session securely
from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Defaults; overridable per-deployment via system_config (admin Settings UI).
DEFAULT_GEMINI_MIN_INTERVAL = 58.0   # seconds between real API calls (1500/day)
DEFAULT_GEMINI_DAILY_CAP = 1500      # hard ceiling on real calls per UTC day


def _usage_key(day: str | None = None) -> str:
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"gemini:calls:{day}"


# Lazily-created shared Redis client for the usage counter.
_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    return _redis_client


async def get_gemini_usage() -> dict:
    """Return today's call count plus the configured cap and intervals."""
    redis = _get_redis()
    raw = await redis.get(_usage_key())
    calls_today = int(raw) if raw else 0
    async with AsyncSessionLocal() as db:
        cap = await _get_int_cfg(db, "gemini_daily_cap", DEFAULT_GEMINI_DAILY_CAP)
        min_interval = await _get_int_cfg(db, "gemini_min_interval_seconds", int(DEFAULT_GEMINI_MIN_INTERVAL))
        news_interval = await _get_int_cfg(db, "news_scan_interval_seconds", 60)
    return {
        "calls_today": calls_today,
        "cap": cap,
        "min_interval": min_interval,
        "news_interval": news_interval,
    }


async def _get_int_cfg(db, key: str, default: int) -> int:
    res = await db.execute(text("SELECT value FROM system_config WHERE key=:k"), {"k": key})
    row = res.fetchone()
    try:
        return int(float(row[0])) if row and row[0] not in (None, "") else default
    except (ValueError, TypeError):
        return default

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

# Per-symbol prediction cache: symbol → (GeminiPrediction, timestamp)
# Gemini's expected_volatility horizon is ~4h so caching that long is safe.
_CACHE_TTL_SECONDS = float(os.getenv("GEMINI_CACHE_TTL", "14400"))  # 4 hours default
_prediction_cache: dict[str, tuple["GeminiPrediction", float]] = {}

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
        # Return cached prediction if it is still within the TTL window.
        # This lets technical indicators run every cycle without waiting for
        # the 58s global rate limiter — Gemini refreshes at most once per TTL.
        cached = _prediction_cache.get(symbol)
        if cached is not None:
            prediction, ts = cached
            if time.time() - ts < _CACHE_TTL_SECONDS:
                logger.debug(f"[{symbol}] Gemini cache hit (age {time.time()-ts:.0f}s)")
                return prediction

        # Fetch API key + usage limits dynamically from DB
        api_key = ""
        daily_cap = DEFAULT_GEMINI_DAILY_CAP
        min_interval = DEFAULT_GEMINI_MIN_INTERVAL
        async with AsyncSessionLocal() as db:
            res = await db.execute(text("SELECT value FROM system_config WHERE key='GEMINI_API_KEY'"))
            row = res.fetchone()
            if row:
                api_key = row[0]
            daily_cap = await _get_int_cfg(db, "gemini_daily_cap", DEFAULT_GEMINI_DAILY_CAP)
            min_interval = float(await _get_int_cfg(db, "gemini_min_interval_seconds", int(DEFAULT_GEMINI_MIN_INTERVAL)))

        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY", "")

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

        # Enforce the daily cap: once exhausted, return a neutral fallback rather
        # than spending another call. Resets automatically at UTC midnight.
        redis = _get_redis()
        usage_key = _usage_key()
        raw_calls = await redis.get(usage_key)
        calls_today = int(raw_calls) if raw_calls else 0
        if calls_today >= daily_cap:
            logger.warning(f"[{symbol}] Gemini daily cap ({daily_cap}) reached — skipping API call.")
            return GeminiPrediction(
                probability_up=0.5,
                probability_down=0.5,
                confidence_score=0.0,
                expected_volatility=1.0,
                reasoning=f"Gemini daily call cap ({daily_cap}) reached. AI analysis paused until UTC midnight.",
                gemini_prob=0.0,
            )

        context = self._build_context(symbol, candles, news_items or [], macro)

        try:
            # Enforce the configurable global rate limit to spread queries over the day.
            global_gemini_limiter.interval = min_interval
            logger.info(f"[{symbol}] GeminiPredictor queued for RateLimit (cap {daily_cap}/day, 1 per {min_interval:.0f}s)...")
            await global_gemini_limiter.wait()
            logger.info(f"[{symbol}] GeminiPredictor starting API call...")

            response = await model.generate_content_async(
                context,
                generation_config=self.generation_config,
            )
            # Count this real API call against today's quota (expire after 48h).
            try:
                new_count = await redis.incr(usage_key)
                if new_count == 1:
                    await redis.expire(usage_key, 172800)
            except Exception as ce:
                logger.error(f"Gemini usage counter error: {ce}")
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

            prediction = GeminiPrediction(
                probability_up=prob_up,
                probability_down=prob_down,
                confidence_score=confidence,
                expected_volatility=volatility,
                reasoning=reasoning,
                gemini_prob=gemini_prob,
            )
            _prediction_cache[symbol] = (prediction, time.time())
            return prediction

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
