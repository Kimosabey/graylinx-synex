"""`F16` cross-signal validity · `F6` sensor bias.

Two real failures on the reference plant drive these, and a single-signal check missed both:
flow transmitters reading near zero while ΔT and power stayed normal, and a condenser ΔT
negative every month. Every band asserted here is quoted from
`docs/knowledge_base/HVAC_INSTRUMENT_VALIDITY.md` in the Thermynx repository — none is tuned
and none is ours.
"""
from __future__ import annotations

import pytest

from app.analytics.validity import (
    EFFICIENCY_IMPOSSIBLE_ABOVE,
    EFFICIENCY_SUSPECT_ABOVE,
    Route,
    Verdict,
    assess_slot,
    blocks_dispatch,
    check_efficiency,
    check_flatline,
    check_flow_against_delta_t_and_power,
    check_negative,
    is_poor_but_real,
)

# ── constraint 19: never take the absolute value before judging credibility ────

def test_a_negative_flow_is_absent_not_small() -> None:
    """`ABS()` once let a reading of −2.49 count as credible and understated a dead
    transmitter by 62 days."""
    finding = check_negative("chiller_flow", -2.49)
    assert finding is not None
    assert finding.verdict is Verdict.INVALID_NEGATIVE
    assert finding.is_instrument_fault
    assert finding.excludes_the_slot
    assert "not a small one" in finding.reason
    assert "2.49 of anything" in finding.reason


def test_a_negative_residual_is_a_reading_not_a_fault() -> None:
    """The distinction that makes constraint 19 safe to apply. A residual is a *signed*
    deviation — −5 is as real as +5, and applying the floor rule would discard half of
    every distribution. Our chiller 1 current residual sits at a median of −25.65."""
    assert check_negative("current_residual", -25.65) is None
    assert check_negative("discharge_pressure_residual", -27.86) is None


def test_a_positive_reading_on_a_floored_signal_passes() -> None:
    assert check_negative("chiller_flow", 107.0) is None


def test_a_missing_reading_is_not_a_negative_one() -> None:
    assert check_negative("chiller_flow", None) is None


# ── the impossible combination ─────────────────────────────────────────────────

def test_zero_flow_with_normal_delta_t_and_power_is_a_dead_transmitter() -> None:
    """The failure that blinded our own plant for two months. A chiller circulating nothing
    cannot produce a temperature difference and draw power at the same time."""
    finding = check_flow_against_delta_t_and_power(flow=0.0, delta_t=5.0, power_kw=180.0)
    assert finding is not None
    assert finding.verdict is Verdict.IMPOSSIBLE_COMBINATION
    assert finding.route is Route.INSTRUMENTATION
    assert "not a chiller fault" in finding.reason
    assert "Do not dispatch a crew" in finding.reason


def test_zero_flow_on_a_stopped_machine_is_not_a_contradiction() -> None:
    """~23,800 of 31,884 slots are zero across every signal — a 25% duty cycle. Flagging an
    idle machine would bury every real finding."""
    assert check_flow_against_delta_t_and_power(flow=0.0, delta_t=5.0, power_kw=0.0) is None


def test_zero_flow_with_no_delta_t_is_not_a_contradiction() -> None:
    """Nothing is contradicted: no flow and no temperature difference agree with each other."""
    assert check_flow_against_delta_t_and_power(flow=0.0, delta_t=0.0, power_kw=180.0) is None


def test_real_flow_is_never_flagged_by_this_test() -> None:
    assert check_flow_against_delta_t_and_power(flow=107.0, delta_t=5.0, power_kw=180.0) is None


def test_power_is_tested_as_drawing_at_all_not_against_a_band() -> None:
    """The source gives "e.g. 150–200 kW on a large water-cooled machine" — an illustration,
    not a threshold, and our chillers are not that machine. A band invented here would be
    exactly the unsourced number the rules forbid. `Q55`."""
    small = check_flow_against_delta_t_and_power(flow=0.0, delta_t=5.0, power_kw=12.0)
    assert small is not None, "a small machine drawing power still contradicts zero flow"


# ── efficiency: three sourced bands ────────────────────────────────────────────

def test_an_impossible_efficiency_says_the_denominator_collapsed() -> None:
    """Flow ≈ 0 drives kW/TR to 100–150 against a design of 0.65–0.85 — wrong by two orders
    of magnitude, not by a margin."""
    finding = check_efficiency(147.0)
    assert finding is not None
    assert finding.verdict is Verdict.IMPLAUSIBLE_EFFICIENCY
    assert finding.excludes_the_slot
    assert "not a bad score but an impossible one" in finding.reason


def test_a_suspect_efficiency_routes_to_the_operator_not_instrumentation() -> None:
    """Between the two bands the first move is to compare siblings, not to pull a transmitter."""
    finding = check_efficiency(7.0)
    assert finding is not None
    assert finding.route is Route.OPERATOR


@pytest.mark.parametrize("value", [0.75, 1.40, 2.4, 5.0])
def test_a_plausible_efficiency_raises_nothing(value: float) -> None:
    assert check_efficiency(value) is None


def test_our_healthiest_measured_month_is_poor_but_real() -> None:
    """Partly answers `Q21`. The design band of 0.65–0.85 alone would have made 1.40 look
    broken. It is not — it is poor, and real, and a machine dismissed as a bad sensor is one
    nobody fixes."""
    assert is_poor_but_real(1.40) is True
    assert is_poor_but_real(0.75) is False, "design-band performance is good, not poor-but-real"
    assert is_poor_but_real(147.0) is False


def test_the_two_efficiency_bands_are_ordered() -> None:
    """A guard against a future edit inverting them and making every reading suspect."""
    assert EFFICIENCY_SUSPECT_ABOVE < EFFICIENCY_IMPOSSIBLE_ABOVE


# ── the stuck tag, and why the sibling condition is not optional ───────────────

def test_a_flat_tag_against_varying_siblings_is_stuck() -> None:
    """Our `dpt` is the case — a flat 107.0 on one chiller and 112.9 on the other, which is
    why condenser approach cannot be computed at all (`Q8`)."""
    finding = check_flatline("dpt", [107.0] * 6, [4.1, 4.3, 5.0, 4.8, 5.2, 4.9])
    assert finding is not None
    assert finding.verdict is Verdict.STUCK_TAG
    assert "frozen in software" in finding.reason


def test_a_flat_tag_on_a_steady_plant_is_not_flagged() -> None:
    """The sibling condition is the whole test. A genuinely steady plant makes everything
    steady, and flagging that would bury real findings under false ones."""
    assert check_flatline("dpt", [107.0] * 6, [4.0] * 6) is None


def test_a_varying_tag_is_never_stuck() -> None:
    assert check_flatline("kw", [180.0, 181.0, 179.5], [4.1, 4.3, 5.0]) is None


def test_too_few_readings_produce_no_verdict() -> None:
    """Two points cannot establish that anything is flat."""
    assert check_flatline("dpt", [107.0], [4.1, 4.3]) is None


# ── F6: rule out the instrument before dispatching a crew ─────────────────────

def test_a_contradiction_blocks_dispatch() -> None:
    """`F6`'s whole purpose. Getting this wrong sends a technician to overhaul a healthy
    compressor when the fault is a transmitter costing a fraction as much."""
    findings = assess_slot(chiller_flow=0.0, chw_delta_t=5.0, kw=180.0, kw_per_tr=147.0)
    blocked, reason = blocks_dispatch(findings)
    assert blocked is True
    assert "the fault may be the measurement rather than the machine" in reason


def test_clean_readings_do_not_block_dispatch() -> None:
    findings = assess_slot(chiller_flow=107.0, chw_delta_t=5.0, kw=180.0, kw_per_tr=1.40)
    assert findings == ()
    blocked, reason = blocks_dispatch(findings)
    assert blocked is False
    assert "no contradiction" in reason


def test_the_inputs_are_checked_before_the_number_is_interpreted() -> None:
    """The playbook's reading order, and the ordering that produced two months of invalid
    efficiency figures when it was reversed."""
    findings = assess_slot(chiller_flow=0.0, chw_delta_t=5.0, kw=180.0, kw_per_tr=147.0)
    assert findings[0].verdict is Verdict.IMPOSSIBLE_COMBINATION, (
        "'can the inputs be believed?' comes before 'what does the number mean?'"
    )


def test_every_finding_renders_words_a_reader_can_act_on() -> None:
    """An absence is not a zero and not a dash."""
    for finding in assess_slot(chiller_flow=-2.49, chw_delta_t=5.0, kw=180.0, kw_per_tr=147.0):
        assert finding.render().strip()
        assert finding.signal in finding.render()
