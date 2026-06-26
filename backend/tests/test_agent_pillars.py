"""
Tests for the Loki M/P/T single-pillar agents and Thor's equal blend.

compute_signal() is the single source of truth, so verifying the pillar-pure
weights here guarantees DecisionEngine, SimulationEngine and the backtester all
behave consistently.
"""
from __future__ import annotations

import math

import pytest

from services.signals import (
    compute_signal, AGENT_WEIGHTS, SELECTABLE_AGENTS, DEFAULT_AGENT,
)


def _ramp_candles(n: int = 40, start: float = 100.0, step: float = 0.5) -> list[dict]:
    """Deterministic uptrending OHLCV candles (enough for indicators)."""
    candles = []
    price = start
    for i in range(n):
        o = price
        c = price + step
        h = c + 0.2
        low = o - 0.2
        candles.append({"time": i, "open": o, "high": h, "low": low, "close": c, "volume": 1000})
        price = c
    return candles


def test_selectable_agents_and_default():
    assert SELECTABLE_AGENTS == ("loki_m", "loki_p", "loki_t", "thor", "odin")
    assert DEFAULT_AGENT == "loki_m"


def test_loki_m_is_math_only():
    """Loki-M final score must equal the technical (math) score alone."""
    candles = _ramp_candles()
    s = compute_signal(candles, symbol="X", gemini_prob=0.9, agent="loki_m")
    # gemini and pattern weights are zero → final == technical_score
    assert s.final_score == pytest.approx(s.technical_score, abs=1e-9)
    assert s.weights["gemini"] == pytest.approx(0.0)
    assert s.weights["pattern"] == pytest.approx(0.0)


def test_loki_t_is_trends_gemini_only():
    """Loki-T final score must equal the Gemini (trends) contribution alone."""
    candles = _ramp_candles()
    s = compute_signal(candles, symbol="X", gemini_prob=0.42, agent="loki_t")
    assert s.final_score == pytest.approx(0.42, abs=1e-9)
    assert s.weights["tech"] == pytest.approx(0.0)
    assert s.weights["pattern"] == pytest.approx(0.0)


def test_loki_p_is_pattern_only():
    """Loki-P final score must equal the pattern contribution alone."""
    candles = _ramp_candles()
    s = compute_signal(candles, symbol="X", gemini_prob=0.9, agent="loki_p")
    assert s.final_score == pytest.approx(s.pattern_score, abs=1e-9)
    assert s.weights["tech"] == pytest.approx(0.0)
    assert s.weights["gemini"] == pytest.approx(0.0)


def test_thor_is_equal_blend_of_three_pillars():
    """Thor must be the simple mean of math, trends and patterns."""
    candles = _ramp_candles()
    gem = 0.3
    s = compute_signal(candles, symbol="X", gemini_prob=gem, agent="thor")
    expected = (s.technical_score + s.gemini_score + s.pattern_score) / 3.0
    expected = max(-1.0, min(1.0, expected))
    assert s.final_score == pytest.approx(expected, abs=1e-9)


def test_thor_preset_weights_are_equal():
    w = AGENT_WEIGHTS["thor"]
    assert w["tech"] == pytest.approx(1 / 3)
    assert w["gemini"] == pytest.approx(1 / 3)
    assert w["pattern"] == pytest.approx(1 / 3)


def test_unknown_agent_falls_back_to_loki():
    candles = _ramp_candles()
    s = compute_signal(candles, symbol="X", gemini_prob=0.1, agent="does_not_exist")
    # Falls back to the legacy 'loki' preset — should not raise and weights sum to 1
    assert math.isclose(sum(s.weights.values()), 1.0, abs_tol=1e-6)
