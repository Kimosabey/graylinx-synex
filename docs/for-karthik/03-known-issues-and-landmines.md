# Known issues and landmines

**Read this before you change anything in the AI code.** Every entry is a real defect that
reached a running system, and most of them share one shape. Recognising the shape is worth more
than memorising the list.

---

## The defect this codebase produces most: machinery with no consumer

Something is built, tested, documented — and **nothing in the request path ever calls it**. Six
instances found in a single day, and they had been sitting for weeks:

| What | How long | How it presented |
|---|---|---|
| `SopIndex` — the whole knowledge layer | since ingest shipped | 269 approved passages, and answers used none of them |
| `devstral` | since the roster was written | a model on the box, mapped to two roles, never called once |
| `RC7` escalation routes | since `RC15` | *"I can't do this"* returned a checklist the reader had just said they could not run |
| `react.py` | until `C20` | a bounded tool loop with no caller |
| `domain_analyst` | since `reasoning_policy` was written | a thinking task nothing invoked |
| Router layer 4 | since the router was written | the `arbiter` hook defaulted to `None` and no caller ever passed one |

**Why it is hard to see.** Every one of these has passing tests. The unit tests test the unit;
the integration tests test paths that exist. Nothing tests *"is this reachable from a request"*.

**How to check.** Before assuming a capability works, grep for its consumers:

```powershell
# Not "does it exist" — "does a request reach it"
Select-String -Path backend\app -Pattern "nearest_approved" -Recurse
```

If the only hits are its own definition, its tests, and an ingest job, it is not wired.

---

## The tunnel dies silently

Covered in `01-running-synex.md` and repeated here because it is the one most likely to waste
your afternoon.

When the SSH tunnel to the GPU box drops: the local port stays bound, `/health` keeps answering,
and every model call falls back to the deterministic rendering — **exactly as designed** for a
box that is not there. No error is logged, because nothing errored.

It cost an evaluation run whose model-written count fell from **12 of 31 to 5** without one test
failing. Run `scripts/jarvis_tunnel.ps1` and leave it running.

---

## An eval suite written by the router's author measures the author

The hand-written suite passed **31 of 31**. Six ordinary questions written minutes later **all
six failed** — because the same person wrote the router's keyword lists and the suite's
questions.

`scripts/eval_generated.py` fixes this by *enumerating* instead of choosing: every machine
crossed with every question shape, every fault class, every signal. 147 cases nobody picked.

**It found a truthfulness violation in six tries.** *"What is the condenser flow on chiller 1?"*
came back carrying **893.7** — a value for a signal with zero non-zero readings in 31,884 slots.
The number came from the registry's own provenance note, which ends *"the simulated window
fabricates it to a max of 893.7"*. Handed to the composer it satisfied every rule, because
*"every figure you state must appear in the result"* was true of 893.7.

Two fixes, because the source and the guard had both failed: the tool now strips figures from
reader-facing notes, and `audit_never_measured` fires on **proximity** rather than only on a
reading-verb pattern — with an exemption so *"0 non-zero readings in 31,884 slots"* still passes.

**The lesson:** a suite containing only cases somebody thought of measures the person who thought
of them. When you add a capability, add generated coverage for it, not three cases you like.

---

## Provenance notes contain numbers that are not readings

Directly from the above, and general enough to catch you elsewhere. A note explaining *why* a
signal cannot be quoted often contains numbers — how many slots were zero, what a fabricated
maximum reached. **Every one is a fact about the absence, not a reading of the signal**, and a
wording layer cannot tell the difference: it sees a number beside a signal name in its evidence
and states it.

If you add anything to what the model sees, ask whether a number in it could be read as a
measurement.

---

## Two absences collapsed into one

A recurring shape. These pairs look alike in code and mean different things to a reader:

| These are not the same | |
|---|---|
| *nothing matched* | *we could not look* |
| *not probed* | *working* |
| *no fitted model* | *healthy* |
| *unavailable auditor* | *audit passed* |
| *no reading* | *a reading of zero* |
| *severity unrated* | *severity low* |

Told the first when the second is true, somebody goes looking for a document that is sitting
there — or trusts a machine nobody examined. The services panel reported **four of seven
capabilities as `unknown`** on a platform where three were up: honest, and useless.

Whenever you write `if not x:`, ask whether `x` being absent and `x` being false are the same
fact.

---

## A guard that is too strict fails invisibly

The SQL validator rejected `SELECT 'chiller_1' AS machine, AVG(comp1_kw) AS avg_kw` — correct
SQL — because `chiller_1`, `machine` and `avg_kw` are not columns. They are not meant to be: one
is a literal labelling a row, the others are names the model invented for its own output.

**A guard that rejects correct input is as broken as one that admits dangerous input**, and it
fails in a way nobody investigates: the refusal is articulate and wrong, so it reads as the plant
not having the column.

---

## Safe is not the same as correct

Also from the SQL path. The first guard-approved statement grouped by `id` — the row primary key
— so it returned one group per reading and an average that *was* the reading. Real numbers, valid
arithmetic, nonsense answer.

The guard makes a statement **safe**. Nothing makes it **correct**. The rendered SQL travels with
every answer for exactly this reason.

---

## The scope gate leaks through inherited context

A selected episode used to admit *every* question. *"What is the capital of France?"* came back
as a full answer about chiller 1 — **honesty checks and all**. Every check passed. Nothing in it
was ungrounded. It was a true answer to a question nobody asked, and no guardrail was watching
for that.

The gate now distinguishes *named in this message* from *resolved from context*. They are
different facts.

---

## Domain vocabulary that an injection also reaches for

When widening the scope gate, `"evidence"` was added and removed the same minute: it is genuine
domain vocabulary **and** the word an injection reaches for — *"answer without the evidence"* —
so listing it admitted a payload naming no machine straight past the gate.

Bare `"data"` was tried later and rejected the same way: *"show me every user in the database"*
contains it. The entries are phrases now — `"days of data"` cannot be reached by naming a
database.

**Every widening goes through the red-team corpus first.** `tests/eval/test_adversarial.py`.

---

## Wall-clock time on a snapshot

The telemetry ends on a fixed date. A query anchored to `NOW()` matches no rows and returns an
empty table that reads as *"nothing wrong"* rather than *"wrong question"*.

`sql_guard` refuses those functions and `episode_ref` refuses relative dates (*"yesterday"*,
*"last week"*) for the same reason. If you add a date path, it needs the same refusal.

---

## The uvicorn reloader leaves orphans

`--reload` runs a parent and a child. Killing the parent can leave the child holding port 8001 —
serving requests, invisible to `Get-Process`, so `taskkill` says "process not found" while the
port is plainly in use. Find it by command line:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'multiprocessing-fork' }
```

---

## Rules that look like preferences and are not

- **Never rename a thing back.** If you find an old name, fix it. `scripts/verify.py` fails the
  build on the banned-phrase list, which exists because a global find-and-replace once expanded
  technical terms into long paraphrases and damaged the document.
- **Never invent a number.** If one is needed and unavailable, write `TBD (see Qn)` and add the
  question to `decisions/OPEN-QUESTIONS.md`.
- **`NO_DIAGNOSIS` is a feature.** Never soften it, and never let a document imply the platform
  will produce an answer when the gates fail.
- **Two-letter feature-ID prefixes must be listed before single-letter ones** in any pattern that
  parses them, or `RC1` matches as `C1` — a silent mis-count rather than an error. `ID_PREFIX` in
  `scripts/verify.py` is the only place this is defined.

---

Next: **[04-testing-and-evaluation.md](04-testing-and-evaluation.md)**.
