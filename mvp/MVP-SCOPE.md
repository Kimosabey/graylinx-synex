# MVP scope — proposal

**Status: proposed, not agreed.** Closing question S1 turns this into the build
plan. Until then, treat every line as a suggestion.

## The MVP test

The MVP is the smallest set of features that closes the loop end to end for one
asset class on one site:

```
a fault is detected → a case opens → it is explained with evidence
→ the checks narrow it to a root cause → a work order is created
→ the work is done → the platform proves it worked
```

The case is the step the first draft of this document missed. A fault does not
become a work order in one hop: somebody has to answer questions, and some of
those answers come back "could not check". That middle is where the work actually
happens, and it is `RC1`–`RC8`.

Anything that does not sit on that path is deferred, however attractive it is.
A demo that answers questions beautifully but cannot prove a repair worked has
not demonstrated the product.

## What is in — 69 of 122 features

| Domain | In MVP | Why |
|---|---|---|
| Synex Copilot | C1–C12 | The whole point. Ask, resolve context, route, gather evidence, explain, recommend, refuse honestly, draft, route approval, hold task state, respect scope, cite sources |
| Conversation shell | C15–C20 | The Copilot is the product, so the shell is not optional: thread memory on every route, a conversational front door, read-only data lookup, route transparency, export, and the skill registry all of it routes through |
| Case Resolution | RC1–RC8 | The lifecycle between a named fault and a closed work order: state machine, curated checklists, capability routing, findings with an explicit cannot-check, the blocking gate, root cause with corrective and preventive actions, three escalation routes, idempotent seeding |
| FDD | F1–F8, F10, F11, F14 | The six models, residuals, gates, isolation path, sensor-bias detection, honest ambiguity, NO_DIAGNOSIS, model health, quarantine, ΔT check |
| Work Orders | W1–W4, W8–W10 | Create from chat or fault, carry the evidence, deterministic priority, capture findings, cannot close unproven, reopen on failure |
| Verification | V1–V4, V6 | Post-work residuals under valid gates, persistence, fault clear, PASS/FAIL/UNKNOWN |
| Reports | R1, R3, R5, R10 | Ask, explain a change, drill to source, reconcile against source |
| Knowledge | K1, K5 | SOP retrieval with the source shown |
| Asset | A1 | One equipment story |
| Roles | U3, U6, U7, U8 | Four personas, because the loop needs a fault judged, worked, approved and governed |
| Energy | E1 | The efficiency baseline the FDD proxy is measured against |
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
| Energy cost, forecasting, optimisation advice (E2–E4) | The analytics exist on the shared platform; the MVP needs the baseline `E1`, not the advice layer |
| Learning from closed cases (F9, V7) | Deliberately withheld: without a retraction mechanism one wrong confirmed root cause becomes permanent precedent. See `CONTEXT.md` §10 |
| Multi-skill orchestration | `C10` carries a job across steps without a planner running skills in parallel |

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
9. A follow-up question — "and its ΔT?" — resolves against the previous turn on
   **every** route, and every turn is present in the stored thread with no holes.
   Verified by asking the same follow-up after each kind of answer.
10. A case cannot leave `awaiting findings` while a blocking item is unanswered,
    and a "could not check" answer does **not** satisfy the item — verified by
    attempting both.
11. Escalating a case up leaves it unassigned and says so, rather than implying
    somebody has it.
12. Re-running the fault scan over the same window opens no second case for an
    episode that already has one.
13. Every checklist item shown to a technician traces to the curated library, and
    no item in the acceptance run was generated by a model.

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
| 8 | Conversation shell: threads, turn memory on every route, the conversational front door, read-only lookup | Stages 3 and 4 |
| 9 | Case resolution: state machine, curated checklists, capability routing, the blocking gate, escalation routes | Stages 2, 5 and the checklist library being SME-reviewed |

Stages 1 and 2 are the critical path and are the ones blocked by SME questions.
Stages 3 and 8 have no SME dependency and can start immediately — the Control
Plane and the conversation shell are both plain software.

Stage 9 has a dependency that is not a threshold: the checklist library is curated
content and cannot ship until an SME has reviewed it, because a plausible-but-wrong
checklist item directs physical work on pressurised equipment. That review is the
long pole nobody costs for.

Four MVP features are named by no stage — `A1`, `U3`, `S1` and `S4`. Two of them
are safety features. This is question Q17.
