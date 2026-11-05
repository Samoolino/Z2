"""Read-only CCXT Pro public order-book streaming.

This adapter intentionally exposes no private account or order methods. Reconnect
policy belongs to the supervising worker so every disconnect can invalidate stale
books before a new snapshot is accepted.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from importlib import import_module
from typing import Any, Self

from z2.core.edge import Level, OrderBook

SUPPORTED_PUBLIC_EXCHANGES = frozenset(
    {
        "binance",
        "bybit",
        "gateio",
        "htx",
        "kucoin",
        "mexc",
        "okx",
        "bitget",
        "kraken",
    }
)

ExchangeFactory = Callable[[str, dict[str, Any]], Any]


def _decimal(value: Any, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"order book {field} must be a positive finite decimal") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"order book {field} must be a positive finite decimal")
    return result


def normalize_ccxt_order_book(
    venue: str,
    symbol: str,
    raw: Mapping[str, Any],
    *,
    received_ts: datetime,
) -> OrderBook:
    """Convert one unified CCXT order-book result into Z2's Decimal model.

    CCXT's unified order-book timestamp is milliseconds since the Unix epoch.
    Missing timestamps are rejected; local receive time is never substituted.
    """
    if not venue or not symbol or not isinstance(raw, Mapping):
        raise ValueError("venue, symbol and a valid order book are required")
    if received_ts.tzinfo is None or received_ts.utcoffset() is None:
        raise ValueError("received timestamp must be timezone-aware")

    returned_symbol = raw.get("symbol")
    if returned_symbol is not None and returned_symbol != symbol:
        raise ValueError(f"order book symbol mismatch: expected {symbol}")

    raw_timestamp = raw.get("timestamp")
    if raw_timestamp is None or isinstance(raw_timestamp, bool):
        raise ValueError("exchange timestamp is required")
    try:
        timestamp_ms = Decimal(str(raw_timestamp))
        if not timestamp_ms.is_finite() or timestamp_ms <= 0:
            raise ValueError
        exchange_ts = datetime.fromtimestamp(float(timestamp_ms / Decimal(1000)), tz=UTC)
    except (InvalidOperation, TypeError, ValueError, OverflowError, OSError) as exc:
        raise ValueError("exchange timestamp is invalid") from exc

    def levels_for(side: str) -> tuple[Level, ...]:
        levels = raw.get(side)
        if not isinstance(levels, (list, tuple)) or not levels:
            raise ValueError(f"order book {side} must contain at least one level")
        normalized: list[Level] = []
        for item in levels:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                raise ValueError(f"order book {side} contains a malformed level")
            normalized.append(
                Level(
                    price=_decimal(item[0], field=f"{side} price"),
                    quantity=_decimal(item[1], field=f"{side} quantity"),
                )
            )
        return tuple(normalized)

    latency_ms = Decimal(str((received_ts - exchange_ts).total_seconds() * 1000))
    return OrderBook(
        venue=venue,
        symbol=symbol,
        bids=levels_for("bids"),
        asks=levels_for("asks"),
        exchange_ts=exchange_ts,
        received_ts=received_ts,
        latency_ms=latency_ms,
    )


def _default_exchange_factory(exchange_id: str, config: dict[str, Any]) -> Any:
    """Load CCXT Pro lazily so importing Z2 does not require network adapters."""
    try:
        ccxtpro = import_module("ccxt.pro")
    except ImportError as exc:
        raise RuntimeError("Install the 'ccxt' package to enable CCXT Pro streams") from exc
    exchange_class = getattr(ccxtpro, exchange_id, None)
    if exchange_class is None:
        raise ValueError(f"CCXT Pro adapter is unavailable for {exchange_id}")
    if not callable(exchange_class):
        raise TypeError(f"CCXT Pro adapter for {exchange_id} is not callable")
    return exchange_class(config)


class CCXTProPublicAdapter:
    """One venue's public spot order-book stream; no API credentials are accepted."""

    def __init__(
        self,
        exchange_id: str,
        *,
        exchange_factory: ExchangeFactory | None = None,
    ) -> None:
        if exchange_id not in SUPPORTED_PUBLIC_EXCHANGES:
            raise ValueError(f"exchange {exchange_id!r} is not allowlisted")
        self.exchange_id = exchange_id
        self._exchange_factory = exchange_factory or _default_exchange_factory
        self._exchange: Any | None = None

    async def connect(self) -> None:
        if self._exchange is not None:
            return

        # Public-only configuration: deliberately no apiKey, secret or password.
        config: dict[str, Any] = {
            "enableRateLimit": True,
            "timeout": 10_000,
            "options": {"defaultType": "spot"},
        }
        exchange = self._exchange_factory(self.exchange_id, config)
        self._exchange = exchange
        try:
            await exchange.load_markets()
            capabilities = getattr(exchange, "has", {})
            if not isinstance(capabilities, Mapping) or capabilities.get("watchOrderBook") is not True:
                raise RuntimeError(f"{self.exchange_id} does not advertise watchOrderBook")
        except Exception:
            await self.close()
            raise

    def _require_active_spot_market(self, symbol: str) -> None:
        if self._exchange is None:
            raise RuntimeError("adapter is not connected")
        markets = getattr(self._exchange, "markets", {})
        market = markets.get(symbol) if isinstance(markets, Mapping) else None
        is_spot = isinstance(market, Mapping) and (
            market.get("spot") is True or market.get("type") == "spot"
        )
        if (
            not is_spot
            or market.get("contract") is True
            or market.get("active") is not True
        ):
            raise ValueError(f"{symbol} is not a verified active spot market on {self.exchange_id}")

    async def watch_order_book(
        self,
        symbol: str,
        *,
        limit: int = 20,
    ) -> AsyncIterator[OrderBook]:
        """Yield each new book; propagate disconnects so the supervisor can fail closed."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("order-book limit must be an integer between 1 and 100")
        await self.connect()
        self._require_active_spot_market(symbol)

        while True:
            raw = await self._exchange.watch_order_book(symbol, limit)
            yield normalize_ccxt_order_book(
                self.exchange_id,
                symbol,
                raw,
                received_ts=datetime.now(UTC),
            )

    async def close(self) -> None:
        exchange, self._exchange = self._exchange, None
        if exchange is not None:
            await exchange.close()

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()
