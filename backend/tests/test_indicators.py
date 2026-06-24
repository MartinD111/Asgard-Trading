"""
Unit tests for services/indicators.py — pure numpy indicators.

All tests are offline (no DB/Redis/network).
"""
from __future__ import annotations

import pytest
from services.indicators import (
    ema, rsi, rsi_score, macd, macd_score,
    atr, momentum_score, trend_score, technical_score,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _trend_candles(n: int, start: float = 100.0, drift: float = 0.001) -> list[dict]:
    candles = []
    price = start
    for i in range(n):
        price *= (1 + drift)
        candles.append({
            "open":   price * 0.999,
            "high":   price * 1.002,
            "low":    price * 0.997,
            "close":  price,
            "volume": 1000.0,
        })
    return candles


def _flat_candles(n: int, price: float = 100.0) -> list[dict]:
    return [
        {"open": price, "high": price * 1.001, "low": price * 0.999,
         "close": price, "volume": 100.0}
        for _ in range(n)
    ]


# ─── EMA ─────────────────────────────────────────────────────────────────────

def test_ema_same_length_as_input():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = ema(values, period=3)
    assert len(result) == len(values)


def test_ema_starts_at_first_value():
    values = [10.0, 20.0, 30.0]
    result = ema(values, period=3)
    assert result[0] == pytest.approx(10.0)


def test_ema_converges_toward_constant():
    values = [100.0] * 50
    result = ema(values, period=10)
    assert all(v == pytest.approx(100.0) for v in result)


# ─── RSI ─────────────────────────────────────────────────────────────────────

def test_rsi_range():
    closes = [float(i) for i in range(1, 40)]
    r = rsi(closes)
    assert 0.0 <= r <= 100.0


def test_rsi_neutral_on_insufficient_data():
    r = rsi([100.0] * 5, period=14)
    assert r == pytest.approx(50.0)


def test_rsi_high_on_rising_series():
    closes = [100.0 + i for i in range(30)]   # steadily rising
    r = rsi(closes)
    assert r > 60.0


def test_rsi_low_on_falling_series():
    closes = [100.0 - i for i in range(30)]   # steadily falling
    r = rsi(closes)
    assert r < 40.0


def test_rsi_score_in_range():
    closes = [100.0 + i * 0.5 for i in range(30)]
    s = rsi_score(closes)
    assert -1.0 <= s <= 1.0


def test_rsi_score_graded_not_binary():
    """Score should not always be exactly ±1 on mixed (realistic) data."""
    import math
    # Sine wave oscillation with slight upward drift — RSI stays graded
    closes = [100.0 + i * 0.05 + math.sin(i * 0.4) * 2 for i in range(40)]
    s = rsi_score(closes)
    assert abs(s) < 1.0   # graded value, not saturated


# ─── MACD ────────────────────────────────────────────────────────────────────

def test_macd_returns_three_floats():
    closes = [100.0 + i * 0.1 for i in range(50)]
    m_line, sig, hist = macd(closes)
    assert isinstance(m_line, float)
    assert isinstance(sig, float)
    assert isinstance(hist, float)


def test_macd_zero_on_insufficient_data():
    closes = [100.0] * 10
    m_line, sig, hist = macd(closes)
    assert m_line == pytest.approx(0.0)


def test_macd_score_in_range():
    closes = [100.0 + i * 0.5 for i in range(60)]
    s = macd_score(closes)
    assert -1.0 <= s <= 1.0


def test_macd_score_positive_on_uptrend():
    closes = [100.0 + i * 1.0 for i in range(60)]
    s = macd_score(closes)
    assert s > 0


def test_macd_score_negative_on_downtrend():
    closes = [200.0 - i * 1.0 for i in range(60)]
    s = macd_score(closes)
    assert s < 0


# ─── ATR ─────────────────────────────────────────────────────────────────────

def test_atr_positive_on_volatile_candles():
    candles = _trend_candles(20, drift=0.002)
    a = atr(candles)
    assert a > 0.0


def test_atr_zero_on_single_candle():
    candles = [{"open": 100, "high": 101, "low": 99, "close": 100}]
    assert atr(candles) == 0.0


def test_atr_zero_on_empty():
    assert atr([]) == 0.0


def test_atr_larger_on_high_volatility():
    calm = _flat_candles(20)
    volatile = _trend_candles(20, drift=0.01)
    assert atr(volatile) > atr(calm)


# ─── Momentum score ───────────────────────────────────────────────────────────

def test_momentum_score_in_range():
    candles = _trend_candles(60)
    s = momentum_score(candles)
    assert -1.0 <= s <= 1.0


def test_momentum_score_positive_above_ema():
    candles = _trend_candles(60, drift=0.005)
    s = momentum_score(candles)
    assert s > 0


def test_momentum_score_neutral_on_flat():
    candles = _flat_candles(60)
    s = momentum_score(candles)
    assert abs(s) < 0.2   # flat market stays near zero


def test_momentum_score_zero_on_insufficient_data():
    candles = _trend_candles(10)
    s = momentum_score(candles)
    assert s == pytest.approx(0.0)


# ─── Trend score ─────────────────────────────────────────────────────────────

def test_trend_score_in_range():
    candles = _trend_candles(80)
    s = trend_score(candles)
    assert -1.0 <= s <= 1.0


def test_trend_score_positive_in_uptrend():
    candles = _trend_candles(80, drift=0.003)
    s = trend_score(candles)
    assert s > 0


def test_trend_score_negative_in_downtrend():
    candles = _trend_candles(80, drift=-0.003)
    s = trend_score(candles)
    assert s < 0


def test_trend_score_zero_on_insufficient_data():
    candles = _trend_candles(30)
    s = trend_score(candles)
    assert s == pytest.approx(0.0)


# ─── Composite technical_score ────────────────────────────────────────────────

def test_technical_score_in_range_uptrend():
    candles = _trend_candles(80, drift=0.002)
    s = technical_score(candles)
    assert -1.0 <= s <= 1.0


def test_technical_score_positive_on_uptrend():
    candles = _trend_candles(80, drift=0.003)
    s = technical_score(candles)
    assert s > 0


def test_technical_score_negative_on_downtrend():
    candles = _trend_candles(80, drift=-0.003)
    s = technical_score(candles)
    assert s < 0


def test_technical_score_zero_on_insufficient_candles():
    candles = _trend_candles(10)
    s = technical_score(candles)
    assert s == pytest.approx(0.0)


def test_technical_score_graded_not_binary():
    """The composite must NOT return ±1.0 on ordinary trending data."""
    candles = _trend_candles(80, drift=0.001)
    s = technical_score(candles)
    assert abs(s) < 1.0  # graded, not saturated to a rail


def test_technical_score_custom_weights():
    candles = _trend_candles(80, drift=0.002)
    s1 = technical_score(candles, w_rsi=0.5, w_macd=0.5, w_momentum=0.0, w_trend=0.0)
    s2 = technical_score(candles, w_rsi=0.0, w_macd=0.0, w_momentum=0.5, w_trend=0.5)
    # Both should be in range but not necessarily equal
    assert -1.0 <= s1 <= 1.0
    assert -1.0 <= s2 <= 1.0
