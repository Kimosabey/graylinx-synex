"""The skill dispatch — `C3`'s other half, and the end of the fall-through.

**The gap this closes, stated plainly.** `SESSION-HANDOFF.md` §8 has said since M1 that *five
of seven skills route correctly then fall into the same explain path*. The routing ladder was
never the problem: it resolves `look_up`, `prepare_work`, `resolve` and `verify` correctly and
carries the skill into the route frame, so the Inspector showed a skill the turn then ignored.
A router whose decision changes nothing is a router that only looks like one.

**What each skill actually needs already exists.** Every service below was built and tested
milestones ago and reachable from nothing:

| Skill | Reaches | Built in |
|---|---|---|
| `look_up` | the pack's figures, exact, no prose | `C17` · `C21` |
| `explain` | the model, over the pack | `C5` |
| `investigate` | the pack plus the same day's other labels and the differential | `C4` · `C6` |
| `prepare_work` | `work_orders.draft_from_pack` | `W2`–`W4` |
| `resolve` | `cases.case_from_pack` | `RC1`–`RC5` |
| `verify` | `analytics.verification` | `V1`–`V4` |

**Four of the six need no model at all**, and that is the point rather than a limitation. A
look-up that asked a model to read a number back would be the one place `C21`'s figure
discipline could not hold — only `FigureView` renders a number, and it never formats. So
`look_up` returns the pack's display strings untouched and `used_model` is `False`, which the
route trace shows.

**Nothing here decides anything.** Each branch composes services that already own their rules:
`may_advance` still owns the blocking gate, the priority formula still owns priority, the
gates still decide whether anything may be diagnosed at all. This module chooses *which
question is being answered*, which is exactly what the separation law leaves to routing.

---

**The second failure this file now closes: `react.py` had no caller.** `C20` registered six
tools, `G4` grew four gates, `react.py` grew a bounded loop with four endings and 32 green
tests — and no request reached any of it, because `register_all()` was never called in a live
process and nothing imported `ReactLoop` but its own test file. That is the sixth time in one
day that a module was built, tested, and consumed by nothing: `RC18`'s stored readings, the
tool registry itself, `context.py`, `app/eval/`, `retrieval/quality.py`, and this. A test that
imports a module is not a consumer. The question is whether a **request** reaches it, and
until `investigate` below called the loop, the honest answer was no.

**Why `investigate` is the right first consumer.** `SESSION-HANDOFF.md` §11.1 marks `C4`
*"what evidence to gather"* as a decision still taken by rules rather than by judgement, and
that decision is exactly what a tool loop is. It is also the one skill whose second question
depends on the first answer: on 2026-04-15 chiller 1 carried **five fault labels at once**, so
*"what is actually wrong with this machine"* is *look the label up, ask whether it may be
narrowed, then ask the same of every other label recorded that day* — a shape a single-shot
pipeline cannot express.

**The chooser here is deterministic, and that is the design rather than a shortfall.** It
picks from the catalogue by rule, so the whole loop is reachable and testable with the GPU
terminated — the same split that lets `ModelClient` replay a committed transcript instead of
needing a card in CI. A model-backed chooser needs a prompt and a transcript recorded against
the Jarvis box, and is a separate wiring step this module neither performs nor needs.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agents import compose
from app.agents.react import (
    Chooser,
    LoopOutcome,
    LoopState,
    ReactLoop,
    Step,
    StopReason,
    ToolChoice,
)
from app.config import get_settings
from app.domain import differential as diff
from app.domain import equipment as _eq
from app.domain.answer import AnswerState
from app.domain.cases import Capability
from app.services.cases import case_from_pack
from app.services.control_plane import Scope
from app.services.evidence import EvidencePack
from app.services.work_orders import draft_from_pack
from app.tools.gateway import Gateway, Outcome, idempotency_key
from app.tools.plant_tools import register_all
from app.tools.registry import REGISTRY, ToolRegistry


@dataclass(frozen=True)
class SkillOutcome:
    """What a deterministic skill produced. `None` text means *fall through to explain*."""

    state: AnswerState
    text: str
    used_model: bool = False
    payload: dict | None = None

    degraded_reason: str = ""
    """Why this skill produced less than it can, in words. Empty means *nothing was withheld*.

    Carried rather than swallowed because `CONTEXT.md` §13 requires degraded mode to be
    **stated**, not silently substituted: *"no identity reached this turn so no tool was
    called"* and *"the tool loop ran and answered"* are different turns, and a reader who
    cannot tell them apart will trust the weaker one as though it were the stronger."""

    @property
    def is_terminal(self) -> bool:
        return bool(self.text)


def _evidence_line(evidence) -> str:
    """One residual, rendered as the pack rendered it.

    **Nothing is reformatted here.** `ResidualEvidence.render()` already produces the string
    the pack carries, and the pack carries display strings rather than floats precisely so the
    numeric audit can compare exact values. Re-rendering would reintroduce a tolerance, and
    every tolerance forgives some fabrication.
    """
    return evidence.render()


def look_up(pack: EvidencePack) -> SkillOutcome:
    """`C17`. The exact numbers, and **no model is spent**.

    A look-up that routed through a model would put a language model between a reader and a
    figure, which is the one place `C21`'s discipline cannot survive: the model would have to
    reproduce the string, and reproducing a number is where a number gets rounded.
    """
    evidence = pack.residual_evidence
    lines = [_evidence_line(e) for e in evidence]
    absences = sum(1 for e in evidence if e.figure.value is None)

    body = "\n".join(lines) if lines else "This episode carries no residual evidence."
    note = (
        f"\n\n{absences} of {len(evidence)} figures are a stated absence rather than a "
        f"value. An absence is not a zero."
        if absences
        else ""
    )
    return SkillOutcome(
        state=AnswerState.ANSWERED,
        text=(
            f"{pack.equipment_display} on {pack.window.render()}, read straight from the "
            f"evidence:\n\n{body}{note}"
        ),
        used_model=False,
        payload={"figures": [e.figure.as_dict() for e in pack.residual_evidence]},
    )


def investigate(pack: EvidencePack) -> SkillOutcome:
    """`C4`/`C6`. What else was true that day, and whether the class can be narrowed at all.

    Falls through to `explain` for the prose — the enquiry is deterministic, the explanation
    is not. What it adds is the two facts a single-label answer hides: the other labels on the
    same machine that day, and whether this class even *qualifies* for a differential.
    """
    others = pack.other_labels_same_day
    label = pack.fault_label or ""
    qualifies = diff.has_differential(label)
    authored = diff.differential_for(label) is not None

    lines = [
        f"Investigating {label or 'an unlabelled slot'} on {pack.equipment_display}, "
        f"{pack.window.render()}."
    ]
    if others:
        lines.append(
            f"The same machine carried {len(others)} other label(s) that day: "
            f"{', '.join(others)}. One repair may explain several — a reader who does not "
            f"know that raises several jobs."
        )
    else:
        lines.append("No other label was recorded on this machine that day.")

    if not qualifies:
        lines.append(
            "This class names a mechanism, so it does not get a differential — narrowing it "
            "would invent ambiguity the trained model never reported."
        )
    elif not authored:
        lines.append(
            "This class declares itself undecidable and qualifies for a differential, but no "
            "candidate set has been authored for it yet. That is missing content, not an "
            "absence of ambiguity."
        )
    else:
        lines.append(
            "This class declares itself undecidable and has a differential — the candidates "
            "can be narrowed by asking, once the discriminators have been reviewed."
        )

    return SkillOutcome(
        state=AnswerState.PARTIAL if not pack.may_diagnose else AnswerState.ANSWERED,
        text="\n\n".join(lines),
        used_model=False,
        payload={
            "other_labels_same_day": list(others),
            "qualifies_for_differential": qualifies,
            "differential_authored": authored,
        },
    )


def prepare_work(pack: EvidencePack) -> SkillOutcome:
    """`W2`–`W4`. A draft carrying its own justification, and it says it is a draft.

    `NEEDS_APPROVAL` rather than `ANSWERED`: nothing is persisted and nobody has approved it.
    A work order that reads as dispatchable when it is not is worse than none, because
    somebody plans against it.
    """
    draft = draft_from_pack(pack)
    priority = draft.priority

    # `missing` is (name, reason) pairs rather than bare names, deliberately: `W4`'s formula
    # spans criticality, SLA and production impact, and three of the four inputs do not exist
    # in this snapshot (`Q51`). Naming the input without the reason would read as an omission
    # somebody could fill in, when it is an absence in the plant's records.
    absent = ", ".join(name for name, _ in priority.missing)
    incomplete = (
        f" The priority is incomplete — {absent} do not exist in this snapshot, so it is "
        f"reported with what was used rather than as a finished rank."
        if not priority.is_complete
        else ""
    )
    return SkillOutcome(
        state=AnswerState.NEEDS_APPROVAL,
        text=(
            f"{draft.title}\n\nPriority {priority.band}. {len(draft.evidence)} evidence "
            f"line(s) travel with this job, each naming its source.{incomplete}\n\n"
            f"This is a draft. Nothing is persisted and nobody has approved it."
        ),
        used_model=False,
        payload=draft.as_dict(),
    )


def resolve(pack: EvidencePack) -> SkillOutcome:
    """`RC1`–`RC5`. Open the case and report whether it may advance — usually it may not.

    Two thirds of measured cases pause: 26 of 43 stop at the checks. So the common outcome
    here is `BLOCKED` with the reason, and that is the feature rather than a shortfall.
    """
    case = case_from_pack(pack)
    return SkillOutcome(
        state=AnswerState.ANSWERED if case.may_advance else AnswerState.BLOCKED,
        text=(
            f"Case {case.id} is {case.state.value}. {case.advance_reason}\n\n"
            f"The checklist content is sample content and every surface says so — the curated "
            f"library is unreviewed, so no real item is shown to anyone yet."
        ),
        used_model=False,
        payload=case.as_dict(Capability.TECHNICIAN),
    )


def verify(pack: EvidencePack) -> SkillOutcome:
    """`V1`–`V4`. Refuses rather than guessing, and the refusal is the honest answer.

    Verification compares post-work residuals against this asset's own band. A turn asking to
    verify from an episode alone has no *after* window, and inventing one would be the failure
    `V1` exists to prevent: a label disappearing looked like a successful repair while the
    residual got worse, because the gates had stopped passing and nothing was being judged.
    """
    return SkillOutcome(
        state=AnswerState.BLOCKED,
        text=(
            "Verification needs a post-work window to compare against, and this request "
            "carries only the episode. A label that has stopped appearing is not evidence "
            "that a repair worked — on this plant a class disappeared after 2026-04-22 and "
            "never returned while the residual got worse over the following week, because the "
            "gates had stopped passing and nothing was being judged at all.\n\n"
            "Close the work order through the verification surface, which reads the after "
            "window."
        ),
        used_model=False,
    )


#: The dispatch. Held as a table rather than a chain of `if`s so a skill that is routed but
#: not dispatched is a missing key somebody can see, rather than a silent fall-through — which
#: is precisely how five skills went a milestone without one.
DETERMINISTIC_SKILLS = {
    "look_up": look_up,
    "investigate": investigate,
    "prepare_work": prepare_work,
    "resolve": resolve,
    "verify": verify,
}


def dispatch(skill: str, pack: EvidencePack) -> SkillOutcome | None:
    """Run the skill's own path, or `None` when it is `explain` and belongs to the model.

    Never raises. A skill that fails is a turn outcome, not a crash — the router's rule, one
    layer along.
    """
    handler = DETERMINISTIC_SKILLS.get(skill)
    if handler is None:
        return None
    try:
        return handler(pack)
    except Exception as exc:
        return SkillOutcome(
            state=AnswerState.FAILED,
            text=(
                f"The {skill} skill could not complete: {type(exc).__name__}: {exc}. "
                f"Nothing was assumed in its place."
            ),
            used_model=False,
        )


# ═══════════════════════════════════════════════════════════════════════════════════════
# `investigate`, through the bounded tool loop — the first request path that reaches `C20`
# ═══════════════════════════════════════════════════════════════════════════════════════

#: The one skill that reaches for tools today. Named rather than inlined so a reader can see
#: at a glance that exactly one skill does, and grep for every place that fact matters.
TOOL_USING_SKILL = "investigate"

#: Which catalogue the loop is offered, and **why it is not narrowed to `investigate`.**
#:
#: `ToolRegistry.for_skill("investigate")` returns nothing at all today: of the six registered
#: tools, `explain_fault_class` declares `skill="explain"`, `differential_availability`
#: declares `skill="resolve"`, and none declares `investigate`. Narrowing to an empty
#: catalogue would hand the chooser a loop it cannot start, and the turn would read as *there
#: is nothing to investigate* when the truth is *no tool has been scoped to this skill yet* —
#: which is the same confusion `for_skill` was fixed on 2026-08-17 to stop making.
#:
#: So the loop is run unnarrowed, which `for_skill("")` documents as *the caller has not
#: narrowed* and which still excludes every permanently-refused tool. The plan below names the
#: tools it wants, so the wider catalogue widens nothing in practice. **TBD (Q103):** the tool
#: scopes belong in `plant_tools.py`, which this task does not own.
CATALOGUE_SCOPE = ""


class ChooserTimeout(Exception):
    """The chooser did not decide inside its bound.

    A named exception with a worded message rather than a bare `TimeoutError`, because
    `ReactLoop._choose_or_stop` renders `type(exc).__name__: exc` into the stop reason and
    `str(TimeoutError())` is the empty string — which would put a blank where the reason
    belongs, in the one place the loop exists to explain itself.
    """


def chooser_timeout_s() -> float:
    """How long the chooser gets to decide.

    **TBD (Q102), and the number is borrowed rather than invented.** `asyncio.wait_for` guards
    `Gateway.invoke` inside the loop and nothing guarded the chooser call, so a chooser that
    never returned held the turn for ever — `max_react_steps` bounds how *many* decisions are
    taken, never how long one takes. None of the ten resource ceilings covers this: ceiling 5
    `tool_timeout_s` bounds one tool call and ceiling 8 `router_arbiter_timeout_s` bounds the
    routing arbiter. Rather than invent an eleventh number, this borrows ceiling 5 — a chooser
    is one call to something that can wedge in exactly the way a tool can — and says so.
    `Q102` asks for a ceiling of its own, and asks that the bound move inside `ReactLoop.run`
    so every future caller inherits it rather than remembering it.
    """
    return get_settings().tool_timeout_s


def bounded_chooser(choose: Chooser, timeout_s: float) -> Chooser:
    """Wrap a chooser so one that never returns ends the turn instead of holding it.

    The timeout becomes `CHOOSER_UNAVAILABLE` rather than an exception escaping the loop: the
    loop already treats *the step that chooses could not decide* as an ending with a stated
    shortfall, and a bound is one more way it cannot decide.
    """

    async def _bounded(state: LoopState) -> ToolChoice:
        try:
            return await asyncio.wait_for(choose(state), timeout=timeout_s)
        except TimeoutError as exc:
            raise ChooserTimeout(
                f"the step that chooses a tool did not decide within {timeout_s}s and the "
                f"decision was abandoned. Whether it would eventually have chosen is unknown; "
                f"the bound exists so one wedged chooser cannot hold the turn"
            ) from exc

    return _bounded


@dataclass(frozen=True)
class PlannedCall:
    """One call the rules decided to make, and what it is meant to establish.

    `purpose` is not decoration: it is what the ceiling report reads back when the loop runs
    out of steps, and without it *"stopped at step 8"* is indistinguishable from *"finished"*.
    """

    tool: str
    arguments: dict[str, Any]
    purpose: str

    @property
    def key(self) -> str:
        """`G5`'s key over this call. Reused rather than re-derived so *the same call* means
        the same thing here as it does at the gate — a second definition is a second answer."""
        return idempotency_key(self.tool, self.arguments)


def plan_for(pack: EvidencePack) -> tuple[PlannedCall, ...]:
    """What `C4` decides to gather, held as data with the reason on each line.

    The order is the dependency: what the label *is* before whether it can be narrowed, and
    both before the other labels recorded the same day. An empty plan is returned for a slot
    with no label, and that is a real state rather than a gap — 5,309 slots on this snapshot
    carry no fault against 674 that do.
    """
    label = (pack.fault_label or "").strip()
    if not label:
        return ()

    plan = [
        PlannedCall(
            tool="explain_fault_class",
            arguments={"fault_label": label},
            purpose=(
                "establish what is settled about the label the detector emitted — its "
                "severity, whether that severity is rated at all, and whether the class "
                "declares itself undecidable — before anything is said about this machine"
            ),
        ),
        PlannedCall(
            tool="differential_availability",
            arguments={"fault_label": label},
            purpose=(
                "establish whether this class may be narrowed at all, because narrowing one "
                "that already names a mechanism would invent ambiguity the trained model "
                "never reported — inherited constraint 27"
            ),
        ),
    ]
    for other in pack.other_labels_same_day:
        if other == label:
            continue
        plan.append(
            PlannedCall(
                tool="explain_fault_class",
                arguments={"fault_label": other},
                purpose=(
                    f"establish whether {other}, recorded on this machine the same day, names "
                    f"a mechanism of its own or the same one — one repair may explain several, "
                    f"and a reader who does not know that raises several jobs"
                ),
            )
        )
    return tuple(plan)


@dataclass(frozen=True)
class PlannedChooser:
    """The deterministic chooser: it picks from the catalogue by rule, and calls no model.

    It is a chooser rather than a script. Every decision is taken against `LoopState` — what
    the catalogue actually offers this turn and what has already been tried — so a tool that
    is missing, refused or broken changes what it does next, which is the behaviour a
    model-backed chooser will have to reproduce. Swapping one in replaces this class and
    nothing else, and that is the whole reason `Chooser` is injected.

    It never decides whether a call is *allowed*: every choice it returns goes to
    `Gateway.invoke`, where the four gates live. Separation law, row 7.
    """

    pack: EvidencePack
    plan: tuple[PlannedCall, ...]

    async def __call__(self, state: LoopState) -> ToolChoice:
        offered = {tool["name"] for tool in state.available_tools}
        tried = {idempotency_key(s.choice.tool, s.choice.arguments) for s in state.steps}
        for call in self.plan:
            # A planned tool the catalogue does not offer is skipped rather than called: an
            # invented tool name is a refusal the gateway would have to issue, and choosing
            # one the catalogue never listed is guessing dressed as a decision.
            if call.tool not in offered or call.key in tried:
                continue
            return ToolChoice.call(call.tool, dict(call.arguments), call.purpose)
        return ToolChoice.finish(compose_answer(self.pack, self.plan, state.steps))


# ── turning what came back into words ───────────────────────────────────────────────────

def _render_fault_class(value: dict[str, Any]) -> str:
    """`explain_fault_class`. Severity is reported with whether it is **rated**, always.

    `Q49`: eight of the nine labels have no agreed severity. Printing the fallback without
    saying it is a fallback is how an unrated class acquires a rank somebody schedules against.
    """
    label = value.get("label") or value.get("fault_label") or "an unnamed class"
    if not value.get("found"):
        return str(value.get("reason") or f"{label} is not a class this plant's model emits.")

    severity = value.get("severity") or "no severity was returned"
    if value.get("severity_is_rated"):
        severity_part = f"severity {severity}, which is rated"
    else:
        note = value.get("severity_note") or "no reason for the absence was returned"
        severity_part = (
            f"NO rated severity — {note}. The value returned is {severity!r}, which is a "
            f"stated absence rather than a rank"
        )

    undecidable = (
        "declares itself undecidable"
        if value.get("declares_undecidable")
        else "names a mechanism rather than declaring itself undecidable"
    )
    narrowing = (
        "and has a differential" if value.get("has_differential") else "and gets no differential"
    )
    return f"{label}: {severity_part}. It {undecidable}, {narrowing}."


def _render_differential(value: dict[str, Any]) -> str:
    """`differential_availability`. The verdict and its reason, never the verdict alone."""
    label = value.get("fault_label") or "this class"
    verdict = "can be narrowed" if value.get("has_differential") else "cannot be narrowed"
    reason = value.get("reason") or "no reason was returned"
    return f"Narrowing {label}: it {verdict} — {reason}."


#: How each tool's return value becomes a line of the answer.
#:
#: A renderer per tool rather than one that paraphrases whatever came back. A summariser that
#: guesses at an unfamiliar shape is a summariser that will one day render an absence as a
#: value — which is the failure the whole figure discipline exists to prevent. A tool with no
#: entry here is reported verbatim **and said to be verbatim**, which is uglier and honest.
_OBSERVATION_RENDERERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "explain_fault_class": _render_fault_class,
    "differential_availability": _render_differential,
}


def _observation_line(step: Step) -> str:
    """One step, rendered. A refusal reads as a refusal; nothing renders as nothing."""
    if not step.result.ok:
        return (
            f"It could not {step.choice.stated_purpose}: {step.choice.tool} came back "
            f"{step.result.outcome.value} — {step.result.reason}"
        )
    renderer = _OBSERVATION_RENDERERS.get(step.choice.tool)
    value = step.result.value
    if renderer is None or not isinstance(value, dict):
        return (
            f"{step.choice.tool} returned a shape this summary cannot read, so it is quoted "
            f"rather than paraphrased: {json.dumps(value, default=str, ensure_ascii=False)}"
        )
    return renderer(value)


def _never_asked_line(call: PlannedCall) -> str:
    return (
        f"{call.tool} was never asked to {call.purpose}: it is not in the catalogue this turn "
        f"was offered. What it would have established is unknown and is not being guessed at."
    )


NO_LABEL_NO_TOOLS = (
    "No tool was called, because this slot carries no fault label — there is no class to look "
    "up and nothing to narrow. On this snapshot 5,309 slots carry no fault against 674 that "
    "do, so an unlabelled slot is the ordinary case rather than a gap in the evidence."
)

SEVERAL_LABELS_ONE_REPAIR = (
    "One repair may explain several of these labels. A reader who does not know that raises "
    "several jobs."
)


def compose_answer(
    pack: EvidencePack, plan: tuple[PlannedCall, ...], steps: tuple[Step, ...]
) -> str:
    """The answer the loop finishes with — assembled from what came back, and **only** that.

    Every planned call gets a line whatever happened to it: an observation, a refusal with its
    reason, or the fact that it was never asked. A summary that listed only the calls that
    succeeded would read as a complete enquiry, which is the shape of dishonesty constraint 16
    puts the honesty layer above the answer to catch.
    """
    label = (pack.fault_label or "").strip()
    lines = [
        f"Investigating {label or 'an unlabelled slot'} on {pack.equipment_display}, "
        f"{pack.window.render()}. {len(steps)} of {len(plan)} planned tool call(s) ran."
    ]
    by_key = {idempotency_key(s.choice.tool, s.choice.arguments): s for s in steps}
    for call in plan:
        step = by_key.get(call.key)
        lines.append(_never_asked_line(call) if step is None else _observation_line(step))

    if not plan:
        lines.append(NO_LABEL_NO_TOOLS)
    elif pack.other_labels_same_day:
        lines.append(
            f"The same machine carried {len(pack.other_labels_same_day)} other label(s) that "
            f"day: {', '.join(pack.other_labels_same_day)}. {SEVERAL_LABELS_ONE_REPAIR}"
        )
    return "\n\n".join(lines)


# ── which of the six answer states each ending becomes ──────────────────────────────────

#: `CONTEXT.md` §7 allows exactly six states, and `react.py` has six endings. They are not the
#: same six, so the mapping is held here as data with the reasoning attached to each row —
#: rather than as a chain of `if`s where the next reader would find a state and no argument.
#:
#: Nothing in this table is `FAILED`. `FAILED` is the only one of the six that means *the
#: software broke*, and a loop that stopped for a reason it can state in words did not break.
#: Nothing in it is `NO_DIAGNOSIS` either: that state carries the gate that failed, the reason
#: and what would change it, and none of these endings consulted a gate. A refusal the gates
#: did not issue is a refusal nobody made.
_STOP_TO_ANSWER_STATE: dict[StopReason, tuple[AnswerState, str]] = {
    StopReason.ANSWERED: (
        AnswerState.ANSWERED,
        "the loop answered inside its ceiling and every planned call came back — the ordinary "
        "end, and the only one with nothing outstanding",
    ),
    StopReason.STEP_CEILING: (
        AnswerState.PARTIAL,
        # **The open question this task was asked to settle, and here is the reasoning.**
        # A loop that made four successful calls and ran out of steps is NOT `FAILED`: nothing
        # broke, and `FAILED` is the one state that means a bug — calling a resource bound a
        # bug would make every long investigation look like a crash. It is NOT `NO_DIAGNOSIS`:
        # the gates never spoke, and `CLAUDE.md` §2.6 forbids letting that state mean anything
        # softer than *the data cannot decide*. It is NOT `BLOCKED`: no policy and no scope
        # forbade anything. `PARTIAL`'s own definition in `domain/answer.py` is *some of the
        # question was answered, and what was not is named rather than omitted* — which is
        # precisely what a ceiling stop produces, provided the turn states what it was still
        # trying to do. TBD (Q101): recorded as a question because this is a product decision
        # about the answer contract, not a coding one.
        "the loop spent every step it had without answering. A resource bound is not a "
        "verdict, so nothing here says the question is unanswerable — what it reached is "
        "reported and what it was still trying to reach is named",
    ),
    StopReason.REPEATED_CALL: (
        AnswerState.PARTIAL,
        "the loop asked a question it had already asked, which cannot produce a new "
        "observation. What it established before that stands; what it was still trying to "
        "establish does not, and `PARTIAL` is the state that carries both facts at once",
    ),
    StopReason.REFUSED: (
        AnswerState.BLOCKED,
        "the Control Plane refused a capability this turn needed, and asking again cannot "
        "change it. `BLOCKED` is §7's state for *policy or scope forbids it* — not "
        "`NO_DIAGNOSIS`, because nothing about the equipment was in question and no gate spoke",
    ),
    StopReason.UNUSABLE_CHOICE: (
        AnswerState.PARTIAL,
        "the loop was handed a decision it could not turn into a call, so nothing was run and "
        "nothing was assumed in its place. Not `FAILED`: no code raised — a decision that "
        "cannot be acted on is a bad decision, not a broken program",
    ),
    StopReason.CHOOSER_UNAVAILABLE: (
        AnswerState.PARTIAL,
        "the step that chooses could not decide — it timed out or it failed. `CONTEXT.md` §13 "
        "requires degraded mode to be stated rather than silently substituted, so the reason "
        "travels with the turn as `degraded_reason`",
    ),
}


def _ensure_registry() -> ToolRegistry:
    """Bind the six tools once, on the first turn that needs them.

    **This is half of the defect this task exists to fix.** `register_all()` existed, was
    tested against fresh registries, and was called from no startup path at all — so the
    process-wide `REGISTRY` was empty in every live request, and a loop reading it would have
    been offered nothing whatever `for_skill` returned. A registry nobody populates reads
    exactly like a registry nobody calls.

    Idempotent by the emptiness check rather than by `register` tolerating duplicates: the
    registry refuses a duplicate name on purpose, because silent replacement is how two
    capabilities share a name and the wrong one answers. **TBD (Q104):** this belongs in
    `main.py`'s lifespan, so a capability becomes reachable when the process decides to grant
    it rather than when the first question happens to need it. `main.py` is not owned here.
    """
    if not REGISTRY.all():
        register_all(REGISTRY)
    return REGISTRY


async def investigate_with_tools(
    pack: EvidencePack,
    *,
    scope: Scope,
    question: str = "",
    loop: ReactLoop | None = None,
    timeout_s: float | None = None,
    plant_repo: object | None = None,
) -> SkillOutcome:
    """`C4`/`C6` through the bounded loop — the request path that finally reaches `G4`.

    **A gateway per turn, deliberately.** `GATEWAY` is a process global holding `G5`'s
    idempotency ledger, and that ledger has no notion of a turn boundary: a second turn asking
    the same question would have had its first call answered `replayed`, which the loop reads
    — correctly — as *this loop is stuck*, and it would stop before it started. `G5`'s
    guarantee is *a retry within a turn does not act twice*; stretching it across turns would
    make the second visitor's question return the first visitor's answer. So the gateway is
    constructed here, per turn, and the ledger dies with the turn that owns it.

    Never raises. A loop that could not run is a turn outcome, not a crash.
    """
    registry = _ensure_registry()
    # The pack this turn already assembled, and the repository the request already holds,
    # handed to the gateway as named resources. A tool declaring either gets it; a tool
    # declaring neither is unaffected. Nothing here constructs a connection — `app.tools` may
    # not import a driver at all, which is the contract that keeps a capability from reaching
    # the plant outside `synex_plant_ro`.
    resources: dict[str, object] = {"pack": pack}
    if plant_repo is not None:
        resources["plant_repo"] = plant_repo
    react = loop or ReactLoop(
        gateway=Gateway(registry, resources=resources), registry=registry
    )
    plan = plan_for(pack)
    choose = bounded_chooser(
        PlannedChooser(pack=pack, plan=plan),
        chooser_timeout_s() if timeout_s is None else timeout_s,
    )
    outcome = await react.run(
        question=question or f"what is actually wrong with {pack.equipment_display}?",
        scope=scope,
        choose=choose,
        skill=CATALOGUE_SCOPE,
    )
    return _outcome_to_skill(pack, plan, outcome)


def _outcome_to_skill(
    pack: EvidencePack, plan: tuple[PlannedCall, ...], outcome: LoopOutcome
) -> SkillOutcome:
    """One loop ending, as one of the six answer states.

    **A stop that is not an answer never gets a summary of what was collected.** Constraint
    16 — the honesty layer overrides the model — and the same rule holds one layer down: an
    answer assembled from an evidence set the loop was still filling reads as complete, and a
    reader cannot tell it apart from one that finished. So an early stop reports what it was
    *still trying to do*, and names which tools ran without paraphrasing what they said.
    """
    state, why = _STOP_TO_ANSWER_STATE[outcome.stop]
    payload = {"react": outcome.as_dict(), "planned_calls": len(plan)}

    if outcome.stop is not StopReason.ANSWERED:
        reached = ", ".join(outcome.tools_called) or "none"
        return SkillOutcome(
            state=state,
            text=(
                f"{outcome.render()}\n\n"
                f"{outcome.step_count} of {len(plan)} planned tool call(s) ran before it "
                f"stopped ({reached}). What they returned is deliberately not summarised "
                f"here: an answer assembled from an evidence set the loop was still filling "
                f"reads as a finished one, and constraint 16 puts the honesty layer above the "
                f"answer rather than after it."
            ),
            used_model=False,
            payload=payload,
            degraded_reason=(
                outcome.stop_reason
                if outcome.stop is StopReason.CHOOSER_UNAVAILABLE
                else ""
            ),
        )

    # It answered. That is still only `ANSWERED` if every planned call came back and the gates
    # passed — a complete plan whose third call was refused produced a real answer from an
    # incomplete evidence set, and `PARTIAL` is the state that says so without discarding it.
    unanswered = tuple(s for s in outcome.steps if not s.result.ok)
    missed = len(plan) - outcome.step_count
    if unanswered or missed or not pack.may_diagnose:
        shortfall = _shortfall_text(unanswered, missed, pack)
        return SkillOutcome(
            state=AnswerState.PARTIAL,
            text=f"{outcome.answer}\n\n{shortfall}",
            used_model=False,
            payload=payload,
        )
    return SkillOutcome(
        state=AnswerState.ANSWERED,
        # `why[0].upper()` rather than `.capitalize()`, which lower-cases everything after the
        # first character and would turn `G4` into `g4` in a sentence a reader is meant to act on.
        text=f"{outcome.answer}\n\n{why[0].upper()}{why[1:]}.",
        used_model=False,
        payload=payload,
    )


def _shortfall_text(unanswered: tuple[Step, ...], missed: int, pack: EvidencePack) -> str:
    """What this enquiry did not establish, named rather than omitted.

    Three different shortfalls, kept apart: a call the tool refused, a call never made, and
    gates that did not pass. Collapsing them into *"partial"* tells a reader to fix the wrong
    thing — the same reasoning that keeps `Outcome`'s refusals distinct one layer down.
    """
    parts: list[str] = []
    if unanswered:
        named = ", ".join(f"{s.choice.tool} ({s.result.outcome.value})" for s in unanswered)
        parts.append(
            f"{len(unanswered)} call(s) did not answer — {named} — so this enquiry is "
            f"reported with what it reached rather than as a finished one."
        )
    if missed:
        parts.append(
            f"{missed} planned call(s) were never made, so what they would have established "
            f"is unknown and is not being guessed at."
        )
    if not pack.may_diagnose:
        failed = ", ".join(g.gate.value for g in pack.gates.results if not g.passed) or "none"
        parts.append(
            f"The gates did not all pass ({failed}), so nothing here names a fault. What the "
            f"tools returned is what is settled about the class, not a diagnosis of this "
            f"machine on this day."
        )
    return " ".join(parts)


NO_IDENTITY_NO_TOOLS = (
    "No tool was called on this turn, because no identity reached it — and permission is "
    "plain software, so with nobody to check the Control Plane could not be asked. The "
    "enquiry below is the rules-only one, which needs no capability at all. This is a stated "
    "shortfall rather than a quieter answer."
)


async def dispatch_with_tools(
    skill: str,
    pack: EvidencePack,
    *,
    scope: Scope | None,
    question: str = "",
    plant_repo: object | None = None,
) -> SkillOutcome | None:
    """The dispatch, with the one tool-using skill reaching for tools.

    Everything else takes the same deterministic path it always did — this is a widening of
    `investigate`, not a rewrite of the table. Never raises: a loop that broke is a turn
    outcome, exactly as `dispatch` treats a skill that broke.
    """
    if skill != TOOL_USING_SKILL:
        return dispatch(skill, pack)

    if scope is None:
        # Stated, not silent. A turn that quietly fell back to the rules-only enquiry would
        # look identical to one where the loop ran and found nothing.
        rules_only = investigate(pack)
        return SkillOutcome(
            state=rules_only.state,
            text=f"{rules_only.text}\n\n{NO_IDENTITY_NO_TOOLS}",
            used_model=False,
            payload=rules_only.payload,
            degraded_reason=NO_IDENTITY_NO_TOOLS,
        )

    try:
        return await investigate_with_tools(
            pack, scope=scope, question=question, plant_repo=plant_repo
        )
    except Exception as exc:
        return SkillOutcome(
            state=AnswerState.FAILED,
            text=(
                f"The {skill} skill could not complete: {type(exc).__name__}: {exc}. "
                f"Nothing was assumed in its place."
            ),
            used_model=False,
        )


# ════════════════════════════════════════════════════════════════════════════════
# The catalogue path — the questions that have no episode
# ════════════════════════════════════════════════════════════════════════════════


def _equipment_named_in(text: str) -> str | None:
    """Which machine this question names, if any.

    Word-boundary matched, never containment: `"chiller 1" in "chiller 12"` is `True`, and
    that once answered a question about a machine which does not exist — confidently, and
    about chiller 1. The same defect shape as `-25.6` sitting inside `-25.645`.
    """
    for e in _eq.all_equipment():
        for name in (e.key.replace("_", " "), e.display_name.lower()):
            if re.search(rf"\b{re.escape(name)}\b", text):
                return e.key
    m = re.search(r"\b(?:chiller|ch)[\s_-]*([12])\b", text)
    return f"chiller_{m.group(1)}" if m else None


async def answer_catalogue(
    question: str,
    *,
    scope: Scope | None,
    plant_repo: object | None = None,
    client: object | None = None,
) -> SkillOutcome | None:
    """Answer a question about the plant's *catalogue* — no episode, no evidence pack.

    **The gap this closes.** Every skill below takes an `EvidencePack`, and a pack needs an
    equipment key, a fault label and a day. So a question about the plant as a whole — *"how
    many episodes are there?"*, *"what equipment do we have?"*, *"which fault classes can the
    model report?"* — had nothing to run against, and `answer_turn` returned *"there is no
    scored evidence for that request"* whatever had been asked. Three of those questions have
    had a registered tool sitting ready to answer them since `C20` shipped; the router reached
    the right skill and the path underneath it needed an episode that does not exist.

    That is why the Copilot felt like it required a selection before it would talk. It did.

    **Read-only and deterministic.** These call the same `G4` gateway every tool call goes
    through — the four gates, the scope check and the ledger — so a catalogue answer is
    authorized exactly like any other, and no model is spent on any of it.

    Returns `None` when the question is not a catalogue one, so the caller falls through to
    the pack-based path unchanged rather than this becoming a second answer route.
    """
    if scope is None:
        return None

    text = question.lower()
    plan: tuple[str, dict] | None = None

    # **A named machine wins over every plant-wide reading.** "What faults did chiller 2 have?"
    # matched the fault-class branch below and returned all nine classes the model can emit —
    # a confident answer to a different question, with the machine silently dropped. A question
    # that names a machine is a question about that machine.
    named = _equipment_named_in(text)

    # Ordered: the more specific reading wins. "how many fault classes" is a fault-class
    # question before it is a counting question.
    # **A plant-wide phrase outranks machine resolution, and it has to.** `Plant` is itself an
    # equipment key on this site, so "what happened across the plant" resolved to a *machine*
    # called Plant and came back "Plant carries no detected fault" — technically true of that
    # row and the opposite of what was asked. The phrase describes a scope, not a name.
    # A comparison names two machines or asks for one outright, and it is checked before the
    # plant-wide branch because "compare the plant's chillers" contains "the plant".
    if any(t in text for t in ("compare", "versus", " vs ", "against each other",
                               "both chillers", "difference between", "side by side")):
        plan = ("compare_equipment", {})
    elif any(
        t in text for t in ("across the plant", "whole plant", "the plant", "worst",
                            "overview", "everything", "all equipment", "all machines",
                            "plant wide", "plant-wide", "situation")
    ):
        plan = ("plant_overview", {})
    elif named and any(
        t in text for t in ("fault", "flagged", "happened", "episode", "wrong", "issue",
                            "problem", "history", "seen", "detected")
    ):
        plan = ("episodes_for_equipment", {"equipment_key": named})
    elif named and any(t in text for t in ("how is", "doing", "standing", "trust", "signal")):
        plan = ("equipment_standing", {"equipment_key": named})
    elif any(t in text for t in ("reconcil", "do the numbers", "figures match", "lineage",
                                 "match the plant", "documented value")):
        plan = ("reconciliation_report", {})
    elif any(t in text for t in ("fault class", "fault label", "what faults", "which faults")):
        plan = ("list_fault_classes", {})
    elif any(t in text for t in ("equipment", "machine", "asset", "chillers", "units")):
        plan = ("list_equipment", {})

    if plan is None:
        return None

    _ensure_registry()
    # The repository is *handed in*, never constructed here. `app.tools` may not import a
    # driver — the contract exists so a tool can never reach the plant outside
    # `synex_plant_ro` — so the API layer builds it and it travels down as a named resource.
    # A tool declaring `needs=("plant_repo",)` against a gateway without one reports
    # `MISSING_RESOURCE` in words rather than failing obscurely.
    resources = {"plant_repo": plant_repo} if plant_repo is not None else None
    gateway = Gateway(REGISTRY, resources=resources)
    result = await gateway.invoke(plan[0], plan[1], scope)

    if result.outcome is not Outcome.OK or not isinstance(result.value, dict):
        # A refusal or a wiring gap is reported in the gateway's own words. Inventing a
        # friendlier sentence here would hide which of the five outcomes actually happened.
        return SkillOutcome(
            state=AnswerState.BLOCKED,
            text=result.reason or f"{plan[0]} did not answer, and gave no reason.",
        )

    # **The tool supplies the facts and the brain supplies the wording.** The deterministic
    # rendering below is the floor, not a fallback nobody exercises: it ships whenever the box
    # is unreachable or the reply is unusable. Composed or not, the answer goes through the
    # same seven audits and the same critique gate — a sentence that invents a figure is
    # replaced exactly as one from the diagnostic path would be.
    rendered = _render_catalogue(plan[0], result.value)
    text, used_model = await compose.compose_from_tool(
        question=question,
        tool=plan[0],
        value=result.value,
        fallback=rendered,
        client=client,
    )
    return SkillOutcome(state=AnswerState.ANSWERED, text=text, used_model=used_model)


def _render_catalogue(tool: str, value: dict) -> str:  # noqa: PLR0911
    """Turn a tool's dict into the sentence a reader gets.

    No model, and no number invented — every figure here is a count of rows the tool itself
    returned. One branch per tool, and `PLR0911` is suppressed because each branch is a
    different *reader*: the sentence a plant overview needs and the sentence a reconciliation
    needs share no structure, and funnelling them through a common shape is how a rendering
    starts saying "3 items" where it used to name them.
    """
    if tool == "compare_equipment":
        lines = []
        for key, m in (value.get("machines") or {}).items():
            lines.append(
                f"- {m['display_name']}: {m['fault_classes']} fault class(es) over "
                f"{m['days_with_a_fault']} day(s), {m['bands_fitted']} model(s) fitted"
            )
        return chr(10).join(
            [str(value.get("comparable_note", "")), ""]
            + lines
            + ["", str(value.get("not_compared_note", ""))]
        )

    if tool == "equipment_standing":
        if not value.get("known"):
            return str(value.get("note") or "That machine is not on this site.")
        lines = [f"{value['display_name']}: {value['scoreable_note']}"]
        never = value.get("never_measured") or []
        unusable = value.get("unusable") or []
        if never or unusable:
            lines.append("")
            lines.append(str(value.get("trust_note", "")))
            for name in unusable:
                lines.append(f"  - {name}")
        lines.append("")
        lines.append(str(value.get("to_go_further", "")))
        return chr(10).join(lines)

    if tool == "plant_overview":
        machines = value.get("machines", [])
        faulted = [m for m in machines if m["fault_classes"]]
        lines = [
            f"{value['with_a_detected_fault']} of {value['equipment']} machine(s) carry a "
            f"detected fault in the measured window."
        ]
        for m in faulted:
            lines.append(
                f"- {m['display_name']} — {m['fault_classes']} fault class(es) over "
                f"{m['days_affected']} day(s): {', '.join(m['labels'])}"
            )
        lines.append("")
        lines.append(str(value.get("ranking_note", "")))
        lines.append("")
        lines.append(str(value.get("unjudged_note", "")))
        return chr(10).join(lines)

    if tool == "episodes_for_equipment":
        if not value.get("known"):
            return str(value.get("note") or "That machine is not on this site.")
        rows = value.get("labels", [])
        if not rows:
            return (
                f"{value['display_name']} carries no detected fault in the measured window. "
                f"That is not a statement that it is healthy — only that nothing was labelled."
            )
        lines = [
            f"{value['display_name']} carries {len(rows)} fault class(es) across "
            f"{value['days_with_a_fault']} day(s), {value['first_day']} to {value['last_day']}:"
        ]
        for r in rows:
            span = r["first"] if r["first"] == r["last"] else f"{r['first']} to {r['last']}"
            lines.append(f"- {r['label']} — {r['days']} day(s), {span}")
        lines.append("")
        lines.append(str(value.get("note", "")))
        return chr(10).join(lines)

    if tool == "reconciliation_report":
        lines = [
            f"{value['agreed']} of {value['checkable']} recomputed figure(s) agree with the "
            f"documented value."
        ]
        if value.get("not_checkable"):
            lines.append(
                f"{value['not_checkable']} could not be recomputed at all, and are reported as "
                f"not checkable rather than as agreeing — those are different facts."
            )
        if value.get("disagreements"):
            lines.append("")
            lines.append(f"{value['disagreed']} disagree:")
            for d in value["disagreements"]:
                name = d.get("key") or d.get("figure") or d.get("name") or "a figure"
                lines.append(f"- {name}: {d.get('note') or d.get('reason') or 'values differ'}")
        else:
            lines.append("Nothing disagrees.")
        return chr(10).join(lines)

    if tool == "list_equipment":
        rows = value.get("equipment", [])
        names = ", ".join(str(r.get("display_name") or r.get("key")) for r in rows)
        return (
            f"This site has {len(rows)} piece(s) of equipment: {names}.\n"
            "Only chiller 1 and chiller 2 carry a fitted residual model and a reference band, "
            "so they are the two whose readings can be judged. The rest carry telemetry that "
            "nothing has been fitted against — which is not a statement that they are healthy."
        )

    # **The fall-through is explicit now.** This function used to end on the fault-class
    # renderer unconditionally, so a tool with no branch — `equipment_standing`, added later —
    # was rendered as a fault-class list, found no `labels` key, and answered "the trained
    # model can report 0 fault class(es)". A confident, well-formed, entirely wrong answer to
    # a question about a machine. A default that renders *something* is worse than one that
    # says it does not know how.
    if tool != "list_fault_classes":
        return (
            f"{tool} answered and this surface has no way to phrase its result yet. Nothing "
            f"was invented in place of it; the raw keys were: {', '.join(sorted(value))}."
        )

    rows = value.get("labels", [])
    lines = [
        f"- {r.get('label')}"
        + (f" — {r.get('slots')} measured slot(s)" if r.get("slots") is not None else "")
        + (" · declares itself undecidable" if r.get("undecidable") else "")
        for r in rows
    ]
    return (
        f"The trained model can report {len(rows)} fault class(es) on this plant:\n"
        + "\n".join(lines)
    )
