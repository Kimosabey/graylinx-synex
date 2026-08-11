# Teams message for Vishnu — paste as-is

Chat, not email. `VISHNU-MESSAGE.md` is the long-form version for a mail with the PDF
attached; this is the version that survives being read on a phone. Same ask, a third of
the words, and the concrete question moved up front — on Teams the thing at the bottom
does not get read.

Attach **`mvp/SME-REVIEW.pdf`** to the message, or send it straight after.

---

## Send this

Hi Vishnu — we've written up the MVP plan for **Graylinx Synex**: the Copilot, the
fault-to-fix loop, and proving a repair actually worked. Most of it is your reasoning
written down rather than anything new.

Two links, and this order matters 🙂

**1. The product — 3 minutes** → https://graylinx-synex-mvp.netlify.app/mock
Click *Start the walkthrough* at the bottom. It follows one real fault from detection to a
repair the system can prove worked. It's a wireframe, so ignore how it looks — the flow is
the point.

**2. The plan** → https://graylinx-synex-mvp.netlify.app
94 of 147 features, with what's deferred and why. Only if you want the full picture.

**What I actually need is one hour on section 1 of the attached agenda.**

We've written **124 checklist items across 11 fault classes, and 4 decision trees** for
*which cause is it*. No refrigeration engineer has looked at any of it. That matters
because the system doesn't just list checks — it uses the answers to **rule causes out**.
If one of our tests is wrong, it eliminates the *correct* cause, sounds certain, and nobody
goes back to question it.

So please try to **break** section 1 rather than approve it. *"I don't know"* and *"it
depends"* are genuinely useful answers — we'd much rather show two possible causes than
confidently eliminate the right one.

**If you only have 15 minutes, do §1.8.** We counted something new in the plant data: on
**15 April, chiller 1 reported five faults at the same time** — and ten of its twelve fault
days have more than one. Our guess is that a **fouled condenser** explains four of the
five, so we group them into **one** work order instead of five. That guess is ours and
nobody qualified has checked it.

The half that really matters is the opposite one: **which faults must never be grouped?**
Hiding a real second fault is far worse than a wasted visit.

Two things worth knowing before you look:

- The cut is a **proposal**. Nothing is agreed yet, and 46 questions are open.
- On this plant's data, **condenser flow has never recorded a reading** — and four of the
  six models depend on it. That's question Q1 and it may be the biggest one in here.

One line per question is plenty, or grab me for a call and I'll write it down.

---

## If you want to open with something shorter

Some people answer a small message and ignore a long one. If so, send this first and the
above once he replies:

Hi Vishnu — got a spare hour this week? We've written the MVP plan for Graylinx Synex and
there's a chunk of it only you can check: 124 checklist items and 4 *which-cause-is-it*
decision trees, none reviewed by a refrigeration engineer. The system uses those answers to
rule causes *out*, so a wrong one quietly eliminates the right cause. Happy to send the
3-minute walkthrough and the agenda whenever suits.

---

## Notes for us — do not send

- **Do not present the grouping as decided.** `RC19` is registered, but its rules are our
  inference. If he draws different groups, the register follows him.
- **§1.8 is deliberately first** in the Teams version and later in the email. It is the most
  concrete question we have — one machine, one date, five labels — so it is the best way to
  get him reasoning about the plant rather than about our document.
- **Do not discuss how Synex and Thermynx relate.** That is `N1`, and it is Harshan's to
  answer rather than something to improvise in a chat.
- If he asks why the recent data looks healthy: real readings stop on **23 June**, the six
  weeks after are simulated, and the simulation **invented condenser flow**. The
  demonstration runs on the real window and returns *no diagnosis* where flow is needed.
  That is §2.6, and it is better raised by us than found by him.
