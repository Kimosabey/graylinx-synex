"""`U6` the reliability workspace · `U7` the supervisor queue.

**The trap these tests exist for is inherited constraint 25.** Role order is *display* order,
not a capability ladder. Ranking by seniority once sent a filter-drier restriction to a
supervisor because one incidental records question outranked three refrigeration measurements.
So the assertions below are written in both directions: a supervisor is refused the residuals a
reliability engineer sees, exactly as the engineer is refused the approvals the supervisor
holds. Neither is above the other, and a test that only checked the supervisor could see *more*
would pass against the ladder it is supposed to forbid.

**The second trap is `RC9`.** Four open cases once described transmitters repaired weeks
earlier while twenty had been waiting since April. A case whose condition cleared is evidence
about the plant; a case nobody has touched is evidence about the queue. One flag would make a
fixed machine and a forgotten one look identical, so the two are asserted as separate tuples
with separate actions and no combined total anywhere.

Numbers here are the measured ones: chiller 1's current model at nRMSE 48.03 against chiller
2's 2.65, `HIGH_HEAD_AMBIGUOUS` at 412 slots on 2026-04-15, and 39 episodes over 12
equipment-days. Nothing is invented.
"""
from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from app.analytics.verification import Outcome, Verification
from app.domain import authority, residuals
from app.services import queues
from app.services.control_plane import Capability, Persona, compute_scope
from app.services.queues import (
    ACTION_FOR,
    ADMITS,
    CLEARED_NEEDS_A_PERSON,
    QUEUE_ORDER_REASON,
    SECTIONS_OF,
    AgeingKind,
    Blocked,
    ClosureBlock,
    ClosureRow,
    Section,
    SupervisorQueue,
    Surface,
    admission,
    fit_note_for,
    reliability_workspace,
    residuals_behind,
    supervisor_queue,
)


def _held(persona: Persona) -> frozenset[Capability]:
    """The real Control Plane's answer, so these tests move when `G1` moves."""
    return frozenset(compute_scope(persona).capabilities)


ENGINEER = _held(Persona.RELIABILITY_ENGINEER)
SUPERVISOR = _held(Persona.SUPERVISOR)
TECHNICIAN = _held(Persona.TECHNICIAN)
ANALYST = _held(Persona.ANALYST)
EVERYTHING = frozenset(Capability)

#: No persona lacks `view_faults` today. The admission table must not assume that, because an
#: identity resolved before its scope is computed holds nothing at all.
NOTHING: frozenset[Capability] = frozenset()

DAY = date(2026, 4, 15)
LATER = date(2026, 6, 23)


@dataclass(frozen=True)
class _Case:
    """A `CaseRecord`, structurally. `app.db.state.CaseRow` satisfies the same protocol, and
    building one here is what keeps this surface testable with PostgreSQL stopped."""

    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    state: str
    updated_at: datetime
    stale_at: datetime | None
    stale_reason: str
    condition_cleared: bool
    slot_count: int


def _case(
    *,
    seed_key: str = "chiller_1|HIGH_HEAD_AMBIGUOUS|2026-04-15",
    equipment_key: str = "chiller_1",
    fault_label: str = "HIGH_HEAD_AMBIGUOUS",
    day: date = DAY,
    state: str = "detected",
    stale_at: datetime | None = None,
    stale_reason: str = "",
    condition_cleared: bool = False,
    slot_count: int = 412,
) -> _Case:
    return _Case(
        seed_key=seed_key,
        equipment_key=equipment_key,
        fault_label=fault_label,
        day=day,
        state=state,
        updated_at=datetime(2026, 4, 15, 9, 0),
        stale_at=stale_at,
        stale_reason=stale_reason,
        condition_cleared=condition_cleared,
        slot_count=slot_count,
    )


def _verification(outcome: Outcome, reason: str = "measured against this asset's own band") -> (
    Verification
):
    return Verification(
        outcome=outcome, reason=reason, residual_name="Chiller_Current", notes=()
    )


# ── constraint 25: admitted by capability, never by rank ───────────────────────

@pytest.mark.parametrize("section", list(Section))
def test_only_the_named_capability_admits_a_section_and_no_pile_of_others_does(
    section: Section,
) -> None:
    """The ladder, refused structurally. Holding *every other capability in the system* —
    including the administrator's `edit_policy` — opens nothing, because admission is a lookup
    against one named capability rather than a comparison against a rank."""
    needed = ADMITS[section]
    assert admission(section, frozenset({needed})).admitted is True
    assert admission(section, EVERYTHING - {needed}).admitted is False


def test_a_supervisor_is_not_a_more_capable_technician_and_neither_contains_the_other() -> None:
    """Constraint 25 in its plainest form. If either capability set were a superset of the
    other, every downstream question could be answered by ordering the two — which is the
    seniority comparison that sent a filter-drier restriction to a supervisor."""
    assert not SUPERVISOR >= ENGINEER
    assert not ENGINEER >= SUPERVISOR
    assert not SUPERVISOR >= TECHNICIAN
    assert not TECHNICIAN >= SUPERVISOR


def test_the_supervisor_sees_the_fault_queue_and_is_refused_the_residuals_behind_it() -> None:
    """The direction a seniority ladder always gets wrong. A supervisor outranks nobody here:
    they hold `view_faults` so the queue appears, and they do not hold `view_residuals` so the
    gauges behind it do not. Authority and records, not measurements."""
    workspace = reliability_workspace([_case()], SUPERVISOR)

    (row,) = workspace.faults
    assert row.residuals == ()
    assert row.fit_note == ""
    assert "view_residuals" in row.residuals_note


def test_the_reliability_engineer_is_refused_every_section_of_the_supervisor_queue() -> None:
    """The mirror. An engineer judging a fault does not thereby acquire the authority to
    approve work against it, and the surface says which capability is missing rather than
    which role is higher."""
    queue = supervisor_queue([_case(state="root_caused")], ENGINEER)

    assert queue.approvals == ()
    assert queue.blocked == ()
    assert queue.closures == ()
    assert {a.section for a in queue.withheld} == set(SECTIONS_OF[Surface.SUPERVISOR_QUEUE])


def test_a_withheld_section_names_the_capability_and_denies_that_it_is_a_rank() -> None:
    """A bare `False` would be the defect. The reader has to be able to act on the refusal,
    and *"ask someone more senior"* is the wrong action — the right one names a capability."""
    refused = admission(Section.RESIDUALS_BEHIND, SUPERVISOR)

    assert refused.admitted is False
    assert refused.capability is Capability.VIEW_RESIDUALS
    assert "view_residuals" in refused.reason
    assert "not a rank" in refused.reason
    assert "a supervisor is not a more capable technician" in refused.reason


def test_an_admitted_section_also_says_why_rather_than_only_saying_yes() -> None:
    """Constraint 14 applied to admission: a value or a stated reason. An audit asking *why
    was this shown* needs the same quality of answer as one asking why it was not."""
    granted = admission(Section.AWAITING_APPROVAL, SUPERVISOR)

    assert granted.admitted is True
    assert "approve_work" in granted.reason


def test_no_persona_reaches_this_module_at_all() -> None:
    """The strongest available guard against the ladder returning. A module that never sees a
    persona cannot compare two of them — `persona >= SUPERVISOR` is unwritable here, and every
    membership question is forced through `ADMITS`."""
    source = inspect.getsource(queues)

    assert "Persona" not in source
    assert "compute_scope" not in source
    assert not hasattr(queues, "Persona")


def test_every_section_has_exactly_one_admitting_capability() -> None:
    """A section missing from `ADMITS` raises rather than defaulting open, and this is the
    test that catches a new section added to the enum and forgotten in the table."""
    assert set(ADMITS) == set(Section)
    assert all(isinstance(c, Capability) for c in ADMITS.values())


def test_the_two_surfaces_share_no_section() -> None:
    """`SECTIONS_OF` is held apart from `ADMITS` so that moving a section between surfaces
    cannot silently change who may see it. Overlap would defeat that separation."""
    workspace = set(SECTIONS_OF[Surface.RELIABILITY_WORKSPACE])
    queue = set(SECTIONS_OF[Surface.SUPERVISOR_QUEUE])
    assert workspace & queue == set()
    assert workspace | queue == set(Section)


def test_every_withheld_admission_carries_its_reason_in_words() -> None:
    """An absence is not a zero and not a dash. A withheld section with an empty reason is a
    greyed-out box, and a greyed-out box still reads as a demand on whoever is standing there."""
    for refused in supervisor_queue([_case()], ENGINEER).withheld:
        assert refused.reason.strip()
        assert refused.capability.value in refused.reason


# ── `U6`: the residuals standing behind a fault ────────────────────────────────

def test_the_unfitted_sixth_model_is_named_as_an_absence_rather_than_left_out() -> None:
    """Constraint 14, and the reason omission is the failure it prevents: a list of five
    models reads as complete. Six models are designed and five are fitted."""
    rows = residuals_behind("chiller_1")

    assert len(rows) == residuals.DESIGNED_MODEL_COUNT
    absent = [r for r in rows if r.is_absent]
    assert len(absent) == 1
    assert absent[0].model_name == residuals.ABSENT_RESIDUAL_COLUMN
    assert absent[0].nrmse is None
    assert absent[0].absence.strip()


def test_the_same_model_is_eighteen_times_worse_on_one_chiller_than_the_other() -> None:
    """Models are fitted per asset, never per fleet. The current model runs at nRMSE 48.03 on
    chiller 1 and 2.65 on chiller 2, so an identical fault label on the two machines does not
    mean the same thing — which is why a residual is never rendered without its fit."""
    def current(equipment_key: str):
        return next(
            r for r in residuals_behind(equipment_key) if r.model_name == "Chiller_Current"
        )

    assert current("chiller_1").nrmse == 48.03
    assert current("chiller_2").nrmse == 2.65
    assert current("chiller_1").is_poor_fit is True
    assert current("chiller_2").is_poor_fit is False


def test_an_asset_with_no_fitted_model_gets_words_and_not_an_empty_list() -> None:
    """An empty tuple is the two-absences collapse: *no residuals exist* and *no model was
    ever fitted here* would render identically, and the second is not a clean bill."""
    rows = residuals_behind("chiller_9")

    assert len(rows) == 1
    assert rows[0].is_absent
    assert "not a zero" in rows[0].absence
    assert "not a clean bill" in rows[0].absence


def test_a_poor_fit_warns_that_the_alarm_may_be_the_model_rather_than_the_fault() -> None:
    """`F10` and `F11` are load-bearing, not hygiene. Part of a 48.03 residual is the model's
    own error, and dispatching a person on it is the cost of not saying so."""
    poor = fit_note_for("chiller_1")
    good = fit_note_for("chiller_2")

    assert "48.03" in poor
    assert "artefact" in poor
    assert "3.77" in good
    assert "artefact" not in good


def test_an_unfitted_asset_says_nothing_about_it_may_be_read_as_measured_and_checked() -> None:
    """The absence of a fit is not a good fit. Without these words a row on an unmodelled
    asset looks exactly like a row that passed."""
    note = fit_note_for("chiller_9")
    assert "No model is fitted" in note
    assert "measured-and-checked" in note


def test_a_row_knows_whether_anything_behind_it_is_an_actual_value() -> None:
    """`has_residuals` must count values, not rows — a single stated absence is one row and
    zero measurements, and counting it as evidence is how an unmodelled asset reads as
    instrumented."""
    real = reliability_workspace([_case()], ENGINEER).faults[0]
    unmodelled = reliability_workspace(
        [_case(equipment_key="chiller_9")], ENGINEER
    ).faults[0]

    assert real.has_residuals is True
    assert unmodelled.has_residuals is False
    assert unmodelled.residuals != ()


def test_the_analyst_sees_the_residuals_and_is_told_why_there_is_no_case() -> None:
    """The Analyst holds `view_residuals` and not `open_case`. Two sections of one surface
    resolving differently for one identity is what a per-section table buys over a role check."""
    (row,) = reliability_workspace([_case()], ANALYST).faults

    assert row.has_residuals is True
    assert "open_case" in row.case_note


def test_each_queued_fault_says_the_case_it_opens_is_one_per_equipment_fault_and_day() -> None:
    """Constraint 35. A single real fault spans hundreds of consecutive readings — 412 on the
    measured day — and a reader who expects a second case per rescan will chase a phantom."""
    (row,) = reliability_workspace([_case()], ENGINEER).faults

    assert row.slot_count == 412
    assert "one case per equipment, fault and day" in row.case_note


# ── `U6`: detection is not seeding ─────────────────────────────────────────────

def test_a_detected_episode_with_no_case_is_reported_rather_than_absent() -> None:
    """Constraint 21. Twenty-two detected episodes once sat outside the case queue because
    nothing called the seed, and the queue read as a clean plant."""
    orphan = "chiller_2|CONDENSER_LOW_FLOW|2026-04-15"
    workspace = reliability_workspace(
        [_case()], ENGINEER, detected_seed_keys=[_case().seed_key, orphan]
    )

    assert workspace.detected_not_queued == (orphan,)
    assert "constraint 21" in workspace.seeding_note


def test_not_checking_the_detector_is_a_different_sentence_from_checking_and_finding_none(
) -> None:
    """The two-absences collapse, at the seed. *Every episode reached the queue* and *nobody
    compared the queue to the detector* are opposite facts and both produce an empty list."""
    unchecked = reliability_workspace([_case()], ENGINEER).seeding_note
    checked = reliability_workspace(
        [_case()], ENGINEER, detected_seed_keys=[_case().seed_key]
    ).seeding_note

    assert unchecked != checked
    assert "has not been checked" in unchecked
    assert "Checked against the detector" in checked


def test_an_empty_queue_a_reader_may_see_is_not_the_same_as_a_queue_withheld() -> None:
    """**Defect found and fixed while writing this test.** `is_empty_queue` returned `True`
    for a reader who was never admitted to the fault queue, so *nothing to work* and *you may
    not look* rendered identically — an empty queue reading as a clean plant, one field along
    from the seeding note that exists to prevent exactly that."""
    empty = reliability_workspace([], ENGINEER)
    withheld = reliability_workspace([], NOTHING)

    assert empty.is_empty_queue is True
    assert withheld.is_empty_queue is False
    assert "not an empty queue" in withheld.seeding_note
    assert withheld.detected_not_queued == ()


def test_a_withheld_fault_queue_never_claims_the_detector_was_checked() -> None:
    """A detection list handed to an identity that cannot see the queue must not produce a
    reassuring *all episodes have a case*, because nothing was compared."""
    workspace = reliability_workspace(
        [], NOTHING, detected_seed_keys=["chiller_1|HIGH_HEAD_AMBIGUOUS|2026-04-15"]
    )

    assert "nothing was checked against the detector" in workspace.seeding_note
    assert "All 1 detected" not in workspace.seeding_note


# ── ordering claims nothing ────────────────────────────────────────────────────

def test_the_queue_is_ordered_by_age_and_never_by_how_big_the_residual_looked() -> None:
    """Inherited constraint 3: non-faults were measured to deviate *more* than faults. The
    412-slot day sorting above a 3-slot one would be a ranking the data cannot support, and a
    reader works the top of a queue whether or not anyone called it a ranking."""
    big_and_recent = _case(seed_key="recent", day=LATER, slot_count=412)
    small_and_old = _case(seed_key="old", day=DAY, slot_count=3)

    workspace = reliability_workspace([big_and_recent, small_and_old], ENGINEER)
    assert [f.seed_key for f in workspace.faults] == ["old", "recent"]


def test_the_order_states_in_words_what_it_deliberately_does_not_claim() -> None:
    """`Q49` agrees severity for one fault class of nine and three of `W4`'s four priority
    inputs do not exist. An order presented without that sentence reads as a priority."""
    assert "not a ranking" in QUEUE_ORDER_REASON
    assert "Q49" in QUEUE_ORDER_REASON
    assert "Q51" in QUEUE_ORDER_REASON
    assert "constraint 3" in QUEUE_ORDER_REASON


def test_both_surfaces_carry_the_same_order_reason() -> None:
    """Two queues ordered the same way and explained differently is how one of the two
    explanations quietly stops being true."""
    assert reliability_workspace([], ENGINEER).order_reason == QUEUE_ORDER_REASON
    assert supervisor_queue([], SUPERVISOR).order_reason == QUEUE_ORDER_REASON


def test_the_measured_thirty_nine_episodes_arrive_as_thirty_nine_rows_in_age_order() -> None:
    """39 episodes over 12 equipment-days is the real scale of the measured queue. Grouping is
    display-level only (constraint 12), so nothing here may collapse them on the way in."""
    cases = [
        _case(
            seed_key=f"chiller_1|LABEL_{n}|{n}",
            fault_label=f"LABEL_{n}",
            day=date(2026, 4, 15 + n % 12),
        )
        for n in range(39)
    ]
    workspace = reliability_workspace(cases, ENGINEER)

    assert len(workspace.faults) == 39
    assert len({f.day for f in workspace.faults}) == 12
    days = [f.day for f in workspace.faults]
    assert days == sorted(days)


# ── `U7`: approvals ────────────────────────────────────────────────────────────

def test_an_escalated_case_asks_a_question_and_never_hands_over_a_measurement() -> None:
    """`RC15`, and constraint 25 arriving by the other door. Escalating up is about authority
    or judgement; putting a supervisor at a gauge is the filter-drier incident restated."""
    (row,) = supervisor_queue([_case(state="escalated")], SUPERVISOR).approvals

    assert row.task_is_a_question is True
    assert "the task is the question, not a measurement" in row.asks.lower()
    assert "unassigned" in row.asks


def test_approving_work_against_an_established_cause_is_not_a_question() -> None:
    """The two approval routes are not interchangeable — constraint 9. One asks a supervisor
    to decide, the other asks them to release a person to site."""
    (row,) = supervisor_queue([_case(state="root_caused")], SUPERVISOR).approvals

    assert row.task_is_a_question is False
    assert "dispatches a person" in row.asks


def test_an_approval_carries_the_whole_ruling_rather_than_a_yes_or_a_no() -> None:
    """`NEEDS_APPROVAL` is not a refusal — somebody down the corridor can sign — so flattening
    `G3`'s ruling to a boolean would tell a reader to give up."""
    (row,) = supervisor_queue([_case(state="root_caused")], SUPERVISOR).approvals

    assert isinstance(row.ruling, authority.Ruling)
    assert row.ruling.decision is authority.Decision.ALLOWED
    assert row.ruling.required_capability == "approve_work"
    assert row.ruling.is_refusal is False
    assert row.may_be_approved_now is True


def test_a_case_nobody_is_waiting_on_manufactures_no_work_for_the_supervisor() -> None:
    """The supervisor already receives the library's preventive 38 of 124 items. Inventing an
    approval for a state that is not waiting on one would add to the one role that had no
    queue until this surface existed."""
    quiet = [
        _case(seed_key="a", state="detected"),
        _case(seed_key="b", state="deferred"),
        _case(seed_key="c", state="closed"),
    ]
    queue = supervisor_queue(quiet, SUPERVISOR)

    assert queue.approvals == ()
    assert queue.blocked == ()
    assert queue.closures == ()


# ── `U7`: blocked, and the block nobody evaluated ──────────────────────────────

def test_a_case_nobody_evaluated_is_reported_as_unknown_rather_than_clear() -> None:
    """Constraint 8 and honesty rule 6. Six "N/A" presses once opened a blocking gate with
    zero evidence behind it, and *nobody checked* must never render as *nothing is blocking*."""
    (row,) = supervisor_queue([_case(state="awaiting_findings")], SUPERVISOR).blocked

    assert row.kind is Blocked.NOT_EVALUATED
    assert "not a clear pass" in row.reason


def test_an_evaluated_block_carries_rc5s_own_words_rather_than_a_second_opinion() -> None:
    """Recomputing the checklist here would be a second answer to one question, and two
    answers is how a gate quietly starts disagreeing with itself."""
    words = "the suction pressure item is blocking and has no measured answer"
    case = _case(state="awaiting_findings")
    (row,) = supervisor_queue(
        [case], SUPERVISOR, blocking_reasons={case.seed_key: words}
    ).blocked

    assert row.kind is Blocked.UNSETTLED_BLOCKING_CHECK
    assert row.reason == words


def test_the_two_kinds_of_block_never_share_a_kind_or_a_reason() -> None:
    """*A check with no measured answer* and *no check was ever run* are different problems
    needing different action. Collapsed, the second inherits the first's air of having been
    looked at."""
    evaluated = _case(seed_key="a", state="awaiting_findings")
    unevaluated = _case(seed_key="b", state="awaiting_findings")
    rows = supervisor_queue(
        [evaluated, unevaluated],
        SUPERVISOR,
        blocking_reasons={evaluated.seed_key: "oil pressure unmeasured"},
    ).blocked

    kinds = {r.seed_key: r.kind for r in rows}
    assert kinds["a"] is Blocked.UNSETTLED_BLOCKING_CHECK
    assert kinds["b"] is Blocked.NOT_EVALUATED
    assert len({r.reason for r in rows}) == 2


# ── `U7`: closures verification has not cleared ────────────────────────────────

def test_work_done_with_nothing_checked_is_not_a_check_that_could_not_decide() -> None:
    """`W9`: a case cannot close unproven. *Nobody ran the check* and *the check ran and could
    not decide* are two absences, and only the first has an obvious next action."""
    nothing_run = _case(seed_key="a", state="actioned")
    undecided = _case(seed_key="b", state="actioned")
    rows = supervisor_queue(
        [nothing_run, undecided],
        SUPERVISOR,
        verifications={undecided.seed_key: _verification(Outcome.UNKNOWN)},
    ).closures

    blocks = {r.seed_key: r.block for r in rows}
    assert blocks["a"] is ClosureBlock.NOT_VERIFIED
    assert blocks["b"] is ClosureBlock.VERIFIED_UNKNOWN
    assert len({r.reason for r in rows}) == 2


def test_a_failed_check_says_what_was_measured_is_still_not_fixed() -> None:
    """`UNKNOWN` and `FAIL` are both permitted outcomes and only one of them is evidence.
    Treating no evidence of a problem as evidence of no problem is the shortcut `V1` refuses."""
    case = _case(state="actioned")
    (row,) = supervisor_queue(
        [case], SUPERVISOR, verifications={case.seed_key: _verification(Outcome.FAIL)}
    ).closures

    assert row.block is ClosureBlock.VERIFIED_FAIL
    assert "still not fixed" in row.reason
    assert row.outcome.startswith("FAIL")


def test_a_verification_that_passed_is_never_reported_as_one_that_could_not_decide() -> None:
    """**Defect found and fixed while writing this test.** A `PASS` fell through to the `else`
    arm and rendered as `VERIFIED_UNKNOWN` — the row read *"the check ran and could not
    decide"* over an outcome field that said `PASS`, inside a section headed *closures
    verification has not cleared*. A proven repair was shown to a supervisor as undecided, and
    the row contradicted itself in a way no reader could catch. A cleared closure is not an
    uncleared one, so it leaves this section entirely."""
    passed = _case(seed_key="a", state="actioned")
    failed = _case(seed_key="b", state="actioned")
    rows = supervisor_queue(
        [passed, failed],
        SUPERVISOR,
        verifications={
            passed.seed_key: _verification(Outcome.PASS, "the residual returned to band"),
            failed.seed_key: _verification(Outcome.FAIL),
        },
    ).closures

    assert [r.seed_key for r in rows] == ["b"]
    assert all(r.block is not ClosureBlock.VERIFIED_UNKNOWN for r in rows)


def test_a_cleared_closure_reaching_the_row_builder_raises_rather_than_rendering() -> None:
    """A code path with no honest row must fail loudly. The alternative is what it did before:
    print a sentence that contradicts the outcome beside it."""
    case = _case(state="actioned")
    with pytest.raises(ValueError, match="cleared closure"):
        queues._closure(case, {case.seed_key: _verification(Outcome.PASS)})


def test_a_supervisor_holding_every_capability_cannot_approve_past_an_unproven_closure(
) -> None:
    """Closing is gated by evidence, not by authority. A `Ruling` on this row would invite
    exactly the sign-off `W9` exists to refuse — and holding every capability in the system
    must not change the answer, or the gate is a seniority check after all."""
    case = _case(state="actioned")
    (row,) = supervisor_queue(
        [case], EVERYTHING, verifications={case.seed_key: _verification(Outcome.FAIL)}
    ).closures

    assert "ruling" not in {f.name for f in dataclasses.fields(ClosureRow)}
    assert not hasattr(row, "may_be_approved_now")
    assert row.block is ClosureBlock.VERIFIED_FAIL


def test_the_closure_section_needs_close_work_and_not_approve_work() -> None:
    """Two capabilities, deliberately. If approving implied closing, one signature would both
    release the work and declare it proven."""
    case = _case(state="actioned")
    only_approve = frozenset({Capability.VIEW_FAULTS, Capability.APPROVE_WORK})

    assert supervisor_queue([case], only_approve).closures == ()
    assert supervisor_queue([case], SUPERVISOR).closures != ()


# ── `RC9`: two kinds of stale, permanently two ─────────────────────────────────

def _cleared_case() -> _Case:
    return _case(
        seed_key="cleared",
        state="stale",
        stale_at=datetime(2026, 6, 1, 12, 0),
        stale_reason="the condition that opened this case is no longer detected.",
        condition_cleared=True,
    )


def _untouched_case() -> _Case:
    return _case(
        seed_key="untouched",
        state="stale",
        stale_at=datetime(2026, 6, 1, 12, 0),
        stale_reason="nobody has touched this case since 2026-04-15. It is still open.",
        condition_cleared=False,
    )


def test_a_fixed_machine_and_a_forgotten_one_land_in_different_tuples() -> None:
    """The `RC9` incident: four open cases described transmitters repaired weeks earlier while
    twenty had been waiting since April. One `stale` flag makes those look identical."""
    queue = supervisor_queue([_cleared_case(), _untouched_case()], SUPERVISOR)

    assert [r.seed_key for r in queue.condition_cleared] == ["cleared"]
    assert [r.seed_key for r in queue.untouched] == ["untouched"]
    assert queue.condition_cleared[0].kind is AgeingKind.CONDITION_CLEARED
    assert queue.untouched[0].kind is AgeingKind.UNTOUCHED


def test_the_two_kinds_call_for_different_actions() -> None:
    """Separate fields would be cosmetic if both rows told the reader to do the same thing.
    One needs somebody to say whether the plant fixed itself; the other needs somebody at all."""
    queue = supervisor_queue([_cleared_case(), _untouched_case()], SUPERVISOR)
    cleared = queue.condition_cleared[0].action
    untouched = queue.untouched[0].action

    assert cleared != untouched
    assert "do not close it on the absence" in cleared
    assert "twenty cases once waited since April" in untouched
    assert set(ACTION_FOR) == {k.value for k in AgeingKind}


def test_a_cleared_condition_is_never_read_as_proof_the_repair_worked() -> None:
    """Constraint 7: `NULL` means not diagnosed, never healthy. A condition that stopped being
    detected is evidence about the plant, and closing on it is closing on an absence."""
    assert "not proof the repair worked" in CLEARED_NEEDS_A_PERSON
    assert "not diagnosed, never healthy" in CLEARED_NEEDS_A_PERSON
    assert "Confirm it or reopen it" in CLEARED_NEEDS_A_PERSON


def test_no_case_is_counted_under_both_kinds_of_stale() -> None:
    """A cleared case also carries a `stale_at`, so a careless filter would list it twice and
    double the apparent size of the backlog."""
    both = _case(
        seed_key="both",
        state="stale",
        stale_at=datetime(2026, 6, 1, 12, 0),
        stale_reason="the condition cleared",
        condition_cleared=True,
    )
    queue = supervisor_queue([both], SUPERVISOR)

    assert [r.seed_key for r in queue.condition_cleared] == ["both"]
    assert queue.untouched == ()


def test_the_rendered_ageing_never_collapses_into_one_number() -> None:
    """A single total is one edit away from a screen on which a fixed machine and a forgotten
    one look identical — which is the whole failure `RC9` exists for."""
    text = supervisor_queue([_cleared_case(), _untouched_case()], SUPERVISOR).render_ageing()

    assert "1 case(s) where the condition cleared" in text
    assert "1 case(s) nobody has touched" in text
    assert "2 case" not in text


def test_the_supervisor_queue_holds_no_field_that_sums_the_two_kinds() -> None:
    """Kept as separate tuples so that collapsing them requires writing new code rather than
    reading a field."""
    names = {f.name for f in dataclasses.fields(SupervisorQueue)}

    assert "condition_cleared" in names
    assert "untouched" in names
    assert not any(n in names for n in ("stale", "stale_count", "aged", "ageing"))


def test_the_stale_reason_is_rc9s_own_words_off_the_row() -> None:
    """`Q56` owns how long a case may sit and `case_store` applies it. Recomputing the verdict
    here is how two parts of one product start disagreeing about which cases are old."""
    recorded = "nobody has touched this case since 2026-04-15. It is still open."
    queue = supervisor_queue([_untouched_case()], SUPERVISOR)

    assert queue.untouched[0].reason == recorded


def test_a_stale_case_with_no_recorded_reason_still_gets_words_rather_than_a_blank() -> None:
    """A stale row with an empty reason is a row nobody can act on — the dash again."""
    queue = supervisor_queue(
        [_case(seed_key="x", state="stale", stale_at=datetime(2026, 6, 1), stale_reason="")],
        SUPERVISOR,
    )

    assert queue.untouched[0].reason.strip()


def test_a_queue_that_could_not_look_at_ageing_does_not_report_that_nothing_aged() -> None:
    """**Defect found and fixed while writing this test.** `render_ageing()` returned
    *"no case has aged"* to an identity that was never admitted to the section, so *we looked
    and nothing has aged* and *nobody looked* produced the same sentence. That is the twenty-two
    episodes again, one layer up: the surface reads calm because nothing was examined."""
    blind = supervisor_queue([_cleared_case(), _untouched_case()], ENGINEER)
    looked = supervisor_queue([], SUPERVISOR)

    assert blind.ageing_was_examined is False
    assert "not checked" in blind.render_ageing()
    assert "not a statement that nothing has aged" in blind.render_ageing()

    assert looked.ageing_was_examined is True
    assert looked.render_ageing() == "no case has aged"


# ── a row the state machine cannot read ────────────────────────────────────────

def test_a_state_that_does_not_parse_is_listed_rather_than_dropped() -> None:
    """A case that vanishes because a string did not parse is a queue that looks calm and is
    not — the twenty-two episodes, arriving through a third door."""
    workspace = reliability_workspace([_case(state="in_progress")], ENGINEER)

    assert workspace.faults == ()
    (bad,) = workspace.unreadable
    assert bad.state == "in_progress"
    assert "not a state the case machine knows" in bad.reason


def test_one_unreadable_row_does_not_take_the_rest_of_the_queue_down() -> None:
    """A crash on one bad string costs a reader every good row beside it, which is a worse
    failure than the row itself."""
    workspace = reliability_workspace(
        [_case(seed_key="bad", state="in_progress"), _case(seed_key="good")], ENGINEER
    )

    assert [f.seed_key for f in workspace.faults] == ["good"]
    assert len(workspace.unreadable) == 1


def test_both_surfaces_report_an_unreadable_row() -> None:
    """`U7` reads the same table. A row that is invisible on one surface and listed on the
    other means the two disagree about how many cases exist."""
    bad = [_case(state="in_progress")]

    assert len(reliability_workspace(bad, ENGINEER).unreadable) == 1
    assert len(supervisor_queue(bad, SUPERVISOR).unreadable) == 1
