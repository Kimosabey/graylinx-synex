"""`C8` the confirm step · `G5` the key that makes a retry harmless.

**The promise being tested is narrow and easy to break.** `C8` is *"shows the action before
saving"*. That is only worth anything if the thing shown and the thing saved are the same
thing — a confirm step that re-derives the draft, rounds a figure, or drops a warning on the
way to storage has demonstrated a different action from the one it performed.

So the load-bearing test here is `test_the_draft_shown_is_exactly_what_gets_stored`. The rest
guard the two ways it degrades: the rendering quietly changing, and something reaching the
table without the act.

The store itself is exercised against a real Postgres in `tests/integration/` — `G5` is a
unique index, and asserting an index against a fake would test the fake.
"""
from __future__ import annotations

import dataclasses
import pathlib
from datetime import date, datetime

import pytest

from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_band_available, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.db.work_order_store import ConfirmedWorkOrder, UnconfirmedWriteError
from app.domain.authority import Decision, Risk
from app.domain.idempotency import UNLABELLED, WorkOrderKind, work_order_key
from app.services import work_orders
from app.services.approvals import GrantDecision, grant
from app.services.control_plane import Persona, compute_scope
from app.services.evidence import build_pack, window_for
from app.services.work_orders import (
    WorkOrderState,
    confirm,
    draft_from_pack,
    identity_for,
)

MEASURED_END = datetime(2026, 6, 23, 11, 50)
DAY = date(2026, 4, 15)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)

ENGINEER = compute_scope(Persona.RELIABILITY_ENGINEER)
SUPERVISOR = compute_scope(Persona.SUPERVISOR)
TECHNICIAN = compute_scope(Persona.TECHNICIAN)


def _pack(label: str = "CONDENSER_LOW_FLOW", day: date = DAY, slots: int = 3):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = tuple(
        ResidualRow("chiller_1", datetime(day.year, day.month, day.day, 9, i), label, values)
        for i in range(slots)
    )
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=GateOutcome(
            (check_running({"a": 141.0}), check_band_available(BAND, "Chiller 1"))
        ),
        window=window_for(day, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=day,
        other_labels_same_day=("HIGH_HEAD_AMBIGUOUS",),
    )


def _draft(**kwargs):
    return draft_from_pack(_pack(**kwargs))


# ── C8: the before must look identical to what gets saved ──────────────────────

def test_the_draft_shown_is_exactly_what_gets_stored() -> None:
    """The whole of `C8`. Not *equivalent to*, not *derived from* — the identical dict.

    A confirm step that rebuilt the draft would be free to round a figure or drop a warning
    between the screen and the table, and nobody would ever see the difference, because the
    screen is gone by the time the row exists.
    """
    draft = _draft()
    shown = draft.as_dict()

    outcome = confirm(draft, SUPERVISOR)
    assert outcome.record is not None
    assert outcome.record.evidence["shown_as"] == shown


def test_confirming_does_not_mutate_the_draft() -> None:
    """The draft is rendered before the act and may be rendered again after it — an interface
    that redraws must not show something different from what was confirmed."""
    draft = _draft()
    before = draft.as_dict()
    confirm(draft, SUPERVISOR)
    assert draft.as_dict() == before
    assert draft.is_draft is True


def test_the_stored_copy_of_the_rendering_keeps_saying_it_was_a_draft() -> None:
    """`is_draft` stays `True` inside `shown_as` because that blob is a record of *what
    somebody was looking at*, not a description of the row. The row's own state is what says
    it is no longer a draft, and conflating the two would make the record of the rendering
    disagree with the rendering."""
    record = confirm(_draft(), SUPERVISOR).record
    assert record is not None
    assert record.evidence["shown_as"]["is_draft"] is True
    assert record.state == WorkOrderState.CONFIRMED.value
    assert WorkOrderState.DRAFT.value == "draft"


def test_the_stored_row_carries_the_evidence_the_draft_carried() -> None:
    """`W3`. Residuals, gates and signal provenance travel with the job rather than being
    looked up later by whoever opens it."""
    record = confirm(_draft(), SUPERVISOR).record
    assert record is not None
    kinds = {line["kind"] for line in record.evidence["shown_as"]["evidence"]}
    assert {"residual", "gate", "signal"} <= kinds
    assert all(line["source"] for line in record.evidence["shown_as"]["evidence"])


def test_the_stored_row_says_whether_its_priority_is_finished() -> None:
    """`W4`/`Q51`. Three of the four inputs do not exist in this snapshot, so a priority
    stored as though it were complete would be a severity wearing a rank — and a planner
    schedules against a rank."""
    record = confirm(_draft(), SUPERVISOR).record
    assert record is not None
    assert record.priority == "P0"
    assert record.priority_is_complete is False


def test_a_draft_on_its_own_reaches_nothing() -> None:
    """`draft_from_pack` is the *showing*. If it could write, the confirm step would be
    decorative — so it is asserted to have no way to reach the store at all."""
    draft = _draft()
    assert draft.is_draft is True

    source = pathlib.Path(work_orders.__file__).read_text(encoding="utf-8")
    body = source.split("def draft_from_pack")[1].split("# ── C8")[0]
    for banned in ("WorkOrderStore", "session", "commit", "add("):
        assert banned not in body, f"draft_from_pack reaches {banned}"


# ── nothing persists that nobody confirmed ─────────────────────────────────────

def test_a_record_cannot_exist_without_the_act_that_created_it() -> None:
    """The rule stated as a constructor rather than as a convention, so the failure lands on
    the line that forgot the confirmation instead of three layers away in a transaction."""
    with pytest.raises(UnconfirmedWriteError) as caught:
        ConfirmedWorkOrder(
            idempotency_key="abc", equipment_key="chiller_1", confirmed_by="  "
        )
    assert "makes the showing decorative" in str(caught.value)


def test_a_record_cannot_exist_without_the_key_that_deduplicates_it() -> None:
    """An empty key would let the second retry through, because a unique index on an empty
    string is only unique once."""
    with pytest.raises(UnconfirmedWriteError):
        ConfirmedWorkOrder(
            idempotency_key="", equipment_key="chiller_1", confirmed_by="supervisor"
        )


def test_the_record_records_who_performed_the_act() -> None:
    record = confirm(_draft(), SUPERVISOR).record
    assert record is not None
    assert record.confirmed_by == Persona.SUPERVISOR.value
    assert record.evidence["identity_kind"] == "demonstration_persona"


# ── G5: the key ────────────────────────────────────────────────────────────────

def test_the_same_draft_always_produces_the_same_key() -> None:
    """`G5`. Two presses on a flaky connection are the same request arriving twice, and the
    key is what turns the second one into a lookup."""
    assert identity_for(_draft()).key == identity_for(_draft()).key


def test_the_key_derivation_is_not_repeated_in_this_layer() -> None:
    """CLAUDE.md §2.8, one source of truth per fact. `app/domain/idempotency.py` owns the
    derivation and the two things this layer would have got wrong alone: `kind` belongs in the
    key, and the fields need a separator no value can contain.

    A second `hashlib` here would be a key that agrees today and drifts at the first edit to
    either copy — and the symptom of drift is a duplicate dispatch, not a test failure.
    """
    source = pathlib.Path(work_orders.__file__).read_text(encoding="utf-8")
    assert "hashlib" not in source
    assert identity_for(_draft()).key == work_order_key(identity_for(_draft()))


def test_who_confirmed_it_and_when_are_deliberately_not_in_the_key() -> None:
    """Two supervisors confirming the same draft is one visit to one machine. A key carrying
    the moment of the press would make two clicks a second apart into two jobs, which is the
    failure `G5` exists for."""
    first = confirm(_draft(), SUPERVISOR).record
    second = confirm(_draft(), SUPERVISOR).record
    assert first is not None and second is not None
    assert first.idempotency_key == second.idempotency_key


def test_the_same_fault_on_a_different_day_is_a_different_job() -> None:
    """Constraint 35's identity: one per equipment, fault and day. Collapsing days would
    make a fault that returns in June invisible behind April's job."""
    assert identity_for(_draft()).key != identity_for(_draft(day=date(2026, 6, 15))).key


def test_a_different_fault_on_the_same_day_is_a_different_job() -> None:
    """Constraint 28: a fouled condenser on a machine that is also low on flow is two real
    causes, and collapsing to the first is how the second gets missed."""
    low_flow = identity_for(_draft()).key
    ambiguous = identity_for(_draft(label="HIGH_HEAD_AMBIGUOUS")).key
    assert low_flow != ambiguous


def test_an_inspection_and_a_corrective_job_for_one_fault_are_two_jobs() -> None:
    """`RC7`. An inspection work order carries the open checks as its task list; a corrective
    one carries the repair. A key without `kind` would refuse the second as a duplicate, and a
    suppressed job leaves no trace anywhere."""
    draft = _draft()
    corrective = identity_for(draft, WorkOrderKind.CORRECTIVE).key
    inspection = identity_for(draft, WorkOrderKind.INSPECTION).key
    assert corrective != inspection

    stored = confirm(draft, SUPERVISOR, kind=WorkOrderKind.INSPECTION).record
    assert stored is not None
    assert stored.kind == "inspection"
    assert stored.idempotency_key == inspection


def test_the_key_fits_the_column_that_enforces_it() -> None:
    """`idempotency_key` is `String(64)`. A key wider than the column would be truncated by
    the database, a truncated key collides, a collision reads as a duplicate, and a duplicate
    is never raised."""
    key = identity_for(_draft()).key
    assert len(key) <= 64
    assert key == key.lower()


def test_what_the_key_was_derived_from_travels_with_the_row() -> None:
    """A hash nobody can invert is a hash nobody can check, so the basis is stored beside it
    and the derivation can be redone by hand."""
    record = confirm(_draft(), SUPERVISOR).record
    assert record is not None
    assert record.evidence["key_basis"] == [
        "corrective",
        "chiller_1",
        "CONDENSER_LOW_FLOW",
        "2026-04-15",
    ]
    assert "chiller_1" in record.evidence["identifies"]


def test_a_draft_with_no_fault_label_is_translated_deliberately_rather_than_defaulted() -> None:
    """`WorkOrderIdentity` refuses an empty label rather than defaulting one, because an empty
    label collapses every unlabelled finding on a machine-day into one job. The draft's own
    placeholder is translated to the declared sentinel here, so the merge is a decision with
    `Q90` against it rather than an accident."""
    draft = dataclasses.replace(_draft(), fault_label=work_orders.UNLABELLED_DRAFT_TITLE)
    assert identity_for(draft).fault_label == UNLABELLED


# ── the act asks G3 first ──────────────────────────────────────────────────────

def test_raising_a_work_order_is_high_risk_and_does_not_reverse_cleanly() -> None:
    """It *commits Synex to an action in the world: dispatches a person* — `Risk.HIGH` by
    that enum's own definition. Deleting the row is not what has to be undone: a technician
    already at the plant cannot be un-dispatched."""
    action = work_orders.raise_action(_draft())
    assert action.risk is Risk.HIGH
    assert action.reverses_cleanly is False
    assert action.target == "chiller_1"


def test_an_identity_without_authority_gets_an_approval_request_rather_than_a_row() -> None:
    """`C8` and `C9` meet here. A Reliability Engineer opens cases; they do not approve work.
    The draft stands and the request goes to a capability."""
    outcome = confirm(_draft(), ENGINEER)

    assert outcome.will_persist is False
    assert outcome.record is None
    assert outcome.needs_approval is True
    assert outcome.approval is not None
    assert outcome.approval.addressed_to == "approve_work"
    assert outcome.approval.is_unassigned is True


def test_the_approval_request_carries_the_evidence_the_draft_was_showing() -> None:
    """Whoever approves is being asked to decide on what the requester saw, not on a title."""
    draft = _draft()
    outcome = confirm(draft, ENGINEER)
    assert outcome.approval is not None
    assert len(outcome.approval.evidence) == len(draft.evidence)


def test_the_person_who_asked_for_the_approval_cannot_grant_it() -> None:
    """`C8` into `C9` into the self-approval rule, end to end and across two modules — the
    place a rule holding in each half separately still fails in the join."""
    outcome = confirm(_draft(), SUPERVISOR)
    assert outcome.will_persist, "a supervisor holds approve_work, so this is the row path"

    from_engineer = confirm(_draft(), ENGINEER)
    assert from_engineer.approval is not None
    assert grant(from_engineer.approval, ENGINEER).decision is (
        GrantDecision.REFUSED_SELF_APPROVAL
    )
    assert grant(from_engineer.approval, SUPERVISOR).decision is GrantDecision.GRANTED


def test_a_technician_confirming_gets_the_same_treatment_as_an_engineer() -> None:
    """Constraint 25: not a ladder. Neither holds `approve_work`, and neither is closer to
    holding it than the other."""
    outcome = confirm(_draft(), TECHNICIAN)
    assert outcome.record is None
    assert outcome.ruling.decision is Decision.NEEDS_APPROVAL


def test_the_outcome_is_a_record_or_an_approval_and_never_both_and_never_neither() -> None:
    """Constraint 14's shape, applied to an act rather than a figure: a value or a stated
    absence. An outcome carrying both would let a caller store the row *and* raise the
    request; one carrying neither is a confirm that silently did nothing."""
    for scope in (SUPERVISOR, ENGINEER, TECHNICIAN):
        outcome = confirm(_draft(), scope)
        assert (outcome.record is None) != (outcome.approval is None)
        assert outcome.reason, "an outcome without its reason is a shrug"


def test_every_confirm_outcome_says_what_it_did_in_words() -> None:
    stored = confirm(_draft(), SUPERVISOR)
    assert "Supervisor confirmed a corrective work order for chiller_1" in stored.reason
    assert "returns that row rather than raising a second job" in stored.reason

    refused = confirm(_draft(), ENGINEER)
    assert "Nothing was stored" in refused.reason
    assert "approve_work" in refused.reason


def test_the_confirm_outcome_serialises_without_losing_the_reason() -> None:
    """The interface renders this. A dict that dropped the reason would put a bare refusal on
    a screen, and a bare refusal reads as a failure."""
    payload = confirm(_draft(), ENGINEER).as_dict()
    assert payload["will_persist"] is False
    assert payload["needs_approval"] is True
    assert payload["approval"]["unassigned_note"]
    assert payload["ruling"]["reason"]
    assert payload["idempotency_key"] == "", "no key is issued for a row that is not stored"


def test_confirm_is_the_only_thing_in_this_module_that_builds_a_stored_record() -> None:
    """`C8`: a draft becomes a row only on an explicit act. If a second constructor appears,
    the act stops being the only route and nobody would notice until a row had no confirmer.
    """
    source = pathlib.Path(work_orders.__file__).read_text(encoding="utf-8")
    assert source.count("ConfirmedWorkOrder(") == 1


def test_the_record_names_every_field_the_row_needs() -> None:
    """A field added to the record and forgotten in the mapping stores a default silently —
    `case_id` defaulting to `None` would detach every job from its case."""
    names = {f.name for f in dataclasses.fields(ConfirmedWorkOrder)}
    assert names == {
        "idempotency_key",
        "equipment_key",
        "confirmed_by",
        "evidence",
        "kind",
        "state",
        "priority",
        "priority_is_complete",
        "case_id",
    }


def test_a_job_raised_inside_a_case_keeps_the_case_it_came_from() -> None:
    record = confirm(_draft(), SUPERVISOR, case_id=7).record
    assert record is not None
    assert record.case_id == 7
