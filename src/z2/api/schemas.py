from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from z2.core.edge import Level, OrderBook, Policy


class LevelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: Decimal
    quantity: Decimal


class BookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    venue: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=3, max_length=40)
    bids: list[LevelIn]
    asks: list[LevelIn]
    exchange_ts: datetime
    received_ts: datetime
    latency_ms: Decimal = Field(ge=0)


class EvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    buy_book: BookIn
    sell_book: BookIn
    base_quantity: Decimal = Field(gt=0)
    buy_fee_bps: Decimal = Field(ge=0)
    sell_fee_bps: Decimal = Field(ge=0)
    policy: dict[str, Decimal] = Field(default_factory=dict)
    now: datetime


def to_order_book(value: BookIn) -> OrderBook:
    return OrderBook(
        venue=value.venue,
        symbol=value.symbol,
        bids=tuple(Level(price=x.price, quantity=x.quantity) for x in value.bids),
        asks=tuple(Level(price=x.price, quantity=x.quantity) for x in value.asks),
        exchange_ts=value.exchange_ts,
        received_ts=value.received_ts,
        latency_ms=value.latency_ms,
    )


def to_policy(value: dict[str, Decimal]) -> Policy:
    allowed = set(Policy.__dataclass_fields__)
    if set(value) - allowed:
        raise ValueError("unknown policy field")
    return Policy(**value)
