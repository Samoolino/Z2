# CCXT engine integration

## Purpose and scope

Z2 is being extended as a CCXT-first, multi-venue arbitrage scanner and execution control plane. CCXT is the exchange adapter, not the strategy engine. Z2 owns opportunity discovery, market normalization, depth-aware profitability, deterministic risk checks, execution coordination, durable state and operator controls.

This change adds the first CCXT connection and order-book normalization layer. It intentionally does **not** add an order-submission endpoint or enable live trading.

## Current implementation

- `ExchangeConfig` validates exchange IDs, market type, timeout and credential pairing.
- `create_exchange` constructs isolated `ccxt.async_support` or `ccxt.pro` clients.
- Sandbox mode is enabled by default and set before the first API call.
- Credentials are optional and hidden from dataclass representations.
- `normalize_order_book` converts price/quantity to Decimal and requires the exchange timestamp; local receipt time is never substituted for a missing exchange timestamp.
- `fetch_order_book` and `watch_order_book` expose REST and WebSocket book acquisition.
- `close_exchange` releases exchange sessions and sockets.
- No function in this module calls `create_order`, `createOrder`, transfer, withdrawal or account-funding methods.

CCXT Pro is included in the free, MIT-licensed CCXT package; it adds WebSocket streaming without a separate paid package. Verify the exact exchange capability flags and parameters for every pinned CCXT version and venue: https://docs.ccxt.com/docs/pro-manual

## Credential boundary

CCXT accepts exchange-specific credentials such as `apiKey`, `secret`, and, where required, `password` or `uid`. These are not interchangeable between exchanges.

- Never collect keys in ChatGPT, the public UI, query strings or client-side JavaScript.
- Keep keys in server-side deployment secrets or, for multi-user accounts, an encrypted credential vault with envelope encryption and per-user access control.
- Use one private CCXT client instance per exchange keypair. Use credential-free clients for public market-data scanning.
- Create separate read-only and trade-only keys. Disable withdrawals and transfers on all trading keys; IP allowlist where supported.
- Start with sandbox/testnet credentials. A production credential does not itself grant Z2 permission to trade.
- Check venue permission endpoints and exchange-specific account scopes. CCXT credential presence checks only establish that required fields are populated; they do not prove that a key has safe permissions.
- Do not share one keypair across concurrent CCXT client instances. Keep nonce and rate-limit state isolated.
- The local `.env` example is for single-operator development only. Do not commit populated secrets. Production secrets belong in Replit Deployment Secrets or a dedicated secret manager.

## Scanner source rules

### Arbitrage Gap

Arbitrage Gap's published free scanner is approximately one minute delayed. Paid plans advertise real-time data. Its terms prohibit bulk copying/scraping, reselling scanner data and bypassing plan delays or rate limits. Its free website widgets may be embedded with the attribution link intact; they show delayed data.

Therefore:
- Do not scrape the scanner HTML, reverse-engineer private endpoints, intercept authenticated browser traffic or bulk export route data.
- Use the official widget as a displayed reference only: https://arbitragegap.com/widgets
- For programmatic ingestion, obtain a written vendor-approved API/feed and license first.
- Z2's own CCXT feeds remain the source of executable bid/ask depth. External scanner output is a discovery hint, never an execution instruction.

### CoinGecko and CoinMarketCap

Use their official backend APIs for asset identity, market reference, liquidity context and broad market metadata. Their ChatGPT connectors do not become deployed backend credentials or APIs.

- CoinGecko Demo API: https://www.coingecko.com/en/api/pricing
- CoinMarketCap Basic API: https://coinmarketcap.com/api/pricing/
- Keep both API keys server-side, obey quotas and cache reference data.
- Do not put either provider in the latency-critical execution decision. Venue-specific order books, contract metadata, fee schedules and balances must come from the exchange adapter.

## Market data and strategy design

1. Load markets from each selected exchange and pin a canonical market identity.
2. For spot, match base/quote assets and network/deposit constraints; for derivatives, additionally match contract type, settlement asset, linear/inverse flag, contract size, margin mode and funding interval.
3. Subscribe to order books with CCXT Pro where supported; use REST polling only as a controlled fallback.
4. Track exchange timestamp, local receive timestamp, sequence/nonce when available, stream age, reconnect gaps and measured latency.
5. Reject missing timestamps, stale books, sequence gaps, excessive cross-venue skew, empty sides and insufficient visible depth.
6. Walk the book to the requested quantity with Decimal arithmetic. Calculate fees, spread, slippage reserve, funding, borrow, transfer/network and rebalance costs.
7. Generate separate strategies: pre-funded spot/spot, spot/perpetual hedge, and perpetual/perpetual funding spread. Do not conflate transfer-based arbitrage with no-transfer pre-funded arbitrage.
8. Emit a candidate only after deterministic gates pass. Persist the input evidence and policy version.

CoinGecko and CoinMarketCap are reference sources, not substitutes for exchange-level order books.

## Live execution requirements (not yet implemented)

Cross-exchange order placement is not atomic. Concurrent requests are not a guaranteed simultaneous fill. A real engine must assume one leg fills while the other is rejected, delayed or partially filled.

Before any live order endpoint is added, implement and review:

- Explicit per-account live arm, independent of the LLM and disabled by default.
- Per-venue permission verification, trade-only keys, withdrawal/transfer disabled and IP allowlisting.
- Pre-funded inventory on both venues for spot/spot; no assumption that a transfer settles within the opportunity lifetime.
- Exchange-specific precision, min-notional, contract-size, position-mode, margin and leverage checks.
- Fresh order books and balances at preflight, plus a maximum age/skew/latency policy.
- Concurrent two-leg submission with deterministic order IDs/client-order IDs where supported.
- IOC/FOK or bounded limit-order behavior only where the venue actually supports it.
- Partial-fill, rejected-order, timeout and unknown-order-state handling; reconcile before allowing new exposure.
- A bounded hedge/unwind path, per-order and per-session caps, daily loss limits and a durable emergency stop.
- Durable order intent journal and one authoritative execution owner per account.
- Exchange sandbox tests, recorded-book replay, paper/shadow soak, fault injection and independent review.

A scanner percentage is not expected realized P&L. There is no cross-exchange atomic transaction and no guaranteed profit.

## Messaging and persistence

The default development stack is PostgreSQL plus Redis Streams:
- PostgreSQL stores users, encrypted credential references, exchange permissions, strategy versions, opportunities, order intents, exchange order IDs, fills, fees, inventory, reconciliation and audit records.
- Redis Streams carries market snapshots, opportunity events and execution status. Use consumer groups, explicit acknowledgements, pending-message recovery and idempotent consumers.
- NATS JetStream is an optional alternative if durable replay, independent consumers or multi-service fan-out outgrow the initial Redis design. Do not run two brokers without a measured reason.

Redis is a transport/cache, not the authoritative trade ledger. PostgreSQL is the durable record.

## Formal verification

- TLA+/TLC: model the lifecycle from preflight through submission, partial/unknown state, hedge/unwind and reconciliation. Check single active cycle per account, no new risk while order state is unknown, stop-latch behavior and idempotency.
- Z3: constrain quantity by visible depth, available balances, market minimums, exposure caps, fee reserves and net-edge floor.
- Hypothesis: generate order-book depth, rounding, fees, stale timestamps, partial fills, duplicate events and reconnect sequences.
- Lean: prove pure arithmetic lemmas and gate invariants over exact inputs.
- Bind model assumptions to the deployed build and record test/proof versions. A proof of a model is not a proof that an exchange fills orders or that a trade is profitable.

## Deployment

Recommended production split:
- Replit Reserved VM (or a dedicated always-on VM) is the recommended home for CCXT WebSocket clients, market-data workers and execution orchestration. Replit documents Reserved VM for always-on APIs and background workers.
- PostgreSQL and Redis as managed services or private Docker services with persistent volumes and backups.
- Vercel WebSocket support is now generally available, so it can host the operator UI's realtime WebSocket gateway. However, each connection is pinned to a Function instance and ends at that Function's maximum duration; use external Redis/pub-sub for cross-instance state and reconnection. Do not rely on a Function as the persistent market-feed or execution worker.
- Use Docker Compose for local integration and single-host staging. Do not expose Postgres, Redis or NATS publicly.

The repository's current API is observe-only. Compose provisions local dependencies; database and stream adapters must be wired and migrated before treating persistence as active.

## Local setup

```bash
cp .env.example .env
# Change POSTGRES_PASSWORD before starting.
python -m pip install -e '.[dev]'
pytest -q
docker compose up --build
```

Dashboard: http://localhost:8000  
OpenAPI: http://localhost:8000/docs

## Codex CLI workflow

From the repository root, start `codex` and ask it to:

1. Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/FORMAL_VERIFICATION.md` and this document.
2. Follow test-driven development and inspect existing tests before changing behavior.
3. Implement the CCXT market-data worker and scanner next; use the adapter in `src/z2/exchanges/ccxt_adapter.py`.
4. Add database migrations and Redis Streams consumer contracts before persistence or worker claims.
5. Keep live order submission disabled. Do not add `create_order` until selected exchanges, market types, account permissions, risk limits and the partial-fill recovery design have been approved.
6. Run focused tests, full `pytest -q`, Ruff, Docker Compose health checks and a recorded-book replay. Report exact commands and results.

Do not use unattended auto-approval for credential handling or live trading changes.

## Related open-source references

- CCXT official spot arbitrage example: https://github.com/ccxt/ccxt/blob/master/examples/py/bots/spot-arbitrage-bot.py. Educational example only; its simple market-order approach is not production execution logic.
- Freqtrade: https://github.com/freqtrade/freqtrade. Mature open-source single-bot framework with spot/futures support and dry-run; not a ready-made cross-exchange arbitrage engine.
- OctoBot: https://github.com/Drakkar-Software/OctoBot. Prebuilt strategy/UI framework using CCXT underneath; GPL-3.0, so check licensing before embedding.
- Hummingbot: https://github.com/hummingbot/hummingbot. Strong open-source connector/strategy project, but it uses its own connector stack rather than CCXT; excluded from this CCXT-only implementation.
