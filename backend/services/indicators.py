"""
Technical indicators — pure numpy, no external TA library required.

All functions accept a list of OHLCV dicts (oldest first) and return
graded float values in [-1, +1] so they can be directly weight-blended.

Normalisation conventions:
  RSI:  (rsi - 50) / 50  → overbought (+1) to oversold (-1)
  MACD: histogram / (price * 0.01) clamped → positive = bullish momentum
  ATR-momentum: (close - EMA20) / ATR clamped to [-3, +3] then / 3
  Trend: (EMA20 - EMA50) / ATR clamped → direction of trend
  Composite: weighted blend, clamped to [-1, +1]
"""
from __future__ import annotations

import math
from typing import Sequence


# ─── EMA ─────────────────────────────────────────────────────────────────────

def ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average. Returns same length as input (NaN-free)."""
    if not values or period <= 0:
        return values[:]
    k = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


# ─── RSI ─────────────────────────────────────────────────────────────────────

def rsi(closes: list[float], period: int = 14) -> float:
    """
    Wilder RSI, returns value in [0, 100].
    Needs at least period + 1 values; returns 50.0 (neutral) otherwise.
    """
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    # Initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def rsi_score(closes: list[float], period: int = 14) -> float:
    """RSI normalised to [-1, +1]. Overbought (>70) → +1, oversold (<30) → -1."""
    r = rsi(closes, period)
    return max(-1.0, min(1.0, (r - 50.0) / 50.0))


# ─── MACD ────────────────────────────────────────────────────────────────────

def macd(closes: list[float],
         fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
    """
    Returns (macd_line, signal_line, histogram).
    All three are price-unit values; use macd_score() for [-1,+1].
    """
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    sig_line = ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, sig_line)]
    return macd_line[-1], sig_line[-1], hist[-1]


def macd_score(closes: list[float],
               fast: int = 12, slow: int = 26, signal: int = 9) -> float:
    """MACD histogram normalised by 1% of current price → [-1, +1]."""
    _, _, hist = macd(closes, fast, slow, signal)
    price = closes[-1] if closes else 1.0
    normaliser = price * 0.01
    if normaliser == 0:
        return 0.0
    return max(-1.0, min(1.0, hist / normaliser))


# ─── ATR ─────────────────────────────────────────────────────────────────────

def atr(candles: list[dict], period: int = 14) -> float:
    """Average True Range over last `period` candles."""
    if len(candles) < 2:
        return 0.0
    trs: list[float] = []
    window = candles[-min(period + 1, len(candles)):]
    for i in range(1, len(window)):
        h = float(window[i].get("high", window[i]["close"]))
        l = float(window[i].get("low", window[i]["close"]))
        pc = float(window[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 0.0


# ─── Momentum (ATR-normalised) ────────────────────────────────────────────────

def momentum_score(candles: list[dict], ema_period: int = 20) -> float:
    """
    (close - EMA20) normalised by ATR, clamped to [-1, +1].
    This replaces the old (close - SMA20)/SMA20 * 100 which saturated
    instantly and was essentially a sign flip.
    """
    if len(candles) < ema_period + 2:
        return 0.0
    closes = [float(c["close"]) for c in candles]
    ema20 = ema(closes, ema_period)[-1]
    current_atr = atr(candles) or (closes[-1] * 0.001)
    raw = (closes[-1] - ema20) / current_atr
    return max(-1.0, min(1.0, raw / 3.0))  # ÷3 so ±3 ATR maps to ±1


# ─── Trend (EMA cross) ────────────────────────────────────────────────────────

def trend_score(candles: list[dict],
                fast_period: int = 20, slow_period: int = 50) -> float:
    """
    (EMA_fast - EMA_slow) normalised by ATR.
    Positive = uptrend, negative = downtrend.
    """
    if len(candles) < slow_period + 2:
        return 0.0
    closes = [float(c["close"]) for c in candles]
    ema_fast = ema(closes, fast_period)[-1]
    ema_slow = ema(closes, slow_period)[-1]
    current_atr = atr(candles) or (closes[-1] * 0.001)
    raw = (ema_fast - ema_slow) / current_atr
    return max(-1.0, min(1.0, raw / 2.0))  # ÷2 so ±2 ATR maps to ±1


# ─── Composite technical score ────────────────────────────────────────────────

def technical_score(
    candles: list[dict],
    w_rsi: float = 0.25,
    w_macd: float = 0.35,
    w_momentum: float = 0.25,
    w_trend: float = 0.15,
) -> float:
    """
    Blended technical score in [-1, +1].
    Weights are normalised internally so they don't need to sum to 1.

    Component interpretation:
      RSI:      mean-reversion signal (extreme RSI = likely reversal)
      MACD:     momentum direction and acceleration
      Momentum: price distance from EMA20 in ATR units
      Trend:    direction of EMA20 vs EMA50 crossover
    """
    if len(candles) < 30:
        return 0.0

    closes = [float(c["close"]) for c in candles]

    r = rsi_score(closes)
    m = macd_score(closes)
    mom = momentum_score(candles)
    t = trend_score(candles)

    total_w = w_rsi + w_macd + w_momentum + w_trend
    if total_w <= 0:
        return 0.0

    score = (w_rsi * r + w_macd * m + w_momentum * mom + w_trend * t) / total_w
    return max(-1.0, min(1.0, score))
