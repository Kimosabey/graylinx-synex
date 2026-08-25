# SME review — the one hour we need from Vishnu

**Owner:** Harshan · **Reviewer:** Vishnu · **Status:** not yet held
**Purpose:** close the questions that only a refrigeration engineer can close, in the
order of what a wrong answer costs.

---

## Read this first

This is a **merged** agenda. Two question sets existed: 36 in this repository, and 57
in the Thermynx FDD initiative at `docs/plan-v4.9.1/fdd/04-sme/questions.md`. They
overlapped. Asking the same threshold twice would spend an hour that cannot be bought
back, so the duplicates are resolved here and the reconciliation is recorded in §6.

**The framing that works — and it is theirs, not ours: _break these, not review
these._** We are most confident about §1.1, which is exactly why being wrong there
costs the most.

> **"I do not know" and "it depends" are useful answers.** If a test is not reliable
> we would far rather show two possible causes and let the technician decide than
> eliminate the right one and sound certain about it.

**Why this is the last gate.** The platform does not just list checks. It uses the
answers to **rule causes out**. If one of our tests is wrong, the system eliminates
the *correct* cause — confidently — and nobody re-examines a settled question.
Elimination is irreversible in this flow.

---

## §1 · Irreversible if wrong — spend the hour here

`RC2` `F5` `F7` — these decide whether the platform may eliminate a candidate cause
on judgement nobody qualified has checked.

### 1.1 Is the filter-drier temperature drop really the deciding test?

When suction pressure is far below expected but current is barely up, we read it as a
**starved evaporator** rather than a compressor working too hard. To tell *why* it is
starved we ask for the temperature drop across the filter-drier. The reasoning: a
blockage makes refrigerant expand and go cold, so a cold spot means a restriction and
no cold spot means the charge is low.

- Can an **undercharged** circuit also produce a cold spot across the drier?
- Is it **safe to measure while the machine is running**?

**If the answer is no:** the test does not separate the two causes, and we are
eliminating the wrong one. `F7` keeps them as a combined label and the differential
loses its first question.

*This is the one we are most confident about, it is the first question asked on six
fault episodes, and it is the example in the demo.*

> **Answer:**

### 1.2 Can condenser leaving-water temperature separate the two fault families?

Measured averages:

| Fault type | Condenser leaving water |
|---|---|
| Condenser low flow | **34.9 °C** |
| Condenser water side | **34.5 °C** |
| High head, cause unclear | 32.4 °C |
| Power high, unexplained | 31.0 °C |
| Refrigerant side high head | **30.1 °C** |

About a **4 °C gap** between the water-side faults and the refrigerant-side one.

- Is that a **real physical difference** we can rely on, or a coincidence of when
  those faults happened to occur?

**If it is real:** whole cause groups can be ruled out from data already held, with
nobody sent to measure anything. **If not:** it stays a *prior* — it may reorder the
questions and nothing else.

> **Answer:**

### 1.3 Does an unusually equal split between two compressors mean a compressor fault?

Each chiller has two compressors metered separately. Normally the second draws about
**1.17×** the first.

| Fault type | Ratio |
|---|---|
| Compressor inefficiency | **1.03** — unusually equal |
| Everything else | 1.09 – 1.20 |

- Does *unusually equal* point at a compressor fault, or is it normal staging,
  lead/lag rotation or unloading?

**If it is real:** it replaces a three-day oil analysis with a reading already held.

> **Answer:**

### 1.4 Are the measured separations strong enough to eliminate on?

`F7` currently keeps two pairs combined — undercharge with restriction, overcharge
with non-condensables — because *automatic elimination on unreviewed thresholds is
more dangerous than the ambiguity it removes*. The separations in 1.2 and 1.3 were
measured and deliberately withheld.

- Do they become **eliminators**, or stay **priors** that only reorder questions?

> **Answer:**

### 1.4a How the narrowing works — so you can judge one line at a time

Four differentials, 19 candidate causes, 19 discriminating questions. Each answer
does one of three things:

| Effect | Meaning | Reversible |
|---|---|---|
| `confirm` | evidence **for** this cause | — |
| `eliminate` | rules it **out** | **no** |
| `keep` | consistent, decides nothing | — |

Three properties are already built in, and we would like you to check the reasoning
rather than the code:

- **A confirmation never eliminates its siblings.** A fouled condenser on a machine
  that is also low on flow is two real causes, and collapsing to the first
  confirmation is how the second gets missed.
- **"Can't tell" does nothing.** Every question carries it explicitly, with no
  effect, because otherwise uncertainty would quietly eliminate something.
- **Every elimination records the check and the answer that caused it** — so *"why
  did nobody look at the tower?"* has a better answer than *"the software decided"*.

**Thirty-one causes have already been ruled out on the live queue**, every one by a
discriminator nobody qualified has reviewed. That is the whole reason for this hour.

> **Answer / corrections, one line at a time:**

### 1.4b The three lines that carry most of the risk

If the hour runs short, answer these three and stop. Roughly forty-one
eliminations exist across the four differentials; these three remove the most
candidates per answer, and two of them sit on the questions most likely to be
asked in production.

**A · The commonest class, on its highest-power question**

`HIGH_HEAD_AMBIGUOUS` is **430 of 674 fault slots — 64 %**, present on 12 of 12
fault days. Its first question is the condenser approach temperature against
design, and answering **wider** eliminates the cooling tower, reasoned as *"the
tower sets the water temperature, not the approach across it."*

- Can a tower fault raising entering-water temperature **coexist** with a widened
  approach? If it can, this is `keep`, not `eliminate` — and it is the elimination
  most likely to actually fire, because it is the lead question on two thirds of
  our faults.

> **Answer:**

**B · One answer that removes three of five causes**

`CONDENSER_WATER_SIDE_UNSPECIFIED` asks for condenser water flow against design.
Answering **at design** eliminates low flow, a blocked strainer *and* the pump in
one go, reasoned as *"adequate flow with a failing condenser points at the
surface, not the hydraulics."*

Two things make this the sharpest line in the library. It removes 60 % of the
differential on a single answer — and **the measurement does not come from
telemetry**. Condenser flow has never recorded a non-zero value on the reference
plant, so the checklist already says to *expect to measure it manually rather
than read it*.

- Is the three-way elimination correct?
- Is a manual condenser-flow measurement realistic on your plants? **If it is
  not, what replaces it as the lead question?** This is the same instrumentation
  gap as `Q1` in §2 — here it decides a differential rather than a model.

> **Answer:**

**C · Four causes closed by one judgement, not a measurement**

`POWER_HIGH_UNEXPLAINED` asks whether actual load is higher than the current
curve explains. Answering **genuinely higher** eliminates **all four** electrical
causes — phase imbalance, the motor, the drive and a loose connection —
reasoned as *"if the load explains the current there is no electrical fault to
chase, and it is the one question an operator can answer from the panel."*

The reasoning holds only if an operator can reliably tell *the machine is working
harder* from a panel. That is a judgement rather than a measurement, and it would
be recorded as **estimated** — which is exactly the case §4.3 asks about in the
general. Here it is concrete: one estimated answer closes the entire electrical
branch, and the plant streams no phase currents, no voltages and no drive
registers, so none of the four can be checked against data afterwards.

- Should this answer eliminate, or only **deprioritise** the electrical branch?
- If an estimate should not settle it, what measurement should?

> **Answer:**

### 1.5 Are any causes missing from the candidate lists?

An absent cause can never be found, which is worse than a wrong elimination.

> **Answer:**

### 1.6 Which faults are answered by stopping the machine, not by raising a work order?

The taxonomy we inherited has **no safety impact class** — every escalation route ends
in a work order, so there was no way to say *stop now*. `S6` exists to fix that and
needs its trigger list.

> **Answer:**

### 1.7 Is a drafted-but-unreviewed interim holding action worse than none?

When a fault is found and the repair must wait, the machine keeps running. Nine short
instructions for running it safely in the meantime were drafted and **deliberately
never switched on**, because telling somebody it is safe to keep running a machine is
the most dangerous thing this system could say. The cost of that choice: a deferred
critical fault runs with nothing protecting it.

- Would an AI-drafted holding action, **approved once per class by you**, be
  acceptable as library content?

> **Answer:**

---

### 1.8 When five faults appear on one machine, how many problems is that?

**This is the newest question and possibly the easiest one to answer.** It comes from
counting our own data rather than from a document, and the proposal we have written is
**our inference, reviewed by nobody.**

**What the data shows.** In the measured window, twelve equipment-days carried a fault.
Naming a case for each *(machine, day, fault label)* gives **thirty-nine**. And on
**15 April, chiller 1 carried five labels at the same time:**

| Label |
|---|
| `CONDENSER_LOW_FLOW` — the only class rated critical |
| `HIGH_HEAD_AMBIGUOUS` |
| `POWER_HIGH_UNEXPLAINED` |
| `REFRIGERANT_SIDE_HIGH_HEAD` |
| `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION` |

17 April is another five, and **ten of chiller 1's twelve fault days carry more than one
label.**

**Why it matters more than it sounds.** If each label opens its own case and each case
raises its own work order, that is five work orders, five visits and five checklist runs.
The technician fixes the real problem on visit one, so visits two to five find nothing and
close as *no fault found* — which teaches the crew that the system cries wolf.

**Our proposal, which we would like you to break:** where several labels share a plausible
common cause, group them into **one** investigation with **one** work order, and show the
grouping to a human who can split it.

**1.8a Can one cause really produce four of those at once?** Our reasoning is that a
**fouled condenser** raises head pressure, makes the compressor work harder, drops
efficiency and shifts refrigerant-side pressures — so `HIGH_HEAD_AMBIGUOUS`,
`POWER_HIGH_UNEXPLAINED`, `COMPRESSOR_INEFFICIENCY` and `REFRIGERANT_SIDE_HIGH_HEAD` would
be four symptoms of one problem. **Is that right, and are the groups you would draw the
same as ours?**

> **Answer / the groups you would draw:**

**1.8b Which pairs must never be grouped?** The opposite mistake is the dangerous one. If a
fouled condenser and a genuinely low refrigerant charge are both present and we group them,
the second one is hidden — and a missed undercharge costs a compressor, where a duplicate
visit costs a morning. **Which label pairs are independent enough that they must always stay
separate cases, even when they appear together?**

> **Answer:**

**1.8c Two of the five contradict each other. What does that mean on the plant?**
`CONDENSER_LOW_FLOW` is one of only two classes whose signature has a **positive**
discharge-pressure residual, which is how the water side gets implicated.
`HIGH_HEAD_AMBIGUOUS` has a **negative** one, and that negative value is precisely the
evidence used to argue the water side is *not* involved. Both were present on the same
machine on the same day.

- Is that **two real faults** at different times of day, **one fault in transition**, or a
  sign the **data is not trustworthy** in that window?
- And which of the three should the platform assume when it cannot tell?

> **Answer:**

**1.8d If an instrument is faulty, can a real fault hide behind it?** Our plan is that when
an instrument fault appears in a group, the instrument case leads and the others wait for
the sensor to be fixed. **Is that safe, or can a genuine fault sit underneath a bad sensor
and be missed while we wait?**

> **Answer:**

**1.8e Is five labels on one machine-day normal?** Or does it tell you the detector is too
sensitive, and the real number of problems on 15 April was one?

> **Answer:**

---

## §1a · Five conflicts the transcription found — these are new, and two are costly

Added 2026-08-17. The 124-item library and all four differentials were transcribed verbatim
into code and machine-verified field by field, twice, against both source documents. The
transcription itself found five contradictions. **Nothing was corrected** — a wrong item a
refrigeration engineer can see is far better than a corrected one they cannot, because this
review is the gate.

**1 · The two documents disagree about which question is asked first, on two classes.**
This is the expensive one.

For `POWER_HIGH_UNEXPLAINED`, `06-differentials` marks *"actual load vs the current curve"*
as **asked first**, and says one free panel reading eliminates four of five causes. But
`05-checklist-library` lists it as check **4**, behind two technician checks including a
megger test. Following the checklist order **sends a technician out before the free reading
is taken.** Constraint 39 says the next question is the one that could move the most live
candidates — these two documents answer that differently.

The same conflict on `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION`: `05` lists the sight glass
first and the filter-drier temperature drop second, `06` makes the filter-drier ΔT Q1 — and
`05`'s own rationale under check 2 calls it *"the single test that separates the two causes"*.

> Which document governs the order, and does the free reading come first?

**2 · Three determinate classes have no blocking item and no discriminator at all.**
`REFRIGERANT_SIDE_HIGH_HEAD`, `COMPRESSOR_INEFFICIENCY` and `CONDENSER_LOW_FLOW` carry **36
of the 86 Part 1 items between them and not one blocking check** — so a case can be
root-caused and closed on any of them **with no measured answer at all**. `CONTEXT.md` §10b
names this for the first class (`Q37`); the transcription found it holds for three.

> Is that right, or should each carry at least one blocking measurement?

**3 · `[SETTLES IT]` is described as singular and applied to twelve items.**
The preamble says *"the item marked `[SETTLES IT]` is the one we ask first"*. Four classes
mark **three items each**.

> Do all three settle it, or is one of them the discriminator?

**4 · The pack's severities are not our severities, and one is not a severity at all.**
The review pack states high ×4, critical ×1, **warning ×2**. `app/domain/faults.py` records
six of seven as unrated against `Q49`, with `CONDENSER_LOW_FLOW` the only sourced critical.
And *warning* is an alert level rather than a severity. Carried as a string and deliberately
not mapped — choosing either reading would invent a rating in the one place `F17` says must
be authoritative.

**5 · The `can't tell` option was absent from some questions and was added.**
Constraint 30 requires every discriminating question to carry an explicit *can't tell* with
empty effects, or uncertainty silently eliminates something. Where the source omitted one it
was **added with no effects**, and that addition is reported here rather than buried.

---

## §2 · The data that does not exist — not your questions to answer, but yours to interpret

Four defects. Three of our checks ask for numbers that are not there. These need the
site and instrumentation team, but only you can say what to do without them.

| # | What we found | What it costs |
|---|---|---|
| 2.1 | **`cond_flow` has never had a reading** — not "died in May", zero non-zero values ever | This is the highest-leverage single measurement. It feeds four of the six models. Without it the entire efficiency and high-head branch returns `NO_DIAGNOSIS` |
| 2.2 | **`dpt` never changes** — a constant 107.0 on chiller 1, 112.9 on chiller 2 | **Condenser approach temperature cannot be computed at all.** That is the fouling threshold *and* a question inside a differential. Is that tag a setpoint or design value rather than a measurement? |
| 2.3 | **Condenser ΔT is negative every month on chiller 1** (−3.0 to −3.4) | A condenser rejects heat, so leaving water must be warmer than entering. Those two columns look **swapped or mislabelled** — and no residual on that machine can be trusted until it is resolved |
| 2.4 | **Both chilled-water flow transmitters have read near zero since May** while ΔT and power stayed normal | Physically impossible. It quietly invalidated two months of efficiency figures and blinded the fault model |

**2.5 If condenser flow cannot be measured, what leads instead?** A manual
measurement, a proxy, or do we accept `NO_DIAGNOSIS` on that branch and say so
plainly?

> **Answer:**

### 2.6 What you will and will not see in the demonstration, and why

Not a question — a disclosure, so that nothing in the demonstration surprises you.

Our copy of the plant data runs to 2026-08-05, but the **measured** data stops at
**2026-06-23**. The six weeks after that are a simulation. Comparing the two windows
column by column, 31 of 32 signals are a continuation of something the plant really
measures. One is not: `cond_flow` has **zero** readings in 31,884 real slots and
**3,354 fabricated ones** in the simulated window, reaching 893.7.

So the demonstration runs on the **measured** window, and the high-head branch will
return `NO_DIAGNOSIS` where condenser flow is needed. **That is deliberate, and it is
the honest result** — we would rather show you the platform refusing than show it
confident on a measurement your plants cannot take.

If you would rather see the branch resolve, that needs an answer to 2.5 first, not a
different window.

> **Anything you want shown differently:**

---

## §3 · Thresholds — the numbers we refuse to invent

Every one of these is unresolved in the documents, and carries no agreed number. We will
not guess them.

| # | Question | Our proposed starting point | If it is wrong |
|---|---|---|---|
| 3.1 | Minimum load for a valid diagnosis | confirm per machine type | gates pass on data the model cannot judge |
| 3.2 | Settling time after a start or stage change | — | residuals trusted during a transient |
| 3.3 | Settling time after a leaving-water setpoint change | — | same |
| 3.4 | Persistence window — one value, or per fault class? | 20–30 minutes as a common default | transients become faults, or faults are missed |
| 3.5 | Healthy chilled-water ΔT band per machine | design ΔT from the machine data sheet | `F14` fires wrongly or never |
| 3.6 | Condenser approach thresholds for fouling | per OEM data sheet | **blocked** — see 2.2, the input does not exist |
| 3.7 | Time constants separating low condenser flow from fouling | low flow spiky/intermittent; fouling steady drift over weeks | the two condenser-side causes cannot be told apart |
| 3.8 | Volatility threshold defining expansion-valve hunting | set from observed data | hunting missed or over-reported |
| 3.9 | Sensor drift thresholds per sensor type | per sensor class | a crew is sent for a drifting sensor |
| 3.10 | Is compressor lead/lag reliably available from the BMS? | — | five of six models shift at every stage change |

> **Answers:**

---

## §4 · The checklist library — 124 items, one review pass

`RC2` `RC3` — the library is **curated content, never model output**, because a
checklist directs physical work on pressurised equipment and a plausible-but-wrong
item is worse than no item. That is what makes this review possible at all.

**What exists:** 124 curated items across 11 fault classes, plus a 7-item generic
fallback. Split **57 RCA · 37 corrective · 30 preventive**, of which **24 are
blocking**. Four decision trees. Role tags: technician 49 · supervisor 38 ·
operator 29 · maintenance 7 · vendor 1.

**One review pass has ever been run, over one class.** It found an oil analysis —
acid number, moisture, metals — being shown to whoever opened a compressor case. That
is a lab task, and it produced the rule that governs the whole role model: *an
operator must never be blocked by a check they cannot perform.*

### 4.1 Is the maintenance/technician split drawn in the right place for this crew?

Only **7 of 124** items are tagged `maintenance`, yet brushing condenser tubes,
cleaning strainers, venting a loop and servicing a tower are in-house mechanical work
and several of those are tagged `technician`. Untagged items default to `technician`
deliberately — over-escalating wastes a callout, under-escalating puts an unqualified
person on a pressurised circuit.

- Are any obviously in the wrong bucket?

> **Answer:**

### 4.2 How does a technician say "I found nothing" versus "I found something"?

When every check comes back negative the platform must stop and **not** produce a root
cause, because a conclusion built on "nothing wrong anywhere" is misleading. Detecting
that from wording is crude. It currently reads this as a **negative**:

> *"Measured 6 °C drop across the drier — **clear** cold spot"*

…because of the word *clear*. That is a strong positive finding and we would be
throwing it away.

- What words do technicians actually use for **"nothing here"**?
- Which words look negative but are really **positive findings**?

> **Answer:**

### 4.3 Does an estimate settle a blocking check, or only a measurement?

Our position is **measured only**. An untagged answer once defaulted to *estimated*
and opened a blocking gate; separately, six "N/A" presses opened one with no evidence
behind it. `RC10` records three answers rather than two — measured, estimated, and
cannot-check — and only the first satisfies a blocking item.

> **Answer:**

### 4.3a Does `REFRIGERANT_SIDE_HIGH_HEAD` need a differential?

It names a *region* rather than a mechanism, probes five mechanisms, and has **no
blocking items and no differential** — so a case can conclude there having gathered
no evidence at all. Should it get one?

> **Answer:**

### 4.4 Should every fault class have a verification step?

Three of seven equipment classes have none. **This question has no counterpart in the
Thermynx set, because that implementation has no verification layer at all** — and
proving the repair worked is the promise this MVP is built on.

- What proves a **condenser cleaning** worked? Our proposal: `rPwr`, `rDP` and `rCWL`
  back inside band, held several days across a representative load range.
- What verifies **compressor inefficiency** and **power high unexplained**?

> **Answer:**

### 4.5 Who approves a recurring obligation?

Thirty preventive items exist and none of them creates a schedule — prevention is
recorded and never happens. `RC11` makes a preventive item a real commitment, which
means somebody signs for future work.

> **Answer:**

### 4.6 Is there a plant document to reconcile against?

An OEM manual or O&M schedule the 124 items could be **cross-checked against** rather
than reviewed from scratch. This could turn an hour of review into a much shorter
cross-check.

> **Answer:**

---

## §5 · Not for Vishnu — the decision Harshan owes

| # | Question | Blocks |
|---|---|---|
| 5.1 | **Is the MVP cut agreed?** 94 of 147 features | `mvp/BACKLOG.md` and all build sequencing |
| 5.2 | How do Synex and Thermynx relate? | every line of positioning copy |
| 5.3 | Which of the three inherited gaps do we take on — no holding action, no retraction mechanism, duplicated checklist work under event grouping? | `F9`, `V7`, deferred-fault risk |
| 5.4 | Four MVP features are named by no build stage, two of them safety | the stage-9 estimate |
| 5.5 | Three role systems — user personas, capability roles, agent skills. Which governs which decision? | `C11`, `C20`, `RC3` |

---

## §6 · Reconciliation — what was merged, and what is uniquely ours

The two sets overlapped substantially. Resolved as follows:

| Ours | Theirs | Resolution |
|---|---|---|
| Q1 condenser flow trustworthy | Q-K4, data defect | **merged** → §2.1, §2.5 |
| Q2 evaporator flow derivation | Q-A11 | **merged** → §2.4 |
| Q8 condenser approach thresholds | data defect `dpt` | **merged** → 3.6, blocked on 2.2 |
| Q10, Q11 keep the pairs combined | Q-K1, Q-K2 | **merged** → §1.1, §1.4 |
| Q20 missing fault classes | Q-K6 | **merged** → §1.5 |
| Q22 stop-the-machine faults | Q-T3 | **merged** → §1.6 |
| Q23 estimated settles a gate | Q-C4 | **merged** → §4.3 |
| Q33 words for "nothing found" | their question 4 | **merged** → §4.2 |
| Q34 maintenance/technician split | Q-N1 | **merged** → §4.1 |
| Q35 who approves a PM obligation | Q-N2 | **merged** → §4.5 |
| Q36 reconcile against a plant document | Q-N5 | **merged** → §4.6 |
| — | Q-B4 interim holding actions | **adopted** → §1.7 |
| **Q15 what proves a repair worked** | *no counterpart* | **uniquely ours** → §4.4 |

**Theirs that stay theirs:** the platform and data questions in their §2 — residual
flag semantics, model refit ownership, whether the classifier is input-gated, the
corrupted subsystem join. Those need their platform team, not this review. Ours
`Q24`–`Q28` are the equivalents on our side.

**The one that matters most for this programme** is §4.4. Everything else sharpens a
diagnosis; that one is the difference between a platform that says a repair worked and
one that proves it.

---

## How to answer

Whatever is easiest — a reply in your own words, one line per question, or writing
under the `> Answer:` lines above, or a call where we write it down for you.

Every mapping you correct is **one line** in the library. It was built that way
deliberately, so a correction never touches the machinery.

---

## When answers arrive

1. Record each in `decisions/DECISIONS.md` in **his words**, with the alternative that
   was rejected — a decision without its rejected alternative cannot be revisited.
2. Move the closed rows in `decisions/OPEN-QUESTIONS.md` to the Closed section. Do not
   delete them.
3. Update the affected register rows and `CONTEXT.md`.
4. Re-run `python scripts/verify.py` and `python scripts/sync_mvp_html.py`.
5. Append a row to `HANDOFF.md` under Recent changes.

---

## Added 2026-08-18 — content approved on a persona's authority, awaiting Vishnu

**This section did not exist when the agenda above was written, and it is now the most
time-critical item in it.** The retrieval corpus went live on 2026-08-18. Search returns only
approved passages, so an unapproved corpus is an invisible one — and to unblock the build
Harshan delegated the approval decision to the acting personas rather than hold it for this
hour. **55 documents were approved by a Reliability Engineer and Supervisor acting in persona.
None of them was read by a refrigeration engineer.**

Every one of those approvals is marked **provisional**, and the words *"approved pending SME
validation"* are printed inside the citation itself — so a passage that reaches an answer says
on its face that no engineer stood behind it. `synex_chunk_approval_event` holds all 55 acts
with the actor and the stated basis, and it survives revocation: withdrawing an approval leaves
the event, so this review can find every one, read what was claimed for it, and undo it.

### What was approved, and the reasoning offered

| Content | Passages | Reasoning the persona recorded |
|---|---|---|
| 51 product & architecture chapters | 242 | Describe how the platform works. No field instruction, so no path to directing physical work. |
| Water-cooled chiller FDD specification | (in the above) | Same — a specification, not an instruction. |
| 4 differentials — candidate causes and discriminating questions | 27 | A differential says what to *consider* and what to *ask*. Wrong content yields a hypothesis that evidence then eliminates; it cannot put a spanner on a pressurised circuit. Constraint 26 — the language model selects and contextualises library content — is exactly this use. |

### What was deliberately withheld

| Content | Passages | Why it was not approved |
|---|---|---|
| 12 checklist library documents | 48 | These contain field instructions directing physical work on pressurised refrigerant equipment. Inherited constraint 1 exists because an unreviewed procedure once reached a technician. No acting-persona approval substitutes for a refrigeration engineer here. |
| 9 drafted holding actions | not indexed at all | They sit behind **two** gates — `sme_reviewed` and `switched_on` — and a chunk row has only one. Indexing them would let a single approval open a policy gate that a review deliberately does not clear (constraint 10). |

### What we need from you, in priority order

1. **The 48 withheld checklist passages.** These are the ones that direct physical work, and
   they are unreachable until you approve them. Read them as instructions you would hand a
   technician. Approve, amend or reject each.
2. **Ratify or revoke the 27 differential passages.** The persona's argument — that a candidate
   cause and a discriminating question cannot themselves cause harm — is the one judgement in
   this whole set that a non-engineer should not have made alone. If you disagree, it revokes
   in one command and the trail records that it was withdrawn.
3. **The 242 chapter passages** need only a glance. If our own written documentation is wrong
   about the equipment, that is worth knowing, but nothing there instructs anyone to do anything.

To withdraw anything:

```
cd backend
python ../scripts/ingest_corpus.py --revoke "<document>" --by "Vishnu" --reason "<why>"
```

### Two fault classes have no evaluation coverage

Separately, and worth a minute of the same hour: the plant's measured window holds **39 detected
episodes across 7 fault labels**, and the golden evaluation set covers **5 of the 7**.
**`COMPRESSOR_INEFFICIENCY` (4 episodes) and `CONDENSER_WATER_SIDE_UNSPECIFIED` (1 episode) have
no golden case at all** — so nothing asserts what a correct answer for them looks like. We need
one worked example of each from you: what the evidence should lead a reader to, and what it
should *not* be allowed to conclude.

---
## Added 2026-08-18 — the 48 withheld passages, triaged for your hour

**What this is.** I read all 48 and sorted them by what a wrong item would *cost*. I have
approved none of them: I am not a refrigeration engineer, and inherited constraint 1 exists
because an unreviewed procedure once reached a technician. This is preparation, not a review.

**A mechanism problem to decide first.** `set_approval` grants per **document**, and each of the
12 fault classes holds all three stages in one document. So there is currently no way to approve
a class's harmless scheduling items without also making its corrective actions retrievable. That
is `Q94` — *is approval per passage, or per document and version?* Until it is answered, approval
is all-or-nothing per fault class.

### The structure

12 fault classes × 3 stages, plus 12 class headers = 48 passages.

| Stage | Passages | What a wrong item costs |
|---|---|---|
| Class header | 12 | Nothing. Label, severity, routing and provenance — no instruction. |
| Preventive actions | 12 | Nothing physical. Scheduling and trending only. |
| Root cause analysis | 12 | Mostly a wasted measurement — but see the oil-sampling note. |
| **Corrective actions** | **12** | **A person acting on a pressurised refrigerant circuit.** This is the stage that needs you. |

### Read these first — every corrective action, in full

These 12 passages carry the whole of the physical risk. Everything else can wait.


**Compressor inefficiency**

- Take an oil sample for analysis; change oil and filter if out of spec — *technician* · not blocking
- Inspect valve plates and unloader mechanism — *technician* · not blocking
- Vibration survey to confirm mechanical condition — *technician* · not blocking
- If wear is confirmed, plan a compressor overhaul with the OEM — *vendor* · not blocking


**Condenser low flow**

- Restore condenser flow — open valves, clean the strainer, vent trapped air — *maintenance* · not blocking
- Verify pump performance against its curve — *technician* · not blocking
- Confirm head pressure and current return to expected after flow is restored — *operator* · not blocking


**Condenser water side — cause unspecified**

- Clean strainers and restore design flow — *maintenance* · not blocking
- Brush-clean condenser tubes if fouling is confirmed — *maintenance* · not blocking
- Service the cooling tower — fill, distribution, fan, basin — *maintenance* · not blocking
- Confirm approach temperature returns to design after the fix — *operator* · not blocking


**Contradictory readings — measurement fault**

- Recalibrate or replace the faulty transmitter — *technician* · not blocking
- If it is a tag/comms fault, restore the point mapping in the BMS — *technician* · not blocking
- Re-verify the derived metric (kW/TR) returns to a plausible band after the fix — *operator* · not blocking
- Mark the affected date range so efficiency and FDD outputs from it are not trusted — *supervisor* · not blocking


**Fault model cannot diagnose this unit**

- Fix the upstream data quality issue before anything else — *technician* · not blocking
- Only then request a model refit from the platform team, with the window stated — *supervisor* · not blocking
- Flag that FDD verdicts for this unit are unreliable until diagnosability recovers — *supervisor* · not blocking


**High head pressure — cause not isolated**

- Address whichever cause the checks isolate — flow, fouling, tower, air, or charge — *technician* · not blocking
- Clean condenser tubes if fouling is indicated — *maintenance* · not blocking
- Verify head pressure returns to expected for the ambient and load — *operator* · not blocking


**High head — refrigerant side**

- Recover, weigh and correct the refrigerant charge — *technician* · not blocking
- Repair any leak found before recharging — *technician* · not blocking
- Purge non-condensables if indicated — *technician* · not blocking
- Replace the filter-drier after opening the circuit — *technician* · not blocking


**Implausible efficiency — suspect measurement**

- Fix whichever input is wrong — flow, delta-T, or power — *technician* · not blocking
- Recompute efficiency for the affected period once the input is corrected — *supervisor* · not blocking
- Exclude the bad period from efficiency reporting and benchmarks — *supervisor* · not blocking


**Power draw high — unexplained**

- Correct any voltage or current imbalance found — *technician* · not blocking
- Complete a motor electrical test; act on the result — *technician* · not blocking
- Review and correct VFD configuration if fitted — *technician* · not blocking


**Signal flatlined — suspect sensor**

- Restore the signal — repair wiring, replace sensor, or fix the BMS point — *technician* · not blocking
- Confirm the value tracks plant state again after the fix — *operator* · not blocking


**Starved evaporator — undercharge or restriction**

- If restricted: isolate, recover, replace the filter-drier, evacuate and recharge to spec — *technician* · not blocking
- If undercharged: leak-test the circuit, repair, then weigh in charge to nameplate — *technician* · not blocking
- Verify superheat and subcooling after the fix — *technician* · not blocking
- Re-check the suction-pressure residual on the next run to confirm the fault cleared — *technician* · not blocking


**generic fallback**

- Address the cause identified by inspection — *technician* · not blocking
- Verify the parameter returns to its expected range — *operator* · not blocking


### Three things I could not resolve and you can

1. **Oil sampling appears at two stages.** *"Oil analysis — acid number, moisture, metals"* is a
   root-cause item, and *"Take an oil sample for analysis; change oil and filter if out of spec"*
   is a corrective one. A previous pass over the role tags already found an oil analysis — a lab
   task — being shown to whoever opened a compressor case. Is taking the sample a technician task
   on a running machine, and does it belong at both stages?

2. **The two sources disagree about routing.** Every class says *"flows straight through"* per
   `05-checklist-library-for-review.md`, while `17-role-tags-every-check.md` prints no routing for
   that class at all. The transcription records both rather than picking one, because a missing
   routing is a different fact from an agreeing one. Which source governs?

3. **`Restore condenser flow — open valves, clean the strainer, vent trapped air`** is tagged
   *maintenance · not blocking* on a class whose severity the source writes as **critical**. A
   non-blocking corrective on a critical fault is either right or a tagging slip, and only you
   can say which.


---

## Added 2026-08-18 — the 19 discriminators, and why they outrank everything else here

**Read this before the checklist library.** It is a smaller ask and it unblocks more.

All four differentials — 19 candidate causes and 19 discriminating questions — currently report
`EXHAUSTED` **the moment they start**, with zero askable questions. Not because the questions
ran out, but because `askable` returns only `sme_reviewed=True` questions and none of the 19 is.
So the narrowing flow, which is the whole of `RC12`–`RC14`, cannot run at all.

**Why we did not simply switch them on.** Elimination is irreversible: a discriminator does not
suggest, it *removes a candidate cause permanently*. On the reference queue **31 causes were
eliminated by these same discriminators, none of them read by a refrigeration engineer**. A
retrieved passage is text somebody can disagree with; an elimination is a door that closes. That
asymmetry is why the corpus could be provisionally approved on a persona's authority and this
cannot.

### What we need — 19 yes/no answers

Each question is a **reading or a records check**. None directs anyone to open, isolate, adjust
or vent anything. For each, we need only: *is this a valid discriminator for this fault class?*

**HIGH_HEAD_AMBIGUOUS** — 5 causes, 5 questions

- Q1 How wide is the condenser approach — leaving water vs condensing temperature? *(technician)*
- Q2 Condenser water flow vs design *(technician)*
- Q3 Is the tower making its design cold-water temperature? *(operator)*
- Q4 Is head pressure above saturation for the measured condenser water temperature? *(technician)*
- Q5 Does the charge log show more refrigerant than nameplate? *(supervisor)*

The other three classes — `POWER_HIGH_UNEXPLAINED` (5), `CONDENSER_WATER_SIDE_UNSPECIFIED` (5)
and `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION` (4) — are in
`backend/app/domain/library/differentials.py`, each carrying the file and heading it was
transcribed from.

### The order we would ask you to work in

1. **The 19 discriminators** — unblocks the narrowing flow entirely. Yes/no per question.
2. **The 12 corrective-action sets** — the only content that puts a tool on a pressurised circuit.
3. **`Q3` the load floor** — you said 30%; we need to know *30% of what*, since no rated capacity
   column exists in the snapshot.
4. **Flow as a constant** — you said take it as constant 1. Constant *design* flow normalised, or
   a literal unit value? It changes every efficiency figure from measured to derived.
