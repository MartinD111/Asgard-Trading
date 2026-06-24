"""
ExecutionBroker — abstract interface for all broker implementations.

Every implementation (Paper, OANDA, Coinbase) must satisfy this interface
so the engine can swap brokers at runtime without code changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderResult:
    broker_order_id: str
    status: str          # FILLED | PARTIAL | PENDING | REJECTED | CANCELLED
    filled_price: float
    filled_qty: float
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True when the order resulted in at least a partial fill."""
        return self.status in ("FILLED", "PARTIAL")


class ExecutionBroker(ABC):
    """Minimal interface every broker implementation must satisfy."""

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,                         # "BUY" | "SELL"
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> OrderResult: ...

    @abstractmethod
    async def close_position(
        self,
        broker_order_id: str,
        symbol: str,
        quantity: float,
    ) -> OrderResult: ...

    @abstractmethod
    async def get_balance(self) -> float: ...

    @abstractmethod
    async def get_open_positions(self) -> list[dict]: ...

    @abstractmethod
    async def get_order_status(self, broker_order_id: str, symbol: str) -> OrderResult:
        """Poll the broker for the current status of a previously placed order."""
        ...
