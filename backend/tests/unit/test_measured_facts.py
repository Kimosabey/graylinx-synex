"""The measured facts, as assertions.

This is the test the plan asks for by name: *"reproducing the measured facts as assertions,
so a query bug then surfaces as a number that disagrees with a document."*

Every number here was measured on `graylinx_synex` and written down in
`docs/20-architecture/00-data-model.md`. Holding them in the domain layer and asserting them
here means the documents and the code cannot drift apart silently — and when the
repositories land, the same numbers are asserted against live query results, so a wrong
`WHERE` clause shows up as **5,308 instead of 5,309** rather than as a plausible answer
nobody checks.

None of this needs MySQL, Postgres, Redis or the GPU.
"""
from __future__ import annotations

from app.domain import equipment, faults, residuals, signals
from app.domain.answer import ANSWER_STATES, AnswerState

# ── the fault inventory ─────────────────────────────────────────────────────────

def test_the_nine_labels_and_their_measured_slot_counts() -> None:
    """`docs/20-architecture/00-data-model.md` §4a, exactly."""
    assert {f.label: f.measured_slots for f in faults.FAULT_CLASSES} == {
        "NO_DIAGNOSIS": 5_309,
        "NO_EFFICIENCY_FAULT": 943,
        "HIGH_HEAD_AMBIGUOUS": 430,
        "REFRIGERANT_SIDE_HIGH_HEAD": 104,
        "COMPRESSOR_INEFFICIENCY": 58,
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION": 32,
        "CONDENSER_WATER_SIDE_UNSPECIFIED": 25,
        "POWER_HIGH_UNEXPLAINED": 22,
        "CONDENSER_LOW_FLOW": 3,
    }


def test_the_refusal_is_the_modal_outcome() -> None:
    """5,309 against 674 faulted slots. The strongest asset in this database.

    If this ever inverts, the demonstration narrative changes completely — so it is
    asserted rather than assumed.
    """
    no_diagnosis = faults.NO_DIAGNOSIS.measured_slots
    faulted = sum(f.measured_slots for f in faults.FAULT_CLASSES if f.is_fault)
    assert faulted == 674
    assert no_diagnosis > faulted * 7


def test_seven_classes_are_faults_and_two_are_not() -> None:
    """`NO_DIAGNOSIS` and `NO_EFFICIENCY_FAULT` are outcomes. A fault count including
    either would be wrong by 6,252 slots."""
    assert len(faults.fault_labels()) == 7
    assert set(faults.all_labels()) - set(faults.fault_labels()) == {
        "NO_DIAGNOSIS",
        "NO_EFFICIENCY_FAULT",
    }


def test_four_of_seven_classes_declare_themselves_undecidable() -> None:
    """Constraint 27: only these get a differential. Four differentials on the reference
    plant, and the count matching is the point."""
    assert set(faults.undecidable_labels()) == {
        "HIGH_HEAD_AMBIGUOUS",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        "CONDENSER_WATER_SIDE_UNSPECIFIED",
        "POWER_HIGH_UNEXPLAINED",
    }


def test_the_ambiguous_class_dominates() -> None:
    """The median outcome, not an edge case to be tidied up later. `F7` is load-bearing."""
    faulted = [f for f in faults.FAULT_CLASSES if f.is_fault]
    assert max(faulted, key=lambda f: f.measured_slots) is faults.HIGH_HEAD_AMBIGUOUS


def test_unlabelled_slots_are_recorded_rather_than_dropped() -> None:
    """7,662 slots the model never scored. A coverage figure that omits them overstates
    reach, which is the shape of inherited constraint 7."""
    assert faults.UNLABELLED_SLOTS == 7_662


# ── severity: one per class, and only one of them is sourced ────────────────────

def test_condenser_low_flow_is_the_only_critical_class() -> None:
    assert faults.CONDENSER_LOW_FLOW.severity is faults.Severity.CRITICAL
    critical = [f for f in faults.FAULT_CLASSES if f.severity is faults.Severity.CRITICAL]
    assert critical == [faults.CONDENSER_LOW_FLOW]


def test_no_severity_is_invented_for_the_other_classes() -> None:
    """Q49. Two severity scales once disagreed on four of seven classes, which is what
    `F17` exists to prevent — and inventing six values in the one authoritative place
    would reproduce that failure with more confidence behind it."""
    assert not faults.is_rated("HIGH_HEAD_AMBIGUOUS")
    assert not faults.is_rated("POWER_HIGH_UNEXPLAINED")
    rated = [f.label for f in faults.FAULT_CLASSES if f.severity is not faults.Severity.UNRATED]
    assert rated == ["CONDENSER_LOW_FLOW"]


def test_an_unknown_label_is_unrated_rather_than_an_error() -> None:
    """A label we have never seen is exactly where guessing is worst."""
    assert faults.severity_of("SOMETHING_NEW") is faults.Severity.UNRATED


def test_an_unrated_severity_renders_as_words() -> None:
    """Never a default, never a dash. The same argument as `Figure.never_measured`."""
    assert "not yet agreed" in faults.UNRATED_SEVERITY_TEXT


# ── coverage: twelve tables, two scoreable ──────────────────────────────────────

def test_twelve_equipment_tables_carry_telemetry() -> None:
    assert len(equipment.all_equipment()) == 12


def test_exactly_two_are_scoreable() -> None:
    """The plan asks for this one by name: the 10-of-12 coverage fact, made executable.

    `gla_residual_stats_wc` is ten rows — five residuals for each of two chillers — so a
    rule that refuses to score equipment with no reference band is the difference between
    two machines and twelve.
    """
    scoreable = equipment.scoreable_equipment()
    assert len(scoreable) == 2
    assert {e.key for e in scoreable} == {"chiller_1", "chiller_2"}


def test_the_other_ten_are_refused_rather_than_guessed() -> None:
    for key in ("condenser_pump_1", "cooling_tower_2", "primary_pump_3", "plant"):
        assert not equipment.is_scoreable(key)


def test_unknown_equipment_is_not_scoreable() -> None:
    """Defaulting the other way would score an asset we know nothing about."""
    assert not equipment.is_scoreable("chiller_3")
    assert equipment.by_key("chiller_3") is None


def test_the_unscoreable_ten_are_the_documented_ones() -> None:
    """Three condenser pumps, three cooling towers, three primary pumps, and the plant."""
    kinds = [e.kind.value for e in equipment.all_equipment() if not e.scoreable]
    assert kinds.count("condenser_pump") == 3
    assert kinds.count("cooling_tower") == 3
    assert kinds.count("primary_pump") == 3
    assert kinds.count("plant") == 1


# ── model fit ───────────────────────────────────────────────────────────────────

def test_ten_rows_five_models_per_chiller() -> None:
    assert len(residuals.MODEL_FITS) == 10
    assert len(residuals.fits_for("chiller_1")) == 5
    assert len(residuals.fits_for("chiller_2")) == 5


def test_the_worst_and_best_fits_are_the_measured_ones() -> None:
    """nRMSE 48.03 against 2.65 — the same model, eighteen times worse on one machine."""
    assert residuals.fit_for("chiller_1", "Chiller_Current").nrmse == 48.03
    assert residuals.fit_for("chiller_2", "Chiller_Current").nrmse == 2.65
    assert residuals.worst_nrmse_for("chiller_1") == 48.03
    assert residuals.worst_nrmse_for("chiller_2") == 3.77


def test_chiller_1_is_badged_and_chiller_2_is_the_hero() -> None:
    """The plan picks the hero case from chiller 2 for exactly this reason, and keeps a
    chiller 1 case in the walkthrough badged — acceptance case 14."""
    assert residuals.has_poor_fit("chiller_1")
    assert not residuals.has_poor_fit("chiller_2")


def test_an_asset_with_no_model_has_no_fit_rather_than_a_default() -> None:
    assert residuals.worst_nrmse_for("cooling_tower_1") is None


def test_the_sixth_model_does_not_exist() -> None:
    """`compressor_power_residual` is 100% NULL. Five are fitted; six is the design.

    Held as an explicit absence because omitting the row is the failure constraint 14
    exists to prevent.
    """
    assert residuals.FITTED_MODEL_COUNT == 5
    assert residuals.DESIGNED_MODEL_COUNT == 6
    assert residuals.ABSENT_RESIDUAL_COLUMN == "compressor_power_residual"
    assert len(residuals.FITTED_MODEL_NAMES) == 5


# ── signal provenance ───────────────────────────────────────────────────────────

def test_condenser_flow_has_never_been_measured() -> None:
    """The single most consequential assertion in this file.

    0 non-zero in 31,884 measured slots, feeding four of the six models. If this ever
    reads MEASURED, either the plant got a flow meter or a query reached the simulated
    window — and the second is far more likely.
    """
    assert signals.status_of("cond_flow") is signals.SignalStatus.NEVER_MEASURED
    assert not signals.COND_FLOW.is_usable
    assert "cond_flow" in signals.never_measured_keys()


def test_the_signals_that_must_never_render_as_a_number() -> None:
    """Four of the five. Only `dpt`… is not usable either — every registered signal here
    is registered *because* something is wrong with it."""
    assert set(signals.unusable_keys()) == {
        "cond_flow",
        "dpt",
        "chiller_flow",
        "cond_leaving_temp",
        "kw_per_tr",
    }


def test_a_suspect_signal_is_not_usable() -> None:
    """Constraint 19: `ABS()` let a flow reading of −2.49 count as credible and understated
    a dead transmitter by 62 days. Suspect is unusable, not merely flagged."""
    assert signals.status_of("chiller_flow") is signals.SignalStatus.SUSPECT
    assert not signals.CHILLER_FLOW.is_usable


def test_dpt_is_constant_rather_than_missing() -> None:
    """Present, and carrying no information. Condenser approach cannot be computed — Q8."""
    assert signals.status_of("dpt") is signals.SignalStatus.CONSTANT


def test_an_unregistered_signal_makes_no_claim() -> None:
    """Silence is not a clean bill of health — constraint 7, applied to signals."""
    assert signals.by_key("suction_pressure") is None
    assert signals.status_of("suction_pressure") is None


def test_absolute_zero_is_the_sentinel_not_a_temperature() -> None:
    assert signals.ABSOLUTE_ZERO_C == -273.15


# ── the answer contract ─────────────────────────────────────────────────────────

def test_six_answer_states_matching_context_section_7() -> None:
    assert ANSWER_STATES == (
        "ANSWERED",
        "PARTIAL",
        "NO_DIAGNOSIS",
        "NEEDS_APPROVAL",
        "BLOCKED",
        "FAILED",
    )


def test_a_refusal_is_not_a_failure() -> None:
    """The distinction the whole product rests on. Collapsing them would mis-describe most
    of what this platform does."""
    assert AnswerState.NO_DIAGNOSIS is not AnswerState.FAILED
    assert AnswerState.NO_DIAGNOSIS.value in ANSWER_STATES
