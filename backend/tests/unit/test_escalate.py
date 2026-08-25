"""Handing the work over: which route, and the distinctions that decide who gets called."""
from __future__ import annotations

import pytest

from app.agents import escalate
from app.domain.cases import CaseState
from app.domain.escalation import Artefact, Blocker


@pytest.mark.parametrize(
    "said,expected",
    [
        ("I haven't got the gauge for that", Blocker.NO_TOOL),
        ("no meter on this unit", Blocker.NO_TOOL),
        ("I'm not allowed to open that panel", Blocker.NO_AUTHORITY),
        ("this needs a supervisor to sign this off", Blocker.NO_AUTHORITY),
        ("I don't understand the reading, need a second opinion", Blocker.CANNOT_INTERPRET),
        ("not now, the plant is still running", Blocker.WRONG_MOMENT),
        ("park this until the next shutdown", Blocker.WRONG_MOMENT),
    ],
)
def test_the_words_decide_the_route(said: str, expected: Blocker) -> None:
    """Four sentences, four destinations. Inherited constraint 9.

    Collapsing these into one "escalate" loses the distinction that decides who gets called
    and what they are handed.
    """
    assert escalate.blocker_in(said) is expected


def test_authority_outranks_tool_when_a_sentence_carries_both() -> None:
    """*"I don't have the authority to run it"* names a tool and an authority.

    The authority is what decides where it goes: sending it to a technician would hand a
    permission question to somebody who also cannot answer it.
    """
    assert escalate.blocker_in("I don't have the authority to run that test") is (
        Blocker.NO_AUTHORITY
    )


def test_asking_for_a_handoff_without_saying_why_names_no_blocker() -> None:
    """**`None` is not `NOT_SURE`, and the difference is load-bearing.**

    *"Escalate this"* is a request with the reason missing, and the four routes go to different
    people — defaulting would quietly pick one. `NOT_SURE` is somebody explicitly saying they
    cannot tell, which is a route of its own that deliberately moves nothing.
    """
    assert escalate.blocker_in("escalate this") is None
    assert escalate.asks_to_escalate("escalate this") is True
    assert escalate.plan(
        "escalate this", equipment_key="chiller_1", fault_label="X", day="2026-04-09"
    ) is None


def test_the_question_asked_back_is_in_the_readers_words() -> None:
    """A technician does not think *"my blocker is NO_TOOL"*."""
    asked = escalate.ask_which()
    assert "haven't got the tool" in asked
    assert "not allowed" in asked
    assert "Not now" in asked
    for name in (b.value for b in Blocker):
        assert name not in asked


def test_no_tool_goes_to_a_technician_with_the_checks_as_the_task_list() -> None:
    handoff = escalate.plan(
        "I haven't got the gauge",
        equipment_key="chiller_1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day="2026-04-09",
    )
    assert handoff is not None
    assert handoff.route.artefact is Artefact.INSPECTION_WORK_ORDER
    assert handoff.route.case_state is CaseState.ESCALATED
    rendered = handoff.render()
    assert "technician" in rendered
    assert "re-derives nothing" in rendered


def test_no_authority_lands_unassigned_and_says_so() -> None:
    """Constraint 9. A named supervisor implies somebody accepted it. Nobody has."""
    handoff = escalate.plan(
        "I'm not allowed to do that",
        equipment_key="chiller_1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day="2026-04-09",
    )
    assert handoff is not None
    rendered = handoff.render()
    assert "unassigned" in rendered
    assert "the question itself, not a measurement" in rendered


def test_wrong_moment_calls_nobody_and_says_that_is_the_point() -> None:
    """A deferral with a reason and a date is not a quiet way of dropping the work."""
    handoff = escalate.plan(
        "not now, it's still running",
        equipment_key="chiller_1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day="2026-04-09",
    )
    assert handoff is not None
    assert handoff.raises_an_artefact is False
    assert "Nobody is called" in handoff.render()
    assert handoff.route.case_state is CaseState.DEFERRED


def test_nothing_is_raised_by_planning_it() -> None:
    """**Escalating is cheap to do and expensive to undo.**

    An inspection work order nobody meant to raise sends a technician across a plant. The
    rendered handoff has to say, in the text a reader sees, that nothing has happened yet.
    """
    handoff = escalate.plan(
        "I haven't got the tool",
        equipment_key="chiller_1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day="2026-04-09",
    )
    assert handoff is not None
    assert "until you confirm it" in handoff.render()


def test_the_episode_id_is_the_form_the_api_takes() -> None:
    handoff = escalate.plan(
        "I haven't got the tool",
        equipment_key="chiller_1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day="2026-04-09",
    )
    assert handoff is not None
    assert handoff.episode_id == "chiller_1:HIGH_HEAD_AMBIGUOUS:2026-04-09"


def test_an_ordinary_question_is_not_read_as_a_handoff() -> None:
    """The reader asking how a machine is doing has not asked for anybody to be called."""
    for ordinary in ("how is chiller 1 doing?", "what happened across the plant?", "hello"):
        assert escalate.asks_to_escalate(ordinary) is False
