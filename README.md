# Graylinx Synex — documentation workspace

> **Graylinx Synex — Intelligent Operations, Connected by AI**
> Kingpin: **Synex Copilot**, the intelligent operating layer for Graylinx.

This repository holds the product and architecture documentation for Synex, and
the working artefacts we iterate on toward the MVP.

## Start here

| If you are | Read |
|---|---|
| Claude Code, starting a session | `CLAUDE.md`, then `CONTEXT.md`, then `HANDOFF.md` |
| A person picking this up | `CONTEXT.md`, then `mvp/MVP-SCOPE.md` |
| Reviewing with the SME | The Feature Review Pack in `docs/00-source/` |
| Looking for what is unresolved | `decisions/OPEN-QUESTIONS.md` |

## Layout

```
CLAUDE.md                  operating rules for this repo
CONTEXT.md                 settled product truth
HANDOFF.md                 state, next tasks, blocking questions
brand/NAMING.md            naming law, palette, typography
decisions/
  OPEN-QUESTIONS.md        everything unresolved, with owners
  DECISIONS.md             the decision log
mvp/
  FEATURE-REGISTER.md      source of truth for all feature IDs
  MVP-SCOPE.md             proposed MVP cut and acceptance criteria
docs/
  00-source/               read-only inputs — never edit
  10-product/              product chapters
  20-architecture/         architecture chapters
  90-archive/              superseded editions
scripts/
  verify.py                compliance gate — must exit 0
  build_docs.py            markdown to docx / pdf
```

## Commands

```bash
python scripts/verify.py               # must pass before any commit
python scripts/verify.py --strict      # also fails on unreferenced TBD markers
python scripts/verify.py --fix-names   # rewrite legacy product names in place
python scripts/build_docs.py           # build docx from markdown
python scripts/build_docs.py --pdf     # build docx and render a PDF
```

Windows: use `py` in place of `python` if it is not on PATH.

## The two rules people break

1. **The language model never diagnoses.** The FDD rules name the fault; the
   Control Plane grants permission; the model explains. `verify.py` fails on
   sentences that say otherwise.
2. **Never invent a number.** If it is not in `CONTEXT.md` or a source
   document, write `TBD (Qn)` and add the question.
