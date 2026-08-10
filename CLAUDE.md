# CLAUDE.md — Operating rules for this repository

You are working on **Graylinx Synex** product and architecture documentation.
Read `CONTEXT.md` before writing anything. Read `HANDOFF.md` to find out where
things currently stand.

---

## 1. The naming law

This is the rule broken most often, so it comes first.

| Use this | Never use this |
|---|---|
| **Graylinx Synex** (first mention), **Synex** (after) | "Graylinx Enterprise AI Platform", "the AI platform", "GEAP" |
| **Synex Copilot** (first mention), **the Copilot** (after) | "the chatbot", "the AI assistant", "Graylinx AI Copilot", "the bot" |
| **Synex FDD**, **the FDD engine** | "the AI diagnosis", "the AI brain" |
| **the agentic layer**, **the language model** | "the AI" used as a catch-all noun |

`Synex` is always capitalised, never `SYNEX` or `synex`, except in a filename.
Never write "Synex AI" — the AI is implied and the doubling reads badly.

**Open naming question N1 is unresolved:** the relationship between Synex and
the existing Thermynx platform. Until a human answers it, do not write any
sentence that positions one as replacing, containing or superseding the other.
See `decisions/OPEN-QUESTIONS.md`.

---

## 2. Hard rules

1. **Never rename a thing back.** If you find an old name, fix it and note the
   file in your summary. Do not "preserve the original wording" for old names.
2. **Never invent a number.** No metric, threshold, page count, percentage or
   model coefficient may appear unless it is in `CONTEXT.md`, in a source
   document under `docs/00-source/`, or explicitly given to you in the prompt.
   If a number is needed and unavailable, write `TBD (see Qn)` and add the
   question to `decisions/OPEN-QUESTIONS.md`.
3. **Product first, architecture second.** Any document that mixes them puts
   user value before implementation. This is not negotiable and has been
   re-litigated twice already.
4. **Plain English in product sections, precise terms in architecture
   sections.** Do not "simplify" a technical term by expanding it inline — that
   is what produced the phrase damage listed in section 4. Use the precise term
   and let the glossary carry the plain meaning.
5. **The language model never diagnoses.** Any sentence implying the LLM names
   a fault, grants a permission, or decides a priority is wrong. The FDD rules
   name the fault; the Control Plane grants permission; a deterministic formula
   sets priority. See `CONTEXT.md` section 5.
6. **NO_DIAGNOSIS is a feature.** Never soften it, never let a document imply
   the platform will produce an answer when gates fail.
7. **Feature IDs.** Prefixes are `C` Copilot, `R` Reports, `W` Work Orders,
   `A` Asset, `F` FDD, `K` Knowledge, `PL` Planning, `I` Inventory, `L` Alerts,
   `V` Verification, `U` Roles, `S` Safety, `G` Control Plane. Planning uses
   `PL`, not `P`, because `P0`/`P1`/`P2` are priority labels and a single-letter
   `P` collides with them. Never introduce a prefix that collides with a
   priority or a phase label.
8. **One source of truth per fact.** The feature register lives in
   `mvp/FEATURE-REGISTER.md` and nowhere else. If a chapter needs the feature
   list, it references IDs; it does not restate them.

---

## 3. Where things go

```
docs/00-source/      read-only inputs. Never edit. Never delete.
docs/10-product/     product chapters (what users get)
docs/20-architecture/ architecture chapters (how it is built)
docs/90-archive/     superseded editions, kept for traceability
brand/               naming, palette, typography
decisions/           open questions and the decision log
mvp/                 scope and the feature register
scripts/             build and verify
```

Write new chapters as individual markdown files with a numeric prefix
(`10-product/03-synex-copilot.md`). One chapter per file. Never create a file
that duplicates a chapter that already exists — extend the existing one.

---

## 4. Banned phrases

A previous global find-and-replace expanded technical terms into long phrases
and damaged the document. `scripts/verify.py` fails the build if any of these
reappear. Do not reintroduce them, and fix them on sight:

| Banned | Correct term |
|---|---|
| "checking that the work really worked" | verification |
| "checking that the answer is based on real information" | grounding |
| "where the data came from and how it was calculated" | lineage |
| "proof / supporting data" | evidence |
| "how important the equipment is" | criticality |
| "sending the issue to the right person/team" | escalation |
| "finding the likely problem" | diagnosis |
| "difference between expected and actual readings" | residuals |
| "based on real available information" | grounded |
| "access area" / "access aread" | scope / scoped |
| "limited mode" | degraded mode |
| "permission check" (as a noun for authority) | authorization |
| "built around AI from the start" | AI-native |
| "testing and proof" | validation |
| "standard procedure" (when it means the document) | SOP |
| "document search" (when it means the technique) | RAG |

---

## 5. Definition of done

A change is done when all of these hold:

- [ ] `python scripts/verify.py` exits 0
- [ ] No new numbers without a source
- [ ] Naming law respected throughout the changed files
- [ ] Any new decision recorded in `decisions/DECISIONS.md`
- [ ] Any new unknown recorded in `decisions/OPEN-QUESTIONS.md`
- [ ] Feature IDs referenced, not restated
- [ ] The change is summarised in `HANDOFF.md` under "Recent changes"

---

## 6. When to stop and ask

Stop and ask a human rather than deciding, when:

- The answer depends on how the equipment actually behaves (that is Vishnu's call)
- The answer changes what gets built in the MVP
- Naming question N1 (Synex vs Thermynx) would need to be resolved to proceed
- A source document contradicts `CONTEXT.md`
- You would need to delete more than one existing chapter

Everything else: proceed, and note the assumption in your summary.
