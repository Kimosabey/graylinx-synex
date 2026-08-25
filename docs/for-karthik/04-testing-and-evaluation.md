# Testing and evaluation

Four gates run offline and must all pass. Two evaluation suites run against a live box and answer
a different question. Knowing which is which saves you from trusting the wrong green tick.

---

## The offline gates — needed for every change

```powershell
cd backend
python -m pytest                          # 3,682 tests, ~22s, no GPU, no database
python -m ruff check app tests            # style
lint-imports --config importlinter.ini    # 7 architectural contracts
cd .. ; python scripts\verify.py          # naming law, banned phrases, feature IDs
```

**`pytest` needs nothing at all.** `tests/conftest.py` pins `SYNEX_MODEL_MODE=stub` so a bare run
never reaches the box. The application default is `live` — turning the models off is a deliberate
act, not something you inherit. `tests/unit/test_config.py` asserts both halves.

### The seven import contracts, because they will catch you

| Contract | What it prevents |
|---|---|
| `app.domain` imports nothing | the leaf stays a leaf |
| only `app.db` imports a database driver | every query lives in one layer |
| only `app.llm` imports a model client | one place reaches the box |
| `app.tools` are deterministic | a tool can never reach the plant outside `synex_plant_ro` |
| `app.analytics` is pure functions | the security boundary has no connections |

When one breaks, the message names the file and the import. It is nearly always a fix in the
right direction: the query belongs in `app.db`, not in the API layer.

### What `verify.py` checks that nothing else does

The naming law (**Graylinx Synex**, **Synex Copilot**, never "the chatbot"), a banned-phrase list
from a find-and-replace that once damaged the document, and the feature-ID register. It fails the
build. It is not advisory.

---

## The two live suites, and why they are separate

> Thermynx puts it well: *this folder = taste-test the food before serving; `model-eval/` = hire
> the cooks.* We only have the first — the roster is inherited, not re-benchmarked.

### `scripts/eval_copilot.py` — hand-written, 40 cases

Every level: plant, machine, fault class, episode, escalation, the guards, the honest absences.
Judged on three axes:

| Axis | Asks |
|---|---|
| **Correctness** | is the state one this question can produce, and are the facts asked for in it |
| **Faithfulness** | does every figure in the prose trace to one the platform assembled |
| **Truthfulness** | is anything claimed the plant cannot support |

Faithfulness is the subtle one. A model that rounds `4.7` to *"about 5"* has **invented a
reading** — nothing in the wording layer may introduce a number the evidence did not carry.

```powershell
python scripts\eval_copilot.py --one-persona    # one identity
python scripts\eval_copilot.py                  # all five personas
```

### `scripts/eval_generated.py` — enumerated, 147 cases

**Read `03-known-issues-and-landmines.md` on why this exists before trusting the one above.** The
hand-written suite passed 31/31 while six ordinary questions written minutes later all failed,
because its author also wrote the router's keywords.

These are enumerated from the plant's own catalogue — every machine crossed with every question
shape, every fault class, every signal — so nobody picks which go in, and nobody can
unconsciously pick the ones that work.

**What they assert is deliberately weak.** These cases cannot know the right answer; the plant
decides that. What they prove is that nothing *breaks*: no empty turn, no internal identifier in
the prose, no value for a never-metered signal, no silence read as health. A generated suite
asserting content would assert whatever its generator believed — the same trap one level up.

```powershell
python scripts\eval_generated.py --record
python scripts\eval_generated.py --filter signal --record   # the batch that found the 893.7 bug
```

---

## The flywheel

`--record` appends every failure to `eval-flywheel.txt`:

```
signal/cond_flow	what is the condenser flow on chiller 1?	gave 'condenser flow' a value...
```

**That file is a work list, and reading it is the job.** Each line is a question the product got
wrong, waiting for somebody to write a real hand-written case with a real expectation. Without
it, a suite ossifies around the questions its author happened to think of.

Nothing yet reads it back automatically. Doing that is on the backlog and it is a good first
task — see `05-one-week-plan.md`.

---

## Two ways to waste an afternoon

**Do not restart the backend while a suite is running.** It dies with `httpx.ReadError`, which
looks like a product failure and is not. Twice in one day, both self-inflicted.

**Check `box_reachable` before believing a model-usage count.** A run against a dropped tunnel
reports every answer as deterministic and every test still passes — the product is behaving
correctly for a box that is not there. The count falls and nothing goes red.

---

## What is not tested, honestly

- **A cited passage actually supporting the sentence citing it.** Retrieval is wired and unit
  tested; whether the passage is *relevant* is not measured. `app/retrieval/quality.py` has the
  machinery.
- **Multi-turn conversation against a live model.** The plumbing is tested end to end;
  the *behaviour* over several real turns is not.
- **A completed 147-case run.** Two attempts died — one to a self-inflicted restart, one to the
  backend dropping. **Nobody has yet seen all 147 finish**, and the highest number reached with
  zero failures is 84.

Do not let that last one be reported as a pass. It is an unfinished measurement.

---

Next: **[05-one-week-plan.md](05-one-week-plan.md)**.
