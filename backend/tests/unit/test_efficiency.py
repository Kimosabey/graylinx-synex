"""`E1` efficiency baseline and kW/TR — and the half of `E1` that must never be delivered.

**Most of this file is about what the module refuses.** `CONTEXT.md` §10a is explicit: design
band **0.65–0.85** against a healthiest *measured* month of **1.40**, therefore *"there is no
defensible baseline yet, so `E1` cannot be built as specified. `Q21`."* A baseline drawn
anyway, or a *"% improvement"* against it, would read as measurement while being an
assumption — so the tests that matter most assert that no number comes back and that the
refusal names `Q21`.

**The incident behind the rest.** Both chilled-water flow transmitters read near zero from
May while ΔT and power stayed normal. Efficiency is computed from flow, so `kw_per_tr` on
chiller 1 ranges from **−6,265 to +30,183**, and two months of efficiency figures were invalid
before anyone noticed. Average those slots in and the figure is not slightly wrong — against a
design band of 0.65–0.85 it is wrong by two orders of magnitude. So invalid slots are
*excluded*, and the count excluded travels with every figure.

Counts here are the measured ones: **31,884** in-window slots per chiller, of which **7,670**
are derived by `derived:tr_from_load_v1` since the 2026-08-17 re-clone.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.analytics import efficiency
from app.analytics.efficiency import (
    DERIVED_SLOTS_IN_MEASURED_WINDOW,
    DERIVED_TR_METHOD,
    DESIGN_BAND,
    EXCLUDED_BANDS,
    EXCLUSION_SUMMARY,
    HEALTHIEST_MEASURED_MONTH,
    MIN_VALID_COVERAGE,
    Band,
    InputBasis,
    PeriodEfficiency,
    Refusal,
    SlotReading,
    baseline,
    classify,
    percent_improvement,
    summarise,
)
from app.analytics.honesty import Absence, Basis
from app.analytics.validity import Route

WINDOW_START = datetime(2026, 4, 15, 0, 0)
WINDOW_END = datetime(2026, 6, 23, 11, 50)
SLOT = datetime(2026, 5, 1, 9, 0)

IN_WINDOW_SLOTS = 31_884
DERIVED_IN_WINDOW = 7_670

#: The two ends of the range chiller 1's `kw_per_tr` actually reached while flow was collapsed.
WORST_MEASURED_LOW = -6_265.0
WORST_MEASURED_HIGH = 30_183.0


def _slot(
    value: float | None,
    *,
    basis: InputBasis = InputBasis.MEASURED,
    reason: str = "",
    kw: float | None = None,
    tr: float | None = None,
) -> SlotReading:
    return SlotReading(SLOT, value, basis, absence_reason=reason, kw=kw, tr=tr)


def _period(readings: list[SlotReading], **kw) -> PeriodEfficiency:
    return summarise(
        equipment_key="chiller_1",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        readings=readings,
        **kw,
    )


# ── Q21: the baseline that is refused, and the refusal that names why ──────────

def test_no_baseline_is_produced_and_the_refusal_names_q21() -> None:
    """`E1` asks for the reference efficiency is measured against. There is not one, and
    inventing one is how *"back to normal"* comes to mean *"back to poor"* permanently."""
    refusal = baseline()
    assert isinstance(refusal, Refusal)
    assert refusal.question == "Q21"
    assert refusal.as_figure().value is None
    assert refusal.as_figure().is_absent
    assert "Q21" in refusal.render()


def test_the_baseline_refusal_shows_the_gap_rather_than_asserting_it() -> None:
    """A refusal a reader cannot check is an assertion. Both halves of the gap are quoted —
    the 0.65–0.85 design band and the 1.40 the plant has actually measured — so the reader can
    see why neither anchors anything."""
    reason = baseline().reason
    assert "0.65-0.85" in reason
    assert str(HEALTHIEST_MEASURED_MONTH) in reason
    assert "poor-but-real" in reason
    assert "nameplate expectation" in reason


def test_a_clean_period_does_not_earn_a_baseline() -> None:
    """The temptation is to let a period that survived exclusion become the reference. It
    cannot: a usable tracking figure and a reference are different claims, and the refusal
    says so with that period's own numbers in it."""
    period = _period([_slot(1.40), _slot(1.45), _slot(1.38)])
    refusal = baseline(period)
    assert refusal.question == "Q21"
    assert refusal.as_figure().value is None
    assert "still not a reference" in refusal.reason


def test_no_percentage_improvement_is_computed_even_between_two_clean_periods() -> None:
    """Refused when the arithmetic would have worked, because the arithmetic was never the
    problem — a percentage needs something to be a percentage *of*."""
    before = _period([_slot(1.40), _slot(1.50)])
    after = _period([_slot(1.30), _slot(1.35)])
    refusal = percent_improvement(before, after)
    assert isinstance(refusal, Refusal)
    assert refusal.question == "Q21"
    assert refusal.as_figure().value is None
    assert "No percentage is produced" in refusal.reason


def test_the_improvement_refusal_gives_four_reasons_not_one() -> None:
    """One reason invites a reader to fix that reason and ask again. The percentage is refused
    on four independent grounds, and the two periods' differing coverage is one of them —
    a difference between them is partly a difference in what survived exclusion."""
    before = _period([_slot(1.40), _slot(WORST_MEASURED_HIGH)])
    after = _period([_slot(1.30)])
    reason = percent_improvement(before, after).reason
    assert "1 of 2" in reason
    assert "1 of 1" in reason
    assert DERIVED_TR_METHOD in reason


def test_a_refusal_is_a_return_value_and_never_an_exception() -> None:
    """Honesty rule 1: a refusal is not an error. `NO_DIAGNOSIS` is the modal outcome on this
    data — 5,309 slots against 674 faulted — so a caller has a well-formed answer to render,
    not a failure to handle. Raising would put the platform's commonest honest answer down the
    error path and into a red card."""
    nothing_survived = _period([_slot(WORST_MEASURED_HIGH), _slot(WORST_MEASURED_LOW)])
    assert isinstance(baseline(nothing_survived), Refusal)
    assert isinstance(
        percent_improvement(nothing_survived, nothing_survived), Refusal
    )


def test_a_refusal_cannot_acquire_a_number_downstream() -> None:
    """The figure a refusal travels as is an absence, and `Figure` cannot hold a value and an
    absence at once — so no rendering path can turn *"no baseline exists"* into `0`."""
    figure = baseline().as_figure()
    assert figure.basis == Basis.ABSENT
    assert figure.render_value() == "not computable from this window"
    assert "Q21" in (figure.note or "")


# ── the bands: 1.40 is poor, and poor is not broken ───────────────────────────

def test_the_healthiest_measured_month_is_poor_performance_and_not_a_bad_sensor() -> None:
    """The whole point of `Q21`. Against the design band alone, 1.40 looks like an instrument
    fault; against the sourced poor-but-real band of 1.3–2.4 it is genuine performance. A
    machine dismissed as a bad sensor is one nobody fixes."""
    verdict = classify(HEALTHIEST_MEASURED_MONTH)
    assert verdict.band is Band.POOR_BUT_REAL
    assert verdict.band is not Band.SUSPECT_INSTRUMENT
    assert verdict.is_readable, "poor-but-real is real, so it belongs in the period figure"
    assert "genuine performance, not an instrument fault" in verdict.reason


def test_a_design_band_reading_is_recorded_and_deliberately_not_scored() -> None:
    """`Q70`: no document says the 0.65–0.85 band belongs to *these* machines rather than to
    water-cooled centrifugals in general. Calling a reading inside it good would be scoring one
    plant against another machine's nameplate."""
    verdict = classify(0.75)
    assert verdict.band is Band.WITHIN_DESIGN_BAND
    assert "Recorded, not scored" in verdict.reason
    assert "Q70" in verdict.reason


def test_the_gap_between_the_two_sourced_bands_is_unclassified_not_ranked() -> None:
    """1.0 sits above the design band's 0.85 and below poor-but-real's 1.3. The knowledge base
    names no band there, so the reading is counted and not ranked — ranking it would need
    boundaries nobody has agreed, which is an invented number wearing a verdict."""
    verdict = classify(1.0)
    assert verdict.band is Band.UNNAMED_BY_THE_SOURCE
    assert verdict.is_readable
    assert "names no band here" in verdict.reason
    assert "0.85" in verdict.reason and "1.3" in verdict.reason


def test_a_suspect_instrument_and_an_impossible_reading_stay_two_findings() -> None:
    """Both are excluded, and they are not the same fact. Above ~5 kW/TR the first move is to
    compare siblings at the panel; above 10 it is a transmitter loop. Collapsing them would
    send the operator's job to instrumentation or the reverse."""
    suspect = classify(7.0)
    impossible = classify(147.0)
    assert suspect.band is Band.SUSPECT_INSTRUMENT
    assert impossible.band is Band.IMPOSSIBLE
    assert suspect.finding is not None and suspect.finding.route is Route.OPERATOR
    assert impossible.finding is not None
    assert impossible.finding.route is Route.INSTRUMENTATION


def test_a_negative_efficiency_is_absent_rather_than_small() -> None:
    """Constraint 19, and the distinction that makes it safe: chiller 1's current *residual*
    sits at a median of −25.645 and that is a reading, because a residual is a signed
    deviation. An efficiency has a physical floor, so −6,265 is an absent reading — `ABS()`
    here would let the collapse count as a very good month."""
    verdict = classify(WORST_MEASURED_LOW)
    assert verdict.band is Band.INVALID_NEGATIVE
    assert not verdict.is_readable


def test_exactly_zero_is_a_stopped_machine_and_never_perfect_efficiency() -> None:
    """~23,800 of 31,884 slots on chiller 1 read zero across every signal at once — roughly a
    25% duty cycle. Averaged in, an idle machine would drag every monthly figure toward zero
    and read as the best plant in the country."""
    verdict = classify(0.0)
    assert verdict.band is Band.NOT_RUNNING
    assert not verdict.is_readable
    assert "stopped machine or a collapsed numerator" in verdict.reason


# ── exclusion: thrown away, counted, and explained ────────────────────────────

def test_invalid_slots_are_excluded_rather_than_averaged_in() -> None:
    """The measured failure, in one assertion. Three real slots at 1.40 alongside the two
    extremes chiller 1 actually reached: the figure is 1.40, and the naive mean over all five
    is in the thousands — wrong by two orders of magnitude, not by a margin."""
    values = [1.40, 1.40, 1.40, WORST_MEASURED_HIGH, WORST_MEASURED_LOW]
    period = _period([_slot(v) for v in values])

    assert period.included_count == 3
    assert period.mean_of_slot_ratios == pytest.approx(1.40)
    assert len(period.excluded) == 2
    assert sum(values) / len(values) > 4_000, (
        "the naive mean this test exists to prevent — if it ever stops being absurd, the "
        "extremes are no longer the ones chiller 1 measured"
    )


def test_the_count_excluded_travels_with_the_figure() -> None:
    """`E1` is only reportable on the strength of this sentence. A monthly kW/TR computed over
    a window whose transmitter had collapsed is confidently wrong, and the exclusion count is
    what lets a reader see that it did not happen here."""
    period = _period([_slot(1.40), _slot(WORST_MEASURED_HIGH), _slot(WORST_MEASURED_LOW)])
    note = period.as_figure().note or ""
    assert "2 of 3 slots were excluded rather than averaged in" in note
    assert "below the physical floor of zero" in note
    assert "the denominator had collapsed" in note


def test_the_exclusion_note_is_never_optional_even_on_a_clean_window() -> None:
    """*"No slot was excluded"* is a claim a reader can check. A blank there is
    indistinguishable from a figure whose exclusions were never computed."""
    note = _period([_slot(1.40)]).exclusion_note()
    assert "No slot was excluded" in note
    assert "1 slots in this window" in note


def test_every_excluded_slot_carries_a_sentence_and_not_a_bare_count() -> None:
    """*"1,204 slots excluded"* is a statistic. *"1,204 excluded because the denominator had
    collapsed"* is a data-quality work order."""
    period = _period([_slot(WORST_MEASURED_HIGH), _slot(WORST_MEASURED_LOW), _slot(0.0)])
    for slot in period.excluded:
        assert slot.reason.strip(), f"{slot.band} was excluded without saying why"
        assert slot.render().strip()


def test_every_excluded_band_has_a_sentence_waiting_for_it() -> None:
    """A guard against a future band joining the excluded set without a phrase. The period note
    looks its band up by name, so the omission would surface as a `KeyError` while rendering a
    monthly figure rather than as a failure here."""
    assert set(EXCLUSION_SUMMARY) >= EXCLUDED_BANDS


def test_coverage_is_reported_because_no_minimum_was_ever_agreed() -> None:
    """`Q69`. A fraction chosen here would silently suppress real figures on a threshold nobody
    agreed — the mirror image of the failure this module exists for. `None` rather than `0.0`,
    so *"no fraction is agreed"* and *"any coverage will do"* stay different statements."""
    assert MIN_VALID_COVERAGE is None
    period = _period([_slot(1.40), _slot(WORST_MEASURED_HIGH)])
    assert period.coverage == pytest.approx(0.5)
    assert "Q69" in period.coverage_note()
    assert "reported rather than used to suppress the figure" in period.coverage_note()


def test_the_period_states_its_window() -> None:
    """Constraint 15. Anomaly counts were once shown on the database wall clock under a heading
    describing a telemetry window that did not overlap it at all."""
    rendered = _period([_slot(1.40)]).render()
    assert "2026-04-15" in rendered
    assert "2026-06-23" in rendered


# ── derived from derived ──────────────────────────────────────────────────────

def test_the_derived_slot_count_is_the_measured_one() -> None:
    """7,670 of the re-clone's 12,589 derived slots fall **inside** the measured window, so no
    window boundary protects a figure from them the way the clip protected it from the
    simulation."""
    assert DERIVED_SLOTS_IN_MEASURED_WINDOW == DERIVED_IN_WINDOW


def test_derived_cooling_output_is_held_out_unless_a_caller_asks_by_name() -> None:
    """*Derived may be quoted, simulated may not* — but quoting requires a label, and no
    rendering path attaches one yet. The quiet path has to be the honest one, so the default
    holds them back rather than folding them in."""
    period = _period([_slot(1.40, basis=InputBasis.DERIVED), _slot(1.40)])
    assert period.included_count == 1
    assert len(period.derived_held) == 1
    assert period.derived_included is False
    assert DERIVED_TR_METHOD in period.derived_held[0].reason


def test_a_held_out_derived_slot_says_it_was_credible_rather_than_invalid() -> None:
    """Two different reasons a slot is not in the figure: nobody could believe it, and nobody
    asked for it in a form it may be quoted in. Held out under the wrong sentence, a derived
    slot reads as a broken transmitter and somebody goes to check one."""
    held = _period([_slot(1.40, basis=InputBasis.DERIVED)]).derived_held[0]
    assert held.band is Band.POOR_BUT_REAL
    assert "the reading is credible" in held.reason
    assert "no caller asked for that" in held.reason


def test_an_efficiency_built_on_derived_cooling_output_says_it_is_derived_from_derived() -> None:
    """`tr` for these slots was computed by `derived:tr_from_load_v1`, so an efficiency over
    them is a derivation of a derivation. It carries the method name, because *"some slots were
    derived"* is not something a reader can check and a method name is."""
    period = _period(
        [_slot(1.40, basis=InputBasis.DERIVED), _slot(1.40)], include_derived=True
    )
    figure = period.as_figure()
    assert period.derived_in_figure == 1
    assert period.derived_included is True
    assert figure.basis == Basis.DERIVED
    assert "derived from derived" in (figure.note or "")
    assert DERIVED_TR_METHOD in (figure.note or "")


def test_a_wholly_measured_figure_is_not_labelled_derived() -> None:
    """The label has to mean something. If every figure carried it, nobody would read it —
    which is how a provenance marker stops being one."""
    figure = _period([_slot(1.40), _slot(1.50)]).as_figure()
    assert figure.basis == Basis.MEASURED
    assert "derived from derived" not in (figure.note or "")


def test_the_derived_hold_out_survives_at_the_measured_scale() -> None:
    """The real proportion: 7,670 derived slots inside a window of 31,884. Coverage drops to
    76% and the reader is told, rather than being handed a figure that looks like the whole
    month."""
    readings = [_slot(1.40, basis=InputBasis.DERIVED) for _ in range(DERIVED_IN_WINDOW)]
    readings += [_slot(1.40) for _ in range(IN_WINDOW_SLOTS - DERIVED_IN_WINDOW)]
    period = _period(readings)

    assert period.slot_count == IN_WINDOW_SLOTS
    assert len(period.derived_held) == DERIVED_IN_WINDOW
    assert period.coverage == pytest.approx(0.7594, abs=1e-4)
    assert "7,670 slots were held out" in period.exclusion_note()


# ── the mean of the ratios is not the ratio of the totals ─────────────────────

def test_the_load_weighted_figure_is_not_the_mean_of_the_slot_ratios() -> None:
    """A slot at a trickle of load weighs the same as a slot at full load. Over one slot at
    100 kW per 100 TR and one at 1 kW per 2 TR the mean of the ratios is 0.75 and the plant
    figure is 0.99 — and only the second means what a reader thinks it means."""
    period = _period(
        [
            SlotReading.from_inputs(SLOT, kw=100.0, tr=100.0, tr_basis=InputBasis.MEASURED),
            SlotReading.from_inputs(SLOT, kw=1.0, tr=2.0, tr_basis=InputBasis.MEASURED),
        ]
    )
    assert period.mean_of_slot_ratios == pytest.approx(0.75)
    assert period.load_weighted_figure().value == pytest.approx(101 / 102)
    assert period.as_figure().label != period.load_weighted_figure().label


def test_neither_figure_is_silently_substituted_for_the_other() -> None:
    """Both are offered and each is labelled. Substituting one would answer a narrower
    question than the one asked while looking like an answer to it."""
    period = _period([_slot(1.40, kw=140.0, tr=100.0)])
    assert "mean slot efficiency" in period.as_figure().label
    assert "load-weighted efficiency" in period.load_weighted_figure().label


def test_the_load_weighted_figure_is_absent_when_the_totals_cannot_be_summed() -> None:
    """The historian sometimes carries the ratio alone. A partial sum over the slots that do
    have both inputs would be a plant figure for a different plant."""
    period = _period([_slot(1.40, kw=140.0, tr=100.0), _slot(1.50)])
    figure = period.load_weighted_figure()
    assert figure.value is None
    assert "not both recorded on every surviving slot" in (figure.note or "")


# ── absences that must not collapse into one ──────────────────────────────────

def test_a_window_with_no_slots_is_not_a_window_whose_slots_all_failed() -> None:
    """**Found by this test.** Both returned `NOT_COMPUTABLE` — *"no valid slot in this window
    to compute from"* — so a question about a period the snapshot does not cover was
    indistinguishable from a month the transmitters had destroyed. One of those sends somebody
    to instrumentation; the other should send them to the date picker."""
    empty = _period([])
    destroyed = _period([_slot(WORST_MEASURED_HIGH), _slot(WORST_MEASURED_LOW)])

    assert empty.as_figure().absence == Absence.NO_DATA
    assert destroyed.as_figure().absence == Absence.NOT_COMPUTABLE
    assert empty.as_figure().absence != destroyed.as_figure().absence


def test_the_two_empty_windows_read_differently_to_a_person_as_well() -> None:
    """The absence code is what a surface renders; the words are what a reader acts on. Both
    have to separate, or the distinction survives only in the payload."""
    assert _period([]).as_figure().render_value() == "no data in this window"
    assert "no slots at all fell in this window" in _period([]).coverage_note()

    destroyed = _period([_slot(WORST_MEASURED_HIGH)])
    assert destroyed.as_figure().render_value() == "not computable from this window"
    assert "1 of 1 slots were excluded" in destroyed.exclusion_note()


def test_an_unreportable_window_renders_words_and_never_a_zero() -> None:
    """Honesty rule 2. `0` in a kW/TR column reads as a machine consuming nothing, which is the
    opposite of *"we could not compute this"*."""
    figure = _period([_slot(WORST_MEASURED_HIGH)]).as_figure()
    assert figure.value is None
    assert figure.as_dict()["value"] is None
    assert figure.render_value() not in {"0", "0.00", "—", ""}


def test_coverage_on_an_empty_window_is_none_and_not_zero() -> None:
    """0% coverage says every slot was thrown away. No slots at all says nothing about the
    instrument, and only one of those is a finding."""
    assert _period([]).coverage is None
    assert _period([_slot(WORST_MEASURED_HIGH)]).coverage == 0.0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEFECT, recorded rather than papered over: a window whose every slot was credible but "
        "derived reports NOT_COMPUTABLE — 'no valid slot in this window to compute from'. The "
        "slots were valid; the figure was withheld for want of a label and is recoverable by "
        "asking for derived slots by name. Fixing it needs an absence code honesty.py does not "
        "have, and honesty.py belongs to another task. The exclusion note does carry the true "
        "reason, so the defect is in the machine-readable claim, not in the prose."
    ),
)
def test_a_window_held_back_for_a_label_is_not_a_window_that_could_not_be_computed() -> None:
    """Third absence, collapsed into the second. *"We could not compute this"* and *"we can, and
    will once you accept the label"* send a reader to different places — the first to the
    transmitters, the second back with one more argument."""
    held = _period([_slot(1.40, basis=InputBasis.DERIVED)])
    assert held.included_count == 0
    assert held.as_figure().absence != Absence.NOT_COMPUTABLE


def test_the_two_kinds_of_withheld_slot_are_counted_separately() -> None:
    """What the defect above does *not* reach. Unbelievable and unlabelled are separate tuples
    and separate counts, so a caller can act on them differently even while the absence code
    conflates the empty cases."""
    period = _period([_slot(WORST_MEASURED_HIGH), _slot(1.40, basis=InputBasis.DERIVED)])
    payload = period.as_dict()
    assert payload["excluded_count"] == 1
    assert payload["derived_held_count"] == 1
    assert payload["derived_included"] is False


# ── a slot with no efficiency says why ────────────────────────────────────────

def test_a_slot_with_no_efficiency_and_no_reason_cannot_be_constructed() -> None:
    """Constraint 14 in the constructor rather than in a docstring: a figure is a value or a
    stated absence, never neither. *"Leave it blank and move on"* is unrepresentable here, not
    merely discouraged."""
    with pytest.raises(ValueError, match="say one thing"):
        SlotReading(SLOT, None, InputBasis.MEASURED)


def test_a_collapsed_cooling_output_gives_an_undefined_efficiency_not_an_enormous_one() -> None:
    """Where the plant's whole efficiency defect enters. With `tr` at zero the quotient is
    enormous rather than undefined, and an enormous number averages into a monthly figure
    without complaint — this is how 30,183 got in."""
    reading = SlotReading.from_inputs(SLOT, kw=180.0, tr=0.0, tr_basis=InputBasis.MEASURED)
    assert reading.kw_per_tr is None
    assert "it is undefined" in reading.absence_reason
    assert "absent reading rather than a small one" in reading.absence_reason


def test_a_missing_input_names_which_input_was_missing() -> None:
    """*"No efficiency for this slot"* is a dead end. Naming power or cooling output tells
    whoever reads it which signal to go and look at."""
    no_power = SlotReading.from_inputs(SLOT, kw=None, tr=100.0, tr_basis=InputBasis.MEASURED)
    no_cooling = SlotReading.from_inputs(SLOT, kw=180.0, tr=None, tr_basis=InputBasis.MEASURED)
    assert "power was not recorded" in no_power.absence_reason
    assert "cooling output was not recorded" in no_cooling.absence_reason


def test_a_slot_that_was_never_computed_is_excluded_carrying_its_own_reason() -> None:
    """The reason the caller gave survives into the period's exclusion list. Replacing it with
    a generic phrase would lose the only account of what happened at that slot."""
    reading = SlotReading.from_inputs(SLOT, kw=180.0, tr=0.0, tr_basis=InputBasis.MEASURED)
    period = _period([reading])
    assert period.excluded[0].band is Band.NOT_READ
    assert "it is undefined" in period.excluded[0].reason


# ── the sourced numbers are the sourced numbers ───────────────────────────────

def test_the_design_band_is_the_one_the_source_states() -> None:
    """`CONTEXT.md` §10a. A drifted threshold reads as a measurement, which is why the bands
    are held in one place and asserted against the document here."""
    assert DESIGN_BAND == (0.65, 0.85)
    assert HEALTHIEST_MEASURED_MONTH == 1.40


def test_the_healthiest_measured_month_sits_outside_the_design_band() -> None:
    """The single fact that makes `E1` undeliverable as specified. If these ever overlapped,
    `Q21` would have an answer and the refusals above would be over-caution rather than
    honesty."""
    assert DESIGN_BAND[1] < HEALTHIEST_MEASURED_MONTH
    assert classify(HEALTHIEST_MEASURED_MONTH).band is not Band.WITHIN_DESIGN_BAND
    assert efficiency.validity.is_poor_but_real(HEALTHIEST_MEASURED_MONTH)
