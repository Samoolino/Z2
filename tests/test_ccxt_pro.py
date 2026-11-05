import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from z2.adapters.ccxt_pro import CCXTProPublicAdapter, normalize_ccxt_order_book

NOW = datetime(2026, 11, 5, 7, 0, tzinfo=UTC)


def raw_book(*, timestamp=None, symbol="BTC/USDT"):
    if timestamp is None:
        timestamp = NOW.timestamp() * 1000
    return {
        "symbol": symbol,
        "timestamp": timestamp,
        "bids": [[D(100), D("1.5")]],
        "asks": [[D(101), D("2.0")]],
    }


class FakeExchange:
    def __init__(self, *, market=None, book=None):
        self.markets = {
            "BTC/USDT": market or {"spot": True, "contract": False, "active": True}
        }
        self.has = {"watchOrderBook": True}
        self.book = book or raw_book()
        self.loaded = False
        self.closed = False
        self.last_symbol = None
        self.last_limit = None

    async def load_markets(self):
        self.loaded = True
        return self.markets

    async def watch_order_book(self, symbol, limit=20):
        self.last_symbol = symbol
        self.last_limit = limit
        return self.book

    async def close(self):
        self.closed = True


def test_normalize_ccxt_book_uses_exchange_timestamp_and_decimal_levels():
    received = NOW + timedelta(milliseconds=12)
    book = normalize_ccxt_order_book(
        "binance",
        "BTC/USDT",
        raw_book(),
        received_ts=received,
    )

    assert book.venue == "binance"
    assert book.symbol == "BTC/USDT"
    assert book.exchange_ts == NOW
    assert book.received_ts == received
    assert book.latency_ms == D(12)
    assert book.bids[0].price == D(100)
    assert book.asks[0].quantity == D("2.0")


def test_normalize_rejects_missing_exchange_timestamp():
    with pytest.raises(ValueError, match="exchange timestamp"):
        normalize_ccxt_order_book(
            "binance",
            "BTC/USDT",
            {**raw_book(), "timestamp": None},
            received_ts=NOW,
        )


def test_normalize_rejects_symbol_mismatch():
    with pytest.raises(ValueError, match="symbol mismatch"):
        normalize_ccxt_order_book(
            "binance",
            "BTC/USDT",
            raw_book(symbol="ETH/USDT"),
            received_ts=NOW,
        )


def test_normalize_rejects_empty_or_invalid_book_levels():
    with pytest.raises(ValueError, match="order book"):
        normalize_ccxt_order_book(
            "binance",
            "BTC/USDT",
            {**raw_book(), "asks": []},
            received_ts=NOW,
        )

    with pytest.raises(ValueError, match="positive finite"):
        normalize_ccxt_order_book(
            "binance",
            "BTC/USDT",
            {**raw_book(), "bids": [[D("NaN"), D(1)]]},
            received_ts=NOW,
        )


def test_adapter_rejects_exchange_outside_allowlist():
    with pytest.raises(ValueError, match="not allowlisted"):
        CCXTProPublicAdapter("unknown-venue")


def test_adapter_streams_public_books_and_closes_exchange():
    fake = FakeExchange()
    factory_calls = []

    def factory(exchange_id, config):
        factory_calls.append((exchange_id, config))
        return fake

    adapter = CCXTProPublicAdapter("binance", exchange_factory=factory)

    async def scenario():
        async with adapter:
            stream = adapter.watch_order_book("BTC/USDT", limit=10)
            snapshot = await anext(stream)
            await stream.aclose()
            return snapshot

    snapshot = asyncio.run(scenario())

    assert snapshot.symbol == "BTC/USDT"
    assert fake.loaded is True
    assert fake.closed is True
    assert fake.last_symbol == "BTC/USDT"
    assert fake.last_limit == 10
    assert len(factory_calls) == 1
    exchange_id, config = factory_calls[0]
    assert exchange_id == "binance"
    assert "apiKey" not in config
    assert "secret" not in config
    assert config["options"]["defaultType"] == "spot"


def test_adapter_rejects_non_spot_market_before_streaming():
    fake = FakeExchange(market={"spot": False, "type": "swap", "contract": True, "active": True})
    adapter = CCXTProPublicAdapter("binance", exchange_factory=lambda *_: fake)

    async def scenario():
        async with adapter:
            stream = adapter.watch_order_book("BTC/USDT")
            with pytest.raises(ValueError, match="active spot"):
                await anext(stream)

    asyncio.run(scenario())


def test_adapter_rejects_inactive_market_before_streaming():
    fake = FakeExchange(market={"spot": True, "contract": False, "active": False})
    adapter = CCXTProPublicAdapter("binance", exchange_factory=lambda *_: fake)

    async def scenario():
        async with adapter:
            stream = adapter.watch_order_book("BTC/USDT")
            with pytest.raises(ValueError, match="active spot"):
                await anext(stream)

    asyncio.run(scenario())
