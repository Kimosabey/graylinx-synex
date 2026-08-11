# 3. The Synex Copilot — The Kingpin of Graylinx

Reports and Work Orders are what the business needs. The Copilot is how people reach them. It is the front door to the whole Graylinx platform: one place where any person — executive, engineer, planner, technician or customer — can ask a question in their own words and get an answer that is scoped to them, backed by real data, and connected to the action that follows.

This section defines the Copilot completely: what it is, how one request travels through it, what it is allowed to touch, what it must say when it does not know, and how we will judge whether it is good. Everything that follows in this document — Reports, Work Orders, Asset intelligence, Reliability, Knowledge, Planning, Inventory, Alerts — is a capability the Copilot can reach.

| **PRODUCT PRINCIPLE** **The Copilot is not a feature of the platform. The Copilot is how the platform is used. Every other capability in this document is a skill the Copilot can call, through the Control Plane, with evidence and an audit trail.** |
|---|

## 3.1 What the Copilot is — and what it is not

| **The Copilot IS** | **The Copilot IS NOT** |
|---|---|
| The single entry point to Reports, Work Orders, Assets, Reliability, Knowledge, Planning, Inventory and Alerts. | A chat box added beside the existing screens that answers general questions. |
| A reasoning and explanation layer on top of the ML and FDD that Graylinx already has. | A replacement for the existing ML and FDD models. |
| An actor that can prepare and execute approved actions through typed tools. | A system that acts on its own authority or holds its own permissions. |
| Honest: it says NO_DIAGNOSIS when the evidence is not good enough. | A system that always produces a confident answer. |
| Traceable: every material answer carries its sources, timestamps and model versions. | A black box whose answers cannot be checked afterwards. |
| Scope-aware: it only ever sees what the person in front of it is allowed to see. | A shared brain that can quietly read across customers or sites. |
| Continuous: it follows a job from question to work order to verified result. | A one-shot question-and-answer tool that forgets the task. |

## 3.2 The fourteen operating modes

A user never chooses a mode. The Copilot works out what kind of request it is receiving and behaves accordingly. Each mode has a different control level, because reading data and changing data are not the same act.

| **Mode** | **The user says** | **What the Copilot does** | **Writes?** | **Control level** |
|---|---|---|---|---|
| ASK | “What is the health of Chiller-03?” | Retrieves and states a fact with its source and timestamp. | No | Scope + permission |
| EXPLAIN | “Why is this unhealthy?” | Builds an evidence pack and gives the likely cause in plain English. | No | Evidence + grounding |
| INVESTIGATE | “What is really going on here?” | Runs a multi-step enquiry across FDD, trends, history and knowledge. | No | Evidence + gates |
| COMPARE | “Chiller-03 versus Chiller-04 this month.” | Aligns two scopes or periods on the same definitions and shows the difference. | No | Scope + metric definitions |
| SEARCH | “What does the manual say about approach temperature?” | Retrieves from SOPs, manuals, WO history and verified cases with sources. | No | Tenant + source scope |
| RECOMMEND | “What should we do about it?” | Proposes ranked next actions with the reason and the confidence for each. | No | Evidence + uncertainty |
| REPORT | “Give me this week’s reliability summary.” | Generates a role-appropriate report with KPI lineage. | Artifact | Scope + lineage |
| DRAFT | “Create a work order for this.” | Prepares a complete, validated WO draft and shows it before anything is saved. | No | Permission + validation |
| APPROVE | “Approve this critical work order.” | Presents the request to the human who holds the authority. It never approves itself. | No | Named human only |
| EXECUTE | “Yes, create it.” | Calls the write tool through the gateway with an idempotency key. | Yes | Policy + tool gateway |
| VERIFY | “Did the repair work?” | Compares post-work evidence against the fault signature and returns PASS / FAIL / UNKNOWN. | Result only | Evidence required |
| ESCALATE | “This is not safe.” | Routes to EHS, reliability or the supervisor per the escalation rule. | Yes | Policy + routing |
| MONITOR | “Tell me if this gets worse.” | Registers a watch on a condition and notifies when the rule fires. | Config | Owner + quota |
| SUMMARIZE | “Brief me on this week.” | Condenses many records into a short briefing with drill-down links. | No | Scope |

## 3.3 Anatomy of one Copilot turn

Every single request — from “what is the temperature” to “close this critical work order” — travels through the same fourteen stages. Stages are never skipped. If a stage cannot complete, the Copilot degrades to a weaker answer state (3.8); it does not proceed as if the stage had passed.

| **#** | **Stage** | **What happens** | **Owned by** | **Budget** |
|---|---|---|---|---|
| 1 | Capture | Message, current screen, selected object and active filter are captured. | Copilot API | 50 ms |
| 2 | Identify | User, role, tenant and approval authority are resolved from the session. | Identity service | 50 ms |
| 3 | Scope | The allowed customer, site, system, asset and data scope is computed. | Control Plane | 100 ms |
| 4 | Resolve context | “this”, “it”, “the same one” are bound to real object IDs. | Router (phi4) | 300 ms |
| 5 | Classify intent | Mode and target skill are chosen; ambiguous requests trigger one question. | Router (phi4) | 300 ms |
| 6 | Pre-authorize | Is this class of request allowed for this person at all? | Control Plane | 100 ms |
| 7 | Plan | Decide which tools to call, in what order, and what evidence is needed. | Brain (gemma4) | 1–3 s |
| 8 | Retrieve | Read-only tools and retrieval run in parallel; results are typed. | Executor (devstral) | 0.5–3 s |
| 9 | Gate data quality | Freshness, operating state, sensor validity and persistence are checked. | Data-quality service | 200 ms |
| 10 | Reason | Evidence pack is assembled and the answer is formed. | Brain (gemma4) | 2–6 s |
| 11 | Ground and audit | Every claim is checked against the evidence pack; unsupported claims are cut. | Auditor (phi4) | 0.5–2 s |
| 12 | Decide action | For any write: ALLOW / ALLOW-WITH-APPROVAL / READ-ONLY / ESCALATE / DENY. | Control Plane | 200 ms |
| 13 | Execute | Write tool is called with a schema-valid payload and an idempotency key. | Tool gateway | 0.2–2 s |
| 14 | Respond and record | Answer, evidence and the full decision trail are returned and stored. | Copilot API + Audit | 200 ms |

Service targets: a read-only answer should complete within 8 seconds at p95, and a first token should appear within 2 seconds. An action turn — one that writes — should complete within 12 seconds at p95, excluding the time a human takes to approve.

| **SEPARATION RULE** **Stages 3, 6, 11 and 12 are outside the language models. The model may decide what it wants to do; it can never decide whether it is allowed to do it.** |
|---|

## 3.4 Context — how the Copilot understands “this”

The single biggest difference between a chatbot and a copilot is context. If a user is already looking at Customer → Plant A → Chiller System → Chiller-03 and asks “why is this bad?”, the Copilot must answer about Chiller-03 without being told.

| **Context slot** | **Where it comes from** | **Example** | **If missing** |
|---|---|---|---|
| WHO | Session identity | Ravi K., Reliability Engineer | Refuse — no anonymous turns |
| AUTHORITY | Role and approval matrix | May draft WOs; may not close critical WOs | Treat as read-only |
| TENANT | Account binding | Customer: Southern Mills Pvt Ltd | Refuse — never guess a tenant |
| SITE / PLANT | Screen or last explicit mention | Plant A, Madurai | Ask one question |
| SYSTEM | Asset hierarchy | Chilled water system | Infer from equipment |
| EQUIPMENT | Selected object | Chiller-03 | Ask one question |
| COMPONENT | Drill-down or fault subject | Condenser bundle | Optional |
| SCREEN | Client context payload | Asset health dashboard | Fall back to conversation |
| ACTIVE FILTER | Client context payload | Last 30 days, weekdays only | Use platform default and say so |
| ACTIVE OBJECT | Client context payload | Fault F-8842 / WO-2291 / Report R-114 | Fall back to conversation |
| CONVERSATION | Thread state | Two turns ago the user asked about Chiller-03 | Ask one question |
| TIME WINDOW | Request or default | This month; current shift | Use platform default and say so |
| PERMISSIONS | Control Plane decision | Read Plant A; no access to Plant C | Refuse the out-of-scope part |

### Reference resolution rules

- **Explicit beats implicit —** An object the user names explicitly always wins over the object on screen.
- **Most recent wins —** the most recent explicitly mentioned object of the right type is used.
- **Ambiguity is a question, not a guess —** if two objects of the same type are equally plausible, ask one short question. Do not guess.
- **Scope is a hard wall —** a reference is never resolved to an object outside the user’s scope. If the referenced object exists but is out of scope, the Copilot says so plainly rather than pretending it does not exist — unless the existence itself is confidential, in which case it reports no access.
- **Resolution is visible —** when the Copilot resolves a reference, the resolved object is shown in the answer header, so the user can see what it understood.

## 3.5 Intent routing

The router turns a sentence into a mode plus a skill. This is a small, fast, cheap decision made by phi4, and it is measured: routing accuracy is a release gate (3.15). Low-confidence routing does not guess; it asks.

| **Intent** | **Example utterance** | **Primary skill** | **Typical tools** | **Writes?** |
|---|---|---|---|---|
| asset_status | “How is Chiller-03 doing?” | Asset intelligence | get_asset, get_health | No |
| fault_explain | “Why did FDD raise this?” | Reliability | get_faults, explain_fault, get_residuals | No |
| root_cause | “What is actually causing the high power?” | Reliability | get_residuals, get_trends, find_similar_cases | No |
| trend_compare | “Is this worse than last month?” | Asset / Reports | get_trends, compare_assets | No |
| report_request | “Weekly maintenance summary for Plant A.” | Reports | create_report, get_report | Artifact |
| report_explain | “Why did availability drop?” | Reports | get_report, get_faults, get_wo | No |
| knowledge_lookup | “What is the inspection procedure?” | Knowledge | search_sop, search_manual | No |
| history_lookup | “How was this fixed last time?” | Knowledge | search_history, search_verified_cases | No |
| wo_create | “Raise a work order for this.” | Work orders | create_wo (after draft) | Yes |
| wo_manage | “Assign it to the day shift.” | Work orders | assign_wo, schedule_wo, update_wo | Yes |
| wo_close | “Close WO-2291.” | Work orders + Verification | verify_fault, close_wo | Yes |
| verify_outcome | “Did the repair work?” | Verification | get_residuals, get_wo, verify_fault | Result |
| planning | “What can we schedule tomorrow?” | Planning | find_window, find_technicians, check_availability | No |
| parts | “Do we have the gasket set?” | Inventory | check_part, check_delivery | No |
| alert_triage | “Why did I get 40 alerts?” | Alerts | get_faults, group and rank | No |
| safety_check | “Can I isolate this now?” | Safety | search_sop, policy check | No |
| admin_query | “Why can’t this user see the report?” | Platform | audit, permissions read | No |
| out_of_scope | “Write my performance review.” | — | None | No |

## 3.6 The Copilot tool belt

The Copilot does not reach the database, the CMMS or the historian directly. It reaches typed tools, and every tool call passes through the Tool Gateway, which validates the schema, applies scope, attaches short-lived credentials and writes the audit record. The columns below are the contract each tool must publish.

Class R = read only. Class W = writes to a system of record. Class A = produces an artifact (a report file, an export) but does not change operational state. Class C = changes configuration.

### Report tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| get_report | Returns an existing report within the user’s scope. | R | Low | None | n/a |
| create_report | Builds a report from a natural-language or structured spec. | A | Low | None | By spec hash |
| compare_reports | Aligns two reports on identical metric definitions. | R | Low | None | n/a |
| export_report | Exports to file or sends outside the platform. | A | Medium | Role-based | By export ID |
| schedule_report | Creates or edits a recurring delivery. | C | Medium | Owner | By schedule key |

### Asset tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| get_asset | Identity, make and model, criticality, ownership, hierarchy position. | R | Low | None | n/a |
| get_health | Current health score, status and contributing factors. | R | Low | None | n/a |
| get_history | Events, faults, work orders and readings for a period. | R | Low | None | n/a |
| get_dependencies | Upstream and downstream assets and served load. | R | Low | None | n/a |
| compare_assets | Side-by-side comparison of like assets on like conditions. | R | Low | None | n/a |

### FDD and ML tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| get_faults | Open and historical fault records with class, state and confidence. | R | Low | None | n/a |
| explain_fault | Returns the rule path and signals that produced a fault class. | R | Low | None | n/a |
| get_residuals | Model residuals per signal with the operating gates that applied. | R | Low | None | n/a |
| get_trends | Trend, volatility and rate of change over a window. | R | Low | None | n/a |
| find_similar_cases | Verified historical cases with a similar fault signature. | R | Low | None | n/a |
| verify_fault | Records a post-work verification outcome against the fault. | W | Medium | Supervisor if critical | By WO + fault |

### Work order tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| create_wo | Creates a work order from a validated draft. | W | Medium | Per policy and criticality | Client key |
| get_wo | Returns a work order and its full history. | R | Low | None | n/a |
| update_wo | Edits permitted fields on an open work order. | W | Medium | Owner or supervisor | By version |
| assign_wo | Assigns to a technician or crew. | W | Medium | Planner or supervisor | By assignment |
| prioritize_wo | Sets or changes priority using risk, criticality and SLA. | W | Medium | Supervisor if raised to P1 | By version |
| schedule_wo | Places the work in a maintenance window. | W | Medium | Planner | By window |
| add_finding | Records technician findings, readings and photographs. | W | Low | None | By finding ID |
| close_wo | Closes a work order. | W | High | Supervisor for critical; verification PASS required | By WO state |
| reopen_wo | Reopens after a failed or unproven repair. | W | Medium | Supervisor | By WO state |

### Knowledge tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| search_sop | Retrieves approved standard operating procedures. | R | Low | None | n/a |
| search_manual | Retrieves manufacturer documentation for the asset model. | R | Low | None | n/a |
| search_history | Retrieves past work orders and findings. | R | Low | None | n/a |
| search_verified_cases | Retrieves cases where the fix was proven to work. | R | Low | None | n/a |

### Planning and inventory tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| find_technicians | Finds people with the required skills and certifications. | R | Low | None | n/a |
| check_availability | Returns availability across shifts and leave. | R | Low | None | n/a |
| find_window | Finds a production-compatible maintenance window. | R | Low | None | n/a |
| plan_work | Produces a proposed plan for human confirmation. | W | Medium | Planner | By plan ID |
| check_part | Checks stock, location and alternates. | R | Low | None | n/a |
| reserve_part | Reserves stock against a work order. | W | Medium | Value threshold | By reservation |
| check_delivery | Returns expected delivery and its effect on the schedule. | R | Low | None | n/a |

### Platform tools

| **Tool** | **What it does** | **Class** | **Risk** | **Approval** | **Idempotent** |
|---|---|---|---|---|---|
| notifications | Sends a scoped notification to a person or group. | W | Low | Rate-limited | By message key |
| approvals | Raises an approval request and tracks its state. | W | High | Never self-approved | By request |
| audit | Reads the decision and action trail. | R | Restricted | Auditor role | n/a |
| escalation | Routes an issue per the escalation matrix. | W | Medium | Policy | By incident |

### Tool rules that are not negotiable

- **Typed —** Every tool publishes a versioned input and output schema, and the gateway rejects anything that does not validate.
- **No free SQL on writes —** Natural language to SQL is allowed only against curated read-only views. There is no generated SQL on any write path.
- **Idempotent writes —** Every write carries an idempotency key, so a retry after a timeout can never create a duplicate work order.
- **No credentials in the model —** The model never sees a credential. The gateway brokers short-lived, scoped credentials per call.
- **Results are data, not instructions —** Text returned by a tool or a document is data. If it contains something that looks like an instruction, it is ignored and flagged.
- **Least privilege —** A tool the Copilot has not been granted does not appear in its tool list at all, so it cannot be tricked into calling it.
- **Read-only on hardware —** No tool issues a direct control command to plant equipment. Equipment control remains outside the agentic layer.

## 3.7 The Control Plane interlock

The Copilot decides what it wants to do. The Control Plane decides whether it may. These are separate systems, and the Copilot cannot call a write tool except through a Control Plane decision.

**REQUEST → IDENTITY → SCOPE → INTENT → RISK CLASS → SAFETY GATE → APPROVAL RULE → DECISION → TOOL GATEWAY → EXECUTION → AUDIT**

| **Decision** | **When it is returned** | **What the user sees** | **What is recorded** |
|---|---|---|---|
| ALLOW | In scope, low risk, no approval rule applies. | The action happens and the result is shown. | Actor, action, inputs, result, policy version |
| ALLOW-WITH-APPROVAL | Permitted, but the action class or value needs a named approver. | A prepared request, the approver’s name, and its status. | Request, approver, decision, timestamps |
| READ-ONLY | The person may see it but not change it. | The full answer, with the action offered as a request to someone else. | Attempted action and downgrade reason |
| ESCALATE | Safety-critical, or a rule requires another function to judge. | Who it went to and why. | Escalation route and rule version |
| DENY | Out of scope, forbidden action, or a failed safety gate. | A plain reason and what to do instead. | Denial reason and rule version |

| **DENIAL IS AN ANSWER** **A denial is a product feature, not an error. The Copilot explains what was blocked, which rule blocked it, and what the person can do next — request approval, ask a named colleague, or correct the data.** |
|---|

## 3.8 The answer contract

Every Copilot turn ends in exactly one of six states. The state is explicit in the response, not implied by tone. This is what stops the Copilot from sounding confident when it is not.

| **State** | **When it is used** | **What the user gets** |
|---|---|---|
| ANSWERED | Evidence is sufficient and grounded. | The answer, the confidence word, the evidence, and the offered next action. |
| PARTIAL | Part of the question is answerable; part is out of scope or unavailable. | What is known, plainly marked, plus exactly what is missing and why. |
| NO_DIAGNOSIS | Operating gates failed, data is stale or invalid, or signals conflict. | A statement that no diagnosis can be made, which check failed, and a data-quality action. |
| NEEDS_APPROVAL | The action is permitted but requires a named human. | The prepared action, the approver, and the request status. |
| BLOCKED | Scope, permission or safety rule prevents the request. | The reason, the rule, and the correct route. |
| FAILED | A tool or dependency failed after retries. | What failed, what was and was not done, and the safe next step. |

### Confidence language

The Copilot uses four words and only four, so that the same word always means the same thing across the platform:

| **Word** | **Meaning** | **Requirement** |
|---|---|---|
| Confirmed | Directly measured or recorded. | A source record with a timestamp. |
| Likely | One fault class fits the evidence and the alternatives do not. | All gates passed; competing classes ruled out. |
| Possible | Evidence fits more than one explanation. | Alternatives must be listed, not hidden. |
| Not enough evidence | Gates failed or required signals are missing. | Must state which signal or gate is the problem. |

### When the Copilot must refuse to diagnose

- The equipment is not in a valid operating state — starting, stopping, below minimum load, or in a setpoint change.
- A required model input is missing or invalid, so the model’s residual cannot be trusted.
- The pattern has not persisted long enough to be a fault rather than a transient.
- Two independent signals contradict each other and no rule separates them.
- The most recent data is older than the freshness threshold for that decision.
**In all five cases the correct output is NO_DIAGNOSIS plus a data-quality or instrumentation action — never a softened guess.**

## 3.9 Memory and state

| **Memory** | **What it holds** | **Lifetime** | **Notes** |
|---|---|---|---|
| Turn context | Screen, selected object, filter, resolved references. | One turn | Rebuilt every turn from the client payload. |
| Conversation thread | Previous questions, resolved objects, offered actions. | Session, then archived | Scope re-checked every turn — it is never inherited. |
| Task state | A multi-step job: investigate → draft → approve → execute → verify. | Until closed or expired | Durable, resumable, survives a dropped session. |
| Watches | Conditions the user asked to be told about. | Until cancelled | Owned by a person, counted against a quota. |
| User preferences | Units, default period, report format, language. | Persistent | Preferences never widen scope. |
| Verified-case memory | Fault signature → fix → proven outcome. | Persistent | Tenant-isolated. Feeds find_similar_cases. |

### Never remembered

- Credentials, tokens or connection strings of any kind.
- Any data belonging to another tenant, in any form, including aggregates and counts.
- A previous approval, as authority for a later action. Every action is authorized on its own.
- A previously granted scope. Scope is recomputed on every turn from the live permission set.

## 3.10 Model routing across the four local models

Graylinx runs four models locally. They are not interchangeable, and the Copilot routes each stage of a turn to the model suited to it. Nothing in this document requires a fifth model.

| **Model** | **Size** | **Environment** | **Used at stages** | **Why this model** |
|---|---|---|---|---|
| gemma4:26b-a4b-it-qat | ~16 GB | OLLAMA_MODEL_BRAIN | 7 Plan, 10 Reason | Strongest reasoning; writes the explanation the user reads. |
| devstral:latest | ~14 GB | OLLAMA_MODEL_TOOL | 8 Retrieve | Reliable structured tool calling, ReAct loop and read-only NL→SQL. |
| phi4 | 9.1 GB | OLLAMA_MODEL_TEXT / _AUDITOR / _RAG / _DEFAULT | 4 Resolve, 5 Classify, 11 Ground, narration | Fast and cheap for short decisions; independent of the brain for auditing. |
| nomic-embed-text | 274 MB | — | Retrieval indexing and query | 768-dimension local embeddings; content never leaves the site. |

### Routing rules

- **Separation of duties —** The brain reasons and explains but never calls a tool directly; the executor calls tools but never writes the final answer to the user.
- **Auditor independence —** The model that grounds and audits an answer is not the model that produced it. Shared weights produce correlated blind spots, so the auditor must be phi4 whenever the brain wrote the answer.
- **Cheap decisions stay cheap —** Routing and reference resolution use the small model. If routing confidence is low, the Copilot asks the user rather than escalating to a larger model and guessing.
- **Embeddings stay local —** Embeddings are always computed locally and never sent to a remote service.
- **Degraded mode is declared —** If the brain is unavailable, the Copilot serves ASK, SEARCH and REPORT in a degraded mode and refuses EXPLAIN, INVESTIGATE and RECOMMEND, saying so. It does not silently substitute a weaker model for reasoning.

## 3.11 Worked example — investigate a chiller fault

This example uses the real water-cooled chiller FDD engine: six residuals from normal-operation models, with operating gates applied before any rule is allowed to fire. A residual is the difference between what a signal actually reads and what the normal-operation model predicted it should read.

*Context: Ravi K., Reliability Engineer, is on the Chiller-03 asset page for Plant A. He types: “Why is this unhealthy?”*

### Stage 1–6 — who, what and whether

Identity resolves to Ravi K., Reliability Engineer, tenant Southern Mills, scope Plant A and Plant B. “this” resolves from the screen to Chiller-03, and the resolved object is shown in the answer header. Intent classifies as fault_explain, mode EXPLAIN. Pre-authorization returns ALLOW — this is a read.

### Stage 8–9 — evidence and gates

The executor calls get_faults, get_residuals, get_trends, get_history and find_similar_cases in parallel. Before any rule runs, the operating gates are checked.

| **Gate** | **Requirement** | **Reading** | **Result** |
|---|---|---|---|
| Running steady | No start or stop transient | Steady 4 h 20 min | PASS |
| Load above minimum | Above the model’s valid load floor | 68% load | PASS |
| Flows valid | Evaporator and condenser flow signals healthy | Both valid | PASS |
| No setpoint change | No leaving-water setpoint move in the window | None | PASS |
| Persistence | Pattern held 20–30 min or more | Held 42 min | PASS |

| **Signal** | **Residual** | **Reading** | **What it means** |
|---|---|---|---|
| Chiller power | rPwr | High | The chiller is using more power than the model expects for these conditions. |
| Discharge pressure | rDP | High | Head pressure is higher than expected. |
| Condenser water leaving | rCWL | High | Heat is not being rejected into the condenser water properly. |
| Suction pressure | rSP | Normal | The evaporator side is not starved. |
| Compressor amps | rAmp | Normal | The compressor is not drawing abnormal current for these pressures. |
| Discharge temperature | rDT | Slightly high | Support signal only — not used to separate the causes. |

### Stage 10 — reasoning down the isolation path

**rPwr high → rDP high → rCWL high → condenser water-side problem → steady and worsening over weeks → condenser fouling**

The rule path is deterministic and comes from the FDD engine, not from the model. Power is high, so an efficiency fault exists. Discharge pressure is high, so the extra power is being driven by high head. Condenser water leaving is also high, which places the problem on the condenser water side rather than the refrigerant side. The remaining question is which condenser water-side cause: low flow presents as spikes and intermittent behaviour, while fouling presents as a steady drift getting worse over weeks. get_trends shows a steady 3-week drift with no spikes, so the class is condenser fouling. The model’s job here is to explain the path in plain English, not to invent it.

### Stage 11–14 — the grounded answer

**Chiller-03 — likely condenser fouling.**

Confidence: Likely. All operating gates passed and the pattern has held for 42 minutes.

- Chiller-03 is using about 9% more power than normal for its current load and water temperatures.
- Head pressure is running high, and the condenser water leaving temperature is also high — so heat is not moving into the condenser water as it should.
- The suction side and the compressor look normal, which rules out a starved evaporator and compressor inefficiency.
- The pattern has drifted steadily worse over three weeks with no spikes, which points to fouling rather than low condenser flow.
- A similar case on Chiller-01 in February was closed by condenser tube cleaning, and power returned to baseline within two days (WO-1877, verified).
**Recommended next action: inspect and clean the condenser tubes at the next available window; check the tower water treatment log for the same period.**

Offered: create a work order — Prepare draft.

### The same question when the data is not good enough

If the condenser flow signal is invalid or missing, the models that depend on it — discharge pressure, power and condenser water leaving — cannot produce trustworthy residuals. The flows-valid gate fails, and the Copilot must not fall back to a softer version of the same conclusion. It returns:

| **WHAT THE USER SEES** **NO_DIAGNOSIS — I cannot diagnose Chiller-03 right now. Three of the six models need a valid condenser flow signal, and that signal is not reporting. Power is elevated, but I cannot tell you why without it. Recommended action: raise a data-quality work order for the condenser flow measurement.** |
|---|

This is the behaviour that makes the rest of the platform trustworthy. A Copilot that guesses when its inputs are missing will eventually send a crew to the wrong equipment, and after that nobody believes the good diagnoses either.

## 3.12 Worked example — act, then prove it worked

### “Create a work order for this.”

| **Step** | **What the Copilot does** | **Control** |
|---|---|---|
| 1 | Carries the resolved asset, fault and evidence pack forward — the user does not re-explain. | Task state |
| 2 | Drafts the WO: asset, fault class, symptom, evidence, recommended work, parts, skills, safety notes. | Validation |
| 3 | Calculates priority from asset criticality, risk, SLA and production impact — and shows the calculation. | Deterministic rule |
| 4 | Checks whether Ravi may create this class of WO on Plant A. | Control Plane |
| 5 | Checks parts: condenser cleaning kit in stock at Plant A stores. | check_part |
| 6 | Shows the complete draft. Nothing has been written yet. | DRAFT mode |
| 7 | On confirmation, calls create_wo with an idempotency key. | Tool gateway |
| 8 | Confirms WO-2291 created, assigned to the mechanical crew, scheduled for Sunday shutdown. | Audit written |
| 9 | Registers a verification task against fault F-8842, due after the work completes. | Task state |

Had this been a safety-critical isolation instead of a cleaning task, step 4 would have returned ALLOW-WITH-APPROVAL, and the Copilot would have shown a prepared request with the named approver rather than a created work order.

### “Did the repair work?”

Six days later the crew has closed out the physical work. The Copilot does not accept “complete” as proof of “fixed”.

| **Verification input** | **What is checked** | **Result** |
|---|---|---|
| Work record | Was the intended work actually performed, with findings recorded? | Tubes cleaned; heavy scale reported |
| Post-work residuals | Have rPwr, rDP and rCWL returned inside the normal band? | All three within band |
| Operating gates | Was the equipment in a valid state when the comparison was made? | PASS |
| Persistence | Has the improvement held across a representative load range? | Held 3 days, 40–85% load |
| Fault state | Has the FDD fault cleared under valid conditions? | F-8842 CLEAR |
| Business outcome | Did the expected energy improvement appear? | About 8% power reduction at like load |

**Result: VERIFIED. The Copilot closes the verification task, permits WO-2291 to move to closed, and writes the case into verified-case memory so the next chiller showing the same signature can be matched against a fix that is known to have worked.**

If the residuals had not returned to band, the result would be FAIL: the work order reopens, the previous findings are preserved so the next technician does not start from zero, and the fault is re-examined with the new evidence included. If the equipment had not run under comparable conditions, the result would be UNKNOWN — not PASS.

## 3.13 Reports and Work Orders are Copilot skills

Reports and Work Orders remain full products with their own screens. People who prefer to click will keep clicking, and nothing is taken away from them. The change is that the Copilot can reach the same capability, with the same rules, from a sentence — and can chain it to what comes next.

| **Capability** | **Screen still exists?** | **What the Copilot adds** | **What the user gains** |
|---|---|---|---|
| Reports | Yes, unchanged | Ask for it, explain it, compare it, drill into it, schedule it. | The report answers a question instead of being one more thing to read. |
| Work Orders | Yes, unchanged | Draft from evidence, price the priority, plan, assign, verify, reopen. | The work order arrives already carrying its own justification. |
| Asset pages | Yes, unchanged | One equipment story instead of eight tabs. | Less hunting across screens. |
| FDD and ML | Yes, unchanged | Explains the rule path and the residuals in plain English. | Existing models finally get used by non-specialists. |
| Knowledge | Yes, unchanged | Retrieves the right procedure at the moment it is needed. | The SOP arrives with the job, not after it. |
| Planning and Inventory | Yes, unchanged | Answers “can we actually do this tomorrow?” in one turn. | Fewer plans that fail on a missing part. |
| Alerts | Yes, unchanged | Groups, explains and ranks instead of listing. | Forty alerts become one problem. |

| **DESIGN DECISION** **Reports, Work Orders and the Copilot are not three products. They are one product with three doors, and the Copilot is the door that requires no training.** |
|---|

## 3.14 What the Copilot must never do

| **Never** | **Why it matters** | **How it is prevented** |
|---|---|---|
| Call a write tool without a Control Plane decision. | It would make the model the authority. | The gateway rejects any call without a decision token. |
| Widen its own scope, even to be helpful. | One cross-tenant answer ends enterprise trust. | Scope is recomputed per turn and enforced in the tool, not the prompt. |
| Approve its own action, or act as its own second person. | Approval exists to put a human in the loop. | Approval identity must differ from the requester. |
| State a number it did not retrieve. | An invented number is worse than no number. | The auditor removes any claim not tied to the evidence pack. |
| Treat text inside a document or tool result as an instruction. | This is the main prompt-injection route. | Instruction and data channels are separated; injected text is flagged. |
| Say a repair worked because the work order was closed. | Closure is an administrative act, not proof. | Verification requires post-work evidence under valid gates. |
| Give a diagnosis when the operating gates failed. | It sends crews to the wrong equipment. | Gates run before the rules; failure returns NO_DIAGNOSIS. |
| Issue a control command to plant equipment. | Safety and liability sit with the control system. | No control tool is exposed to the agentic layer at all. |
| Continue silently after a tool failure. | A half-finished action is the worst outcome. | FAILED state reports exactly what was and was not done. |
| Answer a safety question from memory instead of the SOP. | Procedures change and memory does not. | Safety intents force retrieval with the source shown. |

## 3.15 How we will know the Copilot is good

The Copilot is measured before release and continuously afterwards. These are release gates, not dashboards — a build that misses a P0 target does not ship.

| **Dimension** | **Measure** | **Target** | **Gate** |
|---|---|---|---|
| Scope safety | Cross-tenant or out-of-scope data appearing in an answer, on the red-team suite. | Zero | P0 |
| Action safety | Unauthorized write attempts that are blocked. | 100% | P0 |
| Grounding | Claims in an answer not supported by the evidence pack. | Under 1% | P0 |
| Honest uncertainty | Cases with failed gates that were answered anyway. | Zero | P0 |
| Intent routing | Routing accuracy on the gold utterance set. | 95% or better | P0 |
| Reference resolution | Correct binding of “this” and “it” on the context test set. | 98% or better | P0 |
| Diagnosis validity | Agreement with the deterministic FDD rule path. | 100% — the model never overrides the rule | P0 |
| Injection resistance | Successful instruction injections through documents or tool results. | Zero | P0 |
| Latency | p95 for a read-only turn; first token. | 8 s; 2 s | P1 |
| Task success | Multi-step tasks completed without the user restarting. | 90% or better | P1 |
| Recommendation value | Recommendations accepted by engineers. | Tracked, rising | P1 |
| Verification quality | Verified repairs that later reopen for the same fault. | Falling | P1 |
| Audit completeness | Material actions with a complete decision trail. | 100% | P0 |

Every one of these is testable before a single customer sees the build. That is the difference between a copilot we can sell to an enterprise and a demo.
