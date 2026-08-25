"""The handoff, reached the way a reader reaches it: by typing a sentence.

`test_escalate.py` holds `escalate.py` to the route table. This holds the *wiring* to the
claim that matters — that somebody who says *"I can't do this"* into the chat gets the handoff,
rather than the checklist they could not run.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.agents import skills
from app.agents.router import Skill, route
from app.analytics.honesty import DataWindow
from app.domain.answer import AnswerState
from app.services.evidence import EvidencePack


def _pack() -> EvidencePack:
    """One episode's worth of pack — enough for the skill to name what would be handed over."""
    return EvidencePack(
        equipment_key="chiller_1",
        equipment_display="Chiller 1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day=date(2026, 4, 9),
        slot_count=12,
        window=DataWindow(
            start=datetime(2026, 4, 9, 0, 0), end=datetime(2026, 4, 9, 23, 45)
        ),
        severity="undecidable",
        severity_text="severity is not agreed for this class",
        is_undecidable=True,
    )


@pytest.mark.parametrize(
    "said",
    [
        "I can't do this",
        "escalate this",
        "I haven't got the gauge for that",
        "I'm not allowed to open that panel",
        "this needs a second opinion",
        "not now, the plant is still running",
    ],
)
def test_a_stuck_sentence_routes_to_the_skill_that_can_hand_it_over(said: str) -> None:
    """**Before this, none of these had anywhere to go.**

    `RC7`'s routes were built and tested and no request reached them, so the one thing a
    technician standing at a machine most needs to say produced a checklist they had already
    said they could not run.
    """
    assert route(said, last_equipment="chiller_1").skill is Skill.RESOLVE


def test_a_named_blocker_produces_a_handoff_awaiting_approval() -> None:
    """`NEEDS_APPROVAL`, because escalating is cheap to do and expensive to undo."""
    outcome = skills.dispatch("resolve", _pack(), "I haven't got the gauge")
    assert outcome is not None
    assert outcome.state is AnswerState.NEEDS_APPROVAL
    assert outcome.payload["goes_to"] == "technician"
    assert outcome.payload["artefact"] == "inspection_work_order"
    assert "until you confirm it" in outcome.text


def test_no_authority_lands_unassigned_and_the_payload_says_so() -> None:
    """Constraint 9. A named supervisor would imply somebody accepted it. Nobody has."""
    outcome = skills.dispatch("resolve", _pack(), "I'm not allowed to do that")
    assert outcome is not None
    assert outcome.payload["lands_unassigned"] is True
    assert outcome.payload["goes_to"] == "supervisor"


def test_wrong_moment_raises_nothing_and_calls_nobody() -> None:
    outcome = skills.dispatch("resolve", _pack(), "not now, it's still running")
    assert outcome is not None
    assert outcome.payload["artefact"] == "none"
    assert outcome.payload["case_state"] == "deferred"
    assert "Nobody is called" in outcome.text


def test_asking_to_escalate_without_saying_why_asks_back() -> None:
    """**The four routes go to four different people, so a default would pick one for them.**

    `PARTIAL` rather than `NEEDS_APPROVAL`: nothing is drafted, because which handoff is not
    yet known.
    """
    outcome = skills.dispatch("resolve", _pack(), "escalate this")
    assert outcome is not None
    assert outcome.state is AnswerState.PARTIAL
    assert "Which of these is it?" in outcome.text
    assert outcome.payload is None or "artefact" not in (outcome.payload or {})


def test_the_ordinary_question_still_gets_the_checklist() -> None:
    """The handoff is a branch, not a replacement — `RC1`–`RC5` are untouched."""
    outcome = skills.dispatch("resolve", _pack(), "what should I check?")
    assert outcome is not None
    assert outcome.state in (AnswerState.ANSWERED, AnswerState.BLOCKED)
    assert "Case " in outcome.text


def test_no_question_at_all_still_gets_the_checklist() -> None:
    """A caller that passes nothing gets the behaviour that existed before this branch."""
    outcome = skills.dispatch("resolve", _pack())
    assert outcome is not None
    assert "Case " in outcome.text


def test_the_language_model_writes_none_of_it() -> None:
    """`RC16`: the route and the artefact are deterministic, and answerable with the box off.

    A handoff whose destination came from a prompt could not answer *"why this person"* without
    replaying that prompt — and would stop working the moment the GPU went away.
    """
    for said in ("I haven't got the gauge", "I'm not allowed", "escalate this"):
        outcome = skills.dispatch("resolve", _pack(), said)
        assert outcome is not None
        assert outcome.used_model is False
