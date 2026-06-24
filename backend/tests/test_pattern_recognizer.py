"""Unit tests for pattern_recognizer — pure functions, no DB/Redis needed."""
import pytest
from services.pattern_recognizer import (
    analyze_patterns,
    _detect_double_bottom,
    _detect_double_top,
    _detect_bollinger_squeeze,
    _find_extrema,
)


def _candle(close: float, high: float | None = None, low: float | None = None) -> dict:
    return {
        "open": close,
        "close": close,
        "high": high if high is not None else close * 1.001,
        "low": low if low is not None else close * 0.999,
        "volume": 100.0,
    }


def _flat_candles(n: int = 50, price: float = 100.0) -> list[dict]:
    return [_candle(price) for _ in range(n)]


# ─── analyze_patterns: edge cases ────────────────────────────────────────────

def test_too_few_candles_returns_none():
    result = analyze_patterns([_candle(100)] * 10)
    assert result["pattern"] == "None"
    assert result["confidence"] == 0.0


def test_flat_market_no_pattern():
    result = analyze_patterns(_flat_candles(50))
    assert result["pattern"] == "None"


# ─── Double bottom ────────────────────────────────────────────────────────────

def test_double_bottom_detected():
    """Construct candles with two similar lows separated by a peak, then a breakout."""
    candles = _flat_candles(30, 100.0)  # 30 base candles (indices 0-29)
    # First trough at index 10
    candles[10] = _candle(95.0, high=95.5, low=94.8)
    # Peak between troughs at index 15
    candles[15] = _candle(102.0, high=103.0, low=101.0)
    # Second trough at index 22 (within the 30-candle list)
    candles[22] = _candle(95.1, high=95.6, low=94.9)
    # Append breakout candles to reach 50
    while len(candles) < 50:
        candles.append(_candle(104.0, high=105.0, low=103.0))

    troughs = [10, 22]
    conf = _detect_double_bottom(candles[:50], troughs)
    assert conf > 0.5


def test_double_bottom_requires_two_troughs():
    candles = _flat_candles(50)
    assert _detect_double_bottom(candles, [5]) == 0.0


# ─── Double top ───────────────────────────────────────────────────────────────

def test_double_top_requires_two_peaks():
    candles = _flat_candles(50)
    assert _detect_double_top(candles, [5]) == 0.0


def test_double_top_peaks_too_close():
    candles = _flat_candles(50, 100.0)
    # Peaks only 1 candle apart — below the minimum distance of 3
    assert _detect_double_top(candles, [10, 11]) == 0.0


# ─── Bollinger squeeze ────────────────────────────────────────────────────────

def test_bollinger_squeeze_on_flat_market():
    # A perfectly flat series has zero std dev → band_width = 0 → squeeze
    candles = _flat_candles(50)
    conf = _detect_bollinger_squeeze(candles, period=20)
    assert conf > 0.0


def test_bollinger_no_squeeze_on_volatile():
    import random
    random.seed(42)
    candles = [_candle(100.0 + random.uniform(-5, 5)) for _ in range(50)]
    conf = _detect_bollinger_squeeze(candles, period=20)
    assert conf == 0.0


def test_bollinger_squeeze_needs_enough_candles():
    candles = _flat_candles(10)
    conf = _detect_bollinger_squeeze(candles, period=20)
    assert conf == 0.0


# ─── _find_extrema ────────────────────────────────────────────────────────────

def test_find_extrema_finds_peak():
    candles = _flat_candles(20, 100.0)
    candles[10] = _candle(110.0, high=111.0, low=109.0)
    peaks, troughs = _find_extrema(candles, window=3)
    assert 10 in peaks


def test_find_extrema_finds_trough():
    candles = _flat_candles(20, 100.0)
    candles[10] = _candle(90.0, high=91.0, low=89.0)
    peaks, troughs = _find_extrema(candles, window=3)
    assert 10 in troughs
