"""Which registered tool answers a plant question nobody wrote a keyword for.

**The hole this closes was invisible to a 31-question suite, because I wrote the questions.**
Every one of them matched a phrase in the catalogue planner, so every one was answered. Six
ordinary questions written afterwards — *"which chiller uses more power"*, *"what is the kW/TR
on chiller 1"*, *"how many days of data do we have"*, *"is chiller 1 fouling"* — all failed,
four of them with *"there is no scored evidence for that request"* while `compare_equipment`,
`equipment_standing` and `plant_overview` sat registered and unreached.

**Routing was arbitrated; answering was not.** `arbiter.py` picks which *skill* takes a turn,
and that was the visible half of the problem. The catalogue planner underneath it — the branch
that decides which of fourteen tools runs — stayed a keyword ladder, so a question could be
routed correctly and still fall out of the bottom. A reader cannot tell those two failures
apart: both come back saying the platform has nothing.

**It chooses a tool; it never invents a call.** Only tools already in the registry, only ones
whose whole argument list can be filled from what the deterministic layers already resolved,
and only read-only ones. `set_chiller_setpoint` is registered — it exists so the Control Plane
can refuse it — and a model that could name it would be a model reaching for an actuator.

**The registry's own descriptions are the menu.** Written for the gateway, reused here, so a
tool added tomorrow is choosable tomorrow without a second list to drift. `C20`'s register is
the one source of truth for what this platform can do.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

#: How long to wait before falling back to the deterministic answer. Longer than the router's
#: budget because this call decides whether the turn answers at all, rather than which of seven
#: skills takes it — but still bounded, because a turn that hangs reads as a broken product.
TIMEOUT_S: float = 30.0

#: Tools the arbiter may never name, whatever the registry says. `set_chiller_setpoint` is
#: registered precisely so `G4` can refuse it; a model that could select it would be a model
#: reaching for plant equipment, which is the one thing this product never does.
NEVER_CHOSEN: frozenset[str] = frozenset({"set_chiller_setpoint"})

_SYSTEM = (
    "You choose which read-only lookup answers a question about an industrial chiller plant.\n\n"
    "You never answer the question yourself. You never state a reading, name a fault, judge a "
    "machine or decide anything is urgent. You pick one lookup from the list, and the lookup "
    "produces the answer.\n\n"
    "Pick the one whose description covers what was asked. If none of them does, return null — "
    "the platform will say it cannot answer, which is better than running a lookup that "
    "answers a different question.\n\n"
    "Reply with JSON only:\n"
    '{"tool": "<a name from the list, or null>", "why": "<one short sentence>"}'
)


@dataclass(frozen=True)
class ToolChoice:
    """Which lookup the model chose, and why. `tool` is `None` when it declined."""

    tool: str | None
    why: str = ""

    @property
    def decided(self) -> bool:
        return self.tool is not None


def _menu(specs: list) -> str:
    """The registry's own descriptions, as the list the model chooses from."""
    return "\n".join(f"- {spec.name}: {spec.description}" for spec in specs)


async def choose(
    question: str,
    *,
    specs: list,
    client,
    equipment_known: bool,
) -> ToolChoice:
    """Ask which lookup answers this. **Never raises, never blocks past the timeout.**

    `equipment_known` gates the tools that need a machine named. Offering one when the
    deterministic layers resolved no equipment would produce a call with a hole in it — and
    filling that hole is exactly the invention this whole layer exists to avoid.
    """
    if client is None or not specs:
        return ToolChoice(None, "no model was available to choose a lookup")

    offered = [
        spec
        for spec in specs
        if spec.name not in NEVER_CHOSEN
        and (equipment_known or not _needs_equipment(spec))
    ]
    if not offered:
        return ToolChoice(None, "no lookup could be filled from what this question resolved")

    # **Asked twice before believing a refusal.** Measured on this box: *"what should I look at
    # first this morning"* chose `plant_overview` on one call and returned null on the next,
    # with the same prompt and the same model. A question that answers and then does not is
    # worse than one that never answers — the reader concludes the product is unreliable rather
    # than bounded, and no amount of correct behaviour afterwards undoes that.
    #
    # The cost is real and worth naming: a *genuine* decline now takes two calls rather than
    # one. That is the right trade because a genuine decline is rare and a false one is
    # indistinguishable, to a reader, from the platform having nothing.
    for attempt in (1, 2):
        picked = await _ask_once(question, offered=offered, client=client)
        if picked.decided:
            return picked
        if attempt == 2:
            return picked
    return ToolChoice(None, "no lookup was chosen")


async def _ask_once(question: str, *, offered: list, client) -> ToolChoice:
    """One call to the chooser. Every failure returns undecided rather than raising."""
    try:
        completion = await asyncio.wait_for(
            client.complete(
                role="planner",
                task="choose_tool",
                json_only=True,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"LOOKUPS:\n{_menu(offered)}\n\n"
                            f"QUESTION: {question}\n\n"
                            "Which lookup answers this?"
                        ),
                    },
                ],
            ),
            timeout=TIMEOUT_S,
        )
    except TimeoutError:
        return ToolChoice(None, "the lookup chooser did not answer in time")
    except Exception as cause:
        return ToolChoice(None, f"the lookup chooser could not be reached: {type(cause).__name__}")

    chosen, why = _read(getattr(completion, "text", "") or "")
    if chosen not in {spec.name for spec in offered}:
        return ToolChoice(None, why or "the chooser named nothing this platform has")
    return ToolChoice(chosen, why)


def _needs_equipment(spec) -> bool:
    """Whether this tool cannot run without a machine named.

    Read from the parameter model rather than a hand-kept list, so a tool that grows an
    equipment argument is covered by that change alone.
    """
    fields = getattr(spec.parameters, "model_fields", {})
    return "equipment_key" in fields


def _read(raw: str) -> tuple[str | None, str]:
    """Pull the choice out of whatever came back. Anything unreadable leaves it undecided."""
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
    tool = parsed.get("tool")
    return (tool if isinstance(tool, str) else None), str(parsed.get("why", "")).strip()
