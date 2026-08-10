# MVP scope — proposal

**Status: proposed, not agreed.** Closing question S1 turns this into the build
plan. Until then, treat every line as a suggestion.

## The MVP test

The MVP is the smallest set of features that closes the loop end to end for one
asset class on one site:

```
a fault is detected → it is explained with evidence → a work order is created
→ the work is done → the platform proves it worked
```

Anything that does not sit on that path is deferred, however attractive it is.
A demo that answers questions beautifully but cannot prove a repair worked has
not demonstrated the product.

## What is in — 51 of 101 features

| Domain | In MVP | Why |
|---|---|---|
| Synex Copilot | C1–C12 | The whole point. Ask, resolve context, route, gather evidence, explain, recommend, refuse honestly, draft, route approval, hold task state, respect scope, cite sources |
| FDD | F1–F8, F10, F11, F14 | The six models, residuals, gates, isolation path, sensor-bias detection, honest ambiguity, NO_DIAGNOSIS, model health, quarantine, ΔT check |
| Work Orders | W1–W4, W8–W10 | Create from chat or fault, carry the evidence, deterministic priority, capture findings, cannot close unproven, reopen on failure |
| Verification | V1–V4, V6 | Post-work residuals under valid gates, persistence, fault clear, PASS/FAIL/UNKNOWN |
| Reports | R1, R3, R5, R10 | Ask, explain a change, drill to source, reconcile against source |
| Knowledge | K1, K5 | SOP retrieval with the source shown |
| Asset | A1 | One equipment story |
| Roles | U3 | The technician job pack |
| Safety | S1, S4 | Block safety-critical actions; safety answers only from the SOP |
| Control Plane | G1–G6 | Identity and scope per turn, risk class, approvals, tool gateway, idempotency, audit |

## What is out, and why

| Deferred | Reason |
|---|---|
| Planning and inventory (PL1–PL5, I1–I4) | Needs CMMS and stores integration depth that does not change whether the loop works |
| Alerts (L1–L6) | Valuable, but the MVP has few enough assets that alert noise is not yet the problem |
| Customer portal (R9, U1) | Multi-tenant surface area is a large security burden for little MVP learning |
| Executive briefing (C14, U2, R6) | Needs a history of outcomes to summarise; there will not be one yet |
| Watches (C13) | Depends on alerting |
| Cooling tower (F13) | Blocked on S2, and the tower changes condenser water behaviour in ways that complicate early model validation |
| Re-baselining (F12) | Not needed until the first verified major repair completes |
| Break-glass, policy simulation (G7, G8) | Governance maturity, not product proof |

## MVP acceptance criteria

The MVP is done when all of these are demonstrably true on real site data:

1. A fault raised by the FDD engine can be explained by the Copilot with its
   residuals, gates and rule path visible.
2. When a gate fails, the Copilot returns `NO_DIAGNOSIS` and names the failed
   check — verified by deliberately invalidating a signal.
3. A work order created from that fault carries its evidence, and its priority
   can be recalculated by hand from the formula.
4. The work order cannot be closed until verification returns PASS.
5. Verification returns `UNKNOWN`, not `PASS`, when the machine has not run
   under comparable conditions since the work.
6. An out-of-scope request is blocked with a plain reason and the correct route.
7. Every material action has a complete audit trail with a policy version.
8. No answer in the acceptance run contains a number absent from the evidence
   pack.

## Sequencing

| Stage | Build | Depends on |
|---|---|---|
| 0 | Data in, tags normalised, asset hierarchy | — |
| 1 | Six models, residuals, validity flags, model health | Stage 0, Q1, Q2, Q14 |
| 2 | Gates, persistence, isolation path, NO_DIAGNOSIS | Stage 1, Q3–Q6, Q9 |
| 3 | Control Plane: identity, scope, risk, tool gateway, audit | Stage 0 |
| 4 | Copilot read path: ask, context, route, evidence, explain | Stages 2 and 3 |
| 5 | Work orders: create, evidence, priority, findings | Stages 3 and 4 |
| 6 | Verification and the close gate | Stages 1, 2 and 5, plus Q15 |
| 7 | Reports and knowledge retrieval | Stage 4 |

Stages 1 and 2 are the critical path and are the ones blocked by SME questions.
Stage 3 has no SME dependency and can start immediately.
