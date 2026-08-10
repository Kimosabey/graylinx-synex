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

### T1 — Apply the Synex rename (do this first)
Rewrite the product identity across `Graylinx_Enterprise_AI_Platform_v4.docx`
per the naming law in `CLAUDE.md` section 1. The review pack is already done —
match its wording.
**Done when:** `python scripts/verify.py` reports zero legacy-name hits, the
cover and headers read "Graylinx Synex", and every "AI Copilot" has become
"Synex Copilot". Do not touch the Thermynx relationship.

### T2 — Split the source documents into per-chapter markdown
Convert v4 into one markdown file per chapter under `docs/10-product/` and
`docs/20-architecture/`, keeping chapter numbers as filename prefixes. Preserve
all tables. Move the original .docx to `docs/90-archive/`.
**Done when:** every chapter is a separate file, `verify.py` passes, and no
content is lost (compare word counts and table counts before and after).

### T3 — Reconcile the feature register against the chapters
Every feature ID in `mvp/FEATURE-REGISTER.md` must be traceable to a chapter,
and every capability described in a chapter must have an ID.
**Done when:** `verify.py` reports zero orphan IDs and zero unregistered
capabilities.

### T4 — Produce the MVP build backlog
From the agreed MVP cut, produce `mvp/BACKLOG.md`: one entry per feature with
its dependencies, the data it needs, and the open questions that block it.
**Blocked by:** a human agreeing the MVP cut.

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
| 2026-08-10 | Brand colour `#0020B0` issued and recorded as D-001; `scripts/palette.py` added to derive and audit the whole colour system from it; `brand/NAMING.md` Visual identity replaced. 72 of 72 rendered pairs pass WCAG 2.2 AA in both themes, body text at AAA | Claude |

_Append a row here for every change. This table is how the next session finds
out what happened._
