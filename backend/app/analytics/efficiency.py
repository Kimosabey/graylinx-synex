"""`E1` efficiency baseline and kW/TR tracking — and the baseline this refuses to draw.

**The failure, and it already happened here.** Both chilled-water flow transmitters have read
near zero since May while ΔT and power stayed normal. Efficiency is computed from flow, so
`kw_per_tr` on chiller 1 ranges from **−6,265 to +30,183**, and two months of efficiency
figures were invalid before anyone noticed. Average those slots into a monthly figure and the
number is not slightly wrong: against a design band of **0.65–0.85**, a slot driven by a
collapsed denominator is *"wrong by two orders of magnitude, not by a margin"*. So the first
thing this module does is throw slots away — and the period figure it returns cannot be read
without the count that were thrown away and the reason each one went.

**What `E1` asked for, and the half that cannot be delivered.** `CONTEXT.md` §10a is explicit:
design band 0.65–0.85, healthiest **measured** month **1.40**, therefore *"there is no
defensible baseline yet, so `E1` cannot be built as specified. `Q21`."* Two of the three
candidate baselines fail for different reasons, and neither failure is fixable by arithmetic:

| Candidate baseline | Why it is not one |
|---|---|
| The design band | It is a nameplate expectation for a class of machine, not a fitted
  reference for these two assets. Models are fitted per asset here for exactly this reason —
  0.0 is `HIGH` on chiller 1 and `NORMAL` on chiller 2 |
| The healthiest measured month | 1.40 sits inside the sourced *poor-but-real* band, so it is
  genuine performance rather than an instrument fault — and a period drawn from a window whose
  flow signal had already collapsed cannot anchor anything |

A baseline computed from a period that is itself invalid is the reassuring lie in numeric
form, and a *"% improvement"* against it inherits every defect silently while looking like
measurement. So `baseline()` and `percent_improvement()` exist, are callable, and return a
`Refusal` that names `Q21`. **A refusal is not an error** — neither raises.

**Derived from derived.** `kw_per_tr` needs cooling output, and the 2026-08-17 re-clone marks
`tr` as **derived** for **7,670** slots inside the measured window, all carrying the method
`derived:tr_from_load_v1`. An efficiency computed from a derived cooling output is a
derivation of a derivation. The inherited rule is *derived may be quoted, simulated may not*,
but quoting requires a label — so derived slots are **held out by default**, counted, and
folded in only when a caller asks in so many words.

**One more thing the arithmetic hides.** The mean of a per-slot ratio is not the ratio of the
totals: a slot at a trickle of load weighs the same as a slot at full load. Both figures are
offered and neither is silently substituted for the other, because `Σkw ÷ Σtr` is the
defensible plant figure and it needs both inputs per slot rather than the ratio alone.

Pure functions and frozen dataclasses. Contract 3 keeps `app.analytics` free of a driver, of
settings and of a model client; nothing here calls a model, and the language model never sets
a band, a baseline or an exclusion.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.analytics import validity
from app.analytics.honesty import Absence, Figure
from app.analytics.validity import ValidityFinding, Verdict

# ── sourced numbers ─────────────────────────────────────────────────────────────
# The three bands that judge a reading — instrument-suspect, impossible, poor-but-real —
# live in `validity.py` and are referenced by name below. They are not restated here:
# CLAUDE.md §2.8, one source of truth per fact, applies to a threshold more than to anything
# else, because a duplicated threshold drifts silently and the drift reads as a measurement.

#: *"design band 0.65–0.85"* — `CONTEXT.md` §10a. Held as data because a classification needs
#: a boundary, and `validity.py` quotes the figure inside its own reasoning without holding a
#: constant for it.
#:
#: **It is a design expectation, not a target and not a baseline.** Nothing in this module
#: scores a machine against it, reports a shortfall from it, or treats a reading inside it as
#: an achievement. `Q68`: no document states whether these two chillers' nameplates carry this
#: band or whether it is a generic figure for water-cooled centrifugal machines, and the
#: difference decides whether it may ever anchor a per-asset comparison.
DESIGN_BAND: tuple[float, float] = (0.65, 0.85)

#: The healthiest month the plant has actually recorded — `CONTEXT.md` §10a. Quoted in the
#: baseline refusal so the reader can see the gap rather than take it on trust. It falls inside
#: validity's poor-but-real band, which is what makes it real performance and `Q21` a question
#: about the plant rather than about the instrument.
HEALTHIEST_MEASURED_MONTH: float = 1.40

#: The method on every row of `snapshot_derived_slots`. Named in the hold-out reason, because
#: *"some slots were derived"* is not something a reader can check and a method name is.
DERIVED_TR_METHOD: str = "derived:tr_from_load_v1"

#: Derived slots falling inside the measured window — `CONTEXT.md` §9. Unlike the 156,129
#: simulated slots the re-clone removed, these are **inside** the window rather than kept out
#: of it by the clip, so no window boundary protects a figure from them.
DERIVED_SLOTS_IN_MEASURED_WINDOW: int = 7_670

#: The valid-slot coverage below which a period figure should not be offered at all.
#:
#: TBD (Q67): no document states one, and none is invented. A fraction chosen here would
#: silently suppress real figures on a threshold nobody agreed, which is the mirror image of
#: the failure this module exists for — so coverage is **reported** with every figure instead.
#: `None` rather than `0.0`, so that *"no fraction is agreed"* and *"any coverage will do"*
#: stay distinguishable to a reader and to a caller.
MIN_VALID_COVERAGE: float | None = None


class InputBasis(StrEnum):
    """What the cooling output underneath a reading rests on.

    Stated per slot rather than per window, because the derived slots are inside the measured
    window and a window-level flag cannot see them — `C26` applied one signal further down.
    """

    MEASURED = "measured"
    DERIVED = "derived"
    """Computed by `derived:tr_from_load_v1` from signals the plant does measure. Weaker than
    measured and reported separately, never absorbed into it."""


class Band(StrEnum):
    """Where a reading falls against the sourced bands. A verdict about the *reading*."""

    NOT_READ = "not_read"
    """No efficiency was computed for this slot, and the reason travels with it."""

    INVALID_NEGATIVE = "invalid_negative"
    """Below a physical floor. **Absent, not small** — inherited constraint 19."""

    NOT_RUNNING = "not_running"
    """Exactly zero. A running machine cannot consume no power per ton of cooling, so this is
    a stopped machine or a collapsed numerator — never perfect efficiency."""

    WITHIN_DESIGN_BAND = "within_design_band"
    """Inside the design expectation. Recorded, and deliberately not called good — see
    `DESIGN_BAND` and `Q68`."""

    POOR_BUT_REAL = "poor_but_real"
    """Genuinely poor performance rather than a measurement fault. Saying so is what stops an
    inefficient machine being dismissed as a bad sensor."""

    UNNAMED_BY_THE_SOURCE = "unnamed_by_the_source"
    """Credible, and in a region the knowledge base does not name. Reported as unclassified
    rather than ranked, because ranking it would need boundaries nobody has agreed."""

    SUSPECT_INSTRUMENT = "suspect_instrument"
    """The denominator is collapsing — check flow and ΔT before the compressor."""

    IMPOSSIBLE = "impossible"
    """Not a bad score, an impossible one."""


#: Bands whose readings are left out of a period figure rather than averaged into it.
#:
#: Held as data so the decision is inspectable in one place. The incident: both chilled-water
#: flow transmitters read near zero from May while ΔT and power stayed normal, and the
#: resulting slots quietly invalidated two months of efficiency figures — a mean taken over
#: them is not a worse estimate of the truth, it is a different number altogether.
EXCLUDED_BANDS: frozenset[Band] = frozenset(
    {
        Band.NOT_READ,
        Band.INVALID_NEGATIVE,
        Band.NOT_RUNNING,
        Band.SUSPECT_INSTRUMENT,
        Band.IMPOSSIBLE,
    }
)

#: The short phrase a *period* figure carries per excluded band. The long form stays on each
#: `ExcludedSlot`: a reader scanning a monthly figure needs the shape of the exclusion, and
#: whoever investigates it needs the slot and the sentence.
EXCLUSION_SUMMARY: dict[Band, str] = {
    Band.NOT_READ: "no efficiency was computed for the slot",
    Band.INVALID_NEGATIVE: "below the physical floor of zero — absent, not small",
    Band.NOT_RUNNING: "exactly zero — the machine was off, not efficient",
    Band.SUSPECT_INSTRUMENT: "above the threshold where the instrument is the likely fault",
    Band.IMPOSSIBLE: "impossible rather than poor — the denominator had collapsed",
}


@dataclass(frozen=True)
class Classification:
    """One reading's band, with the words that put it there."""

    band: Band
    reason: str
    finding: ValidityFinding | None = None
    """The cross-signal verdict, where `F16` produced one. Carried rather than flattened, so
    a caller can route an instrument fault to instrumentation instead of to a crew."""

    @property
    def is_readable(self) -> bool:
        """May this reading enter a period figure at all?"""
        return self.band not in EXCLUDED_BANDS


def classify(kw_per_tr: float | None, absence_reason: str = "") -> Classification:
    """Place one reading against the sourced bands, in the playbook's own reading order.

    *"Can the inputs be believed?"* comes first — `validity.check_efficiency` is asked before
    anything else, because interpreting a number before checking whether it can be believed is
    the ordering that produced two months of invalid efficiency figures.
    """
    if kw_per_tr is None:
        return Classification(
            Band.NOT_READ,
            absence_reason
            or "no efficiency was computed for this slot, and no reason was recorded for it",
        )

    finding = validity.check_efficiency(kw_per_tr)
    if finding is not None:
        return Classification(_band_for(finding, kw_per_tr), finding.reason, finding)

    if kw_per_tr == 0:
        return Classification(
            Band.NOT_RUNNING,
            "reads exactly zero. A running machine cannot consume no power per ton of "
            "cooling, so this slot is a stopped machine or a collapsed numerator — roughly "
            "23,800 of 31,884 slots on chiller 1 read zero across every signal at once.",
        )

    low, high = DESIGN_BAND
    if low <= kw_per_tr <= high:
        return Classification(
            Band.WITHIN_DESIGN_BAND,
            f"reads {kw_per_tr}, inside the design band of {low}-{high}. Recorded, not scored: "
            f"the band is a nameplate expectation for a class of machine and no document says "
            f"it is this asset's (Q68).",
        )

    if validity.is_poor_but_real(kw_per_tr):
        poor_low, poor_high = validity.EFFICIENCY_POOR_BUT_REAL
        return Classification(
            Band.POOR_BUT_REAL,
            f"reads {kw_per_tr}, inside the sourced poor-but-real band of {poor_low}-"
            f"{poor_high}. This is genuine performance, not an instrument fault — the "
            f"plant's healthiest measured month sits here at {HEALTHIEST_MEASURED_MONTH}.",
        )

    return Classification(Band.UNNAMED_BY_THE_SOURCE, _unnamed_reason(kw_per_tr))


def _band_for(finding: ValidityFinding, kw_per_tr: float) -> Band:
    """Map `F16`'s verdict onto a band.

    `IMPLAUSIBLE_EFFICIENCY` covers both the suspect and the impossible case, so the split is
    made against `validity`'s own constant rather than against a number written again here.
    """
    if finding.verdict is Verdict.INVALID_NEGATIVE:
        return Band.INVALID_NEGATIVE
    if kw_per_tr > validity.EFFICIENCY_IMPOSSIBLE_ABOVE:
        return Band.IMPOSSIBLE
    return Band.SUSPECT_INSTRUMENT


def _unnamed_reason(kw_per_tr: float) -> str:
    """Say which two sourced bands the reading falls between, and claim nothing else."""
    design_low, design_high = DESIGN_BAND
    poor_low, poor_high = validity.EFFICIENCY_POOR_BUT_REAL

    if kw_per_tr < design_low:
        neighbours = f"below the design band's floor of {design_low}"
    elif kw_per_tr < poor_low:
        neighbours = (
            f"between the design band's ceiling of {design_high} and the poor-but-real "
            f"floor of {poor_low}"
        )
    else:
        neighbours = (
            f"between the poor-but-real ceiling of {poor_high} and the threshold where the "
            f"instrument becomes the likely fault"
        )
    return (
        f"reads {kw_per_tr}, {neighbours}. The knowledge base names no band here, so the "
        f"reading is credible and unclassified — it is counted, and it is not ranked."
    )


@dataclass(frozen=True)
class SlotReading:
    """One slot's efficiency, and what its inputs rest on.

    `kw` and `tr` are optional because the historian sometimes carries the ratio alone. When
    both are present the period can report `Σkw ÷ Σtr`, which is a different and better
    question than the mean of the ratios.
    """

    slot_time: datetime
    kw_per_tr: float | None
    tr_basis: InputBasis
    absence_reason: str = ""
    kw: float | None = None
    tr: float | None = None

    def __post_init__(self) -> None:
        """A missing reading states why. An absence is not a zero and not a dash.

        Enforced in the constructor rather than asked for in a docstring, on the same
        reasoning as `honesty.Figure`: it makes *"leave it blank and move on"*
        unrepresentable rather than discouraged.
        """
        if self.kw_per_tr is None and not self.absence_reason.strip():
            raise ValueError(
                f"the slot at {self.slot_time:%Y-%m-%d %H:%M} has no efficiency and no reason "
                f"for its absence — say one thing"
            )

    @classmethod
    def from_inputs(
        cls,
        slot_time: datetime,
        *,
        kw: float | None,
        tr: float | None,
        tr_basis: InputBasis,
    ) -> SlotReading:
        """Divide power by cooling output, refusing a collapsed denominator in words.

        This is where the reference plant's whole efficiency defect enters: with `tr` at or
        near zero the quotient is enormous rather than undefined, and an enormous number
        averages into a monthly figure without complaint. Constraint 19 applies — cooling
        output has a physical floor of zero, so a value at or below it is absent, not small.
        """
        if kw is None or tr is None:
            missing = "power" if kw is None else "cooling output"
            return cls(
                slot_time,
                None,
                tr_basis,
                absence_reason=f"{missing} was not recorded for this slot, so no efficiency "
                f"exists for it",
                kw=kw,
                tr=tr,
            )
        if tr <= 0:
            return cls(
                slot_time,
                None,
                tr_basis,
                absence_reason=f"cooling output reads {tr} TR, so efficiency is not a large "
                f"number — it is undefined. A cooling output has a physical floor of zero, "
                f"and a value at or below it is an absent reading rather than a small one",
                kw=kw,
                tr=tr,
            )
        return cls(slot_time, kw / tr, tr_basis, kw=kw, tr=tr)


@dataclass(frozen=True)
class ExcludedSlot:
    """A slot left out of a period figure, and the sentence that left it out.

    Never a bare count. *"1,204 slots excluded"* is a statistic; *"1,204 excluded because the
    denominator had collapsed"* is a data-quality work order.
    """

    slot_time: datetime
    value: float | None
    band: Band
    reason: str

    def render(self) -> str:
        return f"{self.slot_time:%Y-%m-%d %H:%M} — {self.reason}"


@dataclass(frozen=True)
class PeriodEfficiency:
    """One window's kW/TR tracking. `E1`'s deliverable half.

    Constructed by `summarise`. The exclusions are fields rather than a computation done
    somewhere else, so the figure and the reason it is trustworthy cannot be separated in
    transit — every rendering path here reports both.
    """

    equipment_key: str
    window_start: datetime
    window_end: datetime
    included: tuple[SlotReading, ...] = field(default_factory=tuple)
    excluded: tuple[ExcludedSlot, ...] = field(default_factory=tuple)
    derived_held: tuple[ExcludedSlot, ...] = field(default_factory=tuple)
    derived_included: bool = False
    """True only when a caller asked for derived slots by name. It changes the figure's basis
    and its label, never only its footnote."""

    @property
    def slot_count(self) -> int:
        return len(self.included) + len(self.excluded) + len(self.derived_held)

    @property
    def included_count(self) -> int:
        return len(self.included)

    @property
    def coverage(self) -> float | None:
        """Fraction of slots that survived. `None` on an empty window.

        Not `0.0`: a window with no slots at all and a window whose every slot was thrown away
        are different statements, and only one of them is about the instrument.
        """
        return self.included_count / self.slot_count if self.slot_count else None

    @property
    def mean_of_slot_ratios(self) -> float | None:
        """The arithmetic mean over surviving slots, and **not** the plant's efficiency.

        A slot at a trickle of load weighs the same as one at full load. `load_weighted_figure`
        is the defensible figure; this one is what a per-slot column can support, and it is
        labelled as such wherever it renders.
        """
        values = [r.kw_per_tr for r in self.included if r.kw_per_tr is not None]
        return sum(values) / len(values) if values else None

    @property
    def derived_in_figure(self) -> int:
        return sum(1 for r in self.included if r.tr_basis is InputBasis.DERIVED)

    def exclusion_note(self) -> str:
        """The count and the why, in words, for the period. Never optional.

        `E1` is only reportable at all on the strength of this sentence: a monthly kW/TR
        figure computed over a window whose flow transmitter had collapsed is confidently
        wrong, and the exclusion count is what lets a reader see that it did not happen here.
        """
        if not self.excluded and not self.derived_held:
            return (
                f"No slot was excluded — all {self.slot_count:,} slots in this window "
                f"classified as readable."
            )

        parts: list[str] = []
        for band in Band:
            group = [x for x in self.excluded if x.band is band]
            if group:
                parts.append(f"{len(group):,} {EXCLUSION_SUMMARY[band]}")

        note = ""
        if parts:
            note = (
                f"{len(self.excluded):,} of {self.slot_count:,} slots were excluded rather "
                f"than averaged in: {'; '.join(parts)}."
            )
        if self.derived_held:
            note += (
                f" A further {len(self.derived_held):,} slots were held out because cooling "
                f"output was computed by {DERIVED_TR_METHOD} rather than measured, and a "
                f"derived value may be quoted only with that label."
            )
        return note.strip()

    def coverage_note(self) -> str:
        """What the figure rests on, as a fraction, plus the fact that no floor is agreed."""
        if self.coverage is None:
            return "no slots at all fell in this window, so there is no coverage to report"
        return (
            f"the figure rests on {self.included_count:,} of {self.slot_count:,} slots "
            f"({self.coverage:.0%}); no minimum coverage has been agreed (Q67), so this is "
            f"reported rather than used to suppress the figure"
        )

    def _basis_note(self) -> str:
        if not self.derived_in_figure:
            return ""
        return (
            f" {self.derived_in_figure:,} of the included slots take their cooling output from "
            f"{DERIVED_TR_METHOD}, so this figure is derived from derived and carries that "
            f"label wherever it is shown."
        )

    def as_figure(self) -> Figure:
        """The period figure, carrying its exclusions and its coverage — or a stated absence.

        Inherited constraint 14: a figure is a value or a stated absence, never both and never
        neither. A window in which nothing survived exclusion is `NOT_COMPUTABLE`, which
        renders as words — never `0`, which would read as a machine consuming nothing.
        """
        label = f"mean slot efficiency, {self.equipment_key}"
        note = f"{self.exclusion_note()} {self.coverage_note()}{self._basis_note()}".strip()
        mean = self.mean_of_slot_ratios
        if mean is None:
            return Figure.absent(label, Absence.NOT_COMPUTABLE, unit="kW/TR", note=note)
        builder = Figure.derived if self.derived_in_figure else Figure.measured
        return builder(label, mean, "kW/TR", note=note, fmt=".2f")

    def load_weighted_figure(self) -> Figure:
        """`Σkw ÷ Σtr` over the surviving slots — the figure that means what a reader thinks.

        Absent with a reason whenever power and cooling output are not both present on every
        included slot, because a partial sum would silently answer a narrower question than
        the one asked.
        """
        label = f"load-weighted efficiency, {self.equipment_key}"
        note = f"{self.exclusion_note()} {self.coverage_note()}{self._basis_note()}".strip()

        if not self.included:
            return Figure.absent(label, Absence.NOT_COMPUTABLE, unit="kW/TR", note=note)
        if any(r.kw is None or r.tr is None for r in self.included):
            return Figure.absent(
                label,
                Absence.NOT_COMPUTABLE,
                unit="kW/TR",
                note=f"power and cooling output are not both recorded on every surviving "
                f"slot, so the totals cannot be summed and only the mean of the per-slot "
                f"ratios is available. {note}",
            )

        total_kw = sum(r.kw for r in self.included if r.kw is not None)
        total_tr = sum(r.tr for r in self.included if r.tr is not None)
        if total_tr <= 0:
            return Figure.absent(
                label,
                Absence.NOT_COMPUTABLE,
                unit="kW/TR",
                note=f"cooling output over this window totals {total_tr}, so efficiency is "
                f"undefined rather than large. {note}",
            )
        return Figure.derived(label, total_kw / total_tr, "kW/TR", note=note, fmt=".2f")

    def render(self) -> str:
        """Inherited constraint 15: every artefact states its data window.

        Anomaly counts were once shown on the database wall clock under a heading describing a
        telemetry window that did not overlap it at all.
        """
        return (
            f"{self.equipment_key} · {self.window_start:%Y-%m-%d} to "
            f"{self.window_end:%Y-%m-%d} · {self.as_figure().render()}"
        )

    def as_dict(self) -> dict:
        return {
            "equipment_key": self.equipment_key,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "slot_count": self.slot_count,
            "included_count": self.included_count,
            "excluded_count": len(self.excluded),
            "derived_held_count": len(self.derived_held),
            "derived_included": self.derived_included,
            "coverage": self.coverage,
            "exclusion_note": self.exclusion_note(),
            "coverage_note": self.coverage_note(),
            "figure": self.as_figure().as_dict(),
            "load_weighted": self.load_weighted_figure().as_dict(),
        }


def summarise(
    *,
    equipment_key: str,
    window_start: datetime,
    window_end: datetime,
    readings: Sequence[SlotReading],
    include_derived: bool = False,
) -> PeriodEfficiency:
    """Track one window's efficiency, excluding the slots that cannot be believed.

    **Validity is judged before provenance.** A slot that is both derived and impossible is
    counted as excluded rather than held out, because *"can the inputs be believed?"* is the
    first question and a derived reading of 30,183 is not a labelling problem.

    `include_derived` must be passed by name and is never a default — the same discipline
    `check_measured_window` applies to simulated slots, for the same reason: the quiet path
    has to be the honest one.
    """
    included: list[SlotReading] = []
    excluded: list[ExcludedSlot] = []
    derived_held: list[ExcludedSlot] = []

    for reading in readings:
        verdict = classify(reading.kw_per_tr, reading.absence_reason)
        if not verdict.is_readable:
            excluded.append(
                ExcludedSlot(reading.slot_time, reading.kw_per_tr, verdict.band, verdict.reason)
            )
            continue
        if reading.tr_basis is InputBasis.DERIVED and not include_derived:
            derived_held.append(
                ExcludedSlot(
                    reading.slot_time,
                    reading.kw_per_tr,
                    verdict.band,
                    f"the reading is credible ({verdict.band.value}), but its cooling output "
                    f"was computed by {DERIVED_TR_METHOD} rather than measured. An efficiency "
                    f"built on it is derived from derived, and no caller asked for that.",
                )
            )
            continue
        included.append(reading)

    return PeriodEfficiency(
        equipment_key=equipment_key,
        window_start=window_start,
        window_end=window_end,
        included=tuple(included),
        excluded=tuple(excluded),
        derived_held=tuple(derived_held),
        derived_included=include_derived,
    )


@dataclass(frozen=True)
class Refusal:
    """A figure this module will not produce, and the reason in words.

    A return value rather than an exception, because a refusal is not an error: the caller has
    a well-formed answer to render, and `NO_DIAGNOSIS` is the modal outcome on this data at
    5,309 slots against 674 faulted.
    """

    what: str
    question: str
    reason: str

    def as_figure(self) -> Figure:
        """The refusal as a figure, so it renders in a table without becoming a number.

        `Figure` cannot hold a value and an absence at once, so a refusal that travels this
        way cannot acquire a number downstream.
        """
        return Figure.absent(
            self.what,
            Absence.NOT_COMPUTABLE,
            unit="kW/TR",
            note=f"{self.reason} ({self.question})",
        )

    def render(self) -> str:
        return f"{self.what}: not produced. {self.reason} ({self.question})"


def baseline(period: PeriodEfficiency | None = None) -> Refusal:
    """`E1` asks for the baseline the FDD efficiency proxy is measured against. There is none.

    This returns the refusal instead of a number, and it takes the optional period so the
    refusal can be concrete about what was on offer. `CONTEXT.md` §10a: *"there is no
    defensible baseline yet, so `E1` cannot be built as specified. `Q21`."*

    The temptation is to take the healthiest measured month and call it the baseline. That is
    the failure in one step: the month is **1.40**, inside the sourced poor-but-real band, and
    it was measured over a window in which the chilled-water flow transmitters had already
    collapsed. Anchoring to it would make *"back to normal"* mean *"back to poor"*, permanently
    and invisibly.
    """
    design_low, design_high = DESIGN_BAND
    offered = ""
    if period is not None:
        offered = (
            f" The period offered here retains {period.included_count:,} of "
            f"{period.slot_count:,} slots after exclusion, which makes it a usable tracking "
            f"figure and still not a reference — the two are different claims."
        )
    return Refusal(
        what="efficiency baseline",
        question="Q21",
        reason=(
            f"No defensible baseline exists for these machines. The design band of "
            f"{design_low}-{design_high} is a nameplate expectation for a class of machine "
            f"rather than a fitted reference for this asset, and the healthiest month the "
            f"plant has actually measured is {HEALTHIEST_MEASURED_MONTH}, which sits inside "
            f"the sourced poor-but-real band. Neither can anchor a comparison, and a baseline "
            f"computed from a period that is itself invalid would read as a measurement while "
            f"being an assumption.{offered}"
        ),
    )


def percent_improvement(before: PeriodEfficiency, after: PeriodEfficiency) -> Refusal:
    """The percentage this will not compute, with all four reasons stated rather than one.

    Refused even when both periods are clean, because the arithmetic is not the problem. A
    percentage needs a reference to be a percentage *of*, and `Q21` says there is not one; the
    remaining three reasons would each be enough on their own.
    """
    return Refusal(
        what="efficiency improvement",
        question="Q21",
        reason=(
            f"No percentage is produced, for four reasons and any one of them is enough. "
            f"First, a percentage needs a baseline to be a percentage of, and none is "
            f"defensible. Second, the two periods rest on different ground — "
            f"{before.included_count:,} of {before.slot_count:,} slots against "
            f"{after.included_count:,} of {after.slot_count:,} — so a difference between them "
            f"is partly a difference in what survived exclusion. Third, the mean of a "
            f"per-slot ratio is not the ratio of the totals, and a percentage change between "
            f"two such means describes no physical quantity. Fourth, where cooling output was "
            f"computed by {DERIVED_TR_METHOD} the figure is derived from derived, and a "
            f"percentage strips the label off. Report the two windows with their exclusions "
            f"and let a reader compare them"
        ),
    )
