"""
OandaBroker — wraps the OANDA v20 REST API (practice + live).

Instrument names use OANDA format: EUR_USD, XAU_USD, XAG_USD.
Quantity is in units (1 unit EUR_USD = 1 EUR); positive = long, negative = short.

Keys are decrypted from the broker_connections table by the ExecutionRouter
and passed in at construction time — never stored in module state.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from brokers.base import ExecutionBroker, OrderResult

logger = logging.getLogger(__name__)

_BASE_URL = {
    "practice": "https://api-fxpractice.oanda.com",
    "live":     "https://api-fxtrade.oanda.com",
}


class OandaBroker(ExecutionBroker):
    def __init__(self, api_key: str, account_id: str, environment: str = "practice"):
        if environment not in _BASE_URL:
            raise ValueError(f"environment must be 'practice' or 'live', got {environment!r}")
        self._base = _BASE_URL[environment]
        self._account = account_id
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "Accept-Datetime-Format": "RFC3339",
        }

    def _url(self, path: str) -> str:
        return f"{self._base}/v3/accounts/{self._account}{path}"

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> OrderResult:
        units = int(quantity) if side == "BUY" else -int(quantity)
        body: dict = {
            "order": {
                "type": "MARKET",
                "instrument": symbol,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        if stop_loss:
            body["order"]["stopLossOnFill"] = {"price": f"{stop_loss:.5f}"}
        if take_profit:
            body["order"]["takeProfitOnFill"] = {"price": f"{take_profit:.5f}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._url("/orders"),
                    json=body,
                    headers=self._headers,
                )
            data = resp.json()
            if resp.status_code not in (200, 201):
                err = data.get("errorMessage", str(data))
                logger.error(f"OANDA place_order HTTP {resp.status_code}: {err}")
                return OrderResult(
                    broker_order_id="", status="REJECTED",
                    filled_price=0.0, filled_qty=0.0, error=err,
                )

            fill = data.get("orderFillTransaction", {})
            broker_id = fill.get("id", "")
            filled_price = float(fill.get("price", 0.0))
            filled_qty = abs(float(fill.get("units", quantity)))
            return OrderResult(
                broker_order_id=broker_id,
                status="FILLED",
                filled_price=filled_price,
                filled_qty=filled_qty,
            )
        except Exception as exc:
            logger.error(f"OANDA place_order exception: {exc}")
            return OrderResult(
                broker_order_id="", status="REJECTED",
                filled_price=0.0, filled_qty=0.0, error=str(exc),
            )

    async def close_position(
        self,
        broker_order_id: str,
        symbol: str,
        quantity: float,
    ) -> OrderResult:
        """Close an open trade by OANDA trade ID."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    self._url(f"/trades/{broker_order_id}/close"),
                    headers=self._headers,
                )
            data = resp.json()
            if resp.status_code != 200:
                err = data.get("errorMessage", str(data))
                logger.error(f"OANDA close_position HTTP {resp.status_code}: {err}")
                return OrderResult(
                    broker_order_id=broker_order_id, status="REJECTED",
                    filled_price=0.0, filled_qty=0.0, error=err,
                )
            fill = data.get("orderFillTransaction", {})
            return OrderResult(
                broker_order_id=fill.get("id", broker_order_id),
                status="FILLED",
                filled_price=float(fill.get("price", 0.0)),
                filled_qty=abs(float(fill.get("units", quantity))),
            )
        except Exception as exc:
            logger.error(f"OANDA close_position exception: {exc}")
            return OrderResult(
                broker_order_id=broker_order_id, status="REJECTED",
                filled_price=0.0, filled_qty=0.0, error=str(exc),
            )

    async def get_balance(self) -> float:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self._url("/summary"), headers=self._headers)
            data = resp.json()
            return float(data.get("account", {}).get("balance", 0.0))
        except Exception as exc:
            logger.error(f"OANDA get_balance exception: {exc}")
            return 0.0

    async def get_open_positions(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self._url("/openTrades"), headers=self._headers)
            data = resp.json()
            return [
                {
                    "broker_order_id": t["id"],
                    "symbol":         t["instrument"],
                    "side":           "BUY" if float(t["currentUnits"]) > 0 else "SELL",
                    "quantity":       abs(float(t["currentUnits"])),
                    "entry_price":    float(t["price"]),
                    "unrealized_pnl": float(t.get("unrealizedPL", 0.0)),
                }
                for t in data.get("trades", [])
            ]
        except Exception as exc:
            logger.error(f"OANDA get_open_positions exception: {exc}")
            return []

    async def get_order_status(self, broker_order_id: str, symbol: str) -> OrderResult:
        # OANDA uses FOK so orders fill or reject synchronously — but we support
        # polling the trade endpoint for correctness.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self._url(f"/trades/{broker_order_id}"),
                    headers=self._headers,
                )
            if resp.status_code == 404:
                return OrderResult(
                    broker_order_id=broker_order_id, status="CANCELLED",
                    filled_price=0.0, filled_qty=0.0,
                )
            data = resp.json()
            trade = data.get("trade", {})
            state = trade.get("state", "")
            status = "FILLED" if state in ("OPEN", "CLOSED") else "PENDING"
            return OrderResult(
                broker_order_id=broker_order_id,
                status=status,
                filled_price=float(trade.get("price", 0.0)),
                filled_qty=abs(float(trade.get("currentUnits", 0.0))),
            )
        except Exception as exc:
            logger.error(f"OANDA get_order_status exception: {exc}")
            return OrderResult(
                broker_order_id=broker_order_id, status="PENDING",
                filled_price=0.0, filled_qty=0.0, error=str(exc),
            )
