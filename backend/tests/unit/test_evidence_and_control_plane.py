"""M1.3 — the evidence pack and the Control Plane, with no model anywhere near them.

The most important test in this file is `test_the_prompt_data_contains_no_raw_floats`. The
whole grounding design in M1.4 rests on the model being handed **display strings**, so the
numeric audit is string containment rather than float comparison. If a float ever leaks into
the prompt payload, that audit silently weakens from exact to approximate and nothing else
in the system would notice.

The second is `test_a_demonstration_identity_can_never_claim_to_be_production`. A stand-in
identity's danger is that it stops being one.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.analytics.bands import BandVerdict, ResidualBand
from app.analytics.gates import GateOutcome, check_band_available, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.services.control_plane import (
    IDENTITY_KIND,
    Capability,
    Persona,
    PersonaTokenError,
    audit_row,
    compute_scope,
    issue_persona_token,
    read_persona_token,
)
from app.services.evidence import (
    EvidencePack,
    SourceRef,
    build_pack,
    window_for,
)

MEASURED_END = datetime(2026, 6, 23, 11, 50)
DAY = date(2026, 4, 15)

CHILLER_1_CURRENT = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)
CHILLER_1_DP = ResidualBand("chiller_1", "Dp_residual", -7.53, -25.677, 10.617)
BANDS = (CHILLER_1_CURRENT, CHILLER_1_DP)


def _row(slot: datetime, label: str, current: float | None = -20.0) -> ResidualRow:
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = current
    values["Dp_residual"] = 3.2
    return ResidualRow("chiller_1", slot, label, values)


def _pack(label: str = "HIGH_HEAD_AMBIGUOUS", current: float | None = -20.0) -> EvidencePack:
    rows = tuple(
        _row(datetime(2026, 4, 15, 9, m), label, current) for m in (0, 5, 10)
    )
    return build_pack(
        rows=rows,
        bands=BANDS,
        gates=GateOutcome(
            (check_running({"a": 141.0}), check_band_available(CHILLER_1_CURRENT, "Chiller 1"))
        ),
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
        other_labels_same_day=("CONDENSER_LOW_FLOW", "POWER_HIGH_UNEXPLAINED"),
    )


# ── the rule the whole grounding design rests on ────────────────────────────────

def _walk(value, path="root"):
    """Yield every leaf in a nested structure with the path that reached it."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, value


def test_the_prompt_data_contains_no_raw_floats() -> None:
    """Display strings only, recursively.

    A model handed `-25.645` prints `-25.6` or `-25.65`, and no float comparison can tell an
    honest rounding from a fabrication. Handed the string, containment answers it exactly.
    """
    for path, leaf in _walk(_pack().to_prompt_data()):
        assert not isinstance(leaf, (float, int)) or isinstance(leaf, bool), (
            f"{path} is a raw number ({leaf!r}); the pack must carry display strings"
        )


def test_every_prompt_leaf_is_a_string() -> None:
    for path, leaf in _walk(_pack().to_prompt_data()):
        assert isinstance(leaf, str), f"{path} is {type(leaf).__name__}, not a string"


# ── a residual never travels without its fit ────────────────────────────────────

def test_a_chiller_1_residual_carries_its_model_nrmse() -> None:
    """48.03. The alarms on this machine may be an artefact of the fit rather than a fault,
    so the fit is not optional context — it is part of the reading."""
    pack = _pack()
    current = next(
        r for r in pack.residual_evidence if r.residual_name == "chiller_current_residual"
    )
    assert current.model_nrmse == 48.03
    assert current.is_from_a_poor_fit
    assert "POOR FIT" in current.render()


def test_the_pack_warns_when_any_residual_comes_from_a_poor_fit() -> None:
    assert _pack().has_poor_fit
    assert "poorly fitted" in _pack().to_prompt_data()["model_fit_warning"]


def test_a_residual_renders_with_its_band_not_against_zero() -> None:
    """The band travels with the number, so the reader can see what "high" meant here."""
    rendered = next(
        r for r in _pack().residual_evidence if r.residual_name == "chiller_current_residual"
    ).render()
    assert "-38.677" in rendered
    assert "-12.613" in rendered
    assert "median" in rendered


def test_the_residual_to_model_mapping_does_not_guess() -> None:
    """`gla_residual_stats_wc` names columns; `gla_equipment_model_metrics` names models.
    Joining them by guesswork attaches a plausible nRMSE to the wrong signal."""
    dp = next(r for r in _pack().residual_evidence if r.residual_name == "Dp_residual")
    assert dp.model_nrmse == 5.38  # chiller_1 Discharge_Pres, not Discharge_Temp's 36.41


# ── absences are figures ────────────────────────────────────────────────────────

def test_the_unfitted_residual_appears_as_a_stated_absence() -> None:
    """100% NULL in 21,534 rows. Omitting the row is the failure constraint 14 prevents."""
    pack = _pack()
    absent = next(
        r for r in pack.residual_evidence if r.residual_name == "compressor_power_residual"
    )
    assert absent.figure.is_absent
    assert absent.figure.render_value() == "no model is fitted for this signal"
    assert absent.verdict is BandVerdict.NO_BAND


def test_a_residual_with_no_band_says_it_cannot_be_judged() -> None:
    pack = _pack()
    unbanded = next(r for r in pack.residual_evidence if r.residual_name == "Sp_residual")
    assert unbanded.verdict is BandVerdict.NO_BAND


# ── severity, and the six that have none ────────────────────────────────────────

def test_an_unrated_class_renders_as_words_not_a_default() -> None:
    """Q49. Six of seven fault classes. A silent `MEDIUM` would be a number invented in the
    one place `F17` says must be authoritative."""
    assert "not yet agreed" in _pack("HIGH_HEAD_AMBIGUOUS").severity_text


def test_the_one_sourced_severity_renders_as_itself() -> None:
    assert _pack("CONDENSER_LOW_FLOW").severity_text == "critical"


def test_an_undecidable_class_is_flagged_as_such() -> None:
    """Constraint 27: only a class the model declares undecidable gets a differential."""
    assert _pack("HIGH_HEAD_AMBIGUOUS").is_undecidable
    assert not _pack("CONDENSER_LOW_FLOW").is_undecidable


# ── the window, the sources, and the signals ────────────────────────────────────

def test_every_pack_states_its_window() -> None:
    """`C22` and constraint 15. On a snapshot, a missing window is a lie by omission."""
    assert "2026-04-15" in _pack().to_prompt_data()["data_window"]


def test_the_window_never_runs_past_the_measured_boundary() -> None:
    """A day at the edge of the snapshot clips to the last real reading, not to midnight."""
    window = window_for(date(2026, 6, 23), MEASURED_END)
    assert window.end == MEASURED_END


def test_every_figure_carries_its_source_and_row_count() -> None:
    """"The median residual was −25.6" means something different over 3 slots than over 412."""
    pack = _pack()
    assert all(r.source.rows == 3 for r in pack.residual_evidence)
    assert any("gla_model_residuals_wc" in s.render() for s in pack.sources)
    assert any("gla_residual_stats_wc" in s.render() for s in pack.sources)


def test_the_pack_always_carries_the_signal_provenance() -> None:
    """`cond_flow` shapes any high-head answer whether or not the answer mentions it. An
    answer that omits it reads as though the branch were fully evidenced."""
    notes = _pack().to_prompt_data()["signal_provenance"]
    assert any("condenser flow" in n for n in notes)
    assert any("never_measured" in n for n in notes)


def test_the_other_labels_that_day_travel_with_the_pack() -> None:
    """Five on 2026-04-15. Without them the model cannot know it is one of several."""
    assert _pack().to_prompt_data()["other_labels_same_day"] == [
        "CONDENSER_LOW_FLOW",
        "POWER_HIGH_UNEXPLAINED",
    ]


def test_a_failed_gate_makes_the_pack_refuse_to_diagnose() -> None:
    pack = build_pack(
        rows=(_row(datetime(2026, 4, 15, 9, 0), "HIGH_HEAD_AMBIGUOUS"),),
        bands=BANDS,
        gates=GateOutcome((check_running({"a": 0.0, "b": 0.0}),)),
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        day=DAY,
    )
    assert not pack.may_diagnose
    assert pack.to_prompt_data()["may_diagnose"] == "no"
    assert any("FAILED" in g for g in pack.to_prompt_data()["gates"])


def test_a_gate_failure_tells_the_model_what_would_change_it() -> None:
    """A refusal that does not say what would unblock it is indistinguishable from a bug."""
    pack = build_pack(
        rows=(),
        bands=(),
        gates=GateOutcome((check_band_available(None, "Cooling tower 1"),)),
        window=window_for(DAY, MEASURED_END),
        equipment_key="cooling_tower_1",
        fault_label=None,
        day=DAY,
    )
    assert any("To change this:" in g for g in pack.to_prompt_data()["gates"])


def test_an_empty_episode_produces_a_pack_rather_than_an_exception() -> None:
    """Ten of twelve assets have nothing. Empty is an answer; a crash is not."""
    pack = build_pack(
        rows=(), bands=(), gates=GateOutcome(),
        window=window_for(DAY, MEASURED_END),
        equipment_key="cooling_tower_1", fault_label=None, day=DAY,
    )
    assert pack.residual_evidence == ()
    assert pack.equipment_display == "Cooling tower 1"


def test_a_source_renders_its_row_count_grammatically() -> None:
    assert "1 row)" in SourceRef("t", 1).render()
    assert "3 rows)" in SourceRef("t", 3).render()


# ── the Control Plane ───────────────────────────────────────────────────────────

def test_a_demonstration_identity_can_never_claim_to_be_production() -> None:
    """D-013. The danger with a stand-in is that it stops being one."""
    for persona in Persona:
        scope = compute_scope(persona)
        assert scope.identity.identity_kind == IDENTITY_KIND
        assert scope.identity.is_production_identity is False


def test_capabilities_are_not_a_ladder() -> None:
    """Constraint 25: a supervisor is not a more capable technician. Neither persona's
    capabilities contain the other's — ranking by seniority once sent a filter-drier
    restriction to a supervisor."""
    tech = compute_scope(Persona.TECHNICIAN).capabilities
    supervisor = compute_scope(Persona.SUPERVISOR).capabilities
    assert not tech.issubset(supervisor)
    assert not supervisor.issubset(tech)


def test_only_the_supervisor_may_approve_and_close() -> None:
    assert compute_scope(Persona.SUPERVISOR).allows(Capability.APPROVE_WORK)
    assert not compute_scope(Persona.RELIABILITY_ENGINEER).allows(Capability.APPROVE_WORK)
    assert not compute_scope(Persona.TECHNICIAN).allows(Capability.CLOSE_WORK)


def test_only_the_administrator_may_edit_policy() -> None:
    assert compute_scope(Persona.ADMINISTRATOR).allows(Capability.EDIT_POLICY)
    for other in (Persona.SUPERVISOR, Persona.TECHNICIAN, Persona.RELIABILITY_ENGINEER):
        assert not compute_scope(other).allows(Capability.EDIT_POLICY)


def test_scope_is_recomputed_rather_than_reused() -> None:
    """A scope carried forward outlives the reason it was granted — and in a conversation
    the previous turn may have been a different persona entirely."""
    first = compute_scope(Persona.TECHNICIAN)
    second = compute_scope(Persona.TECHNICIAN)
    assert first is not second


# ── the signed persona cookie ───────────────────────────────────────────────────

def test_a_persona_token_round_trips() -> None:
    token = issue_persona_token(Persona.SUPERVISOR, "secret")
    assert read_persona_token(token, "secret") is Persona.SUPERVISOR


def test_a_tampered_token_is_refused_rather_than_defaulted() -> None:
    """Editing a cookie must not silently promote a viewer to Administrator mid-demonstration."""
    token = issue_persona_token(Persona.TECHNICIAN, "secret")
    forged = token.replace("technician", "administrator")
    with pytest.raises(PersonaTokenError):
        read_persona_token(forged, "secret")


def test_a_token_signed_with_another_secret_is_refused() -> None:
    token = issue_persona_token(Persona.TECHNICIAN, "secret")
    with pytest.raises(PersonaTokenError):
        read_persona_token(token, "other-secret")


@pytest.mark.parametrize("bad", ["", "no-separator", "{}|deadbeef", "not-json|x"])
def test_a_malformed_token_raises_rather_than_choosing_a_persona(bad: str) -> None:
    """An authorization decision made by a parsing accident is exactly what the separation
    law's seventh row exists to prevent."""
    with pytest.raises(PersonaTokenError):
        read_persona_token(bad, "secret")


# ── the audit trail ─────────────────────────────────────────────────────────────

def test_every_audit_row_records_that_the_identity_was_a_demonstration_one() -> None:
    """So this cannot silently become production auth without the record showing it."""
    row = audit_row(
        request_id="r-1",
        scope=compute_scope(Persona.RELIABILITY_ENGINEER),
        action="explain_fault",
        answer_state="ANSWERED",
        policy_version="2026-08-13.1",
        equipment_key="chiller_1",
    )
    assert row.identity_kind == IDENTITY_KIND
    assert row.as_dict()["identity_kind"] == IDENTITY_KIND


def test_an_audit_row_records_a_refusal_and_the_gate_that_caused_it() -> None:
    """`G6`. A refusal is a turn like any other and is recorded like one."""
    row = audit_row(
        request_id="r-2",
        scope=compute_scope(Persona.TECHNICIAN),
        action="explain_fault",
        answer_state="NO_DIAGNOSIS",
        policy_version="2026-08-13.1",
        gates_failed=("band_available",),
    )
    assert row.answer_state == "NO_DIAGNOSIS"
    assert row.gates_failed == ("band_available",)


def test_the_caller_cannot_forge_the_identity_kind() -> None:
    """It comes from the scope. A route that could pass its own value could log a
    demonstration turn as something else."""
    import inspect

    assert "identity_kind" not in inspect.signature(audit_row).parameters
