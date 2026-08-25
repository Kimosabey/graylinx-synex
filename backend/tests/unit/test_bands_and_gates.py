"""Bands, gates and episodes — M1.2, and the one test the plan singles out.

*"The test that matters: a current residual of −25 is NORMAL on chiller 1 (healthy median
−25.645) and abnormal on chiller 2. That single test is the whole of `F15` and it permanently
catches the compare-to-zero bug."*

It is first in this file for that reason. Everything else here defends a gate.

Nothing in this file touches MySQL, Postgres, Redis or the GPU. If any of it ever needs one,
the layering is wrong.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.analytics.bands import (
    BandVerdict,
    ResidualBand,
    classify,
    find_band,
    is_judgeable,
)
from app.analytics.episodes import (
    Episode,
    LabelledSlot,
    equipment_days,
    inflation_ratio,
    labels_on,
    multi_label_days,
    naive_case_count,
    to_episodes,
)
from app.analytics.gates import (
    EVALUABLE_GATES,
    UNAGREED_GATES,
    Gate,
    GateOutcome,
    check_band_available,
    check_load_floor,
    check_measured_window,
    check_persistence,
    check_physically_plausible,
    check_running,
)

# ── the bands ───────────────────────────────────────────────────────────────────

# ── the real bands, read from gla_residual_stats_wc on 2026-08-14 ───────────────
#
# These are the measured `robust_low`/`med`/`robust_high` values, not illustrative ones. An
# earlier version of this file invented plausible bounds and asserted the claim the plan
# makes — that −25 is normal on chiller 1 and abnormal on chiller 2. **Querying the database
# disproved it:** chiller 2's robust band is [−60.700, 0.680], so −25 is comfortably normal
# on both machines. The invented band had made a false statement look verified, which is the
# exact failure this whole test file exists to catch, one level up.
#
# The real numbers make the point better, because the two bands barely overlap in *shape*:
# chiller 1's is narrow (mad 2.93) and sits well below zero; chiller 2's is four times wider
# (mad 6.90) and reaches past zero.

# Keyed by the *domain* equipment key, not the table name. `gla_residual_stats_wc` stores
# `chiller_1_normalized`; the repository maps that to `chiller_1` on the way in, so database
# naming never reaches the analytics layer.
CHILLER_1_CURRENT = ResidualBand(
    equipment_key="chiller_1",
    residual_name="chiller_current_residual",
    median=-25.645,
    lower=-38.677,
    upper=-12.613,
)

CHILLER_2_CURRENT = ResidualBand(
    equipment_key="chiller_2",
    residual_name="chiller_current_residual",
    median=-30.010,
    lower=-60.700,
    upper=0.680,
)


def test_zero_is_abnormal_on_one_machine_and_normal_on_the_other() -> None:
    """`F15`, entire. The test that permanently catches the compare-to-zero bug.

    A residual of exactly **0.0** — the value a naive implementation treats as perfectly
    healthy — is `HIGH` on chiller 1, whose healthy band is [−38.677, −12.613] and never
    comes near zero. On chiller 2 the same 0.0 is ordinary.

    So the naive reading is not merely imprecise; it is **inverted** on one of the two
    machines. Any implementation comparing against zero fails here.
    """
    assert classify(0.0, CHILLER_1_CURRENT) is BandVerdict.HIGH
    assert classify(0.0, CHILLER_2_CURRENT) is BandVerdict.NORMAL


def test_a_large_negative_residual_is_a_fault_on_one_machine_and_routine_on_the_other() -> None:
    """−50 sits outside chiller 1's band and inside chiller 2's. Same signal, same fleet.

    This is why models are fitted per asset and never per fleet, and why a shared threshold
    would raise on chiller 1 while missing the identical reading on chiller 2.
    """
    assert classify(-50.0, CHILLER_1_CURRENT) is BandVerdict.LOW
    assert classify(-50.0, CHILLER_2_CURRENT) is BandVerdict.NORMAL


def test_minus_25_is_normal_on_both_machines() -> None:
    """The measured correction to the plan's example, kept as a test so it cannot regress.

    The plan states −25 is abnormal on chiller 2. It is not: the robust band reaches
    0.680. Asserting the true behaviour here stops someone "fixing" the code to match the
    document — the document is the thing that was wrong.
    """
    assert classify(-25.0, CHILLER_1_CURRENT) is BandVerdict.NORMAL
    assert classify(-25.0, CHILLER_2_CURRENT) is BandVerdict.NORMAL


def test_the_two_bands_have_very_different_widths() -> None:
    """mad 2.93 against 6.90. A single tolerance cannot serve both."""
    assert CHILLER_1_CURRENT.width < CHILLER_2_CURRENT.width / 2


@pytest.mark.parametrize(
    "value,expected",
    [
        (-38.677, BandVerdict.NORMAL),   # on the lower bound — inclusive
        (-12.613, BandVerdict.NORMAL),   # on the upper bound — inclusive
        (-38.678, BandVerdict.LOW),
        (-12.612, BandVerdict.HIGH),
    ],
)
def test_the_band_edges_are_inclusive(value: float, expected: BandVerdict) -> None:
    """A reading exactly on the healthy bound is healthy. The alternative makes the band
    narrower than the distribution it was fitted from."""
    assert classify(value, CHILLER_1_CURRENT) is expected


def test_no_band_means_nothing_may_be_said() -> None:
    """Ten of twelve assets. `NO_BAND` must never degrade into a comparison against zero."""
    assert classify(-25.0, None) is BandVerdict.NO_BAND
    assert not is_judgeable(None)


def test_a_null_residual_is_not_healthy() -> None:
    """`compressor_power_residual` is 100% NULL. Constraint 7: NULL means not diagnosed."""
    assert classify(None, CHILLER_1_CURRENT) is BandVerdict.NO_BAND


def test_a_band_cannot_be_inverted() -> None:
    with pytest.raises(ValueError, match="lower"):
        ResidualBand("chiller_1", "Chiller_Current", median=0.0, lower=5.0, upper=-5.0)


def test_find_band_does_not_cross_assets() -> None:
    """Scoring chiller 1 against chiller 2's band would look entirely plausible in output.

    And it would be wrong in the worst direction: chiller 2's band is nearly four times
    wider, so chiller 1 readings would be judged normal almost everywhere.
    """
    bands = (CHILLER_1_CURRENT, CHILLER_2_CURRENT)
    assert find_band(bands, "chiller_1", "chiller_current_residual") is CHILLER_1_CURRENT
    assert find_band(bands, "chiller_2", "chiller_current_residual") is CHILLER_2_CURRENT
    assert find_band(bands, "cooling_tower_1", "chiller_current_residual") is None
    assert find_band(bands, "chiller_1", "Sp_residual") is None


# ── gate 1: off, not broken ─────────────────────────────────────────────────────

def test_a_stopped_machine_is_off_not_faulty() -> None:
    """~23,800 of 31,884 slots. The commonest false positive available."""
    result = check_running({"chiller_current": 0.0, "suction_pres": 0.0, "kw": 0.0})
    assert not result.passed
    assert "off, not faulty" in result.reason
    assert result.remedy


def test_a_running_machine_passes() -> None:
    assert check_running({"chiller_current": 141.2, "suction_pres": 0.0}).passed


def test_no_readings_is_not_evidence_of_running() -> None:
    assert not check_running({}).passed
    assert not check_running({"chiller_current": None}).passed


# ── gate 2: is there a band? ────────────────────────────────────────────────────

def test_an_asset_with_no_band_is_refused_by_name() -> None:
    result = check_band_available(None, "Cooling tower 1")
    assert not result.passed
    assert "Cooling tower 1" in result.reason
    assert "chiller 1 or chiller 2" in result.remedy


def test_an_asset_with_a_band_passes() -> None:
    assert check_band_available(CHILLER_1_CURRENT, "Chiller 1").passed


# ── gate 3: measured, or generated? ─────────────────────────────────────────────

MEASURED_END = datetime(2026, 6, 23, 11, 50)


def test_a_simulated_slot_is_refused_and_says_why() -> None:
    """D-009. The refusal names `cond_flow` specifically, because "this window is simulated"
    understates it: the problem is a fabricated instrumentation capability, not weak data."""
    result = check_measured_window(datetime(2026, 8, 5, 12, 0), MEASURED_END)
    assert not result.passed
    assert "condenser flow" in result.reason
    assert "never measured" in result.reason


def test_a_measured_slot_passes() -> None:
    assert check_measured_window(datetime(2026, 4, 15, 9, 0), MEASURED_END).passed


def test_the_boundary_slot_itself_is_measured() -> None:
    """The last real reading is real. An off-by-one here would discard it."""
    assert check_measured_window(MEASURED_END, MEASURED_END).passed


def test_reaching_the_simulated_window_takes_an_explicit_flag() -> None:
    """Never a default. A repository that could return a simulated slot without this being
    passed is the failure the plan's data discipline is built around."""
    assert check_measured_window(
        datetime(2026, 8, 5, 12, 0), MEASURED_END, include_simulated=True
    ).passed


# ── gate 4: physically possible? ────────────────────────────────────────────────

def test_absolute_zero_is_a_sensor_reporting_its_own_failure() -> None:
    result = check_physically_plausible(cond_leaving_temp=-273.2)
    assert not result.passed
    assert "absolute zero" in result.reason


def test_a_negative_condenser_delta_t_is_impossible() -> None:
    """A condenser rejects heat. Negative every month on one chiller, and nothing caught it."""
    result = check_physically_plausible(cond_leaving_temp=29.0, cond_entering_temp=32.2)
    assert not result.passed
    assert "rejects heat" in result.reason


def test_a_meaningless_efficiency_is_refused() -> None:
    """−6,265 to +30,183 on chiller 1. Not a bad score — a meaningless one."""
    assert not check_physically_plausible(kw_per_tr=30_183.0).passed
    assert not check_physically_plausible(kw_per_tr=-6_265.0).passed


def test_plausible_readings_pass() -> None:
    assert check_physically_plausible(
        cond_leaving_temp=35.1, cond_entering_temp=30.4, kw_per_tr=0.72
    ).passed


def test_the_sign_is_not_thrown_away_before_judging() -> None:
    """Constraint 19: `ABS()` let a flow reading of −2.49 count as credible and understated a
    dead transmitter by 62 days. A negative efficiency must not pass by taking its modulus."""
    assert not check_physically_plausible(kw_per_tr=-0.72).passed


# ── the unagreed gates refuse ───────────────────────────────────────────────────

def test_an_unagreed_threshold_refuses_rather_than_passing() -> None:
    """Q3 and Q6. Passing a gate whose threshold nobody agreed is how a diagnosis gets made
    on data the model cannot judge."""
    load = check_load_floor(120.0)
    assert not load.passed
    assert load.unresolved_question == "Q3"

    persistence = check_persistence(6)
    assert not persistence.passed
    assert persistence.unresolved_question == "Q6"
    assert "6 consecutive slot" in persistence.reason


def test_the_unagreed_gates_are_not_in_the_evaluable_set() -> None:
    """Wiring them in today would make every diagnosis refuse for a reason nobody can act
    on. They stay reachable, so it is a one-line change when the answers arrive."""
    assert set(EVALUABLE_GATES).isdisjoint(UNAGREED_GATES)
    assert len(EVALUABLE_GATES) == 4


# ── the outcome ─────────────────────────────────────────────────────────────────

def test_the_named_gate_is_the_first_failure_in_evaluation_order() -> None:
    """Not "the worst". Ordering by severity would imply a ranking nobody agreed, and a
    refusal has to be explainable more than it has to be dramatic."""
    outcome = GateOutcome(
        (
            check_running({"a": 141.0}),
            check_band_available(None, "Cooling tower 1"),
            check_measured_window(datetime(2026, 8, 5), MEASURED_END),
        )
    )
    assert not outcome.passed
    assert len(outcome.failures) == 2
    assert outcome.first_failure.gate is Gate.BAND_AVAILABLE


def test_an_all_pass_outcome_has_no_named_gate() -> None:
    outcome = GateOutcome(
        (
            check_running({"a": 141.0}),
            check_band_available(CHILLER_1_CURRENT, "Chiller 1"),
        )
    )
    assert outcome.passed
    assert outcome.first_failure is None


# ── episodes ────────────────────────────────────────────────────────────────────

def _slots(equipment: str, label: str, day: int, n: int) -> list[LabelledSlot]:
    return [
        LabelledSlot(equipment, datetime(2026, 4, day, 8 + (i // 12), (i % 12) * 5), label)
        for i in range(n)
    ]


def test_a_long_run_collapses_to_one_episode_per_day() -> None:
    """412 slots over ten days become ten episodes, not 412 cases.

    Constraint 35. Per-slot cases would bury one afternoon under five hundred rows.
    """
    slots: list[LabelledSlot] = []
    for day in range(9, 19):
        slots.extend(_slots("chiller_1", "HIGH_HEAD_AMBIGUOUS", day, 41))
    slots.extend(_slots("chiller_1", "HIGH_HEAD_AMBIGUOUS", 19, 2))

    episodes = to_episodes(tuple(slots))
    assert len(slots) == 412
    assert len(episodes) == 11
    assert sum(e.slot_count for e in episodes) == 412


def test_five_labels_on_one_day_make_five_naive_cases() -> None:
    """2026-04-15, chiller 1. One plausible repair, five work orders — the `RC19` problem,
    and Q47 is the question about which of them may be grouped."""
    labels = [
        "CONDENSER_LOW_FLOW",
        "HIGH_HEAD_AMBIGUOUS",
        "POWER_HIGH_UNEXPLAINED",
        "REFRIGERANT_SIDE_HIGH_HEAD",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
    ]
    slots = tuple(s for label in labels for s in _slots("chiller_1", label, 15, 3))

    episodes = to_episodes(slots)
    assert naive_case_count(episodes) == 5
    assert equipment_days(episodes) == 1
    assert inflation_ratio(episodes) == 5.0
    assert labels_on(episodes, "chiller_1", date(2026, 4, 15)) == tuple(sorted(labels))


def test_labels_are_not_ordered_by_how_long_they_ran() -> None:
    """Constraint 36: the ambiguous class is usually both the longest-running and the least
    informative — it appeared on 12 of 12 fault days. Picking "the biggest" would title
    every event with the label that says least."""
    slots = (
        *_slots("chiller_1", "HIGH_HEAD_AMBIGUOUS", 15, 100),
        *_slots("chiller_1", "CONDENSER_LOW_FLOW", 15, 2),
    )
    assert labels_on(to_episodes(slots), "chiller_1", date(2026, 4, 15)) == (
        "CONDENSER_LOW_FLOW",
        "HIGH_HEAD_AMBIGUOUS",
    )


def test_multi_label_days_are_where_correlation_earns_its_keep() -> None:
    slots = (
        *_slots("chiller_1", "HIGH_HEAD_AMBIGUOUS", 15, 3),
        *_slots("chiller_1", "CONDENSER_LOW_FLOW", 15, 3),
        *_slots("chiller_2", "COMPRESSOR_INEFFICIENCY", 12, 3),
    )
    assert multi_label_days(to_episodes(slots)) == (("chiller_1", date(2026, 4, 15)),)


def test_an_empty_window_has_no_ratio_rather_than_a_ratio_of_one() -> None:
    """Returning 1.0 would report a healthy-looking figure for a window in which nothing was
    detected at all — inherited constraint 7, in arithmetic form."""
    assert inflation_ratio(()) is None
    assert equipment_days(()) == 0


def test_episode_order_is_stable() -> None:
    """An unstable order makes the demonstration different every time it is run."""
    slots = (
        *_slots("chiller_2", "COMPRESSOR_INEFFICIENCY", 17, 2),
        *_slots("chiller_1", "HIGH_HEAD_AMBIGUOUS", 15, 2),
        *_slots("chiller_1", "CONDENSER_LOW_FLOW", 15, 2),
    )
    keys = [e.key for e in to_episodes(slots)]
    assert keys == sorted(keys)
    assert isinstance(to_episodes(slots)[0], Episode)
