from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from z2.exchanges.ccxt_adapter import (
    ExchangeConfig,
    create_exchange,
    normalize_order_book,
)


class FakeExchange:
    def __init__(self, config):
        self.config = config
        self.sandbox = False

    def set_sandbox_mode(self, enabled):
        self.sandbox = enabled


def test_exchange_factory_defaults_to_sandbox_and_rate_limit():
    module = SimpleNamespace(binance=FakeExchange)
    exchange = create_exchange(ExchangeConfig("binance"), ccxt_module=module)
    assert exchange.sandbox is True
    assert exchange.config["enableRateLimit"] is True
    assert exchange.config["options"]["defaultType"] == "spot"
    assert "apiKey" not in exchange.config
    assert "secret" not in exchange.config


def test_exchange_factory_includes_server_side_credentials_and_market_type():
    module = SimpleNamespace(bybit=FakeExchange)
    exchange = create_exchange(
        ExchangeConfig(
            "bybit", market_type="swap", api_key="public", secret="private",
            password="passphrase", uid="account", sandbox=False,
        ),
        ccxt_module=module,
    )
    assert exchange.config["apiKey"] == "public"
    assert exchange.config["secret"] == "private"
    assert exchange.config["password"] == "passphrase"
    assert exchange.config["uid"] == "account"
    assert exchange.config["options"]["defaultType"] == "swap"
    assert exchange.sandbox is False


def test_exchange_factory_selects_ccxt_pro_for_streaming(monkeypatch):
    captured = []
    module = SimpleNamespace(okx=FakeExchange)

    def fake_import(name):
        captured.append(name)
        return module

    monkeypatch.setattr("z2.exchanges.ccxt_adapter.importlib.import_module", fake_import)
    create_exchange(ExchangeConfig("okx"), streaming=True)
    assert captured == ["ccxt.pro"]


def test_config_rejects_half_a_credential_pair():
    with pytest.raises(ValueError, match="supplied together"):
        ExchangeConfig("binance", api_key="only-public")


def test_config_rejects_invalid_exchange_identifier():
    with pytest.raises(ValueError, match="CCXT exchange identifier"):
        ExchangeConfig("../binance")


def test_config_hides_secrets_from_repr():
    rendered = repr(ExchangeConfig("binance", api_key="public", secret="private"))
    assert "public" not in rendered
    assert "private" not in rendered


def test_normalize_order_book_uses_exchange_timestamp_and_decimal_levels():
    received = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
    book = normalize_order_book(
        exchange_id="binance",
        symbol="BTC/USDT",
        raw={
            "symbol": "BTC/USDT",
            "timestamp": 1793869200000,
            "bids": [["99.10", "1.25"]],
            "asks": [["99.20", "2.5"]],
        },
        received_at=received,
        latency_ms=Decimal("4.5"),
    )
    assert book.venue == "binance"
    assert book.symbol == "BTC/USDT"
    assert book.bids[0].price == Decimal("99.10")
    assert book.asks[0].quantity == Decimal("2.5")
    assert book.exchange_ts.tzinfo == UTC
    assert book.received_ts == received


def test_normalize_order_book_rejects_missing_exchange_timestamp():
    with pytest.raises(ValueError, match="timestamp is required"):
        normalize_order_book(
            exchange_id="binance", symbol="BTC/USDT",
            raw={"bids": [["99", "1"]], "asks": [["100", "1"]]},
            received_at=datetime.now(UTC), latency_ms=Decimal(1),
        )


def test_normalize_order_book_rejects_symbol_mismatch():
    with pytest.raises(ValueError, match="does not match"):
        normalize_order_book(
            exchange_id="binance", symbol="BTC/USDT",
            raw={"symbol": "ETH/USDT", "timestamp": 1793869200000,
                 "bids": [["99", "1"]], "asks": [["100", "1"]]},
            received_at=datetime.now(UTC), latency_ms=Decimal(1),
        )


def test_normalize_order_book_rejects_incomplete_depth():
    with pytest.raises(ValueError, match="both sides"):
        normalize_order_book(
            exchange_id="binance", symbol="BTC/USDT",
            raw={"timestamp": 1793869200000, "bids": [], "asks": [["100", "1"]]},
            received_at=datetime.now(UTC), latency_ms=Decimal(1),
        )
