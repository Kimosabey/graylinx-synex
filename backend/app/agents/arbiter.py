"""The layer that decides where a question goes when nobody wrote a keyword for it.

**This is what stops the Copilot being a menu with a text box on top.** Every routing layer
before this one matches phrases somebody thought of in advance, and a phrase list always has
the hole nobody imagined: *"I can't tell what this means"* reached the escalation reader and
matched nothing, because the list held *"not sure what this means"* and not that. Widening the
list closes one hole and leaves the next. A reader who hits two of those concludes the product
only answers a fixed set of questions — which is exactly the thing it is supposed not to be.

**Cheapest first, and the ladder is not decoration.** A question that matches a keyword routes
in under a millisecond and never reaches this. Only the ones that fall through pay for a model
call, so the common path stays fast and the long tail stops being refused.

**What the arbiter decides, and what it emphatically does not.** It picks *which skill answers*
and nothing else. It does not name a fault, grant a permission, set a priority or produce a
figure — the separation in `CONTEXT.md` §5 is untouched, because choosing who answers is not
answering. A wrong choice here routes a question to the wrong skill and produces a worse
answer; it cannot produce an ungrounded one, because every skill downstream is unchanged.

**A refusal is never arbitrated.** The preflight and scope layers run *before* this, and their
decisions are final. If a model could route an out-of-scope question back into an answering
skill, the scope gate would be advisory — and this product has already shipped one leak where
inherited context admitted every question. So the arbiter chooses among skills that answer, and
choosing nothing is a valid outcome that falls through to the existing default.

**JSON from the small model, not the large one.** `phi4` holds the `text` role and a short
strict schema is exactly what it is reliable at; the 26B brain was recorded degenerating into a
repetition loop on precisely this job in the Thermynx implementation, and every plan silently
became empty — not a crash, an empty result that reads as "nothing to route". The same lesson
that put `planner` on the small model puts this there.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.llm.client import ModelClient

#: How long the arbiter may take before the turn gives up and uses the default. A router that
#: can hang is a product that appears to hang, and the fallback costs nothing.
TIMEOUT_S: float = 30.0

#: What each skill is *for*, written for a reader deciding between them rather than for us.
#: One entry per skill the arbiter may choose — `refuse` is deliberately absent, because the
#: layers that refuse have already run and their decisions are not open to reconsideration.
CHOICES: tuple[tuple[str, str], ...] = (
    (
        "look_up",
        "a fact that is already recorded: a reading, a count, a list, what equipment exists, "
        "which machines carry a fault, what a fault class means. The answer is retrieved, not "
        "reasoned.",
    ),
    (
        "explain",
        "why something was flagged, what a residual means, what the evidence behind one "
        "detected episode says. Needs one machine, one fault and one day.",
    ),
    (
        "investigate",
        "an open question needing several steps: comparing machines, following something over "
        "time, working out which of a set of readings matters. Broader than one episode.",
    ),
    (
        "prepare_work",
        "turning a detected problem into a job somebody can be sent to do — a work order, a "
        "task, scheduling an intervention.",
    ),
    (
        "resolve",
        "what to do next about a specific problem: the checks to run, the order to run them "
        "in, what is blocking progress, and handing the work to somebody else when the person "
        "asking cannot proceed.",
    ),
    (
        "verify",
        "whether something that was already done actually worked — a repair, a change, an "
        "intervention. Compares after against before.",
    ),
    (
        "converse",
        "conversational rather than a request for information: a greeting, thanks, asking what "
        "this system can do.",
    ),
)

_SYSTEM = (
    "You route questions in an industrial chiller plant assistant. You pick which capability "
    "answers, and nothing else.\n\n"
    "You never decide what is wrong with a machine, whether somebody may do something, how "
    "urgent anything is, or what any reading is. Those are decided elsewhere. Your entire job "
    "is choosing which capability should take this question.\n\n"
    "Pick the closest match. If the question genuinely does not fit any of them, return null "
    "rather than forcing one — a wrong route produces a worse answer than no route.\n\n"
    "Reply with JSON only, in exactly this shape:\n"
    '{"skill": "<one of the names below, or null>", "why": "<one short sentence>"}'
)


@dataclass(frozen=True)
class Arbitration:
    """Which skill the model chose, and the sentence it gave for choosing it.

    `skill` is `None` when the model declined or returned something unrecognised, and the
    caller falls through to its existing default. A `None` here is a routing decision that was
    not made, never a refusal — refusing is a different layer's job and has already happened.
    """

    skill: str | None
    why: str = ""

    @property
    def decided(self) -> bool:
        return self.skill is not None


def _prompt(message: str, *, last_equipment: str | None) -> str:
    """The question, the choices, and what the conversation already established."""
    catalogue = "\n".join(f"- {name}: {what_for}" for name, what_for in CHOICES)
    context = (
        f"The previous turn was about {last_equipment}. A question with no machine named may "
        f"be about that one.\n\n"
        if last_equipment
        else ""
    )
    return (
        f"CAPABILITIES:\n{catalogue}\n\n"
        f"{context}"
        f"QUESTION: {message}\n\n"
        "Which capability answers this?"
    )


async def arbitrate(
    message: str, *, client: ModelClient | None, last_equipment: str | None = None
) -> Arbitration:
    """Ask which skill answers this. **Never raises, never blocks past the timeout.**

    Every failure mode — no client, an unreachable box, a timeout, unparseable output, a name
    that is not a skill — returns an undecided arbitration, because the caller has a working
    default and a router that can fail the turn is worse than one that occasionally shrugs.
    """
    if client is None:
        return Arbitration(None, "no model was available to arbitrate")

    valid = {name for name, _ in CHOICES}
    try:
        completion = await asyncio.wait_for(
            client.complete(
                role="planner",
                task="route",
                json_only=True,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _prompt(message, last_equipment=last_equipment)},
                ],
            ),
            timeout=TIMEOUT_S,
        )
    except TimeoutError:
        return Arbitration(None, "the arbiter did not answer in time")
    except Exception as cause:
        return Arbitration(None, f"the arbiter could not be reached: {type(cause).__name__}")

    chosen, why = _read(getattr(completion, "text", "") or "")
    if chosen not in valid:
        return Arbitration(None, why or "the arbiter named nothing this product has")
    return Arbitration(chosen, why)


def _read(raw: str) -> tuple[str | None, str]:
    """Pull the choice out of whatever came back.

    Models wrap JSON in prose and fences however they were feeling, so the first `{...}` is
    taken rather than the whole string parsed. Anything unreadable is an undecided route, which
    the caller already handles.
    """
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None, ""
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None, ""
    if not isinstance(parsed, dict):
        return None, ""
    skill = parsed.get("skill")
    why = str(parsed.get("why", "")).strip()
    return (skill if isinstance(skill, str) else None), why
