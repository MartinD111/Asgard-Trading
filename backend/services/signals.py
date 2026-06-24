"""
Signals — stateless, pure signal computation used identically by:
  - DecisionEngine (live / paper)
  - SimulationEngine
  - Backtester

compute_signal() is the single source of truth for what constitutes
a trade signal. Any improvement here automatically benefits all three
consumers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services.indicators import technical_score as _compute_technical_score
from services.pattern_recognizer import analyze_patterns


@dataclass
class Signal:
    symbol: str
    direction: str          # "BUY" | "SELL" | "NEUTRAL"
    final_score: float      # [-1, +1]; magnitude drives conviction
    technical_score: float  # [-1, +1]
    pattern_score: float    # [-1, +1]
    gemini_score: float     # [-1, +1]  (0 if Gemini not available)
    pattern_name: str       # human-readable pattern label or "None"
    confidence: float       # [0, 1]
    weights: dict = field(default_factory=dict)


# Default agent weight presets (same as before, now centralised here)
AGENT_WEIGHTS: dict[str, dict[str, float]] = {
    "loki": {"tech": 0.40, "gemini": 0.30, "pattern": 0.30},
    "thor": {"tech": 0.25, "gemini": 0.25, "pattern": 0.25, "corr": 0.25},
    "odin": {"tech": 0.33, "gemini": 0.34, "pattern": 0.33},  # overridden by optimizer
}


def compute_signal(
    candles: list[dict],
    symbol: str = "",
    gemini_prob: float = 0.0,
    weights: dict[str, float] | None = None,
    agent: str = "loki",
) -> Signal:
    """
    Pure, deterministic signal computation.

    Parameters
    ----------
    candles     : OHLCV list, oldest first; minimum 14 required.
    symbol      : Instrument identifier (informational only).
    gemini_prob : Pre-computed Gemini contribution in [-1, +1].
                  Pass 0.0 when running without Gemini (e.g. backtest).
    weights     : Override weight dict {"tech", "gemini", "pattern"}.
                  If None, uses the preset for `agent`.
    agent       : "loki" | "thor" | "odin" — selects default weights.
    """
    if len(candles) < 14:
        return Signal(
            symbol=symbol,
            direction="NEUTRAL",
            final_score=0.0,
            technical_score=0.0,
            pattern_score=0.0,
            gemini_score=0.0,
            pattern_name="None",
            confidence=0.0,
        )

    w = weights if weights is not None else AGENT_WEIGHTS.get(agent, AGENT_WEIGHTS["loki"])

    tech = _compute_technical_score(candles)

    pattern_data = analyze_patterns(candles)
    pat_name = pattern_data.get("pattern", "None")
    pat_conf = pattern_data.get("confidence", 0.0)
    pat_dir = pattern_data.get("direction", "NEUTRAL")
    pat_contrib = pat_conf * (1.0 if pat_dir == "BUY" else -1.0) if pat_name != "None" else 0.0

    w_tech = w.get("tech", 0.40)
    w_gem = w.get("gemini", 0.30)
    w_pat = w.get("pattern", 0.30)
    # Normalise so weights sum to 1 (handles missing keys gracefully)
    total_w = w_tech + w_gem + w_pat
    if total_w > 0:
        w_tech /= total_w
        w_gem /= total_w
        w_pat /= total_w

    final = w_tech * tech + w_gem * gemini_prob + w_pat * pat_contrib
    final = max(-1.0, min(1.0, final))

    # Confidence: blend pattern confidence with score magnitude
    magnitude_conf = min(1.0, abs(final) * 1.5)
    confidence = (magnitude_conf + pat_conf) / 2 if pat_name != "None" else magnitude_conf

    direction = "BUY" if final > 0 else "SELL" if final < 0 else "NEUTRAL"

    return Signal(
        symbol=symbol,
        direction=direction,
        final_score=final,
        technical_score=tech,
        pattern_score=pat_contrib,
        gemini_score=gemini_prob,
        pattern_name=pat_name,
        confidence=confidence,
        weights={"tech": w_tech, "gemini": w_gem, "pattern": w_pat},
    )
