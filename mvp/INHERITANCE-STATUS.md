# What Synex has actually inherited, and what is still open

> **This is a status document, not a description of Thermynx.** The description already exists
> and is better: `docs/20-architecture/03-from-thermynx.md` covers the roles, guardrails and
> playbooks, and `04-thermynx-e2e-reference.md` walks all five features end to end with the
> trust matrix. `CONTEXT.md` §10 is the canonical list of inherited constraints.
>
> What those chapters do not say is which of it is **wired in Synex today**. That is this file,
> and it is the only thing here that is not written down somewhere better.

---

## The correction this file exists because of

On 2026-08-19 the `planner` role was moved off the brain onto `phi4`, on the strength of a
repetition-loop finding read out of Thermynx's `config.py` comments. It was moved back the same
day on Harshan's instruction, and the instruction was right.

**Both architecture chapters already had it correct**, and `04-thermynx-e2e-reference.md` §1
warns about the exact trap in writing:

> *The repository's own architecture-inventory document lists `codestral` for SQL generation and
> `gemma4:12b` for planning; both are retired in the current code, which unconditionally maps
> `sql → tool` (devstral) and `planner/composer → brain` (the 26B model). **Some comments inside
> the code's own config file still list the retired names** — the drift is not only in the
> documentation, it is in stale comments in the code too.*

The lesson is procedural rather than technical: **read this repository's own reference before
reading the source it was derived from.** The chapters were written from a full pass over
Thermynx on 11 and 18 August; a fresh partial pass is worse evidence, not better.

The technical finding stands and is now recorded where it belongs: the brain fails at JSON in a
tight plain-text cap, not at planning. Every JSON-parsing caller sets `json_only`. Measured on
Jarvis afterwards: eight calls, zero blanks.

---

## Wired in Synex

| Capability | Where | Note |
|---|---|---|
| Five router layers + model arbiter | `agents/router.py`, `agents/arbiter.py` | Layer 4 had no caller until 19 Aug |
| ReAct tool loop, devstral choosing | `agents/chooser.py` → `agents/react.py` | `PlannedChooser` is the floor, not a spare |
| NL→SQL | `agents/nl_sql.py` + `analytics/sql_guard.py` | The validator refuses, never repairs |
| Retrieval into the answer | `agents/recall.py` | 269 passages were unreachable until 19 Aug |
| Conversation memory | `agents/conversation.py` | Six exchanges, fenced as a record not a source |
| Postcheck + critique gate + one retry | `agents/postcheck.py`, `agents/critique.py` | phi4 audits, a different family from the writer |
| The analyst pass | `agents/analyst.py` | `domain_analyst` had been in the thinking policy with no caller |
| Planner → parallel specialists | `agents/orchestrate.py` | Bounded at four; a failed read is named |
| Four answer modes | `agents/hypothesise.py` + `agents/answer.py` | Explain · Hypothesise · Interrogate · Interview |
| Escalation, three routes | `agents/escalate.py` | `RC7` had no caller until 19 Aug |
| Machine-day events | `analytics/events.py` | The determinate class leads, never the biggest |

## Not wired, and why

| Capability | Status |
|---|---|
| **The 19 discriminators** | Authored, `sme_reviewed=False` on every one. `askable` returns nothing by construction, so every differential reports `EXHAUSTED`. **This is the single largest gap and it is Vishnu's hour, not engineering.** |
| **The checklist library** | Sample content, and every surface says so. The curated 11 classes are the bigger SME job. |
| **A fourth-family grounding judge** | Thermynx uses `llama3.1:8b` so nothing grades its own output; Synex uses `phi4` for both the critique and the `text` role. `CONTEXT.md` §4 says four models, so this needs a decision rather than an addition. |
| **Vision** | Thermynx has `llama3.2-vision`. Nothing in the Synex MVP needs it. |
| **The eval flywheel, in use** | `scripts/eval_generated.py --record` writes failures to `eval-flywheel.txt`. Nothing yet reads that file back into hand-written cases. |

## Deliberately refused

Three things Thermynx's anomalies surface does that would be untrue here, and
`04-thermynx-e2e-reference.md` §6 independently reaches the same conclusion about the third:

- **A live scan and a "scan now" action.** This database is a snapshot that ends on a fixed
  date. Re-reading it on demand is theatre.
- **An hours window.** Same reason.
- **Severity colouring.** Severity is agreed for one fault class of nine here. Thermynx's own
  status notes record that its severity threshold *"carries no real information — essentially
  every in-window anomaly was measured as the same top severity level"*, so this is not a Synex
  limitation being worked around; it is a known defect not being copied.

Two more, from the work-orders surface:

- **MTTR** and **repeat-issue rate**. Both need closed jobs with timestamps and every job here
  is open. A tile reading `—` looks broken; a tile filled with a guess is worse.

## The finding worth acting on

From `plan-v4.9.1/resolve/00-the-proposed-system.md`, and it is not in either architecture
chapter:

> **The AI's value is inversely proportional to the model's certainty. A product built only for
> [Explain] is a model viewer.**

Four of this plant's fault classes admit in their names that they cannot resolve, and
`HIGH_HEAD_AMBIGUOUS` is both the most common and the least informative. All four answer modes
now exist — but **Hypothesise reaches `EXHAUSTED` immediately**, because no discriminator has
been reviewed. The machinery is done and the content is not, which is why the SME hour outranks
every remaining engineering task on this list.
