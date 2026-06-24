"""
Pure weight-update logic for the Odin optimizer — no DB, no Redis, fully testable.

Import from here in tests. weight_optimizer.py imports from here too so
the constants and algorithm stay in one place.
"""
from __future__ import annotations

# Keys must match signals.AGENT_WEIGHTS keys so compute_signal() picks them up
DEFAULT_WEIGHTS: dict[str, float] = {
    "tech": 0.33,
    "pattern": 0.33,
    "gemini": 0.34,
}

LEARNING_RATE = 0.02    # nudge per evaluated trade
MAX_WEIGHT = 0.70       # cap so no single component dominates
MIN_WEIGHT = 0.05       # floor so no component is fully ignored
AGREEMENT_THRESHOLD = 0.15  # minimum |agreement| to trigger a weight update


def apply_reward(
    weights: dict[str, float],
    scores: dict[str, float],
    side: str,
    is_win: bool,
) -> dict[str, float]:
    """
    Nudge component weights based on whether each component correctly
    predicted the outcome of a closed trade.

    Parameters
    ----------
    weights : current weight dict — modified in place and returned
    scores  : component scores in [-1, +1] keyed by component name
    side    : "BUY" or "SELL" — the actual trade entry direction
    is_win  : True if the trade closed with positive PnL

    Agreement rule: for a BUY trade a positive score means the component
    voted with the trade; for a SELL trade a negative score means agreement.
    Components that were ambiguous (|agreement| < AGREEMENT_THRESHOLD) are
    skipped to avoid learning from noise.
    """
    direction_sign = 1.0 if side.upper() == "BUY" else -1.0
    for component, score in scores.items():
        if component not in weights:
            weights[component] = DEFAULT_WEIGHTS.get(component, 1.0 / len(DEFAULT_WEIGHTS))
        agreement = score * direction_sign   # >0 means "voted with the trade"
        if abs(agreement) < AGREEMENT_THRESHOLD:
            continue
        voted_for = agreement > 0
        if is_win and voted_for:
            weights[component] += LEARNING_RATE
        elif is_win and not voted_for:
            weights[component] -= LEARNING_RATE
        elif not is_win and voted_for:
            weights[component] -= LEARNING_RATE
        else:
            weights[component] += LEARNING_RATE
        weights[component] = max(MIN_WEIGHT, min(MAX_WEIGHT, weights[component]))
    return weights
