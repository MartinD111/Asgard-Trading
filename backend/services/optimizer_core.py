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

# --- Rolling win-rate weighting (Odin's second learning signal) -------------
HITRATE_WINDOW = 50         # how many recent closed trades to score
HITRATE_MIN_SAMPLES = 10    # need at least this many trades before trusting it
HITRATE_BLEND_ALPHA = 0.5   # final = alpha*nudged + (1-alpha)*hitrate
COMPONENTS = ("tech", "pattern", "gemini")


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


def _pillar_hit(score: float, side: str, is_win: bool) -> bool:
    """
    Did this pillar point toward the eventually-correct direction?

    The pillar "voted for" the trade when sign(score) matches the entry side.
    If the trade won, the correct call was the entry side; if it lost, the
    correct call was the opposite side. So the pillar was right exactly when
    (voted_for == is_win).
    """
    direction_sign = 1.0 if side.upper() == "BUY" else -1.0
    voted_for = (score * direction_sign) > 0
    return voted_for == is_win


def compute_hitrate_weights(trades: list[dict]) -> dict[str, float] | None:
    """
    Build a target weight set from each pillar's recent directional hit-rate.

    `trades` is newest-or-oldest-ordered list of dicts, each with keys:
        "tech", "pattern", "gemini" (scores in [-1, +1]),
        "side" ("BUY"|"SELL"), "is_win" (bool).
    Only the last HITRATE_WINDOW trades are considered.

    Returns normalised weights proportional to hit-rate (floored at MIN_WEIGHT),
    or None when there are too few samples to be meaningful.
    """
    window = trades[-HITRATE_WINDOW:]
    if len(window) < HITRATE_MIN_SAMPLES:
        return None

    raw: dict[str, float] = {}
    for comp in COMPONENTS:
        hits = sum(1 for t in window if _pillar_hit(t.get(comp, 0.0), t["side"], t["is_win"]))
        rate = hits / len(window)
        # Floor each pillar so a cold streak never fully silences a component.
        raw[comp] = max(MIN_WEIGHT, rate)

    total = sum(raw.values())
    if total <= 0:
        return None
    return {k: round(v / total, 4) for k, v in raw.items()}


def blend_weights(
    nudged: dict[str, float],
    hitrate: dict[str, float] | None,
    alpha: float = HITRATE_BLEND_ALPHA,
) -> dict[str, float]:
    """
    Combine the per-trade nudged weights with the rolling hit-rate weights.

    final = alpha * nudged + (1 - alpha) * hitrate, clamped to [MIN, MAX] and
    renormalised. When hitrate is None (too few samples) the nudged weights are
    returned unchanged.
    """
    if not hitrate:
        return nudged
    blended: dict[str, float] = {}
    for comp in COMPONENTS:
        n = nudged.get(comp, DEFAULT_WEIGHTS.get(comp, 0.0))
        h = hitrate.get(comp, 0.0)
        blended[comp] = max(MIN_WEIGHT, min(MAX_WEIGHT, alpha * n + (1 - alpha) * h))
    total = sum(blended.values())
    if total <= 0:
        return nudged
    return {k: round(v / total, 4) for k, v in blended.items()}
