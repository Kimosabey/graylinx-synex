"""`RC6` both follow-up checklists · `RC11` a preventive item nobody owns.

Two failures shape everything below, and both are measured rather than imagined:

- **30 of the 124 curated items are preventive.** A case that attaches only the repair fixes
  the machine and leaves those 30 as content nobody opens — the condenser is cleaned and
  nothing changes the interval that let it foul.
- **38 of the 124 role tags are supervisor, almost all of them preventive.** Prevention is a
  records-and-authority activity, so the preventive stage lands on the one role that had no
  queue to receive it. `U7` exists for that, and `RC11` is what fills the queue.
"""
from __future__ import annotations

import pytest

from app.domain.cases import (
    Capability,
    Checklist,
    ChecklistItem,
    Finding,
    FindingKind,
    Stage,
    may_advance,
)
from app.domain.escalation import Candidate
from app.domain.followup import (
    APPROVER_CAPABILITY,
    BLOCKING_ITEMS_IN_LIBRARY,
    FOLLOW_UP_STAGES,
    LIBRARY_STAGE_SPLIT,
    RECURRENCE_INTERVAL_DAYS,
    CommitmentState,
    RootCause,
    attach_follow_ups,
    choose_approver,
    commitments_for,
    commitments_from,
    library_stage_report,
    obligation_gap,
)


def _item(id_: str, stage: Stage, **kw) -> ChecklistItem:
    kw.setdefault("sme_reviewed", True)
    return ChecklistItem(id=id_, text=f"check {id_}", stage=stage, **kw)


#: A fault class carrying all three stages, so the RCA items are present and must still be
#: excluded from the follow-up rather than absent by luck.
FULL_LIBRARY = Checklist(
    "CONDENSER_LOW_FLOW",
    (
        _item("rca-strainer", Stage.RCA, capability=Capability.OPERATOR),
        _item("rca-flow", Stage.RCA, capability=Capability.TECHNICIAN, blocking=True),
        _item("cor-clean", Stage.CORRECTIVE, capability=Capability.TECHNICIAN, blocking=True),
        _item("prv-interval", Stage.PREVENTIVE, capability=Capability.SUPERVISOR),
        _item("prv-trend", Stage.PREVENTIVE, capability=Capability.SUPERVISOR),
    ),
)

FOULING = RootCause(
    cause_id="rc-fouling",
    label="condenser water-side fouling",
    confirmed_by=("condenser approach measured at the panel — high",),
)


# ── RC6: both stages, always ───────────────────────────────────────────────────

def test_recording_a_root_cause_never_attaches_only_the_repair() -> None:
    """The failure `RC6` exists to prevent. 30 of 124 curated items are preventive, and a
    case that attaches the repair alone leaves every one of them unopened — the machine is
    fixed and nothing changes what let it break."""
    follow_up = attach_follow_ups(FOULING, FULL_LIBRARY)
    assert follow_up.stages_attached == FOLLOW_UP_STAGES
    assert len(follow_up.corrective.items) == 1
    assert len(follow_up.preventive.items) == 2


def test_the_rca_stage_is_never_re_attached_as_follow_up_work() -> None:
    """RCA items are the checks that produced the cause. Handing them back would ask a
    technician to re-establish something the case has already settled."""
    follow_up = attach_follow_ups(FOULING, FULL_LIBRARY)
    attached = {i.id for a in follow_up.attachments for i in a.items}
    assert attached == {"cor-clean", "prv-interval", "prv-trend"}
    with pytest.raises(ValueError):
        follow_up.for_stage(Stage.RCA)


def test_an_empty_stage_is_still_attached_and_carries_words() -> None:
    """An absence is not a zero and not a dash. An empty preventive list left to speak for
    itself reads as *nothing needed here*, which is a claim about the equipment nobody made.
    """
    repair_only = Checklist("X", (_item("cor-1", Stage.CORRECTIVE),))
    follow_up = attach_follow_ups(FOULING, repair_only)
    preventive = follow_up.preventive
    assert preventive.is_empty
    assert preventive.stage in follow_up.stages_attached
    assert "gap in the library" in preventive.absence_reason
    assert "not a statement that none is needed" in preventive.absence_reason


def test_a_content_hole_and_a_review_backlog_are_not_the_same_absence() -> None:
    """Only one of them is somebody's next task. Reporting both as "no items" would let the
    SME hour — a queue that will clear — look identical to content that does not exist."""
    missing = attach_follow_ups(FOULING, Checklist("X", (_item("cor-1", Stage.CORRECTIVE),)))
    unreviewed = attach_follow_ups(
        FOULING,
        Checklist("X", (ChecklistItem("prv-1", "text", stage=Stage.PREVENTIVE),)),
    )
    assert "gap in the library" in missing.preventive.absence_reason
    assert "refrigeration engineer" in unreviewed.preventive.absence_reason
    assert missing.preventive.absence_reason != unreviewed.preventive.absence_reason


def test_an_unreviewed_follow_up_is_withheld_and_counted_rather_than_shown() -> None:
    """Constraint 1: a checklist directs physical work on pressurised refrigerant equipment,
    and no refrigeration engineer has read the library. The count keeps the gap a visible
    number instead of a silent omission."""
    library = Checklist(
        "X",
        (
            ChecklistItem("prv-1", "unreviewed", stage=Stage.PREVENTIVE),
            ChecklistItem("prv-2", "unreviewed", stage=Stage.PREVENTIVE),
        ),
    )
    preventive = attach_follow_ups(FOULING, library).preventive
    assert preventive.items == ()
    assert preventive.withheld_for_review == 2


def test_an_untagged_item_is_a_question_rather_than_a_repair() -> None:
    """Constraint 24's reasoning, applied to the stage tag. Mis-staging a repair as a question
    sends somebody to look; the reverse attaches an unasked-for repair to a confirmed cause and
    puts it in front of a technician as agreed work."""
    assert ChecklistItem("i", "text").stage is Stage.RCA
    untagged = Checklist("X", (ChecklistItem("i", "text", sme_reviewed=True),))
    follow_up = attach_follow_ups(FOULING, untagged)
    assert follow_up.corrective.is_empty
    assert follow_up.preventive.is_empty


# ── RC6 against the constraints it inherits ────────────────────────────────────

def test_a_confirmation_does_not_eliminate_its_siblings() -> None:
    """Constraint 28. A fouled condenser on a machine that is also low on flow is two real
    causes, and collapsing to the first confirmation is how the second gets missed."""
    cause = RootCause(
        cause_id="rc-fouling",
        label="condenser water-side fouling",
        confirmed_by=("approach measured high",),
        siblings_still_live=("condenser low flow",),
    )
    note = attach_follow_ups(cause, FULL_LIBRARY).siblings_note
    assert "condenser low flow" in note
    assert "eliminates nothing" in note


def test_a_cause_recorded_with_no_check_behind_it_says_so() -> None:
    """Constraint 31: every verdict records the check and the answer that caused it. *"Why did
    nobody look at the tower?"* needs a better answer than *"the software decided"*."""
    bare = RootCause(cause_id="rc-x", label="something", confirmed_by=())
    assert "no check behind it" in bare.evidence_note
    assert "no check behind it" in attach_follow_ups(bare, FULL_LIBRARY).render()


def test_a_blocking_corrective_item_still_gates_the_case() -> None:
    """A blocking item at the corrective stage stalls a case that already has its cause —
    a different stall from one that blocks the diagnosis, and the same rule settles it.
    Only a measured reading opens it; an estimate does not (constraint 20)."""
    corrective = attach_follow_ups(FOULING, FULL_LIBRARY).corrective.checklist
    estimated = {"cor-clean": Finding("cor-clean", FindingKind.ESTIMATED)}
    blocked, why = may_advance(corrective, estimated)
    assert blocked is False
    assert "no measured answer" in why
    opened, _ = may_advance(corrective, {"cor-clean": Finding("cor-clean", FindingKind.MEASURED)})
    assert opened is True


def test_the_library_split_is_the_measured_one() -> None:
    """57 RCA · 37 corrective · 30 preventive = 124 items across 11 fault classes, 24 of them
    blocking. The 7-item generic fallback belongs to no class and is deliberately outside the
    split — "131 across 11 classes" is the imprecise phrasing."""
    assert LIBRARY_STAGE_SPLIT[Stage.RCA] == 57
    assert LIBRARY_STAGE_SPLIT[Stage.CORRECTIVE] == 37
    assert LIBRARY_STAGE_SPLIT[Stage.PREVENTIVE] == 30
    assert sum(LIBRARY_STAGE_SPLIT.values()) == 124
    assert BLOCKING_ITEMS_IN_LIBRARY == 24


def test_the_blocking_split_across_stages_is_reported_as_unrecorded() -> None:
    """Dividing 24 across three stages in proportion to their sizes would produce three
    numbers that look measured and are not. No source records the split."""
    report = library_stage_report()
    assert "124 curated items" in report
    assert "not recorded anywhere" in report
    assert "not estimated here" in report


# ── RC11: an owner and a date, or the reason there is neither ──────────────────

SUPERVISORS = (
    Candidate("Meera", Capability.SUPERVISOR, open_items=6),
    Candidate("Raj", Capability.SUPERVISOR, open_items=1),
)


def test_a_preventive_item_with_no_named_approver_is_not_a_commitment() -> None:
    """`RC11`'s whole claim. A preventive line with no owner is not prevention, it is a
    sentence — and prevention landed on the one role that had no queue to receive it."""
    (first, _second) = commitments_from(FULL_LIBRARY.at_stage(Stage.PREVENTIVE), candidates=())
    assert first.state is CommitmentState.UNOWNED
    assert first.approver == ""
    assert first.is_an_obligation is False
    assert "no named approver" in first.reason
    assert "`U7`" in first.reason


def test_no_recurrence_interval_is_invented() -> None:
    """`RC11` says "recurring" and no source anywhere says how often. A plausible 30 or 90
    days is worse than nothing: a wrong interval reads as a schedule right up until the thing
    it was meant to prevent happens. TBD (Q62)."""
    assert RECURRENCE_INTERVAL_DAYS is None
    commitment = commitments_from(FULL_LIBRARY.at_stage(Stage.PREVENTIVE), SUPERVISORS)[0]
    assert commitment.state is CommitmentState.UNSCHEDULED
    assert commitment.interval_days is None
    assert commitment.approver == "Raj"
    assert "Q62" in commitment.reason
    assert commitment.is_an_obligation is False


def test_an_agreed_interval_supplied_by_a_human_makes_it_a_real_obligation() -> None:
    """The mechanism works; only the number is missing. An interval that was supplied is a
    different thing from one the software chose, and the wording says which it was."""
    commitment = commitments_from(
        FULL_LIBRARY.at_stage(Stage.PREVENTIVE), SUPERVISORS, interval_days=90
    )[0]
    assert commitment.state is CommitmentState.SCHEDULED
    assert commitment.interval_days == 90
    assert commitment.is_an_obligation is True
    assert "supplied rather than assumed" in commitment.reason


def test_a_supervisor_is_not_a_lesser_technician() -> None:
    """Constraints 13 and 25. A technician with nothing on their plate is still not eligible
    to approve a preventive obligation, because the capability required is authority and
    records — not a lighter workload and not a rank."""
    idle_technician = Candidate("Sam", Capability.TECHNICIAN, open_items=0, can_measure=True)
    assert choose_approver((idle_technician,)) is None
    chosen = choose_approver((idle_technician, *SUPERVISORS))
    assert chosen is not None
    assert chosen.capability is APPROVER_CAPABILITY


def test_the_approver_is_chosen_by_workload_and_never_by_seniority() -> None:
    """Ranking by seniority once sent a filter-drier restriction to a supervisor because one
    incidental records question outranked three refrigeration measurements. Blocking items
    count double, because they are what actually stops other cases moving."""
    busy = Candidate("Meera", Capability.SUPERVISOR, open_items=2, open_blocking_items=3)
    light = Candidate("Raj", Capability.SUPERVISOR, open_items=4)
    chosen = choose_approver((busy, light))
    assert chosen is not None and chosen.name == "Raj"


def test_a_tie_between_approvers_does_not_break_on_who_can_measure() -> None:
    """`RC16` breaks ties toward whoever can physically measure, because the work being
    handed over is a measurement. A preventive obligation is records and authority, so
    carrying that tie-break across would smuggle a gauge criterion into an authority
    decision — constraint 25's failure by a quieter door."""
    measures = Candidate("Zara", Capability.SUPERVISOR, open_items=2, can_measure=True)
    does_not = Candidate("Amit", Capability.SUPERVISOR, open_items=2, can_measure=False)
    chosen = choose_approver((measures, does_not))
    assert chosen is not None and chosen.name == "Amit"


def test_a_corrective_item_never_becomes_a_recurring_commitment() -> None:
    """A repair set to recur would be carried out again on a machine that no longer has the
    fault. The stage is filtered here rather than trusted from the caller."""
    repairs_only = Checklist("X", (_item("cor-1", Stage.CORRECTIVE),))
    assert commitments_from(repairs_only, SUPERVISORS, interval_days=90) == ()

    mixed = Checklist("X", (_item("cor-1", Stage.CORRECTIVE), _item("prv-1", Stage.PREVENTIVE)))
    commitments = commitments_from(mixed, SUPERVISORS, interval_days=90)
    assert [c.item_id for c in commitments] == ["prv-1"]


def test_an_unreviewed_preventive_item_never_becomes_an_obligation() -> None:
    """Constraint 1 again, one layer on: scheduling an unreviewed instruction to recur would
    put it in front of somebody every quarter instead of once."""
    library = Checklist("X", (ChecklistItem("prv-1", "unreviewed", stage=Stage.PREVENTIVE),))
    assert commitments_from(library, SUPERVISORS, interval_days=90) == ()


# ── the gap, reported in words ─────────────────────────────────────────────────

def test_the_obligation_gap_is_words_and_not_a_bare_zero() -> None:
    """Zero obligations is the same number whether nothing was preventable or nothing was
    owned, and those are opposite situations."""
    follow_up = attach_follow_ups(FOULING, FULL_LIBRARY)
    owned, text_only, why = obligation_gap(commitments_for(follow_up, candidates=()))
    assert (owned, text_only) == (0, 2)
    assert "no named approver" in why

    _owned, _text, empty_why = obligation_gap(())
    assert "absence of content" in empty_why


def test_a_fully_owned_and_scheduled_set_reports_no_gap() -> None:
    """The positive case still answers in words, so a reader never has to infer meaning from
    a count that happens to equal the total."""
    follow_up = attach_follow_ups(FOULING, FULL_LIBRARY)
    commitments = commitments_for(follow_up, SUPERVISORS, interval_days=90)
    owned, text_only, why = obligation_gap(commitments)
    assert (owned, text_only) == (2, 0)
    assert "named approver and a recurrence" in why


# ── added 2026-08-17 after adversarial review ──────────────────────────────────

def test_a_review_backlog_is_not_reported_as_a_content_hole() -> None:
    """**The defect this closes fired for all 30 preventive items.**

    `sme_reviewed` defaults to `False` and nothing in the 124-item library has been read by a
    refrigeration engineer, so `commitments_from` returns nothing — and `obligation_gap` used
    to report that as *"no preventive item was attached"*. That is a statement about the
    content when the truth is a statement about the review, and the rest of this module exists
    to keep those apart.
    """
    _, _, words = obligation_gap((), unreviewed_preventive=30)

    assert "none has been read by a refrigeration engineer" in words
    assert "the review is missing, not the content" in words
    assert "no preventive item was attached" not in words


def test_a_genuine_content_hole_still_says_so() -> None:
    """The fix must not swallow the case it was originally written for."""
    _, _, words = obligation_gap((), unreviewed_preventive=0)
    assert "absence of content" in words
