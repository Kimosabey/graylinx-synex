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
| 2026-08-14 | **Work Orders — the third P0 pillar, `v0.20.0`.** `W2` create from a fault, `W3` evidence auto-attached, `W4` deterministic priority. A job is built *from* an evidence pack, so **14 evidence lines travel with it** — every residual with its band and fit, every gate result, the provenance of each unusable signal — each carrying its own source. Nothing in the path calls a model, asserted by a test. **`W4` cannot be fully computed and says so**: the register specifies a formula over *criticality, risk, SLA and production impact*, and the snapshot records **no equipment master, no service-level target and no production schedule**. Three of four inputs do not exist, so `Priority` carries `used`, `missing` and `is_complete=false`, and the interface lists what was left out — a formula that silently dropped three terms would produce a number that looks like a priority and is really a severity wearing a rank, which a planner would schedule against. `CONDENSER_LOW_FLOW` reaches `P0`; the six classes with no agreed severity render `unrated` with the reason, rather than defaulting. `Q51` raised. Drafts only — nothing is persisted, and the card says so, because a work order nobody can be dispatched against must not look like one they can | Claude |
| 2026-08-14 | **Reports, the second P0 pillar — `R5` and `R10`, `v0.19.0`.** Every headline figure the product states is **recomputed from source on load** and shown beside what the documents claim: 14 of 14 agree, and the one that cannot be recomputed is marked *not recomputed* rather than counted as agreeing — a reconciliation claiming 100% while quietly excluding what it could not check would be the reassuring lie the rest of the product refuses. Each row opens onto its source table, row count, plain-English basis and a bounded sample (`R5`), because a number a reader cannot open is one they must take on trust. The answer state is `PARTIAL` rather than `ANSWERED` while anything is unrecomputable. The shell was extracted to `components/Shell.tsx` so both surfaces share one topbar and rail — two hand-written topbars is how a product grows two. Also `mvp/DEMO-SCRIPT.md`, committed with exact equipment and dates so nobody picks a window live, with a test that checks every claim against the database and fails the build days early rather than the demonstration in the room. **94 accessibility rules, zero violations, on both surfaces** | Claude |
| 2026-08-14 | **M1 complete — the Copilot explains a real fault, end to end, `v0.18.0`.** Ten routes and a streamed turn: route → evidence pack → gates → (model explains) → six honesty audits → one answer state. A Next.js shell on 3100 restyled to `mvp/mock.html`'s own token sheet, with the Graylinx wordmark taken from its `--logo` data URI and light mode pinned as the default. **250 offline tests and 61 live**, plus 5 web contract tests and **94 accessibility rules with zero violations**. The evidence chart is `F15` drawn rather than asserted: 113 of 113 readings on chiller 1 sit clear of that asset's own band, so "high for this machine" is visible instead of narrated. Built through the data-viz procedure — the palette was run through its validator rather than eyeballed, and the first status colour was rejected for chroma 0.068, "reads gray". **Four defects were found by the gates rather than by luck**: the scope gate refused *"why was this flagged?"* because the router never saw the selected episode; substring containment made the numeric audit toothless, since `-25.6` is a substring of `-25.645`; the keyword layer out-ranked the scope gate, so "what is the capital of France" routed as a telemetry lookup; and the refusal text ended without a full stop, which the new `did_terminate` dimension read as truncation. The golden set is **13 cases, all real** — with one correction to the plan: it asks for five determinate episodes on chiller 2 and chiller 2 has **two**, so the set uses all seven of its episodes and says so. Six cases need no database at all, because the refusal is the modal outcome and belongs in the gate everybody runs. **Q42 closed**; **Q48**, **Q49** and **Q50** raised rather than guessed | Claude |
| 2026-08-14 | **M1.1 and M1.2 — the documents met the database, and one of them was wrong.** The domain layer (labels, severity, equipment, model fits, signal provenance, the six answer states) and the analytics layer (bands, four gates, episodes), then a read-only repository and 17 live tests. **Every documented number reproduced exactly on the first query**: 5,309 `NO_DIAGNOSIS` against 674 faulted slots, 943 · 430 · 104 · 58 · 32 · 25 · 22 · 3, unlabelled 7,662, 12 fault days, 12 equipment-days, 39 naive cases, ten reference bands, `compressor_power_residual` NULL in all 21,534 rows. **The plan's flagship `F15` example is not true**: it says a current residual of −25 is normal on chiller 1 and abnormal on chiller 2, but chiller 2's robust band reaches 0.680, so −25 is normal on both. The unit test had asserted the plan's version against a band that was invented to fit it — a false statement made to look verified, which is the failure the test file exists to catch one level up. The real bands make the point better: **0.0 is `HIGH` on chiller 1 and `NORMAL` on chiller 2**, so the naive compare-to-zero is not imprecise but *inverted* on one machine. `robust_*` is used rather than `sigma_*` because the robust pair is built from median and MAD, and chiller 2's sigma band spans [−128.168, 34.846] — wide enough to call almost anything normal. **Q42 closed**: `synex_plant_ro` holds exactly two grants. **Q49** severity (only `CONDENSER_LOW_FLOW` has a sourced value; the other six render as words) and **Q50** the nRMSE at which a fit stops being trustworthy. Also `.gitignore`, which did not exist — `backend/.env` was verified as *not ignored* immediately before a password was to be written into it | Claude |
| 2026-08-14 | **M0 closed.** The four CI jobs exist and every gate they run is green locally: `docs` (`verify.py --strict`, the explorer, the PDFs), `contracts` (import-linter, `verify_code.py`, `verify_sse_contract.py`), `backend` (ruff, pytest), `frontend` (a guarded placeholder that says it is *pending* rather than passing, because a green tick against work that does not exist is how a missing gate gets mistaken for a passing one). 71 tests, up from 30, still with MySQL stopped and the box terminated. `scripts/verify_code.py` applies the naming law to source — **phrase rules only**, because the lowercase-`synex` rule fires on `graylinx_synex` and the feature-ID check fires on `C1`; it also carries the Ragas ban, self-tested against all seven forms an import can take. `app/config.py` holds the ten resource ceilings with the failure each prevents carried in the data, not just in a comment — **three have no value in the source** and are marked provisional against **Q48** rather than invented. `ruff.toml` written because there was no ruff config anywhere, so the rule set was whatever the installed version defaulted to. `--strict` had a pre-existing failure in `SME-REVIEW.md`, now fixed and the PDF rebuilt. **D-016**: the 18 August demonstration runs live on the box, and the gate never does | Claude |
| 2026-08-10 | Repo initialised; CLAUDE / CONTEXT / HANDOFF written; feature register and open questions extracted from the review pack | Claude |
| 2026-08-10 | Feature count corrected 85 → 101; Planning IDs renamed `P1–P5` → `PL1–PL5` to stop colliding with priority labels; review pack rebuilt under the Synex name | Claude |
| 2026-08-10 | Workspace organised into a git repository and published privately to `Kimosabey/graylinx-synex`; superseded pre-rename review pack editions filed under `docs/90-archive/`; tagged `v0.1.0`, `develop` branch cut from `main` | Claude |
| 2026-08-10 | `mvp/MVP.html` added — an interactive derived view of the MVP: filterable 101-feature register, the six priority workflows as steppers, the eight cases, the chiller worked example with its `NO_DIAGNOSIS` variant, the FDD engine and the Copilot specification. Domain and case coverage badges are computed from the register, so they cannot drift from it | Claude |
| 2026-08-11 | `graylinx_synex` cloned from `graylinx_v2` — 193 tables, 3,879 MB, verified table by table. Synex writes here and nowhere else; `shiva` stays the read-only customer snapshot. 156,129 slots in the copy are simulated and are named in `snapshot_simulated_slots`. Recorded as D-005 | Claude |
| 2026-08-13 | **The build started.** Plan approved and saved. D-012 monorepo layout and the **corrected layering direction** — `03-from-thermynx.md` §6 placed the probabilistic layer below services and analytics, which a LangGraph orchestrator cannot satisfy; the sibling carries 15 back-edges against its own stated rule, so Synex enforces `api → agents → services → analytics·retrieval → llm·prompts → db → domain` with import-linter, and §6 is amended. D-013 the persona switcher closes `Q41` for the MVP without answering it. D-014 the FDD models are **consumed, not built** — `F1`/`F2` reclassified `ML` → `SW`, which takes `Q1`/`Q2`/`Q14` off the build critical path. D-015 `NO_DIAGNOSIS` gets its own streaming frame, because rendering a refusal as answer text softens it by presentation | Claude |
| 2026-08-13 | **M0 green, tagged `v0.17.0`.** 30 tests pass with MySQL stopped and the GPU box terminated, which was the whole objective. Added the role table (`app/llm/models.py`) with a test that walks the AST of every module and **fails if a model name appears outside it** — "code never names a model" is now a gate rather than a convention. Added the reasoning policy: think ON for diagnosis, OFF for composition, **unknown tasks default OFF** because on a tight budget the model spends the whole allowance thinking and returns empty content. `.env.example` carries the ports verified against what is actually listening, and `infra/sql/01-mysql-grants.sql` creates `synex_plant_ro` with `SELECT` on `graylinx_synex` alone — Q42 as two statements | Claude |
| 2026-08-13 | M0 in progress: monorepo skeleton (33 files), `backend/importlinter.ini` with six contracts, `backend/pytest.ini` with **offline-by-default** `addopts` so a bare `pytest` is the gate, the architecture test that runs the linter in-process, and **the honesty type ported** — `Figure`/`Basis`/`Absence`/`Provenance`, constructor refuses a value-and-reason or neither, plus 19 tests written against our own measured facts. Verified by hand: frozen, `never_measured` renders the words rather than `0` or a dash, simulated and judged both qualify themselves | Claude |
| 2026-08-13 | Section 11.1 reframed from "where the intelligence actually is" to "where the **authority** is". Harshan's objection: the goal is an agentic product, but pushing nearly everything to software and rules is producing a large rule engine instead. The register agrees — **76 of 94 features in the cut involve no language model at all (81%)**, pure software is 44% and pure rules 27%. The old framing presented that as an achievement, which was quietly steering the design. The separation law governs **authority, not capability**: deterministic code owns authority, arithmetic and anything a technician's safety rests on; the agent should own what to look at, what to ask next, what to say and when to stop. Four decisions are marked **under review** because judgment currently sits in rules — `C4` what evidence to gather, `RC12` which question next, `RC19` are these one problem, `RC14` have the returns gone. All three shares are now computed from the register rather than typed | Claude |
| 2026-08-11 | Agenda §1.8 added — the grouping questions, raised as **our inference reviewed by nobody**: can one fouled condenser produce four of the five labels chiller 1 held on 15 April, and more importantly **which labels must never be grouped**, since hiding a real second fault costs a compressor where a duplicate visit costs a morning. Q47 logged. `mvp/VISHNU-TEAMS.md` added for chat, with §1.8 moved to the front because the bottom of a Teams message does not get read | Claude |
| 2026-08-11 | `scripts/build_pdf.py` added — markdown to PDF through Chromium, since there is no pandoc or LibreOffice here and adding one to send a nine-page document would be disproportionate. Its `--check` gate immediately caught what prompted it: `SME-REVIEW.pdf` was a day behind its source and **missing both §1.4b and §1.8** — the sections the hour is meant to spend itself on. The PDF is the artefact that reaches Vishnu, so that pair needed a gate | Claude |
| 2026-08-11 | Cases 13–15 added, all three measured rather than imagined: two labels that contradict each other (one machine-day carried both `CONDENSER_LOW_FLOW`, which implicates the water side, and `HIGH_HEAD_AMBIGUOUS`, whose negative residual argues it does not), same fault on two machines with only one trustworthy model (nRMSE 48.03 against 2.65), and off-not-broken (~23,800 of 31,884 slots zero across every signal, a 25% duty cycle). Fifteen cases now: ten wholly inside the cut, five partly, **none wholly outside**. The case list also gained a markdown source in `MVP-SCOPE.md` — it had existed only in the HTML. Fixed a wrong ID in the sub-case table (`F2` residual computation cited where `F3` operating gates was meant) and a stale "eight cases" comment | Claude |
| 2026-08-11 | `RC19` case correlation registered after measuring the inflation: twelve equipment-days carried a fault and a naive case per equipment-day-label gives **39**, a 3.25× ratio — and on 2026-04-15 chiller 1 held **five labels at once**, so one plausible repair could raise five work orders. Case 12 rewritten with its eight sub-cases and a real example each; four of them occur with two chillers and features already in the cut, so deferring Alerts never deferred the duplicate-work-order risk. 94 of 147. Decision D-011. Q46 raised: no document states a target turn time, and the number is not ours to invent | Claude |
| 2026-08-11 | Coverage audit across every markdown file and both pages for models, roles, personas, specialists, routes, workflows and pipelines. Four gaps found and closed: the **model-role indirection** and **reasoning on/off per task** were in no page (now 13.11), the **five-layer defence stack** and the **resource ceilings** were on no page at all (now 13.14 and 13.15), and **the eight surfaces** existed *only* in the HTML with no markdown record (now `CONTEXT.md` §10d). Everything else was already in both | Claude |
| 2026-08-11 | `docs/20-architecture/03-from-thermynx.md` — the consolidated record of what we take from Thermynx and what we leave: model roles (code never names a model), reasoning on/off per task, the ten agent families and their boundaries, the **five-layer defence stack** with its soft final gate, the injection fencing, the **honesty layer's five signal states enforced by a constructor rather than an instruction**, the four rules that ship with every figure, the proven five-line playbook shape, the one-way code dependency that lets 322 tests run with the GPU off, ten resource ceilings, the eight-layer routing ladder and the five observability capture layers. Its most important paragraph is theirs: the honesty layer shipped with a reassuring lie that **56 unit tests, a clean typecheck and a 100% eval score all missed, and reading one live report caught** — which is the argument for `EV4` staying in the cut | Claude |
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
