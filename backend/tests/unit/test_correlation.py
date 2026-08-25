"""`RC19` — one problem must not become five work orders, and grouping must never be silent.

Built on the measured case: on **2026-04-15 chiller 1 held five labels at once**, and twelve
equipment-days produce 39 naive episodes. These are the real labels from the measured window,
not invented ones.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.analytics.episodes import Episode
from app.domain import correlation
from app.domain.correlation import Relation

DAY = date(2026, 4, 15)


def _episode(label: str, slots: int, equipment: str = "chiller_1", day: date = DAY) -> Episode:
    return Episode(
        equipment_key=equipment,
        fault_label=label,
        day=day,
        slot_count=slots,
        first_slot=datetime.combine(day, datetime.min.time()),
        last_slot=datetime.combine(day, datetime.max.time()),
    )


#: The ambiguous class is deliberately given the largest slot count, because that is what the
#: measurement found — it is both the longest-running and the least informative.
FIVE_LABELS: tuple[Episode, ...] = (
    _episode("HIGH_HEAD_AMBIGUOUS", 412),
    _episode("CONDENSER_LOW_FLOW", 3),
    _episode("COMPRESSOR_INEFFICIENCY", 58),
    _episode("CONDENSER_WATER_SIDE_UNSPECIFIED", 25),
    _episode("POWER_HIGH_UNEXPLAINED", 22),
)


# ── constraint 36: never the longest-running label ─────────────────────────────

def test_the_primary_is_not_the_longest_running_label() -> None:
    """The failure this exists to prevent: titling every event with the label that says
    least. `HIGH_HEAD_AMBIGUOUS` has 412 slots against the winner's 3, and loses."""
    primary, reason = correlation.choose_primary(FIVE_LABELS)
    assert primary.fault_label != "HIGH_HEAD_AMBIGUOUS"
    assert primary.slot_count < max(e.slot_count for e in FIVE_LABELS)
    assert "determinate" in reason


def test_a_determinate_class_beats_an_undecidable_one() -> None:
    """Constraint 36 stated directly. `CONDENSER_LOW_FLOW` names a mechanism;
    `HIGH_HEAD_AMBIGUOUS` says in its own name that it cannot."""
    primary, _ = correlation.choose_primary(
        (_episode("HIGH_HEAD_AMBIGUOUS", 412), _episode("CONDENSER_LOW_FLOW", 3))
    )
    assert primary.fault_label == "CONDENSER_LOW_FLOW"


def test_all_undecidable_labels_produce_a_stated_arbitrary_order() -> None:
    """When nothing is determinate the order claims nothing, and says so rather than
    implying a ranking that the severities cannot support (`Q49`)."""
    primary, reason = correlation.choose_primary(
        (
            _episode("HIGH_HEAD_AMBIGUOUS", 412),
            _episode("POWER_HIGH_UNEXPLAINED", 22),
        )
    )
    assert primary is not None
    assert "not a ranking" in reason


def test_an_instrument_fault_leads_and_the_others_hold() -> None:
    """`RC19`. If the reading is wrong, every other label may be an artefact of it.

    The label is supplied by the caller because the taxonomy has no instrument-fault class —
    that verdict comes from `F16` and the signal provenance, never from `fault_label`.
    """
    primary, reason = correlation.choose_primary(
        FIVE_LABELS, instrument_fault_label="CONDENSER_LOW_FLOW"
    )
    assert primary.fault_label == "CONDENSER_LOW_FLOW"
    assert "artefact" in reason


# ── grouping is proposed, never applied ────────────────────────────────────────

def test_grouping_is_a_proposal_that_always_needs_a_human() -> None:
    """A wrong grouping hides a real second fault, and one made silently is never revisited."""
    (proposal,) = correlation.propose(FIVE_LABELS)
    assert proposal.requires_confirmation is True
    assert proposal.episode_count == 5
    assert proposal.work_orders_avoided == 4
    assert "Nothing is grouped until someone accepts this" in proposal.render()


def test_the_proposal_carries_the_episodes_rather_than_replacing_them() -> None:
    """Constraint 12: grouping is display-level only. The per-label episodes are the trained
    model's actual output, and rewriting them destroys the record of what it emitted."""
    (proposal,) = correlation.propose(FIVE_LABELS)
    carried = {proposal.primary.fault_label, *(e.fault_label for e in proposal.held)}
    assert carried == {e.fault_label for e in FIVE_LABELS}


def test_the_shared_cause_route_reports_itself_unavailable() -> None:
    """`RC19` also groups labels sharing a candidate cause. That needs reviewed differential
    content, which does not exist — so the route is absent and says so rather than grouping
    on unreviewed judgement."""
    (proposal,) = correlation.propose(FIVE_LABELS)
    assert proposal.shared_cause_route_available is False


def test_a_single_label_day_produces_no_proposal() -> None:
    """Manufacturing a one-episode group would inflate the saving this reports."""
    assert correlation.propose((_episode("CONDENSER_LOW_FLOW", 3),)) == ()


def test_outcomes_that_are_not_faults_are_never_grouped() -> None:
    """`NO_DIAGNOSIS` is the modal outcome at 5,309 slots. Grouping refusals into a work
    order would turn the platform's commonest honest answer into work."""
    assert correlation.propose(
        (_episode("NO_DIAGNOSIS", 5_309), _episode("NO_EFFICIENCY_FAULT", 943))
    ) == ()


# ── the reopen rule ────────────────────────────────────────────────────────────

def test_the_same_label_on_the_same_machine_reopens() -> None:
    """Identity, not judgement — so this one is resolved without asking anyone."""
    existing = _episode("CONDENSER_LOW_FLOW", 3)
    new = _episode("CONDENSER_LOW_FLOW", 5, day=DAY + timedelta(days=1))
    relation, matched = correlation.relation_to_open(new, (existing,))
    assert relation is Relation.REOPEN
    assert matched is existing


def test_a_different_machine_is_never_the_same_problem() -> None:
    """Models are fitted per asset; two identical chillers do not share one."""
    existing = _episode("CONDENSER_LOW_FLOW", 3, equipment="chiller_1")
    new = _episode("CONDENSER_LOW_FLOW", 3, equipment="chiller_2")
    relation, matched = correlation.relation_to_open(new, (existing,))
    assert relation is Relation.SEPARATE
    assert matched is None


def test_a_different_label_on_the_same_day_is_only_proposed() -> None:
    existing = _episode("HIGH_HEAD_AMBIGUOUS", 412)
    new = _episode("CONDENSER_LOW_FLOW", 3)
    relation, _ = correlation.relation_to_open(new, (existing,))
    assert relation is Relation.PROPOSED_GROUP


def test_an_old_episode_outside_the_window_opens_fresh() -> None:
    existing = _episode("CONDENSER_LOW_FLOW", 3)
    new = _episode("CONDENSER_LOW_FLOW", 3, day=DAY + timedelta(days=30))
    relation, _ = correlation.relation_to_open(new, (existing,))
    assert relation is Relation.SEPARATE


# ── the inflation figure ───────────────────────────────────────────────────────

def test_the_saving_is_a_ceiling_and_not_a_plan() -> None:
    """Reporting the grouped figure as though it had happened is the silent grouping `RC19`
    forbids. Five labels collapse to at most one — and only once a human agrees."""
    naive, days, accepted = correlation.inflation(FIVE_LABELS)
    assert (naive, days, accepted) == (5, 1, 1)


def test_choose_primary_refuses_an_empty_group() -> None:
    with pytest.raises(ValueError):
        correlation.choose_primary(())
