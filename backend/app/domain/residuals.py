"""The residual models, their fit quality, and the sixth model that is not there.

From `gla_equipment_model_metrics` — ten rows, **five models per chiller, not six** —
recorded in `docs/20-architecture/00-data-model.md` §4c.

**Two facts here change how every residual must be read.**

**A residual is not zero-centred.** `CONTEXT.md` §6 spends its longest paragraph on this:
chiller 1's current residual sits at a median of −25.65 in normal operation, and chiller 2's
discharge-pressure residual at −27.86 against chiller 1's −7.53. "High" and "normal" mean
*for this asset, against its own healthy distribution*. A design that compares residuals
against zero, or against a shared threshold, will rank ordinary operation above a real
fault. That is why fit quality lives here rather than in a dashboard.

**The same model is eighteen times worse on one machine than the other** — chiller 1's
current model at nRMSE 48.03 against chiller 2's 2.65. An identical fault label on the two
machines does not mean the same thing. So a residual is never rendered without its fit, and
`worst_nrmse_for` exists to make that cheap rather than optional.

**There is no compressor-power model.** `compressor_power_residual` is 100% NULL. The
six-model description in `CONTEXT.md` §6 is the design; five is what is fitted. Constraint
14 says a figure is a value or a stated absence and never neither — so the sixth is held as
an explicit absence rather than omitted, because omission is the failure that constraint
exists to prevent.

**Ignore MAPE.** It reads 2,931,599 and 12,202,370 on three of the ten rows, because the
denominator approaches zero. It is deliberately not carried in this module.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Above this, a model's residual is mostly its own error. Chiller 1's current model at
#: 48.03 is the case that forces the question, and the alarms it raises may be an artefact:
#: the residual is out of band in 402 of 412 high-head readings on that machine.
#:
#: TBD (Q50): no document states the threshold at which a fit becomes untrustworthy. This
#: value is **not** used to suppress anything — it only decides whether a badge is shown,
#: so being wrong costs a visible warning rather than a hidden fault.
POOR_FIT_NRMSE: float = 10.0


@dataclass(frozen=True)
class ModelFit:
    """One fitted normal-operation model, for one asset."""

    equipment_key: str
    model_name: str
    """As `gla_equipment_model_metrics` names it, e.g. `Chiller_Current`."""
    nrmse: float

    @property
    def is_poor_fit(self) -> bool:
        return self.nrmse >= POOR_FIT_NRMSE


#: The ten rows, exactly as measured. Ordered worst fit first per machine, as the source
#: table is presented, because the worst fit is the one that changes what may be claimed.
MODEL_FITS: tuple[ModelFit, ...] = (
    ModelFit("chiller_1", "Chiller_Current", 48.03),
    ModelFit("chiller_1", "Discharge_Temp", 36.41),
    ModelFit("chiller_1", "Suction_Pres", 7.93),
    ModelFit("chiller_1", "Discharge_Pres", 5.38),
    ModelFit("chiller_1", "Condenser_Leav_Temp", 2.95),
    ModelFit("chiller_2", "Suction_Pres", 3.77),
    ModelFit("chiller_2", "Discharge_Temp", 3.41),
    ModelFit("chiller_2", "Discharge_Pres", 2.90),
    ModelFit("chiller_2", "Chiller_Current", 2.65),
    ModelFit("chiller_2", "Condenser_Leav_Temp", 1.68),
)

#: The five models that are actually fitted, by name.
FITTED_MODEL_NAMES: tuple[str, ...] = (
    "Chiller_Current",
    "Discharge_Temp",
    "Suction_Pres",
    "Discharge_Pres",
    "Condenser_Leav_Temp",
)

#: The sixth residual in `gla_model_residuals_wc`, which is 100% NULL. Named so that it can
#: be rendered as "no model is fitted for this signal" rather than quietly left out.
ABSENT_RESIDUAL_COLUMN: str = "compressor_power_residual"

#: The design says six models per chiller; five are fitted. Held as data so a document
#: claiming six fails a test rather than a reading.
DESIGNED_MODEL_COUNT: int = 6
FITTED_MODEL_COUNT: int = 5


def fits_for(equipment_key: str) -> tuple[ModelFit, ...]:
    return tuple(f for f in MODEL_FITS if f.equipment_key == equipment_key)


def fit_for(equipment_key: str, model_name: str) -> ModelFit | None:
    for f in MODEL_FITS:
        if f.equipment_key == equipment_key and f.model_name == model_name:
            return f
    return None


def worst_nrmse_for(equipment_key: str) -> float | None:
    """The worst fit on this asset — what a whole-asset claim has to answer for.

    `None` for the ten unscoreable assets, which is the honest answer: no model, so no fit,
    so nothing to qualify a claim with. The caller renders a stated absence.
    """
    fits = fits_for(equipment_key)
    return max(f.nrmse for f in fits) if fits else None


def has_poor_fit(equipment_key: str) -> bool:
    """True for chiller 1. The hero demonstration case is therefore chiller 2.

    Chiller 1 stays in the walkthrough, badged — that is acceptance case 14, and showing a
    badged machine beside a clean one is more convincing than hiding it.
    """
    return any(f.is_poor_fit for f in fits_for(equipment_key))
