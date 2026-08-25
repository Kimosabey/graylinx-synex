"""`W2`, `W3`, `W4` — and the three inputs the priority formula does not have.

The tests that matter here are the ones asserting the formula **refuses to look complete**.
A priority is a number a planner schedules against, so one that silently dropped three of
its four terms would be worse than none.
"""
from __future__ import annotations

from datetime import date, datetime

from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_band_available, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.domain import priority as prio
from app.services import work_orders
from app.services.evidence import build_pack, window_for

MEASURED_END = datetime(2026, 6, 23, 11, 50)
DAY = date(2026, 4, 15)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(label: str, slots: int = 3, gates: GateOutcome | None = None):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = tuple(
        ResidualRow("chiller_1", datetime(2026, 4, 15, 9, i), label, values)
        for i in range(slots)
    )
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=gates
        or GateOutcome(
            (check_running({"a": 141.0}), check_band_available(BAND, "Chiller 1"))
        ),
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
        other_labels_same_day=("HIGH_HEAD_AMBIGUOUS",),
    )


# ── W4: the formula, and what it cannot include ────────────────────────────────

def test_the_one_sourced_severity_produces_a_band() -> None:
    p = prio.compute("CONDENSER_LOW_FLOW", 3)
    assert p.band is prio.Band.P0
    assert p.severity == "critical"


def test_an_unrated_class_produces_no_priority_rather_than_a_default() -> None:
    """Six of seven fault classes. A silent `P2` would be a rank invented from nothing."""
    p = prio.compute("HIGH_HEAD_AMBIGUOUS", 40)
    assert p.band is prio.Band.UNRATED
    assert "no agreed severity" in p.explanation
    assert "Q49" in p.explanation


def test_priority_is_never_complete_while_three_inputs_are_missing() -> None:
    """`Q51`. `W4` names criticality, risk, SLA and production impact; this plant records
    one of the four. A formula that looked complete would be scheduled against."""
    for label in ("CONDENSER_LOW_FLOW", "HIGH_HEAD_AMBIGUOUS"):
        p = prio.compute(label, 30)
        assert not p.is_complete
        assert {name for name, _ in p.missing} == {
            "criticality",
            "sla",
            "production_impact",
        }


def test_every_missing_input_says_why_it_is_missing() -> None:
    for _, why in prio.MISSING_INPUTS:
        assert len(why) > 20, "a missing input without a reason is a shrug"


def test_the_explanation_can_be_recomputed_by_hand() -> None:
    """`W4` is a rule, not a model. A rule a planner cannot redo is indistinguishable from
    one, so the explanation names every term it used."""
    p = prio.compute("CONDENSER_LOW_FLOW", 30)
    assert "critical" in p.explanation
    assert "P0" in p.explanation
    assert "30 slots" in p.explanation
    assert str(prio.SUSTAINED_SLOTS) in p.explanation
    assert "Q51" in p.explanation


def test_persistence_is_a_term_but_never_residual_magnitude() -> None:
    """Constraint 3: non-faults were measured to deviate more than faults, so ranking by
    how far a residual sits from its band would put ordinary operation above a real fault.

    `compute` takes a slot count and a label — there is no parameter through which a
    residual could reach it.
    """
    import inspect

    params = set(inspect.signature(prio.compute).parameters)
    assert params == {"fault_label", "slot_count"}
    assert prio.compute("CONDENSER_LOW_FLOW", 30).sustained
    assert not prio.compute("CONDENSER_LOW_FLOW", 3).sustained


# ── W2 and W3: the job carries its own justification ───────────────────────────

def test_the_draft_carries_its_evidence() -> None:
    """The pillar's promise, literally: residuals, gates and signal provenance travel with
    the job rather than being looked up by whoever opens it."""
    draft = work_orders.draft_from_pack(_pack("CONDENSER_LOW_FLOW"))
    kinds = {e.kind for e in draft.evidence}
    assert {"residual", "gate", "signal"} <= kinds
    assert all(e.source for e in draft.evidence), "every line names where it came from"


def test_the_draft_says_it_is_a_draft() -> None:
    """Nothing is persisted yet. A work order nobody can be dispatched against must not
    look like one they can."""
    assert work_orders.draft_from_pack(_pack("CONDENSER_LOW_FLOW")).is_draft


def test_a_poor_fit_warns_before_anyone_is_dispatched() -> None:
    draft = work_orders.draft_from_pack(_pack("CONDENSER_LOW_FLOW"))
    assert any("poorly fitted" in w for w in draft.warnings)


def test_an_undecidable_class_says_the_job_investigates() -> None:
    """It must not read as a repair order for a mechanism nobody has established."""
    draft = work_orders.draft_from_pack(_pack("HIGH_HEAD_AMBIGUOUS"))
    assert any("investigates" in w for w in draft.warnings)


def test_other_labels_the_same_day_are_flagged_as_duplicate_risk() -> None:
    """`RC19`: raising a job per label is how one problem becomes several visits."""
    draft = work_orders.draft_from_pack(_pack("CONDENSER_LOW_FLOW"))
    assert any("several visits" in w for w in draft.warnings)


def test_a_failed_gate_makes_the_job_an_investigation() -> None:
    pack = _pack(
        "CONDENSER_LOW_FLOW",
        gates=GateOutcome((check_running({"a": 0.0, "b": 0.0}),)),
    )
    draft = work_orders.draft_from_pack(pack)
    assert any("investigation, not a repair" in w for w in draft.warnings)


def test_the_draft_states_what_would_close_it() -> None:
    """`W9` is M3, but a work order that does not say what closes it is one somebody
    closes on a note."""
    draft = work_orders.draft_from_pack(_pack("CONDENSER_LOW_FLOW"))
    assert len(draft.cannot_close_until) == 3
    joined = " ".join(draft.cannot_close_until)
    assert "PASS" in joined
    assert "UNKNOWN" in joined
    assert "closure note" in joined


def test_nothing_in_the_work_order_path_calls_a_model() -> None:
    """`W2`, `W3` and `W4` are SW and R in the register. `W1` is the one that needs the
    language model, and it is not this."""
    import pathlib

    source = pathlib.Path(work_orders.__file__).read_text(encoding="utf-8")
    for banned in ("ModelClient", "app.llm", "complete("):
        assert banned not in source, f"work_orders reaches {banned}"
