"""CCXT connection and order-book adapters. This module never submits orders."""
from __future__ import annotations

import importlib
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from z2.core.edge import Level, OrderBook

MarketType = Literal["spot", "swap", "future"]


@dataclass(frozen=True, slots=True)
class ExchangeConfig:
    exchange_id: str
    market_type: MarketType = "spot"
    api_key: str | None = field(default=None, repr=False)
    secret: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    uid: str | None = field(default=None, repr=False)
    sandbox: bool = True
    timeout_ms: int = 5_000
    enable_rate_limit: bool = True

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9_]+", self.exchange_id):
            raise ValueError("exchange_id must be a CCXT exchange identifier")
        if self.market_type not in ("spot", "swap", "future"):
            raise ValueError("market_type must be spot, swap or future")
        if bool(self.api_key) != bool(self.secret):
            raise ValueError("api_key and secret must be supplied together")
        if self.timeout_ms < 1 or self.timeout_ms > 120_000:
            raise ValueError("timeout_ms must be between 1 and 120000")


def create_exchange(
    config: ExchangeConfig,
    *,
    streaming: bool = False,
    ccxt_module: Any | None = None,
) -> Any:
    """Create one isolated CCXT client; sandbox mode is set before any API call.

    Use a separate client instance for each private keypair. The scanner should
    use credential-free public clients, while trade credentials remain server-side.
    """
    module = ccxt_module or importlib.import_module(
        "ccxt.pro" if streaming else "ccxt.async_support"
    )
    exchange_class = getattr(module, config.exchange_id, None)
    if exchange_class is None or not callable(exchange_class):
        raise ValueError(f"unsupported CCXT exchange: {config.exchange_id}")

    params: dict[str, Any] = {
        "enableRateLimit": config.enable_rate_limit,
        "timeout": config.timeout_ms,
        "options": {"defaultType": config.market_type},
    }
    if config.api_key and config.secret:
        params["apiKey"] = config.api_key
        params["secret"] = config.secret
    if config.password:
        params["password"] = config.password
    if config.uid:
        params["uid"] = config.uid

    exchange = exchange_class(params)
    if config.sandbox:
        set_sandbox_mode = getattr(exchange, "set_sandbox_mode", None)
        if not callable(set_sandbox_mode):
            raise ValueError(f"{config.exchange_id} does not expose sandbox mode")
        set_sandbox_mode(True)
    return exchange


def normalize_order_book(
    *,
    exchange_id: str,
    symbol: str,
    raw: dict[str, Any],
    received_at: datetime,
    latency_ms: Decimal,
) -> OrderBook:
    """Convert a CCXT order book to Z2's strict UTC/Decimal contract.

    Missing exchange timestamps are rejected rather than replaced with local time.
    That fail-closed rule prevents an old book from looking fresh.
    """
    timestamp_ms = raw.get("timestamp")
    if timestamp_ms is None:
        raise ValueError("exchange order book timestamp is required")
    if (
        isinstance(timestamp_ms, bool)
        or not isinstance(timestamp_ms, (int, float))
        or timestamp_ms <= 0
    ):
        raise ValueError("exchange order book timestamp must be positive milliseconds")
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("received_at must be timezone-aware")
    if not symbol or raw.get("symbol", symbol) != symbol:
        raise ValueError("order book symbol does not match requested symbol")

    try:
        bids = tuple(
            Level(Decimal(str(price)), Decimal(str(quantity)))
            for price, quantity in raw["bids"]
        )
        asks = tuple(
            Level(Decimal(str(price)), Decimal(str(quantity)))
            for price, quantity in raw["asks"]
        )
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError("order book levels are malformed") from exc
    if not bids or not asks:
        raise ValueError("both sides of the order book are required")

    exchange_ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    return OrderBook(
        venue=exchange_id,
        symbol=symbol,
        bids=bids,
        asks=asks,
        exchange_ts=exchange_ts,
        received_ts=received_at.astimezone(UTC),
        latency_ms=latency_ms,
    )


async def fetch_order_book(
    exchange: Any,
    *,
    exchange_id: str,
    symbol: str,
    limit: int = 20,
) -> OrderBook:
    if limit < 1 or limit > 1000:
        raise ValueError("order book limit must be between 1 and 1000")
    started = time.perf_counter()
    raw = await exchange.fetch_order_book(symbol, limit)
    latency_ms = Decimal(str((time.perf_counter() - started) * 1000))
    return normalize_order_book(
        exchange_id=exchange_id,
        symbol=symbol,
        raw=raw,
        received_at=datetime.now(UTC),
        latency_ms=latency_ms,
    )


async def watch_order_book(
    exchange: Any,
    *,
    exchange_id: str,
    symbol: str,
    limit: int = 20,
) -> OrderBook:
    if limit < 1 or limit > 1000:
        raise ValueError("order book limit must be between 1 and 1000")
    started = time.perf_counter()
    raw = await exchange.watch_order_book(symbol, limit)
    latency_ms = Decimal(str((time.perf_counter() - started) * 1000))
    return normalize_order_book(
        exchange_id=exchange_id,
        symbol=symbol,
        raw=raw,
        received_at=datetime.now(UTC),
        latency_ms=latency_ms,
    )


async def close_exchange(exchange: Any) -> None:
    """Close a CCXT async/Pro client and release its sockets/session."""
    close = getattr(exchange, "close", None)
    if callable(close):
        await close()
