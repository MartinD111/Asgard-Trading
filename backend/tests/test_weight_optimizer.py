"""
Unit tests for the weight optimizer's pure reward logic.

All tests call apply_reward() directly — no DB, no Redis required.
"""
from __future__ import annotations

import pytest
from services.optimizer_core import (
    apply_reward, DEFAULT_WEIGHTS, LEARNING_RATE,
    MIN_WEIGHT, MAX_WEIGHT, AGREEMENT_THRESHOLD,
)


def _default_weights() -> dict:
    return DEFAULT_WEIGHTS.copy()


# ─── Win + component voted for trade → reward ─────────────────────────────────

def test_win_with_bullish_tech_on_buy_increases_tech():
    w = _default_weights()
    before = w["tech"]
    apply_reward(w, {"tech": 0.8, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=True)
    assert w["tech"] > before


def test_win_with_bearish_tech_on_sell_increases_tech():
    w = _default_weights()
    before = w["tech"]
    # Negative score on a SELL trade = component agreed with entry direction
    apply_reward(w, {"tech": -0.8, "pattern": 0.0, "gemini": 0.0}, side="SELL", is_win=True)
    assert w["tech"] > before


# ─── Win + component voted against trade → punish ─────────────────────────────

def test_win_with_bearish_tech_on_buy_decreases_tech():
    w = _default_weights()
    before = w["tech"]
    apply_reward(w, {"tech": -0.8, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=True)
    assert w["tech"] < before


def test_win_with_bullish_tech_on_sell_decreases_tech():
    w = _default_weights()
    before = w["tech"]
    apply_reward(w, {"tech": 0.8, "pattern": 0.0, "gemini": 0.0}, side="SELL", is_win=True)
    assert w["tech"] < before


# ─── Loss + component voted for trade → punish ───────────────────────────────

def test_loss_with_bullish_tech_on_buy_decreases_tech():
    w = _default_weights()
    before = w["tech"]
    apply_reward(w, {"tech": 0.8, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=False)
    assert w["tech"] < before


# ─── Loss + component voted against trade → reward ───────────────────────────

def test_loss_with_bearish_tech_on_buy_increases_tech():
    w = _default_weights()
    before = w["tech"]
    apply_reward(w, {"tech": -0.8, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=False)
    assert w["tech"] > before


# ─── Ambiguous score below threshold → no change ─────────────────────────────

def test_ambiguous_score_no_weight_change():
    w = _default_weights()
    before = w.copy()
    # Score below AGREEMENT_THRESHOLD → should not move
    apply_reward(
        w,
        {"tech": AGREEMENT_THRESHOLD * 0.5, "pattern": 0.0, "gemini": 0.0},
        side="BUY", is_win=True,
    )
    assert w["tech"] == pytest.approx(before["tech"])


def test_zero_score_no_weight_change():
    w = _default_weights()
    before = w.copy()
    apply_reward(w, {"tech": 0.0, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=True)
    assert w == pytest.approx(before)


# ─── Clamp behaviour ──────────────────────────────────────────────────────────

def test_weight_never_exceeds_max():
    w = {"tech": MAX_WEIGHT - 0.001, "pattern": 0.33, "gemini": 0.34}
    for _ in range(20):
        apply_reward(w, {"tech": 0.9, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=True)
    assert w["tech"] <= MAX_WEIGHT


def test_weight_never_below_min():
    w = {"tech": MIN_WEIGHT + 0.001, "pattern": 0.33, "gemini": 0.34}
    for _ in range(20):
        apply_reward(w, {"tech": 0.9, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=False)
    assert w["tech"] >= MIN_WEIGHT


# ─── Multi-component update ───────────────────────────────────────────────────

def test_all_components_update_independently():
    w = _default_weights()
    scores = {"tech": 0.8, "pattern": -0.8, "gemini": 0.8}
    # BUY trade WIN:
    #   tech=+0.8 agreed → reward tech
    #   pattern=-0.8 disagreed → punish pattern
    #   gemini=+0.8 agreed → reward gemini
    apply_reward(w, scores, side="BUY", is_win=True)
    assert w["tech"] > DEFAULT_WEIGHTS["tech"]
    assert w["pattern"] < DEFAULT_WEIGHTS["pattern"]
    assert w["gemini"] > DEFAULT_WEIGHTS["gemini"]


def test_nudge_magnitude_equals_learning_rate():
    w = _default_weights()
    before_tech = w["tech"]
    apply_reward(w, {"tech": 0.9, "pattern": 0.0, "gemini": 0.0}, side="BUY", is_win=True)
    assert w["tech"] == pytest.approx(before_tech + LEARNING_RATE)


# ─── Unknown component gets default weight ────────────────────────────────────

def test_unknown_component_initialised_to_default():
    w = {}
    apply_reward(w, {"tech": 0.9}, side="BUY", is_win=True)
    assert "tech" in w
    assert w["tech"] > 0
