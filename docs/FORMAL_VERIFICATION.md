# Formal verification and execution assurance

Formal methods apply to the rules and state transitions Z2 controls. They do not turn market risk into a guarantee of profit.

## TLA+ / TLC — concurrent execution protocol

Model:
- cycle lifecycle: IDLE -> PREFLIGHT -> RESERVED -> SUBMITTING -> PARTIAL/UNKNOWN -> HEDGING/UNWINDING -> RECONCILED;
- per-account active-cycle lock;
- durable idempotency keys;
- operator stop latch;
- process restart and lost-response recovery.

Safety properties to model-check:
- LiveSubmit implies PreflightPassed, RiskApproved and ExplicitLiveArm.
- ActiveCycles(account) is never greater than one.
- UnknownOrderState implies NoNewRisk.
- StopLatched implies NoNewExposure.
- An idempotency key cannot produce two distinct exchange submissions.
- Exposure remains within configured limits after every state transition.

## Lean 4 — pure financial core

Prove arithmetic properties for:
- quote spent and base acquired during depth walking;
- fees are non-negative and reduce net proceeds;
- increasing a fee cannot increase assessed net P&L;
- a candidate failing a required gate cannot be marked eligible;
- exact rational/decimal conversion and rounding boundaries.

## Z3 — constrained sizing

Check constraints such as:
- notional <= min(configured cap, fresh available balances, visible depth);
- net-after-fees >= required floor;
- worst-case reserve >= configured adverse-movement allowance;
- per-asset and total exposure remain under policy;
- exchange precision/minimum-notional constraints are satisfied.

A sat result means a model assignment satisfies the encoded constraints, not that an exchange will fill an order. An unknown result is not approval.

## Hypothesis and deterministic tests

Generate cases for:
- order-book depth boundaries;
- decimal precision, tick sizes and step sizes;
- fee changes and fee-tier uncertainty;
- stale/future timestamps and cross-venue clock skew;
- partial fills, duplicate events, reconnects and unknown order outcomes;
- insufficient balances and exchange minimum-notional constraints.

## Runtime evidence

Every live-eligible decision must retain source/receive timestamps, book sequence/version and latency, venue permission evidence and expiry, depth walk and fee schedule, risk-policy version, deterministic assessment, order IDs, acknowledgements, fills and reconciliation records.

The UI must expose proof/test status and runtime evidence separately. A passing formal model does not prove the deployed binary matches the model unless build provenance, version pinning and release checks bind them together.
