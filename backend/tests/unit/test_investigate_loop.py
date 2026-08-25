"""`investigate` through the bounded loop — the tests that make `react.py` reachable.

**What these exist to stop happening again.** `react.py` shipped with 32 green tests and no
caller: the only thing that imported it was its own test file. That is the sixth module in one
day built, tested and consumed by nothing — `RC18`'s stored readings, the `C20` registry,
`context.py`, `app/eval/` and `retrieval/quality.py` were the others. A test that imports a
module proves the module parses. These tests instead follow a **request**: `answer_turn` with
a scope, routed to `investigate`, down to `Gateway.invoke` and back.

Every test here runs with MySQL stopped and the GPU terminated. The chooser is deterministic
by design, which is the same split that lets `ModelClient` replay a committed transcript
rather than needing a card in CI — a model-backed chooser is a separate wiring step.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest
from pydantic import BaseModel, Field

from app.agents import skills
from app.agents.answer import answer_turn
from app.agents.react import ReactLoop, StopReason, ToolChoice
from app.agents.router import Skill, route
from app.analytics.bands import ResidualBand
from app.analytics.gates import Gate, GateOutcome, GateResult, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.domain.answer import AnswerState
from app.services.control_plane import Persona, compute_scope
from app.services.evidence import build_pack, window_for
from app.tools.gateway import Gateway
from app.tools.plant_tools import register_all
from app.tools.registry import ControlLevel, SideEffect, ToolRegistry, ToolSpec

DAY = date(2026, 4, 15)
MEASURED_END = datetime(2026, 6, 23, 11, 50)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)

#: The question the router sends to `investigate`. "how often" is layer 3's keyword and
#: "chiller" is the domain term layer 3.5 requires — both are needed, or the turn refuses
#: before any skill is reached.
INVESTIGATE_QUESTION = "how often has chiller 1 shown this pattern?"


class _FaultLabelArgs(BaseModel):
    """A parameter model matching the real tool's, so the refusal under test comes from the
    Control Plane rather than from argument validation. Those are different guarantees, and a
    test that could not tell them apart would pass against a broken gate."""

    model_config = {"extra": "forbid"}

    fault_label: str = Field(description="A fault class label")


def _pack(label: str | None = "HIGH_HEAD_AMBIGUOUS", *, blind: bool = False, others=()):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = (ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), label or "", values),)
    gates = (
        GateOutcome(
            (GateResult(Gate.RUNNING, passed=False, reason="no readings", remedy="check feed"),)
        )
        if blind
        else GateOutcome((check_running({"a": 141.0}),))
    )
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=gates,
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
        other_labels_same_day=others,
    )


@pytest.fixture
def engineer():
    return compute_scope(Persona.RELIABILITY_ENGINEER)


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    register_all(r)
    return r


# ── the defect this whole file exists for: a request must reach the loop ──────

async def test_the_investigate_skill_actually_calls_a_tool(engineer) -> None:
    """The one assertion that would have caught six modules with no consumer.

    Not *"the loop is importable"* and not *"a chooser was constructed"* — a tool name in
    `tools_called` means a request travelled through `Gateway.invoke` and came back.
    """
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer)
    called = outcome.payload["react"]["tools_called"]
    assert called, "investigate reached no tool at all — the loop still has no consumer"
    assert "explain_fault_class" in called
    assert "differential_availability" in called


async def test_a_request_through_answer_turn_reaches_the_tool_loop(engineer) -> None:
    """The full path: `POST /api/v1/ask` calls `answer_turn`, which is this.

    The router has to resolve `investigate` for this to mean anything, so the routing is
    asserted first — a test that assumed the skill would silently prove the wrong thing.
    """
    assert route(INVESTIGATE_QUESTION).skill is Skill.INVESTIGATE

    turn = await answer_turn(
        question=INVESTIGATE_QUESTION, pack=_pack(), client=None, scope=engineer
    )
    assert turn.used_model is False
    assert "HIGH_HEAD_AMBIGUOUS" in turn.text
    assert "Narrowing" in turn.text, "the differential tool's answer never reached the turn"


async def test_the_other_skills_still_take_the_path_they_always_did(engineer) -> None:
    """This is a widening of one skill, not a rewrite of the table. A change that quietly
    routed `resolve` through a tool loop would be a second decision nobody made."""
    resolved = await skills.dispatch_with_tools("resolve", _pack(), scope=engineer)
    assert resolved.payload is not None
    assert "react" not in resolved.payload
    assert await skills.dispatch_with_tools("explain", _pack(), scope=engineer) is None


# ── the process-global ledger, and why a gateway is built per turn ────────────

async def test_two_consecutive_turns_with_the_same_question_both_reach_the_tools(
    engineer,
) -> None:
    """**The defect adversarial review flagged.** `GATEWAY` is a process global holding `G5`'s
    idempotency ledger. A second turn asking the same question would have had its first call
    answered `replayed`, which the loop reads — correctly — as *this loop is stuck*, and it
    would stop before it started. The second visitor would get the first visitor's silence.
    """
    first = await skills.investigate_with_tools(_pack(), scope=engineer)
    second = await skills.investigate_with_tools(_pack(), scope=engineer)

    for turn, which in ((first, "first"), (second, "second")):
        assert turn.payload["react"]["stop"] != "repeated_call", (
            f"the {which} turn was stopped by an idempotency ledger that outlived a turn"
        )
        assert turn.payload["react"]["tools_called"], f"the {which} turn called no tool"

    assert second.payload["react"]["tools_called"] == first.payload["react"]["tools_called"]


async def test_the_ledger_dies_with_the_turn_that_owns_it(engineer) -> None:
    """`G5`'s guarantee is *a retry within a turn does not act twice*. Stretching it across
    turns is a different promise nobody made, and it is the one that returns stale answers."""
    turn = await skills.investigate_with_tools(_pack(), scope=engineer)
    assert not [s for s in turn.payload["react"]["steps"] if s["result"]["replayed"]]


# ── the chooser: deterministic, and bounded ───────────────────────────────────

async def test_the_chooser_spends_no_model_and_runs_with_the_box_terminated(
    engineer,
) -> None:
    """A model-backed chooser needs a prompt and a transcript recorded against Jarvis. This
    one picks from the catalogue by rule, so the loop is reachable and testable with the GPU
    off — the same split that lets `ModelClient` replay instead of needing a card in CI."""
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer)
    assert outcome.used_model is False


async def test_the_plan_is_the_dependency_order_rather_than_a_list(engineer) -> None:
    """The second question depends on the first answer: what the label *is*, then whether it
    may be narrowed, then the same of every other label recorded that day. On 2026-04-15
    chiller 1 carried five labels at once, which is why the loop exists at all."""
    plan = skills.plan_for(_pack(others=("CONDENSER_LOW_FLOW",)))
    assert [c.tool for c in plan] == [
        "explain_fault_class",
        "differential_availability",
        "explain_fault_class",
    ]
    assert all(len(c.purpose.split()) > 5 for c in plan), "a purpose is read back on a ceiling"


async def test_a_chooser_that_never_returns_is_bounded_rather_than_holding_the_turn(
    engineer, registry
) -> None:
    """**The second defect review flagged.** `asyncio.wait_for` guarded `Gateway.invoke` and
    nothing guarded the chooser call — `max_react_steps` bounds how *many* decisions are taken,
    never how long one takes. A wedged chooser held the turn for ever."""

    async def _never_decides(state):
        await asyncio.sleep(5)
        return ToolChoice.finish("eventually")

    loop = ReactLoop(gateway=Gateway(registry), registry=registry, max_steps=3)
    outcome = await loop.run(
        question="q",
        scope=engineer,
        choose=skills.bounded_chooser(_never_decides, 0.01),
    )
    assert outcome.stop is StopReason.CHOOSER_UNAVAILABLE
    assert "did not decide within 0.01s" in outcome.stop_reason


async def test_the_chooser_bound_reports_a_reason_rather_than_a_blank(engineer, registry) -> None:
    """A bare `TimeoutError` stringifies to nothing, so the loop would print `TimeoutError: `
    where the reason belongs — a blank in the one place the loop exists to explain itself."""

    async def _never_decides(state):
        await asyncio.sleep(5)
        return ToolChoice.finish("eventually")

    loop = ReactLoop(gateway=Gateway(registry), registry=registry, max_steps=2)
    outcome = await loop.run(
        question="q", scope=engineer, choose=skills.bounded_chooser(_never_decides, 0.01)
    )
    assert "one wedged chooser cannot hold the turn" in outcome.stop_reason


async def test_the_chooser_bound_borrows_a_sourced_number_rather_than_inventing_one() -> None:
    """`Q102`. None of the ten ceilings bounds the chooser, so this borrows ceiling 5 and says
    so. An invented eleventh number would be a threshold nobody agreed."""
    from app.config import get_settings

    assert skills.chooser_timeout_s() == get_settings().tool_timeout_s


# ── which of the six answer states a loop ending becomes ──────────────────────

def test_every_loop_ending_has_an_answer_state_and_a_reason() -> None:
    """A `StopReason` with no entry would raise inside the turn — or worse, if the lookup were
    forgiving, it would silently pick a state. `CONTEXT.md` §7 allows exactly six, and
    `react.py` has six endings that are not the same six."""
    assert set(skills._STOP_TO_ANSWER_STATE) == set(StopReason)
    for stop, (state, why) in skills._STOP_TO_ANSWER_STATE.items():
        assert state in set(AnswerState), f"{stop} maps outside the answer contract"
        assert len(why.split()) > 5, f"{stop} has no reason a reader can act on"


def test_no_loop_ending_becomes_failed_or_no_diagnosis() -> None:
    """`Q101`, and the two states this mapping must never reach for.

    `FAILED` is the only one of the six that means a bug, and a loop that stopped for a reason
    it can state in words did not break. `NO_DIAGNOSIS` carries the gate that failed, the
    reason and what would change it — and none of these endings consulted a gate. A refusal
    the gates did not issue is a refusal nobody made, and `CLAUDE.md` §2.6 forbids softening
    that state into anything else.
    """
    states = {state for state, _ in skills._STOP_TO_ANSWER_STATE.values()}
    assert AnswerState.FAILED not in states
    assert AnswerState.NO_DIAGNOSIS not in states


def test_a_ceiling_stop_is_partial() -> None:
    """`Q101` settled here rather than left to whoever reads the code next. Nothing broke, so
    not `FAILED`; the gates never spoke, so not `NO_DIAGNOSIS`; nothing was forbidden, so not
    `BLOCKED`. `PARTIAL` is defined as *some of the question was answered, and what was not is
    named rather than omitted*, which is what a ceiling stop produces."""
    state, why = skills._STOP_TO_ANSWER_STATE[StopReason.STEP_CEILING]
    assert state is AnswerState.PARTIAL
    assert "not a verdict" in why


def test_a_refusal_inside_the_loop_becomes_blocked_rather_than_no_diagnosis() -> None:
    """Two different facts: *policy forbids this* and *the data cannot decide*. Collapsing
    them tells a reader to fix the wrong thing — and makes an honest refusal look like a
    permissions problem, or the reverse."""
    state, _ = skills._STOP_TO_ANSWER_STATE[StopReason.REFUSED]
    assert state is AnswerState.BLOCKED


# ── an early stop never summarises what it happened to collect ────────────────

async def test_a_ceiling_stop_says_what_it_was_still_trying_to_do(engineer, registry) -> None:
    """**Constraint 16, one layer down.** An answer assembled from an evidence set the loop was
    still filling reads as a finished one, and a reader cannot tell it apart from a complete
    enquiry. So the turn reports the intent, not the haul."""
    tiny = ReactLoop(gateway=Gateway(registry), registry=registry, max_steps=1)
    outcome = await skills.investigate_with_tools(
        _pack(others=("CONDENSER_LOW_FLOW",)), scope=engineer, loop=tiny
    )
    assert outcome.state is AnswerState.PARTIAL
    assert "still trying to" in outcome.text
    assert "deliberately not summarised here" in outcome.text


async def test_a_ceiling_stop_does_not_render_the_observations_it_collected(
    engineer, registry
) -> None:
    """The sharper half of the same rule: the first call *succeeded* and its answer is in the
    trace. It must not appear in the prose, or the turn reads as an enquiry that concluded."""
    tiny = ReactLoop(gateway=Gateway(registry), registry=registry, max_steps=1)
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer, loop=tiny)
    assert outcome.payload["react"]["steps_used"] == 1
    assert "It declares itself undecidable" not in outcome.text
    assert "Narrowing" not in outcome.text


async def test_a_ceiling_stop_still_names_which_tools_ran(engineer, registry) -> None:
    """Naming what was reached is a fact about the turn; paraphrasing what it said is a
    summary of an unfinished enquiry. Only the second one is dishonest."""
    tiny = ReactLoop(gateway=Gateway(registry), registry=registry, max_steps=1)
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer, loop=tiny)
    assert "explain_fault_class" in outcome.text
    assert "of 2 planned tool call(s) ran before it stopped" in outcome.text


async def test_a_refused_capability_blocks_the_turn_rather_than_answering(engineer) -> None:
    """Retrying a refusal until it succeeds is how a refused capability executes. The turn
    ends `BLOCKED` and does not compose an answer out of the calls that did work."""
    r = ToolRegistry()

    async def _writes() -> str:
        return "written"

    r.register(
        ToolSpec(
            name="explain_fault_class",
            description="",
            parameters=_FaultLabelArgs,
            side_effect=SideEffect.WRITES_SYNEX_STATE,
            control_level=ControlLevel.NEEDS_APPROVAL,
            handler=_writes,
        )
    )
    loop = ReactLoop(gateway=Gateway(r), registry=r, max_steps=4)
    outcome = await skills.investigate_with_tools(
        _pack(), scope=compute_scope(Persona.TECHNICIAN), loop=loop
    )
    assert outcome.state is AnswerState.BLOCKED
    assert "approve_work" in outcome.text
    assert "The Control Plane decides this, not the model" in outcome.text


# ── a complete plan is not the same as a complete evidence set ────────────────

async def test_a_label_the_model_never_emits_is_a_stated_absence_not_a_broken_call(
    engineer,
) -> None:
    """`explain_fault_class` answers `found: False` with the labels that *do* exist rather
    than raising. So the enquiry completes and the line reads as an absence — which is the
    distinction `Outcome` keeps one layer down: the system worked and said no."""
    r = ToolRegistry()
    register_all(r)
    loop = ReactLoop(gateway=Gateway(r), registry=r, max_steps=8)
    outcome = await skills.investigate_with_tools(
        _pack("HIGH_HEAD_AMBIGUOUS", others=("INVENTED_CLASS",)), scope=engineer, loop=loop
    )
    assert "INVENTED_CLASS" in outcome.text
    assert "is not a label this plant's model emits" in outcome.text
    assert outcome.payload["react"]["stop"] == "answered"


async def test_a_call_that_did_not_answer_makes_a_finished_plan_partial(engineer) -> None:
    """The loop can run its plan to the end and still have gathered less than it asked for.

    Here the second planned tool is registered with no handler, so `G4` returns
    `not_implemented` — declared, visible, and not an answer. The plan finished; the evidence
    set did not, and `PARTIAL` is the state that says so without discarding what did come back.
    """
    r = ToolRegistry()
    r.register(
        ToolSpec(
            name="explain_fault_class",
            description="",
            parameters=_FaultLabelArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=None,
        )
    )
    loop = ReactLoop(gateway=Gateway(r), registry=r, max_steps=6)
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer, loop=loop)
    assert outcome.state is AnswerState.PARTIAL
    assert "1 call(s) did not answer" in outcome.text
    assert "explain_fault_class (not_implemented)" in outcome.text
    assert "1 planned call(s) were never made" in outcome.text


async def test_gates_that_did_not_pass_make_the_turn_partial_and_say_so(engineer) -> None:
    """The tools report what is settled about a *class*. That is never a diagnosis of this
    machine on this day, and when the gates are shut the turn has to say which ones."""
    outcome = await skills.investigate_with_tools(_pack(blind=True), scope=engineer)
    assert outcome.state is AnswerState.PARTIAL
    assert "The gates did not all pass" in outcome.text
    assert "not a diagnosis of this" in outcome.text


async def test_a_complete_enquiry_with_open_gates_answers(engineer) -> None:
    """The ordinary end. `ANSWERED` requires every planned call to have come back *and* the
    gates to have passed — a state this strict is what makes `PARTIAL` mean something."""
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer)
    assert outcome.state is AnswerState.ANSWERED
    assert "the ordinary end" in outcome.text


# ── absences: never a zero, never a dash ──────────────────────────────────────

async def test_an_unlabelled_slot_calls_no_tool_and_says_why(engineer) -> None:
    """5,309 slots carry no fault against 674 that do, so this is the ordinary case. An empty
    enquiry that printed nothing would read as a machine nobody looked at."""
    outcome = await skills.investigate_with_tools(_pack(None), scope=engineer)
    assert outcome.payload["react"]["tools_called"] == []
    assert "there is no class to look up and nothing to narrow" in outcome.text


async def test_a_planned_tool_missing_from_the_catalogue_is_named_not_skipped(
    engineer,
) -> None:
    """An empty registry offers nothing, so every planned call goes unmade. Silently returning
    a one-line answer would read as an enquiry that found nothing to say."""
    empty = ToolRegistry()
    loop = ReactLoop(gateway=Gateway(empty), registry=empty, max_steps=4)
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer, loop=loop)
    assert "was never asked to" in outcome.text
    assert "is not being guessed at" in outcome.text


async def test_an_unrated_severity_is_a_stated_absence_rather_than_a_rank(engineer) -> None:
    """`Q49`: eight of the nine labels have no agreed severity. Printing the fallback without
    saying it is a fallback is how an unrated class acquires a rank somebody schedules."""
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer)
    assert "NO rated severity" in outcome.text
    assert "stated absence rather than a rank" in outcome.text
    assert "Q49" in outcome.text, "the question the absence is waiting on must travel with it"


# ── no identity means no tool call, stated ────────────────────────────────────

async def test_without_a_scope_the_turn_says_no_tool_was_called(engineer) -> None:
    """Permission is plain software, so with nobody to check, the Control Plane cannot be
    asked. Defaulting a persona would be an authorization decision made by a keyword
    argument — the separation law's seventh row, broken by convenience."""
    outcome = await skills.dispatch_with_tools("investigate", _pack(), scope=None)
    assert outcome.payload is not None
    assert "react" not in outcome.payload
    assert "no identity reached it" in outcome.text
    assert outcome.degraded_reason, "a quieter answer and a smaller one look the same on screen"


async def test_a_turn_without_a_scope_still_answers(engineer) -> None:
    """Degraded is stated, not fatal. `CONTEXT.md` §13 — a demonstration where something is
    missing should lose that thing, not its answer."""
    turn = await answer_turn(question=INVESTIGATE_QUESTION, pack=_pack(), client=None)
    assert turn.state in {AnswerState.ANSWERED, AnswerState.PARTIAL}
    assert turn.degraded_reason


# ── the registry is populated, which it was not in any live process ───────────

def test_the_tools_are_bound_before_the_first_turn_needs_them() -> None:
    """`register_all()` existed, was tested against fresh registries, and was called from no
    startup path — so the process-wide registry was empty in every live request. A registry
    nobody populates reads exactly like a registry nobody calls."""
    registry = skills._ensure_registry()
    assert [t.name for t in registry.all()], "the live registry is still empty"
    assert skills._ensure_registry() is registry, "binding twice must not raise on a duplicate"


async def test_the_catalogue_never_offers_a_permanently_refused_tool(engineer) -> None:
    """A gate should be the second line of defence, not the first. Offering a model a tool it
    may never use is an invitation to try, and `set_chiller_setpoint` can never run."""
    outcome = await skills.investigate_with_tools(_pack(), scope=engineer)
    assert "set_chiller_setpoint" not in outcome.payload["react"]["tools_called"]
