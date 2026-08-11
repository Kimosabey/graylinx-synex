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
  database Synex writes to. 193 tables, 3,879 MB, verified table by table and by
  exact row count on the largest eight. `CONTEXT.md` §9 previously said Synex used
  the shared platform database; it does not.
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
