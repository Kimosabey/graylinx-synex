"""A broad question answered from several reads at once, rather than from the best single one.

**The shape of question this exists for.** *"Give me a full review of the plant"*, *"what should
I know before the handover"*, *"how are we doing overall"* — none names one thing to look up.
The tool chooser picks the single best capability for a question, which is right when there is
one and wrong here: a review answered from `plant_overview` alone is a review missing the
reconciliation and the signal standing, and a reader cannot tell which parts were left out.

**The planner decides what to read, never what is wrong.** It names capabilities from the
registry and nothing else — no fault, no priority, no verdict. Choosing which drawers to open
is not deciding what is in them, so `CONTEXT.md` §5 is untouched. A bad plan produces a thinner
answer; it cannot produce an ungrounded one, because every capability it can name is the same
read-only tool a direct question would have reached.

**Parallel, and bounded at four.** The reads are independent, so running them in sequence is
four round trips for one answer and a reader waits four times as long. Four because a plan is
a prompt-sized thing: past that the results stop fitting the composer's window and the
evidence starts being surrendered to make room, which trades the thing that makes an answer
true for more of the thing that makes it broad.

**A failed read is named, never dropped.** If three of four capabilities answer, the fourth is
reported as unavailable in the synthesis. A review silently assembled from three quarters of
what it meant to gather reads exactly like a complete one — that is the *"machinery with no
consumer"* failure in a different costume, and this is where it would be least visible.

**`PARTIAL`, always.** A review of a plant where ten of twelve machines have no fitted model is
partial by construction, whatever it manages to gather.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

#: How many capabilities one plan may name. See the module note: past four the results crowd
#: the evidence out of the composer's window.
MAX_STEPS: int = 4

#: How long the planner may take. The roster budgets ~25s for a plan on the brain and this is a
#: short one, but a router that can hang is a product that appears to hang.
TIMEOUT_S: float = 30.0

_SYSTEM = (
    "You plan which read-only lookups answer a broad question about an industrial chiller "
    "plant. You choose what to READ. You never decide what is wrong with a machine, how "
    "urgent anything is, or what any reading means — those are decided elsewhere, from the "
    "results you gather.\n\n"
    f"Name between one and {MAX_STEPS} lookups from the list, in the order they should be "
    "read. Do not name the same one twice. If one lookup answers the whole question, name "
    "only that one — a plan is not better for being longer.\n\n"
    "Reply with JSON only:\n"
    '{"steps": [{"tool": "<name from the list>", "why": "<what this contributes>"}]}'
)


@dataclass(frozen=True)
class Step:
    """One read the plan calls for, and what it was expected to contribute."""

    tool: str
    why: str = ""
    value: dict | None = None
    failed: str = ""

    @property
    def answered(self) -> bool:
        return self.value is not None and not self.failed


@dataclass(frozen=True)
class Plan:
    """What was read, what came back, and what did not."""

    steps: tuple[Step, ...] = field(default_factory=tuple)
    reason: str = ""

    @property
    def any_answered(self) -> bool:
        return any(s.answered for s in self.steps)

    def as_evidence(self) -> dict:
        """The gathered results, shaped for one composed answer.

        Failures travel beside successes rather than being filtered out: a review assembled
        from three quarters of what it meant to gather reads exactly like a complete one.
        """
        return {
            "gathered": {s.tool: s.value for s in self.steps if s.answered},
            "could_not_read": {s.tool: s.failed for s in self.steps if not s.answered},
            "note": (
                "Each entry is one read-only lookup. Nothing here has been ranked or judged — "
                "say what the results show and name anything that could not be read."
            ),
        }


async def plan(question: str, *, specs: list, client) -> tuple[str, ...]:
    """Which capabilities to read for this question. Empty when no plan could be made.

    Empty rather than a default plan: a planner that falls back to reading everything turns a
    model failure into four unnecessary round trips, and the caller has a single-tool path that
    is better than a guessed multi-tool one.
    """
    if client is None or not specs:
        return ()

    menu = "\n".join(f"- {s.name}: {s.description}" for s in specs)
    try:
        completion = await asyncio.wait_for(
            client.complete(
                role="planner",
                task="plan",
                json_only=True,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": f"LOOKUPS:\n{menu}\n\nQUESTION: {question}"},
                ],
            ),
            timeout=TIMEOUT_S,
        )
    except Exception:
        return ()

    known = {s.name for s in specs}
    named: list[str] = []
    for step in _read(getattr(completion, "text", "") or ""):
        # Deduplicated on the way in: a plan naming the same lookup twice reads it twice and
        # composes an answer that says the same thing in two places.
        if step in known and step not in named:
            named.append(step)
    return tuple(named[:MAX_STEPS])


async def gather(tools: tuple[str, ...], *, run) -> Plan:
    """Run the planned reads at once. **Never raises.**

    `run` is a callable taking a tool name and returning its result — the gateway invocation,
    handed in so this module needs neither a registry nor a connection.
    """
    if not tools:
        return Plan(reason="no plan was made, so nothing was gathered")

    async def one(name: str) -> Step:
        try:
            value = await run(name)
        except Exception as cause:
            return Step(tool=name, failed=f"{type(cause).__name__}")
        if value is None:
            return Step(tool=name, failed="the lookup returned nothing")
        return Step(tool=name, value=value)

    return Plan(steps=tuple(await asyncio.gather(*(one(name) for name in tools))))


def _read(raw: str) -> list[str]:
    """Pull the tool names out of whatever came back. Anything unreadable plans nothing."""
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    steps = parsed.get("steps") if isinstance(parsed, dict) else None
    if not isinstance(steps, list):
        return []
    return [
        s["tool"]
        for s in steps
        if isinstance(s, dict) and isinstance(s.get("tool"), str)
    ]
