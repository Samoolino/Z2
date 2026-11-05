# Z2 multi-exchange agentic arbitrage platform

## Product definition

Z2 is a complete agentic arbitrage platform, not a passive scanner or a dashboard that forwards third-party signals. It extends the Arbitrage Gap product concept with its own exchange-wide market intelligence, strategy selection, deterministic risk authorization, CCXT execution, reconciliation and operator controls.

The product has two coordinated but separately secured planes:

1. **Market intelligence plane** — discovers and continuously monitors every venue and market that the installed CCXT version can support, subject to exchange availability, rate limits, region restrictions and capability flags.
2. **Trading plane** — authenticates individual exchange accounts, verifies permissions and balances, and executes only strategies explicitly armed under deterministic risk policies.

The external Arbitrage Gap scanner is an optional upstream reference/integration, not the system's authority and not a prerequisite for Z2 to operate. Use only a vendor-approved API/feed or permitted attributed widget. Never scrape private endpoints, bypass plan delays, or bulk-copy proprietary scanner data. Z2 must independently verify every candidate against fresh exchange order books.

## What "all exchanges live" means

"All exchanges" is a dynamic CCXT catalogue requirement, not a hardcoded list of two venues:

- Discover exchange IDs from the pinned CCXT package at runtime/build time.
- Create a venue capability record from CCXT's declared capabilities and the exchange's loaded market metadata.
- Attempt public market-data connections for every enabled, supported venue using adaptive concurrency, per-venue rate limits and subscription budgets.
- Subscribe to every eligible market only where the venue supports the relevant stream and the configured resource budget permits it. Shard workers by venue/market; do not open unbounded sockets or subscribe blindly to every symbol.
- Keep unsupported, restricted, maintenance, unavailable or rate-limited venues visible with an explicit state and reason rather than silently omitting them.
- Expose spot, swap, future, option and other market types only where the exchange and CCXT adapter actually support the required methods and metadata. Initial trading strategy scope is spot and linear/inverse derivatives; options can remain market-data-only until separately qualified.
- Public market-data access does not require private API credentials. Private balance/order streams and live trading are enabled only per configured account after permission verification.

Each venue has an independent lifecycle state:

DISCOVERED -> QUALIFIED -> CONNECTING -> MARKET_DATA_LIVE -> PRIVATE_ACCOUNT_READY -> LIVE_TRADING_ARMED

Failure states include DEGRADED, RATE_LIMITED, MAINTENANCE, UNSUPPORTED and DISABLED. LIVE_TRADING_ARMED is per account, market type and strategy policy; it is never inferred from a connected WebSocket or the presence of an API key.

The dashboard must show the total CCXT catalogue count, qualified venues, live public feeds, stale/degraded feeds, authenticated accounts, trade-enabled accounts and the reason each venue is not eligible.

## CCXT-only connector architecture

- Use CCXT async REST for discovery, metadata, controlled snapshots and fallback polling.
- Use the bundled CCXT Pro WebSocket interface for supported public order-book/trade streams and supported private account streams.
- Build a dynamic ExchangeRegistry around ccxt.exchanges, with an explicit allow/deny policy and a generated capability matrix. Never assume all exchanges implement the same methods or market types.
- Build a VenueSupervisor that owns one isolated client per exchange/account keypair, connection lifecycle, heartbeat, reconnect with jitter, backoff, rate-limit coordination, time synchronization and graceful close.
- Keep public market-data clients credential-free. Keep private clients isolated per account and never share a keypair instance across workers.
- Use exchange metadata (has, markets, precision, limits, contract size, linear/inverse, settlement and time-in-force capabilities) rather than venue-name conditionals wherever possible. Add narrowly scoped venue adapters only for genuine exchange-specific behavior.
- Pin CCXT versions and run capability/contract tests on upgrades. Exchange APIs change independently of CCXT.

All market, price, quantity, fee and P&L arithmetic uses Decimal. Preserve exchange timestamps and local receive timestamps separately. Track sequence numbers where available, feed age, reconnect gaps, clock skew, cross-venue skew and measured round-trip latency.

## Canonical market identity and opportunity graph

Create canonical identities for assets, spot pairs and derivative contracts. Do not equate symbols solely by display string. Validate base, quote, settlement, contract size, linear/inverse type, expiry, margin currency and market status.

Build a continuously updated opportunity graph from qualified markets:

1. Cross-exchange spot/spot, using pre-funded inventory at both venues.
2. Spot/perpetual hedge (cash-and-carry or reverse cash-and-carry), including funding and borrow costs.
3. Perpetual/perpetual basis and funding spread, with matched contract exposure and settlement currencies.
4. Intra-exchange triangular spot arbitrage where all three books and fees are available.
5. Additional strategies only after a separately tested market/contract model exists.

For every route, walk actual bid/ask depth at the proposed size. Calculate executable proceeds and cost, trading fees, slippage reserve, funding, borrow, rebalance/network costs, minimum order values, precision/step-size effects and inventory opportunity cost. A displayed spread or last-traded price is not executable profit.

Candidate states are DISCOVERED, INDEPENDENTLY_VERIFIED, RISK_APPROVED, PAPER_EXECUTED, LIVE_SUBMITTED, PARTIALLY_FILLED, HEDGING, RECONCILING, CLOSED and REJECTED. Preserve evidence, source timestamps, strategy version, market metadata and rejection reason for every transition.

## Agentic strategy layer

The agent is an active strategy operator, but not an unrestricted order signer:

- It continuously interprets opportunities, compares eligible strategies, ranks routes and explains why a candidate passed or failed.
- It may select among operator-enabled strategies and tune parameters only within pre-authorized bounds.
- It can request a policy change, but cannot widen exposure, leverage, loss or notional limits itself.
- It can pause a strategy, recommend hedging, identify feed degradation and request operator intervention.
- It cannot manufacture prices, override stale-data gates, invent balances, bypass permissions, sign orders or send raw exchange requests.
- The low-latency trading path must be deterministic and must not wait for an LLM response. The agent supervises and configures bounded strategies; deterministic code makes final pre-trade decisions and submits orders.

The UI must distinguish agent recommendation, deterministic approval, operator authorization and exchange-confirmed execution.

## Execution engine

Cross-exchange execution is not atomic. Concurrent requests do not guarantee simultaneous fills. The engine must assume any leg can be delayed, rejected, partially filled or have an unknown status.

Required components:

- Per-account execution owner and durable order-intent journal.
- Explicit per-account live arm, per-strategy enablement and a persistent emergency stop.
- Trade-only API keys with withdrawals/transfers disabled and IP allowlisting where supported. Verify permissions through exchange-specific signed endpoints; unknown permissions fail closed.
- Fresh synchronized books and balances immediately before submission.
- Venue-specific precision, min/max amount, min-notional, contract-size, position mode, margin and leverage checks.
- Deterministic client order IDs/idempotency keys where supported.
- Concurrent paired-leg submission using only supported order types and time-in-force semantics.
- Partial-fill, rejection, timeout and unknown-order-state recovery. Reconcile with the exchange before retrying; never blindly resubmit an uncertain order.
- Bounded hedge/unwind policy, per-order/asset/venue/account/session caps, max exposure, max slippage, daily loss limit and circuit breakers.
- Private order/fill/balance streams plus REST reconciliation.
- Pre-funded inventory as the default. No strategy assumes a transfer can settle within an opportunity's lifetime.
- Emergency stop blocks new risk while allowing separately authorized risk-reducing actions.

Do not enable live order submission until paper/shadow soak, sandbox contract tests, fault injection, formal state-machine checks, security review and an explicitly approved live pilot are complete. Never ask for exchange secrets in ChatGPT; enter them only in the deployed server-side credential vault.

## Persistence and messaging

PostgreSQL is the authoritative ledger for users, encrypted credential references, venue capabilities, account permissions, strategy/policy versions, opportunities, order intents, exchange order IDs, fills, fees, balances, positions, reconciliation and immutable audit events.

Redis Streams carries high-rate normalized market events, opportunity updates and execution status. Use consumer groups, explicit acknowledgements, idempotent consumers, pending-message recovery and bounded retention. Redis is not the trade ledger. Add NATS JetStream only when measured replay/fan-out requirements justify another broker.

## Agentic operator interface

The dashboard must provide:

- **Exchange universe:** all CCXT IDs, qualification, market types, feed state, latency, rate-limit health, account state and trade eligibility.
- **Live scanner:** cross-venue route graph, executable size, gross/net edge, depth, fees, slippage, funding, source age and confidence/rejection reason.
- **Strategy cockpit:** enabled strategies, bounded parameters, agent rationale, risk budget and per-strategy pause/arm controls.
- **Execution terminal:** paired legs, client/exchange order IDs, fills, partial fills, hedges, open exposure, reconciliation and realized P&L.
- **Risk center:** exposure, balances, daily loss, circuit breakers, stale-feed count and global/per-account kill switches.
- **Audit timeline:** immutable decision evidence and the distinction between recommendation, approval, submission, fill and reconciliation.
- **External references:** attributed Arbitrage Gap widget or approved feed, plus CoinGecko/CoinMarketCap reference context. These are not executable book sources.

The UI must never label a candidate as a trade or profit until exchange-confirmed fills and ledger reconciliation support that status.

## Formal verification and test obligations

- **TLA+/TLC:** model concurrent strategy cycles, one execution owner per account, paired-leg partial fills, unknown order status, stop-latch behavior, reconciliation and restart recovery. Check that no new risk is admitted while prior exposure is unresolved.
- **Z3:** constrain quantity, depth, balances, minimums, precision, fees, exposure, leverage and net-edge thresholds.
- **Hypothesis:** property-test depth walking, rounding, fee monotonicity, duplicate events, stale books, reconnect gaps, partial fills and order-state transitions.
- **Recorded-book replay:** deterministic scanner and strategy regression against captured market events.
- **Sandbox and fault injection:** exchange contract tests for every qualified venue and supported order type.
- **Proof boundary:** a proof establishes properties of the specified model under its assumptions. It does not prove market liquidity, fill probability, API availability or profitability.

## Deployment topology

- Replit Reserved VM or a dedicated always-on host: CCXT venue supervisors, scanner workers, agent supervisor and execution services.
- Vercel: optional web UI and short-lived API/BFF; not the persistent trading loop.
- PostgreSQL: managed/private durable storage with backups and migrations.
- Redis Streams: managed/private event transport.
- Docker Compose: reproducible local development and staging; do not expose database/broker ports publicly.
- OpenTelemetry + Prometheus/Grafana: per-venue feed age, latency, reconnects, queue lag, opportunity conversion, order failures, exposure and reconciliation metrics.

## Delivery gates

1. **Catalogue and capability registry:** discover all CCXT IDs, qualify features and render every venue state.
2. **All-venue public market-data plane:** adaptive connection supervisor, market metadata, WebSocket feeds, fallback polling and health dashboard.
3. **Canonical scanner:** cross-venue opportunity graph, depth-aware net edge and recorded-book replay.
4. **Strategy and agent supervisor:** bounded strategy selection, explanations, alerts and operator controls.
5. **Durable event/ledger layer:** PostgreSQL migrations, Redis Streams consumers, idempotency and audit trail.
6. **Paper/shadow execution:** simulate paired orders and realistic partial-fill/latency/failure scenarios across all qualified venues.
7. **Sandbox execution:** exchange-specific private permissions, order types, reconciliation and fault injection.
8. **Formal/security review and live pilot:** per-account opt-in only, explicit risk policy and gradual venue rollout.

"All exchanges" is the target catalogue and continuous qualification requirement. It does not mean forcing unsupported APIs, bypassing geographic restrictions, exceeding venue rate limits or enabling live trading on accounts without verified permissions.
