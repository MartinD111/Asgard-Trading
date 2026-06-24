"""Unit tests for RiskManager — pure functions, no DB/Redis needed."""
import pytest
from services.risk_manager import RiskManager


@pytest.fixture
def rm():
    return RiskManager(initial_balance=10_000.0)


# ─── Kelly fraction ─────────────────────────────────────────────────────────

def test_kelly_positive_edge(rm):
    k = rm.kelly_fraction(win_probability=0.6, win_loss_ratio=1.5)
    assert k > 0.0, "Positive edge should produce positive kelly"


def test_kelly_zero_edge(rm):
    # p=0.4, b=1.5: k = (1.5*0.4 - 0.6)/1.5 ≈ 0  (floating-point may be ~1e-17)
    k = rm.kelly_fraction(win_probability=0.4, win_loss_ratio=1.5)
    assert k == pytest.approx(0.0, abs=1e-10)


def test_kelly_capped_at_25pct(rm):
    k = rm.kelly_fraction(win_probability=0.99, win_loss_ratio=10.0)
    assert k <= 0.25


def test_kelly_risk_multiplier_scales(rm):
    base = rm.kelly_fraction(win_probability=0.6, win_loss_ratio=1.5, global_risk_multiplier=1.0)
    half = rm.kelly_fraction(win_probability=0.6, win_loss_ratio=1.5, global_risk_multiplier=0.5)
    assert half < base


def test_kelly_never_negative(rm):
    k = rm.kelly_fraction(win_probability=0.0, win_loss_ratio=1.5)
    assert k == 0.0


# ─── Position sizing ─────────────────────────────────────────────────────────

def test_position_size_positive(rm):
    qty = rm.position_size(
        equity=10_000, entry_price=1.1000, stop_loss_price=1.0890,
        win_probability=0.6
    )
    assert qty > 0


def test_position_size_zero_price_risk(rm):
    qty = rm.position_size(
        equity=10_000, entry_price=1.1000, stop_loss_price=1.1000,
        win_probability=0.6
    )
    assert qty == 0.0


def test_position_size_invalid_prices(rm):
    assert rm.position_size(0, 0, 0, 0.6) == 0.0


# ─── Stop loss / take profit ─────────────────────────────────────────────────

def test_stop_loss_buy_below_entry(rm):
    sl = rm.calculate_stop_loss("BUY", entry_price=1.1000, atr=0.002)
    assert sl < 1.1000


def test_stop_loss_sell_above_entry(rm):
    sl = rm.calculate_stop_loss("SELL", entry_price=1.1000, atr=0.002)
    assert sl > 1.1000


def test_take_profit_buy_above_entry(rm):
    sl = rm.calculate_stop_loss("BUY", entry_price=1.1000, atr=0.002)
    tp = rm.calculate_take_profit("BUY", entry_price=1.1000, stop_loss=sl)
    assert tp > 1.1000


def test_take_profit_risk_reward_ratio(rm):
    entry, atr = 100.0, 1.0
    sl = rm.calculate_stop_loss("BUY", entry_price=entry, atr=atr)
    tp = rm.calculate_take_profit("BUY", entry_price=entry, stop_loss=sl, risk_reward=2.0)
    sl_dist = abs(entry - sl)
    tp_dist = abs(tp - entry)
    assert abs(tp_dist / sl_dist - 2.0) < 0.01


# ─── Drawdown guard ──────────────────────────────────────────────────────────

def test_drawdown_not_triggered_within_limit(rm):
    assert rm.check_drawdown(9_500.0) is False  # 5% drawdown, limit is 10%


def test_drawdown_triggered_at_limit(rm):
    assert rm.check_drawdown(8_900.0) is True  # 11% drawdown


def test_drawdown_updates_peak(rm):
    rm.check_drawdown(12_000.0)  # new peak
    assert rm.peak_equity == 12_000.0
    assert rm.check_drawdown(10_900.0) is False  # 9.2% from 12k peak
