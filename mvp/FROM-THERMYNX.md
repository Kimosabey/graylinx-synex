# What Synex takes from Thermynx

> Read with `CONTEXT.md` §10, which lists the inherited constraints and where they came from.
> This is the working list: every idea from the Thermynx implementation that Synex should carry,
> what state each is in here, and what it would take to close the ones still open.
>
> **The rule throughout: copy the mechanism, re-derive every number.** A figure measured on
> Thermynx's plant is not a figure about this one.

---

## 1. The finding that should shape the roadmap

From `plan-v4.9.1/resolve/00-the-proposed-system.md`, and it is the most consequential sentence
in either codebase:

> **The AI's value is inversely proportional to the model's certainty. A product built only for
> [Explain] is a model viewer.**

The plant's own fault model is honest about its limits — four of its classes literally admit
they cannot resolve: *ambiguous*, *undercharge **or** restriction*, *unspecified*,
*unexplained*. On Thermynx's data **two thirds of detected faults are cases where the sensors
genuinely cannot decide**. The same shape holds here: `HIGH_HEAD_AMBIGUOUS` is the
longest-running class on this plant and the least informative.

So the product's value is not in the cases the model already settled. It is in the cases it
could not.

### The four modes, chosen by how much evidence exists

| Mode | When | What the AI contributes | Synex today |
|---|---|---|---|
| **Explain** | a definitive verdict | the meaning and the fix | ✅ built |
| **Hypothesise** | the verdict is ambiguous | **not an answer — the right question** | ⚠ machinery built, Copilot never enters it |
| **Interrogate** | data but no verdict | what it *can* prove, and what it cannot | ⚠ partly: gates report, but as a refusal |
| **Interview** | nothing usable | a guided troubleshooting conversation | ❌ absent |

**This is the single largest gap.** Synex answers in mode 1 and refuses everywhere else. Four
differentials are authored — exactly the four classes the model declares undecidable — and
`investigate` only reports *whether* one exists rather than running it. A `NO_DIAGNOSIS` should
shift mode, not end the turn.

**One design point the data forces**: when grouping co-occurring labels, never pick the biggest.
`HIGH_HEAD_AMBIGUOUS` appears on 12 of 12 fault days with the most slots, so "the biggest" would
title every event with the label that says least. A determinate class present alongside it leads.

---

## 2. The roster, and the division of labour

Settled in Thermynx's v4 roster and restated by Harshan for Synex on 19 Aug 2026.

| Model | Roles | Job | Synex |
|---|---|---|---|
| `gemma4:26b-a4b-it-qat` | brain · planner · composer | plans, reasons, writes the prose | ✅ |
| `devstral` | tool · sql | executes: the ReAct loop and NL→SQL | ⚠ loop wired 19 Aug; SQL still unwired |
| `phi4` | auditor · text · rag | audits — a different family, so it never grades its own output | ✅ |
| `nomic-embed-text` | embed | retrieval vectors | ✅ |

**`planner` belongs on the brain, and the objection is a mode problem.** The 26B model was
recorded degenerating into a repetition loop emitting JSON, the object never closing, every plan
silently becoming empty. The cause is in the same roster: it *"works in JSON-mode (thinks AND
emits JSON), goes BLANK in a tight plain-text cap"*. So every JSON-parsing caller sets
`json_only` and budgets ~25s. Measured on Jarvis after that change: 8 calls, 0 blanks.

**Thinking is scoped, not global** — ON for diagnosis and investigation, OFF for narration,
synthesis, SQL and plans. Synex has `should_think`; it should be audited against this list.

**A fifth model Synex does not have**: `llama3.1:8b` as an *independent grounding judge*,
deliberately a fourth family so nothing grades its own output. Synex uses `phi4` for both the
critique gate and the `text` role, so the auditor and the narrator are the same model. Worth
either adopting or writing down as a deliberate difference — `CONTEXT.md` §4 says four models,
do not invent a fifth, so this needs a decision rather than a drive-by addition.

---

## 3. The engine map — one message, one route, one engine

| Engine | What it is | Synex equivalent |
|---|---|---|
| `quick` | grounded single-agent answer, the default fallback | ✅ `explain` |
| `data_sql` | NL→SQL, deterministic, no agent | ❌ `sql_guard.py` built, unwired |
| `investigate` / `root_cause` | ReAct tool loop | ✅ wired 19 Aug |
| `optimize` | ranked energy actions | ❌ absent, and needs data this plant lacks |
| `maintenance` | CBM, RUL, fault-driven | ❌ absent |
| `brief` | short plant brief across several units | ⚠ `plant_overview` answers a thinner version |
| `orchestrate` | **planner → parallel specialists → synthesis** | ❌ absent |

`orchestrate` is the one worth building: a planner emits a structured `Plan` (never
prose-parsed), each subtask runs the ReAct graph in parallel sharing devstral so the box does
not thrash, and a synthesis pass merges the findings. It is how *"give me a full plant review"*
becomes one answer instead of seven.

---

## 4. The shared backbone

```
preflight  →  [ engine ]  →  postcheck  →  critique(+gate)  →  [retry once]  →  END
```

| Stage | Thermynx | Synex |
|---|---|---|
| preflight — pure regex, no model | ✅ | ✅ five router layers |
| postcheck — every number, name and citation must appear in the context | ✅ | ✅ seven audits |
| critique — a judge plus a soft gate marking `needs-review` | ✅ | ✅ `critique.py` |
| **retry once when gated** | ✅ re-answers using only grounded data, dropping unsupported claims | ❌ **absent — we gate and stop** |

The retry is cheap and it is the difference between "this answer was flagged" and "here is the
answer with the unsupported parts removed".

---

## 5. Two failures Thermynx paid for, and where Synex stands

**The stall that no error-watching guard can see.** Their ReAct agent was observed calling
`get_timeseries_summary` **13 times in a row**, every call succeeding, until the step ceiling ran
out — so `propose_work_order` was never reached and the operator got prose claiming a draft that
did not exist. Repeating a *succeeding* call throws nothing, so every guard watching for errors
is blind to it. **Synex already ends on `REPEATED_CALL` with a per-turn ledger** — learned from
`G5` from the other direction. Turning the model chooser on would have exposed exactly this.

**The wall-clock anchor on a snapshot.** A query anchored to `NOW()` matches no rows and returns
an empty table that reads as "nothing wrong" rather than "wrong question". `sql_guard.py`
refuses those functions and `episode_ref.py` refuses relative dates for the same reason.

---

## 6. Testing — the two harnesses, and why they are separate

> *"this folder = taste-test the food before serving; `model-eval/` = hire the cooks"*

| Harness | Question it answers | Synex |
|---|---|---|
| `tests/eval/` | does the **pipeline** give correct, safe answers, against the live backend, on every push | ✅ `scripts/eval_copilot.py` — 40 cases × 5 personas, three axes |
| `model-eval/` | which model is best for each **task** | ❌ absent, and deliberately: the roster is inherited, not re-benchmarked |

Their eval line carries pieces Synex does not have and should consider:

- **`canary_gate.py`** — a small set that must pass before anything else runs, so a broken box
  fails in seconds rather than after the full suite.
- **`chat_honesty_eval.py`** — honesty scored as its own axis, separate from correctness.
  Synex has this as `truthfulness` in the sweep.
- **`export_flagged.py`** — the gated answers exported for a human to read. Without it a soft
  gate produces a number nobody looks behind.
- **`flywheel.py`** — flagged answers become next week's cases. This is what stops an eval suite
  ossifying around the questions its author happened to think of.

**The flywheel matters more than it sounds.** Synex's suite passed 31/31 while six ordinary
questions written minutes later all failed — because the suite's author wrote questions that
matched the keywords. An eval that only contains cases somebody thought of measures the author,
not the product.

---

## 7. Knowledge — curated, never generated

**124 checklist items across 11 fault classes, hand-written. The model selects and
contextualises; it never writes a step.** The argument, which applies unchanged here:

- a checklist instructs somebody to **physically open a pressurised circuit**, and a
  plausible-but-wrong item is worse than none, because it will be followed
- the grounding gate audits numbers against context, and **a checklist has no numbers**, so the
  one automated defence is toothless on exactly this output
- at 39 episodes, generated procedures cannot be meaningfully evaluated; **11 curated lists can
  be read once and signed off**
- it keeps working with the GPU off

Synex's checklist content is sample content and every surface says so. The curated library is
the work, and it is Vishnu's to review — not ours to generate.

---

## 8. Interface pieces worth taking

**Work orders** — Thermynx shows six states (`open`, `assigned`, `in_progress`, `resolved`,
`closed`, `cancelled`), four priorities, a **source** (`manual` · `agent` · `anomaly` · `PM`),
and five tiles: Total, Open/Active, Resolved/Closed, MTTR, repeat-issue rate.

Synex's row carries `kind` (`inspection` · `authorisation` · `corrective`), `state`, `priority`,
`priority_is_complete`, `evidence`, `created_at`, `closed_at`. Taking their page wholesale would
mean two invented tiles: **MTTR and repeat-issue rate need closed work orders with timestamps,
and Synex has none raised yet**. Take the shape — states, kinds, source, counts — and leave
those two out until there is something to compute them from. `choose_assignee` exists and is
deterministic, so an assignee column is honest as soon as it is stored.

**Anomalies** — their `AnomaliesPanel` is the queue Synex calls the workspace. The idea worth
taking is *live* versus *history* as separate reads, and the grouping rule from §1: one case per
`(equipment, fault, day)`, with a determinate class leading over an ambiguous one.

---

## 9. In order

1. **Enter Hypothesise mode instead of refusing.** Four differentials are authored and the
   Copilot never runs one. This is the product's signature and it is one wiring job.
2. **Retry once when the critique gate fires.**
3. **NL→SQL** — `sql_guard.py` is built and validated. It is `data_sql`, and it is devstral's
   other job.
4. **The flywheel** — flagged answers become cases, so the suite stops measuring its author.
5. **`orchestrate`** — planner → parallel specialists → synthesis.
6. **The analyst pass** — the brain writes a short expert assessment *before* composing, thinking
   on. Cheap, and it is what makes a diagnosis read like an engineer wrote it.
7. **Decide on the fourth-family grounding judge**, rather than leaving `phi4` grading prose
   `phi4` narrated.
