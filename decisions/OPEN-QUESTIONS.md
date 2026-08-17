# Open questions

Anything unresolved lives here. `TBD (Qn)` in a document must point at a row in
this file. When a question closes, record a decision in `DECISIONS.md` and move
the row to the Closed section — do not delete it.

## Naming

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| N1 | How do Synex and Thermynx relate — replacement, layer above, or separate products? | All positioning copy | Harshan | Open |
| N2 | Is "Graylinx Synex" or "Synex by Graylinx" the commercial form? | Cover, marketing | Harshan | Open |

## Product scope

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| S1 | Is the proposed MVP cut agreed? | `mvp/BACKLOG.md`, all build sequencing | Harshan | Open |
| S2 | Is the cooling tower in scope for phase one? | F13 | Vishnu + Harshan | Open |
| S3 | Which actions require SME sign-off rather than supervisor approval? | Approval matrix, G3 | Vishnu | Open |
| S4 | Relative weighting of criticality, SLA and production impact in the priority formula | W4 | Operations | Open |
| Q17 | Which build stage delivers `A1`, `U3`, `S1` and `S4`? Four MVP features are named by no stage, two of them safety features | Sequencing, and the stage-9 estimate | Harshan | Open |
| Q18 | Three different things are called roles — user personas, capability roles and agent skills. Which system governs which decision? | `C11`, `C20`, `RC3`, `U1`–`U8` | Harshan + Vishnu | Open |
| Q21 | What is a defensible efficiency baseline for these machines? Design band 0.65–0.85; the healthiest measured month on the reference plant is 1.40 | `E1`, and any cost or ROI figure | Vishnu | Open |
| Q22 | Which faults are answered by stopping the machine rather than by raising a work order? | `S6`, the escalation matrix | Vishnu + EHS | Open |
| Q23 | Does an estimated answer settle a blocking check, or only a measured one? | `RC5`, `RC10` | Vishnu | Open — proposed: measured only |
| Q24 | What triggers case seeding in live operation? | `RC8`; a detector that fires into nowhere leaves the queue reading empty | Harshan + platform | Open |
| Q25 | Should a case age, and into what? Auto-escalation on a timer dispatches people on a clock rather than on evidence | `RC9` | Harshan + Vishnu | Open |
| Q26 | What should marking a window untrusted actually do to reports, efficiency figures and the models? | `C23`, `C22` | Harshan + platform | Open |
| Q27 | Who owns model refits, on what trigger, and is there a schedule? | `F10`, `F11`, `F12` | Platform + Vishnu | Open |
| Q37 | Should `REFRIGERANT_SIDE_HIGH_HEAD` get a differential and blocking items? It names a region, probes five mechanisms, and has neither — so a case can conclude there with no evidence | `RC12`, `F7` | Vishnu | Open |
| Q38 | Two severity scales disagree on four of seven classes. Which one governs? | `W4`, and any queue ordering | Vishnu + Harshan | Open |
| Q39 | Evidence a checklist asks for already sits in the database and is not carried into the case, so a human is asked to fetch what the platform holds | `C4`, `RC2`, `W3` | Platform | Open |
| Q34 | Is the maintenance/technician split drawn in the right place for this crew? Only 7 of 124 items are tagged maintenance, yet brushing tubes, cleaning strainers and venting a loop are in-house mechanical work | `RC3`; the wrong split generates unnecessary callouts | Vishnu | Open |
| Q35 | Who approves a recurring obligation? A preventive item that creates a PM schedule commits somebody to future work | `RC11` | Harshan + Vishnu | Open |
| Q36 | Is there a plant document — an OEM manual or O&M schedule — the 124-item library should be reconciled *against*, rather than reviewed from scratch? | Could turn an hour of review into a cross-check | Vishnu | Open |
| Q29 | Are the entering and leaving condenser water columns swapped on affected assets? A negative condenser &Delta;T every month is physically impossible | `F16`, and every residual on that machine | Vishnu + site | Open |
| Q30 | What separates a starved evaporator caused by restriction from one caused by undercharge? The proposed test is the temperature drop across the filter-drier — can an undercharged circuit also produce a cold spot, and is it safe to measure while running? | `F7`; it is the first question asked on six fault episodes | Vishnu | Open — highest-consequence |
| Q31 | Is the ~4 °C gap in condenser leaving-water temperature between water-side and refrigerant-side faults a real physical difference, or a coincidence of when those faults occurred? | `F5`; if real, whole cause groups can be ruled out from data already held | Vishnu | Open |
| Q32 | Does an unusually equal split between two compressors (1.03 against a normal 1.17) indicate compressor inefficiency, or is it staging, lead/lag rotation or unloading? | `F5`; if real, it replaces a three-day oil analysis with a reading already held | Vishnu | Open |
| Q33 | What words do technicians actually use for "nothing found", and which words look negative but are positive findings? A wording detector read "clear cold spot" as a negative | `RC4`, `RC6` — a conclusion built on all-negative findings is misleading | Vishnu | Open |
| Q40 | Do we adopt the four evidence-graded response modes as specified, or collapse them? The claim behind them is that the assistant's value is inversely proportional to the model's certainty | `C25` | Harshan | Open — proposed: adopt |
| Q28 | Is the brain's reasoning mode toggled per stage? **Partly answered by observation:** a live trace shows the brain composing with thinking **on**. What is unrecorded is whether routing and narration run with it off The turn budget allows 1–3 s to plan and 2–6 s to reason, against a p95 of 8 s for a read-only answer and a first token inside 2 s. Reasoning always on will not hold those budgets; always off costs answer quality on the two stages that need it | Copilot latency and answer quality; `C3`, `C20` | Platform | Open — proposed: on for plan and reason, off for narration and routing |
| Q19 | Three inherited gaps are adopted as unsolved: no interim holding action for a deferred critical fault, no retraction mechanism (so learning from closed cases stays out), and duplicated checklist work under event grouping. Which, if any, does this programme take on? | `F9`, `V7`, and the deferred-fault risk | Harshan + Vishnu | Open |

## Instrumentation and data

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| Q1 | Is condenser flow measured at target sites, and is the signal trustworthy? | F1–F8: four of six models, and most fault classes | Vishnu + site survey | Open |
| Q2 | How is evaporator flow derived? **The documented derivation is known broken on the reference plant** — the differential-pressure input reads NULL while flow reports healthy values. What feeds it now? | `rSP` validity, efficiency proxy | Vishnu + site survey | Open — chain broken |
| Q14 | Is compressor lead/lag state reliably available from the BMS? | Five of six models | Site survey | Open |

## FDD thresholds — Vishnu

| ID | Question | Proposed starting point | Status |
|---|---|---|---|
| Q3 | Minimum load for a valid diagnosis | Confirm per machine type | Open |
| Q4 | Settling time after a start or stage change before residuals are trusted | TBD | Open |
| Q5 | Settling time after a leaving-water setpoint change | TBD | Open |
| Q6 | Persistence window — one value or per fault class? | 20–30 minutes as a common default | Open |
| Q7 | Healthy chilled-water ΔT band per machine | Design ΔT from the machine data sheet | Open |
| Q8 | Condenser approach temperature thresholds for fouling. **Currently unanswerable:** on the reference plant `dpt` is a constant, so approach cannot be computed at all. Is that tag a setpoint or design value rather than a measurement? | Per OEM data sheet — but the input must exist first | Open — blocked on the input |
| Q9 | Time constants separating low condenser flow from fouling | Low flow spiky/intermittent; fouling steady drift over weeks | Open |
| Q10 | Split overcharge from non-condensables, or keep combined? | Keep combined until instrumentation supports a split | Open |
| Q11 | Confirm undercharge and restriction stay combined | Keep combined, label the ambiguity honestly | Open |
| Q12 | Volatility threshold defining expansion valve hunting | Set from observed data | Open |
| Q13 | Sensor drift thresholds per sensor type before declaring sensor bias | Per sensor class | Open |
| Q20 | Are any fault classes missing from the fingerprint matrix? | Open — SME to add | Open |

## Verification and lifecycle

| ID | Question | Proposed starting point | Status |
|---|---|---|---|
| Q15 | What proves a condenser cleaning worked? | `rPwr`, `rDP`, `rCWL` back inside band, held several days across a representative load range | Open |
| Q16 | Re-baseline policy after an overhaul — who authorises, how long must the machine run first? | SME authorises; minimum steady running period to be agreed | Open |

## Platform and delivery

Three decisions that are ours rather than Vishnu's, all raised by reading the Thermynx
stack and measuring our own server. Full detail in `docs/20-architecture/01-stack.md`
and `02-deployment.md`.

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| Q41 | **How does a turn establish identity?** There is no authentication library in the backend at all, and `gl_user` / `gl_role` / `gl_access` hold zero rows in the snapshot — yet `G1` is `P0` and the Control Plane cannot grant a scope it cannot establish. `pyjwt` + `passlib` for a self-contained demonstration, a signed header from the host platform for production, or `authlib` for OIDC? | `G1`–`G4`, `U3`, `U6`–`U8` | Harshan + Vishnu | **Parked** — for the joint session |
| Q42 | **Should the plant database be read-only by grant rather than by convention?** The backend connects as `root` with `SUPER`, `DROP`, `FILE` and `GRANT OPTION` on `*.*`, and all three databases share the server — so the credentials reach `shiva`. Two `GRANT` statements would make "Synex never writes to the plant" a database property. Touches a server Thermynx shares | Nothing today; it removes a class of accident | Harshan + Thermynx | **Parked** — for the joint session |
| Q43 | **What does "production" mean for an on-premise delivery?** There is no Dockerfile anywhere and no offline wheel bundle, and an air-gapped plant needs pre-built wheels, pre-pulled images and pre-pulled Ollama models. Also: do the run-time honesty counters ship, or is `/metrics` enough? | Handing the product to a customer | Harshan | **Parked** — for the joint session |

**All three are parked for the joint session, and parking costs nothing today.**
Two of them genuinely block nothing: `Q42` removes a class of accident rather than fixing
a live defect — the SQL validator is thorough and there is no reachable vulnerability — and
`Q43` only becomes the critical path the moment someone says *"install it at the customer"*.

`Q41` is the one to watch. It blocks no demonstration, but `G1` is `P0` and four personas
need a scope, so it lands on the build critical path the day `S1` closes. If the build has
to start before the question is answered, the demonstration-safe fallback is a **persona
switcher with no real authentication, labelled as a demonstration affordance** — it lets
`G1`'s scoping logic be built and tested against a known identity without committing to
any of the three routes. That keeps the question genuinely open instead of answering it by
default, which is how these get decided badly.

## Raised while building

These arrived from measuring or from writing code, not from reading a document. They had
been appended to the section above without a header row of their own, so they rendered as
paragraphs rather than as a table — which is why `Q46` and `Q47` now sit under a heading.

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| Q51 | **Three of the four inputs `W4`'s priority formula names do not exist.** The register specifies a deterministic formula over *criticality, risk, SLA and production impact*. Only risk is partly available — and only partly, because severity is sourced for one fault class of nine (`Q49`). The snapshot holds **no equipment master and no criticality rating**, **no service-level target**, and **no production schedule** joined to this plant. A formula that silently dropped three of its four terms would produce a number that looks like a priority and is really a severity wearing a rank, which is worse than no number because a planner would schedule against it. `app/domain/priority.py` therefore computes what it can, carries `missing` and `is_complete=false`, and the interface lists what was left out | `W4` completeness, and any queue ordered by it | Harshan + Vishnu | Open |
| Q49 | **What severity does each fault class carry?** `F17` says a class has exactly one severity read from one place, and `app/domain/faults.py` is now that place — but only **one of nine** labels has a sourced value: the data model records `CONDENSER_LOW_FLOW` as the only `critical` class. The other six faults are `UNRATED` and render as *"severity not yet agreed"* rather than defaulting to a plausible `MEDIUM`. Severity is stored nowhere in the database, so there is nothing to read it from — and two severity scales previously disagreed on four of seven classes, which is the failure `F17` exists to prevent. Assigning six values in the one authoritative place without a source would reproduce that failure with more confidence behind it | `F17`, `W4` priority inputs, and what a case card shows | Vishnu | Open |
| Q50 | **At what nRMSE does a model's residual become untrustworthy?** Chiller 1's current model runs at 48.03 against chiller 2's 2.65, and on that machine the residual is out of band in **402 of 412** high-head readings — so the alarms may be an artefact of the fit rather than a fault. `POOR_FIT_NRMSE` is provisionally 10.0 and is used **only to decide whether a badge is shown**, never to suppress a fault, so being wrong costs a visible warning rather than a hidden problem. `F10` and `F11` depend on the real answer | Whether chiller 1 residuals may be shown unqualified; `F10`, `F11` | Vishnu | Open — first question in `mvp/VISHNU-GROUPING.md` |
| Q48 | **What are the three unnumbered resource ceilings?** `docs/20-architecture/03-from-thermynx.md` §7 gives ten bounds and names the failure each prevents, but three carry no value: per-request input characters ("capped"), assembled context ("hard cap") and SQL rows ("hard `LIMIT`"). The other seven are numbers we inherited and can copy. These three cannot be invented — the input cap trades a pasted log against a VRAM spike, the context cap trades evidence against silent partial context, and the row cap trades a useful answer against pulling a whole table. `app/config.py` carries conservative provisional values and marks all three `provisional: true` in `ceilings()`, so the operations endpoint shows which numbers are ours and which are guesses | Nothing today — the bounds hold. It blocks *claiming* they are the right bounds | Harshan | Open |
| Q47 | **Which fault labels can share one physical cause, and which must never be grouped?** On 2026-04-15 chiller 1 carried five labels at once, and twelve equipment-days produce thirty-nine naive cases. `RC19` groups them; the grouping rules are **our inference and unreviewed**. The dangerous direction is over-grouping: a hidden undercharge costs a compressor where a duplicate visit costs a morning. Also: two of the five contradict each other on the sign of the discharge-pressure residual — two faults, one transition, or untrustworthy data? | `RC19` grouping rules, and `RC12` narrowing when labels conflict | Vishnu | Open — agenda §1.8 |
| Q46 | **What is the target turn time for the demonstration?** No document states one, and the purpose of this MVP is to be shown. Fourteen stages, a brain call with a generous budget, a 1–3 s critique layer and a 150 s graph ceiling can compose into an answer nobody wants to watch arrive. A number is needed — it is not ours to invent, and once set it constrains whether the advisory reasoning pass is affordable at all | Perceived quality of every demonstration | Harshan | Open |

## Knowledge coverage — from the Thermynx playbook review

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| Q44 | **Should fault and alarm code lookup be in the cut?** Thermynx has **zero** coverage — not one drive or controller fault code in any playbook — so a technician holding a code has nothing to retrieve. Registered nowhere by us either | `K1`, `K5` depth | Harshan + Vishnu | Open |
| Q45 | **Should a work-order resolution note become searchable knowledge automatically?** It already works in Thermynx and only **2** notes have ever been captured. This is not the same thing as `F9`/`V7`, which we deferred deliberately: human-written text becoming retrievable is a weaker claim than a model-derived root cause hardening into precedent. Cheap, and it grows plant-specific knowledge for free | `K1`, and the value of `W8` findings | Harshan | Open |

| Q53 | **Should the measured window now extend past 2026-06-23 11:50?** It ends there because the *simulation* began at 11:55, and the re-clone (D-017) removed every simulated row — real data now runs to 2026-08-05 17:10, so the clip is a boundary against something that no longer exists. Extending it would add roughly 12,400 slots per chiller and **move every count in the demonstration script and the golden set**. Deliberately not changed on 2026-08-17, the day before the demonstration; keeping it is why all ten label counts came through identical. Note the interaction: 4,281 `compressor_power_residual` values and the whole derived tail sit beyond the current clip, so extending the window makes a **sixth model appear** and would need `FITTED_MODEL_COUNT` revisited | the demonstration script, the golden set, `FITTED_MODEL_COUNT`, every asserted count | Harshan | Open |

| Q54 | **How far back does an open case count as the same problem?** `RC19` says the same label on the same equipment "in a window" reopens rather than opening a second case, and fixes no number. Set to **one day** in `app/domain/correlation.py` because that is the granularity the detector produces — episodes are keyed per (equipment, label, **day**), so a wider window compares units that do not exist. It only ever decides *reopen versus open fresh*; it eliminates nothing and suppresses no detection | `RC19` reopen behaviour, and the case count a supervisor sees | Harshan + Vishnu | Open |

| Q55 | **What counts as "drawing normal power" on our two chillers?** `F16`'s headline cross-signal check — near-zero flow *with* normal ΔT *and* normal power means a dead transmitter rather than a chiller fault — needs a power band. The source (`HVAC_INSTRUMENT_VALIDITY.md`) gives *"e.g. 150–200 kW on a large water-cooled machine"*, which is an illustration rather than a threshold, and our machines are not that machine. Implemented as **power > 0** so the check is conservative: it fires whenever the machine is drawing anything at all, which over-detects rather than under-detects. A real band would tighten it | `F16` sensitivity, `F6` dispatch blocking | Vishnu | Open |

| Q56 | **How long may a case sit untouched before it ages visibly?** `RC9` says a case nobody has touched must age rather than sit silently, and fixes no interval. Set to **7 days** in `app/db/case_store.py` because the observed failure was cases waiting since April — months, not days — so any value in the range of days surfaces it. Ageing only ever *shows* a case; it never closes, hides or decides one | `RC9`, the supervisor queue | Harshan | Open |
| Q57 | **How often should detection-to-queue reconciliation run?** `RC17` fixes no interval. Set to **15 minutes** in `app/jobs/reconcile.py` because the plant writes on a five-minute slot cadence, so three slots is the smallest window that cannot miss a whole reading period. `RC8` makes a re-run free, so running often costs a few no-op queries while running rarely cost twenty-two episodes — erring toward often is the cheap error. It changes latency only, never what is detected | `RC17` | Harshan | Open |
| Q58 | **At what corpus size does pgvector need an index?** The document store does an exact scan today. IVFFlat and HNSW only pay off in the thousands, and an approximate index trades accuracy for a speedup nobody would measure at 131 checklist items plus a handful of documents. No trigger is recorded, so none is asserted — the scan is exact and the reason is in `app/db/knowledge.py` | `K1` latency at scale | Harshan | Open |
| Q59 | **How many passages should an SOP search return?** `K1` fixes no number. Set to **5** in `app/retrieval/sop.py` because the four decision trees and the seven-item generic fallback mean a single question rarely has more than a handful of relevant entries, and a reader handed twelve passages reads none. It bounds display only; it never stops a passage being findable | `K1`, `S4` | Harshan + Vishnu | Open |

| Q60 | **Which fault classes carry a safety impact?** `S1` blocks a safety-critical action and `S6` raises a stop-the-machine instruction, but the taxonomy has **no safety impact class at all** and six of seven fault classes have no agreed severity (`Q49`). The mapping in `app/domain/safety.py` is therefore **deliberately empty and gated**, exactly as the checklist library is gated by `sme_reviewed` — the mechanism is complete and tested, the content is absent, and the unassessed count is exposed as a number. Nothing was guessed: assigning a safety impact on our own judgement is the one place a wrong answer costs a person rather than a morning | `S1`, `S6`, the escalation matrix | Vishnu + EHS | Open |
| Q61 | **How quickly must a stop-the-machine instruction be acknowledged, and what happens if it is not?** `S6` raises a human instruction — no tool stops a machine, in any phase (`CONTEXT.md` §13) — so an unacknowledged stop order is a real gap with no owner. No document states a target, so none is set; the case reports the instruction as *raised and not received* rather than assuming it landed | `S6`, `S5` EHS escalation | Vishnu + EHS | Open |
| Q62 | **What recurrence interval does a preventive action get?** `RC11` turns a preventive item into a scheduled obligation with a named approver. Nothing in the library or the source documents states an interval for any of the 30 preventive items. `app/domain/followup.py` sets `None` and reports the commitment as *unscheduled* — a distinct state, so the missing half is visible rather than defaulted to a plausible-looking figure that would read as a schedule until the thing it prevents happens | `RC11`, `U7` the supervisor queue | Vishnu | Open |
| Q63 | **How many blocking items does each fault class carry?** The library is 24 blocking items across 11 classes, but the per-class split is recorded nowhere. `Checklist.blocking_items` reads the data rather than asserting a count, so this changes no behaviour — it means we cannot yet say *"this class has three blocking checks"* in an interface | `RC5`, `RC6` | Vishnu | Open |
| Q64 | **How old may a stored reading be before it stops being worth offering?** `RC18` offers a stored value as *"the stored reading was X — confirm at the panel"*, and it never settles a blocking check. But a reading from six weeks ago is not worth a technician's attention at all, and no document fixes the boundary. Named constant with the question against it in `app/domain/stored_readings.py`; it bounds what is *offered*, never what settles | `RC18`, `RC10` | Vishnu | Open |
| Q65 | **Should the tool gateway check equipment scope?** Found by the adversarial suite: several tools accept an equipment key and **no gate reads `Scope.covers`**. Today every persona sees all of a single site, so nothing is reachable that should not be — but that is true by configuration rather than by construction, and the second site changes it. `G1` recomputes scope every turn; `G4` does not yet consult it | `G4`, `G1`, multi-site readiness | Harshan | Open |
| Q66 | **How many turns should the Copilot remember?** `C15` fixes no depth. Set to **6** in `app/agents/memory.py` because the four case journeys plus an opening and a closing turn is the longest exchange the demonstration script contains, so nothing in the walkthrough falls off the end. It bounds recall only — it can never cause a refusal, and dropping a turn never changes what the current turn may see | `C15`, `C10` | Harshan | Open |

| Q67 | **Which phrasings count as reassuring over an untrusted window?** Constraint 16 says the honesty layer *overrides* the model rather than advising it, so a reassuring headline over a blind window is replaced outright. Which words trigger that replacement is a list in `app/analytics/windows.py` and no document fixes it — a list that is too short lets a lie through, and one that is too long rewrites honest text | `C23`, constraint 16 | Harshan | Open |
| Q68 | **Does a constant signal untrust the window it rests on, or only the figure derived from it?** `dpt` is a flat 107.0 on chiller 1 and 112.9 on chiller 2 (`Q8`), so condenser approach cannot be computed. Whether that makes the whole *period* untrustworthy or only the approach figure is unstated, and the two produce very different screens | `C23`, `F16` | Vishnu | Open |
| Q69 | **What fraction of a period must be valid before an efficiency figure may be shown?** Invalid slots are excluded rather than averaged in — *"wrong by two orders of magnitude, not by a margin"* — but no document states a minimum coverage. A fraction chosen here would decide which months get a number and which do not | `E1`, `R10` | Vishnu | Open |
| Q70 | **Do these two chillers' nameplates carry the 0.65–0.85 design band?** The band is quoted as a design figure, but no document confirms it belongs to *these* machines rather than to water-cooled centrifugals in general. Comparing a plant against another machine's nameplate is how a healthy unit gets reported as failing | `E1`, `Q21` | Vishnu | Open |
| Q71 | **What orders a working queue?** `U6` and `U7` show cases to a person and no document says in what order. Oldest first in `app/services/queues.py`, because age is the one property nobody disputes — but severity would be defensible too, and six of seven classes have no agreed severity (`Q49`) | `U6`, `U7` | Harshan | Open |
| Q72 | **Does a condition-cleared case need a named human to confirm it?** `RC9` marks a case stale when the condition is no longer detected, and explicitly says that is **not** proof the repair worked. Whether it may then leave the queue without anybody looking is unstated — and `V1` found a label disappearing while the residual got *worse* | `RC9`, `U7`, `V1` | Vishnu | Open |
| Q73 | **Which residual column belongs to which of the six named models?** `CONTEXT.md` §6 names DP, SP, DT, Power, Comp Amps and Cond Leaving, but no document maps those names onto the residual columns. `A1` currently infers the mapping and says it is inferred | `A1`, `F15` | Vishnu | Open |
| Q74 | **What is the policy versioning scheme, and what advances it?** `U8` stamps a policy version on every decision so an audit row can be read years later. Neither the format nor the trigger is defined anywhere | `U8`, `G6` | Harshan | Open |
| Q75 | **Who is a policy change attributable to, once identity is real?** Today `is_production_identity` is hard-wired `False` (`Q41`), so a policy change is attributable to a demonstration persona. That is honest now and unusable later | `U8`, `Q41` | Harshan | Open |
| Q76 | **How is a policy change tested before it goes live?** `G8` policy simulation is Phase 3, deliberately. Until it exists a rule change is applied without any way to try it first, and `U8` says so rather than being silent about it | `U8`, `G8` | Harshan | Open |

## To reconcile

The Thermynx FDD initiative holds **57 open questions** at
`docs/plan-v4.9.1/fdd/04-sme/questions.md`, none of them answered. That agenda has
been **read** and the findings that change this programme are folded in — see
`CONTEXT.md` §10a and questions Q21–Q27. What has **not** been done is a
question-by-question reconciliation.

Their §1 is nine safety-critical questions about whether the system may *eliminate*
a candidate cause on unreviewed judgement, and it deserves the SME hour on its own
merits. Two of them bear directly on our `F7`: whether a wide approach eliminates
the cooling tower on the commonest fault class, and whether measured separations of
about 4 °C are strong enough to eliminate on or must stay priors. Our answer today
is the conservative one — keep the combined labels — and their reasoning supports it.

**Owner:** Harshan. **Blocks:** nothing today. **Do before the SME session**, not
after: their §3 overlaps our Q3–Q13, and asking Vishnu the same threshold twice
wastes the one review that matters.

## Closed

_None yet._
