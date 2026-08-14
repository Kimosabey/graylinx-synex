"""The honesty layer — what an answer must state before it is allowed to state anything else.

Ported from the sibling implementation, where it is the single most valuable file, and adapted
to the facts measured on our own database. The type is domain-neutral; only the examples in
this docstring are ours.

**Why a type rather than an instruction.** A figure either has a value **or** a stated reason
for its absence — never both, never neither, and the constructor refuses anything else. The
sibling's justification is the whole argument: *"that is stronger than an instruction, because
an instruction is followed most of the time."* It makes "print a blank and move on"
unrepresentable rather than discouraged.

**Three measured properties of our own snapshot make an unguarded answer confidently wrong
rather than approximately wrong.** Each has a rule here.

1. **`cond_flow` has never recorded a non-zero value** — 0 of 31,884 measured readings on
   chiller 1, and the same on chiller 2. Four of the six models depend on it. So condenser
   flow and approach cannot be computed at all, and a figure absent for `NEVER_MEASURED`
   renders *the words* "never measured". It can never render `0` and never render `—`; those
   are three different claims and only one of them is true.

2. **`cond_leaving_temp` reads −273.2 °C** on 25 April, 14 May, 21 May and 5 June. That is
   absolute zero — a sensor reporting its own failure, not a temperature. It is
   `INSTRUMENT_INVALID`, and it must never be averaged into anything.

3. **`kw_per_tr` ranges from −6,265 to +30,183** on chiller 1, because efficiency was computed
   while flow was near zero. A figure that large is not a bad score, it is a meaningless one —
   so it is a stated absence rather than a number.

And one property of the database rather than the plant: **156,129 slots are simulated**, and
the simulation *invented* `cond_flow`. A window that is generated rather than measured is not
a lesser reading, it is a different claim, which is why provenance travels with the value
(`C26`) rather than with the window alone.

Pure functions and frozen dataclasses. No DB, no LLM, no I/O, and — enforced by contract 3 in
`importlinter.ini` — not even settings, because a pure function that reads a feature flag is
not a pure function.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class Basis:
    """Where a number came from. A reader's trust should follow this, not the decimal places.

    `DERIVED` carries the same weight as `MEASURED` — it is arithmetic over measured facts.
    `JUDGED` does not: a projection or an estimate is a model's opinion with a unit attached,
    and printing it in the same typeface as a meter reading is how a guess becomes a budget
    line.
    """

    MEASURED = "measured"
    DERIVED = "derived"
    JUDGED = "judged"
    ABSENT = "absent"


class Provenance:
    """How the reading came to exist. `C26`, and the reason it is per signal rather than per
    window.

    Marking a whole window *simulated* is one level too coarse. In our data every synthetic
    signal continues something the plant genuinely measures — except `cond_flow`, which the
    simulation fabricated. The first is a weaker reading; the second implies an
    instrumentation capability the site does not have, which is a different and worse claim.
    """

    MEASURED = "measured"
    SIMULATED = "simulated"
    NOT_INSTRUMENTED = "not_instrumented_here"


class Absence:
    """*Why* a figure is missing. `0`, `—` and "never measured" are three different statements.

    Collapsing them is the commonest way an answer lies without containing a false number: a
    blank in the condenser-flow row reads as "nothing to report", when the truth is that this
    plant has never had a working condenser flow meter.
    """

    NEVER_MEASURED = "never_measured"           # the tag exists; no credible value ever recorded
    INSTRUMENT_INVALID = "instrument_invalid"   # the tag reported provably impossible values
    NOT_COMPUTABLE = "not_computable"           # no valid slot in this window to compute from
    NOT_DIAGNOSABLE = "not_diagnosable"         # the detector was blind; absence != no fault
    NO_DATA = "no_data"                         # nothing recorded in this window at all
    NOT_MODELLED = "not_modelled"               # no model is fitted for this signal


_ABSENCE_TEXT = {
    Absence.NEVER_MEASURED: "never measured",
    Absence.INSTRUMENT_INVALID: "not measurable — the input reading is faulty",
    Absence.NOT_COMPUTABLE: "not computable from this window",
    Absence.NOT_DIAGNOSABLE: "not diagnosable — the detector was blind",
    Absence.NO_DATA: "no data in this window",
    Absence.NOT_MODELLED: "no model is fitted for this signal",
}

# Rendered next to a judged figure. Deliberately short: it appears inline, and the legend
# explains it once.
_JUDGED_SUFFIX = " (estimated)"

JUDGED_LEGEND = "Figures marked (estimated) rest on model judgement, not on a measurement."

# Rendered next to a figure that is not straightforwardly a measurement of this plant.
_PROVENANCE_SUFFIX = {
    Provenance.SIMULATED: " (simulated)",
    Provenance.NOT_INSTRUMENTED: " (not instrumented here)",
}


@dataclass(frozen=True)
class Figure:
    """One number, carrying what it rests on and — when it is missing — why.

    Construct through the classmethods. The invariant they enforce is the whole point of the
    type: a value **xor** an absence reason.
    """

    label: str
    value: float | None = None
    unit: str | None = None
    basis: str = Basis.MEASURED
    absence: str | None = None
    provenance: str = Provenance.MEASURED
    note: str | None = None
    fmt: str = ".3g"

    def __post_init__(self) -> None:
        if self.value is None and not self.absence:
            raise ValueError(
                f"figure {self.label!r} has no value and no absence reason — say one thing"
            )
        if self.value is not None and self.absence:
            raise ValueError(
                f"figure {self.label!r} has both a value ({self.value}) and an absence "
                f"reason ({self.absence}) — say one thing"
            )
        if self.absence and self.absence not in _ABSENCE_TEXT:
            raise ValueError(f"unknown absence reason: {self.absence!r}")
        if self.provenance not in (
            Provenance.MEASURED,
            Provenance.SIMULATED,
            Provenance.NOT_INSTRUMENTED,
        ):
            raise ValueError(f"unknown provenance: {self.provenance!r}")

    # ── constructors ────────────────────────────────────────────────────────────

    @classmethod
    def measured(
        cls,
        label: str,
        value: float,
        unit: str | None = None,
        *,
        note: str | None = None,
        fmt: str = ".3g",
    ) -> Figure:
        return cls(label, float(value), unit, Basis.MEASURED, note=note, fmt=fmt)

    @classmethod
    def derived(
        cls,
        label: str,
        value: float,
        unit: str | None = None,
        *,
        note: str | None = None,
        fmt: str = ".3g",
    ) -> Figure:
        return cls(label, float(value), unit, Basis.DERIVED, note=note, fmt=fmt)

    @classmethod
    def judged(
        cls,
        label: str,
        value: float,
        unit: str | None = None,
        *,
        note: str | None = None,
        fmt: str = ".3g",
    ) -> Figure:
        return cls(label, float(value), unit, Basis.JUDGED, note=note, fmt=fmt)

    @classmethod
    def simulated(
        cls,
        label: str,
        value: float,
        unit: str | None = None,
        *,
        note: str | None = None,
        fmt: str = ".3g",
    ) -> Figure:
        """A real measurement's synthetic continuation. Weaker than measured, and it says so."""
        return cls(
            label,
            float(value),
            unit,
            Basis.MEASURED,
            provenance=Provenance.SIMULATED,
            note=note,
            fmt=fmt,
        )

    @classmethod
    def absent(
        cls,
        label: str,
        absence: str,
        *,
        unit: str | None = None,
        note: str | None = None,
        provenance: str = Provenance.MEASURED,
    ) -> Figure:
        return cls(
            label, None, unit, Basis.ABSENT, absence=absence, provenance=provenance, note=note
        )

    @classmethod
    def never_measured(
        cls, label: str, *, unit: str | None = None, note: str | None = None
    ) -> Figure:
        """The strongest absence, and the one most often mis-rendered as zero.

        This is `cond_flow` on this plant: 0 of 31,884 measured readings.
        """
        return cls.absent(
            label,
            Absence.NEVER_MEASURED,
            unit=unit,
            note=note,
            provenance=Provenance.NOT_INSTRUMENTED,
        )

    # ── rendering ───────────────────────────────────────────────────────────────

    @property
    def is_absent(self) -> bool:
        return self.value is None

    def render_value(self) -> str:
        """The value alone.

        For an absent figure this is **words**, never a number and never a dash — `—` in a
        table reads as "nothing notable", which is the opposite of what an absence means.
        """
        if self.value is None:
            return _ABSENCE_TEXT[self.absence or Absence.NO_DATA]
        text = format(self.value, self.fmt)
        if self.unit:
            text = f"{text} {self.unit}"
        if self.basis == Basis.JUDGED:
            text += _JUDGED_SUFFIX
        text += _PROVENANCE_SUFFIX.get(self.provenance, "")
        return text

    def render(self) -> str:
        """`label: value`, plus the note — which is where an exclusion count or a reason lives."""
        out = f"{self.label}: {self.render_value()}"
        if self.note:
            out += f" — {self.note}"
        return out

    def as_dict(self) -> dict:
        """The API and evaluation shape.

        `value` stays `None` for an absent figure, so a caller that serialises this cannot
        accidentally turn "never measured" into `0` — only into `null` plus a stated reason.
        """
        return {
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "basis": self.basis,
            "absence": self.absence,
            "provenance": self.provenance,
            "text": self.render_value(),
            "note": self.note,
        }


@dataclass(frozen=True)
class DataWindow:
    """What an answer covers.

    On a static snapshot, an answer that does not say this is a lie by omission: the reader
    supplies "now" from their own head, and every tense inherits it. That is `C22`.
    """

    start: datetime
    end: datetime
    is_snapshot: bool = True
    source: str = "telemetry snapshot"

    def render(self) -> str:
        return (
            f"{self.start:%Y-%m-%d %H:%M} to {self.end:%Y-%m-%d %H:%M}"
            f"{' (snapshot)' if self.is_snapshot else ''}"
        )

    def as_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "is_snapshot": self.is_snapshot,
            "source": self.source,
        }
