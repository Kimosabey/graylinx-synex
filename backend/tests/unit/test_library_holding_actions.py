"""Nine drafted holding actions, and the two gates that must both be open before one is given.

A holding action is an operating instruction given to somebody with nobody standing over
them. Constraint 10 says none ships unreviewed, and names the cost it accepts: a deferred
critical fault then runs with no interim protection. These tests defend the shape of that
decision.

The test that matters most is `test_review_alone_does_not_switch_them_on`. If the review flag
were the only gate, signing off the checklist library would put nine unsupervised operating
instructions live in the same stroke — and nobody would have decided to do that. The second
gate exists so the decision has to be taken on purpose, and a future edit that collapses the
two flags into one is exactly what this file is here to catch.
"""
from __future__ import annotations

import dataclasses

from app.domain.library import holding_actions as ha

# ── switched off means unreachable ──────────────────────────────────────────────

def test_no_accessor_returns_a_holding_action_today() -> None:
    """Constraint 10. Every normal route out of this module must be empty."""
    assert ha.available() == ()
    for action in ha.for_review():
        assert ha.holding_action_for(action.fault_label) is None


def test_every_drafted_action_is_both_unreviewed_and_switched_off() -> None:
    assert ha.unreviewed_count() == len(ha.DRAFTED_HOLDING_ACTIONS)
    assert ha.switched_off_count() == len(ha.DRAFTED_HOLDING_ACTIONS)
    assert not any(a.may_be_shown for a in ha.DRAFTED_HOLDING_ACTIONS)


def test_review_alone_does_not_switch_them_on() -> None:
    """The review clears one gate. Going live is a second, deliberate act.

    Collapsing the two into one flag would mean signing off the checklist library also
    published nine unsupervised operating instructions — the decision constraint 10 says must
    be taken on purpose.
    """
    reviewed = dataclasses.replace(ha.DRAFTED_HOLDING_ACTIONS[0], sme_reviewed=True)
    assert not reviewed.may_be_shown
    assert "switched off as a matter of policy" in reviewed.why_not_shown


def test_switching_on_alone_does_not_clear_the_review() -> None:
    """And the reverse: a policy switch cannot substitute for a refrigeration engineer."""
    switched = dataclasses.replace(ha.DRAFTED_HOLDING_ACTIONS[0], switched_on=True)
    assert not switched.may_be_shown
    assert "no refrigeration engineer has reviewed it" in switched.why_not_shown


def test_both_gates_open_is_the_only_way_through() -> None:
    both = dataclasses.replace(
        ha.DRAFTED_HOLDING_ACTIONS[0], sme_reviewed=True, switched_on=True
    )
    assert both.may_be_shown
    assert both.why_not_shown == ""


def test_the_only_accessor_that_returns_drafted_content_says_so_in_its_name() -> None:
    """`for_review` is the review pack. Nothing else hands a switched-off action back."""
    assert len(ha.for_review()) == 9
    assert ha.available() == ()


# ── silence is not an acceptable substitute ─────────────────────────────────────

def test_a_switched_off_action_still_produces_a_sentence() -> None:
    """A case that quietly shows nothing reads as *there is nothing to do in the meantime*."""
    note = ha.why_nothing_is_shown("CONDENSER_LOW_FLOW")
    assert "drafted" in note
    assert "Constraint 10" in note
    assert "no interim protection" in note


def test_a_class_with_no_drafted_action_says_that_instead() -> None:
    """`None` from `holding_action_for` carries two different facts; they stay separable."""
    assert not ha.is_drafted_for("INSTRUMENT_FLATLINE")
    note = ha.why_nothing_is_shown("INSTRUMENT_FLATLINE")
    assert "No interim holding action has been drafted" in note
    assert "authoring a field instruction" in note


def test_a_drafted_class_and_an_undrafted_class_are_distinguishable() -> None:
    assert ha.is_drafted_for("CONDENSER_LOW_FLOW")
    assert not ha.is_drafted_for("INSTRUMENT_IMPLAUSIBLE_EFFICIENCY")
    assert ha.holding_action_for("CONDENSER_LOW_FLOW") is None
    assert ha.holding_action_for("INSTRUMENT_IMPLAUSIBLE_EFFICIENCY") is None


# ── the transcription ───────────────────────────────────────────────────────────

def test_nine_rows_in_source_order() -> None:
    assert [a.fault_label for a in ha.DRAFTED_HOLDING_ACTIONS] == [
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        "HIGH_HEAD_AMBIGUOUS",
        "REFRIGERANT_SIDE_HIGH_HEAD",
        "COMPRESSOR_INEFFICIENCY",
        "CONDENSER_WATER_SIDE_UNSPECIFIED",
        "POWER_HIGH_UNEXPLAINED",
        "CONDENSER_LOW_FLOW",
        "INSTRUMENT_CONTRADICTION",
        "MODEL_BLIND",
    ]


def test_every_action_names_the_document_it_came_from() -> None:
    for action in ha.for_review():
        assert action.source_file.endswith("05-checklist-library-for-review.md")
        assert action.source_part == "Part 3 — Interim holding actions"


def test_the_two_classes_with_no_holding_action_are_recorded_not_filled() -> None:
    """Writing an interim instruction for a suspect sensor would be authorship."""
    drafted = {a.fault_label for a in ha.DRAFTED_HOLDING_ACTIONS}
    for label in ha.LABELS_WITH_NO_HOLDING_ACTION:
        assert label not in drafted


def test_the_load_limits_are_recorded_as_ours_rather_than_the_oems() -> None:
    """The source says so, and it is why the second act must not be automatic."""
    assert "our numbers, not the OEM's" in ha.WHAT_THESE_ARE
    assert "switched OFF" in ha.CURRENT_STATE


def test_the_instruction_text_is_not_softened() -> None:
    """Spot-checks against the source table. A hedge added here is a hedge nobody wrote."""
    by_label = {a.fault_label: a.text for a in ha.DRAFTED_HOLDING_ACTIONS}
    assert by_label["COMPRESSOR_INEFFICIENCY"] == (
        "Avoid running below 40% load — surge risk. Listen for noise or vibration."
    )
    assert by_label["POWER_HIGH_UNEXPLAINED"] == (
        "Log phase currents each shift. Stop the machine if any phase climbs further."
    )
