---- MODULE ExecutionProtocol ----
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS MaxExposure, IdempotencyKeys

ASSUME
  /\ MaxExposure \in Nat
  /\ MaxExposure > 0
  /\ IdempotencyKeys # {}

Phases ==
  {"IDLE", "PREFLIGHT", "RESERVED", "SUBMITTING",
   "UNKNOWN", "PARTIAL", "RECONCILING", "DONE", "HALTED"}

VARIABLES
  phase,
  stopLatched,
  preflightPassed,
  riskApproved,
  liveArmed,
  orderUnknown,
  exposure,
  submittedKeys,
  submitCount,
  currentKey,
  submitAuthorized,
  stopWasClearAtSubmit,
  stopSubmitCount

vars ==
  <<phase, stopLatched, preflightPassed, riskApproved, liveArmed,
    orderUnknown, exposure, submittedKeys, submitCount, currentKey,
    submitAuthorized, stopWasClearAtSubmit, stopSubmitCount>>

Init ==
  /\ phase = "IDLE"
  /\ stopLatched = FALSE
  /\ preflightPassed = FALSE
  /\ riskApproved = FALSE
  /\ liveArmed = FALSE
  /\ orderUnknown = FALSE
  /\ exposure = 0
  /\ submittedKeys = {}
  /\ submitCount = 0
  /\ currentKey = "NONE"
  /\ submitAuthorized = FALSE
  /\ stopWasClearAtSubmit = FALSE
  /\ stopSubmitCount = 0

BeginCycle ==
  /\ phase \in {"IDLE", "DONE"}
  /\ ~stopLatched
  /\ exposure = 0
  /\ phase' = "PREFLIGHT"
  /\ preflightPassed' = FALSE
  /\ riskApproved' = FALSE
  /\ liveArmed' = FALSE
  /\ orderUnknown' = FALSE
  /\ currentKey' = "NONE"
  /\ submitAuthorized' = FALSE
  /\ stopWasClearAtSubmit' = FALSE
  /\ UNCHANGED <<stopLatched, exposure, submittedKeys, submitCount, stopSubmitCount>>

PreflightPass ==
  /\ phase = "PREFLIGHT"
  /\ phase' = "RESERVED"
  /\ preflightPassed' = TRUE
  /\ UNCHANGED <<stopLatched, riskApproved, liveArmed, orderUnknown,
                 exposure, submittedKeys, submitCount, currentKey,
                 submitAuthorized, stopWasClearAtSubmit, stopSubmitCount>>

ApproveRisk ==
  /\ phase = "RESERVED"
  /\ preflightPassed
  /\ ~stopLatched
  /\ riskApproved' = TRUE
  /\ UNCHANGED <<phase, stopLatched, preflightPassed, liveArmed,
                 orderUnknown, exposure, submittedKeys, submitCount,
                 currentKey, submitAuthorized, stopWasClearAtSubmit,
                 stopSubmitCount>>

ArmLive ==
  /\ phase = "RESERVED"
  /\ preflightPassed
  /\ riskApproved
  /\ ~stopLatched
  /\ liveArmed' = TRUE
  /\ UNCHANGED <<phase, stopLatched, preflightPassed, riskApproved,
                 orderUnknown, exposure, submittedKeys, submitCount,
                 currentKey, submitAuthorized, stopWasClearAtSubmit,
                 stopSubmitCount>>

Submit(k, amount) ==
  /\ phase = "RESERVED"
  /\ preflightPassed
  /\ riskApproved
  /\ liveArmed
  /\ ~stopLatched
  /\ ~orderUnknown
  /\ k \in IdempotencyKeys
  /\ k \notin submittedKeys
  /\ amount \in 1..MaxExposure
  /\ exposure + amount <= MaxExposure
  /\ phase' = "SUBMITTING"
  /\ exposure' = exposure + amount
  /\ submittedKeys' = submittedKeys \cup {k}
  /\ submitCount' = submitCount + 1
  /\ currentKey' = k
  /\ submitAuthorized' = TRUE
  /\ stopWasClearAtSubmit' = TRUE
  /\ UNCHANGED <<stopLatched, preflightPassed, riskApproved, liveArmed,
                 orderUnknown, stopSubmitCount>>

AckPartial ==
  /\ phase = "SUBMITTING"
  /\ phase' = "PARTIAL"
  /\ UNCHANGED <<stopLatched, preflightPassed, riskApproved, liveArmed,
                 orderUnknown, exposure, submittedKeys, submitCount,
                 currentKey, submitAuthorized, stopWasClearAtSubmit,
                 stopSubmitCount>>

AckUnknown ==
  /\ phase = "SUBMITTING"
  /\ phase' = "UNKNOWN"
  /\ orderUnknown' = TRUE
  /\ UNCHANGED <<stopLatched, preflightPassed, riskApproved, liveArmed,
                 exposure, submittedKeys, submitCount, currentKey,
                 submitAuthorized, stopWasClearAtSubmit, stopSubmitCount>>

AckFilled ==
  /\ phase \in {"SUBMITTING", "PARTIAL"}
  /\ phase' = "RECONCILING"
  /\ UNCHANGED <<stopLatched, preflightPassed, riskApproved, liveArmed,
                 orderUnknown, exposure, submittedKeys, submitCount,
                 currentKey, submitAuthorized, stopWasClearAtSubmit,
                 stopSubmitCount>>

ConfirmFlat ==
  /\ phase \in {"UNKNOWN", "PARTIAL", "RECONCILING"}
  /\ phase' = IF stopLatched THEN "HALTED" ELSE "DONE"
  /\ orderUnknown' = FALSE
  /\ exposure' = 0
  /\ UNCHANGED <<stopLatched, preflightPassed, riskApproved, liveArmed,
                 submittedKeys, submitCount, currentKey, submitAuthorized,
                 stopWasClearAtSubmit, stopSubmitCount>>

AbortBeforeSubmit ==
  /\ phase \in {"PREFLIGHT", "RESERVED"}
  /\ phase' = IF stopLatched THEN "HALTED" ELSE "DONE"
  /\ preflightPassed' = FALSE
  /\ riskApproved' = FALSE
  /\ liveArmed' = FALSE
  /\ UNCHANGED <<stopLatched, orderUnknown, exposure, submittedKeys,
                 submitCount, currentKey, submitAuthorized,
                 stopWasClearAtSubmit, stopSubmitCount>>

LatchStop ==
  /\ ~stopLatched
  /\ stopLatched' = TRUE
  /\ stopSubmitCount' = submitCount
  /\ phase' = IF phase \in {"IDLE", "DONE"} THEN "HALTED" ELSE phase
  /\ UNCHANGED <<preflightPassed, riskApproved, liveArmed, orderUnknown,
                 exposure, submittedKeys, submitCount, currentKey,
                 submitAuthorized, stopWasClearAtSubmit>>

ResetStop ==
  /\ stopLatched
  /\ phase \in {"HALTED", "DONE"}
  /\ exposure = 0
  /\ stopLatched' = FALSE
  /\ phase' = "IDLE"
  /\ stopSubmitCount' = submitCount
  /\ UNCHANGED <<preflightPassed, riskApproved, liveArmed, orderUnknown,
                 exposure, submittedKeys, submitCount, currentKey,
                 submitAuthorized, stopWasClearAtSubmit>>

Next ==
  \/ BeginCycle
  \/ PreflightPass
  \/ ApproveRisk
  \/ ArmLive
  \/ \E k \in IdempotencyKeys, amount \in 1..MaxExposure : Submit(k, amount)
  \/ AckPartial
  \/ AckUnknown
  \/ AckFilled
  \/ ConfirmFlat
  \/ AbortBeforeSubmit
  \/ LatchStop
  \/ ResetStop

TypeOK ==
  /\ phase \in Phases
  /\ stopLatched \in BOOLEAN
  /\ preflightPassed \in BOOLEAN
  /\ riskApproved \in BOOLEAN
  /\ liveArmed \in BOOLEAN
  /\ orderUnknown \in BOOLEAN
  /\ exposure \in 0..MaxExposure
  /\ submittedKeys \subseteq IdempotencyKeys
  /\ submitCount \in Nat
  /\ submitCount = Cardinality(submittedKeys)
  /\ currentKey \in IdempotencyKeys \cup {"NONE"}
  /\ submitAuthorized \in BOOLEAN
  /\ stopWasClearAtSubmit \in BOOLEAN
  /\ stopSubmitCount \in Nat

ExposureBound ==
  exposure <= MaxExposure

NoUnauthorizedSubmission ==
  submitAuthorized =>
    preflightPassed /\ riskApproved /\ liveArmed /\ stopWasClearAtSubmit

NoDuplicateIdempotency ==
  submitCount = Cardinality(submittedKeys)

UnknownBlocksNewRisk ==
  orderUnknown => phase \notin {"RESERVED", "SUBMITTING"}

StopBlocksNewSubmissions ==
  [] (stopLatched => submitCount = stopSubmitCount)

Spec ==
  Init /\ [][Next]_vars

====
