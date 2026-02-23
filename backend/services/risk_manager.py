"""
Risk Manager — Kelly Criterion position sizing, drawdown guards, stop-loss.
"""
import os
import math
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

MAX_DRAWDOWN_LIMIT = float(os.getenv("MAX_DRAWDOWN_LIMIT", "0.10"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))


class RiskManager:
    def __init__(self, initial_balance: float = 10_000.0):
        self.initial_balance = initial_balance
        self.peak_equity = initial_balance

    def kelly_fraction(
        self,
        win_probability: float,
        win_loss_ratio: float = 1.5,
        global_risk_multiplier: float = 1.0,
    ) -> float:
        """
        Full Kelly: K = (b*p - q) / b
        where b = win/loss ratio, p = win prob, q = 1-p.
        We use Half-Kelly (×0.5) for safety.
        """
        p = max(0.0, min(1.0, win_probability))
        q = 1.0 - p
        b = max(win_loss_ratio, 0.001)
        k = (b * p - q) / b
        raw_kelly = max(0.0, min(k * 0.5, 0.25))  # cap at 25% of equity (Half-Kelly)
        
        # Apply global risk multiplier
        adjusted_kelly = raw_kelly * max(0.1, min(1.5, global_risk_multiplier))
        return adjusted_kelly

    def position_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss_price: float,
        win_probability: float,
        win_loss_ratio: float = 1.5,
        global_risk_multiplier: float = 1.0,
    ) -> float:
        """Returns number of units to trade."""
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        k = self.kelly_fraction(win_probability, win_loss_ratio, global_risk_multiplier)
        # Also enforce max risk per trade, adjusted by multiplier
        effective_max_risk = RISK_PER_TRADE * max(0.1, min(1.5, global_risk_multiplier))
        dollar_risk = equity * min(k, effective_max_risk)
        price_risk = abs(entry_price - stop_loss_price)

        if price_risk == 0:
            return 0.0

        units = dollar_risk / price_risk
        return round(units, 8)

    def calculate_stop_loss(
        self,
        side: str,
        entry_price: float,
        atr: float = 0.0,
        atr_multiplier: float = 2.0,
        fallback_pct: float = 0.01,
    ) -> float:
        """ATR-based stop loss, falls back to 1% of price."""
        sl_distance = atr * atr_multiplier if atr > 0 else entry_price * fallback_pct
        if side == "BUY":
            return round(entry_price - sl_distance, 5)
        else:
            return round(entry_price + sl_distance, 5)

    def calculate_take_profit(
        self,
        side: str,
        entry_price: float,
        stop_loss: float,
        risk_reward: float = 2.0,
    ) -> float:
        """Take profit at risk_reward × stop-loss distance."""
        distance = abs(entry_price - stop_loss)
        if side == "BUY":
            return round(entry_price + distance * risk_reward, 5)
        else:
            return round(entry_price - distance * risk_reward, 5)

    def check_drawdown(self, current_equity: float) -> bool:
        """Returns True if trading should be halted due to max drawdown."""
        self.peak_equity = max(self.peak_equity, current_equity)
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        if drawdown >= MAX_DRAWDOWN_LIMIT:
            logger.warning(
                f"MAX DRAWDOWN BREACHED: {drawdown:.1%} >= {MAX_DRAWDOWN_LIMIT:.1%}. HALTING."
            )
            return True
        return False

    def current_drawdown(self, equity: float) -> float:
        self.peak_equity = max(self.peak_equity, equity)
        return (self.peak_equity - equity) / max(self.peak_equity, 0.01)
