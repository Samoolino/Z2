from fastapi.testclient import TestClient

from z2.api.main import app


def test_status_is_observe_only_and_never_enables_order_submission():
    response = TestClient(app).get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE_ONLY"
    assert body["live_trading_enabled"] is False
    assert body["order_submission_enabled"] is False
    assert body["safety"]["llm_can_authorize_orders"] is False


def test_health_endpoint():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_dashboard_is_served_from_same_origin():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Arbitrage command center" in response.text


def test_dashboard_assets_are_served():
    response = TestClient(app).get("/assets/app.js")
    assert response.status_code == 200
    assert "refreshStatus" in response.text


def test_evaluation_endpoint_never_submits_orders():
    payload = {
        "buy_book": {
            "venue": "buy", "symbol": "BTC/USDT",
            "bids": [{"price": "99", "quantity": "2"}],
            "asks": [{"price": "100", "quantity": "2"}],
            "exchange_ts": "2026-11-05T06:00:00Z",
            "received_ts": "2026-11-05T06:00:00Z", "latency_ms": "5"
        },
        "sell_book": {
            "venue": "sell", "symbol": "BTC/USDT",
            "bids": [{"price": "102", "quantity": "2"}],
            "asks": [{"price": "103", "quantity": "2"}],
            "exchange_ts": "2026-11-05T06:00:00Z",
            "received_ts": "2026-11-05T06:00:00Z", "latency_ms": "5"
        },
        "base_quantity": "1", "buy_fee_bps": "10", "sell_fee_bps": "10",
        "policy": {"min_expected_net_bps": "100", "min_worst_case_net_bps": "50"},
        "now": "2026-11-05T06:00:00Z"
    }
    response = TestClient(app).post("/api/v1/opportunities/evaluate", json=payload)
    assert response.status_code == 200
    assert response.json()["eligible"] is True
    assert response.json()["execution"] == "NOT_SUBMITTED"
