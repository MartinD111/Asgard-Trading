"""
Graph Pattern Recognizer
Analyzes short-term OHLCV candles to detect scalping patterns:
- Double Top / Double Bottom
- Flags (Bull / Bear)
Returns a dictionary of recognized patterns and confidence scores.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _find_extrema(candles: List[Dict], window: int = 3) -> tuple[List[int], List[int]]:
    """Finds local maxima (peaks) and minima (troughs) indices."""
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
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

def _detect_double_bottom(candles: List[Dict], troughs: List[int], tolerance: float = 0.002) -> float:
    """Returns confidence [0-1] of a double bottom pattern."""
    if len(troughs) < 2:
        return 0.0
        
    # Check the last two troughs
    t1, t2 = troughs[-2], troughs[-1]
    
    # Ensure they are somewhat separated in time but not too far
    if not (3 <= (t2 - t1) <= 20):
        return 0.0
        
    low1 = candles[t1]["low"]
    low2 = candles[t2]["low"]
    
    # Are the lows at a similar level?
    diff = abs(low1 - low2) / low1
    if diff > tolerance:
        return 0.0
        
    # Must have a peak in between them
    highs_between = [c["high"] for c in candles[t1+1:t2]]
    if not highs_between:
        return 0.0
        
    peak_between = max(highs_between)
    current_close = candles[-1]["close"]
    
    # Has price broken above the neckline (peak between bottoms)?
    is_breakout = current_close > peak_between
    
    confidence = 0.7 if diff <= tolerance/2 else 0.5
    if is_breakout:
        confidence += 0.2
        
    return min(1.0, confidence)

def _detect_double_top(candles: List[Dict], peaks: List[int], tolerance: float = 0.002) -> float:
    """Returns confidence [0-1] of a double top pattern."""
    if len(peaks) < 2:
        return 0.0
        
    p1, p2 = peaks[-2], peaks[-1]
    
    if not (3 <= (p2 - p1) <= 20):
        return 0.0
        
    high1 = candles[p1]["high"]
    high2 = candles[p2]["high"]
    
    diff = abs(high1 - high2) / high1
    if diff > tolerance:
        return 0.0
        
    lows_between = [c["low"] for c in candles[p1+1:p2]]
    if not lows_between:
        return 0.0
        
    trough_between = min(lows_between)
    current_close = candles[-1]["close"]
    
    is_breakout = current_close < trough_between
    
    confidence = 0.7 if diff <= tolerance/2 else 0.5
    if is_breakout:
        confidence += 0.2
        
    return min(1.0, confidence)


def analyze_patterns(candles: List[Dict]) -> Dict[str, Any]:
    """
    Main entry point for Pattern Recognizer.
    Analyzes the last N candles for scalp patterns.
    """
    if len(candles) < 30:
        return {"pattern": "None", "confidence": 0.0, "direction": "NEUTRAL"}
        
    recent_candles = candles[-50:] # Focus on immediate context
    peaks, troughs = _find_extrema(recent_candles)
    
    db_conf = _detect_double_bottom(recent_candles, troughs)
    dt_conf = _detect_double_top(recent_candles, peaks)
    
    best_pattern = "None"
    best_conf = 0.0
    direction = "NEUTRAL"
    
    if db_conf > 0.5 and db_conf > dt_conf:
        best_pattern = "Double Bottom"
        best_conf = db_conf
        direction = "BUY"
    elif dt_conf > 0.5 and dt_conf > db_conf:
        best_pattern = "Double Top"
        best_conf = dt_conf
        direction = "SELL"
        
    return {
        "pattern": best_pattern,
        "confidence": best_conf,
        "direction": direction,
    }
