# Z2 Codex CLI implementation sequence

Status: implementation brief based on a read-only audit of the current Z2, NU-ARB, A2 and arbitrage_bot repositories on 2026-11-05. This is not evidence that integrations are deployed or live trading is enabled.

## Objective

Turn Z2 into the operator-facing intelligence and verification plane for near-real-time arbitrage. Use CCXT Pro for independent exchange book streams, Redis Streams for event transport, the existing Decimal verifier for executable-edge decisions, and a separately controlled execution adapter. The LLM is advisory only.

Do not build a second autonomous trading engine until the existing NU-ARB and arbitrage_bot execution contracts have been reviewed and a concrete gap is demonstrated.

## Findings that constrain implementation

### Arbitrage Gap

- Its public FAQ says the existing My Exchanges feature accepts read-only exchange keys only. Trading-enabled and withdrawal-enabled keys are rejected there.
- Its FAQ and terms say paper bots are available, but real trading is not yet released; a futures bot is described as in development.
- Free scanner data is approximately one minute delayed; paid plans advertise live data.
- The terms prohibit bulk copying/scraping, reselling data, redistributing alerts and bypassing plan delays or technical limits.
- No public developer API or execution SDK was established in the pages reviewed.

Therefore: do not scrape the site, reverse-engineer private browser endpoints, reuse its browser key storage, or attempt to bypass the Free delay. Integrate only through a vendor-approved API/feed if the provider supplies one. Until then, accept a user-provided export/manual signal as unverified context and independently rediscover the route from exchange APIs.

### Existing NU-ARB repository

- The public Vercel scanner exposes a read-only `GET /api/scan` endpoint. It uses CCXT REST snapshots and returns opportunity summaries with `executionEnabled: false`; it strips raw order books from its response.
- The authenticated Python engine uses `ccxt.pro` adapters and has a 20-venue candidate registry. Its public dashboard currently documents 18 public scanner venues.
- The control API has `/api/v1/engine/start`, `/stop`, `/state` and `/journal`. Start requires the service proxy token and a signed-in user session cookie; it starts the engine session, not a single Z2 opportunity order.
- Its docs identify Binance, Bybit and KuCoin as the only venues with strict permission probes that may qualify for live execution, subject to fresh account, stream and permission evidence.
- Its docs also say the production live runner is not yet an unattended daemon that turns every scanner result into an autonomous live route.

Therefore: use the public scanner only as a candidate source, then refresh books independently. Do not assume the current engine start endpoint is a safe per-opportunity execution API. A new authenticated, versioned service-to-service contract or a separately reviewed Z2 execution adapter is required before Z2 can control live orders.

### Existing arbitrage_bot and A2 repositories

- arbitrage_bot contains Rust/Python execution components, a durable journal, Redis Streams/gRPC integration, risk schemas and paper/shadow tooling. Its README documents Bybit as the current exchange integration and lists important deployment/observability gaps.
- A2 contains connector and key-management design material.
- Reuse their contracts or services where the exact runtime, authentication, deployment and safety behavior can be verified. Do not copy code or assume a repository's README proves its service is currently deployed.

## Target system boundaries

1. **Signal adapters**: Arbitrage Gap approved feed (if granted), NU-ARB public scanner, and manually imported signals. Treat every external signal as untrusted data.
2. **Market-data adapters**: CCXT Pro public WebSocket order books. No API credentials are needed for public market data. Validate spot market identity, active status, exchange timestamps, sequence continuity where exposed, reconnect state and book depth.
3. **Reference-data adapters**: official CoinGecko and CoinMarketCap APIs for asset identity, metadata, broad market context and independent reference prices. ChatGPT's CoinGecko/CMC connectors are conversation tools, not callable Python libraries inside a deployed Z2 process.
4. **Event transport**: Redis Streams (Upstash-compatible `rediss://` URL) for normalized snapshots, candidate signals, assessments and execution lifecycle events. Use durable event IDs and consumer-group acknowledgements; dead-letter malformed events.
5. **Verification core**: Decimal-only calculations. Re-fetch both venue books at decision time. Check canonical base/quote identity, executable depth, fees, precision/minimums, latency, freshness, inventory, funding/borrow and rebalance costs. Reject incomplete or stale evidence.
6. **Agentic interface**: LLM can summarize, compare, explain and propose parameter changes. It cannot approve risk, arm live mode, sign requests or submit/cancel orders.
7. **Execution adapter**: paper/shadow first. Before live mode, choose either (a) a reviewed service-to-service contract to the existing NU-ARB engine or (b) a Z2-owned CCXT execution service with encrypted server-side credentials and venue-specific permission probes. Never wire the LLM directly to CCXT private methods.
8. **Reconciliation**: durable idempotency, order-state polling/streams, partial-fill handling, unknown-outcome blocking, exposure accounting, hedge/unwind policy and operator kill switch.

## Implementation stages for Codex CLI

### Stage 0 — inspect before changing

- Read `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/FORMAL_VERIFICATION.md`, every existing API/core/test file and CI workflow.
- Inspect the relevant NU-ARB and arbitrage_bot contracts; do not infer behavior from filenames.
- Establish the actual Python version, dependency lock strategy, test commands and deployment topology.
- Produce a short plan and list contract gaps before implementing.

### Stage 1 — provider contracts

- Define typed Pydantic schemas for signal provenance, venue book snapshots, canonical markets, fee schedules and assessment results.
- Add a NU-ARB public scanner adapter using its documented `/api/scan` endpoint as a non-authoritative signal source. Validate response shape, timestamp age, `dataMode` and `executionEnabled`; do not accept its P&L as executable P&L.
- Keep Arbitrage Gap disabled unless a documented, vendor-approved endpoint and terms-compliant access method are provided.
- Add CoinGecko/CMC API adapters for non-critical reference data only.

### Stage 2 — CCXT Pro market-data runtime

- Add a pinned `ccxt` dependency after verifying the current supported version and Python import contract.
- Use `import ccxt.pro as ccxtpro`; the CCXT documentation describes WebSocket `watch_order_book` and related stream methods.
- Build an allowlisted exchange factory with public-only credentials, per-venue rate limits, bounded subscriptions and deterministic close/shutdown.
- Start with a small configured symbol universe; do not subscribe to every market by default.
- Reject missing exchange timestamps rather than replacing them with local receive time.
- Add reconnect/backoff, stale-book invalidation, sequence-gap recovery and venue-health telemetry.
- Add fake-exchange tests for timestamp absence, invalid levels, market mismatch, reconnect and cleanup.

### Stage 3 — event bus and persistence

- Add Redis Streams via `redis.asyncio`; support Upstash TLS URLs.
- Version every event schema and include event ID, source, venue, symbol, exchange timestamp, receive timestamp and schema version.
- Implement consumer groups, pending-message recovery, deduplication and dead-letter streams.
- Persist opportunities, approvals, orders, fills and reconciliation state durably; Redis is transport/cache, not the only ledger.

### Stage 4 — deterministic opportunity verification

- Keep `src/z2/core/edge.py` pure and Decimal-only.
- Add canonical asset/contract identity checks across venues.
- Support notional sizing by walking asks on the buy venue and bids on the sell venue; do not compare only top-of-book prices.
- Include actual user fee tiers, market precision, minimum quantity/notional, taker/maker mode, slippage reserve and inventory availability.
- For cross-exchange spot, require pre-funded inventory on both venues. Do not rely on a transfer completing before the spread closes.
- For spot-perpetual and perp-perp, separately model contract size, funding timestamps/rates, mark/index price, margin and liquidation constraints.
- Add Hypothesis properties: increasing fees cannot improve net edge; reducing depth cannot create an eligible trade; stale data cannot pass; invalid or non-finite values always fail closed.

### Stage 5 — dashboard and agentic interaction

- Extend the existing dashboard rather than replacing it.
- Add live feed age, venue health, signal provenance, independently verified opportunity queue, depth/size curves, fee breakdown, expected/worst-case net edge, paper fills, open exposure and reconciliation state.
- Stream updates from the backend (WebSocket or SSE) and show reconnect/stale status explicitly.
- Provide explicit mode labels: OBSERVE, PAPER, SHADOW and LIVE-ARMED.
- Add an operator approval flow with a short-lived, one-use approval token bound to the exact opportunity, symbol, venues, size and risk-policy version.
- AI may explain and recommend; deterministic policy code alone evaluates eligibility. Human approval is mandatory for the initial live pilot.

### Stage 6 — paper/shadow engine

- Replay recorded order-book events with configurable latency, fees and partial fills.
- Compare predicted edge to simulated realized fills and reconcile balances/exposure.
- Run failure injection for dropped WebSockets, sequence gaps, duplicate events, delayed acknowledgements, rate limits, exchange downtime, partial fills, timeouts and process restarts.
- Require a soak period and measured false-positive/edge-decay statistics before live pilot review.

### Stage 7 — controlled live execution (separate approval gate)

- Do not enable live mode as part of the initial CCXT data-adapter PR.
- Choose the first two venues explicitly. Candidate support in NU-ARB documentation is not proof of current account or regional eligibility.
- Use a dedicated key per bot instance, least privilege, spot trading only where applicable, no withdrawal or transfer permissions, IP allowlisting and venue permission probes. Use read-only credentials for observation.
- Encrypt credentials server-side with envelope encryption and a KMS/secret manager. Never return them to the browser or log them.
- Require pre-funded balances, per-order/per-venue/per-asset/session caps, daily loss stop, one active cycle per account, durable kill switch and operator approval.
- Implement idempotent order intents. A timeout is an UNKNOWN outcome, not a failed order; query by client order ID before retrying.
- Cross-exchange orders are not atomic. Model partial fills, hedge/unwind paths and residual inventory explicitly.
- Keep live disabled in code/config until the TLA+ model, tests, permission probes, exchange sandbox tests, security review and operational runbook pass.

## Formal verification requirements

- Use `specs/ExecutionProtocol.tla` as a draft state-machine model and run TLC once available. Extend it to the actual two-leg protocol before live use.
- Add Hypothesis property tests for pure financial functions.
- Use Z3 (or equivalent) to check sizing, balance, notional, fee, precision and exposure constraints.
- Bind the checked model, source revision, build artifact and deployed version in release evidence.
- Distinguish unit tests, property tests, model checking, integration tests and runtime evidence. Never call the system "formally verified" until the relevant model has actually been checked and implementation correspondence is reviewed.

## Hosting

- First deployment recommendation: Replit Reserved VM for the persistent Python API, CCXT Pro subscriptions and background workers; use managed PostgreSQL for durable records and Upstash Redis for event transport.
- Vercel is suitable for the static dashboard and short request/response endpoints. Vercel announced WebSocket support in public beta in June 2026 and longer function durations, but this does not make a bounded serverless invocation a substitute for a supervised, continuously running exchange market-data worker.
- Do not provision paid resources or expose credentials without explicit account-owner approval. Add health checks, spend limits, process restart recovery and alerting.

## Local Codex CLI bootstrap

```bash
git clone https://github.com/Samoolino/Z2.git
cd Z2
codex
```

Paste this instruction into the Codex CLI session:

> Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/FORMAL_VERIFICATION.md and docs/CODEX_CLI_BUILD_SEQUENCE.md. Inspect the actual repository and its tests. Implement Stage 1 and Stage 2 only using test-driven development. Do not implement or enable live order submission. Add failing tests first, then the smallest implementation, run focused tests, Ruff and the full pytest suite, and report exact commands/results. If a contract, dependency version, venue capability or provider permission is uncertain, stop and document the gap rather than guessing. Keep the change in a focused branch and open a PR.

## Required operator decision before venue-specific execution

Which two exchanges and which spot symbols should be the first paper/shadow pilot? Do not request or paste API secrets into chat. Credentials should be configured only in the deployment's secret manager after the vault and permission checks have been reviewed.
