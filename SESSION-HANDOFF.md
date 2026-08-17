# Session handoff — 2026-08-17

**For the next session, starting cold.** Read `CLAUDE.md`, `CONTEXT.md` and `HANDOFF.md`
first; this file is what those do not yet say.

---

## 1 · Where the build is

**48% of the MVP cut — 45 of 94 features.** 40 fully working (route, screen, tests), 5 built
as rules with no screen yet.

| Milestone | |
|---|---|
| M0 Foundations | ✅ complete — `v0.17.0` |
| M1 Copilot explains one fault | ✅ complete, 27/27 — `v0.18.0` |
| M2 Case + work order | ◑ ~14 of 37 |
| M3 Verification | ◑ 4 of 8 — `v0.21.0` |
| M4 Read surfaces | ◑ 2 of 19 — `v0.19.0` |
| M5 Hardening | ✗ 0 of 3 |

Tags: `v0.17.0` M0 · `v0.18.0` M1 · `v0.19.0` Reports · `v0.20.0` Work orders ·
`v0.21.0` Verification · `v0.22.0` The case surface.

**Tests: ~393 offline, 4 live suites.** Every gate green — `verify.py --strict`,
`verify_code.py`, `verify_sse_contract.py`, import-linter, ruff, typecheck, and **94
accessibility rules with zero violations** on both web surfaces.

**Everything runs with MySQL stopped and the GPU terminated.** That is the design, not a
temporary state.

### Running it

```bash
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
cd apps/web && npm run dev            # port 3100, not 3000 — 3000-3003 are occupied
```

Two traps that cost time this session, both self-inflicted:
- **Never run `npm run build` while `next dev` is running** — it clobbers `.next` and the
  dev server serves 404s for its own chunks. Symptom: `main-app.js 404`.
- `TaskStop` does not always kill the node process. Free the port with
  `Get-NetTCPConnection -LocalPort 3100 | Stop-Process`.

---

## 2 · What is on screen

Four of five loop steps: **fault → evidence → answer → case → work order → verification.**

**Copilot** (`/`) — persona switcher labelled as a demonstration · 39 real episodes ·
a residual chart against that asset's own band · route trace showing the layer and whether a
model was spent · six figures with band verdicts and fit badges · provenance · answer or
refusal in its own card · six honesty checks · case with capability-routed checklist ·
work-order draft with a hand-recomputable priority · verification.

**Reports** (`/reports`) — every headline figure recomputed from source on load. 14 of 14
agree; the one that cannot be recomputed says so rather than being counted as agreeing.

---

## 3 · Blocked on Harshan — these gate 22 features

1. **The Jarvis box.** Every Copilot answer is still the deterministic fallback and says so.
   One `SYNEX_MODEL_MODE=record` run captures transcripts that replay offline for ever, and
   live mode works after that. Unblocks `W1`, `C6`, `C8`–`C10`. **The single biggest gap
   between what exists and what demos.**
2. **PostgreSQL.** Nothing persists — cases, work orders, findings and audit rows are
   computed and discarded. Not a register feature, but a foundation under roughly 20 of
   them, and `RC8` idempotent seeding and `RC9` ageing are meaningless without it.
3. **The SME hour.** `RC2`. The mechanism is built and gated; only content is missing.

---

## 4 · The database, and the state of the simulated-row issue

`graylinx_synex` on MySQL `:3307`. App connects as `synex_plant_ro` — `SELECT` on that one
database and nothing else (Q42, closed). Password is in `backend/.env`, which is gitignored.
**Root is `root123`** — needed for anything structural; `synex_plant_ro` deliberately cannot.

### Done this session

`app/db/provenance.py` — signal availability **computed from `snapshot_simulated_slots`**
rather than asserted in a registry. `app/agents/postcheck.py` now audits against
`pack.never_measured_signals` instead of a module-level table.

Live, through the API:
> *condenser flow: never measured — 0 non-zero in 31,884 real slots, and the 3,354 non-zero
> values in this column are all simulated*
>
> *chilled water flow: the instrument stopped reading credibly after 2026-04-22 17:35*

Both reach `prompt_data`, so the model is told rather than left to infer.

**A correction to `docs/DATA-ISSUE-2026-08-14-simulated-rows.md`:** it says
`audit_never_measured` currently passes on `cond_flow`. It did not — it caught it, because
`app/domain/signals.py` hardcoded the verdict. The real defect was different and worse: the
verdict was *asserted*, the registry covers 5 of a normalized table's 38 columns, and the
other 33 returned "no claim made".

### Not done — the next database step

`docs/DB-MIGRATION-PROPOSAL-2026-08-17.md` has the full analysis, backup commands and
rollback. **Nothing executed.** Headlines:

- Every number the tests assert is **identical** in the rebuilt `graylinx_v2`.
- **Breaks:** `compressor_power_residual` is no longer globally 100% NULL (4,281 non-null,
  all outside our clip) — two tests and two documents need a narrower restatement.
- **Watch:** `snapshot_derived_slots` has **7,670 rows inside our measured window**, and our
  code has no concept of *derived*. Same defect shape, different door.
- **The clone does not fix `cond_flow`** — zero in all three databases. The plant does not
  meter it.

A `DROP DATABASE` was **blocked by the safety classifier**, correctly. It needs Harshan's
keystroke; the script does the rest.

---

## 5 · The honesty rules a new session must not break

Each exists because a specific failure happened. Breaking one makes the product dishonest,
not merely worse.

1. **A refusal is not an error.** `NO_DIAGNOSIS` is the modal outcome — 5,309 slots against
   674 faulted. Its own card, the accent colour, never red.
2. **An absence is not a zero and not a dash.** Words: *"never measured"*, *"no model is
   fitted for this signal"*.
3. **Only `FigureView` renders a number**, and it never formats — it prints the string the
   back end produced. Enforced by a web test that greps for formatting APIs.
4. **The pack carries display strings, never raw floats.** The numeric audit compares exact
   values; a float would force a tolerance, and every tolerance forgives some fabrication.
5. **Only a measured reading settles a blocking check.** Estimated, cannot-check and
   not-applicable all leave the gate shut.
6. **`cannot_check` ≠ `not_applicable`.** Six "N/A" presses once opened a blocking gate.
7. **Elimination is irreversible, and *can't tell* changes nothing at all.**
8. **Never invent a number.** Five questions were raised rather than guessed this session:
   **Q48** unnumbered ceilings · **Q49** severity for 8 of 9 labels · **Q50** the nRMSE trust
   threshold · **Q51** three of four priority inputs do not exist · **Q52** the collapse
   fraction.

---

## 6 · Bugs the gates caught, worth knowing about

Not trivia — each is a pattern that will recur.

- **Substring containment made the numeric audit toothless.** `-25.6` is a substring of
  `-25.645`, so the exact truncation the audit existed to catch sailed through — and the test
  written to catch it passed against the broken version. Now token-and-value comparison.
- **The keyword layer out-ranked the scope gate.** "What is the capital of France" matched
  `what is the` and routed as a telemetry lookup. Layer 3 now proposes; layer 3.5 vetoes.
- **The scope gate refused the product's most natural question.** *"Why was this flagged?"*
  names no machine, so it was refused even with an episode selected.
- **`did_terminate` failed on its first real run** — the refusal text ended without a full
  stop, so a complete answer read as truncated.
- **The plan's `F15` example is wrong.** −25 is normal on *both* chillers. The real
  comparison is better: **0.0 is `HIGH` on chiller 1 and `NORMAL` on chiller 2** — the naive
  compare-to-zero is inverted, not merely imprecise.
- **Chiller 2 has two determinate episodes, not the five the plan assumes.**

---

## 7 · What to do next

**Not blocked, in order of value:**

1. **Finish M2's rules** — `RC6`, `RC8`, `RC9`, `RC11`, `RC17`, `RC18`, `RC19`, `F6`, `F17`.
   Pure domain like `differential.py` and `cases.py`; the cheapest work left, ~8 features per
   block.
2. **Wire the differential to a screen.** `RC12`–`RC14` are built and tested with no UI. The
   design handoff argues this is the product's potential signature: candidate causes visibly
   narrowing, eliminated ones struck out with *why* attached.
3. **`RC8`/`RC9`** once PostgreSQL exists.
4. **M4's read surfaces** — 17 features, mostly software, largely independent.

**Two documents are ready to hand to someone else:** `mvp/DEMO-SCRIPT.md`, with a test that
checks every episode it names against the live database, and `mvp/DESIGN-HANDOFF.md`,
covering all eight surfaces, five flows and mobile-first responsive across four breakpoints.

---

## 8 · The gap no percentage captures

**This is a single-shot pipeline with strong governance, not an agent loop.**

Built: the role table, reasoning on/off, the eight-layer routing ladder, prompt fencing, six
postcheck audits, ten resource ceilings, stub/record/live.

Not built: **LangGraph** (not installed), the **ReAct tool loop** (`max_react_steps` is
configured and nothing consumes it), **any tools at all**, **five of seven skills** (they
route correctly then fall into the same explain path), **specialist fan-out**, and **real
turn memory** — `C15` is a single `last_equipment` string, which is carry-forward, not
memory. M1's count should honestly read 26 of 27.

That is Harshan's own section 11.1 objection, and it has not moved: **76 of 94 features
involve no language model at all.** Correctly so under the separation law — but the agentic
half is the work after the demonstration, and the order is tools → LangGraph → turn memory →
fan-out.
