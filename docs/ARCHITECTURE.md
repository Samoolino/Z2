# Z2 architecture and integration plan

## Platform assessment

The reviewed Arbitrage Gap public pricing/FAQ pages describe:
- Free plan: scanners and market pages, with scanner data delayed by one minute.
- Paid scanner plans: real-time spot/futures data; pricing page describes 42 spot and 34 futures exchanges refreshed every three seconds.
- Paid plans include read-only exchange keys for balance/scanner features and paper bots operating on real order books/funding.
- Exchange keys with trading, transfer or withdrawal permissions are refused.
- The published FAQ says its futures trading bot is in development and not yet included as a live trading feature.

Conclusion: use Arbitrage Gap for discovery only. No public developer API or execution SDK was established in the pages reviewed. Obtain written vendor confirmation before implementing a direct feed; otherwise use user-exported CSV or manual signal input. Do not scrape private endpoints or reverse-engineer authenticated browser traffic.

CoinGecko and CoinMarketCap ChatGPT connectors are usable inside ChatGPT but are not persistent backend services for Z2. The deployed app must call the providers' own APIs server-side. Use them for asset identity, reference prices, broad volume, metadata and market context — not venue-specific executable depth. Cache and throttle provider calls; keep them out of the latency-critical order path.

## Existing repository integration

| Existing system | Current responsibility | Z2 integration |
|---|---|---|
| Samoolino/NU-ARB | Multi-exchange scanner, CCXT Pro adapters, account verification and hybrid execution | Authenticated opportunity/status/execution adapter after API contract review |
| Samoolino/arbitrage_bot | Rust/Python execution, three-leg coordinator, PostgreSQL ledger, Redis Streams and paper reconciliation | Optional service adapter for supported strategy/engine commands |
| Samoolino/A2 | Hummingbot, Gateway, Condor, EMQX and connector qualification | Hummingbot API/Gateway adapter; AI proposes, deterministic gate authorizes |

Do not duplicate engines or run two independent execution coordinators against the same account. Keep one authoritative ledger and one execution owner per account.

## Connector/library selection

| Component | Recommended role | License / caveat |
|---|---|---|
| CCXT | Unified CEX REST/WebSocket and order interface | MIT; verify exact installed version and exchange capabilities |
| Hummingbot | Reuse existing CEX strategy/connector execution | Apache 2.0 / MIT components; verify each repository license |
| Hummingbot Gateway | DEX/AMM middleware | Qualify each chain/protocol connector |
| NautilusTrader | Optional high-performance event-driven runtime | LGPL-3.0; pin a stable release and API |
| Cryptofeed | Optional market-data stream handler | AGPL-3.0; legal review before embedding in proprietary services |
| Hypothesis | Property-based testing | Test dependency |
| TLA+ / TLC | Model-check concurrent execution and recovery | Formal-methods tooling |
| Lean 4 | Prove core arithmetic and invariants | Theorem prover |
| Z3 | Constraint checking for sizing and risk policies | SMT solver |

## Data and execution flow

1. Ingest an external scanner candidate, recording source, observed time, received time and original payload hash.
2. Normalize asset, symbol, venue and market type.
3. Independently refresh direct exchange books and balances.
4. Validate sequence continuity, timestamp age/skew, latency, depth and venue permission evidence.
5. Walk visible depth using Decimal arithmetic.
6. Subtract taker fees, slippage reserve, funding/borrow, gas, network, transfer and rebalancing costs as applicable.
7. Apply deterministic risk policy.
8. Send only a versioned, idempotent execution intent to one approved execution service.
9. Reconcile acknowledgements, partial fills, fees, inventory and realized P&L.
10. Persist the evidence and render the outcome in the Z2 interface.

Two CEX legs are not atomic. Pre-fund both venues; use bounded IOC limits where supported; reconcile every order and define a risk-reducing hedge/unwind path. CEX/DEX and cross-chain routes require separate settlement/finality and bridge-risk controls.

## Deployment

Recommended split:
- Vercel for the static/operator UI and short request/response endpoints.
- Replit Reserved VM (or dedicated VPS) for persistent scanner ingestion, WebSocket sessions and orchestration.
- PostgreSQL for durable opportunity, order/fill and reconciliation records.
- Reuse Redis Streams or EMQX as the canonical event transport.

Do not run the trading loop inside a Vercel Function. Vercel Functions have bounded invocation duration and do not support acting as a WebSocket server. Replit Reserved VM is the closer fit for persistent processes; deployment uptime, restarts and recovery still require operational testing.

## Delivery phases

### P0 — foundation (current)
Observe-only API, dashboard, Decimal cross-venue assessment, timestamp/latency/depth/fee gates and tests.

### P1 — scanner ingestion
Obtain Arbitrage Gap's official API/feed/export schema. Until then use user-exported CSV/manual records and mark them UNVERIFIED_EXTERNAL_SIGNAL.

### P2 — independent market data
Add direct CEX WebSocket adapters, normalized order books, sequence recovery and provider APIs for CoinGecko/CMC as secondary context.

### P3 — opportunity engine
Match signals to canonical markets, independently refresh books, depth-walk size and compute executable net edge after all costs.

### P4 — paper/shadow execution
Connect to NU-ARB or arbitrage_bot through authenticated versioned contracts. Compare modeled and realized paper fills and test partial-fill/recovery behavior.

### P5 — formal and operational verification
TLA+ state-machine model, Lean arithmetic proofs, Z3 constraints, Hypothesis property tests, failure injection, soak tests and security review.

### P6 — controlled live pilot (not enabled by this foundation)
Requires venue permission evidence, IP allowlisting, separate trade-only credentials, pre-funded inventory, per-order/session/daily risk limits, durable kill switch, partial-fill recovery, operator approval and independent code review.
