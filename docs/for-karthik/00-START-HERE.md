# Synex — Knowledge Transfer for Karthik

This folder is everything you need to pick up Synex and keep building on it. It has two halves,
and reading them in the wrong order will cost you a day.

**The six numbered files here are the working half** — how to run it, what happens inside the
Copilot, what has already gone wrong, how it is tested, a five-day plan, and the handover
checklist. Read those in order, starting with `01-running-synex.md` **today**, before any of the
reference material below. Reading about a system you cannot see running is far harder than
reading about one you can click through.

| File | Roughly | What it is for |
|---|---|---|
| **[01-running-synex.md](01-running-synex.md)** | 30 min, hands on | Get it on screen. Do this first. |
| **[02-the-copilot-end-to-end.md](02-the-copilot-end-to-end.md)** | 45 min | **The most important one if you own the AI side.** One question, all the way through, and what each model is forbidden from doing. |
| **[03-known-issues-and-landmines.md](03-known-issues-and-landmines.md)** | 30 min | **Read before changing anything in the AI code.** Real defects that reached a running system, and the shape they share. |
| **[04-testing-and-evaluation.md](04-testing-and-evaluation.md)** | 20 min | Four offline gates, two live suites, and which green tick means what. |
| **[05-one-week-plan.md](05-one-week-plan.md)** | 15 min | **The scope boundary, and the week.** Build what `mvp/MVP-SCOPE.md` says, in the order it gives, and nothing else. Includes what is already built, what is blocked, and what is deliberately out. |
| **[06-handoff-checklist.md](06-handoff-checklist.md)** | 15 min | Access, verification, and the gaps stated plainly. |
| **[07-data-dumps.md](07-data-dumps.md)** | 10 min | **A clone gives you no data.** The two dumps you need, how to restore them, and how to tell a half-finished restore from a working one. |

**The rest of this file is the second half: the reading order for the repo's own documentation.**
Synex already has excellent, thorough docs — this maps them and connects them to what you know
from THERMYNX. It is not a replacement for them. Synex already has
excellent, thorough documentation — this file exists only to tell you what order to read it in,
and to connect it to what you already know from THERMYNX. Written 2026-08-24, based on this
repo's own `CONTEXT.md`, `HANDOFF.md`, `mvp/MVP-SCOPE.md`, `mvp/INHERITANCE-STATUS.md`, and
`decisions/OPEN-QUESTIONS.md` as of that date.

## What Synex is, briefly

Synex ("Intelligent Operations, Connected by AI") is a separate Graylinx product from THERMYNX —
built by the same team, reusing THERMYNX's database, GPU box, and model roster, but designed to
be **domain-neutral**. HVAC/chillers is its first vertical, not its definition — unlike THERMYNX,
which is chiller-plant-specific by design. The centerpiece is **Synex Copilot**: one conversational
assistant sitting alongside two other surfaces (Reports, Work Orders) as a third way into the same
underlying capability.

Two governing rules carry over from — and sharpen — lessons THERMYNX already learned the hard way
(see [THERMYNX's own landmines doc](../../../../thermynx/docs/kt-karthik/08-known-issues-and-landmines.md)
for the concrete incidents that motivated rules like these):
- **"The language model never diagnoses."** Deterministic FDD rules decide the fault; a
  deterministic Control Plane decides whether an action is permitted; the model's only job is
  explaining the result in plain English. A confident-sounding "no fault found" (`NO_DIAGNOSIS`)
  is a legitimate, honest answer — not something to hide.
- **"Never invent a number."** Every number the Copilot states must be a real value or an
  explicitly stated absence — never neither, never both. Every signal is labeled
  measured/simulated/derived/never-measured so a fabricated reading can never present as real.

## Is there real code here, or just planning docs?

**Real code — more than the README's "documentation workspace" framing suggests.** There's a
FastAPI backend (122 source files, 3,600+ offline tests) and a real Next.js/TypeScript frontend
at `apps/web/` (the top-level `frontend/` folder is an empty scaffold — don't be misled by it,
`apps/web` is where the actual UI lives). Infrastructure: its own Postgres+pgvector and Redis,
plus a cloned MySQL snapshot of real plant telemetry, and the same rented "Jarvis" GPU box concept
as THERMYNX running a 4-model Ollama roster.

## What's actually settled vs. still open — read this before assuming anything is decided

**A live inconsistency worth knowing about, not resolving yourself:** `CLAUDE.md` lists question
**N1** ("how do Synex and THERMYNX relate?") as open and blocking. But `CONTEXT.md` §9a and
decision `D-006` already state Synex is "an AI layer on the existing platform, not a replacement"
— and `decisions/OPEN-QUESTIONS.md` still marks N1 **Open**. The documents disagree with
themselves on whether this is decided. Don't silently pick a side — flag it if it matters for
whatever you're working on, the same way THERMYNX's docs try to be honest about "no answer" rather
than guessing (see [THERMYNX's conventions doc](../../../../thermynx/docs/kt-karthik/11-conventions-and-constraints.md)
for that as a cross-project house value).

**The MVP scope is proposed, not agreed** (`mvp/MVP-SCOPE.md`, blocked on decision **S1**) — 94 of
147 registered features, chosen to close one complete loop end-to-end for water-cooled chillers on
one site: fault detected → case opens → explained with evidence → narrowed to root cause → work
order created → work verified. Don't treat this scope as final.

**The actual current bottleneck is not engineering.** Per `mvp/INHERITANCE-STATUS.md`: the
diagnostic engineering (19 discriminator questions, a 124-item technician checklist library) is
built and tested, but every differential immediately reports `EXHAUSTED` because none of that
content has been reviewed by a refrigeration engineer yet. That file's own words: "it is Vishnu's
hour, not engineering." (Vishnu is the same domain SME referenced in THERMYNX's own docs — see
`thermynx/docs/for-vishnu/` — a recurring stakeholder across both products, not Synex-specific.)
**Practical implication for you:** if you're looking for something to build, prefer the two build
stages the MVP plan says have no SME dependency and can proceed now — the Control Plane and the
conversation shell (stages 3 and 8 of the 10-stage build sequence in `MVP-SCOPE.md`) — over the
FDD/diagnosis stages (1–2), which are blocked on Vishnu's review regardless of engineering effort.

## Reading order

| Order | File | Roughly | What's in it |
|---|---|---|---|
| 1 | `../../README.md` | 5 min | Repo map |
| 2 | `../../CLAUDE.md` | 10 min | Operating rules, naming law, banned phrases |
| 3 | `../../CONTEXT.md` | 45–60 min | **The most important file** — settled product truth, the separation law, the FDD engine, the answer contract, all 39 inherited constraints |
| 4 | `../../mvp/MVP-SCOPE.md` | 20–25 min | What's planned to be built, the 15 test cases, acceptance criteria, the 10-stage build sequence |
| 5 | `../../mvp/INHERITANCE-STATUS.md` | 10 min | What's wired vs. not yet wired — the fastest bridge doc for someone who already knows THERMYNX |
| 6 | `../20-architecture/03-from-thermynx.md` and `04-thermynx-e2e-reference.md` | 35–45 min | Explicit inheritance/comparison against THERMYNX — read these once you've done the THERMYNX KT folder, they'll click fast |
| 7 | `../../decisions/OPEN-QUESTIONS.md` | 25–30 min | Everything unresolved — especially the instrumentation-trust questions (Q1/Q2) and the parked platform questions (Q41–43) |
| 8 | `../../mvp/FEATURE-REGISTER.md` | reference | Feature ID lookup — not meant to be read start to finish |
| 9 | `../../decisions/DECISIONS.md` | reference | Decision log — check when a design choice looks surprising |
| 10 | `../../HANDOFF.md` | 15–20 min | Read the "Recent changes" table **bottom-to-top** (newest first); the rest is a long build log, lower priority |
| — | remaining `docs/10-product/*`, `docs/20-architecture/*` chapters | as needed | Treat as an encyclopedia (44+ chapters) — sample, don't read cover to cover |

## The single most useful thing you already have

You've just been through THERMYNX's own Knowledge Transfer folder
(`thermynx/docs/kt-karthik/`). Everything in it about grounding, tool registries, the read-only
refusal reflex, and verifying claims against real data is the *lived history* behind Synex's
"never diagnose / never invent a number" rules — you're not learning a new philosophy here, you're
seeing the second product built by people who already got burned once.
