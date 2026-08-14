# Decision log

Every decision that changes what gets built goes here, then into the affected
chapters. If it is not in this file, it did not happen.

## Format

```
### D-nnn — Short title
- **Date:**
- **Decided by:**
- **Closes:** (Qn / Nn, if applicable)
- **Decision:**
- **Reason:**
- **Affects:** chapters, feature IDs
- **Reflected in docs:** yes / no / partial
```

---

### D-001 — The Graylinx brand colour is `#0020B0`, and the design system is derived from it
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing — this is a new decision, not an answer to an open question
- **Decision:** `#0020B0` (International Klein Blue) is the brand colour. The
  full colour system — brand, neutral, success, warning and danger ramps, plus
  the light and dark semantic tokens — is generated from that single value by
  `scripts/palette.py`. `--accent` is the brand hex unmodified. The placeholder
  palette in `brand/NAMING.md` (`#0F3D5C` / `#1B6E9C`) is superseded and must not
  be reintroduced. Light is the default theme; dark is an explicit opt-in rather
  than an OS preference.
- **Reason:** `brand/NAMING.md` reserved that section to be replaced when a brand
  palette was issued, and one now has been. Deriving the whole system from one
  input rather than hand-picking values means the palette can be regenerated,
  and — more importantly — audited: `--audit` checks all 72 rendered pairs
  against WCAG 2.2 in both themes and fails the build rather than the user.
  Neutrals are placed on the brand hue so the greys belong to the blue.
- **Affects:** `brand/NAMING.md` (Visual identity replaced), `scripts/palette.py`
  (new), `mvp/MVP.html`, `assets/logo.png`. No feature IDs.
- **Reflected in docs:** yes for `brand/NAMING.md` and `mvp/MVP.html`. The v4
  source document in `docs/00-source/` still carries the placeholder palette and
  will pick this up when task T2 splits it into per-chapter markdown.

### D-002 — The MVP cut grows from 51 to 69 after the Thermynx flow review
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing. S1 remains open — it now closes on 69 features, not 51
- **Decision:** Four groups of capability were in daily use in the existing
  Thermynx implementation, or are required for the loop to close, and were named
  nowhere in this register. They are registered and taken into the cut:
  the conversation shell `C15`–`C20`, the case-resolution lifecycle `RC1`–`RC8`,
  energy and cost `E1`–`E4` (only `E1` in the cut), and the three personas the
  loop cannot close without, `U6`–`U8`. Two new prefixes: `RC` and `E`.
- **Reason:** the earlier cut described a loop that went from a named fault
  straight to a work order. That hop does not exist in practice — somebody
  answers questions first, and some answers come back "could not check". The
  register also assumed a chat surface without naming any of it, while the
  Copilot is the product's differentiator. Registering these makes them
  reviewable; leaving them implicit meant they would be built without a spec.
- **Affects:** `mvp/FEATURE-REGISTER.md`, `mvp/MVP-SCOPE.md` (13 acceptance
  criteria, 10 stages), `CONTEXT.md` §9–§11, `CLAUDE.md` §2 rule 7,
  `scripts/verify.py` `ID_PREFIX`, `mvp/MVP.html`.
- **Reflected in docs:** yes.

### D-003 — Synex inherits Thermynx's platform decisions rather than re-litigating them
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision:** The shared graylinx-v2 database, the Jarvis GPU box and the
  existing stack are used as they are. Thirteen decisions taken before this
  programme, with reasoning recorded against source, are adopted as settled
  truth and listed in `CONTEXT.md` §10. Where one of them constrains a feature,
  the register row says so.
- **Reason:** each of the thirteen was paid for. Two in particular were learned
  the hard way — six "N/A" presses once opened a blocking safety gate with no
  evidence behind it, and ranking checklist routing by seniority once sent a
  filter-drier restriction to a supervisor over three refrigeration
  measurements. Rediscovering those in production is not a reasonable plan.
- **Affects:** `CONTEXT.md` §9–§11; constrains `RC2`, `RC3`, `RC4`, `RC5`,
  `RC7`, `F7`, `F9`, `V7`, `W4`.
- **Reflected in docs:** partial. The constraints are in `CONTEXT.md`; the v4
  source document does not yet mention them and will pick them up at task T2.
- **Note:** three of the thirteen are open capability gaps rather than settled
  design — no interim holding action, no retraction mechanism, and duplicated
  checklist work under event grouping. They are inherited as unsolved. See Q19.

### D-005 — Synex gets its own database, cloned from graylinx_v2
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision:** `graylinx_synex` is cloned from `graylinx_v2` and is the only
  database Synex writes to. 193 tables, 3,879 MB. `CONTEXT.md` §9 previously said
  Synex used the shared platform database; it does not.
- **Verification, completed 2026-08-11:** every row in every table of all three
  databases counted, not a sample. `graylinx_v2` and `graylinx_synex` are identical on
  all 193 tables and on 14,271,741 rows, with no table present in one and absent from
  the other, and no views, routines or triggers anywhere to be missed. Against `shiva`
  the copy is a strict superset: two extra tables and 313,424 extra rows, all
  attributable to the simulation. Zero registry entries fall at or before the measured
  boundary and the simulation log records `gaps_filled=False`, so not one measured slot
  was overwritten. See `docs/20-architecture/00-data-model.md`.
- **Reason:** the lineage already has this shape. `shiva` is the customer snapshot
  and stays read-only; `graylinx_v2` exists as a writable copy so nothing done to
  the data can corrupt the original. Staging demo scenarios for a pitch is exactly
  the kind of work that argument was made for, and doing it in `graylinx_v2` would
  disturb a copy that is in active use. A third generation costs 4 GB of disk.
- **Note on what came with it:** 156,129 slots in the copy are **simulated** — the
  real snapshot ends 2026-06-23 and a simulation extends it to 2026-08-05.
  `snapshot_simulated_slots` names every synthetic pair, so the two can always be
  told apart. Anything shown over a simulated window must say so, on the same
  principle as `C23`. A pitch that quietly presents generated data as measured is
  the exact failure this product argues against.
- **Affects:** `CONTEXT.md` §9. No feature IDs.
- **Reflected in docs:** yes.

### D-006 — Synex is an AI layer on the existing Graylinx platform, and this MVP is built to be shown
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing. N1 remains open — this is about the Graylinx platform, not
  about Thermynx
- **Decision:** Synex plugs into the existing platform rather than replacing it, and
  this MVP's purpose is demonstration: the pitch, the differentiation, and the
  argument for the approach.
- **Reason:** it explains the shape of the cut, and it is better written down than
  inferred. A demonstrator has to close the loop *completely* and does not have to
  be broad — which is why one asset class on one site with verification beats ten
  domains that cannot prove anything. It also sets a bar the honesty rules already
  meet: a demonstration that overstates what the data supports is worth less than
  one that shows the platform refusing.
- **Affects:** `CONTEXT.md` §9a. No feature IDs.
- **Reflected in docs:** yes.

### D-012 — The build is a monorepo, and the layering direction in `03-from-thermynx.md` §6 is corrected
- **Date:** 2026-08-13
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision, part one:** application code lives in this repository beside the
  documentation — `backend/`, `frontend/`, `infra/` alongside `docs/`, `mvp/`, `decisions/`,
  `brand/` and `scripts/`. None of the existing directories move, because `netlify.toml`,
  `scripts/build_site.sh` and `CLAUDE.md` §3 all depend on where they are. The Python
  package is named `app`, so the ported modules need no import edits.
- **Decision, part two:** the one-way dependency order is
  **`api → agents → services → analytics · retrieval → llm · prompts → db → domain`**,
  enforced by import-linter contracts from the first commit.
- **Reason the chapter needed correcting:** §6 lists the order as
  `api → services → analytics → ai → db → domain`, placing the probabilistic layer
  *below* services and analytics. That cannot be satisfied. A LangGraph agent loop is an
  orchestrator: it must call services and read analytics. The sibling implementation's own
  import graph proves it — `ai → services` seven times, `ai → analytics` five times, and
  `services → ai` seven times. Fifteen back-edges and one cycle, in a codebase whose
  docstrings state the rule. **An unsatisfiable contract is not a strict rule, it is a rule
  that gets switched off in week two.**
- **What the chapter got right, and keeps:** the *containment*. `analytics` and `domain`
  stay pure — no DB, no LLM, no I/O. `services` holds no prompts and makes no model calls.
  Everything probabilistic stays in one place so it can be gated. A prompt change still
  cannot alter a state transition, because the transition validator never sees a prompt.
  Those three consequences are why the rule exists and all three survive the reorder.
- **Three moves eliminate every back-edge rather than excusing it:**
  - `assess_checks` and `escalation_target` drop to `domain`. Both are pure and LLM-free, so
    they are domain constants rather than AI — and escalation must work with the GPU off.
  - the tool-payload sanitiser drops to `domain/untrusted_text.py`. Treating text as hostile
    is a domain rule, and `RC4` technician findings need it from the services side anyway.
  - RAG becomes its own `retrieval` layer below services.
- **Affects:** `docs/20-architecture/03-from-thermynx.md` §6 amended,
  `docs/20-architecture/04-code-layering.md` (new), `backend/importlinter.ini`. No feature IDs.
- **Reflected in docs:** yes.

### D-013 — A persona switcher with no authentication closes `Q41` for the MVP without answering it
- **Date:** 2026-08-13
- **Decided by:** Harshan
- **Closes:** `Q41`, for the MVP only. The production route stays open
- **Decision:** identity for the demonstration is a persona switcher with **no
  authentication**, labelled in the interface as a demonstration affordance. Every audit row
  carries `identity_kind='demonstration_persona'`, so it cannot silently become production
  auth. Scope is recomputed every turn and never inherited.
- **Reason:** `G1` is `P0` and four personas need a scope, so the Control Plane cannot be
  built without *an* identity — but `gl_user`, `gl_role` and `gl_access` hold zero rows in
  the snapshot and there is no authentication library in the inherited back end. The
  switcher lets `G1`'s scoping logic be built and tested against a known identity while
  leaving all three real routes open. `AUTH_MODE` carries them as
  `dev_jwt` / `signed_header` / `oidc`.
- **Reason it is recorded rather than assumed:** under schedule pressure this is exactly the
  kind of question that gets answered by default. Writing it down makes the default a
  decision.
- **Affects:** `backend/app/api/deps.py`, `backend/app/services/control_plane.py`,
  `frontend` persona control. Constrains `G1`–`G4`, `U3`, `U6`–`U8`.
- **Reflected in docs:** yes.

### D-014 — The FDD models are consumed, not built, and `F1`/`F2` are reclassified
- **Date:** 2026-08-13
- **Decided by:** Harshan
- **Closes:** nothing. It removes `Q1`, `Q2` and `Q14` from the build critical path
- **Decision:** Synex reads the residuals the Graylinx platform already computes. The six
  regression models are not code we own. `gla_model_residuals_wc`,
  `gla_residual_stats_wc`, `gla_equipment_model_params` and `gla_equipment_model_metrics`
  hold the residuals, the per-asset bands, the coefficients and the fit quality, so `F1` and
  `F2` are a read-only repository layer plus one band function. **Their `Engine` column is
  `SW`, not `ML`.**
- **Reason:** inherited constraint 34 says never re-detect. Re-fitting models we do not own,
  against a snapshot, to reproduce labels that already exist would add a second source of
  truth for the one thing the separation law says must have exactly one.
- **What this changes about sequencing:** `mvp/MVP-SCOPE.md`'s Stage 1 depends on `Q1`, `Q2`
  and `Q14`, and everything else queues behind it — which draws the whole build behind a site
  survey. But the residuals and labels exist on the measured window regardless of whether
  condenser flow is measured at a *future* site. **`Q1` blocks a claim about a target site,
  not a build step**, and the designed response to it — `NO_DIAGNOSIS` plus a data-quality
  work order — is already the behaviour.
- **What it does not change:** five models are fitted per chiller, not six.
  `compressor_power_residual` is 100% NULL, and it is rendered as a stated absence rather
  than omitted, because omission is the failure constraint 14 exists to prevent.
- **Affects:** `mvp/FEATURE-REGISTER.md` (`F1`, `F2` engine), `mvp/MVP-SCOPE.md` sequencing,
  `backend/app/db/telemetry.py`, `backend/app/analytics/`.
- **Reflected in docs:** yes.

### D-015 — `NO_DIAGNOSIS` gets its own streaming frame
- **Date:** 2026-08-13
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision:** the streaming contract carries a `no_diagnosis` frame of its own, holding the
  gate that failed, the reason, and what would change the answer. It renders as a distinct
  state rather than as answer text, and it increments `no_diagnosis_total{gate}` from the same
  place.
- **Reason:** the inherited implementation emits a refusal as a `token` frame, so the
  interface cannot style a refusal differently from an answer. `CLAUDE.md` §2.6 says
  `NO_DIAGNOSIS` is a feature and must never be softened — and rendering a refusal in the same
  typeface as a confident answer **softens it by presentation**. On this data the refusal is
  also the modal outcome: 5,309 slots against 674 faulted ones. A state that common needs to
  look deliberate.
- **Consequence worth naming:** the frontend port is therefore not a pure port. Recording it
  so the divergence is a decision rather than a surprise during the port.
- **Affects:** `backend/app/agents/sse_frames.py`, `frontend` turn rendering,
  `scripts/verify_sse_contract.py`. Constrains `C7`, `F8`.
- **Reflected in docs:** yes.

### D-011 — One problem must not become five work orders: `RC19`
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing. It takes on one of the three gaps inherited as unsolved under Q19
- **Decision:** `RC19` case correlation before escalation joins the cut. Cut goes from 93
  to 94 of 147. A case may not raise a work order until it has been checked against open
  cases on the same equipment within a window:
  - **same label** → reopen the existing case rather than open a second;
  - **different labels sharing a candidate cause** → group under one investigation, with
    **one** work order;
  - **an instrument fault in the group** → the instrument case leads and the others hold,
    because a dead sensor can produce several fault labels at once.
- **Reason, measured on our own window:** twelve equipment-days carried a fault, and a
  naive case per (equipment, day, label) yields **39** — a 3.25× inflation. On 2026-04-15
  chiller 1 carried **five labels simultaneously**: `CONDENSER_LOW_FLOW`,
  `HIGH_HEAD_AMBIGUOUS`, `POWER_HIGH_UNEXPLAINED`, `REFRIGERANT_SIDE_HIGH_HEAD` and
  `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION`. 2026-04-17 is another five, and ten of
  chiller 1's twelve fault days carry more than one label. A fouled condenser plausibly
  explains four of those five at once, so the honest case count is one and the naive one
  is five — five work orders, five visits, five checklist runs.
- **Why it is not an Alerts feature:** the case that describes it, case 12, is currently
  outside the cut because it needs `L1`–`L4`. But four of its sub-cases occur with two
  chillers and the features already in the cut, so deferring the Alerts domain does not
  defer the duplicate-work-order risk. `G5` prevents a **retry** creating a second work
  order; nothing prevents two genuinely distinct cases about one physical problem each
  raising one.
- **Why grouping is proposed and never silent:** a wrong grouping hides a real second
  fault, which is worse than a duplicate visit. This is `RC12`'s rule one level up — a
  confirmation never eliminates its siblings, and by the same argument a grouping never
  closes its members. A human sees what was grouped, and can split it.
- **What is deliberately not claimed:** correlation across *equipment* — a cooling tower
  starving both chillers — is a real production risk and **cannot be demonstrated on our
  data**: there are zero slots where both chillers carried a fault simultaneously. `RC19`
  scopes to one equipment for that reason, and the cross-equipment case stays with the
  Alerts domain.
- **Affects:** `mvp/FEATURE-REGISTER.md`, `mvp/MVP-SCOPE.md`,
  `docs/20-architecture/00-data-model.md`, `mvp/MVP.html`.
- **Reflected in docs:** yes.

### D-010 — The Thermynx stack is inherited whole, including two refusals
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing. Raises Q41, Q42, Q43
- **Decision:** Synex uses the existing stack as it stands, and adopts its **refusals**
  as well as its choices. Recorded in full in `docs/20-architecture/01-stack.md`;
  the deployment shape in `02-deployment.md`.
  - **Evaluation: DeepEval** with a local Ollama judge, plus `pytest`. A stronger cloud
    judge stays available, lazy-imported, pointed only at the **synthetic** golden set —
    so a hard case can be judged well with zero egress.
  - **Observability: Prometheus, Grafana, Loki, Alertmanager**, already in the compose
    file behind `profiles: [obs]`. We run with that profile **on**, which is a
    configuration change rather than new technology.
  - **Refused: Ragas.** Not unchosen — removed there on 2026-06-10 because it
    hard-imports a class langchain 1.x deleted, and pinning low enough to restore it
    breaks langgraph. Their note calls it *"the ADR-0001 framework-churn risk, realized.
    Do not re-add without a stack bump."*
  - **Refused: Langfuse.** Integrated and then deliberately disabled: self-hosting v3
    needs five more containers. For an on-premise product that is five more things a
    customer must accept, patch and back up, and Prometheus answers the same question.
  - **Refused: `scikit-learn`.** The six models are OLS; `statsmodels` and `numpy`
    already do it. Adding an ML framework to compute an RMSE is how a stack drifts.
- **Reason:** every one of these has a reason recorded against it, which is the only
  thing that makes D-003's "inherit rather than re-litigate" safe. Two of them are
  refusals with an incident behind them, and a refusal is easier to reverse by accident
  than a choice — so they are written down here rather than left implicit in a
  requirements comment in another repository.
- **What this closes without work:** `arq` is already installed, so `RC17` is a
  scheduled job and a visible counter rather than a component — the Thermynx failure was
  a scheduler nobody pointed at the seed. `echarts` is already in the frontend, so `C24`
  has its charting library. `@axe-core/playwright` is already there, so the WCAG work on
  the design system is testable in CI rather than by eye.
- **What it does not settle:** identity has no library at all and the snapshot's user and
  role tables are empty (Q41); the plant database is read-only by convention rather than
  by grant (Q42); and there is no application image or offline wheel bundle (Q43).
- **Affects:** `CONTEXT.md` §9, `docs/20-architecture/01-stack.md` and `02-deployment.md`
  (both new), `mvp/MVP.html`. No feature IDs.
- **Reflected in docs:** yes.

### D-009 — The demonstration window is the real one, because our database invented condenser flow
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing. It sharpens `Q1` considerably
- **Decision:** Three parts.
  1. **A demonstration runs on the measured window**, 2026-03-04 to 2026-06-23, unless
     a specific reason says otherwise and the synthetic signals in the chosen window
     have been checked one by one.
  2. **`C26` per-signal provenance joins the cut.** A signal is labelled *measured*,
     *simulated*, or *not instrumented here*. `C23` marks a window; `C26` marks the
     signal inside it.
  3. **A signal the site cannot measure is never presented as a reading**, in any mode,
     regardless of what the database contains.
- **Reason:** measured on `graylinx_synex`, every numeric column on
  `chiller_1_normalized` compared across the real and simulated windows. Of 32
  columns, exactly one differs *in kind*: `cond_flow` has **zero** non-zero values in
  31,884 real slots, and **3,354** synthetic values reaching 893.7 in the simulated
  window. `chiller_2_normalized` matches, with 3,592 reaching 1,099.6.
- **Why this one signal matters more than the rest:** condenser flow is what
  `CONTEXT.md` §6 calls the highest-leverage single measurement. Four of the six models
  depend on it, and *"flow is at design"* eliminates three of five causes in the
  `CONDENSER_WATER_SIDE_UNSPECIFIED` differential. The one signal that decides the most
  is the one our database fabricated.
- **Why disclosure alone does not fix it:** the natural demonstration window is the most
  recent data, which runs to five days ago and is entirely synthetic. Labelling it
  *simulated* would still leave the audience watching condenser flow read healthily,
  the models resolve cleanly and the differential narrow with confidence — on a
  measurement the plant **cannot take at all**. Every other synthetic signal continues
  something the plant genuinely measures. This one implies an instrumentation
  capability that is not there, and that is a different and worse claim.
- **Side effect worth reporting upstream:** Thermynx's `Q-A11` asks what feeds
  `chiller_flow` now that `dpt` is NULL, recorded as verified finding VF4. In the
  simulated window `dpt` is absent and `chiller_flow` is synthesised directly, so the
  documented derivation is not broken — it is not being applied, because that window
  was generated. Their observation was made on data running through August, inside the
  simulated span. A candidate explanation, not a confirmed one, and cheap to check.
- **Affects:** `mvp/FEATURE-REGISTER.md` (`C26`), `mvp/MVP-SCOPE.md`, `CONTEXT.md` §10a,
  `docs/20-architecture/00-data-model.md` (new), `mvp/MVP.html`.
- **Reflected in docs:** yes.

### D-007 — A detected fault that never reaches the queue is registered as `RC17`
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision:** `RC17` detection-to-queue reconciliation joins the cut. A detected
  episode reaches the queue on a schedule, and the count of detected-but-not-queued
  is displayed rather than assumed to be zero. Cut goes from 89 to 90 of 143.
- **Reason:** the Thermynx FDD sequencing brainstorm records 22 detected episodes
  covering 612 slots — including the only two of `critical` class — sitting in the
  detector and never reaching the queue. The seeding call is idempotent by
  construction and nothing scheduled it. `RC8` already registers that the seed is
  safe to re-run; nothing registered that it runs, and the gap between those two
  statements is where a plant with unreported critical faults hid. The brainstorm
  calls fixing it *"the highest-value action in this entire workspace"*, and it is a
  single scheduled call.
- **Reason the count is shown rather than trusted:** the failure was silent. A queue
  that is quietly incomplete reads exactly like a queue that is complete, so the
  reconciliation has to be visible to be worth anything.
- **Affects:** `mvp/FEATURE-REGISTER.md`, `mvp/MVP-SCOPE.md`, `mvp/MVP.html`.
- **Reflected in docs:** yes.

### D-008 — Two more gaps from the FDD register: stored evidence, and a single severity scale
- **Date:** 2026-08-11
- **Decided by:** Harshan
- **Closes:** nothing
- **Decision:** `RC18` and `F17` join the cut. Cut goes from 90 to 92 of 145.
- **Reason for `RC18` (Thermynx gap register, item 18):** four readings the checklist sent a technician to
  take were columns on the same normalised table the model had just read — oil
  pressure, compressor balance, condenser approach, ambient. The operator is asked to
  go and fetch a number the system already holds, and the model reasons about a fault
  while blind to a signal in the same row. It is the same defect that produced the
  `MODEL_BLIND` incident, diagnosed there as *"the library knew; the evidence pack did
  not carry it"* — and fixed for that one fact rather than generalised.
- **Reason it is not a pure win:** a number in the snapshot is not a gauge reading
  now, and on a plant whose instruments are demonstrably unreliable, showing a stored
  value as though it were a measurement is its own hazard. So `RC18` fixes the wording
  as well as the behaviour — *confirm at the panel*, never *this is* — and a stored
  reading never settles a blocking check on its own. That keeps it consistent with
  `RC10`, which already says only a measured answer opens a gate.
- **Reason for `F17` (Thermynx gap register, item 13):** two functions with the same name returned different
  severity scales and disagreed on four of seven fault classes, all four rated
  `critical` by one and `high` by the other. The impact was latent only because the
  second path defaulted to off; enabling it would have shown the same fault at two
  severities on two screens. Severity is how bad the fault is and `W4` decides when
  the work happens — one number, read from one place, by everything.
- **Affects:** `mvp/FEATURE-REGISTER.md`, `mvp/MVP-SCOPE.md`, `mvp/MVP.html`.
- **Reflected in docs:** yes.

### D-004 — The FDD instrumentation reality is recorded, and four gaps are closed
- **Date:** 2026-08-10
- **Decided by:** Harshan
- **Closes:** nothing. It sharpens Q1 and Q2 and raises Q21–Q27
- **Decision:** The findings from the Thermynx FDD discovery pass are recorded in
  `CONTEXT.md` §10a as evidence about instrumentation reality, and four
  capabilities are added because each closes a gap that already produced a real
  incident there: `C23` untrusted-window marking, `RC9` case ageing and
  auto-stale, `RC10` measured-versus-estimated per finding, and `S6` a
  stop-the-machine response class. Cut goes from 75 to 79 of 132.
- **Reason:** the discovery pass found that condenser flow has never recorded a
  non-zero value at the reference plant. That is the signal `CONTEXT.md` §6 calls
  the highest-leverage single measurement, feeding four of six models. It does not
  change what we build, but it changes what the MVP can honestly promise, and a
  roadmap that assumes the FDD half is nearly done would be wrong. The other three
  additions each have an incident behind them: an untagged finding defaulting to
  *estimated* opened a blocking gate; twenty-two detected episodes never reached
  the queue; four open cases described transmitters repaired weeks earlier. `S6`
  exists because that taxonomy had no safety impact class at all — every
  escalation route ended in a work order, so there was no way to say stop now.
- **Reason it is not deferred:** three of the four are one-line rules. The
  expensive one is `S6`, and it is the one whose absence is least acceptable.
- **Affects:** `mvp/FEATURE-REGISTER.md`, `CONTEXT.md` §10 (constraints 20–22)
  and §10a, `decisions/OPEN-QUESTIONS.md` (Q1, Q2 restated; Q21–Q27 added),
  `mvp/MVP.html`.
- **Reflected in docs:** yes.
- **Note:** the evidence is from one plant's snapshot. Whether the target sites
  match it is exactly Q1 and Q2, and those remain the highest-leverage questions
  in the programme.
