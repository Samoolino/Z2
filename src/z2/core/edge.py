from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

BPS = Decimal("10000")
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Level:
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class OrderBook:
    venue: str
    symbol: str
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    exchange_ts: datetime
    received_ts: datetime
    latency_ms: Decimal


@dataclass(frozen=True, slots=True)
class Policy:
    min_expected_net_bps: Decimal = Decimal("5")
    min_worst_case_net_bps: Decimal = Decimal("1")
    max_book_age_ms: Decimal = Decimal("500")
    max_book_skew_ms: Decimal = Decimal("150")
    max_latency_ms: Decimal = Decimal("100")
    slippage_reserve_bps: Decimal = Decimal("2")
    max_notional_quote: Decimal = Decimal("100")


@dataclass(frozen=True, slots=True)
class Assessment:
    eligible: bool
    reasons: tuple[str, ...]
    buy_quote_cost: Decimal
    sell_quote_proceeds: Decimal
    expected_net_quote: Decimal
    worst_case_net_quote: Decimal
    expected_net_bps: Decimal
    worst_case_net_bps: Decimal
    book_age_ms: Decimal
    book_skew_ms: Decimal


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _valid_levels(levels: Iterable[Level]) -> bool:
    return all(level.price.is_finite() and level.quantity.is_finite()
               and level.price > ZERO and level.quantity > ZERO for level in levels)


def _walk(levels: tuple[Level, ...], quantity: Decimal, *, asks: bool) -> Decimal | None:
    ordered = sorted(levels, key=lambda x: x.price, reverse=not asks)
    remaining = quantity
    quote = ZERO
    for level in ordered:
        take = min(remaining, level.quantity)
        quote += take * level.price
        remaining -= take
        if remaining == ZERO:
            return quote
    return None


def _age_ms(book: OrderBook, now: datetime) -> Decimal:
    exchange_age = Decimal(str((now - book.exchange_ts).total_seconds() * 1000))
    receive_age = Decimal(str((now - book.received_ts).total_seconds() * 1000))
    return max(exchange_age, receive_age)


def _rejected(reasons: list[str], age: Decimal = ZERO, skew: Decimal = ZERO) -> Assessment:
    return Assessment(False, tuple(reasons), ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, age, skew)


def assess_cross_exchange(
    buy_book: OrderBook,
    sell_book: OrderBook,
    base_quantity: Decimal,
    buy_fee_bps: Decimal,
    sell_fee_bps: Decimal,
    policy: Policy,
    now: datetime,
) -> Assessment:
    """Assess a pre-funded spot buy/sell route. This function never submits orders."""
    reasons: list[str] = []

    if not _aware(now) or not _aware(buy_book.exchange_ts) or not _aware(buy_book.received_ts) \
            or not _aware(sell_book.exchange_ts) or not _aware(sell_book.received_ts):
        return _rejected(["timestamps_must_be_timezone_aware"])

    numeric = [
        base_quantity, buy_fee_bps, sell_fee_bps,
        policy.min_expected_net_bps, policy.min_worst_case_net_bps,
        policy.max_book_age_ms, policy.max_book_skew_ms, policy.max_latency_ms,
        policy.slippage_reserve_bps, policy.max_notional_quote,
        buy_book.latency_ms, sell_book.latency_ms,
    ]
    if any(not x.is_finite() for x in numeric):
        return _rejected(["non_finite_numeric_input"])
    if base_quantity <= ZERO:
        reasons.append("base_quantity_must_be_positive")
    if buy_fee_bps < ZERO or sell_fee_bps < ZERO:
        reasons.append("fees_must_be_non_negative")
    if any(x < ZERO for x in numeric[3:]):
        reasons.append("policy_and_latency_values_must_be_non_negative")
    if not buy_book.venue or not sell_book.venue or buy_book.venue == sell_book.venue:
        reasons.append("distinct_named_venues_required")
    if buy_book.symbol != sell_book.symbol or not buy_book.symbol:
        reasons.append("matching_symbol_required")
    if not _valid_levels(buy_book.asks) or not _valid_levels(sell_book.bids):
        reasons.append("invalid_order_book_levels")

    age_buy = _age_ms(buy_book, now)
    age_sell = _age_ms(sell_book, now)
    exchange_skew = abs((buy_book.exchange_ts - sell_book.exchange_ts).total_seconds())
    receive_skew = abs((buy_book.received_ts - sell_book.received_ts).total_seconds())
    skew = Decimal(str(max(exchange_skew, receive_skew) * 1000))
    age = max(age_buy, age_sell)
    if any(ts > now for ts in (
        buy_book.exchange_ts, buy_book.received_ts,
        sell_book.exchange_ts, sell_book.received_ts,
    )):
        reasons.append("future_or_clock_skewed_book_timestamp")
    if age > policy.max_book_age_ms:
        reasons.append("stale_order_book")
    if skew > policy.max_book_skew_ms:
        reasons.append("order_book_timestamp_skew")
    if buy_book.latency_ms > policy.max_latency_ms or sell_book.latency_ms > policy.max_latency_ms:
        reasons.append("venue_latency_above_limit")
    if reasons:
        return _rejected(reasons, age, skew)

    buy_cost = _walk(buy_book.asks, base_quantity, asks=True)
    sell_proceeds = _walk(sell_book.bids, base_quantity, asks=False)
    if buy_cost is None or sell_proceeds is None:
        return _rejected(["insufficient_visible_depth"], age, skew)
    if buy_cost > policy.max_notional_quote:
        return _rejected(["notional_above_policy_limit"], age, skew)

    buy_fee = buy_cost * buy_fee_bps / BPS
    sell_fee = sell_proceeds * sell_fee_bps / BPS
    expected = sell_proceeds - buy_cost - buy_fee - sell_fee
    reserve = (buy_cost + sell_proceeds) * policy.slippage_reserve_bps / BPS
    worst = expected - reserve
    expected_bps = expected / buy_cost * BPS
    worst_bps = worst / buy_cost * BPS

    if expected_bps < policy.min_expected_net_bps:
        reasons.append("expected_net_edge_below_floor")
    if worst_bps < policy.min_worst_case_net_bps:
        reasons.append("worst_case_net_edge_below_floor")

    return Assessment(
        eligible=not reasons,
        reasons=tuple(reasons),
        buy_quote_cost=buy_cost,
        sell_quote_proceeds=sell_proceeds,
        expected_net_quote=expected,
        worst_case_net_quote=worst,
        expected_net_bps=expected_bps,
        worst_case_net_bps=worst_bps,
        book_age_ms=age,
        book_skew_ms=skew,
    )
