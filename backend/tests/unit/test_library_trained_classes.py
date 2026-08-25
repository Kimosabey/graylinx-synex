"""The transcription gates for Part 1 of the curated library.

These tests do not check that the content is *right* — no test can, which is the whole reason
the SME hour exists. They check the properties that make the review possible at all, and every
one of them has a way of failing silently:

* an item that claims a review it has not had,
* an item that borrows `is_sample` to become visible,
* an item that cannot name where it came from, so it is indistinguishable from model output,
* a reordering, which overwrites the author's judgement about which check to ask first,
* a dropped `[SETTLES IT]` marker, which loses the discriminators among the routine checks,
* a class with nothing an operator can do, which starts somebody stuck.

The operator check reads the transcription rather than `Checklist.for_capability`. That method
filters through `visible_items`, which correctly returns nothing while the library is
unreviewed — so asserting through it would pass for the wrong reason today, and keep passing
after the review, when it is the only time it would matter.
"""
from __future__ import annotations

import pytest

from app.domain.cases import DEFAULT_CAPABILITY, Capability, Stage
from app.domain.library.trained_model_classes import (
    DECLARES_UNDECIDABLE,
    NEEDS_A_HUMAN,
    PART,
    ROLE_TAG_SOURCE,
    TEXT_SOURCE,
    TRAINED_MODEL_CLASSES,
    all_items,
    by_label,
    unreviewed_count,
)

ALL = all_items()
LABELS = [c.label for c in TRAINED_MODEL_CLASSES]


# ── the honesty flags ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=LABELS)
def test_every_item_is_unreviewed(fault_class) -> None:
    """No exceptions. An instruction directing physical work on a pressurised circuit that
    claims a review it has not had is the failure inherited constraint 1 exists to stop."""
    for item in fault_class.items:
        assert item.sme_reviewed is False, item.id


@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=LABELS)
def test_nothing_is_flagged_as_sample(fault_class) -> None:
    """`is_sample` means *invented to demonstrate the mechanism*. This is the real library.

    Sample content is shown with `sme_reviewed=True` in `app/services/cases.py`, so borrowing
    the flag is precisely the route by which unreviewed instructions would reach a technician.
    """
    for item in fault_class.items:
        assert item.is_sample is False, item.id


def test_the_whole_library_is_hidden_from_users() -> None:
    """The consequence of the two flags above, asserted where a user would see it."""
    for fault_class in TRAINED_MODEL_CLASSES:
        checklist = fault_class.checklist()
        assert checklist.visible_items() == ()
        assert checklist.unreviewed_count == len(fault_class.items)


def test_the_unreviewed_count_is_every_item() -> None:
    assert unreviewed_count() == len(ALL)
    assert len(ALL) == 86, "Part 1 is 86 of the pack's 124 items"


def test_the_stage_split_is_the_pack_s() -> None:
    """40 RCA, 25 corrective, 21 preventive — the library's 57 · 37 · 30 less Part 2's
    17 · 12 · 9. A class transcribed with only its questions leaves the repair and the
    prevention as content nobody ever opens."""
    split = {stage: sum(1 for i in ALL if i.stage is stage) for stage in Stage}
    assert split == {Stage.RCA: 40, Stage.CORRECTIVE: 25, Stage.PREVENTIVE: 21}


# ── provenance ──────────────────────────────────────────────────────────────────

def test_every_item_names_the_documents_it_came_from() -> None:
    """A curated item that cannot name its source is indistinguishable from model output.

    Two documents, recorded separately: a reviewer who disagrees with a role tag is
    disagreeing with `17`, not with the instruction text in `05`.
    """
    for item in ALL:
        assert item.source_file == TEXT_SOURCE, item.id
        assert item.role_tag_file == ROLE_TAG_SOURCE, item.id
        assert item.source_part == PART, item.id
    assert TEXT_SOURCE != ROLE_TAG_SOURCE


@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=LABELS)
def test_every_item_names_its_fault_class_heading(fault_class) -> None:
    """The heading verbatim, so a reviewer can find the item in the pack by eye."""
    assert fault_class.display
    for item in fault_class.items:
        assert item.source_heading == fault_class.display, item.id
        assert item.source_fault_label == fault_class.label, item.id
        assert fault_class.display in item.provenance


def test_an_item_cannot_be_built_without_its_source() -> None:
    """The base class refuses it, so the provenance rule is enforced rather than remembered."""
    from app.domain.library.curated import TranscribedItem

    with pytest.raises(ValueError, match="cannot name its source"):
        TranscribedItem(id="x", text="Read the field device directly")


# ── order, which is load-bearing ────────────────────────────────────────────────

@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=LABELS)
def test_source_order_is_preserved_within_every_stage(fault_class) -> None:
    """Constraint 39: the next question is the one that could move the most live candidates,
    and the source's numbering is the author's judgement about that. A reordering silently
    overwrites an engineering opinion, so the ids must run 1..n in order within each stage."""
    slug = fault_class.label.lower().replace("_", "-")
    for stage in Stage:
        items = fault_class.at_stage(stage)
        assert items, f"{fault_class.label} has no {stage.value} items"
        assert [i.id for i in items] == [
            f"{slug}-{stage.value}-{n}" for n in range(1, len(items) + 1)
        ]


def test_ids_are_unique_across_part_one() -> None:
    assert len({i.id for i in ALL}) == len(ALL)


def test_the_starved_evaporator_checks_are_in_the_packs_order() -> None:
    """One class asserted line by line, because a shape test cannot catch two items swapped
    with each other — and this is the class the pack calls its demo case."""
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
    assert LABELS == [
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
    assert {i.id for i in ALL if i.settles_it} == {
        "starved-evap-undercharge-or-restriction-rca-1",
        "starved-evap-undercharge-or-restriction-rca-2",
        "starved-evap-undercharge-or-restriction-rca-3",
        "condenser-water-side-unspecified-rca-1",
        "condenser-water-side-unspecified-rca-2",
        "condenser-water-side-unspecified-rca-4",
        "high-head-ambiguous-rca-1",
        "high-head-ambiguous-rca-2",
        "high-head-ambiguous-rca-3",
        "power-high-unexplained-rca-1",
        "power-high-unexplained-rca-3",
        "power-high-unexplained-rca-4",
    }


def test_an_unmarked_item_is_marked_false_not_unknown() -> None:
    """`None` on `settles_it` means the marker document does not cover the item. `05` Part 1
    covers all 86, so every one of them is a stated `True` or a stated `False`."""
    assert all(i.settles_it is not None for i in ALL)


def test_only_the_classes_that_need_a_human_carry_a_marker() -> None:
    """Transcribed, not enforced: it is what the pack happens to say, and it matches
    constraint 27 — only a class the model declares undecidable gets a differential."""
    for fault_class in TRAINED_MODEL_CLASSES:
        if fault_class.settles_it_items:
            assert fault_class.needs_human, fault_class.label


def test_a_marked_item_is_always_a_question() -> None:
    """A discriminator that was a repair would rule a cause out by doing work to the plant."""
    for item in ALL:
        if item.settles_it:
            assert item.stage is Stage.RCA, item.id


# ── constraint 37 ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fault_class", TRAINED_MODEL_CLASSES, ids=LABELS)
def test_every_class_leaves_the_operator_something_to_do(fault_class) -> None:
    """Constraint 37, read off the transcription rather than through the SME gate.

    Otherwise somebody starts stuck rather than getting stuck partway — and the property has
    to hold now, while `visible_items` is empty, or the test is asserting nothing.
    """
    operator_checks = fault_class.for_capability(Capability.OPERATOR)
    assert operator_checks, f"{fault_class.label} walls the operator out entirely"
    assert any(
        i.stage is Stage.RCA for i in operator_checks
    ), f"{fault_class.label} gives the operator no question to open with"


# ── the role tags ───────────────────────────────────────────────────────────────

def test_no_role_tag_was_guessed() -> None:
    """Every Part 1 item is tagged in `17-role-tags-every-check.md`, so nothing fell to
    constraint 24's default here. An untagged item would default to technician *and record
    that it did* — the tag is never inferred from the wording of the check."""
    assert [i.id for i in ALL if i.capability_defaulted] == []


def test_a_defaulted_tag_would_be_technician() -> None:
    """The asymmetry is deliberate: mis-tagging a technician task as operator work puts an
    unqualified person on a pressurised circuit; the reverse merely wastes a callout."""
    assert DEFAULT_CAPABILITY is Capability.TECHNICIAN


def test_every_capability_in_the_role_document_is_used() -> None:
    """Including `vendor`, which tags exactly one item in the whole 131 — the compressor
    overhaul. A transcription that quietly dropped it would lose the only OEM task."""
    used = {i.capability for i in ALL}
    assert used == set(Capability)
    vendor = [i.id for i in ALL if i.capability is Capability.VENDOR]
    assert vendor == ["compressor-inefficiency-corrective-4"]


def test_blocking_is_only_ever_stated_on_a_question() -> None:
    """A repair cannot be what a case is waiting on before it has a cause."""
    for item in ALL:
        if item.blocking:
            assert item.stage is Stage.RCA, item.id


def test_the_three_straight_through_classes_carry_no_blocking_item() -> None:
    """Transcribed as it stands. It is the shape of Q37 rather than a defect to fix here: a
    class with no blocking item can be concluded with no measured answer at all."""
    for fault_class in TRAINED_MODEL_CLASSES:
        if not fault_class.needs_human:
            assert fault_class.blocking_items == (), fault_class.label


# ── what the source says about each class ───────────────────────────────────────

def test_each_class_carries_the_severity_word_the_source_states() -> None:
    """The pack's word, not a mapping onto `faults.Severity` — `warning` is not on that scale,
    and six of the seven classes are `UNRATED` there against `Q49`. Reconciling the two is a
    judgement about severity, and it belongs to a human."""
    assert {c.label: c.severity_word for c in TRAINED_MODEL_CLASSES} == {
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


def test_both_documents_framings_are_kept() -> None:
    """`05` and `17` word the same claim differently, and `17` says nothing at all about the
    three determinate classes. Neither is rewritten into the other."""
    for fault_class in TRAINED_MODEL_CLASSES:
        if fault_class.needs_human:
            assert fault_class.routing_05 == NEEDS_A_HUMAN
            assert fault_class.routing_17 == DECLARES_UNDECIDABLE
        else:
            assert fault_class.routing_05 == "flows straight through"
            assert fault_class.routing_17 == ""


def test_a_note_is_present_only_where_the_source_writes_one() -> None:
    """Absent means absent. Composing the missing ones is authorship, not transcription."""
    assert {i.id for i in ALL if i.source_note} == {
        "starved-evap-undercharge-or-restriction-rca-1",
        "starved-evap-undercharge-or-restriction-rca-2",
        "starved-evap-undercharge-or-restriction-rca-5",
        "refrigerant-side-high-head-rca-5",
        "compressor-inefficiency-rca-1",
        "condenser-water-side-unspecified-rca-2",
    }


def test_an_unknown_label_is_reported_as_absent_not_as_empty() -> None:
    """`None` means *not transcribed in Part 1* — Parts 2 and 3 hold the rest. An empty
    checklist would read as *this class needs no checks*, which is a different claim."""
    assert by_label("INSTRUMENT_FLATLINE") is None
    assert by_label("NO_DIAGNOSIS") is None
