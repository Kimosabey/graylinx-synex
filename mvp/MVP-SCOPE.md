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
happens, and it is `RC1`–`RC18`.

Anything that does not sit on that path is deferred, however attractive it is.
A demo that answers questions beautifully but cannot prove a repair worked has
not demonstrated the product.

## What is in — 93 of 146 features

| Domain | In MVP | Why |
|---|---|---|
| Synex Copilot | C1–C12 | The whole point. Ask, resolve context, route, gather evidence, explain, recommend, refuse honestly, draft, route approval, hold task state, respect scope, cite sources |
| Conversation shell | C15–C20 | The Copilot is the product, so the shell is not optional: thread memory on every route, a conversational front door, read-only data lookup, route transparency, export, and the skill registry all of it routes through |
| Honesty discipline | C21–C26 | What stops a fluent answer from being a confident wrong one: every number a value or a stated absence, every artefact carrying its data window, untrusted periods marked and honoured, figures drawn only from the evidence pack, four response modes graded by how much the evidence can actually settle, and per-signal provenance so a fabricated measurement can never read as a real one |
| Case Resolution | RC1–RC18 | The lifecycle between a named fault and a closed work order: state machine, curated checklists, capability routing, findings with an explicit cannot-check, the blocking gate, root cause with corrective and preventive actions, three escalation routes, seeding that is both safe to re-run and actually run, ageing, measured-versus-estimated, stored readings offered only as a confirmation, differential narrowing with an elimination audit, honest exhaustion, the work order escalation produces, and a deterministic assignee |
| FDD | F1–F8, F10–F11, F14–F17 | The six models, residuals, gates, isolation path, sensor-bias detection, honest ambiguity, NO_DIAGNOSIS, model health, quarantine, ΔT check, per-asset reference bands, cross-signal physical plausibility, and one severity scale |
| Work Orders | W1–W4, W8–W10 | Create from chat or fault, carry the evidence, deterministic priority, capture findings, cannot close unproven, reopen on failure |
| Verification | V1–V4, V6 | Post-work residuals under valid gates, persistence, fault clear, PASS/FAIL/UNKNOWN |
| Reports | R1, R3, R5, R10 | Ask, explain a change, drill to source, reconcile against source |
| Knowledge | K1, K5 | SOP retrieval with the source shown |
| Asset | A1 | One equipment story |
| Roles | U3, U6–U8 | Four personas, because the loop needs a fault judged, worked, approved and governed |
| Energy | E1 | The efficiency baseline the FDD proxy is measured against |
| Evaluation | EV1–EV4 | A demonstrator that cannot be shown to be honest is worth little: a golden case set, a gate that fails the build on dishonest answers, dimensions no overall score can trade away, and tests of the gate itself |
| Safety | S1, S4, S6 | Block safety-critical actions; safety answers only from the SOP; and a response class for faults answered by stopping the machine rather than by raising a work order |
| Control Plane | G1–G6 | Identity and scope per turn, risk class, approvals, tool gateway, idempotency, audit |

## The shape of the cut, and why it stopped growing

The table below is generated from the register, so it cannot drift from what is
actually being built. Read the *shape* of it rather than the totals.

<!-- BEGIN GENERATED — scripts/sync_mvp_html.py. Do not edit by hand. -->

| Domain | In | Out | In the cut |
|---|--:|--:|---|
| Synex Copilot | 24 | 2 | C1–C12, C15–C26 |
| Case Resolution | 18 | 0 | RC1–RC18 |
| Reliability & FDD | 14 | 3 | F1–F8, F10–F11, F14–F17 |
| Work Orders | 7 | 5 | W1–W4, W8–W10 |
| Control Plane | 6 | 2 | G1–G6 |
| Verification | 5 | 2 | V1–V4, V6 |
| Reports | 4 | 6 | R1, R3, R5, R10 |
| Evaluation | 4 | 0 | EV1–EV4 |
| Roles | 4 | 4 | U3, U6–U8 |
| Safety | 3 | 3 | S1, S4, S6 |
| Knowledge | 2 | 4 | K1, K5 |
| Asset Intelligence | 1 | 4 | A1 |
| Energy & Cost | 1 | 3 | E1 |
| **Planning** | 0 | 5 | — deferred whole |
| **Inventory** | 0 | 4 | — deferred whole |
| **Alerts** | 0 | 6 | — deferred whole |
| **Total** | **93** | **53** | of 146 registered |

**88 of the 93 are `P0`.** Almost nothing in the cut is optional; the 5 that are not are there because the loop reads badly without them, not because they are nice to have. Deferred work splits 45 to Phase 2 and 8 to Phase 3.

**2 domains are in whole** — Case Resolution, Evaluation — and **3 are out whole** — Planning, Inventory, Alerts. That is the shape of the decision, not an accident of counting. A demonstrator has to close the loop *completely* and does not have to be *broad*, so the middle of the loop is taken entire while domains that are genuinely valuable, but not on it, are taken not at all.

<!-- END GENERATED -->

### The cut has grown four times, and each time for the same reason

| Cut | When | What was found |
|---|---|---|
| 51 of 101 | the first proposal | — |
| 69 of 122 | after reviewing the Thermynx flows | The loop went from a named fault straight to a work order. That hop does not exist: somebody answers questions first, and some answers come back "could not check" (D-002) |
| 79 of 132 | after the FDD discovery pass | Four gaps that had each already produced a real incident there — `C23`, `RC9`, `RC10`, `S6` (D-004) |
| 90 of 143 | after the sequencing brainstorm | 22 detected episodes, including the only two `critical`, never reached the queue — `RC17` (D-007) |
| 93 of 146 | after reading our own data | Evidence sitting unread in the row the model had just read, two severity scales disagreeing, and a signal the simulation invented — `RC18`, `F17`, `C26` (D-008, D-009) |

Every increase came from finding a defect in a system that had already been built and
run, never from imagining a feature. That is the useful pattern, and it is also the
reason to believe the growth has stopped: the last four additions were **rules** —
each a paragraph of behaviour attached to a component already in the cut — rather than
new subsystems. Running out of subsystems and finding only rules is what the end of a
gap hunt looks like.

**This is what question `S1` asks.** Not "is 93 the right number", but "are we done
adding?" Agreeing the cut is the decision to stop looking and start sequencing, and it
is what unblocks `mvp/BACKLOG.md` — one entry per feature with its dependencies, the
data it needs, and the open questions that block it. Until then there is a
specification and no build plan.

## What is out, and why

| Deferred | Reason |
|---|---|
| Planning and inventory (PL1–PL5, I1–I4) | Needs CMMS and stores integration depth that does not change whether the loop works |
| Alerts (L1–L6) | Valuable, but the MVP has few enough assets that alert noise is not yet the problem |
| Customer portal (R9, U1) | Multi-tenant surface area is a large security burden for little MVP learning |
| Executive briefing (C14, U2, R6) | Needs a history of outcomes to summarise; there will not be one yet |
| Watches (C13) | Depends on alerting |
| Report authoring and distribution (R2, R4, R7, R8) | `R1` already answers a question and `R5` already drills to source. Building reports, comparing scopes and scheduling delivery are reporting-product work, not proof that the loop closes |
| Work order logistics (W5–W7, W11, W12) | Scheduling, assignment, parts and SLA routing all need CMMS and stores depth. `RC16` already puts a named person on the job deterministically, which is what the loop requires |
| Asset analytics (A2–A5) | Health scores, dependencies, like-for-like comparison and repeat-failure detection need a history of closed cases. There will not be one until the MVP has run |
| Knowledge beyond the SOP (K2, K3, K4, K6) | Manuals, work order history and verified cases are all corpora we do not yet have indexed. `K1` and `K5` prove retrieval with the source shown, which is the mechanism being demonstrated |
| Cooling tower (F13) | Blocked on S2, and the tower changes condenser water behaviour in ways that complicate early model validation |
| Re-baselining (F12) | Not needed until the first verified major repair completes |
| Break-glass, policy simulation (G7, G8) | Governance maturity, not product proof |
| Energy cost, forecasting, optimisation advice (E2–E4) | The analytics exist on the platform already; the MVP needs the baseline `E1`, not the advice layer |
| Business outcome check (V5) | Needs a measured energy or downtime improvement to appear, which takes longer than the MVP runs. `V1`–`V4` prove the repair worked; `V5` proves it was worth doing |
| Planner queue and permission explanation (U4, U5) | Both are surfaces for personas the MVP does not include |
| Permit, qualification, EHS routing (S2, S3, S5) | All three are `P0` and none is deferred on value — they need a permit system, a qualification record and an escalation matrix that are the customer's, not ours. `S1` still blocks the unsafe action; what is deferred is the paperwork around it |
| Learning from closed cases (F9, V7) | Deliberately withheld: without a retraction mechanism one wrong confirmed root cause becomes permanent precedent. See `CONTEXT.md` §10 |
| Multi-skill orchestration | `C10` carries a job across steps without a planner running skills in parallel |

Every one of the 146 registered features appears in exactly one of the two tables
above. `scripts/verify.py` checks that against `mvp/FEATURE-REGISTER.md` and fails
if a feature is in neither or in both.

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
