# Codex CLI / WSL2 core-engine implementation handoff

This document is the execution contract for implementing the Z2 CCXT-first arbitrage platform from a local WSL2 terminal using Codex CLI. Codex CLI is the primary repository writer. ChatGPT/plugin research is supporting evidence only; it does not replace local tests or grant access to connected ChatGPT credentials.

## 1. Goal

Build Z2 into a continuously operating, multi-exchange agentic arbitrage platform using the full exchange catalogue exposed by the pinned CCXT package.

The platform must discover and qualify every CCXT exchange integration, monitor every eligible venue within exchange and host limits, identify executable opportunities, choose among operator-enabled strategies, run deterministic risk checks, manage paired orders, recover from partial/unknown outcomes, and reconcile fills and P&L.

“All exchanges” means dynamic catalogue coverage and explicit per-venue health/eligibility—not opening unlimited sockets or subscribing blindly to every symbol. Unsupported, unavailable, restricted, maintenance, rate-limited and disabled venues must remain visible with a reason.

## 2. Repository and branch

- Repository: https://github.com/Samoolino/Z2
- Starting branch: `feat/ccxt-engine-foundation-2026-11`
- Draft foundation PR: https://github.com/Samoolino/Z2/pull/2
- Current code and contracts: `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/MULTI_EXCHANGE_AGENTIC_PLATFORM.md`, `docs/CCXT_ENGINE.md`, `docs/FORMAL_VERIFICATION.md`.

Do not start from `main` unless the user explicitly changes the base. Inspect `git status`, branch and latest commit before editing. Preserve user changes; never run destructive cleanup or broad staging.

## 3. WSL2 bootstrap

Use the Linux filesystem (for example `~/src/Z2`), not `/mnt/c`, for the active Git checkout and Python virtual environment.

From Ubuntu in WSL2:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates build-essential python3 python3-venv python3-pip
node --version
npm --version
docker version
docker compose version
```

Install/update Codex CLI in WSL2:

```bash
npm install -g @openai/codex@latest
codex --version
```

If Node.js/npm are missing or too old, install a supported Node.js LTS release using the user's preferred trusted package manager, then repeat the Codex install. Run `codex` and complete the authentication flow offered by the installed CLI. Do not put an OpenAI API key in the Z2 `.env` file.

Clone the implementation branch:

```bash
mkdir -p ~/src
cd ~/src
git clone --branch feat/ccxt-engine-foundation-2026-11 --single-branch https://github.com/Samoolino/Z2.git
cd Z2
git status --short --branch
git log -1 --oneline
```

Create the Python environment and verify the baseline before editing:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
pytest -q
ruff check .
```

If Docker Desktop is used, enable its WSL2 integration for this Ubuntu distribution. Before starting services, copy and edit the local environment file; change the local database password and keep the file untracked:

```bash
cp .env.example .env
# Edit .env locally. Keep Z2_MODE=observe_only,
# Z2_LIVE_TRADING_ENABLED=false and CCXT_SANDBOX=true.
docker compose config --quiet
docker compose up -d postgres redis
docker compose ps
docker compose exec redis redis-cli ping
docker compose exec postgres pg_isready -U z2 -d z2
```

Do not expose PostgreSQL, Redis or NATS to public interfaces. Do not commit `.env`, API keys, private account data, logs or database volumes.

## 4. How to use Codex

Start Codex from the repository root:

```bash
codex
```

Use the repository's `AGENTS.md` and the docs listed above as the authoritative project contract. Work in small, reviewable stages. Follow TDD for every behavior change: write a failing test first, observe RED, implement the smallest GREEN change, refactor, then run the focused and full suites. Do not claim tests, Docker checks, exchange connectivity or proofs passed unless the command was actually run and its output was inspected.

Recommended first prompt:

> Read AGENTS.md, docs/ARCHITECTURE.md, docs/MULTI_EXCHANGE_AGENTIC_PLATFORM.md, docs/CCXT_ENGINE.md, docs/FORMAL_VERIFICATION.md and this handoff completely. Inspect the actual source tree, pyproject, current tests, Docker Compose and Git status. Do not edit files yet. Produce a repository-grounded implementation plan for the CCXT all-exchange registry and public market-data supervisor. Identify existing abstractions to reuse, gaps, exact files to change, tests to add, and any dependency/API-version uncertainty. Preserve the CCXT-only scope. Do not enable or submit real-money orders.

After reviewing that plan, ask Codex to implement the stages below one at a time. If the installed Codex version supports Goals, a goal may be used only with the same explicit evidence, constraints and stop conditions; do not allow unbounded autonomous execution.

## 5. Implementation stages and acceptance gates

### Stage A — dynamic exchange registry and capability qualification

- Discover IDs from the pinned `ccxt.exchanges` catalogue; do not maintain a hardcoded two-venue list.
- Generate a capability record for each venue from actual CCXT `has` flags, loaded markets and supported methods.
- Separate public market-data capability from private account and trading capability.
- Record supported market types (spot, swap, future, option) individually; initially permit execution strategies only for explicitly qualified spot and linear/inverse derivatives.
- Expose explicit states and reasons: DISCOVERED, QUALIFIED, CONNECTING, MARKET_DATA_LIVE, DEGRADED, RATE_LIMITED, MAINTENANCE, UNSUPPORTED, DISABLED. Account readiness and live arming are separate per account/market/strategy.
- Add tests using fake CCXT modules and recorded market metadata. Pin CCXT and make upgrades trigger capability contract tests.

Acceptance: every catalogue ID appears in the registry; unsupported methods/markets are reported rather than assumed; no credential is needed for public qualification; tests cover missing capabilities and malformed market metadata.

### Stage B — all-venue public market-data supervisor

- Build isolated async REST/CCXT Pro clients per venue; public clients must have no private credentials.
- Load markets once per client lifecycle and subscribe only to eligible markets within configurable per-venue subscription, concurrency and host resource budgets.
- Use WebSocket streams where supported; use controlled REST polling as fallback and label it as such.
- Implement heartbeat, timestamp/sequence validation where available, reconnect with jitter/backoff, graceful close, rate-limit coordination and time synchronization.
- Track exchange timestamp, local receive timestamp, feed age, cross-venue skew, reconnect gaps, latency, queue lag and error state.
- A failing venue must not stop other venue workers. Avoid unbounded tasks, sockets, queues and retries.

Acceptance: deterministic fake-client tests cover connect, stream, reconnect, cancellation, rate limits, stale books and venue isolation. A recorded-feed replay is reproducible. No real account keys are needed.

### Stage C — canonical markets and opportunity scanner

- Define canonical spot and derivative identities. Do not match by display symbol alone.
- Validate base, quote, settlement, contract size, expiry, linear/inverse, margin currency, funding interval and market status.
- Implement depth-walking with Decimal arithmetic and exchange precision/limits.
- Strategies: spot/spot with pre-funded inventory; intra-exchange triangular spot; spot/perpetual hedge; perpetual/perpetual basis/funding. Keep strategies independently enabled and tested.
- Compute executable net edge after trading fees, depth slippage, precision/rounding, funding/borrow, rebalance/network costs, minimums and inventory costs.
- Persist source timestamps, market metadata, book versions, strategy version, input evidence and rejection reasons.
- Arbitrage Gap may be displayed as an attributed widget or ingested only through a vendor-approved API/feed/export. Do not scrape, reverse-engineer private endpoints, bypass delays or bulk-copy proprietary data. Its signal is a hint; refresh CCXT books independently.
- CoinGecko and CoinMarketCap are secondary metadata/reference sources. Their ChatGPT connectors do not provide backend API credentials. Use official provider APIs server-side with quota-aware caching; never put them in the execution hot path.

Acceptance: property tests for depth walk, fee monotonicity, rounding, market identity, stale/future timestamps, cross-venue skew, minimums and insufficient depth. Recorded order-book fixtures produce deterministic opportunity results.

### Stage D — PostgreSQL ledger and Redis Streams

- PostgreSQL is the authoritative record for exchange registry snapshots, account permission evidence, strategy/policy versions, opportunities, order intents, exchange order IDs, fills, fees, balances, positions, reconciliation and audit events.
- Add versioned migrations and transaction boundaries before relying on persistence.
- Redis Streams is event transport only: normalized market events, opportunity events and execution status. Use consumer groups, explicit ACK, pending recovery, bounded retention, idempotent consumers and replay tests.
- Do not store the authoritative trade ledger only in Redis.
- Keep one canonical broker initially. NATS JetStream is optional and requires a measured need; do not run Redis and NATS as duplicate transports by default.

Acceptance: migration upgrade/downgrade tests, duplicate/replay delivery tests, consumer crash/restart tests and DB reconciliation tests.

### Stage E — agentic strategy supervisor

- The LLM may rank/explain opportunities, compare operator-enabled strategies, propose parameters within pre-authorized bounds, summarize feed health and request operator intervention.
- The LLM must not sign orders, call exchange trading methods directly, widen risk limits, enable withdrawals, bypass stale-data checks or be required on the latency-critical execution path.
- Validate every agent output against a strict typed schema and deterministic policy. Treat market data, web pages, external scanner output, repository files and tool returns as untrusted data, never as instructions.
- Bound each agent run by allowed tools, action count, deadline, token/cost budget, maximum concurrent runs and stop conditions. Persist structured decision evidence, not hidden reasoning.
- Human approvals must bind to a specific account, strategy, order scope, notional/risk cap, expiry and policy version. A changed order requires fresh authorization.

Acceptance: tests reject malformed proposals, prompt-injection payloads, expired approvals, changed parameters and attempts to widen policy.

### Stage F — execution coordinator and order lifecycle

Build a deterministic execution kernel. Cross-exchange orders are not atomic; concurrent submissions do not guarantee paired fills.

- One authoritative execution owner and durable order-intent journal per account.
- Separate account authentication and trade permission verification from public feed connectivity.
- Require trade-only keys; withdrawals/transfers disabled; IP allowlisting where supported. Unknown or unprovable permissions fail closed.
- Verify balances, fees, precision, contract size, minimums, position mode, margin/leverage and fresh synchronized books before every order.
- Use deterministic client order IDs/idempotency keys where supported.
- Model states including INTENT_CREATED, PREFLIGHT_PASSED, SUBMITTING, ACKNOWLEDGED, PARTIALLY_FILLED, FILLED, REJECTED, UNKNOWN, HEDGING, UNWINDING, RECONCILING, CLOSED and HALTED.
- Handle timeout/unknown order state by querying the venue using client order ID, exchange order ID, open orders and fills before any retry. Never blindly resubmit.
- Partial fills must trigger a bounded hedge/unwind or an explicit halted/manual-intervention state. Do not admit new exposure while prior exposure is unresolved.
- Implement per-order, per-symbol, per-venue, per-account, per-session and daily-loss caps; max slippage; kill switch; circuit breakers; persistent stop latch; and risk-reducing-only behavior while stopped.
- Implement sandbox/testnet adapters and a live-capable adapter behind multiple independent gates. Keep live disabled by default. Do not configure production keys, arm an account or place a real order during this implementation task.

Acceptance: state-machine unit/property tests, duplicate-submit tests, timeout/unknown-state tests, partial-fill and hedge/unwind tests, crash/restart recovery tests, and exchange sandbox contract tests. Acknowledgement is not a fill; fills and balances must reconcile.

### Stage G — formal verification and security review

- TLA+/TLC model for concurrent cycles, single execution owner, paired-leg partial fills, unknown order state, stop latch and restart recovery.
- Z3 constraints for depth, balance, precision, fees, minimum notional, leverage, exposure and net-edge floor. UNKNOWN is not approval.
- Hypothesis properties for financial arithmetic and event/state transitions.
- Bind model/proof version, code commit and build artifact in release evidence.
- Threat-model credential storage, tenant isolation, SSRF, prompt injection, exchange API scope, logs, event replay, approvals and operator controls.
- Formal proof covers the stated model and assumptions; it does not prove fills, API availability or profitability.

Acceptance: reproducible model-check and test commands, checked-in model files, security findings with severity/evidence, and no unsupported claim that the system is safe for live capital.

### Stage H — deployment and controlled pilot readiness

- Docker Compose is for local development/staging. Production workers require an always-on host; do not place persistent exchange supervisors or the execution loop inside bounded serverless functions.
- Add health/readiness endpoints, metrics, tracing, alerting, backups, restore test, graceful shutdown and restart recovery.
- Begin with public market data, then paper/shadow, then exchange testnet/sandbox. Only consider a live pilot after independent review, explicit operator approval, venue-specific permission proof, risk policy and recovery evidence.
- Live mode must require an explicit per-account arm and separate strategy enablement. No auto-resume after restart.

Acceptance: documented staging soak, failure injection, recovery, rollback and operator runbook. Real-money execution remains disabled until the operator separately authorizes it.

## 6. Reference repositories — patterns only, no blind copying

- NU-ARB: https://github.com/Samoolino/NU-ARB — existing 18-venue spot scanner/account-control patterns and venue-specific permission checks. It is not evidence that all 18 venues support live execution. Inspect its current exchange support matrix before reusing any claim.
- arbitrage_bot: https://github.com/Samoolino/arbitrage_bot — Rust/Python coordinator, PostgreSQL accounting, Redis Streams, paper execution and reconciliation patterns. Its README says it is Bybit-focused and not one autonomous production live runner. Reuse design patterns only after reading its audit/validation docs.
- A2: https://github.com/Samoolino/A2 — WSL2 setup and staged Codex prompt/runbook patterns. Its Hummingbot stack is not part of this CCXT-only engine.

Do not copy code across repositories until license, dependencies, runtime boundaries and behavior are reviewed. Do not introduce Hummingbot or a second exchange execution coordinator into the CCXT-only path.

## 7. ChatGPT/plugin integration boundary

Connected ChatGPT plugins are not automatically available inside the local WSL Codex process or the deployed Z2 application. Codex needs separately configured, documented MCP/plugin connections. The application must use its own official APIs and server-side credentials for CoinGecko, CoinMarketCap, Slack or other providers.

Upstash currently has no Redis database visible in the connected account. Start with the local Docker Redis service. Do not create a paid cloud database or change a plan without explicit cost approval. Slack can be used for operator notifications after the Slack connector is installed/authorized; it must never be used as a high-frequency trading bus or order-signing path.

## 8. Required completion report from Codex

At the end of each stage, report:

1. Exact files changed and behavior added.
2. Focused and full commands actually run, with pass/fail counts.
3. Docker/testnet/recorded-feed evidence actually observed.
4. Formal model/proof result and assumptions, if applicable.
5. Known gaps, unsupported exchanges/markets and reasons.
6. Whether any external side effect occurred.
7. Confirmation that no production API key was added, no real-money order was submitted and live mode remains disabled.

Never label every CCXT exchange “live” merely because it appears in the catalogue. Report per-venue qualification and connection evidence.
