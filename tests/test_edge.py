from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from z2.core.edge import Level, OrderBook, Policy, assess_cross_exchange


NOW = datetime(2026, 11, 5, 6, 0, tzinfo=UTC)


def book(venue, *, bid, ask, ts=NOW, qty="10", latency="10"):
    return OrderBook(
        venue=venue,
        symbol="BTC/USDT",
        bids=(Level(D(bid), D(qty)),),
        asks=(Level(D(ask), D(qty)),),
        exchange_ts=ts,
        received_ts=ts,
        latency_ms=D(latency),
    )


def policy(**kwargs):
    return Policy(**kwargs)


def test_profitable_depth_aware_route_passes_after_fees_and_reserve():
    result = assess_cross_exchange(
        buy_book=book("buy", bid="99", ask="100"),
        sell_book=book("sell", bid="102", ask="103"),
        base_quantity=D(1),
        buy_fee_bps=D(10),
        sell_fee_bps=D(10),
        policy=policy(min_expected_net_bps=D(100), min_worst_case_net_bps=D(50)),
        now=NOW,
    )
    assert result.eligible is True
    assert result.expected_net_quote == D("1.798")
    assert result.worst_case_net_quote < result.expected_net_quote
    assert result.reasons == ()


def test_stale_book_is_rejected():
    result = assess_cross_exchange(
        book("buy", bid="99", ask="100", ts=NOW - timedelta(seconds=2)),
        book("sell", bid="102", ask="103"),
        D(1), D(0), D(0),
        policy(max_book_age_ms=D(500)),
        NOW,
    )
    assert result.eligible is False
    assert "stale_order_book" in result.reasons


def test_future_timestamp_is_rejected():
    result = assess_cross_exchange(
        book("buy", bid="99", ask="100", ts=NOW + timedelta(seconds=1)),
        book("sell", bid="102", ask="103"),
        D(1), D(0), D(0), policy(), NOW,
    )
    assert result.eligible is False
    assert "future_or_clock_skewed_book_timestamp" in result.reasons


def test_insufficient_visible_depth_is_rejected():
    result = assess_cross_exchange(
        book("buy", bid="99", ask="100", qty="0.2"),
        book("sell", bid="102", ask="103", qty="0.2"),
        D(1), D(0), D(0), policy(), NOW,
    )
    assert result.eligible is False
    assert "insufficient_visible_depth" in result.reasons


def test_same_venue_is_rejected():
    result = assess_cross_exchange(
        book("same", bid="99", ask="100"),
        book("same", bid="102", ask="103"),
        D(1), D(0), D(0), policy(), NOW,
    )
    assert result.eligible is False
    assert "distinct_named_venues_required" in result.reasons


def test_mismatched_symbols_are_rejected():
    sell = replace(book("sell", bid="102", ask="103"), symbol="ETH/USDT")
    result = assess_cross_exchange(
        book("buy", bid="99", ask="100"), sell,
        D(1), D(0), D(0), policy(), NOW,
    )
    assert result.eligible is False
    assert "matching_symbol_required" in result.reasons


def test_high_latency_is_rejected():
    result = assess_cross_exchange(
        book("buy", bid="99", ask="100", latency="500"),
        book("sell", bid="102", ask="103"),
        D(1), D(0), D(0), policy(max_latency_ms=D(100)), NOW,
    )
    assert result.eligible is False
    assert "venue_latency_above_limit" in result.reasons


def test_expected_profit_below_floor_is_rejected():
    result = assess_cross_exchange(
        book("buy", bid="99.99", ask="100"),
        book("sell", bid="100.01", ask="100.02"),
        D(1), D(10), D(10),
        policy(min_expected_net_bps=D(5), min_worst_case_net_bps=D(1)),
        NOW,
    )
    assert result.eligible is False
    assert "expected_net_edge_below_floor" in result.reasons


def test_orderbook_negative_levels_are_rejected():
    bad = OrderBook(
        venue="buy", symbol="BTC/USDT",
        bids=(Level(D(99), D(1)),),
        asks=(Level(D(-100), D(1)),),
        exchange_ts=NOW, received_ts=NOW, latency_ms=D(1),
    )
    result = assess_cross_exchange(
        bad, book("sell", bid="102", ask="103"),
        D(1), D(0), D(0), policy(), NOW,
    )
    assert result.eligible is False
    assert "invalid_order_book_levels" in result.reasons


def test_higher_fees_cannot_improve_net_edge():
    buy = book("buy", bid="99", ask="100")
    sell = book("sell", bid="102", ask="103")
    low_fee = assess_cross_exchange(buy, sell, D(1), D(1), D(1), policy(), NOW)
    high_fee = assess_cross_exchange(buy, sell, D(1), D(20), D(20), policy(), NOW)
    assert high_fee.expected_net_quote < low_fee.expected_net_quote


def test_higher_slippage_reserve_cannot_improve_worst_case():
    buy = book("buy", bid="99", ask="100")
    sell = book("sell", bid="102", ask="103")
    low = assess_cross_exchange(buy, sell, D(1), D(1), D(1), policy(slippage_reserve_bps=D(1)), NOW)
    high = assess_cross_exchange(buy, sell, D(1), D(1), D(1), policy(slippage_reserve_bps=D(20)), NOW)
    assert high.worst_case_net_quote < low.worst_case_net_quote
