# Z2 — Agentic Arbitrage Intelligence & Execution Orchestrator

Z2 is a complete agentic, multi-exchange arbitrage platform. It extends the Arbitrage Gap concept with its own CCXT-powered market intelligence, strategy selection, deterministic risk authorization, automated execution, reconciliation and operator interface.

**Product scope:** all exchanges supported by the pinned CCXT catalogue are dynamically discovered and capability-qualified. Public market data is monitored across every enabled/eligible venue; private account trading is armed separately per configured account, market type and strategy policy. No fixed two-exchange ceiling.

**Current implementation status:** observe-only foundation plus a draft CCXT connector/infrastructure PR. No exchange credentials are configured, no vendor feed is connected, and no live order endpoint is enabled. Z2 does not claim live trading readiness or guaranteed profit.

## Product architecture

- **Market intelligence:** all-venue CCXT REST/WebSocket market feeds, canonical market mapping, executable order-book depth, route discovery and net-edge verification.
- **Agentic strategy:** opportunity ranking, strategy selection within operator-approved bounds, rationale, alerts and bounded parameter control.
- **Execution:** paired-order coordinator, per-account risk gates, partial-fill hedging, order-state recovery and reconciliation.
- **Operations:** exchange universe, live scanner, strategy cockpit, execution terminal, risk center and audit timeline.

Read [docs/MULTI_EXCHANGE_AGENTIC_PLATFORM.md](docs/MULTI_EXCHANGE_AGENTIC_PLATFORM.md) for the complete product contract and delivery gates. Read [docs/CCXT_ENGINE.md](docs/CCXT_ENGINE.md) for the current adapter and connector boundaries.

## Non-negotiable boundaries

- Public market-data connection is separate from private account authentication and live-trading authorization.
- Live trading is disabled by default and requires separately verified trade permissions, explicit per-account arming and risk policy.
- Never enable withdrawal or transfer permissions on trading keys.
- The LLM is an agentic supervisor/advisor, not an order signer. Deterministic code owns final risk authorization and order submission.
- Cross-exchange orders are not atomic. Partial fills, unknown order status, hedging and reconciliation are first-class states.
- Arbitrage Gap is an optional external reference or approved feed; Z2's own CCXT order books determine executability.
- CoinGecko and CoinMarketCap are market-reference sources, not executable order-book sources.
- Formal proofs apply to stated models and assumptions; they do not guarantee exchange fills or profit.

## Repository and implementation

Repository: https://github.com/Samoolino/Z2

The CCXT foundation is under review in [PR #2](https://github.com/Samoolino/Z2/pull/2). It introduces the first asynchronous CCXT adapter and local infrastructure but is not the complete trading engine. The next delivery gates are the dynamic exchange registry, all-venue public feed supervisor, canonical opportunity scanner, agent supervisor, durable event/ledger layer, paper/shadow execution, sandbox execution and reviewed live pilot.

## Local development

    cp .env.example .env
    # Change POSTGRES_PASSWORD before starting.
    python -m pip install -e '.[dev]'
    pytest -q
    docker compose up --build

The existing API remains observe-only. Do not treat provisioned PostgreSQL/Redis services as active persistence until migrations and application consumers are implemented.
