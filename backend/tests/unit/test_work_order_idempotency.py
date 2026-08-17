"""`G5` at the work-order boundary — *"a retry can never create a second work order"*.

The register's sentence is about work orders, and until this module the derivation existed
only for tool calls. These tests hold two things in place: a retry of the same job keys
identically whatever else moved, and two **different** jobs never collapse into one — because
a suppressed duplicate leaves no trace anywhere and nobody goes.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.domain.escalation import Artefact
from app.domain.idempotency import (
    EXCLUDED_FROM_THE_KEY,
    KEY_INPUTS,
    KEY_LENGTH,
    KIND_FOR_ARTEFACT,
    UNLABELLED,
    WorkOrderIdentity,
    WorkOrderKind,
    kind_for_artefact,
    same_job,
    work_order_key,
)

DAY = date(2026, 4, 15)

LOW_FLOW = WorkOrderIdentity(
    equipment_key="chiller_1",
    fault_label="CONDENSER_LOW_FLOW",
    day=DAY,
    kind=WorkOrderKind.CORRECTIVE,
)


# ── the retry, which is the whole feature ──────────────────────────────────────

def test_the_same_job_described_twice_produces_the_same_key() -> None:
    """The headline. Two presses a second apart, or two surfaces reaching the same case, are
    one job — and the key is what makes that true of the mechanism rather than of everybody's
    care."""
    again = WorkOrderIdentity(
        equipment_key="chiller_1", fault_label="CONDENSER_LOW_FLOW", day=DAY
    )
    assert again.key == LOW_FLOW.key
    matched, reason = same_job(LOW_FLOW, again)
    assert matched
    assert "already at" in reason


def test_the_key_is_independent_of_everything_that_moves_between_attempts() -> None:
    """`W4`'s priority has three of four inputs missing (`Q51`) and the drafted title is
    written by the language model, so both can legitimately differ between two attempts at one
    job. Neither is in the basis, and the basis is all that is hashed."""
    assert LOW_FLOW.basis == (
        "corrective",
        "chiller_1",
        "CONDENSER_LOW_FLOW",
        "2026-04-15",
    )
    assert len(KEY_INPUTS) == len(LOW_FLOW.basis), "every hashed field has a recorded reason"


def test_every_excluded_input_says_what_including_it_would_do() -> None:
    """An exclusion nobody wrote down is one that gets added back by whoever next needs the key
    to be more specific — and each addition turns a retry into a new job with nothing failing.
    """
    assert EXCLUDED_FROM_THE_KEY, "the exclusions are the load-bearing half"
    for excluded in EXCLUDED_FROM_THE_KEY:
        assert excluded.field.strip()
        assert len(excluded.would_cause) > 40, f"{excluded.field} does not say what it costs"


# ── the direction this module refuses to fail in ───────────────────────────────

def test_an_inspection_and_an_authorisation_for_one_case_are_two_jobs() -> None:
    """`RC7`. One asks a technician for a measurement; the other asks a supervisor a question,
    and lands unassigned. A key without `kind` would refuse the second as a duplicate — so
    nobody would be asked the question, and nothing anywhere would record that."""
    inspection = WorkOrderIdentity(
        equipment_key="chiller_1",
        fault_label="CONDENSER_LOW_FLOW",
        day=DAY,
        kind=WorkOrderKind.INSPECTION,
    )
    authorisation = WorkOrderIdentity(
        equipment_key="chiller_1",
        fault_label="CONDENSER_LOW_FLOW",
        day=DAY,
        kind=WorkOrderKind.AUTHORISATION,
    )
    assert inspection.key != authorisation.key
    matched, reason = same_job(inspection, authorisation)
    assert not matched
    assert "kind" in reason
    assert "nobody goes" in reason


def test_five_labels_on_one_machine_on_one_day_are_five_jobs() -> None:
    """On 2026-04-15 chiller 1 carried five labels at once. Inherited constraint 28: a fouled
    condenser on a machine that is *also* low on flow is two real causes, and collapsing to the
    first is how the second gets missed."""
    labels = (
        "CONDENSER_LOW_FLOW",
        "HIGH_HEAD_AMBIGUOUS",
        "POWER_HIGH_UNEXPLAINED",
        "COMPRESSOR_INEFFICIENCY",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
    )
    keys = {
        WorkOrderIdentity(equipment_key="chiller_1", fault_label=label, day=DAY).key
        for label in labels
    }
    assert len(keys) == 5


def test_two_machines_with_the_same_fault_on_the_same_day_are_two_jobs() -> None:
    """Models are fitted per asset, and so are visits. Two identical chillers on one site do
    not share a repair any more than they share a band."""
    other = WorkOrderIdentity(
        equipment_key="chiller_2", fault_label="CONDENSER_LOW_FLOW", day=DAY
    )
    assert other.key != LOW_FLOW.key


def test_no_pair_of_fields_can_be_rearranged_into_the_same_key() -> None:
    """The null separator, tested rather than trusted. Joining with nothing would let an
    equipment key ending in a fragment of a label key identically to a shorter pair — two
    different jobs sharing a row, which is the failure direction that leaves no trace."""
    left = WorkOrderIdentity(equipment_key="chiller_1x", fault_label="HIGH", day=DAY)
    right = WorkOrderIdentity(equipment_key="chiller_1", fault_label="xHIGH", day=DAY)
    assert left.key != right.key


# ── refusals at construction ───────────────────────────────────────────────────

def test_an_identity_without_an_equipment_key_is_refused() -> None:
    """Every job on the site with that label and day would otherwise share a key, and the
    second machine's job would never be raised."""
    with pytest.raises(ValueError, match="needs an equipment key"):
        WorkOrderIdentity(equipment_key="  ", fault_label="CONDENSER_LOW_FLOW", day=DAY)


def test_an_empty_fault_label_is_refused_and_the_sentinel_is_deliberate() -> None:
    """An empty label silently collapses every unlabelled finding on one machine-day into a
    single job. The sentinel makes that a decision somebody typed rather than a default — and
    `Q90` asks whether the merge is right at all."""
    with pytest.raises(ValueError, match="needs a fault label"):
        WorkOrderIdentity(equipment_key="chiller_1", fault_label="", day=DAY)

    unlabelled = WorkOrderIdentity(
        equipment_key="chiller_1", fault_label=UNLABELLED, day=DAY
    )
    assert unlabelled.key, "the sentinel is usable; it is just never implicit"


# ── the two enums cannot drift apart ───────────────────────────────────────────

def test_every_escalation_artefact_that_is_a_work_order_maps_to_a_kind() -> None:
    """`RC15` names three artefacts and two of them are work orders. If a fourth appears
    without a kind, a real escalation route would silently raise no job."""
    work_order_artefacts = {a for a in Artefact if a is not Artefact.NONE}
    assert work_order_artefacts == set(KIND_FOR_ARTEFACT)


def test_the_routes_that_call_nobody_map_to_no_kind_at_all() -> None:
    """Constraint 30 and the defer route: *can't tell* changes nothing, and *wrong moment*
    parks the case with a reason and a date. Giving either one a kind would raise a job for a
    case where the whole point is that nobody was called."""
    assert kind_for_artefact(Artefact.NONE) is None
    assert kind_for_artefact(Artefact.INSPECTION_WORK_ORDER) is WorkOrderKind.INSPECTION
    assert (
        kind_for_artefact(Artefact.AUTHORISATION_WORK_ORDER) is WorkOrderKind.AUTHORISATION
    )


# ── the key fits where it is stored ────────────────────────────────────────────

def test_the_key_fits_the_column_that_enforces_it() -> None:
    """`synex_work_order.idempotency_key` is `String(64)`. A key that overflowed would be
    truncated, a truncated key collides, a collision reads as a duplicate — and a duplicate is
    never raised. That is the one direction this module must not fail in."""
    long_identity = WorkOrderIdentity(
        equipment_key="c" * 64,
        fault_label="STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION" * 3,
        day=DAY,
        kind=WorkOrderKind.AUTHORISATION,
    )
    assert len(work_order_key(long_identity)) == KEY_LENGTH <= 64
    assert len(LOW_FLOW.key) == KEY_LENGTH


def test_the_identity_explains_itself_in_words() -> None:
    """A refusal reading *"idempotency key collision"* tells somebody standing at a screen
    nothing they can act on."""
    rendered = LOW_FLOW.render()
    assert "chiller_1" in rendered
    assert "CONDENSER_LOW_FLOW" in rendered
    assert "2026-04-15" in rendered
    assert "corrective" in rendered
