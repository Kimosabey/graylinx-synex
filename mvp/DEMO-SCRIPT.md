# The demonstration script

**18 August 2026.** Every equipment id, date and figure below is committed so that nobody
picks a window live. Choosing a machine and a day in front of an audience is how a
demonstration lands on the simulated span, or on the badly-fitted machine when it meant to
show the clean one.

`backend/tests/golden/test_demo_script.py` asserts that every episode named here still
exists in the data with the slot count claimed. If someone re-clones the database and an
episode moves, the build fails rather than the demonstration.

---

## Before the room

| Check | Command | Expected |
|---|---|---|
| Plant reachable, read-only | `curl -s localhost:8001/api/v1/health` | `"status":"ok"`, `"read_only_by_grant":true` |
| Model mode | same | `"model_mode":"live"` on the day; `stub` while rehearsing |
| Box roster | `curl -s localhost:11500/api/tags` | four models listed |
| Front end | open `localhost:3100` | topbar, rail, 39 episodes |

**The box wipes `/home` on restart, so the roster re-pulls in about ten minutes.** Start it
well before the room, not at the door.

**If the box is down, do not cancel.** The turn still completes: the answer is assembled
deterministically from the evidence and the interface says so, in as many words. That is
worth showing on purpose — see step 6.

---

## The walkthrough

### 1 · Open on the fault queue — *"the platform found these; nobody staged them"*

The page opens on **39 detected episodes over 12 equipment-days**, all on measured data.

> The engine's output already existed. We did not stage a fault for this — these are the
> faults the trained models actually emitted on this plant's own readings.

**Do not skip the count.** 39 episodes over 12 equipment-days is a 3.25× inflation, and it
is the problem `RC19` exists for: one plausible repair can raise five work orders.

### 2 · The hero case — **chiller 2 · `REFRIGERANT_SIDE_HIGH_HEAD` · 2026-04-12**

Select it. 30 slots, a determinate class, on the machine whose worst model runs at
**nRMSE 3.77**.

> This is the well-fitted machine, so its residuals can be shown without qualification.

### 3 · The chart — *the single most important idea in the product*

The residual is plotted **against that asset's own healthy band**, not against zero.

> A residual is not zero-centred. Chiller 1's current residual sits at a median of
> **−25.645** when the machine is perfectly healthy. If you compare against zero, ordinary
> running looks like a catastrophe — and a real fault on the other machine looks like
> nothing. Two identical chillers, two different bands. That is why models are fitted per
> asset and never per fleet.

If asked for the sharpest version: **0.0 — the value that looks healthiest — is `HIGH` on
chiller 1 and `NORMAL` on chiller 2.** The naive reading is not imprecise; it is inverted on
one of the two machines.

### 4 · Ask *"Why was chiller 2 flagged on 12 April?"*

Watch the order the frames arrive in: **route → evidence → answer → audits**.

> The evidence arrives before the prose. That ordering is deliberate — the answer is a
> reading of the evidence, not a summary the numbers were fitted to afterwards.

Point at the route line: **`explain · 3 · keywords · no model involved`**. Routing cost
about a millisecond and spent no model call.

### 5 · The badged machine — **chiller 1 · `CONDENSER_LOW_FLOW` · 2026-04-15**

The only `critical` class in the taxonomy, on the day chiller 1 carried **five labels at
once**.

Two things to point at:

- **`poor fit · nRMSE 48.03`** on the current residual. The same model is **eighteen times
  worse** on this machine than on chiller 2, and its residual is out of band in 402 of 412
  high-head readings. The alarm may be an artefact of the fit rather than a fault — and the
  platform says so rather than letting you read it as a finding.
- **`compressor_power_residual: no model is fitted for this signal`** — words, not `0`, and
  not a dash. Five models are fitted per chiller, not the six the design describes, and the
  row is stated rather than omitted.

> Most products would hide the badly-fitted machine. Showing it beside the clean one is the
> product.

### 6 · The refusal — ask about **cooling tower 1**

`NO_DIAGNOSIS`, in its own card, in its own colour, naming the check that stopped it and
what would change the answer.

> Ten of the twelve equipment tables carry telemetry and have no fitted model, no reference
> band and no scored residual. So the honest answer is that nothing can be judged — and on
> this snapshot, refusal is the **most common labelled outcome there is**: 5,309 slots
> against 674 faulted ones. This is what the platform does most. It is deliberately not
> styled like an error, because it is not one.

### 7 · The honesty checks

Six audits under every answer. Then the line worth saying out loud:

> These are deterministic. No model is grading another model's work, because an auditor that
> can be talked round is not an auditor. Every number in that answer was checked against the
> evidence by exact value — if the model had written `−25.6` where the evidence says
> `−25.645`, this would have failed and the answer would have been withheld and replaced.

### 8 · Signal provenance — the closing point

> Condenser flow has **never recorded a non-zero value** on this plant: 0 readings in
> 31,884. It feeds four of the six models. So the whole efficiency and high-head branch is
> `NO_DIAGNOSIS` by design, on day one, and we would rather tell you that than show you a
> number.
>
> Our own database has a simulated window that *invented* condenser flow, up to 893.7. The
> demonstration you just watched refuses to run on it.

---

## Two questions the room will ask

**"Why not just show us the most recent data?"**
Because it is synthetic past **2026-06-23 11:50**, and the simulation fabricated condenser
flow — a signal this site has no instrument for. Marking it *simulated* is not enough: the
problem is not that the numbers are generated, it is that they imply an instrumentation
capability the plant does not have. Reaching past that boundary takes an explicit flag at
every call site.

**"How much of this is the language model?"**
The trained models named the fault. Deterministic gates decided whether anything could be
claimed. A formula will set the priority, and plain software grants permission. The language
model explains — and everything you saw today ran with it switched off.

---

## What to say if something breaks

| If | Say |
|---|---|
| The box is down | *"The prose layer is unavailable, so it has assembled the answer from the evidence and told us it did. That is the degraded mode working."* — then show the audit line that says so |
| MySQL is down | Health reports `degraded` and names the reason; the roster, ceilings and equipment registry still answer |
| An answer looks wrong | Open `/api/v1/episodes/{id}/pack` and read `prompt_data` — it is exactly what the model was handed, verbatim |

## What is deliberately not in this demonstration

The case lifecycle (M2), work orders (M2) and verification (M3). The rail shows them
disabled rather than hidden, because a product that pretends its unbuilt half exists is the
thing this whole approach is arguing against.
