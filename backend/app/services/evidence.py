"""The evidence pack — the only thing the language model ever sees.

Everything the model is given about a fault is assembled here, deterministically, with no
model involved in building it. That is the whole point: if the pack is wrong the answer is
wrong, and the pack is unit-testable with the GPU off.

**Display strings, not raw floats.** Every figure in the pack carries a rendered string, and
the model is handed *only* those strings. This one decision is what makes grounding usable:
the numeric audit in M1.4 becomes **string containment** rather than float comparison, so
"did the model invent this number" is answerable exactly rather than approximately. A model
handed `-25.645` will print `-25.6` or `-25.65` and no float comparison can tell an honest
rounding from a fabrication.

**A residual is never rendered without its fit.** Chiller 1's current model runs at nRMSE
48.03 against chiller 2's 2.65, and on that machine the residual is out of band in 402 of
412 high-head readings — so the alarms may be an artefact of the model rather than a fault.
`ResidualEvidence` therefore carries `model_nrmse`, and a test asserts a chiller 1 residual
cannot be assembled without one.

**Absences are figures too.** `compressor_power_residual` is NULL in all 21,534 rows, and it
appears in the pack as *"no model is fitted for this signal"* rather than being omitted —
omission is the failure constraint 14 exists to prevent.

This module lives in `services` because it needs both `analytics` (the honesty type, band
verdicts) and `db` (the rows), and `services` is the lowest layer that may import both.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.analytics.bands import BandVerdict, ResidualBand, classify, find_band
from app.analytics.gates import GateOutcome
from app.analytics.honesty import Absence, DataWindow, Figure
from app.db.plant import UNFITTED_RESIDUAL_COLUMN, ResidualRow
from app.domain import equipment as eq
from app.domain import faults, residuals, signals


@dataclass(frozen=True)
class SourceRef:
    """Where a figure came from, and how much data stood behind it.

    Row count is not decoration. "The median residual was −25.6" means something different
    over 3 slots than over 412, and an answer that cannot say which is not auditable.
    """

    table: str
    rows: int
    note: str = ""

    def render(self) -> str:
        base = f"{self.table} ({self.rows} row{'s' if self.rows != 1 else ''})"
        return f"{base} — {self.note}" if self.note else base


@dataclass(frozen=True)
class ResidualEvidence:
    """One residual, its band verdict, and the fit quality of the model that produced it."""

    residual_name: str
    figure: Figure
    verdict: BandVerdict
    band: ResidualBand | None
    model_nrmse: float | None
    source: SourceRef

    @property
    def is_from_a_poor_fit(self) -> bool:
        """True on chiller 1's current and discharge-temperature models.

        The interface badges rather than hides — showing a badged machine beside a clean one
        is more convincing than showing only the clean one, and it is acceptance case 14.
        """
        return (
            self.model_nrmse is not None
            and self.model_nrmse >= residuals.POOR_FIT_NRMSE
        )

    def render(self) -> str:
        """One line, carrying the verdict and the fit together.

        They travel together deliberately: "discharge pressure is high" and "the model that
        said so explains almost none of the variance" are the same sentence or neither.
        """
        line = f"{self.figure.render()} — {self.verdict.value} for this asset"
        if self.band is not None:
            line += (
                f" (healthy band {self.band.lower:.3f} to {self.band.upper:.3f}, "
                f"median {self.band.median:.3f})"
            )
        if self.model_nrmse is not None:
            line += f"; model nRMSE {self.model_nrmse:.2f}"
            if self.is_from_a_poor_fit:
                line += " — POOR FIT, treat this residual with caution"
        return line


@dataclass(frozen=True)
class SignalNote:
    """A signal the answer touched, and what this plant can actually say about it."""

    key: str
    display_name: str
    status: str
    note: str

    def render(self) -> str:
        return f"{self.display_name}: {self.status} — {self.note}"


@dataclass(frozen=True)
class EvidencePack:
    """Everything known about one episode, assembled without a model.

    The model receives `to_prompt_data()`, never this object and never a raw float.
    """

    equipment_key: str
    equipment_display: str
    fault_label: str | None
    day: date
    slot_count: int
    window: DataWindow

    severity: str
    severity_text: str
    is_undecidable: bool

    residual_evidence: tuple[ResidualEvidence, ...] = field(default_factory=tuple)
    gates: GateOutcome = field(default_factory=GateOutcome)
    signal_notes: tuple[SignalNote, ...] = field(default_factory=tuple)
    sources: tuple[SourceRef, ...] = field(default_factory=tuple)
    other_labels_same_day: tuple[str, ...] = field(default_factory=tuple)

    @property
    def may_diagnose(self) -> bool:
        """Every gate passed. If not, the turn ends `NO_DIAGNOSIS` and names the gate."""
        return self.gates.passed

    @property
    def has_poor_fit(self) -> bool:
        return any(r.is_from_a_poor_fit for r in self.residual_evidence)

    def to_prompt_data(self) -> dict:
        """What the language model is handed. **Display strings only.**

        No raw floats anywhere in the returned structure, so the postcheck numeric audit is
        string containment. A test asserts this recursively — if a float ever leaks in, the
        audit silently weakens from exact to approximate and nothing else would notice.
        """
        return {
            "equipment": self.equipment_display,
            "fault_label": self.fault_label or "no label on this slot",
            "day": self.day.isoformat(),
            "slots_in_episode": str(self.slot_count),
            "data_window": self.window.render(),
            "severity": self.severity_text,
            "model_declares_undecidable": "yes" if self.is_undecidable else "no",
            "residuals": [r.render() for r in self.residual_evidence],
            "gates": [
                (
                    f"{g.gate.value}: {'passed' if g.passed else 'FAILED'}"
                    + (f" — {g.reason}" if g.reason else "")
                    + (f" To change this: {g.remedy}" if g.remedy else "")
                )
                for g in self.gates.results
            ],
            "signal_provenance": [s.render() for s in self.signal_notes],
            "sources": [s.render() for s in self.sources],
            "other_labels_same_day": list(self.other_labels_same_day),
            "may_diagnose": "yes" if self.may_diagnose else "no",
            "model_fit_warning": (
                "At least one residual comes from a poorly fitted model. Say so."
                if self.has_poor_fit
                else ""
            ),
        }


# ── assembly ────────────────────────────────────────────────────────────────────

def _severity_text(label: str | None) -> tuple[str, str]:
    """The severity, and how to render it.

    `UNRATED` renders as words naming `Q49`, never as a default. Six of the seven fault
    classes land here — F17 says a class has exactly one severity from one place, and this
    is that place refusing to invent six values.
    """
    severity = faults.severity_of(label or "")
    if severity is faults.Severity.UNRATED:
        return severity.value, faults.UNRATED_SEVERITY_TEXT
    return severity.value, severity.value


def _residual_figure(name: str, value: float | None, verdict: BandVerdict) -> Figure:
    """A residual as a `Figure` — a value, or a stated reason there is none."""
    if name == UNFITTED_RESIDUAL_COLUMN:
        return Figure.absent(name, Absence.NOT_MODELLED)
    if value is None:
        return Figure.absent(name, Absence.NO_DATA)
    if verdict is BandVerdict.NO_BAND:
        return Figure.measured(name, value, note="no reference band — cannot be judged")
    return Figure.measured(name, value)


def build_pack(
    *,
    rows: tuple[ResidualRow, ...],
    bands: tuple[ResidualBand, ...],
    gates: GateOutcome,
    window: DataWindow,
    equipment_key: str,
    fault_label: str | None,
    day: date,
    other_labels_same_day: tuple[str, ...] = (),
) -> EvidencePack:
    """Assemble the pack for one episode. Deterministic, and no model is called.

    The representative slot is the **last** in the episode, not the worst. Picking the worst
    would be selecting evidence to fit a conclusion, and severity never comes from residual
    magnitude anyway — inherited constraint 3, since non-faults were measured to deviate
    more than faults.
    """
    equipment = eq.by_key(equipment_key)
    display = equipment.display_name if equipment else equipment_key

    representative = rows[-1] if rows else None
    evidence: list[ResidualEvidence] = []

    if representative is not None:
        for name, value in representative.residuals.items():
            band = find_band(bands, equipment_key, name)
            verdict = classify(value, band)
            fit = residuals.fit_for(equipment_key, _model_name_for(name))
            evidence.append(
                ResidualEvidence(
                    residual_name=name,
                    figure=_residual_figure(name, value, verdict),
                    verdict=verdict,
                    band=band,
                    model_nrmse=fit.nrmse if fit else None,
                    source=SourceRef(
                        table="gla_model_residuals_wc",
                        rows=len(rows),
                        note=f"slot {representative.slot_time:%Y-%m-%d %H:%M}",
                    ),
                )
            )

    severity, severity_text = _severity_text(fault_label)
    fault = faults.by_label(fault_label or "")

    return EvidencePack(
        equipment_key=equipment_key,
        equipment_display=display,
        fault_label=fault_label,
        day=day,
        slot_count=len(rows),
        window=window,
        severity=severity,
        severity_text=severity_text,
        is_undecidable=bool(fault and fault.declares_undecidable),
        residual_evidence=tuple(evidence),
        gates=gates,
        signal_notes=_signal_notes(),
        sources=(
            SourceRef("gla_model_residuals_wc", len(rows), "residuals and label"),
            SourceRef("gla_residual_stats_wc", len(bands), "per-asset reference bands"),
            SourceRef(
                "gla_equipment_model_metrics",
                len(residuals.fits_for(equipment_key)),
                "model fit quality",
            ),
        ),
        other_labels_same_day=other_labels_same_day,
    )


#: `gla_residual_stats_wc` names residuals by column; `gla_equipment_model_metrics` names
#: the models that produce them. The two vocabularies differ, and joining them by guesswork
#: would silently attach the wrong nRMSE to a residual — a plausible-looking number against
#: the wrong signal, which is worse than none.
_RESIDUAL_TO_MODEL: dict[str, str] = {
    "Dp_residual": "Discharge_Pres",
    "Sp_residual": "Suction_Pres",
    "dt_residual": "Discharge_Temp",
    "chiller_current_residual": "Chiller_Current",
    "cond_leaving_residual": "Condenser_Leav_Temp",
    # compressor_power_residual has no model at all — that is the point of it.
}


def _model_name_for(residual_column: str) -> str:
    return _RESIDUAL_TO_MODEL.get(residual_column, "")


def _signal_notes() -> tuple[SignalNote, ...]:
    """Every signal this plant cannot straightforwardly report, with the reason.

    Carried on every pack rather than only when a signal is used. `cond_flow` feeds four of
    the six models, so its absence shapes any answer about high head whether or not the
    answer mentions it — and an answer that quietly omits it reads as though the branch were
    fully evidenced.
    """
    return tuple(
        SignalNote(
            key=s.key,
            display_name=s.display_name,
            status=s.status.value,
            note=s.note,
        )
        for s in signals.SIGNALS
        if not s.is_usable
    )


def window_for(day: date, measured_window_end: datetime) -> DataWindow:
    """The window an episode's answer covers. `C22`, and constraint 15.

    An answer that does not state its window is a lie by omission on a static snapshot: the
    reader supplies "now" from their own head and every tense inherits it.
    """
    return DataWindow(
        start=datetime(day.year, day.month, day.day, 0, 0),
        end=min(datetime(day.year, day.month, day.day, 23, 59), measured_window_end),
        is_snapshot=True,
        source="gla_model_residuals_wc",
    )
