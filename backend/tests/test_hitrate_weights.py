"""
Tests for Odin's second learning signal: rolling directional hit-rate weighting.

Pure functions — no DB/Redis required.
"""
from __future__ import annotations

import pytest

from services.optimizer_core import (
    compute_hitrate_weights, blend_weights, _pillar_hit,
    HITRATE_MIN_SAMPLES, MIN_WEIGHT, MAX_WEIGHT, DEFAULT_WEIGHTS,
)


def _trade(tech, pattern, gemini, side, is_win):
    return {"tech": tech, "pattern": pattern, "gemini": gemini, "side": side, "is_win": is_win}


# ─── _pillar_hit ──────────────────────────────────────────────────────────────

def test_pillar_hit_voted_for_and_won():
    # Bullish score on a BUY that won → hit
    assert _pillar_hit(0.8, "BUY", True) is True


def test_pillar_hit_voted_for_and_lost():
    # Bullish score on a BUY that lost → miss
    assert _pillar_hit(0.8, "BUY", False) is False


def test_pillar_hit_voted_against_and_lost():
    # Bearish score on a BUY that lost → the pillar was right to doubt it
    assert _pillar_hit(-0.8, "BUY", False) is True


def test_pillar_hit_sell_side():
    # Bearish score on a SELL that won → hit
    assert _pillar_hit(-0.8, "SELL", True) is True


# ─── compute_hitrate_weights ──────────────────────────────────────────────────

def test_too_few_samples_returns_none():
    trades = [_trade(0.5, 0.5, 0.5, "BUY", True) for _ in range(HITRATE_MIN_SAMPLES - 1)]
    assert compute_hitrate_weights(trades) is None


def test_perfect_tech_dominates_weights():
    # tech always correct, pattern/gemini always wrong → tech weight is largest
    trades = []
    for _ in range(20):
        trades.append(_trade(tech=0.8, pattern=-0.8, gemini=-0.8, side="BUY", is_win=True))
    w = compute_hitrate_weights(trades)
    assert w is not None
    assert w["tech"] > w["pattern"]
    assert w["tech"] > w["gemini"]
    # normalised (weights are rounded to 4 decimals, so allow rounding slack)
    assert sum(w.values()) == pytest.approx(1.0, abs=2e-3)


def test_weights_respect_min_floor():
    # gemini always wrong → should still keep at least the MIN floor (pre-normalisation)
    trades = [_trade(0.8, 0.8, -0.8, "BUY", True) for _ in range(20)]
    w = compute_hitrate_weights(trades)
    assert w["gemini"] > 0  # never fully zeroed


def test_only_last_window_considered():
    # Old wrong trades, recent right trades → tech should look good
    old = [_trade(-0.8, 0.0, 0.0, "BUY", True) for _ in range(60)]  # tech wrong
    new = [_trade(0.8, 0.0, 0.0, "BUY", True) for _ in range(50)]   # tech right
    w = compute_hitrate_weights(old + new)
    assert w is not None
    # The most recent 50 (all tech-correct) drive the result
    assert w["tech"] >= w["pattern"]


# ─── blend_weights ────────────────────────────────────────────────────────────

def test_blend_none_hitrate_returns_nudged():
    nudged = {"tech": 0.5, "pattern": 0.3, "gemini": 0.2}
    assert blend_weights(nudged, None) == nudged


def test_blend_mixes_and_normalises():
    nudged = {"tech": 0.6, "pattern": 0.2, "gemini": 0.2}
    hitrate = {"tech": 0.2, "pattern": 0.6, "gemini": 0.2}
    out = blend_weights(nudged, hitrate, alpha=0.5)
    assert sum(out.values()) == pytest.approx(1.0, abs=2e-3)
    for v in out.values():
        assert MIN_WEIGHT <= v <= MAX_WEIGHT
    # tech pulled down from nudged, pattern pulled up
    assert out["tech"] < nudged["tech"]
    assert out["pattern"] > nudged["pattern"]
