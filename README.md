# Z2 — Agentic Arbitrage Intelligence & Execution Orchestrator

Z2 is the independent intelligence and control plane for a multi-venue arbitrage system. It combines external scanner signals, independent live exchange books, market-reference providers, deterministic safety checks and existing execution engines.

**Current status:** initial observe-only foundation. The deterministic order-book assessment API and safety-status contract are implemented. No exchange credentials are configured, no vendor feed is connected, and no live order endpoint is enabled. Z2 does not claim live trading readiness or guaranteed profit.

## Why Z2 exists

- Arbitrage Gap is an opportunity scanner. Its published FAQ says it accepts read-only exchange keys and currently offers paper bots; it does not currently provide live trading execution.
- CoinGecko and CoinMarketCap provide broad market-reference data. Their ChatGPT connectors are useful in this conversation, but they are not persistent APIs that a deployed Z2 service can call. Z2 must use the providers' own APIs from its backend.
- NU-ARB already contains a 20-venue candidate registry, CCXT Pro adapters, a public scanner, authenticated account verification, paper/live control paths and a separate control service.
- arbitrage_bot already contains Rust/Python execution, a three-leg coordinator, PostgreSQL accounting, Redis Streams, a FastAPI control plane and paper-execution/reconciliation patterns.
- A2 already documents Hummingbot, Gateway, Condor, EMQX and connector qualification.

Z2 orchestrates these systems through versioned, authenticated service adapters. It should not fork or duplicate their execution engines without a reviewed reason.

## Initial capabilities

- GET /healthz — process health.
- GET /api/v1/status — connector readiness and safety mode.
- POST /api/v1/opportunities/evaluate — deterministic, Decimal-based cross-exchange spot assessment using two independently supplied order books.
- Rejects stale/future-dated books, excessive timestamp skew, high latency, insufficient visible depth, invalid books, mismatched markets, same-venue routes, fees and policy violations.
- Every evaluation is informational: execution is NOT_SUBMITTED.

## Run locally

    python -m pip install -e '.[dev]'
    PYTHONPATH=src uvicorn z2.api.main:app --reload --host 0.0.0.0 --port 8000

Open http://localhost:8000 for the dashboard and http://localhost:8000/docs for the API contract.

## Target architecture

    Arbitrage Gap / CoinGecko / CoinMarketCap / CEX WebSockets / NU-ARB / Hummingbot
                                      |
                                      v
                            Z2 normalizer and event bus
                                      |
                                      v
                            Independent book verifier
                                      |
                                      v
                              Decimal profit engine
                                      |
                                      v
                              Formal and risk gate
                                      |
                              paper / shadow first
                                      |
                       approved execution service adapter
                                      |
                      NU-ARB / Hummingbot / Rust engine
                                      |
                         fills, ledger, reconciliation
                                      |
                                      v
                             Z2 agentic operations UI

The LLM may explain signals, compare strategies, propose parameters and summarize evidence. It must never authorize, sign or submit an order. Only deterministic code with fresh venue evidence, explicit operator controls and risk limits may authorize an execution request.

## Arbitrage Gap integration boundary

No public developer API or execution SDK was established in the pages reviewed. Do not scrape private endpoints, reverse-engineer authenticated browser traffic or bypass access controls. First use a vendor-approved API/feed if Arbitrage Gap provides one; otherwise accept user-exported CSV or manually supplied route evidence and label it delayed/unverified. Z2 independently refreshes both venues' executable books before an opportunity can pass its own gate.

The scanner's displayed percentage or estimated profit is never treated as executable P&L.

## Data-provider roles

| Source | Intended use | Not suitable for |
|---|---|---|
| Arbitrage Gap | External discovery and route context | Live order execution or sole source of book truth |
| CoinGecko | Asset identity, market reference and metadata | Exchange-specific executable depth |
| CoinMarketCap | Independent reference prices and market context | Per-venue bid/ask execution |
| CCXT | Unified exchange REST/WebSocket and order adapters | Replacing venue-specific permission verification |
| Hummingbot / Gateway | Existing strategy and CEX/DEX connector runtime | LLM-controlled unrestricted execution |
| NautilusTrader | Optional high-performance event-driven runtime | Unpinned development builds in production |

## Credential policy

- Never place exchange secrets in frontend code, browser storage, Git, issue comments or logs.
- Use server-side Replit Deployment Secrets for service-level keys. For per-user keys use an encrypted credential vault with envelope encryption and strict access controls.
- Exchange keys must be least-privilege: read plus required spot-trading scope only; withdrawals and transfers disabled; IP allowlisting enabled where supported.
- Keep separate read-only keys for observation and trade-only keys for execution.
- Verify actual permissions from the exchange's signed permission endpoint. If a venue cannot prove safe scopes, it remains ineligible for live execution.
- Never ask users to paste private keys into ChatGPT.
- CoinGecko/CMC keys are data-provider credentials, not exchange trading credentials.

## Deployment decision

Recommended split:
- Vercel: static/operator UI and short request/response endpoints only.
- Replit Reserved VM: persistent scanner ingestion, WebSocket sessions, event processing and orchestration worker.
- PostgreSQL: durable opportunity, order/fill and reconciliation records.
- Redis Streams or EMQX: event transport. Reuse existing infrastructure where possible; avoid duplicate brokers without a measured need.

Do not run the trading loop inside a Vercel Function. Vercel Functions have bounded invocation duration and do not support acting as a WebSocket server. If Vercel is selected for the UI, the execution worker must run elsewhere.

## Verification

    python -m pip install -e '.[dev]'
    pytest -q

Formal verification roadmap:
1. TLA+ model of execution lifecycle, concurrent cycle admission, stop-latch and unknown-order recovery.
2. Lean proofs for pure arithmetic identities and gate invariants over exact rational/decimal inputs.
3. Z3 constraint checks for size, balance, fee, notional and exposure constraints.
4. Hypothesis property tests for depth walking, fee monotonicity, rounding and invalid/stale input rejection.
5. Integration tests against exchange sandboxes and recorded order-book replays.
6. Paper/shadow soak, failure injection, reconciliation and security review before any live pilot.

Formal verification can prove properties of the model and implementation under stated assumptions. It cannot prove that market prices remain available, that a venue will fill an order, or that real execution cannot lose money.

## Non-negotiable execution invariants

- Observe-only is the default; live execution remains disabled until a separate reviewed implementation explicitly enables it.
- No order when books are stale, unsynchronized, incomplete or beyond latency bounds.
- No order unless executable depth covers the requested quantity on both sides.
- Net edge must clear fees, spread, slippage reserve, funding/borrow costs, transfer/rebalance costs and venue minimums.
- No duplicate order submission for an idempotency key.
- An unknown order state or partial fill blocks new risk until reconciled or hedged.
- Enforce per-order, per-venue, per-asset, per-session and daily-loss limits.
- Emergency stop blocks new exposure but permits separately authorized risk-reducing actions.
- Cross-exchange orders are not atomic. Pre-fund inventory on both venues; handle partial fills and unwind risk explicitly.
- The UI distinguishes scanner opportunity, independently verified opportunity, paper fill, submitted order, exchange-confirmed fill and reconciled P&L.

## Repository integration targets

- Samoolino/NU-ARB — multi-exchange scanner and existing hybrid execution service.
- Samoolino/arbitrage_bot — Rust/Python execution and durable paper ledger.
- Samoolino/A2 — Hummingbot, Gateway, Condor and EMQX orchestration.

Integration is by authenticated, versioned service contracts. No credentials or live-order authority are shared with the LLM.
