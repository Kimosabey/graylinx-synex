# HANDOFF.md — Where things stand

Last updated: 2026-08-10 · Owner: Harshan · SME: Vishnu

---

## 1. Read me first

```
1. CLAUDE.md      how to work in this repo
2. CONTEXT.md     what Synex is — settled truth
3. this file      what is done, what is next
```

Then run `python scripts/verify.py` to confirm the repo is clean before you
change anything.

---

## 2. What is done

- **Product & Architecture Document v4** — 78 pages, 44 chapters in two parts
  plus an appendix. Product first, architecture second. Includes the full
  Copilot specification (14 modes, 14-stage turn lifecycle, context contract,
  intent routing, 38-tool belt, answer contract, model routing, worked chiller
  examples), and two ML chapters covering the ML/rules/LLM separation and the
  equipment ML layer.
- **Feature Review Pack** — 9-page landscape working document, already renamed
  to Synex. 101 features with IDs, the FDD fingerprint matrix, the
  instrumentation survey table, 20 open SME questions and a decision log.
  A miscount in an earlier draft ("85 features") was corrected when the register
  was generated — the register is now the arithmetic authority.
- **Terminology repair** — roughly 340 damaged phrases restored across the
  document, plus a 39-term plain-English glossary. The banned list is now
  enforced by `scripts/verify.py`.

## 3. What is NOT done

- **The Synex rename has not been applied to v4.** The 78-page reference still
  says "Graylinx Enterprise AI Platform" and "AI Copilot". The review pack has
  already been renamed. This is task T1 below.
- No decision has been recorded for any of the 20 SME questions.
- The MVP cut in `mvp/MVP-SCOPE.md` is a proposal, not an agreement.
- Naming question N1 (Synex vs Thermynx) is unanswered and blocks any sentence
  that positions the two products relative to each other.

## 4. Immediate tasks

### ~~T1 — Apply the Synex rename~~ — DONE
Both source documents renamed, verified at zero occurrences by the gate:

- **v4 reference document** — 13 "AI Copilot", 14 "Chatbot", 13 "the chatbot",
  1 "Enterprise AI Platform" and 1 "Enterprise AI Copilot", plus the title,
  subject and keywords in `docProps`. Compound forms collapsed to one name
  rather than two: "Chatbot / AI Copilot" is "Synex Copilot", not both.
- **Feature Review Pack** — this file previously claimed it was already done. It
  was not: 1 "Graylinx Enterprise AI Platform", 3 "AI Copilot" and an all-caps
  `SYNEX` running header. The gate found all four the moment it learned to read
  `.docx`.

One occurrence was deliberately left: *"the single biggest difference between a
chatbot and a copilot is context"* contrasts the two categories rather than naming
this product, and rewriting it would destroy the sentence. `verify.py` carries that
exemption explicitly.

Pre-rename editions are in `docs/90-archive/`. `verify.py` now scans `.docx`
sources, so this class of drift cannot hide again — and the check was self-tested
against the archived original to prove it fails when it should.

### ~~T2 — Split the source documents into per-chapter markdown~~ — DONE
`scripts/split_source.py` converts v4 into 47 files: front matter and chapters 1-25
plus Appendix A in `docs/10-product/`, chapters 26-44 in `docs/20-architecture/`, each
directory with a generated index. All **111 tables** preserved; word count rises from
19,623 to 23,216 because markdown adds its own syntax, and the script fails if it ever
falls.

The .docx **stays in `docs/00-source/`**. This task previously said to move it to
`docs/90-archive/`, which contradicts CLAUDE.md §3 — that directory is read-only input
and the archive is for superseded editions, not for the source everything derives from.

Re-run the script after the .docx changes; it is idempotent.

### T3 — Reconcile the feature register against the chapters
Every feature ID in `mvp/FEATURE-REGISTER.md` must be traceable to a chapter,
and every capability described in a chapter must have an ID.
**Done when:** `verify.py` reports zero orphan IDs and zero unregistered
capabilities.

### T4 — Produce the MVP build backlog
From the agreed MVP cut, produce `mvp/BACKLOG.md`: one entry per feature with
its dependencies, the data it needs, and the open questions that block it.
**Blocked by:** a human agreeing the MVP cut.

### ~~T5b — Reconcile the two open-question sets~~ — DONE
Merged into `mvp/SME-REVIEW.md`: 11 of our questions merged into theirs, one of
theirs adopted whole, their platform questions left with their platform team, and
one question identified as having no counterpart in their 57 — what proves a repair
worked. That document is the agenda for the session.

### T6 — Read the rest of the Thermynx knowledge base
Covered: `docs/nyx`, the intent router, the route list, Resolve, the fault
taxonomy, the 14 pre-existing SME decisions, the hardware and Jarvis docs, the
v6 horizon, the chat implementation status, and the **57-question FDD SME
agenda** with its discovery findings (D-004).

**Still not read:** `docs/plan-v4.9.1/fdd/01-fdd-discovery` (the rule inventory,
fault catalog, schema and engine analysis) and `02-fault-analysis` (severity
model, confidence scoring, fault relationships, the four differentials) —
about 30k words that would sharpen `F1`–`F14` further. Also `docs/plan-v5`
(data layers, Kafka, ETL, the MySQL→Postgres decision), `docs/architecture`,
`docs/layers`, `docs/playbook-expansion`, `docs/models-decision`,
`docs/analysis` and `docs/ai-investigation`.
**Done when:** anything that changes the cut is registered, and anything that
constrains a feature is in `CONTEXT.md` §10.

### T5 — Fold SME decisions back in
After the review session with Vishnu, transcribe the decision log from the
review pack into `decisions/DECISIONS.md`, then update the affected chapters.
**Blocked by:** the review session.

## 5. Blocking questions

| ID | Question | Blocks | Owner |
|---|---|---|---|
| N1 | How do Synex and Thermynx relate? | All positioning copy | Harshan |
| Q1 | Is condenser flow measured and trustworthy on target sites? | Most FDD fault classes | Vishnu + site |
| Q2 | How is evaporator flow derived? | All `rSP`-based classes | Vishnu + site |
| Q15 | What proves a condenser cleaning worked? | Verification PASS criteria | Vishnu |
| — | Is the MVP cut agreed? | T4 | Harshan |

Full list: `decisions/OPEN-QUESTIONS.md`.

## 6. How to run things

```bash
# from the repo root
python scripts/verify.py              # compliance gate — must exit 0
python scripts/verify.py --strict     # also fails on TBD markers
python scripts/build_docs.py          # markdown -> docx (needs pandoc)
python scripts/build_docs.py --pdf    # also renders a PDF (needs LibreOffice)
```

On Windows, use `py scripts\verify.py` if `python` is not on PATH.

## 7. Recent changes

| Date | Change | By |
|---|---|---|
| 2026-08-10 | Repo initialised; CLAUDE / CONTEXT / HANDOFF written; feature register and open questions extracted from the review pack | Claude |
| 2026-08-10 | Feature count corrected 85 → 101; Planning IDs renamed `P1–P5` → `PL1–PL5` to stop colliding with priority labels; review pack rebuilt under the Synex name | Claude |
| 2026-08-10 | Workspace organised into a git repository and published privately to `Kimosabey/graylinx-synex`; superseded pre-rename review pack editions filed under `docs/90-archive/`; tagged `v0.1.0`, `develop` branch cut from `main` | Claude |
| 2026-08-10 | `mvp/MVP.html` added — an interactive derived view of the MVP: filterable 101-feature register, the six priority workflows as steppers, the eight cases, the chiller worked example with its `NO_DIAGNOSIS` variant, the FDD engine and the Copilot specification. Domain and case coverage badges are computed from the register, so they cannot drift from it | Claude |
| 2026-08-11 | `graylinx_synex` cloned from `graylinx_v2` — 193 tables, 3,879 MB, verified table by table. Synex writes here and nowhere else; `shiva` stays the read-only customer snapshot. 156,129 slots in the copy are simulated and are named in `snapshot_simulated_slots`. Recorded as D-005 | Claude |
| 2026-08-11 | The stack and deployment shape recorded for the first time: `docs/20-architecture/01-stack.md` and `02-deployment.md`, decision D-010. Every dependency was already chosen in Thermynx with reasoning attached, including **two refusals** — Ragas removed as the framework-churn risk realised, Langfuse disabled because self-hosting costs five containers. Three things close without work: `arq` already installed so `RC17` is a scheduled job, `echarts` already present so `C24` has its charting, `axe-core` already present so the WCAG audit is CI-testable. Q41–Q43 raised: identity has no library and the snapshot's user tables are empty; the back end connects as `root` with `SUPER`/`DROP`/`FILE` so the plant is read-only by promise rather than by grant; no application image and no offline wheel bundle for an air-gapped site | Claude |
| 2026-08-11 | Measured what is demonstrable: **all seven fault classes are labelled on real data**, and `NO_DIAGNOSIS` is the most common labelled outcome at 5,309 slots — the honest refusal is what the platform does most, not a contrived case. Also **12 equipment tables carry telemetry and 2 have any model**, and the same model is 18× worse on chiller 1 than chiller 2 (nRMSE 48.03 vs 2.65). Five models are fitted per chiller, not six. Q44–Q45 raised from the Thermynx playbook review: zero fault-code coverage anywhere, and resolution-note capture that works but has caught 2 notes | Claude |
| 2026-08-11 | Two ID collisions found in the freshly-converted chapters and normalised on the way out of the .docx: design levels `L0`–`L6` (ch. 26) and architecture layers `L0`–`L9` (ch. 28) both collided with Alerts `L1`–`L6`, and release gates `G0`–`G5` (ch. 37) with Control Plane `G1`–`G6`. Now "Level n", "Layer n" and "Gate n". They had survived because the ID scanner treated `**` and `|` as non-boundaries, so a bold gate label sitting alone in a table cell was invisible — widened, and self-tested | Claude |
| 2026-08-11 | T2 done: `scripts/split_source.py` splits v4 into 47 chapter files across `docs/10-product/` and `docs/20-architecture/`, all 111 tables preserved. The gate went from scanning 12 markdown files to 61 and immediately found two separation-law hits — both false positives, which exposed that the negation check only looked inside the matched span. It now reads the sentence containing the match plus the one after it, and knows "refuse" is a denial | Claude |
| 2026-08-11 | `mvp/MVP-SCOPE.md` gains "The shape of the cut, and why it stopped growing" — the per-domain split generated by `sync_mvp_html.py` between markers, plus the growth history 51 → 69 → 79 → 90 → 93 and what each increase came from. Generating it immediately corrected a claim made in conversation: two domains are in whole, not three — the Control Plane defers `G7` and `G8` | Claude |
| 2026-08-11 | Analysed `graylinx_synex` against the live server and wrote `docs/20-architecture/00-data-model.md` — the first file in that directory. Two findings changed the plan: the MySQL snapshot holds **no** cases, work orders, equipment master or anomalies, so those are Synex's own state in PostgreSQL; and of 32 numeric columns on `chiller_1_normalized`, exactly one differs in kind between the measured and simulated windows — `cond_flow` has zero readings in 31,884 real slots and 3,354 fabricated ones. That is the signal four of six models depend on. `C26` per-signal provenance registered; the demonstration window is the measured one. 93 of 146. Decision D-009 | Claude |
| 2026-08-11 | `mvp/MVP.html` gains section 16.0 — the system architecture and the plug-in boundary, which existed nowhere as a picture despite D-006 making the boundary the point. Querying the database while drawing it caught the diagram claiming work orders live in MySQL; they do not | Claude |
| 2026-08-11 | `RC18` and `F17` registered from the FDD gap register: evidence the checklist asks for sitting unread in the same table, and two severity scales disagreeing on four of seven classes — items 18 and 13 in the Thermynx gap register. 92 of 145. Decision D-008 | Claude |
| 2026-08-11 | `RC17` registered after reading the FDD sequencing brainstorm: 22 detected episodes, including the only two `critical`, never reached the queue because the idempotent seed was never scheduled. 90 of 143. Decision D-007 | Claude |
| 2026-08-11 | `mvp/SME-REVIEW.md` §1.4b added — the three eliminations that carry most of the risk, named individually rather than left inside the general question. `HIGH_HEAD_AMBIGUOUS` Q1 (64 % of fault slots), `CONDENSER_WATER_SIDE_UNSPECIFIED` Q1 (three of five causes, on a measurement telemetry does not carry), `POWER_HIGH_UNEXPLAINED` Q1 (four causes closed by one estimated judgement) | Claude |
| 2026-08-11 | Two drift gates added to `verify.py`. `check_counts` ties every "N of M features" in prose to the register — it immediately found four stale, including `MVP-SCOPE.md` at "69 of 122", three cuts out of date. `check_scope_tables` proves the what-is-in and what-is-out tables partition the register exactly; it found 21 cut features and 22 deferred ones named by no row at all. Both tables rewritten to account for all 143 | Claude |
| 2026-08-11 | The specification's prose counts are computed from the register at load instead of typed. The register lede had claimed 80, 133 and 122 in one paragraph — the `v0.4.0` figures, disagreeing with themselves | Claude |
| 2026-08-11 | Positioning recorded as D-006: Synex is an AI layer on the existing Graylinx platform, and this MVP is built to be shown — which is why the loop must be complete rather than broad | Claude |
| 2026-08-10 | T1 done: the Synex rename applied to both source documents including their metadata, 41 legacy occurrences to zero, with one generic use of "chatbot" deliberately preserved. `verify.py` extended to scan `.docx` — which immediately disproved this file's claim that the review pack was already renamed. Pre-rename editions archived | Claude |
| 2026-08-10 | T6 done: the differential mechanism registered — `RC12` narrowing, `RC13` elimination audit, `RC14` exhausted-not-settled — with constraints 27–32 and Q37–Q39. 86 of 139 | Claude |
| 2026-08-10 | `mvp/SME-REVIEW.md` added — the two open-question sets merged into one agenda ordered by what a wrong answer costs (task T5b). Published the explorer to Netlify from `develop` with the publish directory pinned to a built `site/`, so `docs/00-source/` stays off the internet; three layers of noindex. Live and byte-identical to the repository copy | Claude |
| 2026-08-10 | Thermynx FDD knowledge base read (task T6, partial): the 57-question SME agenda and the discovery findings. Condenser flow has never recorded a non-zero value on the reference plant — the signal four of six models depend on. Recorded in `CONTEXT.md` §10a with three more inherited constraints; `C23`, `RC9`, `RC10`, `S6` added (79 of 132); Q1 and Q2 restated with the evidence; Q21–Q27 raised. Decision D-004 | Claude |
| 2026-08-10 | MVP cut grown 51 → 69 of 122 after reviewing the flows in the existing Thermynx implementation: conversation shell `C15`–`C20`, case resolution `RC1`–`RC8`, energy and cost `E1`–`E4`, personas `U6`–`U8`. Two new prefixes `RC` and `E`; `verify.py` `ID_PREFIX` extended so `RC1` is not read as `C1`. 13 acceptance criteria, 10 build stages. Recorded as D-002 | Claude |
| 2026-08-10 | Thirteen Thermynx platform decisions adopted as inherited constraints in `CONTEXT.md` §10, with the graylinx-v2 database, the Jarvis box and the shared stack recorded as what Synex stands on. Three of the thirteen are inherited as unsolved gaps — Q19. Recorded as D-003 | Claude |
| 2026-08-10 | `scripts/sync_mvp_html.py` added: the explorer's feature data is now generated from the register instead of hand-transcribed, so the page cannot drift from it. `--check` fails if it is stale | Claude |
| 2026-08-10 | Brand colour `#0020B0` issued and recorded as D-001; `scripts/palette.py` added to derive and audit the whole colour system from it; `brand/NAMING.md` Visual identity replaced. 72 of 72 rendered pairs pass WCAG 2.2 AA in both themes, body text at AAA | Claude |

_Append a row here for every change. This table is how the next session finds
out what happened._
