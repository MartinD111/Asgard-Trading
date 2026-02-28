"""
Graph Pattern Recognizer
Analyzes OHLCV candles to detect patterns based on Bulkowski's statistics and mathematical geometry:
- Double Top / Double Bottom
- Head & Shoulders (Bearish, 70% Win Rate)
- Inverse Head & Shoulders (Bullish, 89% Win Rate)
- Bull Flag (Bullish, 85% Win Rate)
- Bollinger Band Squeeze
Returns a dictionary of recognized patterns and confidence scores.
"""
import logging
import math
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _find_extrema(candles: List[Dict], window: int = 3) -> tuple[List[int], List[int]]:
    """Finds local maxima (peaks) and minima (troughs) indices."""
    highs = [c.get("high", c.get("close", 0)) for c in candles]
    lows = [c.get("low", c.get("close", 0)) for c in candles]
    peaks = []
    troughs = []
    
    n = len(candles)
    for i in range(window, n - window):
        is_peak = True
        is_trough = True
        
        for j in range(i - window, i + window + 1):
            if i == j:
                continue
            if highs[i] < highs[j]:
                is_peak = False
            if lows[i] > lows[j]:
                is_trough = False
                
        if is_peak:
            peaks.append(i)
        if is_trough:
            troughs.append(i)
            
    return peaks, troughs

def _detect_double_bottom(candles: List[Dict], troughs: List[int], tolerance: float = 0.005) -> float:
    if len(troughs) < 2:
        return 0.0
    t1, t2 = troughs[-2], troughs[-1]
    if not (3 <= (t2 - t1) <= 30):
        return 0.0
    low1 = candles[t1].get("low", candles[t1].get("close", 1))
    low2 = candles[t2].get("low", candles[t2].get("close", 1))
    if low1 == 0: return 0.0
    
    diff = abs(low1 - low2) / low1
    if diff > tolerance:
        return 0.0
        
    highs_between = [c.get("high", c.get("close", 1)) for c in candles[t1+1:t2]]
    if not highs_between: return 0.0
    
    peak_between = max(highs_between)
    current_close = candles[-1]["close"]
    
    is_breakout = current_close > peak_between
    confidence = 0.88 if is_breakout else 0.65  # Double Bottom success rate is ~88% on breakouts
    if diff > tolerance / 2:
        confidence -= 0.1
    return float(min(1.0, confidence))

def _detect_double_top(candles: List[Dict], peaks: List[int], tolerance: float = 0.005) -> float:
    if len(peaks) < 2:
        return 0.0
    p1, p2 = peaks[-2], peaks[-1]
    if not (3 <= (p2 - p1) <= 30):
        return 0.0
    high1 = candles[p1].get("high", candles[p1].get("close", 1))
    high2 = candles[p2].get("high", candles[p2].get("close", 1))
    if high1 == 0: return 0.0
    
    diff = abs(high1 - high2) / high1
    if diff > tolerance:
        return 0.0
        
    lows_between = [c.get("low", c.get("close", 1)) for c in candles[p1+1:p2]]
    if not lows_between: return 0.0
    
    trough_between = min(lows_between)
    current_close = candles[-1]["close"]
    
    is_breakout = current_close < trough_between
    confidence = 0.85 if is_breakout else 0.60
    if diff > tolerance / 2:
        confidence -= 0.1
    return float(min(1.0, confidence))

def _detect_head_and_shoulders(candles: List[Dict], peaks: List[int], tolerance: float = 0.01) -> float:
    """Bearish Head & Shoulders (70% success rate on breakout)."""
    if len(peaks) < 3:
        return 0.0
    p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
    
    h1 = candles[p1].get("high", candles[p1].get("close", 1))
    h2 = candles[p2].get("high", candles[p2].get("close", 1))
    h3 = candles[p3].get("high", candles[p3].get("close", 1))
    
    # Head must be higher than both shoulders
    if not (h2 > h1 and h2 > h3):
        return 0.0
        
    # Shoulders should be roughly at the same level
    if abs(h1 - h3) / h1 > tolerance:
        return 0.0
        
    # Find neckline (troughs between p1-p2 and p2-p3)
    troughs_1 = [c.get("low", c.get("close", 1)) for c in candles[p1+1:p2]]
    troughs_2 = [c.get("low", c.get("close", 1)) for c in candles[p2+1:p3]]
    if not troughs_1 or not troughs_2:
        return 0.0
    neck1, neck2 = min(troughs_1), min(troughs_2)
    
    current_close = candles[-1]["close"]
    is_breakout = current_close < min(neck1, neck2)
    
    confidence = 0.70 if is_breakout else 0.40 # 70% WR per Bulkowski
    return float(min(1.0, confidence))

def _detect_inverse_head_and_shoulders(candles: List[Dict], troughs: List[int], tolerance: float = 0.01) -> float:
    """Bullish Inverse Head & Shoulders (89% success rate on breakout)."""
    if len(troughs) < 3:
        return 0.0
    t1, t2, t3 = troughs[-3], troughs[-2], troughs[-1]
    
    l1 = candles[t1].get("low", candles[t1].get("close", 1))
    l2 = candles[t2].get("low", candles[t2].get("close", 1))
    l3 = candles[t3].get("low", candles[t3].get("close", 1))
    
    # Head must be lower than both shoulders
    if not (l2 < l1 and l2 < l3):
        return 0.0
        
    # Shoulders should be roughly at the same level
    if l1 == 0: return 0.0
    if abs(l1 - l3) / l1 > tolerance:
        return 0.0
        
    # Find neckline (peaks between t1-t2 and t2-t3)
    peaks_1 = [c.get("high", c.get("close", 1)) for c in candles[t1+1:t2]]
    peaks_2 = [c.get("high", c.get("close", 1)) for c in candles[t2+1:t3]]
    if not peaks_1 or not peaks_2:
        return 0.0
    neck1, neck2 = max(peaks_1), max(peaks_2)
    
    current_close = candles[-1]["close"]
    is_breakout = current_close > max(neck1, neck2)
    
    confidence = 0.89 if is_breakout else 0.50 # 89% WR per Bulkowski
    return float(min(1.0, confidence))

def _detect_bull_flag(candles: List[Dict]) -> float:
    """Bull Flag: Impulse up followed by a descending channel. (85% success rate)"""
    n = len(candles)
    if n < 20: return 0.0
    
    # Split into impulse pole and flag
    pole_candles = candles[-20:-10]
    flag_candles = candles[-10:-1]
    
    pole_start = pole_candles[0].get("low", pole_candles[0]["close"])
    pole_end = pole_candles[-1].get("high", pole_candles[-1]["close"])
    
    if pole_start == 0: return 0.0
    pole_return = (pole_end - pole_start) / pole_start
    
    # Pole must clearly go up
    if pole_return < 0.01:
        return 0.0
        
    # Flag should consolidate slightly downwards
    flag_start = flag_candles[0].get("high", flag_candles[0]["close"])
    flag_end = flag_candles[-1].get("close", flag_candles[-1].get("high", 1))
    
    # Flag shouldn't retrace more than 50% of the pole
    retrace = (pole_end - flag_end) / (pole_end - pole_start)
    if not (0.1 < retrace < 0.5):
        return 0.0
        
    current_close = candles[-1]["close"]
    # Breakout of the flag top
    is_breakout = current_close > flag_candles[0].get("high", flag_start)
    
    confidence = 0.85 if is_breakout else 0.60
    return float(min(1.0, confidence))

def _detect_bollinger_squeeze(candles: List[Dict], period: int = 20) -> float:
    """Detects Bollinger Band Squeeze which indicates a volatility breakout."""
    if len(candles) < period * 2:
        return 0.0
        
    recent = candles[-period:]
    closes = [c["close"] for c in recent]
    sma = sum(closes) / period
    
    variance = sum((c - sma) ** 2 for c in closes) / period
    std_dev = math.sqrt(variance)
    
    if sma == 0: return 0.0
    band_width = (2 * std_dev) / sma
    
    # If bandwidth is extremely tight (<1%)
    if band_width < 0.01:
        return 0.70 # Squeeze detected, direction neutral but breakout imminent
    return 0.0

def analyze_patterns(candles: List[Dict]) -> Dict[str, Any]:
    """
    Main entry point for Pattern Recognizer.
    Analyzes the last N candles for geometrically robust patterns.
    """
    if len(candles) < 30:
        return {"pattern": "None", "confidence": 0.0, "direction": "NEUTRAL"}
        
    recent_candles = candles[-50:] # Focus on immediate context
    peaks, troughs = _find_extrema(recent_candles)
    
    # Evaluate all patterns
    patterns = {
        "Inverse Head & Shoulders": {"conf": _detect_inverse_head_and_shoulders(recent_candles, troughs), "dir": "BUY"},
        "Double Bottom": {"conf": _detect_double_bottom(recent_candles, troughs), "dir": "BUY"},
        "Bull Flag": {"conf": _detect_bull_flag(recent_candles), "dir": "BUY"},
        "Head & Shoulders": {"conf": _detect_head_and_shoulders(recent_candles, peaks), "dir": "SELL"},
        "Double Top": {"conf": _detect_double_top(recent_candles, peaks), "dir": "SELL"},
    }
    
    # Volatility Check
    squeeze_conf = _detect_bollinger_squeeze(recent_candles)
    
    best_pattern = "None"
    best_conf = 0.0
    direction = "NEUTRAL"
    
    for pat, data in patterns.items():
        if data["conf"] > best_conf:
            best_conf = data["conf"]
            best_pattern = pat
            direction = data["dir"]
            
    # If we have a squeeze combined with a pattern, increase confidence by confluence
    if squeeze_conf > 0.0 and best_conf > 0.6:
        best_conf = min(0.95, best_conf + 0.1)
        best_pattern += " + BB Squeeze"
        
    if best_conf < 0.5:
        return {"pattern": "None", "confidence": 0.0, "direction": "NEUTRAL"}
        
    return {
        "pattern": best_pattern,
        "confidence": best_conf,
        "direction": direction,
    }

