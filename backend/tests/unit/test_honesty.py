"""The honesty type, tested for the failures it exists to prevent.

Every test here corresponds to a way an answer can be confidently wrong. The first three are
the invariant; the rest are the measured facts from `docs/20-architecture/00-data-model.md`
turned into assertions, so a change that would let one of them slip fails the build.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.analytics.honesty import Absence, Basis, DataWindow, Figure, Provenance

# ── the invariant: a value xor a reason ────────────────────────────────────────

def test_a_figure_with_neither_value_nor_reason_is_refused() -> None:
    """The whole point of the type. 'Print a blank and move on' must be unrepresentable."""
    with pytest.raises(ValueError, match="no value and no absence reason"):
        Figure(label="condenser flow")


def test_a_figure_with_both_a_value_and_a_reason_is_refused() -> None:
    """Saying two things is as dishonest as saying nothing."""
    with pytest.raises(ValueError, match="both a value"):
        Figure(label="kW/TR", value=0.72, absence=Absence.NEVER_MEASURED)


def test_an_unknown_absence_reason_is_refused() -> None:
    """A typo'd reason would render as an empty string, which is a dash by another route."""
    with pytest.raises(ValueError, match="unknown absence reason"):
        Figure(label="approach", absence="dunno")


# ── never measured is not zero, and not a dash ─────────────────────────────────

def test_never_measured_renders_words_not_a_number() -> None:
    """`cond_flow` on this plant: 0 of 31,884 measured readings.

    `0`, `—` and 'never measured' are three different claims and only one is true.
    """
    f = Figure.never_measured("condenser flow", unit="m3/h")
    assert f.render_value() == "never measured"
    assert "0" not in f.render_value()
    assert "—" not in f.render_value()
    assert f.is_absent


def test_never_measured_serialises_as_null_plus_a_reason() -> None:
    """A caller that serialises this cannot turn 'never measured' into 0 — only into null."""
    d = Figure.never_measured("condenser flow").as_dict()
    assert d["value"] is None
    assert d["absence"] == Absence.NEVER_MEASURED
    assert d["text"] == "never measured"


def test_never_measured_is_not_instrumented_here() -> None:
    """Provenance, not just presence. `C26`: the signal is absent because the site lacks it."""
    assert Figure.never_measured("condenser flow").provenance == Provenance.NOT_INSTRUMENTED


# ── the measured facts, as assertions ──────────────────────────────────────────

def test_an_impossible_sensor_reading_is_an_absence_not_a_value() -> None:
    """`cond_leaving_temp` reads -273.2 on four days. Absolute zero is a failure report."""
    f = Figure.absent(
        "condenser leaving temperature",
        Absence.INSTRUMENT_INVALID,
        unit="C",
        note="the sensor reported -273.2 C, which is absolute zero",
    )
    assert f.is_absent
    assert "faulty" in f.render_value()
    assert "-273.2" in (f.note or "")


def test_a_meaningless_efficiency_figure_is_an_absence() -> None:
    """`kw_per_tr` ranges -6,265 to +30,183 on chiller 1, computed while flow was near zero.

    A number that large is not a bad score, it is a meaningless one.
    """
    f = Figure.absent(
        "efficiency",
        Absence.NOT_COMPUTABLE,
        unit="kW/TR",
        note="flow was below the valid floor for every slot in this window",
    )
    assert f.is_absent
    assert f.value is None


def test_the_sixth_model_is_absent_rather_than_omitted() -> None:
    """`compressor_power_residual` is 100% NULL — five models are fitted per chiller, not six.

    Omitting the row is the failure; stating it is the fix.
    """
    f = Figure.absent("compressor power residual", Absence.NOT_MODELLED)
    assert f.render_value() == "no model is fitted for this signal"


def test_a_blind_window_is_not_a_healthy_window() -> None:
    """`NO_DIAGNOSIS` is the modal outcome — 5,309 slots against 674 faulted ones.

    An absent fault count over a blind window reads as a clean month. It was not.
    """
    f = Figure.absent("faults detected", Absence.NOT_DIAGNOSABLE)
    assert "blind" in f.render_value()


# ── simulated is a different claim from measured ───────────────────────────────

def test_a_simulated_value_says_so() -> None:
    """156,129 slots are synthetic. A generated reading is not a lesser one, it is a
    different claim."""
    f = Figure.simulated("suction pressure", 121.4, "kPa")
    assert f.provenance == Provenance.SIMULATED
    assert "(simulated)" in f.render_value()


def test_a_measured_value_carries_no_qualifier() -> None:
    f = Figure.measured("suction pressure", 121.4, "kPa")
    assert f.provenance == Provenance.MEASURED
    assert "simulated" not in f.render_value()
    assert "estimated" not in f.render_value()


def test_an_unknown_provenance_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown provenance"):
        Figure(label="x", value=1.0, provenance="probably_fine")


# ── judgement is labelled as judgement, in the same sentence ───────────────────

def test_a_judged_figure_is_marked_inline() -> None:
    """A model's opinion with a unit attached, printed like a meter reading, becomes a
    budget line."""
    assert "(estimated)" in Figure.judged("annual saving", 42000, "INR").render_value()


def test_derived_carries_the_same_weight_as_measured() -> None:
    """Arithmetic over measured facts is not a guess, and must not be marked as one."""
    f = Figure.derived("cost", 3570.0, "INR")
    assert f.basis == Basis.DERIVED
    assert "estimated" not in f.render_value()


# ── the data window ───────────────────────────────────────────────────────────

def test_a_window_states_its_period() -> None:
    """`C22`. On a snapshot, an answer that does not say what it covers is a lie by omission."""
    w = DataWindow(start=datetime(2026, 3, 4, 18, 55), end=datetime(2026, 6, 23, 11, 50))
    rendered = w.render()
    assert "2026-03-04" in rendered
    assert "2026-06-23" in rendered
    assert "snapshot" in rendered


def test_a_figure_is_immutable() -> None:
    """A figure that can be edited after construction can be edited past its own invariant.

    The exception is named rather than blind. `pytest.raises(Exception)` would also pass if
    the assignment failed for some unrelated reason — an `AttributeError` from a renamed
    field, say — which would leave this test green while the frozen guarantee was gone.
    """
    f = Figure.measured("kW", 175.0)
    with pytest.raises(FrozenInstanceError):
        f.value = 0.0  # type: ignore[misc]
