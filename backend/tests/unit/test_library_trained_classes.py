"""The transcription gates for Part 1 of the curated library.

These tests do not check that the checklist content is *right* — no test can, which is the
whole reason the SME hour exists. They check the properties that make the review possible at
all, and every one of them has a way of failing silently:

* an item that says it has been reviewed when it has not,
* an item that borrows `is_sample` to become visible,
* an item that cannot name where it came from, so it is indistinguishable from model output,
* a reordering, which overwrites the author's judgement about which check to ask first,
* a dropped `[SETTLES IT]` marker, which loses the discriminators in among the routine checks,
* a class with nothing an operator can do, which starts somebody stuck.

The last one reads the transcription rather than `Checklist.for_capability`. That method
filters through `visible_items`, which correctly returns nothing while the library is
unreviewed — so asserting through it would pass for the wrong reason today and keep passing
after the review, when it would matter.
"""
from __future__ import annotations

import pytest

from app.domain.cases import Capability, Stage
from app.domain.library.trained_model_classes import (
    CHECKLIST_SOURCE,
    ROLE_TAG_SOURCE,
    TRAINED_MODEL_CLASSES,
    all_items,
    by_label,
    unreviewed_count,
)

ALL = all_items()


def _ids(labelled) -> list[str]:
    return [c.label for c in labelled]


# ── the honesty flags ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=_ids(TRAINED_MODEL_CLASSES))
def test_every_item_is_unreviewed(fault_class) -> None:
    """No exceptions. An instruction directing physical work on a pressurised circuit that
    claims a review it has not had is the failure inherited constraint 1 exists to stop."""
    for item in fault_class.items:
        assert item.to_checklist_item().sme_reviewed is False, item.id


@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=_ids(TRAINED_MODEL_CLASSES))
def test_nothing_is_flagged_as_sample(fault_class) -> None:
    """`is_sample` means *invented to demonstrate the mechanism*. This is the real library.

    Marking it sample would make it visible — `app/services/cases.py` shows sample content
    with `sme_reviewed=True` — and that is exactly the route by which unreviewed instructions
    would reach a technician.
    """
    for item in fault_class.items:
        assert item.to_checklist_item().is_sample is False, item.id


def test_the_whole_library_is_hidden_from_users() -> None:
    """The consequence of the two flags above, asserted where a user would see it."""
    for fault_class in TRAINED_MODEL_CLASSES:
        checklist = fault_class.checklist()
        assert checklist.visible_items() == ()
        assert checklist.unreviewed_count == len(fault_class.items)


def test_the_unreviewed_count_is_every_item() -> None:
    assert unreviewed_count() == len(ALL)
    assert len(ALL) == 86, "Part 1 is 86 of the pack's 124 items"


# ── provenance ──────────────────────────────────────────────────────────────────

def test_every_item_names_the_file_it_came_from() -> None:
    """A curated item that cannot name its source is indistinguishable from model output."""
    for item in ALL:
        assert item.source_file == CHECKLIST_SOURCE, item.id
        assert item.capability_source_file == ROLE_TAG_SOURCE, item.id


@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=_ids(TRAINED_MODEL_CLASSES))
def test_every_item_names_its_fault_class_heading(fault_class) -> None:
    """The heading, verbatim, so a reviewer can find the item in the pack by eye."""
    assert fault_class.heading
    for item in fault_class.items:
        assert item.source_heading == fault_class.heading, item.id


def test_the_text_and_the_role_tag_come_from_different_documents() -> None:
    """They are separately challengeable, and collapsing them would hide that."""
    assert CHECKLIST_SOURCE != ROLE_TAG_SOURCE


# ── order, which is load-bearing ────────────────────────────────────────────────

@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=_ids(TRAINED_MODEL_CLASSES))
def test_source_order_is_preserved_within_every_stage(fault_class) -> None:
    """Constraint 39: the next question is the one that could move the most live candidates,
    and the source's numbering is the author's judgement about that. A reordering is a
    silent overwrite of an engineering opinion, so the positions must run 1..n in order."""
    for stage in Stage:
        items = fault_class.at_stage(stage)
        assert [i.position for i in items] == list(range(1, len(items) + 1)), stage


def test_the_id_carries_the_source_position() -> None:
    """So a reordering shows up as an id change rather than passing unnoticed."""
    for item in ALL:
        assert item.id.endswith(f":{item.stage.value}:{item.position}"), item.id
    assert len({i.id for i in ALL}) == len(ALL), "ids must be unique"


def test_the_starved_evaporator_checks_are_in_the_packs_order() -> None:
    """One class asserted line by line, because a parametrised shape test cannot catch two
    items swapped with each other."""
    starved = by_label("STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION")
    assert starved is not None
    assert [i.text for i in starved.at_stage(Stage.RCA)] == [
        "Sight glass at full load — bubbles or flashing?",
        "Temperature drop across the filter-drier (inlet vs outlet)",
        "Measured superheat at the TXV vs setpoint",
        "Subcooling at the condenser outlet",
        "Any refrigerant service or charge adjustment on this circuit recently?",
        "Evaporator water flow and entering/leaving temperatures vs design",
    ]


def test_the_classes_are_in_the_packs_order() -> None:
    assert _ids(TRAINED_MODEL_CLASSES) == [
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        "REFRIGERANT_SIDE_HIGH_HEAD",
        "COMPRESSOR_INEFFICIENCY",
        "CONDENSER_LOW_FLOW",
        "CONDENSER_WATER_SIDE_UNSPECIFIED",
        "HIGH_HEAD_AMBIGUOUS",
        "POWER_HIGH_UNEXPLAINED",
    ]


# ── the [SETTLES IT] marker ─────────────────────────────────────────────────────

def test_the_marked_items_are_the_ones_the_pack_marks() -> None:
    """The marker identifies the discriminator, and `06-differentials-for-review.md` states
    what each answer eliminates. Dropping it would leave the highest-risk checks looking
    exactly like the routine ones — and those are the items the pack asks to be challenged."""
    marked = {i.id for i in ALL if i.settles_it}
    assert marked == {
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION:rca:1",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION:rca:2",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION:rca:3",
        "CONDENSER_WATER_SIDE_UNSPECIFIED:rca:1",
        "CONDENSER_WATER_SIDE_UNSPECIFIED:rca:2",
        "CONDENSER_WATER_SIDE_UNSPECIFIED:rca:4",
        "HIGH_HEAD_AMBIGUOUS:rca:1",
        "HIGH_HEAD_AMBIGUOUS:rca:2",
        "HIGH_HEAD_AMBIGUOUS:rca:3",
        "POWER_HIGH_UNEXPLAINED:rca:1",
        "POWER_HIGH_UNEXPLAINED:rca:3",
        "POWER_HIGH_UNEXPLAINED:rca:4",
    }


def test_only_the_classes_that_need_a_human_carry_a_marker() -> None:
    """Transcribed, not enforced: it is what the pack happens to say, and it matches
    constraint 27 — only a class the model declares undecidable gets a differential."""
    for fault_class in TRAINED_MODEL_CLASSES:
        if fault_class.settles_it_items:
            assert fault_class.needs_human, fault_class.label


def test_a_marked_item_is_always_a_question() -> None:
    """A discriminator that was a repair would eliminate a cause by doing work to the plant."""
    for item in ALL:
        if item.settles_it:
            assert item.stage is Stage.RCA, item.id


# ── constraint 37 ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=_ids(TRAINED_MODEL_CLASSES))
def test_every_class_leaves_the_operator_something_to_do(fault_class) -> None:
    """Constraint 37, read off the transcription rather than through the SME gate.

    Otherwise somebody starts stuck rather than getting stuck partway — and the check has to
    hold now, while `visible_items` is empty, or it is testing nothing.
    """
    operator_checks = fault_class.for_capability(Capability.OPERATOR)
    assert operator_checks, f"{fault_class.label} walls the operator out entirely"
    assert any(
        i.stage is Stage.RCA for i in operator_checks
    ), f"{fault_class.label} gives the operator no question to open with"


# ── the role tags ───────────────────────────────────────────────────────────────

def test_no_role_tag_was_guessed() -> None:
    """Every Part 1 item is tagged in `17-role-tags-every-check.md`, so nothing fell to
    constraint 24's default here. If a future edit adds an untagged item, it defaults to
    technician and records that it did — it never infers a tag."""
    defaulted = [i.id for i in ALL if i.capability_defaulted]
    assert defaulted == []


def test_a_defaulted_tag_would_be_technician() -> None:
    """The asymmetry is deliberate: mis-tagging a technician task as operator work puts an
    unqualified person on a pressurised circuit; the reverse wastes a callout."""
    from app.domain.cases import DEFAULT_CAPABILITY

    assert DEFAULT_CAPABILITY is Capability.TECHNICIAN


def test_the_blocking_flags_come_from_the_role_document() -> None:
    """Blocking is stated there and nowhere else, and it is stated only on RCA checks —
    a repair cannot be what a case is waiting on before it has a cause."""
    for item in ALL:
        if item.blocking:
            assert item.stage is Stage.RCA, item.id


def test_the_three_straight_through_classes_carry_no_blocking_item() -> None:
    """Transcribed as it stands, and it is the shape of Q37 rather than a defect to fix here:
    a class with no blocking item can be concluded with no measured answer at all."""
    for fault_class in TRAINED_MODEL_CLASSES:
        if not fault_class.needs_human:
            assert fault_class.blocking_items == (), fault_class.label


# ── what the source says about each class ───────────────────────────────────────

def test_each_class_carries_the_severity_word_the_source_states() -> None:
    """The pack's word, not a mapping onto `faults.Severity` — `warning` is not on that
    scale, and six of the seven classes are `UNRATED` there against `Q49`. Reconciling the
    two is a judgement about severity, and it belongs to a human."""
    stated = {c.label: c.stated_severity for c in TRAINED_MODEL_CLASSES}
    assert stated == {
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION": "high",
        "REFRIGERANT_SIDE_HIGH_HEAD": "high",
        "COMPRESSOR_INEFFICIENCY": "high",
        "CONDENSER_LOW_FLOW": "critical",
        "CONDENSER_WATER_SIDE_UNSPECIFIED": "high",
        "HIGH_HEAD_AMBIGUOUS": "warning",
        "POWER_HIGH_UNEXPLAINED": "warning",
    }


def test_needs_a_human_matches_the_four_classes_the_source_names() -> None:
    assert {c.label for c in TRAINED_MODEL_CLASSES if c.needs_human} == {
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        "CONDENSER_WATER_SIDE_UNSPECIFIED",
        "HIGH_HEAD_AMBIGUOUS",
        "POWER_HIGH_UNEXPLAINED",
    }


def test_every_stage_of_the_pack_is_transcribed() -> None:
    """RCA, corrective and preventive. A class transcribed with only its questions leaves the
    repair and the prevention as content nobody ever opens."""
    for fault_class in TRAINED_MODEL_CLASSES:
        for stage in Stage:
            assert fault_class.at_stage(stage), f"{fault_class.label} has no {stage.value}"


def test_a_rationale_is_present_only_where_the_source_writes_one() -> None:
    """Absent means absent. Composing the missing ones is authorship, not transcription."""
    with_rationale = {i.id for i in ALL if i.rationale is not None}
    assert with_rationale == {
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION:rca:1",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION:rca:2",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION:rca:5",
        "REFRIGERANT_SIDE_HIGH_HEAD:rca:5",
        "COMPRESSOR_INEFFICIENCY:rca:1",
        "CONDENSER_WATER_SIDE_UNSPECIFIED:rca:2",
    }


def test_an_unknown_label_is_reported_as_absent_not_as_empty() -> None:
    """`None` means *not transcribed in Part 1* — Parts 2 and 3 hold the rest. An empty
    checklist would read as *this class needs no checks*, which is a different claim."""
    assert by_label("INSTRUMENT_FLATLINE") is None
    assert by_label("NO_DIAGNOSIS") is None
