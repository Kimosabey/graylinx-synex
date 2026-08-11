# Message for Vishnu — send as-is

> Two links and one ask. Keep it short: the agenda does the detailed work, and
> `mvp/SME-REVIEW.pdf` goes with it. The framing below is deliberate — asking him to
> *break* the reasoning gets a better hour than asking him to *review* it.

---

Hi Vishnu,

We have written the MVP plan for **Graylinx Synex** — the product built around the
Copilot, the fault-to-fix loop, and proving a repair actually worked. It draws
heavily on what the chiller-plant work has already taught us, so a lot of it is
your reasoning written down rather than anything new.

**Two links, and I would look at them in this order.**

**1. The product — https://graylinx-synex-mvp.netlify.app/mock**
Click **"Start the walkthrough"** at the bottom. Eight steps, about three minutes,
and it walks one real fault from detection to a repair the system can prove worked.
It is a wireframe, not a design — the point is the flow, not how it looks.

The parts worth pausing on:

- **Cases** — the checklist with a *cannot_check* answer, and the blocking gate
  staying shut because of it
- **Work orders** — the close button that will not open because verification came
  back UNKNOWN rather than PASS
- **Copilot** — try the refusals rather than the answers. "Why is Chiller-03
  unhealthy? (condenser flow missing)" is the one that matters

**2. The plan — https://graylinx-synex-mvp.netlify.app**
94 of 147 features proposed for the MVP, with what is deferred and why. Worth ten
minutes if you want the full picture, but it is not what I need from you.

**What I actually need is one hour, on section 1 of the attached agenda.**

We have written **124 checklist items across 11 fault classes and four "which cause
is it" decision trees.** None of it has been looked at by a refrigeration engineer.

That matters more than it sounds, because the system does not just list checks — it
uses the answers to **rule causes out**. If one of our tests is wrong, it will
eliminate the *correct* cause, do it confidently, and nobody will go back and
question it. **A wrong answer that looks certain is worse than no answer.**

So please try to **break** section 1 rather than approve it. We are most confident
about the filter-drier test, which is exactly why being wrong about it would cost
the most. **"I do not know" and "it depends" are genuinely useful answers** — we
would far rather show two possible causes and let the technician decide than
eliminate the right one and sound sure.

**One new question, and it may be the quickest win in the whole agenda — §1.8.**

We counted something in the plant data last week that we had not looked at before. On
**15 April, chiller 1 reported five different faults at the same time** — including the
only one rated critical. Ten of its twelve fault days carry more than one label.

If each of those becomes its own work order, we send someone five times to fix what is
probably one thing. The technician fixes it on the first visit, the other four find nothing,
and everyone learns to ignore the system.

So we now group faults that look like one problem — our reasoning being that a **fouled
condenser** would raise head pressure, make the compressor work harder, drop efficiency and
shift refrigerant pressures all at once. **That reasoning is ours and nobody qualified has
checked it.** §1.8 asks you to check it, and especially to tell us **which faults must never
be grouped** — because hiding a real second fault is far worse than a wasted visit.

It should be a quick one to answer from experience, and getting it wrong is expensive.

Three things you should know before you look:

- The cut is a **proposal**, not a plan. Nothing is agreed yet.
- **46 questions are open and none are answered.** Most of them are yours.
- On the plant data we have, **condenser flow has never recorded a reading** — and
  four of the six models depend on it. That is question Q1, and it may be the most
  important one in the whole thing.
- The recent-looking data is **partly simulated**. Real readings stop on 23 June; the
  six weeks after that are generated, and the simulation **invented condenser flow** —
  the one signal the plant has never measured. So the demonstration deliberately runs on
  the **real** window, and the high-head branch returns *no diagnosis* where flow is
  needed. That is the honest result, not a bug. §2.6 spells it out.

Reply in whatever form is easiest — one line per question is plenty, or a call and
we will write it down.

Thanks,
Harshan

---

## Notes for us — do not send

- **Order matters.** The mock first. The specification is 147 features and will
  swamp the ask if he opens it first.
- **Do not defend section 1.** Every correction is one line in the library; that is
  why it was built that way. Agreeing quickly costs nothing and disagreeing is the
  point of the hour.
- **Lead the data problems yourself** — condenser flow never reporting, `dpt`
  constant so approach cannot be computed, condenser ΔT negative every month. He
  will find them; better that we raised them.
- **The one to get if he gives nothing else** is §4.4 — what proves a repair worked.
  It has no counterpart in the existing question set because that implementation has
  no verification layer, so there is no answer to borrow.
- **Do not discuss how Synex and Thermynx relate.** That is question N1 and it is
  Harshan's to answer, not a thing to improvise in a technical review.
- If he offers more than an hour, §2 (the data that does not exist) is the next best
  use of it.
- **§1.8 is a good opener**, not a closer. It is concrete — one machine, one date, five
  labels — so it warms him up on real plant reasoning before the abstract elimination
  questions. And 1.8b is the one that matters: *which faults must never be grouped*.
- **Do not present the grouping as decided.** `RC19` is registered, but its rules are our
  inference. If he draws different groups, that is the answer and the register follows him.
