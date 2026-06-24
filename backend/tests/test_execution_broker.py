"""
Unit tests for the M4 broker execution layer.

No live broker accounts or network calls required:
  - OrderResult / ExecutionBroker base contract
  - PaperBroker (mocked Redis)
  - ExecutionRouter symbol mapping
  - OandaBroker / CoinbaseBroker construction guards
  - Kill-switch and drawdown logic (pure)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from brokers.base import ExecutionBroker, OrderResult
from brokers.paper import PaperBroker
from brokers.router import SYMBOL_BROKER


# ─── OrderResult ──────────────────────────────────────────────────────────────

class TestOrderResult:
    def test_filled_is_ok(self):
        r = OrderResult(broker_order_id="x", status="FILLED", filled_price=1.0, filled_qty=1.0)
        assert r.ok is True

    def test_partial_is_ok(self):
        r = OrderResult(broker_order_id="x", status="PARTIAL", filled_price=1.0, filled_qty=0.5)
        assert r.ok is True

    def test_rejected_is_not_ok(self):
        r = OrderResult(broker_order_id="", status="REJECTED", filled_price=0.0, filled_qty=0.0, error="bad")
        assert r.ok is False

    def test_pending_is_not_ok(self):
        r = OrderResult(broker_order_id="x", status="PENDING", filled_price=0.0, filled_qty=0.0)
        assert r.ok is False

    def test_cancelled_is_not_ok(self):
        r = OrderResult(broker_order_id="x", status="CANCELLED", filled_price=0.0, filled_qty=0.0)
        assert r.ok is False

    def test_error_field_optional(self):
        r = OrderResult(broker_order_id="y", status="FILLED", filled_price=2.0, filled_qty=1.0)
        assert r.error is None

    def test_dataclass_equality(self):
        a = OrderResult("id", "FILLED", 1.5, 2.0)
        b = OrderResult("id", "FILLED", 1.5, 2.0)
        assert a == b


# ─── ExecutionBroker ABC ──────────────────────────────────────────────────────

def test_cannot_instantiate_abstract_broker():
    with pytest.raises(TypeError):
        ExecutionBroker()  # type: ignore[abstract]


# ─── PaperBroker ─────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=b"50000.0")
    return r


@pytest.mark.asyncio
async def test_paper_broker_place_order_filled(mock_redis):
    broker = PaperBroker(redis=mock_redis)
    result = await broker.place_order("BTCUSDT", "BUY", 0.01)
    assert result.ok
    assert result.status == "FILLED"
    assert result.filled_price == 50000.0
    assert result.filled_qty == 0.01


@pytest.mark.asyncio
async def test_paper_broker_place_order_sell(mock_redis):
    result = await PaperBroker(redis=mock_redis).place_order("BTCUSDT", "SELL", 0.5)
    assert result.ok
    assert result.filled_price == 50000.0


@pytest.mark.asyncio
async def test_paper_broker_close_position(mock_redis):
    broker = PaperBroker(redis=mock_redis)
    result = await broker.close_position("paper-abc", "BTCUSDT", 0.01)
    assert result.ok
    assert result.filled_price == 50000.0


@pytest.mark.asyncio
async def test_paper_broker_order_id_unique(mock_redis):
    broker = PaperBroker(redis=mock_redis)
    r1 = await broker.place_order("BTCUSDT", "BUY", 1.0)
    r2 = await broker.place_order("BTCUSDT", "BUY", 1.0)
    assert r1.broker_order_id != r2.broker_order_id


@pytest.mark.asyncio
async def test_paper_broker_missing_price_falls_back(mock_redis):
    mock_redis.get.return_value = None
    result = await PaperBroker(redis=mock_redis).place_order("BTCUSDT", "BUY", 1.0)
    assert result.ok
    assert result.filled_price == 0.0


@pytest.mark.asyncio
async def test_paper_broker_get_balance(mock_redis):
    broker = PaperBroker(redis=mock_redis, balance=75_000.0)
    assert await broker.get_balance() == 75_000.0


@pytest.mark.asyncio
async def test_paper_broker_get_open_positions_empty(mock_redis):
    result = await PaperBroker(redis=mock_redis).get_open_positions()
    assert result == []


# ─── ExecutionRouter symbol mapping ──────────────────────────────────────────

class TestSymbolBrokerMapping:
    def test_oanda_symbols(self):
        for sym in ("EUR_USD", "XAU_USD", "XAG_USD"):
            assert SYMBOL_BROKER[sym] == "oanda", f"{sym} should route to oanda"

    def test_coinbase_symbols(self):
        for sym in ("BTCUSDT", "ETHUSDT"):
            assert SYMBOL_BROKER[sym] == "coinbase", f"{sym} should route to coinbase"

    def test_unknown_symbol_not_in_map(self):
        assert "AAPL" not in SYMBOL_BROKER
        assert "SPY" not in SYMBOL_BROKER


@pytest.mark.asyncio
async def test_router_returns_paper_broker_when_live_mode_off():
    """When live_mode is not set for a user, router returns PaperBroker."""
    from brokers.router import get_broker_for_user

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=b"false")   # live_mode = false
    mock_db = AsyncMock()

    broker = await get_broker_for_user("user-uuid", "EUR_USD", mock_db, mock_r)
    assert isinstance(broker, PaperBroker)


@pytest.mark.asyncio
async def test_router_returns_paper_broker_for_unmapped_symbol():
    """Symbols with no broker entry always route to PaperBroker."""
    from brokers.router import get_broker_for_user

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=b"true")   # live_mode = true
    mock_db = AsyncMock()

    broker = await get_broker_for_user("user-uuid", "AAPL", mock_db, mock_r)
    assert isinstance(broker, PaperBroker)


# ─── OandaBroker construction ─────────────────────────────────────────────────

def test_oanda_rejects_invalid_environment():
    from brokers.oanda import OandaBroker
    with pytest.raises(ValueError, match="environment"):
        OandaBroker(api_key="k", account_id="acc", environment="sandbox")


def test_oanda_practice_base_url():
    from brokers.oanda import OandaBroker, _BASE_URL
    broker = OandaBroker(api_key="k", account_id="acc", environment="practice")
    assert broker._base == _BASE_URL["practice"]


def test_oanda_live_base_url():
    from brokers.oanda import OandaBroker, _BASE_URL
    broker = OandaBroker(api_key="k", account_id="acc", environment="live")
    assert broker._base == _BASE_URL["live"]


# ─── CoinbaseBroker construction ──────────────────────────────────────────────

def test_coinbase_symbol_translation():
    from brokers.coinbase import _to_product_id
    assert _to_product_id("BTCUSDT") == "BTC-USDT"
    assert _to_product_id("ETHUSDT") == "ETH-USDT"


def test_coinbase_unknown_symbol_passthrough():
    from brokers.coinbase import _to_product_id
    assert _to_product_id("XYZ-ABC") == "XYZ-ABC"


@pytest.mark.asyncio
async def test_coinbase_close_position_returns_rejected():
    """Coinbase close_position always returns REJECTED (use opposite-side order instead)."""
    from brokers.coinbase import CoinbaseBroker
    broker = CoinbaseBroker(api_key="k", api_secret="s")
    result = await broker.close_position("order-id", "BTCUSDT", 0.1)
    assert result.status == "REJECTED"
    assert result.error is not None


# ─── get_order_status — OANDA ─────────────────────────────────────────────────

def _httpx_ctx(status_code: int, json_data: dict):
    """Helper: returns a mock async context manager for httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestGetOrderStatus:
    # ── OANDA ────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_oanda_open_trade_returns_filled(self):
        from brokers.oanda import OandaBroker
        broker = OandaBroker(api_key="k", account_id="acc", environment="practice")
        json_body = {"trade": {"state": "OPEN", "price": "1905.50", "currentUnits": "0.1"}}

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("trade-001", "XAU_USD")

        assert result.status == "FILLED"
        assert result.filled_price == pytest.approx(1905.50)
        assert result.filled_qty == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_oanda_closed_trade_returns_filled(self):
        from brokers.oanda import OandaBroker
        broker = OandaBroker(api_key="k", account_id="acc", environment="practice")
        json_body = {"trade": {"state": "CLOSED", "price": "1.1000", "currentUnits": "10000"}}

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("trade-002", "EUR_USD")

        assert result.status == "FILLED"

    @pytest.mark.asyncio
    async def test_oanda_404_returns_cancelled(self):
        from brokers.oanda import OandaBroker
        broker = OandaBroker(api_key="k", account_id="acc", environment="practice")

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(404, {})):
            result = await broker.get_order_status("trade-missing", "XAU_USD")

        assert result.status == "CANCELLED"

    @pytest.mark.asyncio
    async def test_oanda_unknown_state_returns_pending(self):
        from brokers.oanda import OandaBroker
        broker = OandaBroker(api_key="k", account_id="acc", environment="practice")
        json_body = {"trade": {"state": "PENDING_FILL", "price": "0", "currentUnits": "0"}}

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("trade-003", "XAU_USD")

        assert result.status == "PENDING"

    # ── Coinbase ─────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_coinbase_filled_status_returns_filled(self):
        from brokers.coinbase import CoinbaseBroker
        broker = CoinbaseBroker(api_key="k", api_secret="s")
        json_body = {
            "order": {
                "status": "FILLED",
                "average_filled_price": "65000.00",
                "filled_size": "0.001",
            }
        }

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("cb-order-1", "BTCUSDT")

        assert result.status == "FILLED"
        assert result.filled_price == pytest.approx(65000.0)
        assert result.filled_qty == pytest.approx(0.001)

    @pytest.mark.asyncio
    async def test_coinbase_cancelled_status_returns_cancelled(self):
        from brokers.coinbase import CoinbaseBroker
        broker = CoinbaseBroker(api_key="k", api_secret="s")
        json_body = {"order": {"status": "CANCELLED", "average_filled_price": "0", "filled_size": "0"}}

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("cb-order-2", "BTCUSDT")

        assert result.status == "CANCELLED"

    @pytest.mark.asyncio
    async def test_coinbase_expired_status_returns_cancelled(self):
        from brokers.coinbase import CoinbaseBroker
        broker = CoinbaseBroker(api_key="k", api_secret="s")
        json_body = {"order": {"status": "EXPIRED", "average_filled_price": "0", "filled_size": "0"}}

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("cb-order-3", "BTCUSDT")

        assert result.status == "CANCELLED"

    @pytest.mark.asyncio
    async def test_coinbase_open_status_returns_pending(self):
        from brokers.coinbase import CoinbaseBroker
        broker = CoinbaseBroker(api_key="k", api_secret="s")
        json_body = {"order": {"status": "OPEN", "average_filled_price": "0", "filled_size": "0"}}

        with patch("httpx.AsyncClient", return_value=_httpx_ctx(200, json_body)):
            result = await broker.get_order_status("cb-order-4", "BTCUSDT")

        assert result.status == "PENDING"
