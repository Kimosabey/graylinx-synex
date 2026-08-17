"""The four measurement faults, the seven-item fallback, and the flags that keep them off screen.

Three things are being defended here, and each has a way of going quietly wrong.

- **Nothing reaches a user.** `sme_reviewed=False` on every item is the whole gate. A single
  `True` anywhere puts an unreviewed instruction about a pressurised circuit in front of
  somebody, and it would not look like a failure — it would look like content appearing.
- **`is_sample` keeps meaning what it means.** Sample content is invented to demonstrate the
  mechanism. This is the real library awaiting review. Marking it sample would make the two
  indistinguishable and destroy the only flag that currently separates them.
- **The fallback belongs to no class.** Attaching it to one would lend a refrigeration
  engineer's judgement about a named fault to a fault nobody has looked at, invisibly.
"""
from __future__ import annotations

import pytest

from app.domain.cases import Capability, Stage
from app.domain.library import generic_fallback as fb
from app.domain.library import measurement_faults as mf
from app.domain.library.curated import TranscribedItem

ALL = mf.all_items() + fb.FALLBACK_ITEMS


# ── the SME gate ────────────────────────────────────────────────────────────────

def test_not_one_item_is_marked_reviewed() -> None:
    """No refrigeration engineer has read any of this. Constraint 1."""
    assert [i.id for i in ALL if i.sme_reviewed] == []


def test_no_item_reaches_a_user_through_any_checklist() -> None:
    """`visible_items` is the gate, and today it must return nothing for every class."""
    for label in mf.labels():
        checklist = mf.checklist_for(label)
        assert checklist is not None
        assert checklist.visible_items() == ()
        assert checklist.unreviewed_count == len(checklist.items)
    assert fb.fallback_checklist_for("SOMETHING_NEW").visible_items() == ()


def test_narrowing_by_stage_does_not_open_the_gate() -> None:
    """`at_stage` returns a `Checklist`, so the gate has to survive the narrowing."""
    checklist = mf.checklist_for(mf.CONTRADICTION)
    assert checklist is not None
    for stage in Stage:
        assert checklist.at_stage(stage).visible_items() == ()


def test_no_capability_can_see_anything() -> None:
    """`for_capability` filters through `visible_items`, and must keep doing so."""
    checklist = mf.checklist_for(mf.FLATLINE)
    assert checklist is not None
    for capability in Capability:
        assert checklist.for_capability(capability) == ()
        assert checklist.blocked_for(capability) == ()
    assert checklist.blocking_items() == ()


# ── is_sample means invented, and must keep meaning that ────────────────────────

def test_nothing_is_flagged_as_sample() -> None:
    """This is the real library awaiting review, not content invented to demonstrate."""
    assert [i.id for i in ALL if i.is_sample] == []


def test_a_curated_item_cannot_be_constructed_as_a_sample() -> None:
    with pytest.raises(ValueError, match="is_sample"):
        TranscribedItem(
            id="x",
            text="t",
            is_sample=True,
            source_file="f",
            source_part="p",
            source_heading="h",
            role_tag_file="r",
        )


# ── provenance ──────────────────────────────────────────────────────────────────

def test_every_item_names_the_file_and_the_heading_it_came_from() -> None:
    """An item that cannot say where it came from is indistinguishable from model output."""
    for item in ALL:
        assert item.source_file
        assert item.source_part
        assert item.source_heading
        assert item.role_tag_file
        assert item.provenance


def test_an_item_without_provenance_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="cannot name its source"):
        TranscribedItem(id="x", text="t")


def test_the_text_and_the_role_tag_name_their_own_documents() -> None:
    """Two human judgements by two authors — a reviewer disputing a tag disputes doc 17."""
    for item in mf.all_items():
        assert item.source_file.endswith("05-checklist-library-for-review.md")
        assert item.role_tag_file.endswith("17-role-tags-every-check.md")


# ── the transcription itself ────────────────────────────────────────────────────

def test_four_classes_and_thirty_eight_items() -> None:
    assert len(mf.MEASUREMENT_FAULTS) == 4
    assert len(mf.all_items()) == 38


def test_the_stage_split_is_seventeen_twelve_nine() -> None:
    counts = mf.stage_counts()
    assert counts[Stage.RCA] == 17
    assert counts[Stage.CORRECTIVE] == 12
    assert counts[Stage.PREVENTIVE] == 9


def test_item_ids_are_unique() -> None:
    ids = [i.id for i in ALL]
    assert len(ids) == len(set(ids))


def test_no_role_tag_was_defaulted() -> None:
    """Doc 17 tags every check in Part 2 and Part 3, so constraint 24's default never fired.

    Asserted rather than assumed: a defaulted tag is a gap in the source and has to be
    visible as one, so if a future edit drops a tag this test says so instead of silently
    routing the item to a technician.
    """
    assert [i.id for i in ALL if i.capability_defaulted] == []


def test_settles_it_and_blocking_coincide_but_stay_separate_fields() -> None:
    """They are the same on every Part 2 item — and the sources define them differently.

    `[SETTLES IT]` is a belief about discriminating power; `BLOCKING` is *the case cannot be
    root-caused until a human answers*. Merging them on the strength of this coincidence
    would erase a distinction two documents drew on purpose, so the coincidence is recorded
    as a fact rather than as an implementation.
    """
    for item in mf.all_items():
        assert item.settles_it == item.blocking


def test_every_measurement_class_carries_an_operator_check() -> None:
    """Constraint 37, read off the raw transcription — `operator_can_start` cannot see it yet.

    `operator_can_start` filters through `visible_items` and therefore returns `False` for
    every class today, which is correct and useless as a test of the content. This asserts
    the library will satisfy constraint 37 the moment the review lands.
    """
    for label in mf.labels():
        assert mf.operator_items(label), label


def test_severity_is_carried_as_the_sources_own_word() -> None:
    """`warning` is not a `Severity` value, and translating it would invent a rating."""
    words = {f.label: f.severity_word for f in mf.MEASUREMENT_FAULTS}
    assert words[mf.CONTRADICTION] == "high"
    assert words[mf.FLATLINE] == "high"
    assert words[mf.IMPLAUSIBLE_EFFICIENCY] == "high"
    assert words[mf.MODEL_BLIND] == "warning"


def test_both_documents_framings_are_kept_and_neither_is_resolved() -> None:
    """The two sources contradict each other about who raises these, so both are recorded."""
    for fault in mf.MEASUREMENT_FAULTS:
        assert fault.routing_05 != fault.routing_17
        assert "cannot resolve" in fault.routing_05
        assert "our arithmetic" in fault.routing_17


def test_an_unknown_label_gets_none_rather_than_a_borrowed_class() -> None:
    assert mf.checklist_for("SOMETHING_ELSE") is None
    assert mf.items_for("SOMETHING_ELSE") == ()


def test_the_unreviewed_counter_reports_the_whole_library() -> None:
    assert mf.unreviewed_count() == 38
    assert fb.unreviewed_count() == 7


# ── the generic fallback belongs to no class ────────────────────────────────────

def test_the_fallback_is_seven_items() -> None:
    assert len(fb.FALLBACK_ITEMS) == 7
    assert fb.FALLBACK_ITEM_COUNT == 7


def test_no_fallback_item_is_attributed_to_a_fault_class() -> None:
    """The whole point of the seven. Attribution would lend curated judgement to an
    uncurated fault, and it would be invisible on the screen."""
    assert [i.id for i in fb.FALLBACK_ITEMS if i.source_fault_label is not None] == []


def test_no_fallback_item_appears_in_any_measurement_class() -> None:
    class_item_ids = {i.id for i in mf.all_items()}
    assert class_item_ids.isdisjoint({i.id for i in fb.FALLBACK_ITEMS})


def test_the_arriving_label_goes_on_the_checklist_never_on_the_items() -> None:
    checklist = fb.fallback_checklist_for("A_BRAND_NEW_LABEL")
    assert checklist.fault_label == "A_BRAND_NEW_LABEL"
    assert all(i.source_fault_label is None for i in checklist.items)


def test_an_unlabelled_fault_still_gets_the_fallback() -> None:
    assert fb.fallback_checklist_for(None).fault_label == "unlabelled"
    assert len(fb.fallback_checklist_for(None).items) == 7


def test_the_fallback_carries_no_settles_it_verdict() -> None:
    """The marker lives in doc 05, which does not carry these seven at all.

    `None` rather than `False`: *"the document that marks it does not cover this item"* is a
    different fact from *"the document covers it and left it unmarked"*.
    """
    assert [i.settles_it for i in fb.FALLBACK_ITEMS] == [None] * 7


def test_the_honest_count_is_a_hundred_and_twenty_four_plus_seven() -> None:
    """`131 across 11 classes` folds seven unattributed items into a per-class total."""
    assert fb.honest_total() == 131
    assert fb.CURATED_ITEM_COUNT == 124
    note = fb.count_note()
    assert "124" in note
    assert "attached to no class" in note


def test_the_sources_own_review_question_is_carried_not_answered() -> None:
    assert "refuse" in fb.OPEN_REVIEW_QUESTION
