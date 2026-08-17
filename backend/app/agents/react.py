"""The bounded tool loop — `C20`'s registry finally has a caller, and it cannot run for ever.

**The failure this closes, stated plainly.** Six tools have been registered since 2026-08-17 —
five read-only and one permanently refused — and `G4`'s four gates have guarded **zero** calls,
because nothing in the product ever invoked one. `max_react_steps = 8` has sat in `config.py`
since M0 with nothing consuming it, one of ten resource ceilings whose stated purpose is *"a
tool loop that never terminates"* — a bound protecting a loop that did not exist. That is
inherited constraint 21 one layer along: **detection is not seeding**, because twenty-two
detected episodes sat outside the case queue and the queue read as empty. A registry nothing
calls reads the same way: as a capability the product has.

**Why a loop at all, on this plant.** On 2026-04-15 chiller 1 carried **five fault labels at
once**, and twelve equipment-days produce thirty-nine naive cases. Answering *"what is actually
wrong with this machine"* is several lookups whose second question depends on the first
answer — which is precisely the shape a single-shot pipeline cannot express.

**Four ways this loop ends, and each says which one in words:**

| | Terminates on | The failure it prevents |
|---|---|---|
| 1 | An **answer** | — the ordinary end |
| 2 | The **step ceiling** | A turn that never ends. It reports what it was *still trying to
  do*, because a loop that stops silently at step 8 looks identical to one that finished |
| 3 | A **repeated identical call** | `G5` already detects this and calls it `replayed`. A loop
  replaying the same call is stuck, and a retry that acts twice is how one approval becomes
  two work orders |
| 4 | A **refusal it cannot route around** | An authority refusal does not soften on a second
  asking. Retrying one until it succeeds is how a refused capability executes |

**The separation law's seventh row is the whole design here.** The model decides *which* tool
to call; it never decides whether it is *allowed* to. Every call in this module goes through
`Gateway.invoke`, which is where the four gates live — there is no path from here to a handler,
deliberately, because a loop that could reach `spec.handler` would be a loop that could run a
refused capability by forgetting one line.

**Nothing here calls a model.** The tool-choosing step is an injected callable, exactly as
`ModelClient`'s stub mode makes the explain path replayable: the whole loop is exercised with
the GPU terminated and MySQL stopped, and a model-backed chooser is a separate wiring step that
this module neither performs nor needs.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.config import CONTEXT_TRUNCATION_MARKER, get_settings
from app.services.control_plane import Scope
from app.tools.gateway import GATEWAY, Gateway, Outcome, ToolResult, idempotency_key
from app.tools.registry import REGISTRY, ToolRegistry


class Move(StrEnum):
    """What the chooser decided to do next. Two, and they are not interchangeable."""

    CALL_TOOL = "call_tool"
    """Reach for a capability. Which one is the model's decision; whether it may is not."""

    FINISH = "finish"
    """Stop and answer. The only move that ends the loop without a stated shortfall."""


class Routing(StrEnum):
    """Whether the loop may try something else after this outcome."""

    CONTINUE = "continue"
    STOP = "stop"


class StopReason(StrEnum):
    """Why the loop ended. Six, and five of them are not an answer.

    Kept distinct on purpose, for the reason `Outcome` keeps its refusals apart: *it ran out of
    steps* and *it was refused* are different facts about the world, and collapsing them tells a
    reader to fix the wrong thing.
    """

    ANSWERED = "answered"
    STEP_CEILING = "step_ceiling"
    REPEATED_CALL = "repeated_call"
    REFUSED = "refused"
    UNUSABLE_CHOICE = "unusable_choice"
    CHOOSER_UNAVAILABLE = "chooser_unavailable"


#: What the loop does with each gateway outcome, and the reason in words.
#:
#: Held as a table rather than a chain of `if`s so that adding an outcome is a decision somebody
#: makes, rather than a branch that silently falls into "keep going" — which is the failure mode
#: `DETERMINISTIC_SKILLS` was written as a table to prevent, one layer up.
#:
#: Exactly one entry stops the loop, and it is the authority refusal. Inherited constraint 13
#: is why: a capability is not a rank, so a refusal is not a threshold the caller can approach
#: from another angle. It is the Control Plane's answer, and it is the same answer next time.
_ROUTING: dict[Outcome, tuple[Routing, str]] = {
    Outcome.OK: (
        Routing.CONTINUE,
        "the tool answered; the loop may use what it returned to choose the next step",
    ),
    Outcome.UNKNOWN_TOOL: (
        Routing.CONTINUE,
        "the tool named does not exist, and the refusal lists the ones that do — so a second "
        "choice is an informed one rather than another guess",
    ),
    Outcome.INVALID_ARGUMENTS: (
        Routing.CONTINUE,
        "the arguments were rejected and the refusal names the field, so the same tool can be "
        "called correctly",
    ),
    Outcome.NOT_IMPLEMENTED: (
        Routing.CONTINUE,
        "this tool is declared with no handler bound. Nothing the loop does next binds one, but "
        "a different tool may still answer the question",
    ),
    Outcome.REFUSED: (
        Routing.STOP,
        "the Control Plane refused this capability for this caller. Asking again cannot change "
        "it — permission is plain software and it does not soften on a second attempt. A loop "
        "that retries a refusal until it succeeds is how a refused capability executes",
    ),
    Outcome.FAILED: (
        Routing.CONTINUE,
        "the tool broke, which is not a refusal — the system did not say no, something went "
        "wrong. Another tool may still answer, and the step ceiling bounds how long it tries",
    ),
}


@dataclass(frozen=True)
class ToolChoice:
    """One decision by the chooser: reach for a tool, or answer.

    `purpose` is not decoration. It is what the ceiling report reads back when the loop runs
    out of steps, and without it *"stopped at step 8"* is indistinguishable from *"finished"*.
    """

    move: Move
    tool: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    purpose: str = ""
    """What this call is meant to establish, in words. Never a bare tool name."""

    answer: str | None = None
    """Only on `FINISH`. `None` means no answer was produced — which is an absence, and the
    loop reports it as one rather than as an empty string that reads like a blank reply."""

    @classmethod
    def call(cls, tool: str, arguments: dict[str, Any], purpose: str) -> ToolChoice:
        return cls(move=Move.CALL_TOOL, tool=tool, arguments=arguments, purpose=purpose)

    @classmethod
    def finish(cls, answer: str) -> ToolChoice:
        return cls(move=Move.FINISH, answer=answer)

    @property
    def stated_purpose(self) -> str:
        """The purpose, or the fact that none was stated. Never blank, never a dash."""
        return self.purpose.strip() or "no purpose was stated for this call"


@dataclass(frozen=True)
class Step:
    """One turn of the loop: what was chosen, and what came back.

    The whole `ToolResult` is kept rather than a summary of it, because the trace is the only
    record of which gate refused and why — and a summary is where the reason gets shortened
    into something a reader cannot act on.
    """

    index: int
    choice: ToolChoice
    result: ToolResult

    def render(self) -> str:
        """What a chooser reads back on the next step. Words for everything that is not a value.

        The observation is the tool's own return value serialised, or the refusal's reason — an
        absence is never rendered as an empty observation, because a chooser cannot tell that
        apart from a tool that genuinely returned nothing.
        """
        if self.result.ok:
            observation = json.dumps(self.result.value, default=str, ensure_ascii=False)
        else:
            observation = f"{self.result.outcome.value} — {self.result.reason}"
        return (
            f"step {self.index}: called {self.choice.tool} "
            f"to {self.choice.stated_purpose}\n  -> {observation}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "move": self.choice.move.value,
            "tool": self.choice.tool,
            "arguments": self.choice.arguments,
            "purpose": self.choice.stated_purpose,
            "result": self.result.as_dict(),
        }


@dataclass(frozen=True)
class LoopState:
    """What the chooser is shown before it decides. Everything it needs, and nothing else.

    It is deliberately not given the gateway, the scope or the registry objects: a chooser that
    could see `spec.handler` could call around the gate, and one that could read the scope would
    be one step from deciding permission with it.
    """

    question: str
    skill: str
    steps: tuple[Step, ...]
    steps_remaining: int
    available_tools: tuple[dict[str, Any], ...]
    context_cap: int

    @property
    def is_first_step(self) -> bool:
        return not self.steps

    def render(self) -> str:
        """The transcript so far, truncated **and marked**.

        Truncating is fine; truncating silently is not — `config.py` names that one of the two
        ceilings easiest to get wrong, because a chooser answering from a fragment produces a
        step that reads complete. The marker is a constant rather than a setting for the same
        reason.
        """
        if not self.steps:
            return "nothing has been tried yet in this loop"
        body = "\n".join(step.render() for step in self.steps)
        if len(body) <= self.context_cap:
            return body
        return body[: self.context_cap] + CONTEXT_TRUNCATION_MARKER


@dataclass(frozen=True)
class LoopOutcome:
    """How the loop ended, what it produced, and what it was still trying to do.

    `answer` is `None` rather than `""` on every ending that is not an answer. Inherited
    constraint 14: a figure is a value or a stated absence, never both and never neither — and
    the same holds for the answer itself. An empty string reads as a reply nobody wrote.
    """

    question: str
    stop: StopReason
    stop_reason: str
    """Words, always. A loop that stopped for a reason a reader cannot act on has not stopped
    honestly, whatever it printed."""

    steps: tuple[Step, ...]
    ceiling: int
    unfinished_intent: str
    """What it was still trying to do when it stopped. Words even when it answered, because
    "nothing outstanding" is a fact and a blank field is not."""

    answer: str | None = None

    @property
    def has_answer(self) -> bool:
        return self.answer is not None

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def tools_called(self) -> tuple[str, ...]:
        """Which capabilities this turn actually reached. Order preserved — what was tried
        second is only meaningful against what was tried first."""
        return tuple(s.choice.tool for s in self.steps)

    def render(self) -> str:
        """The answer, or why there is not one. Never returns the empty string."""
        if self.answer is not None:
            return self.answer
        return f"No answer was produced. {self.stop_reason} {self.unfinished_intent}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "stop": self.stop.value,
            "stop_reason": self.stop_reason,
            "has_answer": self.has_answer,
            "answer": self.answer,
            "unfinished_intent": self.unfinished_intent,
            "steps_used": self.step_count,
            "ceiling": self.ceiling,
            "tools_called": list(self.tools_called),
            "steps": [s.as_dict() for s in self.steps],
        }


#: The tool-choosing step. Injected rather than imported, so the loop is exercised with the box
#: terminated — the same split that lets `ModelClient` replay a transcript instead of needing a
#: GPU in CI. A model-backed chooser lives above this module and is wired separately.
Chooser = Callable[[LoopState], Awaitable[ToolChoice]]

NOTHING_OUTSTANDING = "Nothing was outstanding — the loop finished on an answer."


class ReactLoop:
    """A bounded loop over the registry, through the gateway.

    Constructed per turn in service and fresh in every test. It holds no state between runs:
    the repeat ledger is built inside `run`, because a call made in one turn must not silently
    suppress the same call in the next — that would be idempotency across a boundary nobody
    asked for, and `G5`'s ledger already states its own limits.
    """

    def __init__(
        self,
        *,
        gateway: Gateway | None = None,
        registry: ToolRegistry | None = None,
        max_steps: int | None = None,
        tool_timeout_s: float | None = None,
        context_cap: int | None = None,
    ) -> None:
        settings = get_settings()
        self._gateway = gateway or GATEWAY
        self._registry = registry or REGISTRY
        # Ceiling 3 of the ten. Its stated purpose is *"a tool loop that never terminates"*, and
        # until now no loop existed for it to bound. Overridable so a test can drive the ceiling
        # itself rather than paying for eight steps to reach it.
        self._max_steps = settings.max_react_steps if max_steps is None else max_steps
        # Ceiling 5: *"one slow tool holding the loop"*. A per-call bound rather than a bound on
        # the whole turn, because one wedged tool must not consume the ceiling that exists to
        # stop the loop itself.
        self._tool_timeout_s = (
            settings.tool_timeout_s if tool_timeout_s is None else tool_timeout_s
        )
        # Ceiling 2: *"unbounded growth, and silent partial context"*. Applied to what the
        # chooser is shown, and the truncation is marked.
        self._context_cap = settings.max_context_chars if context_cap is None else context_cap

    @property
    def ceiling(self) -> int:
        return self._max_steps

    async def run(
        self, *, question: str, scope: Scope, choose: Chooser, skill: str = ""
    ) -> LoopOutcome:
        """Run the loop. Never raises — a failure is a turn outcome, not a crash.

        The router's rule that no layer may raise applies here for a sharper reason than usual:
        this is the one place a model's decision becomes an action, so an exception escaping it
        would be a stack trace where an audit record should be.
        """
        available = tuple(t.describe() for t in self._registry.for_skill(skill))
        steps: list[Step] = []
        issued: set[str] = set()

        if self._max_steps < 1:
            return self._never_started(question)

        for index in range(1, self._max_steps + 1):
            state = LoopState(
                question=question,
                skill=skill,
                steps=tuple(steps),
                steps_remaining=self._max_steps - index + 1,
                available_tools=available,
                context_cap=self._context_cap,
            )
            decision = await self._choose_or_stop(state, choose, index, steps)
            if isinstance(decision, LoopOutcome):
                return decision
            if decision.move is Move.FINISH:
                return self._finished(question, steps, decision)

            stopped = await self._act(
                question=question,
                choice=decision,
                scope=scope,
                index=index,
                steps=steps,
                issued=issued,
            )
            if stopped is not None:
                return stopped

        return self._hit_the_ceiling(question, steps)

    # ── the parts, kept small so `run` reads as the loop it is ──────────────────

    async def _choose_or_stop(
        self, state: LoopState, choose: Chooser, index: int, steps: list[Step]
    ) -> ToolChoice | LoopOutcome:
        """Get the next decision, or the ending that makes the loop unable to take one."""
        try:
            choice = await choose(state)
        except Exception as exc:
            # Deliberately broad. The chooser is a model in service, and `ModelUnavailable` is
            # only one of the ways it fails to produce a decision. The turn degrades to what the
            # loop has already established, and says which step it stopped on — `CONTEXT.md` §13
            # requires stating degraded mode, not substituting quietly.
            return self._stopped(
                state.question,
                steps,
                StopReason.CHOOSER_UNAVAILABLE,
                (
                    f"The step that chooses a tool could not decide at step {index}: "
                    f"{type(exc).__name__}: {exc}. Nothing was chosen in its place."
                ),
                (
                    f"It had completed {len(steps)} step(s) and was choosing the next one. "
                    f"Whatever it would have tried is unknown, and is not being guessed at."
                ),
            )

        if choice.move is Move.CALL_TOOL and not choice.tool.strip():
            return self._stopped(
                state.question,
                steps,
                StopReason.UNUSABLE_CHOICE,
                (
                    "The loop was told to call a tool and given no tool name. That is not a "
                    "request the gateway can refuse or accept, so nothing was run and nothing "
                    "was assumed in its place."
                ),
                (
                    f"It had completed {len(steps)} step(s). The decision it made at step "
                    f"{index} could not be turned into a call, so nothing was run."
                ),
            )
        return choice

    async def _act(
        self,
        *,
        question: str,
        choice: ToolChoice,
        scope: Scope,
        index: int,
        steps: list[Step],
        issued: set[str],
    ) -> LoopOutcome | None:
        """Make one call and decide whether the loop may carry on. `None` means it may."""
        key = idempotency_key(choice.tool, choice.arguments)
        if key in issued:
            return self._stopped(
                question, steps, StopReason.REPEATED_CALL,
                (
                    f"The loop chose {choice.tool} with arguments it had already used this "
                    f"turn. Replaying an identical call cannot produce a new observation, so "
                    f"the loop was going round rather than forward."
                ),
                (
                    f"It was still trying to {choice.stated_purpose}, and had run out of ways "
                    f"to ask that were not the question it had already asked."
                ),
            )
        issued.add(key)

        result = await self._invoke(choice, scope)
        steps.append(Step(index=index, choice=choice, result=result))

        if result.replayed:
            # `G5` answered from its ledger, so this exact call was already made this turn —
            # before the loop started, since the guard above catches the loop's own repeats.
            # 'replayed' is the signal that the loop is stuck rather than progressing.
            return self._stopped(
                question, steps, StopReason.REPEATED_CALL,
                (
                    f"{choice.tool} came back from the idempotency ledger rather than from the "
                    f"tool: this exact call had already been made this turn. `G5` calls that "
                    f"replayed, and a loop replaying a call is stuck."
                ),
                (
                    f"It was still trying to {choice.stated_purpose}, using a call whose answer "
                    f"it already had."
                ),
            )

        routing, why = _ROUTING[result.outcome]
        if routing is Routing.STOP:
            return self._stopped(
                question, steps, StopReason.REFUSED,
                f"{result.reason} This ends the loop: {why}.",
                (
                    f"It was trying to {choice.stated_purpose}, and that needs a capability "
                    f"this caller does not hold. Nothing else it could choose supplies it."
                ),
            )
        return None

    async def _invoke(self, choice: ToolChoice, scope: Scope) -> ToolResult:
        """One call, through the gateway and nowhere else.

        There is no branch here that reaches a handler, and that absence is the design: the four
        gates live in `Gateway.invoke`, so a loop that could construct a result some other way
        would be a loop that could run a refused capability by forgetting one line.
        """
        try:
            return await asyncio.wait_for(
                self._gateway.invoke(choice.tool, choice.arguments, scope),
                timeout=self._tool_timeout_s,
            )
        except TimeoutError:
            # Not a refusal — the tool did not say no, it did not answer in time. Reported as a
            # failure with the bound named, so a reader can tell a slow tool from a broken one.
            return ToolResult(
                tool=choice.tool,
                outcome=Outcome.FAILED,
                reason=(
                    f"{choice.tool} did not answer within {self._tool_timeout_s}s and the call "
                    f"was abandoned. Whether it would eventually have answered is unknown; the "
                    f"bound exists so one slow tool cannot hold the loop."
                ),
                arguments=dict(choice.arguments),
            )

    def _never_started(self, question: str) -> LoopOutcome:
        """A ceiling below one. Reported rather than returned as an empty trace, because an
        empty trace reads like a question nobody asked rather than one nobody was allowed."""
        return LoopOutcome(
            question=question,
            stop=StopReason.STEP_CEILING,
            stop_reason=(
                f"The step ceiling is {self._max_steps}, so no tool was allowed to run at all. "
                f"A ceiling of zero is not a safe loop; it is a loop that cannot start."
            ),
            steps=(),
            ceiling=self._max_steps,
            unfinished_intent=(
                "It had not begun — the question was never given a single step in which to "
                "reach for anything."
            ),
        )

    def _hit_the_ceiling(self, question: str, steps: list[Step]) -> LoopOutcome:
        """Every step spent, and the last decision was a call rather than an answer.

        The last choice's purpose is read back verbatim. Without it *"stopped at step 8"* is
        indistinguishable from *"finished at step 8"*, and the two mean opposite things to
        whoever is reading the trace.
        """
        last = steps[-1]
        return self._stopped(
            question, steps, StopReason.STEP_CEILING,
            (
                f"The loop reached its ceiling of {self._max_steps} step(s) without producing "
                f"an answer. The bound exists to stop a tool loop that never terminates; it is "
                f"a ceiling rather than a verdict, so nothing here says the question is "
                f"unanswerable."
            ),
            (
                f"It was still trying to {last.choice.stated_purpose} — its last call was "
                f"{last.choice.tool}, which returned {last.result.outcome.value}. "
                f"{len(steps)} tool call(s) were made and none of them completed the answer."
            ),
        )

    def _finished(
        self, question: str, steps: list[Step], choice: ToolChoice
    ) -> LoopOutcome:
        """The chooser stopped. It has either an answer or an absence, and never both."""
        answer = (choice.answer or "").strip()
        if not answer:
            return self._stopped(
                question, steps, StopReason.UNUSABLE_CHOICE,
                (
                    "The loop was told to finish and given no answer to finish with. An empty "
                    "answer reads as a reply nobody wrote, so it is reported as an absence."
                ),
                (
                    f"It had completed {len(steps)} step(s) and decided it was done. What it "
                    f"concluded from them was never stated."
                ),
            )
        return LoopOutcome(
            question=question,
            stop=StopReason.ANSWERED,
            stop_reason=(
                f"The loop answered after {len(steps)} tool call(s), within its ceiling of "
                f"{self._max_steps}."
            ),
            steps=tuple(steps),
            ceiling=self._max_steps,
            unfinished_intent=NOTHING_OUTSTANDING,
            answer=answer,
        )

    def _stopped(
        self,
        question: str,
        steps: list[Step],
        stop: StopReason,
        stop_reason: str,
        unfinished_intent: str,
    ) -> LoopOutcome:
        """Every ending that is not an answer. `answer` stays `None`, deliberately."""
        return LoopOutcome(
            question=question,
            stop=stop,
            stop_reason=stop_reason,
            steps=tuple(steps),
            ceiling=self._max_steps,
            unfinished_intent=unfinished_intent,
        )
