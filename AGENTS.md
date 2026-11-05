# Z2 engineering instructions

- Keep the system observe-only until a separate reviewed implementation explicitly enables paper and then live execution.
- Never add exchange order submission to the current API surface without tests, explicit operator approval and a documented risk review.
- The LLM is an advisory interface only; deterministic code owns risk authorization.
- Use Decimal for all financial arithmetic. Do not use binary floating point for price, quantity, fees or P&L.
- Treat scanner signals as untrusted hints. Re-fetch and validate executable venue books independently.
- Fail closed on stale/future timestamps, clock skew, incomplete depth, missing balances, unknown permissions, unknown order status or failed reconciliation.
- Never permit withdrawal/transfer permissions on trading keys. Keep secrets out of source, UI, logs, tests and chat.
- Preserve idempotency, durable journaling, kill-switch and reconciliation requirements.
- Use test-driven development: add a failing regression test before changing behavior; run focused tests and then the full suite.
- Do not claim that backtests, paper results, formal proofs or modeled worst-case floors guarantee realized profit.
- Record actual verification evidence. Never report a test or deployment as successful unless it was run and its result was observed.
