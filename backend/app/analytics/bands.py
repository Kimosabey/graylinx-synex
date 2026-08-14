"""Band membership — is this residual high or normal **for this asset**?

This module is `F15`, and it is the single place the compare-to-zero bug is prevented.

**A residual is not zero-centred.** `CONTEXT.md` §6 spends its longest paragraph on this and
the measurement is unambiguous: chiller 1's current residual sits at a median of −25.645 in
**normal** operation. Chiller 2's discharge-pressure residual sits at −27.86 against chiller
1's −7.53 — the same signal, two machines, twenty points apart while both are healthy.

So *high* and *normal* mean **high or normal for this asset, against its own healthy
distribution** — median and spread. They never mean "above an absolute threshold", and they
never mean "far from zero". A design that compares residuals against zero, or against a
shared threshold, will rank ordinary operation above a real fault.

**And severity never comes from magnitude.** Inherited constraint 3: non-faults were
measured to deviate *more* than faults. This module answers "is this inside its own band";
it does not answer "how bad is it", and nothing here may be used to rank.

Pure functions and frozen dataclasses. Contract 3 forbids this package from importing
`app.config`, `app.db` or anything above — a pure function that reads a feature flag is not
a pure function.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BandVerdict(StrEnum):
    """Where a residual sits against its own asset's healthy distribution."""

    NORMAL = "normal"
    """Inside the healthy band for this asset and this signal."""

    HIGH = "high"
    """Above the healthy band. The direction the isolation path cares about."""

    LOW = "low"
    """Below the healthy band. `rSP` low with `rDP` normal is a starved evaporator."""

    NO_BAND = "no_band"
    """No reference band is fitted for this asset and signal, so **nothing may be said**.

    Ten of twelve equipment tables land here, and that is the correct answer rather than a
    gap. It is the difference between two machines and twelve."""


@dataclass(frozen=True)
class ResidualBand:
    """One asset's healthy distribution for one residual, from `gla_residual_stats_wc`.

    Ten rows exist — five residuals for each of the two chillers — and nothing else. The
    bounds are the healthy spread, not a fault threshold: crossing one means *unusual for
    this machine*, which is the input to the isolation path rather than a verdict.
    """

    equipment_key: str
    residual_name: str
    median: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError(
                f"band for {self.equipment_key}/{self.residual_name} has lower "
                f"{self.lower} above upper {self.upper}"
            )

    @property
    def width(self) -> float:
        return self.upper - self.lower


def classify(value: float | None, band: ResidualBand | None) -> BandVerdict:
    """Where this reading sits in that band.

    `band is None` returns `NO_BAND` rather than falling back to a comparison against zero.
    That fallback is the entire bug this module exists to prevent, and it is the tempting
    one, because zero *looks* like the natural reference for a residual.

    `value is None` also returns `NO_BAND`: `compressor_power_residual` is 100% NULL, and
    inherited constraint 7 says a NULL means not diagnosed, never healthy.
    """
    if band is None or value is None:
        return BandVerdict.NO_BAND
    if value > band.upper:
        return BandVerdict.HIGH
    if value < band.lower:
        return BandVerdict.LOW
    return BandVerdict.NORMAL


def is_judgeable(band: ResidualBand | None) -> bool:
    """Can anything be said about this asset and signal at all?"""
    return band is not None


def bands_by_key(bands: tuple[ResidualBand, ...]) -> dict[tuple[str, str], ResidualBand]:
    """Index a band set by `(equipment_key, residual_name)` for O(1) lookup.

    A plain helper, but it keeps the lookup key in one place: getting the tuple order wrong
    would silently score chiller 1 against chiller 2's band, which is exactly the failure
    the per-asset rule exists to prevent and would look entirely plausible in output.
    """
    return {(b.equipment_key, b.residual_name): b for b in bands}


def find_band(
    bands: tuple[ResidualBand, ...], equipment_key: str, residual_name: str
) -> ResidualBand | None:
    for b in bands:
        if b.equipment_key == equipment_key and b.residual_name == residual_name:
            return b
    return None
