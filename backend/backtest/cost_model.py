"""
Cost model — realistic transaction costs applied on every simulated open/close.

Sources:
  Forex (OANDA practice): ~1–2 pip spread, no commission.
  Metals (OANDA practice): XAU ~$0.50 spread, XAG ~$0.03.
  Crypto (Binance/Coinbase taker): ~0.10 % taker fee each side.
  Stocks (Alpaca): ~$0.005/share commission, negligible spread.

Slippage: modelled as a fraction of ATR to account for fill uncertainty.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    spread: float = 0.0       # absolute price units (e.g. 0.00015 for EUR_USD)
    commission_pct: float = 0.0  # percentage of notional (e.g. 0.001 = 0.1%)
    slippage_pct: float = 0.0005  # 0.05 % of price as fill slippage

    def entry_cost(self, price: float, quantity: float) -> float:
        notional = price * quantity
        spread_cost = self.spread * quantity
        commission = notional * self.commission_pct
        slippage = notional * self.slippage_pct
        return spread_cost + commission + slippage

    def exit_cost(self, price: float, quantity: float) -> float:
        return self.entry_cost(price, quantity)

    def total_cost(self, price: float, quantity: float) -> float:
        return self.entry_cost(price, quantity) + self.exit_cost(price, quantity)


# ─── Per-instrument presets ───────────────────────────────────────────────────

COST_MODELS: dict[str, CostModel] = {
    # Forex: ~1.5 pip spread on EUR/USD, no commission
    "EUR_USD": CostModel(spread=0.00015, commission_pct=0.0, slippage_pct=0.0003),
    "GBP_USD": CostModel(spread=0.00020, commission_pct=0.0, slippage_pct=0.0003),
    "USD_JPY": CostModel(spread=0.015,   commission_pct=0.0, slippage_pct=0.0003),
    # Metals
    "XAU_USD": CostModel(spread=0.50,    commission_pct=0.0, slippage_pct=0.0005),
    "XAG_USD": CostModel(spread=0.03,    commission_pct=0.0, slippage_pct=0.0005),
    # Crypto — 0.10 % taker each side
    "BTCUSDT":  CostModel(spread=0.0, commission_pct=0.001, slippage_pct=0.0005),
    "ETHUSDT":  CostModel(spread=0.0, commission_pct=0.001, slippage_pct=0.0005),
    "SOLUSDT":  CostModel(spread=0.0, commission_pct=0.001, slippage_pct=0.0005),
    # Stocks — small commission
    "MSFT": CostModel(spread=0.01, commission_pct=0.0, slippage_pct=0.0003),
    "SPY":  CostModel(spread=0.01, commission_pct=0.0, slippage_pct=0.0002),
}

DEFAULT_COST = CostModel(spread=0.0, commission_pct=0.001, slippage_pct=0.0005)


def get_cost_model(symbol: str) -> CostModel:
    return COST_MODELS.get(symbol, DEFAULT_COST)
