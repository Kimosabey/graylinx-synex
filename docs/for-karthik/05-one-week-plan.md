# One week on Synex

Five days, ending with a real change shipped under your name. Sequenced so each day makes the
next one cheaper, and front-loaded with seeing it run — reading about this system before watching
it work is much harder than the other way round.

Thermynx has its own week plan at
`thermynx/docs/kt-karthik/14-one-week-plan-thermynx-and-synex.md`. If you are doing both
products, that one sequences them together.

---

## Day 1 — see it run, then read the two rules

**Morning.** Work through `01-running-synex.md` and get all three terminals up. Do not skip the
tunnel keeper. Confirm `box_reachable: True` before going further — half of what you would read
today makes no sense against a box that is not answering.

Then open the Copilot and ask, in this order:

| Ask | What to notice |
|---|---|
| *what equipment do we have?* | the badge says **Language model · wrote the wording** |
| *how is chiller 2 doing?* | it names what is unexamined, not just what is wrong |
| *what is the capital of France?* | refused — and read the refusal, it is not a fob-off |
| *can you change the chilled water setpoint?* | the boundary, stated as a boundary |
| *which chiller uses more power?* | this one writes SQL. Read the statement it shows you |
| *why was chiller 1 flagged on 9 April?* | the evidence path |

**Afternoon.** Read `CONTEXT.md` §5 (the separation) and §10 (inherited constraints), then
`CLAUDE.md` end to end. It is short and every rule in it has an incident behind it.

**Do not write code today.**

---

## Day 2 — the AI path

**Morning.** `02-the-copilot-end-to-end.md`, then follow it in the source with the app open
beside you: `router.py` → `answer.py` → `compose.py` → `postcheck.py` → `critique.py`.

Ask a question and watch the **Inspector** panel under the answer — it shows the route, the
layer that decided it, the stages and the audits. That panel is the cheapest debugging tool here
and most people never open it.

**Afternoon.** `03-known-issues-and-landmines.md`. Slowly. Then do this exercise, because it is
the defect this codebase produces most:

> Pick any capability in `app/agents/`. Grep for its consumers. Convince yourself a **request**
> reaches it — not a test, not an ingest job, a request.

Six capabilities failed that test in one day.

---

## Day 3 — the tests, and your first change

**Morning.** `04-testing-and-evaluation.md`. Run all four offline gates. Then run
`scripts/eval_copilot.py --one-persona` and watch it — about four minutes, and it teaches you
the shape of every answer state.

**Afternoon — your first change, and it is a real one.**

Open `eval-flywheel.txt`. Every line is a question the product got wrong. Pick one, write a
proper hand-written case for it in `scripts/eval_copilot.py` with a real expectation, and see it
fail. Then fix the product until it passes.

That is the whole loop in one afternoon: a real defect, a real test, a real fix. Run all four
gates before you commit.

---

## Day 4 — the SME gap, and the thing that is actually blocked

**Morning.** Read `mvp/INHERITANCE-STATUS.md` and `mvp/ASK-VISHNU.md`, then ask the Copilot:

> *why was chiller 1 flagged on 9 April for HIGH_HEAD_AMBIGUOUS?*

Where the gates fail you will get **Hypothesise mode**: five named candidate causes, five checks
that would separate them, and a sentence saying none has been reviewed by a refrigeration
engineer.

**That sentence is the largest gap in the product.** The machinery is complete. `askable` returns
only SME-reviewed questions and none is reviewed, so every differential reports `EXHAUSTED` by
construction. Nineteen yes/no answers from Vishnu turn *"no check has been reviewed"* into
*"answer this one reading and two of five candidates are gone"*.

Understand why it is deliberate before you are tempted to switch the flag: thirty-one causes were
once eliminated on the reference queue by discriminators nobody qualified had read, and an
elimination is a door that closes quietly.

**Afternoon.** Pick a second task from the backlog below and start it.

---

## Day 5 — ship it

Finish the task, run the four gates, and write the `HANDOFF.md` entry yourself. Read a few
existing entries first — they explain *why*, not *what*, and the commit messages do the same.
That convention is worth keeping: six months from now the diff is still readable and the reason
is not.

---

## The backlog, roughly in order of value

**Small, and each is a genuine improvement**

1. **Make the flywheel read itself.** `eval-flywheel.txt` accumulates failures and nothing reads
   it back. A script turning recorded failures into stub cases closes the loop.
2. **Finish a 147-case run.** Nobody has yet seen all of them complete — two attempts died to
   infrastructure. The highest clean run is 84.
3. **Retrieval quality.** `app/retrieval/quality.py` has the machinery and nothing measures
   whether a cited passage actually supports the sentence citing it.

**Medium**

4. **Multi-turn evaluation.** Conversation memory is plumbed and unit tested; behaviour over
   several real turns is not measured.
5. **Interview mode.** Three of the four answer modes are built. The fourth — a guided
   conversation when there is nothing usable — is not.
6. **The anomalies surface.** Deliberately *not* copied from Thermynx: live scanning, an hours
   window and severity colouring would each be untrue here. See `mvp/INHERITANCE-STATUS.md`
   under "Deliberately refused" before building anything in that direction.

**Needs a decision, not code**

7. **A fourth-family grounding judge.** Thermynx uses `llama3.1:8b` so nothing grades its own
   output; we use `phi4` for both the critique and the `text` role. `CONTEXT.md` §4 says four
   models — so this needs a decision recorded in `decisions/DECISIONS.md`, not a quiet addition.

**Blocked on Vishnu, and worth more than all of the above**

8. The 19 discriminators · Q3's load-floor denominator · the flow-constant confirmation.
   `mvp/ASK-VISHNU.md` is the message; it has been sent.

---

## Three things to ask Harshan rather than decide

`CLAUDE.md` §6 has the full list. The ones most likely to come up:

- **Anything depending on how the equipment actually behaves.** That is Vishnu's call, not an
  engineering judgement.
- **Naming question N1** — how Synex and Thermynx relate. `CLAUDE.md` lists it open and blocking;
  `CONTEXT.md` §9a and `D-006` read as though it is settled. The documents disagree with
  themselves. Do not silently pick a side.
- **Anything changing what gets built in the MVP.**

Everything else: proceed, and note the assumption in your summary.
