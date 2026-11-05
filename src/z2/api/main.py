from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from z2.api.schemas import EvaluateIn, to_order_book, to_policy
from z2.core.edge import assess_cross_exchange

app = FastAPI(
    title="Z2 Arbitrage Intelligence API",
    version="0.1.0",
    description="Observe-only opportunity assessment. No live order endpoints are enabled.",
)

WEB_DIR = Path(__file__).resolve().parents[3] / "web"
if WEB_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/", include_in_schema=False)
def dashboard():
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Dashboard assets are not installed")
    return FileResponse(index)


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "z2-control"}


@app.get("/api/v1/status")
def status():
    return {
        "service": "z2-control",
        "mode": "OBSERVE_ONLY",
        "live_trading_enabled": False,
        "order_submission_enabled": False,
        "connectors": [
            {"id": "arbitragegap", "state": "UNCONFIGURED", "method": "vendor-approved API or manual CSV"},
            {"id": "coingecko", "state": "UNCONFIGURED", "method": "server-side public API"},
            {"id": "coinmarketcap", "state": "UNCONFIGURED", "method": "server-side API key"},
            {"id": "ccxt", "state": "UNCONFIGURED", "method": "CCXT async REST / Pro WebSocket"},
            {"id": "nu-arb", "state": "UNCONFIGURED", "method": "authenticated service adapter"},
            {"id": "hummingbot", "state": "UNCONFIGURED", "method": "Hummingbot API adapter"},
        ],
        "safety": {
            "llm_can_authorize_orders": False,
            "withdrawal_permission_allowed": False,
            "paper_mode_only": True,
        },
    }


@app.post("/api/v1/opportunities/evaluate")
def evaluate(payload: EvaluateIn):
    try:
        result = assess_cross_exchange(
            buy_book=to_order_book(payload.buy_book),
            sell_book=to_order_book(payload.sell_book),
            base_quantity=payload.base_quantity,
            buy_fee_bps=payload.buy_fee_bps,
            sell_fee_bps=payload.sell_fee_bps,
            policy=to_policy(payload.policy),
            now=payload.now,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "eligible": result.eligible,
        "reasons": list(result.reasons),
        "buy_quote_cost": str(result.buy_quote_cost),
        "sell_quote_proceeds": str(result.sell_quote_proceeds),
        "expected_net_quote": str(result.expected_net_quote),
        "worst_case_net_quote": str(result.worst_case_net_quote),
        "expected_net_bps": str(result.expected_net_bps),
        "worst_case_net_bps": str(result.worst_case_net_bps),
        "book_age_ms": str(result.book_age_ms),
        "book_skew_ms": str(result.book_skew_ms),
        "execution": "NOT_SUBMITTED",
    }
