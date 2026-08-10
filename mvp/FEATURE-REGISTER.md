# Feature register

The single source of truth for what Synex is. If a capability is not on this
list, it is not being built. Chapters reference these IDs; they do not restate
them.

**Engine:** `SW` plain deterministic software · `R` deterministic rule ·
`ML` equipment model · `LLM` language model / agentic layer.

**Phase:** `MVP` · `Phase 2` · `Phase 3`. The MVP column is a proposal until
question S1 is closed.

## C — Synex Copilot

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| C1 | Natural-language ask across the platform | One entry point to reports, assets, faults, work orders and documents. | Everyone | `SW + LLM` | P0 | MVP |
| C2 | Context resolution | Understands "this" and "it" from the screen and the conversation. | Everyone | `SW + LLM` | P0 | MVP |
| C3 | Intent routing | Chooses the right skill and tools for the request. | Everyone | `LLM` | P0 | MVP |
| C4 | Evidence pack assembly | Collects the readings, versions and records behind every answer. | Everyone | `SW` | P0 | MVP |
| C5 | Grounded fault explanation | Explains the FDD rule path in plain English, without inventing it. | Reliability | `LLM` | P0 | MVP |
| C6 | Ranked recommendation | Proposes next actions with reason, confidence and alternatives. | Maintenance | `R + LLM` | P0 | MVP |
| C7 | Honest uncertainty | Returns NO_DIAGNOSIS when gates fail or signals conflict. | Everyone | `R` | P0 | MVP |
| C8 | Draft before write | Shows the complete action before anything is saved. | Everyone | `SW` | P0 | MVP |
| C9 | Approval request routing | Prepares the request and names the approver; never self-approves. | Supervisor | `SW` | P0 | MVP |
| C10 | Multi-step task memory | Carries a job from investigation to work order to verification. | Everyone | `SW` | P0 | MVP |
| C11 | Role-scoped answers | Same assistant, different scope and depth per role. | Everyone | `SW` | P0 | MVP |
| C12 | Source-cited knowledge answers | Quotes the SOP or manual and shows where it came from. | Technician | `LLM` | P0 | MVP |
| C13 | Watches | Monitored condition with a notification when the rule fires. | Plant Manager | `R` | P1 | Phase 2 |
| C14 | Executive briefing | Condenses the week into a short business summary with drill-down. | Executive | `LLM` | P1 | Phase 2 |
| C15 | Conversation thread and turn memory | Per-session memory on **every** route, with every turn persisted. | Everyone | `SW` | P0 | MVP |
| C16 | Conversational fast path | Greetings and capability questions answered at once, with starter prompts, without touching telemetry. | Everyone | `SW + LLM` | P1 | MVP |
| C17 | Read-only data lookup in natural language | Exact numbers, counts and averages from the database. Read-only, always. | Analyst | `SW + LLM` | P0 | MVP |
| C18 | Route transparency | Names the skill that answered and why it was chosen. | Everyone | `SW` | P1 | MVP |
| C19 | Thread export with evidence | The conversation and the evidence behind it leave as one record. | All | `SW` | P1 | MVP |
| C20 | Skill registry | The named set of analysis skills, each with its tool scope and its control level. What `C3` routes to and `C18` reports. | Platform | `SW` | P0 | MVP |
| C21 | Figure discipline | Every number is either a value or a stated absence — never both, never neither. | Everyone | `SW` | P0 | MVP |
| C22 | Data window on every artefact | Every answer, report and export states the period it was computed over. | All | `SW` | P0 | MVP |
| C23 | Untrusted-window marking | A period can be marked untrusted, and reports, efficiency figures and models all honour it. | Data / Reliability | `SW` | P0 | MVP |
| C25 | Evidence-graded response mode | Four modes by how much the data can settle: explain a definitive verdict, hypothesise the right question when it is ambiguous, interrogate what can and cannot be proven, or interview when nothing is usable. | Everyone | `LLM + R` | P0 | MVP |
| C24 | Inline evidence rendering | Trends, comparisons and result tables drawn in the answer from the evidence pack — never decoration, and never a figure the pack does not contain. | Everyone | `SW` | P0 | MVP |

## R — Reports

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| R1 | Ask a question of a report | Conversational follow-up on any report. | All | `LLM` | P0 | MVP |
| R2 | Create report from natural language | Builds a report from a spoken or typed request. | Manager | `SW + LLM` | P0 | Phase 2 |
| R3 | Explain a KPI change | Traces a movement to the equipment, faults and work behind it. | Manager | `SW + LLM` | P0 | MVP |
| R4 | Compare sites, assets or periods | Aligns two scopes on identical metric definitions. | Regional Head | `SW` | P0 | Phase 2 |
| R5 | Drill down to source records | Every number opens to the records that produced it. | Analyst | `SW` | P0 | MVP |
| R6 | AI narrative | Writes the commentary over verified metrics only. | Executive | `LLM` | P1 | Phase 2 |
| R7 | Schedule and deliver | Recurring role-aware delivery. | Manager | `SW` | P1 | Phase 2 |
| R8 | Export with lineage | Export carries metric definitions and source references. | Analyst | `SW` | P1 | Phase 2 |
| R9 | Customer-scoped report | Customers see only their own sites and assets. | Customer | `SW` | P0 | Phase 2 |
| R10 | KPI reconciliation | Reported numbers are checked against the source calculation. | Finance | `SW` | P0 | MVP |

## W — Work Orders

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| W1 | Create work order from chat | From a sentence, with the evidence attached. | Maintenance | `SW + LLM` | P0 | MVP |
| W2 | Create work order from a fault | Direct from an FDD finding, pre-populated. | Reliability | `SW + R` | P0 | MVP |
| W3 | Evidence auto-attached | Residuals, gates, trends and similar cases travel with the job. | Technician | `SW` | P0 | MVP |
| W4 | Priority calculation | Deterministic formula over criticality, risk, SLA and production impact. | Planner | `R` | P0 | MVP |
| W5 | Maintenance window planning | Finds a production-compatible slot. | Planner | `SW` | P1 | Phase 2 |
| W6 | Technician assignment | Matches skills, certifications and availability. | Supervisor | `SW` | P1 | Phase 2 |
| W7 | Parts check and reservation | Stock, alternates, delivery impact. | Stores | `SW` | P1 | Phase 2 |
| W8 | Findings capture | Structured technician findings, readings and photographs. | Technician | `SW` | P0 | MVP |
| W9 | Verification gate before close | A work order cannot close unproven. | Supervisor | `R` | P0 | MVP |
| W10 | Reopen on failed repair | Previous findings preserved for the next technician. | Supervisor | `SW` | P0 | MVP |
| W11 | Closure summary | What was found, what was done, what it proved. | Manager | `LLM` | P1 | Phase 2 |
| W12 | SLA escalation | Routes when work approaches or breaches its SLA. | Manager | `R` | P1 | Phase 2 |

## A — Asset Intelligence

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| A1 | One equipment story | Health, status, faults, history, documents and risks in one view. | All | `SW + LLM` | P1 | MVP |
| A2 | Health score with reasons | The number plus the contributing factors. | Reliability | `R + ML` | P1 | Phase 2 |
| A3 | Dependency and served load | What this machine feeds and what feeds it. | Operations | `SW` | P1 | Phase 2 |
| A4 | Like-for-like comparison | Compares similar machines under similar conditions only. | Reliability | `SW` | P1 | Phase 2 |
| A5 | Repeat-failure detection | Surfaces the assets consuming disproportionate effort. | Reliability | `R` | P1 | Phase 2 |

## F — Reliability and FDD

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| F1 | Six normal-operation models per chiller | DP, SP, DT, Power, Compressor Amps, Condenser Leaving. | Reliability | `ML` | P0 | MVP |
| F2 | Residual computation | Actual minus predicted, with a validity flag per residual. | Reliability | `ML` | P0 | MVP |
| F3 | Operating gates | Running steady, load above floor, flows valid, no setpoint change. | Reliability | `R` | P0 | MVP |
| F4 | Persistence and volatility test | Separates a fault from a passing disturbance. | Reliability | `R` | P0 | MVP |
| F5 | Deterministic isolation path | Power to head to water side vs refrigerant side to a single class. | Reliability | `R` | P0 | MVP |
| F6 | Sensor bias detection | Rules out instrumentation before dispatching a crew. | Reliability | `R` | P0 | MVP |
| F7 | Honest ambiguity labels | High head ambiguous; undercharge and restriction kept combined. | Reliability | `R` | P0 | MVP |
| F8 | NO_DIAGNOSIS on failed gates | No softened guess when the inputs are not trustworthy. | Reliability | `R` | P0 | MVP |
| F9 | Similar verified case matching | Past cases with the same signature and a proven fix. | Maintenance | `SW` | P1 | Phase 2 |
| F10 | Model health and drift monitoring | Detects a model going quietly stale. | Data / Reliability | `R + ML` | P0 | MVP |
| F11 | Model quarantine | A failed model stops being used, not merely flagged. | Data / Reliability | `SW` | P0 | MVP |
| F12 | Re-baseline after verified major work | A repaired machine may have a legitimately new normal. | Reliability | `ML` | P1 | Phase 2 |
| F13 | Cooling tower assessment | Wet bulb, approach and tower running hours. | Reliability | `R + ML` | P1 | Phase 2 |
| F15 | Per-asset residual reference band | "High" and "Normal" are measured against that asset's own healthy distribution, never an absolute threshold. | Reliability | `R + ML` | P0 | MVP |
| F16 | Cross-signal physical plausibility | Rejects combinations that cannot physically occur — zero flow with a normal &Delta;T and normal power, or a condenser &Delta;T with the wrong sign. | Data / Reliability | `R` | P0 | MVP |
| F14 | Chilled-water delta-T health check | Flags sustained low delta-T against the design band. | Reliability | `R` | P0 | MVP |

## RC — Case Resolution

The lifecycle between a named fault and a closed work order. Detection ends where
this begins (`F5`) and execution starts where it ends (`W2`) — it is neither.
Every row here is constrained by an inherited decision; see `CONTEXT.md` §10.

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| RC1 | Fault-case state machine | detected → awaiting findings → escalated → deferred → root-caused → actioned → closed. | Reliability | `SW + R` | P0 | MVP |
| RC2 | Curated checklist library | Three kinds per fault class — RCA, corrective, preventive — human-written and reviewable. The language model selects and contextualises; it never authors a field instruction. | Reliability | `SW` | P0 | MVP |
| RC3 | Capability-routed checklist items | Five capabilities — operator, maintenance, technician, supervisor, vendor. **An operator is never blocked by a check they cannot perform.** Untagged defaults to technician, the safe direction. Escalation targets by workload, never by seniority. | Supervisor | `SW` | P0 | MVP |
| RC4 | Findings capture with an explicit cannot-check | "Could not check" is recorded separately from "not applicable", so an unanswered check can never open a gate. | Technician | `SW` | P0 | MVP |
| RC5 | Blocking-items gate | A case cannot advance while a blocking item is unanswered. | Supervisor | `R` | P0 | MVP |
| RC6 | Root cause with corrective and preventive actions | Recording the cause attaches both follow-up checklists. | Reliability | `SW + R` | P0 | MVP |
| RC7 | Three escalation routes | Sideways for the wrong skill, up for authority, defer for the wrong moment. Escalating up lands unassigned and says so. | Supervisor | `R` | P0 | MVP |
| RC8 | Idempotent case seeding | A rescan can never open a second case for the same episode. | Data / Reliability | `SW` | P0 | MVP |
| RC9 | Case ageing and auto-stale | A case whose condition has cleared marks itself stale; one nobody has touched ages visibly rather than sitting silently. | Supervisor | `R` | P0 | MVP |
| RC10 | Measured or estimated, per finding | Only a measured answer settles a blocking check. An estimate is recorded and does not open the gate. | Technician | `SW` | P0 | MVP |
| RC12 | Differential narrowing | Candidate causes per ambiguous class, narrowed by asking the single most discriminating question at a time rather than presenting a flat list. | Reliability | `R` | P0 | MVP |
| RC13 | Elimination audit | Every ruled-out cause records the check and the answer that ruled it out. "The software decided" is not an answer. | Reliability | `SW` | P0 | MVP |
| RC14 | Honestly exhausted, distinct from settled | A differential that runs out of questions says so, rather than concluding on whichever cause is left. | Reliability | `R` | P0 | MVP |
| RC15 | Escalation produces a work order | No tool raises an **inspection** work order with the open checks as its task list; no authority raises an **authorisation** work order whose task is the question, not a measurement. | Supervisor | `SW + R` | P0 | MVP |
| RC16 | Deterministic assignee | Matched by skill against the fault label, never chosen by a model — so it works with the GPU off and "why this person" is answerable without replaying a prompt. | Supervisor | `SW` | P0 | MVP |
| RC11 | Preventive actions become a scheduled obligation | A preventive item creates a recurring commitment with a named approver, rather than a line of text nobody owns. | Supervisor | `SW` | P0 | MVP |

## K — Knowledge

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| K1 | SOP search | Approved procedures, retrieved with the source shown. | Technician | `LLM` | P1 | MVP |
| K2 | Manufacturer manual search | What the OEM actually says about this model. | Technician | `LLM` | P1 | Phase 2 |
| K3 | Work order history search | How this was fixed last time. | Maintenance | `LLM` | P1 | Phase 2 |
| K4 | Verified case search | Only fixes that were proven to work. | Reliability | `LLM` | P1 | Phase 2 |
| K5 | Source-visible answers | Every important answer names its document and version. | All | `SW` | P0 | MVP |
| K6 | Explain a technical document simply | Turns dense OEM text into plain English. | Technician | `LLM` | P2 | Phase 3 |

## PL / I — Planning and Inventory

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| PL1 | Prioritised work queue | Ranked by risk, criticality, SLA and production impact. | Planner | `R` | P1 | Phase 2 |
| PL2 | Maintenance window finder | Slots that production can actually give. | Planner | `SW` | P1 | Phase 2 |
| PL3 | Certification-aware matching | Only people qualified for the task. | Supervisor | `SW` | P1 | Phase 2 |
| PL4 | Workload balance | Avoids overloading one crew. | Supervisor | `SW` | P2 | Phase 3 |
| PL5 | Plan feasibility answer | Can we actually do this tomorrow, in one turn. | Planner | `SW + LLM` | P1 | Phase 2 |
| I1 | Stock check | Availability and location. | Stores | `SW` | P1 | Phase 2 |
| I2 | Reservation against a work order | Parts held for the job. | Stores | `SW` | P1 | Phase 2 |
| I3 | Alternates | Acceptable substitutes when the primary part is out. | Stores | `SW` | P2 | Phase 3 |
| I4 | Delivery impact on schedule | What the lead time does to the plan. | Planner | `SW` | P2 | Phase 3 |

## E — Energy and Cost

Analytics that already run against the shared platform database. Registered so the
capability is named and traceable rather than assumed.

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| E1 | Efficiency baseline and kW/TR tracking | The per-asset baseline the FDD efficiency proxy is measured against. | Reliability | `SW + ML` | P0 | MVP |
| E2 | Energy cost attribution | Consumption and cost split by asset, site and period. | Manager | `SW` | P1 | Phase 2 |
| E3 | Load forecast | Expected load and consumption ahead of a window. | Planner | `ML` | P1 | Phase 2 |
| E4 | Setpoint and staging optimisation advice | Advice only. No tool issues a control command, in any phase. | Operations | `R + LLM` | P1 | Phase 2 |

## EV — Evaluation

The standing gates. An answer contract nothing measures is a wish, and an
evaluation suite that cannot fail is decoration.

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| EV1 | Golden regression suite | A fixed case set that must stay green before any change to model behaviour ships. | Platform | `SW` | P0 | MVP |
| EV2 | Answer-honesty gate | Scores answers on stated dimensions and fails the build below the bar. | Product | `SW + LLM` | P0 | MVP |
| EV3 | Hard dimensions exempt from tolerance | Some dimensions cannot be traded against an overall score — a report whose figures disagree with each other fails outright. | Product | `R` | P0 | MVP |
| EV4 | The evaluation's own tests | Deliberately dishonest inputs fed to the gate, so it cannot quietly start passing everything. | Platform | `SW` | P0 | MVP |

## L / V — Alerts and Verification

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| L1 | Duplicate grouping | Forty alerts become one problem. | Operations | `R` | P1 | Phase 2 |
| L2 | Alert explanation | Why this fired, in plain English. | Operations | `LLM` | P1 | Phase 2 |
| L3 | Prioritisation | Ranked, not listed. | Operations | `R` | P1 | Phase 2 |
| L4 | Routing | To the person who can act on it. | Operations | `SW` | P1 | Phase 2 |
| L5 | Escalation | When it is not picked up or crosses a threshold. | Manager | `R` | P1 | Phase 2 |
| L6 | Noise measurement | Alert volume tracked as a product metric. | Product | `SW` | P2 | Phase 3 |
| V1 | Post-work residual comparison | Are the residuals back inside the band? | Reliability | `R + ML` | P0 | MVP |
| V2 | Valid comparison window | Comparison only under comparable operating conditions. | Reliability | `R` | P0 | MVP |
| V3 | Persistence across load range | Improvement must hold, not appear once. | Reliability | `R` | P0 | MVP |
| V4 | Fault-clear check | Does the FDD fault clear under valid conditions? | Reliability | `R` | P0 | MVP |
| V5 | Business outcome check | Did the expected energy or downtime improvement appear? | Manager | `SW` | P1 | Phase 2 |
| V6 | PASS / FAIL / UNKNOWN | Three outcomes; UNKNOWN is real and common. | Supervisor | `R` | P0 | MVP |
| V7 | Verified-case memory | Signature, fix and proven outcome written back for reuse. | Reliability | `SW` | P1 | Phase 2 |

## U / S / G — Roles, Safety, Control Plane

| ID | Feature | What it does | Primary user | Engine | Pri | Phase |
|---|---|---|---|---|---|---|
| U1 | Customer view | Only their own sites, assets and reports. | Customer | `SW` | P0 | Phase 2 |
| U2 | Executive brief | The answer, not twenty screens. | Executive | `LLM` | P1 | Phase 2 |
| U3 | Technician job pack | Job context, safety, SOP, history, parts, findings. | Technician | `SW + LLM` | P0 | MVP |
| U4 | Planner queue view | What can be done, when, by whom. | Planner | `SW` | P1 | Phase 2 |
| U5 | Permission explanation | Why a user cannot see a report. | Administrator | `SW` | P2 | Phase 3 |
| U6 | Reliability engineer workspace | The fault queue, the residuals behind each one, and the case it opens. | Reliability | `SW + LLM` | P0 | MVP |
| U7 | Supervisor approval and closure queue | What is waiting on a named human: approvals, blocked cases, closures that verification has not cleared. | Supervisor | `SW` | P0 | MVP |
| U8 | Administrator scope and policy | Who may see and do what, the approval matrix, and the policy version every decision is stamped with. | Administrator | `SW` | P0 | MVP |
| S1 | Safety-critical action block | The AI stops; it does not weigh the risk itself. | EHS | `SW` | P0 | MVP |
| S2 | Permit and isolation gate | Permit, LOTO and isolation checks before work. | EHS | `SW` | P0 | Phase 2 |
| S3 | Qualification check | Only qualified people are proposed for restricted work. | Supervisor | `SW` | P0 | Phase 2 |
| S4 | Safety answers from the SOP | Never answered from model memory. | Technician | `LLM` | P0 | MVP |
| S5 | EHS escalation | Routed per the escalation matrix. | EHS | `R` | P0 | Phase 2 |
| S6 | Stop-the-machine response class | Some faults are answered by stopping the machine now, not by raising a work order. A response class that is not a work order. | EHS | `R` | P0 | MVP |
| G1 | Identity and scope per turn | Scope recomputed every turn, never inherited. | Platform | `SW` | P0 | MVP |
| G2 | Risk classification | Low / medium / high / safety-critical / system-critical. | Platform | `R` | P0 | MVP |
| G3 | Approval engine | Who must approve what, under which conditions. | Platform | `SW` | P0 | MVP |
| G4 | Tool gateway | Schema validation, credentials, safe retry, side-effect control. | Platform | `SW` | P0 | MVP |
| G5 | Idempotency | A retry can never create a second work order. | Platform | `SW` | P0 | MVP |
| G6 | Audit trail | Every material action and decision, permanently. | Audit | `SW` | P0 | MVP |
| G7 | Break-glass | Emergency elevation that is temporary, recorded and expiring. | Security | `SW` | P1 | Phase 3 |
| G8 | Policy versioning and simulation | Test a rule change before it goes live. | Governance | `SW` | P1 | Phase 3 |

---

**Totals:** 142 features, of which 89 are in the proposed MVP cut.

The cut grew from 51 to 65 after reviewing the flows in the existing Thermynx
implementation. Four groups of capability were in daily use there, or required for
the loop to close, and named nowhere in this register:

- the conversation shell — `C15`–`C19`, plus the skill registry `C20`
- the case resolution lifecycle — `RC1`–`RC8`
- energy and cost analytics — `E1`–`E4`
- the three personas the loop cannot close without — `U6`, `U7`, `U8`
- honesty discipline and the standing evaluation gates — `C21`, `C22`, `EV1`–`EV4`

A later pass over the Thermynx FDD knowledge base added four more, each closing a
gap that had already produced a real incident there: `C23`, `RC9`, `RC10`, `S6`.
See `CONTEXT.md` §10 constraints 20–22 and decision D-004.

Recorded as decision D-002.
