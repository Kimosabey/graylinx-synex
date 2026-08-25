# One week on Synex — building to the plan

**The scope boundary, first, because it is the whole point of this file.** Build what
`mvp/MVP-SCOPE.md` says, in the sequence it gives, and nothing else. Not a better idea, not a
tidier architecture, not a feature that seems obviously missing. If something looks wrong with
the plan, say so — and keep building the plan while the answer comes back.

That is not bureaucracy. The scope is 94 of 147 registered features, chosen to close **one**
complete loop end to end: fault detected → case opens → explained with evidence → narrowed to a
root cause → work order raised → work verified. Anything outside that loop makes the loop later,
and the loop is the demonstration.

---

## Where the plan actually stands

`mvp/MVP-SCOPE.md` §Sequencing has ten stages. Read that table before this one — but read this
one before you start, because the stage table says what to build and does not say what already
exists.

| Stage | What it is | State |
|---|---|---|
| 0 | Data in, tags normalised, asset hierarchy | **done** — the MySQL clone |
| 1 | Six models, residuals, validity flags | **not ours to build** — see below |
| 2 | Gates, persistence, isolation path, `NO_DIAGNOSIS` | built — `app/analytics/gates.py` |
| 3 | Control Plane: identity, scope, risk, gateway, audit | built — `app/services/control_plane.py`, `app/tools/gateway.py` |
| 4 | Copilot read path: ask, context, route, evidence, explain | built — `app/api/v1/ask.py`, `app/agents/` |
| 5 | Work orders: create, evidence, priority, findings | built — `app/services/work_orders.py` |
| 6 | Verification and the close gate | built — `app/analytics/verification.py`; `PASS` unreachable pending **Q15** |
| 7 | Reports and knowledge retrieval | built — retrieval only reached the answer path on 19 Aug |
| 8 | Conversation shell: threads, turn memory, front door | built — `app/agents/conversation.py` |
| 9 | Case resolution: state machine, checklists, escalation | machinery built — **content blocked on SME** |

**Stage 1 is not ours and that matters.** The trained detection model is Shiva's. Synex reads
per-slot verdicts out of `gla_model_residuals_wc` and **never re-detects** — where that model has
a verdict it is higher-confidence than any heuristic we would write. If you find yourself about
to compute a residual, stop: you are rebuilding somebody else's model.

**So "from scratch" does not mean deleting working code.** It means you build the remaining
named work yourself, in the planned order, rather than inheriting a finished system to maintain.
The list of what remains is at the bottom of this file, and every item on it is named by the
plan.

---

## Day 1 — see it run, then read the two rules

**Morning.** Work through `01-running-synex.md` until all three terminals are up and
`box_reachable: True`. Do not skip the tunnel keeper. Reading about this system before watching
it work is much harder than the other way round.

Then ask the Copilot, in this order:

| Ask | What to notice |
|---|---|
| *what equipment do we have?* | the badge reads **Language model · wrote the wording** |
| *how is chiller 2 doing?* | it names what is **unexamined**, not only what is wrong |
| *what is the capital of France?* | refused — read the refusal, it is not a fob-off |
| *can you change the chilled water setpoint?* | the boundary, stated as a boundary |
| *which chiller uses more power?* | this one writes SQL. Read the statement it shows you |
| *why was chiller 1 flagged on 9 April?* | the evidence path, end to end |

**Afternoon.** `CONTEXT.md` §5 (the separation law) and §10 (the inherited constraints), then
`CLAUDE.md` end to end. Both are short. Every rule in them has an incident behind it.

**No code today.**

---

## Day 2 — the plan, then the AI path

**Morning — the plan.** `mvp/MVP-SCOPE.md` in full: the 15 acceptance test cases, the acceptance
criteria, the sequencing table. Then `mvp/FEATURE-REGISTER.md` as a lookup — it is the single
source of truth for what a feature ID means, and chapters reference IDs rather than restating
them.

By lunch you should be able to say which stage any piece of work belongs to. If a task does not
map to a stage, that is the signal to ask rather than to start.

**Afternoon — the AI path.** `02-the-copilot-end-to-end.md`, then follow it in the source with
the app open beside you: `router.py` → `answer.py` → `compose.py` → `postcheck.py` →
`critique.py`.

Ask a question and open the **Inspector** panel under the answer. It shows the route, the layer
that decided it, the stages and the audits. Cheapest debugging tool here and most people never
open it.

---

## Day 3 — landmines and the gates

**Morning.** `03-known-issues-and-landmines.md`, slowly. Then do this, because it is the defect
this codebase produces most:

> Pick any capability in `app/agents/`. Grep for its consumers. Convince yourself a **request**
> reaches it — not a test, not an ingest job, a request.

Six capabilities failed that test in one day. Every one had passing tests.

**Afternoon.** `04-testing-and-evaluation.md`. Run all four offline gates, then
`scripts/eval_copilot.py --one-persona` and watch it — about four minutes, and it teaches you the
shape of every answer state.

---

## Day 4 — your first build, from the plan

Take **one item from the remaining work below**, in the order listed. They are ordered by what
the plan needs next, not by what is interesting.

Build it the way everything else here is built:

1. The domain rule goes in `app/domain/` — which imports nothing.
2. Anything touching a database goes in `app/db/`.
3. Anything reaching a model goes through a **role**, never a model name.
4. A test that would have caught the bug, written before the fix.
5. All four gates before you commit.

Then write the `HANDOFF.md` entry yourself. Read a few existing ones first — they explain *why*,
not *what*, and the commit messages do the same. Six months from now the diff is still readable
and the reason is not.

---

## Day 5 — finish, and hand back

Finish the item. Run the gates. Then do the thing that is easy to skip: **run
`scripts/eval_generated.py --record` and read `eval-flywheel.txt`.** Every line is a question the
product got wrong. That file is the honest list of what your change did not fix.

---

## The remaining work, all of it named by the plan

**Stage 9 — blocked on SME, and larger than everything else combined**

The 19 discriminators are authored and unreviewed, so `askable` returns nothing and every
differential reports `EXHAUSTED` by construction. The checklist library is sample content and
every surface says so. `mvp/ASK-VISHNU.md` is the message; it has been sent. **This is not
engineering and you cannot unblock it by building.**

**Stage 6 — blocked on Q15**

`PASS` is deliberately unreachable until the verification threshold is agreed. Do not pick a
number to make the path testable.

**Buildable now, in this order**

1. **Close the evaluation loop.** `eval-flywheel.txt` accumulates failures and nothing reads it
   back. A script that turns recorded failures into stub cases is small and it is what stops the
   suite ossifying around questions its author thought of. *Stage 4, and it protects every stage.*
2. **Finish a 147-case run.** Nobody has seen all 147 complete — two attempts died to
   infrastructure. Highest clean count is 84. Until one finishes, the number is an unfinished
   measurement.
3. **Retrieval quality.** `app/retrieval/quality.py` has the machinery; nothing measures whether
   a cited passage supports the sentence citing it. *Stage 7.*
4. **Multi-turn evaluation.** Conversation memory is plumbed and unit tested; behaviour over
   several real turns against a live model is not measured. *Stage 8.*
5. **Interview mode.** Three of the four answer modes exist. The fourth — a guided conversation
   when there is nothing usable — does not. *Stage 4.*

**Needs a decision, not code**

6. **A fourth-family grounding judge.** Thermynx uses `llama3.1:8b` so nothing grades its own
   output; we use `phi4` for both the critique and the `text` role. `CONTEXT.md` §4 says four
   models. This needs an entry in `decisions/DECISIONS.md`, not a quiet fifth model.

**Explicitly out of scope, and staying out**

- Anomalies as Thermynx does it — live scanning, an hours window, severity colouring. Each would
  be untrue here. `mvp/INHERITANCE-STATUS.md` under "Deliberately refused" has the reasoning.
- MTTR and repeat-issue rate tiles. Both need closed jobs with timestamps and every job is open.
- The four MVP features named by no stage — `A1`, `U3`, `S1`, `S4`. Two are safety features.
  That gap is **Q17** and it is a question, not a task.

---

## Ask rather than decide

`CLAUDE.md` §6 has the full list. The three most likely to come up:

- **Anything depending on how the equipment actually behaves.** Vishnu's call, not an engineering
  judgement.
- **Naming question N1** — how Synex and Thermynx relate. `CLAUDE.md` lists it open and blocking;
  `CONTEXT.md` §9a and `D-006` read as settled. The documents disagree with themselves. Do not
  silently pick a side.
- **Anything that changes what gets built in the MVP** — which includes anything not on the list
  above.

Everything else: proceed, and note the assumption in your summary.
