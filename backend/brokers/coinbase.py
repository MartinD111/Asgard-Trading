"""
CoinbaseBroker — wraps the Coinbase Advanced Trade REST API v3.

Symbol translation: engine uses BTCUSDT/ETHUSDT; Coinbase uses BTC-USDT/ETH-USDT.
Authentication: HMAC-SHA256 signature over timestamp + method + path + body.

Keys are passed in at construction time from the decrypted broker_connections row.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Optional

import httpx

from brokers.base import ExecutionBroker, OrderResult

logger = logging.getLogger(__name__)

_BASE = "https://api.coinbase.com"

# Engine symbol → Coinbase product ID
_SYMBOL_MAP: dict[str, str] = {
    "BTCUSDT": "BTC-USDT",
    "ETHUSDT":  "ETH-USDT",
    "BTCUSD":   "BTC-USD",
    "ETHUSD":   "ETH-USD",
}


def _to_product_id(symbol: str) -> str:
    return _SYMBOL_MAP.get(symbol, symbol)


class CoinbaseBroker(ExecutionBroker):
    def __init__(self, api_key: str, api_secret: str):
        self._key = api_key
        self._secret = api_secret

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + path + body
        sig = hmac.new(
            self._secret.encode(),
            message.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return {
            "CB-ACCESS-KEY":       self._key,
            "CB-ACCESS-SIGN":      sig,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "Content-Type":        "application/json",
        }

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> OrderResult:
        product_id = _to_product_id(symbol)
        client_id = str(uuid.uuid4())
        path = "/api/v3/brokerage/orders"
        payload = {
            "client_order_id": client_id,
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "market_market_ioc": {"base_size": str(quantity)}
            },
        }
        body_str = json.dumps(payload)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_BASE}{path}",
                    content=body_str,
                    headers=self._headers("POST", path, body_str),
                )
            data = resp.json()
            if not data.get("success"):
                err = str(data.get("error_response", data))
                logger.error(f"Coinbase place_order failed: {err}")
                return OrderResult(
                    broker_order_id="", status="REJECTED",
                    filled_price=0.0, filled_qty=0.0, error=err,
                )
            order = data.get("success_response", {}).get("order", {})
            return OrderResult(
                broker_order_id=order.get("order_id", client_id),
                status="FILLED" if order.get("status") == "FILLED" else "PENDING",
                filled_price=float(order.get("average_filled_price", 0.0)),
                filled_qty=float(order.get("filled_size", quantity)),
            )
        except Exception as exc:
            logger.error(f"Coinbase place_order exception: {exc}")
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
        # Coinbase spot: close = market order in the opposite direction.
        # The caller (PositionManager) must know the original side to invert it.
        # For now, return a clear error so the caller falls back to paper settlement.
        return OrderResult(
            broker_order_id="",
            status="REJECTED",
            filled_price=0.0,
            filled_qty=0.0,
            error="Use place_order with the opposite side to close a Coinbase spot position",
        )

    async def get_balance(self) -> float:
        path = "/api/v3/brokerage/accounts"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE}{path}",
                    headers=self._headers("GET", path),
                )
            data = resp.json()
            for acc in data.get("accounts", []):
                if acc.get("currency") in ("USD", "USDT"):
                    return float(acc.get("available_balance", {}).get("value", 0.0))
            return 0.0
        except Exception as exc:
            logger.error(f"Coinbase get_balance exception: {exc}")
            return 0.0

    async def get_open_positions(self) -> list[dict]:
        path = "/api/v3/brokerage/orders/historical/batch"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE}{path}",
                    params={"order_status": "OPEN"},
                    headers=self._headers("GET", path),
                )
            data = resp.json()
            return [
                {
                    "broker_order_id": o["order_id"],
                    "symbol":         o["product_id"],
                    "side":           o["side"],
                    "quantity":       float(o.get("filled_size", 0.0)),
                    "entry_price":    float(o.get("average_filled_price", 0.0)),
                    "unrealized_pnl": 0.0,
                }
                for o in data.get("orders", [])
            ]
        except Exception as exc:
            logger.error(f"Coinbase get_open_positions exception: {exc}")
            return []

    async def get_order_status(self, broker_order_id: str, symbol: str) -> OrderResult:
        path = f"/api/v3/brokerage/orders/historical/{broker_order_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE}{path}",
                    headers=self._headers("GET", path),
                )
            data = resp.json()
            order = data.get("order", {})
            cb_status = order.get("status", "UNKNOWN")
            if cb_status == "FILLED":
                status = "FILLED"
            elif cb_status in ("CANCELLED", "EXPIRED", "FAILED"):
                status = "CANCELLED"
            else:
                status = "PENDING"
            return OrderResult(
                broker_order_id=broker_order_id,
                status=status,
                filled_price=float(order.get("average_filled_price", 0.0)),
                filled_qty=float(order.get("filled_size", 0.0)),
            )
        except Exception as exc:
            logger.error(f"Coinbase get_order_status exception: {exc}")
            return OrderResult(
                broker_order_id=broker_order_id, status="PENDING",
                filled_price=0.0, filled_qty=0.0, error=str(exc),
            )
