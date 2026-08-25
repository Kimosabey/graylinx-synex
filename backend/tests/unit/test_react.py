"""The bounded tool loop — the end of a registry with no caller.

`SESSION-HANDOFF.md` §8 has said since M0 that `max_react_steps` is *"configured, nothing
consumed it"*, and since 2026-08-17 that six tools exist and no ReAct loop calls them. A gate
guarding zero calls is not a gate, so these tests do two jobs: they prove the loop terminates on
each of its four endings, and they prove it cannot reach a handler around the gateway.

Every test here runs with MySQL stopped and the GPU terminated. The tool-choosing step is an
injected callable, so the loop is driven deterministically — the same split that lets
`ModelClient` replay a transcript rather than needing a card in CI.
"""
from __future__ import annotations

import asyncio

import pytest

from app.agents.react import (
    _ROUTING,
    Move,
    ReactLoop,
    StopReason,
    ToolChoice,
)
from app.config import get_settings
from app.services.control_plane import Persona, compute_scope
from app.tools.gateway import Gateway, Outcome
from app.tools.plant_tools import NoArgs, register_all
from app.tools.registry import ControlLevel, SideEffect, ToolRegistry, ToolSpec


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    register_all(r)
    return r


@pytest.fixture
def gateway(registry: ToolRegistry) -> Gateway:
    return Gateway(registry)


@pytest.fixture
def loop(gateway: Gateway, registry: ToolRegistry) -> ReactLoop:
    return ReactLoop(gateway=gateway, registry=registry, max_steps=3)


@pytest.fixture
def engineer():
    return compute_scope(Persona.RELIABILITY_ENGINEER)


def _script(*choices: ToolChoice):
    """A chooser that plays a fixed sequence, then repeats its last decision.

    Repeating rather than raising at the end is deliberate: it is what a stuck model does, and
    several tests below exist precisely to prove the loop notices.
    """

    async def choose(state):
        index = min(len(state.steps), len(choices) - 1)
        return choices[index]

    return choose


def _always(choice: ToolChoice):
    async def choose(state):
        return choice

    return choose


LIST_FAULTS = ToolChoice.call(
    "list_fault_classes", {}, "find out which classes this plant's model can emit"
)


# ── the table is exhaustive, or an outcome falls through silently ──────────────

def test_every_gateway_outcome_has_a_routing_decision() -> None:
    """A new `Outcome` with no entry would raise inside the loop — or worse, if the lookup were
    forgiving, it would silently mean *keep going*. That is how a refusal gets retried."""
    assert set(_ROUTING) == set(Outcome)


def test_exactly_one_outcome_ends_the_loop_and_it_is_the_authority_refusal() -> None:
    """Asserting the count stops a later edit widening what stops a turn. An unknown tool and a
    bad argument are recoverable — the model chooses again; a refusal is not."""
    stopping = {o for o, (routing, _) in _ROUTING.items() if routing.value == "stop"}
    assert stopping == {Outcome.REFUSED}


def test_every_routing_decision_carries_its_reason_in_words() -> None:
    """A loop that stops or continues for a reason nobody can read is one nobody can audit."""
    for outcome, (_, why) in _ROUTING.items():
        assert len(why.split()) > 5, f"{outcome} has no reason a reader can act on"


# ── ending 1: an answer ────────────────────────────────────────────────────────

async def test_the_loop_stops_as_soon_as_the_model_produces_an_answer(loop, engineer) -> None:
    """The ordinary ending. It must not spend its remaining steps once it has one."""
    outcome = await loop.run(
        question="which fault classes exist?",
        scope=engineer,
        choose=_script(LIST_FAULTS, ToolChoice.finish("Eleven classes, four undecidable.")),
    )
    assert outcome.stop is StopReason.ANSWERED
    assert outcome.has_answer
    assert outcome.step_count == 1, "it must not keep calling tools after it has answered"
    assert outcome.unfinished_intent.startswith("Nothing was outstanding")


async def test_an_answer_can_be_reached_with_no_tool_call_at_all(loop, engineer) -> None:
    """Not every question needs a tool, and a loop that forced one would spend a call to look
    busy. Four of the seven skills need no model; some questions need no tool."""
    outcome = await loop.run(
        question="hello",
        scope=engineer,
        choose=_always(ToolChoice.finish("I read this plant's chiller telemetry.")),
    )
    assert outcome.stop is StopReason.ANSWERED
    assert outcome.step_count == 0
    assert outcome.tools_called == ()


# ── ending 2: the ceiling, and what it was still trying to do ──────────────────

def test_the_loop_consumes_the_configured_ceiling_rather_than_its_own_number() -> None:
    """`max_react_steps` has sat in `config.py` since M0 with nothing consuming it. The whole
    point of this module is that the bound and the loop are the same fact."""
    assert ReactLoop().ceiling == get_settings().max_react_steps


async def test_hitting_the_ceiling_reports_what_it_was_still_trying_to_do(
    loop, engineer
) -> None:
    """A loop that stops silently at the ceiling looks identical to one that finished. The
    difference has to be in the output, not in a log nobody reads."""
    outcome = await loop.run(
        question="what is wrong with chiller 1?",
        scope=engineer,
        choose=_script(
            ToolChoice.call("list_fault_classes", {}, "see which classes exist"),
            ToolChoice.call("list_equipment", {}, "see which assets are on this site"),
            ToolChoice.call(
                "explain_fault_class",
                {"fault_label": "HIGH_HEAD_AMBIGUOUS"},
                "establish whether this class can be narrowed at all",
            ),
        ),
    )
    assert outcome.stop is StopReason.STEP_CEILING
    assert outcome.step_count == 3
    assert "establish whether this class can be narrowed" in outcome.unfinished_intent
    assert "explain_fault_class" in outcome.unfinished_intent


async def test_a_ceiling_stop_is_an_absence_rather_than_an_empty_answer(loop, engineer) -> None:
    """Constraint 14 one layer along: an answer is a value or a stated absence, never neither.
    An empty string would render as a reply nobody wrote."""
    outcome = await loop.run(
        question="what is wrong?",
        scope=engineer,
        choose=_script(
            ToolChoice.call("list_fault_classes", {}, "see the classes"),
            ToolChoice.call("list_equipment", {}, "see the assets"),
            ToolChoice.call("checklist_for_fault", {"fault_label": "CONDENSER_LOW_FLOW"}, "look"),
        ),
    )
    assert outcome.answer is None
    assert outcome.has_answer is False
    assert outcome.render().startswith("No answer was produced.")
    assert "ceiling of 3" in outcome.stop_reason


async def test_the_ceiling_stop_does_not_claim_the_question_is_unanswerable(
    loop, engineer
) -> None:
    """A refusal and a resource bound are different facts. `NO_DIAGNOSIS` means the data cannot
    decide; running out of steps means we stopped asking."""
    outcome = await loop.run(
        question="what is wrong?",
        scope=engineer,
        choose=_script(
            ToolChoice.call("list_fault_classes", {}, "see the classes"),
            ToolChoice.call("list_equipment", {}, "see the assets"),
            ToolChoice.call("explain_fault_class", {"fault_label": "HIGH_HEAD_AMBIGUOUS"}, "read"),
        ),
    )
    assert outcome.stop is StopReason.STEP_CEILING
    assert "nothing here says the question is unanswerable" in outcome.stop_reason


async def test_a_ceiling_of_zero_stops_before_any_tool_runs(gateway, registry, engineer) -> None:
    """A bound of zero is not a safe loop; it is a loop that cannot start, and it must say so
    rather than returning an empty trace that reads like a question nobody asked."""
    loop = ReactLoop(gateway=gateway, registry=registry, max_steps=0)
    outcome = await loop.run(question="anything", scope=engineer, choose=_always(LIST_FAULTS))
    assert outcome.stop is StopReason.STEP_CEILING
    assert outcome.step_count == 0
    assert "cannot start" in outcome.stop_reason


# ── ending 3: a repeated identical call ────────────────────────────────────────

async def test_an_identical_call_twice_stops_the_loop_rather_than_replaying_it(
    loop, engineer
) -> None:
    """`G5` calls this replayed, and a loop replaying a call is going round rather than
    forward. Without this it burns the whole ceiling on one question."""
    outcome = await loop.run(
        question="which classes exist?",
        scope=engineer,
        choose=_always(LIST_FAULTS),
    )
    assert outcome.stop is StopReason.REPEATED_CALL
    assert outcome.step_count == 1, "the second identical call must not be issued at all"
    assert "cannot produce a new observation" in outcome.stop_reason
    assert "find out which classes" in outcome.unfinished_intent


async def test_the_same_call_with_reordered_arguments_still_counts_as_repeated(
    loop, engineer
) -> None:
    """The repeat guard reuses `G5`'s key, so `{a,b}` and `{b,a}` are the same call. A guard
    over raw text would let a stuck loop through on dictionary ordering alone."""
    first = ToolChoice.call(
        "set_chiller_setpoint", {"equipment_key": "chiller_1", "setpoint_c": 6.5}, "try"
    )
    second = ToolChoice.call(
        "set_chiller_setpoint", {"setpoint_c": 6.5, "equipment_key": "chiller_1"}, "try again"
    )
    outcome = await ReactLoop(
        gateway=Gateway(ToolRegistry()), registry=ToolRegistry(), max_steps=4
    ).run(question="q", scope=engineer, choose=_script(first, second))
    # The empty registry refuses both as unknown tools, which is recoverable — so what stops
    # this loop is the repeat guard and nothing else.
    assert outcome.stop is StopReason.REPEATED_CALL


async def test_a_call_already_made_this_turn_comes_back_replayed_and_stops(
    gateway, registry, engineer
) -> None:
    """`G5`'s ledger outlives the loop within a turn. A result from the ledger is the signal
    that this exact question has already been asked, whoever asked it."""
    await gateway.invoke("list_fault_classes", {}, engineer)
    loop = ReactLoop(gateway=gateway, registry=registry, max_steps=3)
    outcome = await loop.run(question="q", scope=engineer, choose=_script(LIST_FAULTS))

    assert outcome.stop is StopReason.REPEATED_CALL
    assert outcome.steps[-1].result.replayed is True
    assert "idempotency ledger" in outcome.stop_reason


# ── ending 4: a refusal it cannot route around ─────────────────────────────────

async def test_an_authority_refusal_ends_the_loop_rather_than_being_retried(engineer) -> None:
    """Retrying a refusal until it succeeds is how a refused capability executes. Permission is
    plain software — the separation law's seventh row — and it does not soften on a re-ask."""
    r = ToolRegistry()

    async def _handler() -> str:
        return "written"

    r.register(
        ToolSpec(
            name="close_a_case",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.WRITES_SYNEX_STATE,
            control_level=ControlLevel.NEEDS_APPROVAL,
            handler=_handler,
        )
    )
    loop = ReactLoop(gateway=Gateway(r), registry=r, max_steps=5)
    outcome = await loop.run(
        question="close it",
        scope=compute_scope(Persona.TECHNICIAN),
        choose=_always(ToolChoice.call("close_a_case", {}, "close the case out")),
    )
    assert outcome.stop is StopReason.REFUSED
    assert outcome.step_count == 1
    assert "approve_work" in outcome.stop_reason
    assert "close the case out" in outcome.unfinished_intent


async def test_a_permanently_refused_tool_never_reaches_its_handler(loop, engineer) -> None:
    """`_set_chiller_setpoint` raises if it is ever executed. `CONTEXT.md` §13: no tool issues a
    control command to plant equipment, in any phase — and a loop that could reach a handler
    around the gateway would be a loop that could do it by forgetting one line."""
    outcome = await loop.run(
        question="set the setpoint to 6.5",
        scope=engineer,
        choose=_always(
            ToolChoice.call(
                "set_chiller_setpoint",
                {"equipment_key": "chiller_1", "setpoint_c": 6.5},
                "lower the setpoint",
            )
        ),
    )
    assert outcome.stop is StopReason.REFUSED
    assert "in every phase and for every persona" in outcome.stop_reason


async def test_the_loop_decides_nothing_about_permission(engineer) -> None:
    """The identical choice, the identical loop, two personas, two answers — and the difference
    comes entirely from the Control Plane. The model chooses *which* tool; never *whether*."""
    r = ToolRegistry()

    async def _handler() -> str:
        return "written"

    r.register(
        ToolSpec(
            name="close_a_case",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.WRITES_SYNEX_STATE,
            control_level=ControlLevel.NEEDS_APPROVAL,
            handler=_handler,
        )
    )
    choice = ToolChoice.call("close_a_case", {}, "close the case out")
    finish = ToolChoice.finish("Closed.")

    refused = await ReactLoop(gateway=Gateway(r), registry=r, max_steps=4).run(
        question="close it", scope=compute_scope(Persona.TECHNICIAN),
        choose=_script(choice, finish),
    )
    allowed = await ReactLoop(gateway=Gateway(r), registry=r, max_steps=4).run(
        question="close it", scope=compute_scope(Persona.SUPERVISOR),
        choose=_script(choice, finish),
    )
    assert refused.stop is StopReason.REFUSED
    assert allowed.stop is StopReason.ANSWERED


# ── the refusals it CAN route around ───────────────────────────────────────────

async def test_an_invented_tool_name_does_not_end_the_loop(loop, engineer) -> None:
    """Hallucinated capability is the commonest agent failure and it must be boring. The
    refusal lists what does exist, so the next choice is informed rather than another guess."""
    outcome = await loop.run(
        question="who should I call?",
        scope=engineer,
        choose=_script(
            ToolChoice.call("summon_a_technician", {}, "find somebody to send"),
            ToolChoice.finish("There is no dispatch tool; raise a work order instead."),
        ),
    )
    assert outcome.stop is StopReason.ANSWERED
    assert outcome.steps[0].result.outcome is Outcome.UNKNOWN_TOOL
    assert "list_fault_classes" in outcome.steps[0].result.reason


async def test_bad_arguments_do_not_end_the_loop(loop, engineer) -> None:
    """The refusal names the field, which is what makes a corrected second call possible."""
    outcome = await loop.run(
        question="explain that class",
        scope=engineer,
        choose=_script(
            ToolChoice.call("explain_fault_class", {"wrong": "x"}, "read the class"),
            ToolChoice.call(
                "explain_fault_class",
                {"fault_label": "CONDENSER_LOW_FLOW"},
                "read the class, correctly this time",
            ),
            ToolChoice.finish("Condenser low flow is determinate."),
        ),
    )
    assert outcome.stop is StopReason.ANSWERED
    assert outcome.steps[0].result.outcome is Outcome.INVALID_ARGUMENTS
    assert outcome.steps[1].result.ok


async def test_a_broken_tool_is_not_a_refusal_and_does_not_end_the_loop(engineer) -> None:
    """A break and a refusal are different facts: the system did not say no, something went
    wrong. Another tool may still answer, and the ceiling bounds how long it tries."""
    r = ToolRegistry()

    async def _boom() -> None:
        raise RuntimeError("the database went away")

    r.register(
        ToolSpec(
            name="boom",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_boom,
        )
    )
    loop = ReactLoop(gateway=Gateway(r), registry=r, max_steps=3)
    outcome = await loop.run(
        question="q",
        scope=engineer,
        choose=_script(
            ToolChoice.call("boom", {}, "read the residuals"),
            ToolChoice.finish("The store is unreachable, so nothing was read."),
        ),
    )
    assert outcome.steps[0].result.outcome is Outcome.FAILED
    assert outcome.steps[0].result.is_refusal is False
    assert outcome.stop is StopReason.ANSWERED


# ── one slow tool must not hold the loop ───────────────────────────────────────

async def test_a_slow_tool_is_abandoned_with_the_bound_named(engineer) -> None:
    """Ceiling 5 of the ten: *one slow tool holding the loop*. Abandoned as a failure rather
    than a refusal, because whether it would eventually have answered is unknown."""
    r = ToolRegistry()

    async def _slow() -> str:
        await asyncio.sleep(5)
        return "eventually"

    r.register(
        ToolSpec(
            name="slow",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_slow,
        )
    )
    loop = ReactLoop(gateway=Gateway(r), registry=r, max_steps=2, tool_timeout_s=0.01)
    outcome = await loop.run(
        question="q",
        scope=engineer,
        choose=_script(
            ToolChoice.call("slow", {}, "read the trend"),
            ToolChoice.finish("The trend tool did not answer in time."),
        ),
    )
    assert outcome.steps[0].result.outcome is Outcome.FAILED
    assert "did not answer within 0.01s" in outcome.steps[0].result.reason
    assert "one slow tool cannot hold the loop" in outcome.steps[0].result.reason


# ── the chooser itself failing is a state, not a crash ─────────────────────────

async def test_a_chooser_that_cannot_decide_becomes_a_state_not_a_crash(loop, engineer) -> None:
    """In service the chooser is a model, and `ModelUnavailable` is one of several ways it
    fails. A stack trace is not an answer, and on a demonstration it reads as a broken
    product."""

    async def _unavailable(state):
        raise RuntimeError("no transcript for this prompt")

    outcome = await loop.run(question="q", scope=engineer, choose=_unavailable)
    assert outcome.stop is StopReason.CHOOSER_UNAVAILABLE
    assert "no transcript for this prompt" in outcome.stop_reason
    assert "is not being guessed at" in outcome.unfinished_intent


async def test_a_chooser_failing_midway_keeps_what_was_already_established(
    loop, engineer
) -> None:
    """Degraded mode is stated, not substituted — `CONTEXT.md` §13. The two steps that did run
    are evidence, and discarding them would throw away work that was already paid for."""
    calls = {"n": 0}

    async def _fails_on_the_second(state):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("the box went away")
        return LIST_FAULTS

    outcome = await loop.run(question="q", scope=engineer, choose=_fails_on_the_second)
    assert outcome.stop is StopReason.CHOOSER_UNAVAILABLE
    assert outcome.step_count == 1
    assert outcome.tools_called == ("list_fault_classes",)


# ── a decision that cannot become a call ───────────────────────────────────────

async def test_finishing_with_no_answer_is_reported_as_an_absence(loop, engineer) -> None:
    """An empty answer reads as a reply nobody wrote. An absence is not a zero and not a dash,
    and it is not an empty string either."""
    outcome = await loop.run(
        question="q", scope=engineer, choose=_always(ToolChoice(move=Move.FINISH, answer="   "))
    )
    assert outcome.stop is StopReason.UNUSABLE_CHOICE
    assert outcome.answer is None
    assert "reads as a reply nobody wrote" in outcome.stop_reason


async def test_a_call_with_no_tool_name_runs_nothing(loop, engineer) -> None:
    """The gateway can refuse a tool that does not exist; it cannot refuse a request that names
    none. Nothing is run and nothing is assumed in its place."""
    outcome = await loop.run(
        question="q",
        scope=engineer,
        choose=_always(ToolChoice(move=Move.CALL_TOOL, tool="  ", purpose="do something")),
    )
    assert outcome.stop is StopReason.UNUSABLE_CHOICE
    assert outcome.step_count == 0
    assert "given no tool name" in outcome.stop_reason


async def test_a_call_with_no_stated_purpose_still_reports_one(loop, engineer) -> None:
    """The ceiling report reads the purpose back. If a chooser omits it, the report must say so
    rather than printing a blank where the intent should be."""
    outcome = await loop.run(
        question="q",
        scope=engineer,
        choose=_always(ToolChoice(move=Move.CALL_TOOL, tool="list_fault_classes")),
    )
    assert "no purpose was stated" in outcome.unfinished_intent


# ── the trace, and what the chooser is shown ───────────────────────────────────

async def test_the_chooser_sees_what_the_previous_steps_returned(loop, engineer) -> None:
    """This is what makes it a loop rather than three independent calls: the second decision is
    allowed to depend on the first observation."""
    seen: list[str] = []

    async def _watching(state):
        seen.append(state.render())
        if state.is_first_step:
            return LIST_FAULTS
        return ToolChoice.finish("done")

    await loop.run(question="q", scope=engineer, choose=_watching)
    assert seen[0] == "nothing has been tried yet in this loop"
    assert "step 1: called list_fault_classes" in seen[1]
    assert "HIGH_HEAD_AMBIGUOUS" in seen[1], "the observation itself must reach the chooser"


async def test_the_transcript_shown_to_the_chooser_is_truncated_and_marked(
    gateway, registry, engineer
) -> None:
    """Ceiling 2: *unbounded growth, and silent partial context*. Truncating is fine;
    truncating silently means the next step is chosen from a fragment and reads complete."""
    loop = ReactLoop(gateway=gateway, registry=registry, max_steps=3, context_cap=80)
    seen: list[str] = []

    async def _watching(state):
        seen.append(state.render())
        if state.is_first_step:
            return LIST_FAULTS
        return ToolChoice.finish("done")

    await loop.run(question="q", scope=engineer, choose=_watching)
    assert "context truncated" in seen[1]
    assert len(seen[1]) < 200


async def test_a_refusal_reaches_the_chooser_as_words_rather_than_as_nothing(
    loop, engineer
) -> None:
    """A chooser shown an empty observation cannot tell a refusal from a tool that returned
    nothing, and it will try the same thing again."""
    seen: list[str] = []

    async def _watching(state):
        seen.append(state.render())
        if state.is_first_step:
            return ToolChoice.call("summon_a_technician", {}, "find somebody")
        return ToolChoice.finish("done")

    await loop.run(question="q", scope=engineer, choose=_watching)
    assert "unknown_tool — there is no tool called" in seen[1]


async def test_the_whole_run_serialises_for_a_surface(loop, engineer) -> None:
    """`G6` keeps the trail permanently, and the Inspector shows the route. A trace that cannot
    be serialised is one no surface can display and no audit row can carry."""
    outcome = await loop.run(
        question="which classes exist?",
        scope=engineer,
        choose=_script(LIST_FAULTS, ToolChoice.finish("Eleven, four undecidable.")),
    )
    payload = outcome.as_dict()
    assert payload["stop"] == "answered"
    assert payload["steps_used"] == 1
    assert payload["ceiling"] == 3
    assert payload["steps"][0]["tool"] == "list_fault_classes"
    assert payload["steps"][0]["result"]["idempotency_key"]
    assert payload["unfinished_intent"]


async def test_the_scope_of_a_skill_narrows_the_tools_offered(loop, engineer) -> None:
    """A skill is a named entry with a tool scope. Offering the resolve tools to a look-up would
    make the scope decorative — and the registry is the one place that scope is declared."""
    offered: list[tuple[str, ...]] = []

    async def _watching(state):
        offered.append(tuple(t["name"] for t in state.available_tools))
        return ToolChoice.finish("done")

    await loop.run(question="q", scope=engineer, choose=_watching, skill="look_up")
    assert "list_fault_classes" in offered[0]
    assert "checklist_for_fault" not in offered[0], "that tool belongs to resolve"


async def test_the_catalogue_says_which_capability_is_permanently_refused(loop, engineer) -> None:
    """**Changed 2026-08-17 after adversarial review, and the change is the point.**

    This used to assert the chooser was *shown* `set_chiller_setpoint` so that choosing it
    would be an informed refusal. That was wrong: `for_skill` read an empty skill as
    *available to every skill*, so the permanently-refused equipment-control tool sat in
    **every** catalogue, with `G4` the only thing standing behind it. A gate should be the
    second line of defence, not the first — offering a model a tool it may never use is an
    invitation to try.

    So the catalogue never offers it, and the registry still **declares** it. Both halves
    matter: an absent capability proves nothing, because a reader cannot tell *we decided
    against this* from *nobody thought of it*.
    """
    from app.tools.plant_tools import register_all
    from app.tools.registry import ToolRegistry

    offered: list[dict] = []

    async def _watching(state):
        offered.extend(state.available_tools)
        return ToolChoice.finish("done")

    await loop.run(question="q", scope=engineer, choose=_watching)
    assert offered, "the chooser must be given a usable catalogue"
    assert not [t for t in offered if t["permanently_refused"]], (
        "a catalogue must never offer a tool that cannot run"
    )

    declared = ToolRegistry()
    register_all(declared)
    assert "set_chiller_setpoint" in [t.name for t in declared.all()]


async def test_the_chooser_is_never_handed_the_handler(loop, engineer) -> None:
    """A caller that can see the function can call it around the gateway — the same reason
    `ToolSpec.describe()` omits it."""
    offered: list[dict] = []

    async def _watching(state):
        offered.extend(state.available_tools)
        return ToolChoice.finish("done")

    await loop.run(question="q", scope=engineer, choose=_watching)
    assert offered
    assert all("handler" not in tool for tool in offered)
