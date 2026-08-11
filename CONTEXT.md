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

**A residual is not zero-centred.** This is the single most consequential thing
the discovery pass found, and it changes how the table below must be read.
Measured healthy baselines on the reference plant: chiller 1's current residual
sits at a median of **−25.65** in normal operation; chiller 2's discharge-pressure
residual sits at **−27.86** against chiller 1's −7.53. So:

- "High" and "Normal" in the isolation path mean **high or normal for this asset,
  against its own healthy distribution** — median and spread. They never mean a
  number above an absolute threshold. That is `F15`.
- Severity is never derived from `|residual|`, because non-faults were measured to
  deviate *more* than faults. That is inherited constraint 3.
- Two identical machines will have different bands. This is why models are fitted
  per asset and never per fleet.

A design that compares residuals against zero, or against a shared threshold,
will rank ordinary operation above a real fault.

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
| **`graylinx_synex` — our own database** | Cloned from `graylinx_v2` on 2026-08-11: 193 tables, 3,879 MB. Verified exhaustively rather than by sample — every row in every table of all three databases counted. `graylinx_v2` and `graylinx_synex` match on all 193 tables and 14,271,741 rows. Synex writes here and nowhere else. |
| **What it was cloned from** | `shiva` is the customer's snapshot and is **read-only**. `graylinx_v2` is a writable working copy of it. `graylinx_synex` is a third generation, so staging demo data for a pitch cannot disturb the copy that is in active use. Same reasoning, applied once more. |
| **156,129 slots in it are simulated** | The snapshot's real data ends 2026-06-23; a simulation extends it to 2026-08-05. `snapshot_simulated_slots` names every synthetic `(equipment, slot_time)` pair, so real and generated can always be told apart. Treat a simulated window exactly as `C23` treats an untrusted one — anything shown over it says so. |
| **The Jarvis box** | A rented Jarvislabs.ai GPU, used exactly as it is for Thermynx: **RTX PRO 6000 Blackwell, 96 GB, India region**, on demand, about ₹179/hr plus ₹2.84/hr for 250 GB. Chosen because the four-model roster must fit on **one** card — Ollama does not pool GPUs cleanly — and the resident set is roughly 41 GB at Q4 and 53 GB at Q8. Worked in one contiguous burst per session and then terminated; a fresh box wipes `/home`, so the roster re-pulls in about ten minutes. Nothing touching a model ships without a green run on it, and the acceptance run is a box run. Source: `docs/operations/hardware/JARVISLABS_GPU_SELECTION.md` and `JARVIS_BOX_BURST.md` in the Thermynx repository. |
| **The same stack** | **Python and FastAPI on the back end**, React and TypeScript on the front end, MySQL for the plant snapshot and PostgreSQL with pgvector for the platform's own state, Ollama for local inference, LangGraph for the agent loop. Chosen because it is proven here, not because it is novel — the leverage is in the Control Plane, the verification layer and the case lifecycle, none of which the stack gives us for free. |
| **The Jarvis connection** | The back end talks to the model roster over Ollama on the rented box, not to a hosted API. That is what keeps embeddings and inference on infrastructure we control, and it is why the roster has to fit one card. |

A working FDD and agent implementation also exists. Its decisions are inherited,
not re-litigated — see section 10.

## 9a. What Synex is, and what it is not

**Synex is an AI layer on the existing Graylinx platform, not a replacement for it.**
It plugs into what is already there: the plant database, the equipment models, the
work-order records. What it adds is the Copilot, the case lifecycle between a fault
and a work order, and the verification that proves a repair worked.

**This MVP exists to be shown.** Its job is to demonstrate the AI layer's abilities
convincingly enough to be worth building out — the pitch, the differentiation, and
the argument for the approach. That is a real constraint on scope, and it explains
some of the cut: the loop must be *complete* end to end, and it does not have to be
*broad*. One asset class on one site, closing the loop, beats ten domains that
cannot prove anything.

It does not change the honesty rules. A demonstration that overstates what the data
supports is worth less than one that shows the platform refusing — which is why
`NO_DIAGNOSIS` is in the walkthrough rather than hidden from it.

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
| 20 | **An estimate does not settle a blocking check** | On the reference plant an untagged answer defaulted to `estimated` and opened a blocking gate. This is the same failure as constraint 8, by a second route. Constrains `RC10`. |
| 21 | **Detection is not seeding** | Twenty-two detected episodes sat outside the case queue because nothing called the seed. A detector that fires into nowhere is worse than no detector, because the queue reads as empty. Constrains `RC8`. |
| 22 | **A case must be able to go stale** | Four open cases described transmitters that had been repaired weeks earlier, and twenty had been waiting since April. Constrains `RC9`. |
| 23 | **An operator must never be blocked by a check they cannot perform** | A domain review found an oil analysis being shown to whoever opened a compressor case. Constrains `RC3`. |
| 24 | **An untagged item defaults to technician, and that asymmetry is deliberate** | Mis-tagging a technician task as operator puts an unqualified person on a pressurised circuit. The reverse wastes a callout. Over-escalating is the cheap error. |
| 25 | **Role order is display order, not a capability ladder** | A supervisor is not a more capable technician; it is a different capability — authority and records, not gauges. Treating it as seniority once sent a filter-drier restriction to a supervisor because one incidental records question outranked three refrigeration measurements. Escalation therefore targets by **workload**, blocking items weighted double, ties broken toward whoever can physically measure. |
| 26 | **The language model selects and contextualises library content; it never authors a field instruction** | A checklist directs physical work on pressurised refrigerant equipment. It also removes the evaluation gate for that content, because data is unit-testable without a GPU. Constrains `RC2`. |
| 27 | **Only a class the model itself declares undecidable gets a differential** | Narrowing a class that already names a mechanism would be inventing ambiguity the model did not report. Four of eleven classes qualify. Constrains `RC12`. |
| 28 | **A confirmation never eliminates its siblings** | A fouled condenser on a machine that is also low on flow is *two real causes*, and collapsing to the first confirmation is how the second gets missed. |
| 29 | **Elimination is final** | An answer does not resurrect a cause that has been ruled out. This is why an unreviewed discriminator is dangerous: nobody re-examines a settled question. |
| 30 | **"Can't tell" must have no effect at all** | Every discriminating question carries an explicit *can't tell* option with empty effects, or uncertainty would silently eliminate something. |
| 31 | **Every elimination records the check and the answer that caused it** | *"Why did nobody look at the tower?"* needs a better answer than *"the software decided"* — especially while the discriminators are unreviewed engineering judgement. Constrains `RC13`. |
| 32 | **Exhausted is not the same as settled** | A differential that runs out of questions has established *"we cannot separate these with the checks we have"*, which is a different statement from a conclusion. Constrains `RC14`. |
| 33 | **Pause for a person exactly when the data cannot answer the question — and never otherwise** | Which faults those are is fixed per fault class, because the trained model already declares which ones it cannot resolve. The language model decides *what* to ask; it never decides *whether* to ask. |
| 34 | **Never re-detect** | Where the trained model has a verdict, consume it. It is higher-confidence than any heuristic we would write, and re-deriving it invents a second opinion nobody asked for. |
| 35 | **One case per equipment, fault and day** | A single real fault spans hundreds of consecutive readings — up to 412 observed. Per-slot cases would bury one afternoon under five hundred rows. |
| 36 | **Event grouping must not pick the longest-running label as primary** | The ambiguous class is usually both the longest-running and the least informative — it appeared on 12 of 12 fault days. Picking "the biggest" would title every event with the label that says least. A determinate class present alongside it leads. |
| 37 | **Every fault class must carry at least one check the operator can do** | Otherwise somebody starts stuck rather than getting stuck partway. A test fails if a future edit walls a class off. |
| 38 | **A check the reader cannot perform collapses; it does not grey out** | A greyed-out *"oil analysis — acid, moisture, metals"* still reads as a demand on whoever is standing there. |
| 39 | **The next question is the one that could move the most live candidates** | Tie-broken toward whoever is already at the machine, so cheap eliminations come first. On the weakest class the opener is *"is the machine actually running harder?"* — read off a panel, and it can settle the whole class alone. |

## 10a. What the reference plant's data actually says

The first vertical is not a clean slate, and the numbers below change what the MVP
can honestly promise. All are from the Thermynx FDD discovery pass, 5 August 2026,
against one plant's snapshot — they are **evidence about instrumentation reality**,
not yet confirmed for the sites Synex will target. That confirmation is Q1 and Q2.

| Finding | What it does to the design |
|---|---|
| **Condenser flow has never recorded a non-zero value** at that site | This is the signal `CONTEXT.md` §6 calls the highest-leverage single measurement, feeding four of the six models. If the target sites match, the correct output for the whole efficiency and high-head branch is `NO_DIAGNOSIS` plus a data-quality work order — by design, on day one. |
| The documented chilled-water flow derivation **no longer holds** — the differential-pressure input reads NULL while flow reports healthy values | Q2 is not merely open; the chain it asks about is known to be broken. |
| **No phase currents, voltages, insulation or VFD data are streamed** | The electrical branch cannot be contradicted by measurement, so an operator's judgement is the only input — which is exactly where elimination becomes dangerous. |
| The dominant fault class is the **ambiguous** one — 47% of fault slots, 62% of fault days | Honest ambiguity (`F7`) is not an edge case to be tidied up later. It is the median outcome. |
| One model runs at **nRMSE 48%**, and its residual is partly model error | `F10` model health and `F11` quarantine are load-bearing, not hygiene. |
| Models trained once, never refitted, still scoring months later | Nobody owns the refit trigger. Q27. |
| Efficiency: design band 0.65–0.85, healthiest measured month **1.40** | There is no defensible baseline yet, so `E1` cannot be built as specified. Q21. |
| The taxonomy has **no safety impact class** — every escalation route ends in a work order | There was no way to say "stop the machine now". `S6` exists because of this. |
| `dpt` never changes — a constant 107.0 on one chiller and 112.9 on the other | **Condenser approach temperature cannot be computed at all**, which is the fouling threshold *and* a question inside a differential. Q8 is unanswerable until this is resolved. |
| Condenser ΔT is **negative every month** on one chiller, −3.0 to −3.4 | A condenser rejects heat, so leaving water must be warmer than entering. The two columns are swapped or mislabelled. No residual model can be trusted on that machine until it is fixed — and nothing detected it. `F16` exists because of this. |
| Both chilled-water flow transmitters have read near zero since May while ΔT and power stayed normal | Physically impossible, and it quietly invalidated two months of efficiency figures while blinding the fault model. A single-signal validity flag did not catch it; a cross-signal check would have. `F16`. |
| Four of seven fault classes are **declared undecidable** by their own names | Our `F7` keeps two combined pairs. Theirs has four classes whose names say `UNSPECIFIED` or `AMBIGUOUS`. Any confidence figure printed against those would be actively misleading — which is why section 7 allows four words and no number. |
| The checklist library is **124 curated items across 11 fault classes**, plus a 7-item generic fallback — 131 in total. Split **57 RCA · 37 corrective · 30 preventive**, of which **24 are blocking**. Four decision trees | Nothing in it has been reviewed by a refrigeration engineer. It is the last gate before a technician sees any of it, about one hour of SME time, and the long pole in `RC2`. "131 across 11 classes" is the imprecise phrasing — the fallback belongs to no class. |
| Role tags: **technician 49 · supervisor 38 · operator 29 · maintenance 7 · vendor 1** | Supervisor's 31% is almost entirely the *preventive* stage — intervals, schedules, trends. Prevention is a records-and-authority activity, so that is right in principle, but it means preventive work lands on the one role that had no queue to receive it. `U7` exists for this. |
| One review pass, of one class, has ever been run over those 124 role tags | It found an oil analysis — acid number, moisture, metals — being shown to whoever opened a compressor case. That is a lab task. |

**The honest read:** the platform's own detection layer is largely blind on the
branch this product leads with. That is an argument for `NO_DIAGNOSIS` being a
first-class output rather than a fallback, and against any roadmap that assumes
the FDD half is nearly done.

### Our own database fabricates the signal that matters most

Measured on `graylinx_synex`, 2026-08-11. Every numeric column on
`chiller_1_normalized` was compared across the real and the simulated window. Of 32
columns, exactly one differs in kind:

| Signal | Real window (31,884 slots) | Simulated window (12,529 slots) |
|---|--:|--:|
| `cond_flow` | **0 non-zero, max 0.0** | 3,354 non-zero, **max 893.7** |
| `dpt` | 8,089 non-zero | **0** |

`chiller_2_normalized` matches, with 3,592 synthetic values reaching 1,099.6.

This **confirms** the Thermynx finding above — condenser flow has never been
measured on the reference plant — and adds a constraint of its own. The natural
demonstration window is the most recent data, and it is entirely synthetic. Marking
it *simulated* is not sufficient, because the problem is not that the numbers are
generated: it is that they imply an **instrumentation capability the site does not
have.** Every other synthetic signal continues something the plant genuinely
measures. Full analysis in `docs/20-architecture/01-data-model.md`; the constraint is
D-009 and the feature is `C26`.

## 10b. The differential — how a cause is ruled out

A flat checklist says *go and do all six of these*. A differential says *three
causes fit; this one test kills two of them*. Same library, different question —
and it is the mechanism `F5` hands off to once a class is named but ambiguous.

**Scale on the reference plant:** 4 differentials · 19 candidate causes · 19
discriminating questions · about 41 effects. Only the four classes the trained
model declares undecidable have one.

| Effect | Meaning | Reversible |
|---|---|---|
| `confirm` | positive evidence **for** this cause | — |
| `eliminate` | rules the cause **out** | **no** |
| `keep` | consistent; neither confirms nor eliminates | — |

Two terminal states, kept deliberately distinct: **settled**, and **exhausted but
not settled** — the honest *"we cannot separate these with the checks we have"*.

**Why this is the highest-risk content in the programme.** Thirty-one causes have
already been eliminated on that queue, every one by a discriminator no refrigeration
engineer has reviewed. Elimination is irreversible and nobody re-examines a settled
question, so a wrong discriminator does not produce a wrong answer once — it
produces a confident wrong answer that is never revisited. That is why the SME hour
is spent on §1 of `mvp/SME-REVIEW.md` and nowhere else.

Two known holes, recorded rather than fixed: the highest-power question in the
condenser-water-side differential **cannot be answered from telemetry**, and
`REFRIGERANT_SIDE_HIGH_HEAD` names a region, probes five mechanisms, and has no
differential and no blocking items — so a case can conclude there with no evidence.
That is Q37.

## 10c. Four journeys, not one

`RC1`'s state machine is one object with several routes through it, and the pause
points differ by fault class. Measured on the reference queue:

| Journey | Cases | Where it pauses |
|---|---|---|
| **Straight through** | 13 | nowhere — the data is conclusive |
| **Needs a technician** | 26 | at the checks, and it refuses to proceed |
| **Broken sensor** | 2 | arrives already explained; waits for someone at the panel |
| **Model blind** | 2 | the same, except the detector itself is the problem |

**Two thirds of all detected faults are cases the sensors genuinely cannot decide.**
Four of the seven fault names say so in the name: *ambiguous*, *undercharge **or**
restriction*, *unspecified*, *unexplained*. A product built only for the
straight-through journey is a model viewer.

### What happens when the person who opened it cannot answer

The system offers the handoff rather than waiting to be asked, because a worker
often does not know they are out of their depth, that a handoff exists, or which one
is right. Each route produces a different artefact — this is `RC7` and `RC15`:

| Blocker | Goes to | Case state | Artefact |
|---|---|---|---|
| No tool | a technician, matched by skill against the fault | `escalated` | an **inspection** work order — the open checks are its task list |
| No authority, or cannot interpret | a supervisor | `escalated` | an **authorisation** work order — the task is the *question*, not a measurement |
| Wrong moment | nobody — parked with a reason and a date | `deferred` | none; nobody was called |
| Not sure | stays with you, offered for confirmation | unchanged | none; it eliminates nothing |

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

An earlier draft of this section said "four of eight". That was wrong, and the
register says so: **fourteen distinct roles are the primary user of at least one
feature in the cut.** The useful distinction is not who is present but who needs a
screen of their own.

**Four get their own surface** — the loop cannot close without a fault being
judged, worked, approved and governed:

| Persona | Why the MVP needs them | Delivered by |
|---|---|---|
| Reliability Engineer | judges the fault, opens the case, asks why | `U6` |
| Technician | does the work and records findings | `U3`, `RC4` |
| Supervisor | approves, unblocks, and owns the close gate | `U7`, `C9`, `W9`, `RC5`, `RC7` |
| Administrator | authors scope, the approval matrix and the policy version | `U8`, `G1`–`G3` |
| Planner | — deferred with planning | `U4`, Phase 2 |
| Manager · Executive | — needs an outcome history that will not exist yet | `U2`, Phase 2 |
| Customer | — multi-tenant surface for little MVP learning | `U1`, Phase 2 |
| EHS | policy owner rather than a daily user; the block is enforced without a screen | `S1`, `S4`, `S6` |

**Ten more are served without a surface of their own** — through the Copilot,
through Reports, or through somebody else's screen. Each is the primary user of a
feature in the cut, so none of them is deferred; they simply do not need a page
built for them yet.

| Role | Serves | Reached through |
|---|---|---|
| Data / Reliability | model health, quarantine, untrusted windows, case seeding | `C23`, `F10`, `F11`, `RC8` — alerts and the case queue |
| Maintenance | ranked recommendations and raising work from a sentence | `C6`, `W1` — the Copilot |
| **Analyst** | exact numbers with their lineage, and drilling to source | `C17`, `R5` — the Copilot and Reports |
| Platform | the skill registry, the gates, the Control Plane itself | `C20`, `EV1`, `EV4`, `G1`–`G5` — configuration, not a screen |
| Product | the honesty bar the build is held to | `EV2`, `EV3` — the evaluation gate |
| Manager | why a number moved | `R3` — Reports |
| Finance | reported numbers reconciled against source | `R10` — Reports |
| Planner | the deterministic priority formula | `W4` — their own queue view `U4` is Phase 2 |
| Audit | the trail, permanently | `G6` — the audit record |
| EHS | see above | `S1`, `S4`, `S6` |

The Analyst is worth calling out because the earlier draft omitted them entirely
while two MVP features name them as the primary user. That is exactly the kind of
omission the register is supposed to catch, and did.

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
