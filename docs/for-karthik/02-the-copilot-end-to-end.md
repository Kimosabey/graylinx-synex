# The Copilot, end to end

The most important document here if you are taking the AI side. It follows one question all the
way through, names every model that touches it, and — more usefully — says what each one is
**forbidden** from doing.

`docs/20-architecture/29-agentic-and-model-architecture.md` is the specification. This is the
walkthrough.

---

## The one rule everything else serves

> **The language model never diagnoses.**

The trained FDD model says a reading is abnormal. Deterministic rules name the fault. A
deterministic formula sets the priority. The Control Plane grants permission. **The language
model's only job is saying what happened in English.**

Every design decision below follows from that, and when you are unsure whether a change is
allowed, ask which of those four things it would move into the model. If the answer is any of
them, it is not allowed.

The second rule: **never invent a number.** Every figure is a real value or an explicitly stated
absence. Never neither, never both.

---

## The four models, and the division of labour

| Model | Roles it serves | Job |
|---|---|---|
| `gemma4:26b-a4b-it-qat` | `brain` · `planner` · `composer` | plans, reasons, writes the prose a person reads |
| `devstral:latest` | `tool` · `sql` | executes — picks tools in the loop, writes SQL |
| `phi4` | `auditor` · `text` · `rag` | audits and narrates |
| `nomic-embed-text` | `embed` | retrieval vectors |

**Code never names a model.** Every call site asks for a *role* and `app/llm/models.py` resolves
it. Three roles are aliases. If you find a model name anywhere outside that table, a test will
fail — `tests/unit/test_role_table.py` enforces it.

**phi4 audits because it is a different family from the model that wrote the answer.** A model
grading its own output is not an audit. This is the one property of the roster that is about
independence rather than capability.

**A warning that has already cost a day.** Thermynx's `config.py` still contains stale comments
naming retired models (`gemma4:12b` for planning, `codestral` for SQL). Reading those comments
led to `planner` being moved off the brain and back again within a day. Our own
`docs/20-architecture/04-thermynx-e2e-reference.md` §1 warns about exactly this in writing.
**Read this repository's reference before the source it was derived from.**

---

## One question, all the way through

Take *"why was chiller 1 flagged on 9 April?"*

### 1 · The router — five layers, cheapest first

`app/agents/router.py`. Each layer either decides or falls through, and none of them raises.

| Layer | What it does | Model? |
|---|---|---|
| 0 · override | an explicit mode skips everything | no |
| 1 · preflight | prompt-injection patterns, refused outright | no |
| 1.5 · fast path | greetings, "what can you do" | no |
| 3 · keywords | high-precision phrase matches | no |
| 3.5 · scope gate | is this about this plant at all | no |
| **4 · arbiter** | **the model picks the skill** | **gemma4, JSON mode** |

Layers 0 through 3.5 are pure functions and cost microseconds. The arbiter only runs when
everything cheaper was inconclusive.

**The arbiter is what stops the Copilot being a menu.** A phrase list always has the hole nobody
imagined — *"I can't tell what this means"* matched nothing because the list held *"not sure
what this means"*. Widening the list closes one hole and leaves the next.

**`refuse` is deliberately not on the arbiter's menu.** The layers that refuse have already run.
If a model could route an out-of-scope question back into an answering skill, the scope gate
would be advisory — and this product has already shipped one leak of exactly that shape, where a
selected episode admitted *"what is the capital of France"* as a full answer about chiller 1.

### 2 · The evidence pack — assembled without a model

`app/services/evidence.py`. Residuals, bands, gates, provenance, sources. The model receives
`to_prompt_data()` and never the object — **display strings only, no raw floats anywhere**, so
the numeric audit afterwards is a string containment check rather than a float comparison.

### 3 · The gates — five of them, and failing is normal

If any gate fails, the turn cannot diagnose. On this data that is the *modal* outcome, and it is
the feature rather than a shortfall.

### 4 · What happens when the gates fail — four modes, not one refusal

This is the part most worth understanding, and it comes from Thermynx's Resolve design:

> **The AI's value is inversely proportional to the model's certainty. A product built only for
> [Explain] is a model viewer.**

| Mode | When | What it contributes |
|---|---|---|
| **Explain** | gates passed | the meaning and the fix |
| **Hypothesise** | an undecidable class | **not an answer — the right question** |
| **Interrogate** | data but no verdict | what it can prove, and what it cannot |
| **Interview** | nothing usable | what *is* still answerable |

Four of this plant's fault classes admit in their own names that they cannot resolve —
*ambiguous*, *undercharge **or** restriction*, *unspecified*, *unexplained*. `HIGH_HEAD_AMBIGUOUS`
is both the most common and the least informative.

`app/agents/hypothesise.py` handles those: it names the five candidate causes and the check that
would narrow them most. **Nothing in it diagnoses** — the candidates are transcribed content, the
next question is chosen by *reach* (how many live candidates one answer could eliminate) with
ties broken toward the lowest id, so *"why was I asked this first?"* is answerable from the data
rather than from a prompt.

**Today it always reports `EXHAUSTED`**, because `askable` returns only SME-reviewed questions
and none is reviewed. That is deliberate: thirty-one causes were once eliminated on the reference
queue by discriminators nobody qualified had read. An elimination is a door that closes quietly.
**This is the single largest gap in the product and it is one hour of a refrigeration engineer's
time, not engineering.**

### 5 · Composition — the model finally writes something

`app/agents/compose.py`. The prompt is assembled in a deliberate order:

```
conversation transcript   ← what was said before (fenced, six exchanges)
retrieved documents       ← approved SOP passages (fenced, with citations)
the tool result           ← the evidence (fenced)
the question
```

That order is the authority order: more authoritative going down. A manual describes how
equipment behaves *in general*; the readings say what *this* machine did. Everything fenced is
labelled DATA and cannot change the rules, whatever it appears to say.

### 6 · The audits — seven deterministic, then one model

`app/agents/postcheck.py` runs seven checks. Every number in the answer must appear in the
evidence. Every equipment name must be one that exists. **The one that matters most on this
plant:** a never-measured signal must never be quoted as a reading.

Then `app/agents/critique.py` — phi4 reads what gemma4 wrote and classifies each claim
verified / unverified / suspicious. It is a **soft** gate: it badges, never hides. A hidden
answer teaches a reader the system is broken; a badged one teaches them what to check.

**`available=False` is not the same as passing.** An answer nobody audited is not an audited
answer.

### 7 · The retry — one, and only on a real gate

If the critique gates the answer, it is written once more with the unverified claims quoted back
and an instruction to leave them out: *"do not soften them, do not hedge them, do not restate
them with a caveat."* "Be more grounded" is advice, and advice produces a hedged version of the
same claim.

---

## The other paths

**The tool loop** (`app/agents/react.py`) — devstral picks the next tool and follows what it
finds; the brain composes from what came back. **devstral gathers, the brain reasons.**
`PlannedChooser` is the floor beneath it, not a spare: every model failure falls to the same
deterministic plan the loop used before.

> A landmine already paid for elsewhere: Thermynx's agent was observed calling one succeeding
> tool **13 times in a row** until the step ceiling ran out. Repeating a *succeeding* call throws
> nothing, so every guard watching for errors is blind to it. `react.py` ends on `REPEATED_CALL`
> with a per-turn ledger. Do not remove that.

**NL→SQL** (`app/agents/nl_sql.py`) — the one path where a model produces something *executable*.
`app/analytics/sql_guard.py` is the security boundary: SELECT only, one statement, allow-listed
tables and columns, mandatory LIMIT, and **no wall-clock functions** — this telemetry is a
snapshot, so `NOW()` matches no rows and returns an empty table that reads as *"nothing wrong"*.
The validator **refuses and never repairs**; one that rewrote a statement could be argued with.

**Orchestrate** (`app/agents/orchestrate.py`) — a broad question reads up to four capabilities in
parallel and composes one answer. A read that failed is **named**, never dropped: a review
silently assembled from three quarters of what it meant to gather reads exactly like a complete
one.

**Retrieval** (`app/agents/recall.py`) — approved passages only, each with its citation, and the
unapproved count travels with them. Hiding that number turns *"we have not reviewed this"* into
*"this does not exist"*.

---

## Where to look when something is wrong

| Symptom | Look at |
|---|---|
| every answer says "language model · not used" | the tunnel — `box_reachable` in `/health` |
| a question is refused that should not be | `router.py` scope gate; then the arbiter |
| a right-sounding answer with a wrong figure | `postcheck.py`, then the composer's prompt |
| a refusal with no reason | that is a bug — every refusal must name what would change it |
| a differential that says nothing is reviewed | expected; that is the SME gap |

---

Next: **[03-known-issues-and-landmines.md](03-known-issues-and-landmines.md)** — read it before
changing anything in the AI code.
