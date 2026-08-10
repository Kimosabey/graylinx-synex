# CONTEXT.md — What Graylinx Synex is

Everything in this file is settled product truth. If a source document
contradicts it, the source document is out of date — flag it, do not follow it.

---

## 1. Positioning

> **Graylinx Synex — Intelligent Operations, Connected by AI**

**Synex** = Sync + Nexus.

- **Sync** — connects data, people, equipment and workflows
- **Nexus** — the central connection point
- **Synex** — short, modern, AI-native, and not tied to HVAC, FDD or maintenance

The name is deliberately domain-neutral. Nothing in the documentation should
narrow Synex to HVAC. HVAC is the first vertical, not the definition.

## 2. The kingpin

> **Synex Copilot — the intelligent operating layer for Graylinx**

The Copilot is not a feature of the platform. It is how the platform is used.
Every other capability is a skill the Copilot reaches, through the Control
Plane, with evidence and an audit trail.

A user asks in their own words. Synex resolves who they are, what they are
allowed to see, what "this" refers to, what evidence exists, what it means,
what to do next, and — if approved — does it and proves it worked.

```
ASK → UNDERSTAND → FIND DATA → EXPLAIN → RECOMMEND → CREATE/ACT → VERIFY → REPORT → LEARN
```

## 3. The three P0 pillars

| Priority | Pillar | Promise |
|---|---|---|
| P0 | Synex Copilot | One assistant that understands, explains, prepares work and proves the result |
| P0 | Reports | Ask a question, get the answer with the numbers behind it |
| P0 | Work Orders | Work that arrives carrying its own justification and cannot close unproven |

Reports and Work Orders keep their own screens. The Copilot is a third door to
the same capability, not a replacement for the first two.

## 4. The four local models

Do not invent a fifth. Power comes from models + agents + tools + existing
ML/FDD + data + RAG + Control Plane + workflows + verification.

| Model | Size | Env | Role |
|---|---|---|---|
| `gemma4:26b-a4b-it-qat` | ~16 GB | `OLLAMA_MODEL_BRAIN` | Reasoning, final answer |
| `devstral:latest` | ~14 GB | `OLLAMA_MODEL_TOOL` | Tool execution, ReAct loop, read-only NL→SQL |
| `phi4` | 9.1 GB | `OLLAMA_MODEL_TEXT` / `_AUDITOR` / `_RAG` / `_DEFAULT` | Routing, narration, grounding, audit |
| `nomic-embed-text` | 274 MB | — | 768-dim embeddings, always local |

Rules: the brain never calls tools directly; the executor never writes the final
user-facing answer; the auditor must not be the model that wrote the answer;
embeddings never leave the site.

## 5. The separation law

This is the single most important architectural statement in the product.

| Question | Decided by | Never decided by |
|---|---|---|
| Is this reading abnormal? | The ML model, as a residual | Rules or the LLM |
| Is the equipment fit to be judged? | A deterministic gate | ML or the LLM |
| Has the pattern lasted long enough? | A deterministic persistence rule | The LLM |
| Which fault class is this? | The deterministic isolation path | The LLM |
| What does it mean in plain English? | The LLM | — |
| What priority does the work get? | A deterministic formula | The LLM |
| Is this person allowed? | Plain software — the Control Plane | ML or the LLM |
| Did the repair work? | Post-work residuals + a deterministic rule | The closure note or the LLM |

## 6. The FDD engine (first vertical: water-cooled chillers)

Six normal-operation models per chiller. A residual is
`rX(t) = X_actual(t) − X_predicted(t)`.

| Model | Predicts | Inputs | Residual |
|---|---|---|---|
| DP | Discharge pressure | Suction pressure; cooling load; condenser water entry temp; condenser flow; lead/lag | `rDP` |
| SP | Suction pressure | Evaporator leaving; evaporator entry; evaporator flow/DPT; lead/lag | `rSP` |
| DT | Discharge temperature | Suction pressure; discharge pressure; cooling load; condenser water entry temp; condenser flow; lead/lag | `rDT` |
| Power | Chiller amps / power | Evaporator leaving temp; chiller load; condenser water entry temp; condenser flow | `rPwr` |
| Comp Amps | Compressor amps | Suction pressure; discharge pressure; chiller load; lead/lag | `rAmp` |
| Cond Leaving | Condenser water leaving temp | Chiller load; condenser water entry temp; condenser flow; lead/lag | `rCWL` |

Computed: evaporator ΔT, condenser ΔT, and
`efficiency proxy = (condenser ΔT × condenser flow) ÷ (evaporator ΔT × evaporator flow)`.

**Gates — nothing is diagnosed until all pass:** running steady, load above the
model's floor, flows valid, no setpoint change, and the pattern persisted
(20–30 min proposed, unconfirmed — see Q6).

**Isolation path:** `rPwr` high → `rDP` high → `rCWL` high or normal separates
condenser water-side from refrigerant-side high head. Steady drift over weeks =
fouling; spiky/intermittent = low condenser flow. `rDP` normal with `rAmp` high
= compressor inefficiency; `rDP` normal with `rSP` low = starved evaporator.
`rDT` is a **support signal only** and must never be used to separate the
high-head causes.

**Honest ambiguity:** undercharge and restriction/underfeeding stay a combined
label. Overcharge and non-condensables stay a combined label. Do not let any
document imply the platform separates them.

**The dependency that shapes everything:** condenser flow feeds DP, DT, Power
and Cond Leaving — four of the six models. Without a trustworthy condenser flow
signal, the entire efficiency and high-head branch collapses and the correct
output is `NO_DIAGNOSIS` plus a data-quality work order. This is Q1 and it is
the highest-leverage open question in the programme.

## 7. Answer contract

Every Copilot turn ends in exactly one of six states:
`ANSWERED` · `PARTIAL` · `NO_DIAGNOSIS` · `NEEDS_APPROVAL` · `BLOCKED` · `FAILED`.

Confidence uses four words only: **Confirmed**, **Likely**, **Possible**,
**Not enough evidence**.

## 8. What exists today

| Artefact | State | Location |
|---|---|---|
| Product & Architecture Document v4 | 78 pages, 44 chapters, product-first, validated | `docs/00-source/` |
| Feature Review Pack | 9 pages landscape, 85 features, 20 SME questions | `docs/00-source/` |
| WC Chiller FDD specification | Source of section 6 above | `docs/00-source/` |
| Feature register | 85 features, IDs C/R/W/A/F/K/P/I/L/V/U/S/G | `mvp/FEATURE-REGISTER.md` |
| MVP cut | Proposed, not agreed | `mvp/MVP-SCOPE.md` |

## 9. What Synex stands on

Synex is not being built on empty ground. Two pieces of the platform already
exist and are used as they are:

| Piece | What it means for the build |
|---|---|
| **The graylinx-v2 database** | The shared platform database. Telemetry, assets, work orders, cases and threads live here. Stage 0 of the sequencing is integration, not construction. |
| **The Jarvis box** | A rented Jarvislabs.ai GPU, used exactly as it is for Thermynx: **RTX PRO 6000 Blackwell, 96 GB, India region**, on demand, about ₹179/hr plus ₹2.84/hr for 250 GB. Chosen because the four-model roster must fit on **one** card — Ollama does not pool GPUs cleanly — and the resident set is roughly 41 GB at Q4 and 53 GB at Q8. Worked in one contiguous burst per session and then terminated; a fresh box wipes `/home`, so the roster re-pulls in about ten minutes. Nothing touching a model ships without a green run on it, and the acceptance run is a box run. Source: `docs/operations/hardware/JARVISLABS_GPU_SELECTION.md` and `JARVIS_BOX_BURST.md` in the Thermynx repository. |
| **The same stack** | Python and FastAPI on the service side, React and TypeScript on the front end, PostgreSQL, Ollama for local inference, LangGraph for the agent loop. Chosen because it is proven here, not because it is novel — the leverage is in the Control Plane, the verification layer and the case lifecycle, none of which the stack gives us for free. |

A working FDD and agent implementation also exists. Its decisions are inherited,
not re-litigated — see section 10.

## 10. Inherited constraints

These were decided before this programme, with reasoning recorded against source.
They are settled truth here. If a document contradicts one of these, the document
is wrong.

| # | Constraint | Why it is not negotiable |
|---|---|---|
| 1 | The checklist library is **curated content, never model output** | A checklist directs physical work on pressurised refrigerant equipment. A plausible-but-wrong item is worse than no item. It is also what makes SME review possible at all. |
| 2 | **No numeric confidence score** | The trained model ships none, and a derived 0–100 is read as a probability by whoever sees it. Qualitative axes only — which is why section 7 allows exactly four words. |
| 3 | Severity comes from **fault class plus persistence, never residual magnitude** | Measurement showed non-faults deviate more than faults. This constrains the `W4` priority formula. |
| 4 | A statistical prior may **reorder questions and nothing else** | If the prior is wrong the cost is one less-efficient question, never a wrong conclusion. |
| 5 | **No automatic elimination** on unreviewed thresholds | Elimination is irreversible in this flow. Automatic elimination on unreviewed thresholds is more dangerous than the ambiguity it removes — which is why `F7` keeps its combined labels. |
| 6 | Routing to a human is a **static per-label lookup**, not a model judgement | The language model decides *what to ask*, never *whether to ask*. |
| 7 | `NULL` means **not diagnosed**, never healthy | An empty queue on a blind window would read as a clean plant. Vindicated in practice: a two-month window was blind, not clean. |
| 8 | **`cannot_check` is separate from `not applicable`** | Six "N/A" presses once opened a blocking gate with zero evidence behind it. That is how a safety gate gets walked past. Constrains `RC4` and `RC5`. |
| 9 | **Three escalation routes**, not one | Sideways (wrong skill), up (authority or judgement) and defer (right person, wrong moment) are not interchangeable. Escalating up lands unassigned and says so. |
| 10 | **No interim holding action ships unreviewed** | Shipping an unreviewed holding instruction is worse than none — accepting that a deferred critical fault then runs unprotected. |
| 11 | **Learning from closed cases is deliberately not built** | Without a retraction mechanism, one wrong confirmed root cause becomes permanent precedent. This is why `F9` and `V7` sit outside the MVP. |
| 12 | **Event grouping is display-level only** | The per-label cases are the trained model's actual output; rewriting them destroys the record of what it emitted. Group them in the view, never in the data. |
| 13 | **Roles are capabilities, not ranks** | Ranking by seniority once sent a filter-drier restriction to a supervisor because one incidental records question outranked three refrigeration measurements. |
| 14 | A figure is **a value or a stated absence, never both and never neither** | The alternative is a report that reads as informative and is not. Constrains `C21`. |
| 15 | **Every artefact states its data window** | Anomaly counts were once shown on the database wall clock under a heading describing a telemetry window that did not overlap it at all. Constrains `C22`. |
| 16 | The honesty layer **overrides the model**, it does not advise it | A reassuring headline over a blind window is replaced outright and the record marked corrected. |
| 17 | Some evaluation dimensions are **hard** — exempt from any overall tolerance | A report whose own figures disagree cannot pass because it scored well elsewhere. Constrains `EV3`. |
| 18 | The evaluation suite **has its own tests** | Deliberately dishonest inputs are fed to the gate so it cannot silently start passing everything. Constrains `EV4`. |
| 19 | **Do not take the absolute value of a signal before judging credibility** | `ABS()` let a flow reading of −2.49 count as credible and understated a dead transmitter by 62 days. |

## 11. The three role systems

Three different things are called roles, and conflating them causes real routing
bugs. This is question Q18.

| System | Members | Used for |
|---|---|---|
| **User personas** | Reliability Engineer, Technician, Supervisor, Planner, Manager, Executive, Customer, EHS | scope and answer depth — `C11`, `U1`–`U5` |
| **Capability roles** | operator, maintenance, technician, supervisor, vendor | who can answer a checklist item — `RC3` |
| **Agent skills** | see below | which skill the Copilot routes to — `C3`, `C18`, registered by `C20` |

### The skills the MVP needs

Seven, of three deferred. A skill is not a feature of its own — it is a named
entry in the `C20` registry with a tool scope and a control level.

| Skill | What it does | In MVP | Delivered by |
|---|---|---|---|
| Converse | greeting, capability, starter prompts — no telemetry touched | yes | `C16` |
| Look up | exact numbers from the database, read-only | yes | `C17` |
| Explain | the FDD rule path in plain English | yes | `C5` |
| Investigate | multi-step enquiry across FDD, trends, history, knowledge | yes | `C4`, `C6` |
| Prepare work | draft the work order, priority, evidence | yes | `C8`, `W1`–`W4` |
| Resolve | drive the case through its checklists to a root cause | yes | `RC1`–`RC8` |
| Verify | compare post-work evidence and return one of three outcomes | yes | `V1`–`V6` |
| Optimise | setpoint and staging advice | no — Phase 2 | `E4` |
| Brief | condense a period for a manager or executive | no — Phase 2 | `C14`, `U2` |
| Orchestrate | a planner running several skills as one job | no — Phase 2 | `C10` covers sequencing without it |

### The personas the MVP needs

Four of eight. The loop cannot close without all four — a fault has to be judged,
worked, approved and governed.

| Persona | Why the MVP needs them | Delivered by |
|---|---|---|
| Reliability Engineer | judges the fault, opens the case, asks why | `U6` |
| Technician | does the work and records findings | `U3`, `RC4` |
| Supervisor | approves, unblocks, and owns the close gate | `U7`, `C9`, `W9`, `RC5`, `RC7` |
| Administrator | authors scope, the approval matrix and the policy version | `U8`, `G1`–`G3` |
| Planner | — deferred with planning | `U4`, Phase 2 |
| Manager · Executive | — needs an outcome history that will not exist yet | `U2`, Phase 2 |
| Customer | — multi-tenant surface for little MVP learning | `U1`, Phase 2 |
| EHS | policy owner in the MVP rather than a daily user; the block is enforced without a screen | `S1`, `S4` |

## 12. Scale, and what that rules out

The first vertical runs at roughly ten units on one facility. The existing
platform is sized for that, and the things it deliberately does **not** have are
gated on triggers rather than dates:

| Trigger | Threshold | What it would introduce |
|---|---|---|
| A second facility | any | multi-broker replication, CDC in place of a polling bridge |
| External feeds | tariff, weather or vendor APIs | scheduled dependency-ordered ingestion |
| Model retraining | new labelled data | a train → validate → swap pipeline |
| Volume | daily telemetry beyond roughly a million rows, about fifty units | a separate warehouse engine |

None of these hold today. Designing for them now would be the expensive kind of
foresight — but a document that quietly assumes them is worse, so they are named
here and excluded.

## 13. Known constraints

- On-premise by default. Embeddings and inference stay local.
- Agents are read-only with respect to hardware control. No tool issues a
  control command to plant equipment, in any phase.
- Models are fitted per asset, not per fleet. Two identical chillers on one site
  do not share a model.
- The platform must state when it is in degraded mode rather than silently
  substituting a weaker capability.
