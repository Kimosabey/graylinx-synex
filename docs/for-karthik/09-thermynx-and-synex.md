# Thermynx and Synex — what is shared, what is separate, what is undecided

You are the one person who will hold both products at once, so this needs to be exact rather
than roughly right. Three different questions get muddled here and only one of them is open.

---

## The three questions, kept apart

| Question | Status |
|---|---|
| Does Synex replace the **Graylinx platform**? | **Settled** — no. `D-006`, 11 Aug. It is an AI layer that plugs into what is there. |
| Does Synex replace **Thermynx**? | **Open** — `N1`. Nobody has answered it. |
| Do they **share infrastructure**? | Settled by fact, not by decision — yes, extensively. See below. |

**There is no contradiction in the documents, and one KT file used to say there was.** `D-006`
settles the first question and states in its own text: *"Closes: nothing. N1 remains open — this
is about the Graylinx platform, not about Thermynx."* It anticipated exactly this misreading.

So `CLAUDE.md` listing `N1` as open and `CONTEXT.md` §9a saying *"an AI layer, not a
replacement"* are both correct and are about different things. Do not treat the second as
having quietly answered the first.

### What `N1` being open means for you day to day

`CLAUDE.md` §1 is blunt: **do not write any sentence that positions one as replacing,
containing or superseding the other.** That applies to product copy, chapter prose, commit
messages and anything a customer might read.

It does not stop you building. Every stage in `mvp/MVP-SCOPE.md` is buildable without an answer.
It stops you *asserting* the relationship.

---

## What they genuinely share

Not a design principle — the practical situation, and each one has a consequence.

| Shared | Consequence |
|---|---|
| **The plant database** — the same MySQL, same site telemetry | Synex's grant is `synex_plant_ro` and cannot write. Thermynx's own access is separate. **You can break Thermynx by writing to that database; you cannot break it through Synex.** |
| **The Jarvis GPU box** — one rented card, ~₹179/hr | One box, one Ollama, one roster. If both products want it at once, they contend. Terminate it when you are done. |
| **The model roster** — same four models | `gemma4:26b` · `devstral` · `phi4` · `nomic-embed-text`. Same models, same roles, arrived at by Thermynx's bake-off. |
| **The SME** | Vishnu reviews for both. His hour is the scarce resource in both products. |
| **The findings** | Condenser flow never measured, the flow transmitters dead since May — discovered on Thermynx's data, true of the same plant. |

### Ports, because they collide

Thermynx occupies **5442, 6380, 8000 and 5173**. Synex deliberately sits beside it:

| | Thermynx | Synex |
|---|---|---|
| Backend | 8000 | **8001** |
| Postgres | 5442 | **5443** |
| Redis | 6380 | **6381** |
| Front end | 5173 | **3000** |

Both can run at once, and during a demonstration they often are. If a Synex command reaches
8000 you are talking to Thermynx — that happened once here and produced a confusing five minutes
of "why does this endpoint not exist".

---

## What is separate, and deliberately

| | |
|---|---|
| **The repositories** | Different repos, different histories. No shared code, no package dependency. |
| **The state database** | Synex has its own Postgres — its own cases, work orders and vector store. |
| **The detection model** | Neither product trains it. Both read Shiva's verdicts out of `gla_model_residuals_wc` and never re-detect. |
| **The rules** | Synex's `CLAUDE.md` naming law, banned phrases and feature-ID scheme are its own. `scripts/verify.py` enforces them and knows nothing about Thermynx. |

---

## Copy the mechanism, re-derive every number

The rule for everything taken across, and it is stricter than it sounds.

**Mechanisms carry.** The ReAct loop, the tool registry, the postcheck audit, the critique gate,
the four answer modes, the NL→SQL validator — all shaped by Thermynx's incidents, and an
incident is a more reliable designer than we are.

**Numbers do not.** A threshold measured on Thermynx's plant is a fact about *that* plant. Even
where it is the same site, the window differs, the fitted models differ, and a figure that
travels without being re-measured is a figure nobody can defend. `CLAUDE.md` §2 forbids it
outright: no metric, threshold or coefficient appears unless it is in `CONTEXT.md`, in a source
document, or given to you directly.

The one place this got close to going wrong: the critique gate's thresholds were inherited
rather than invented, and that is recorded as `Q106` so nobody later reads them as measured
here.

---

## The trap that already cost a day

**Thermynx's `config.py` contains stale comments naming retired models** — `gemma4:12b` for
planning, `codestral` for SQL. Both are retired in its own live code.

Reading those comments led to Synex's `planner` role being moved off the brain and back again
within a day, with a wrong argument made confidently in between.

Our own `docs/20-architecture/04-thermynx-e2e-reference.md` §1 warns about this in writing, and
was not read first.

> **Read this repository's own reference before the source it was derived from.**
> `03-from-thermynx.md` and `04-thermynx-e2e-reference.md` came from full passes over Thermynx on
> 11 and 18 August. A fresh partial pass is *worse* evidence, not newer evidence.

---

## Where to read what

| For | Read |
|---|---|
| What Thermynx *is* | `thermynx/docs/kt-karthik/` — its own KT folder |
| How its five features work end to end | `docs/20-architecture/04-thermynx-e2e-reference.md` — read from its live code, and §8 lists four places its own docs have drifted |
| What Synex inherited and why | `docs/20-architecture/03-from-thermynx.md` |
| Which of it is **wired in Synex today** | `mvp/INHERITANCE-STATUS.md` — the only one of these that answers that |
| The inherited constraints, canonically | `CONTEXT.md` §10 |

---

## The one thing to ask Harshan

**`N1`, if it ever affects what you are writing.** Not to unblock building — nothing is blocked —
but because the moment you write a sentence positioning the two products, you need the current
answer rather than an inference.

`CLAUDE.md` §6 lists it as one of the situations where you stop and ask rather than decide.
