"""The fault taxonomy — nine labels, seven of them faults, and one severity per class.

Every label and every count here was measured on `graylinx_synex` over the **measured**
window and recorded in `docs/20-architecture/00-data-model.md` §4a. Nothing is invented, and
the counts are carried as data so `tests/unit/test_measured_facts.py` can assert that a
query returning something else is a query bug rather than a surprise.

**`NO_DIAGNOSIS` is the largest label by a wide margin — 5,309 slots.** It is not a
contrived demonstration case to be apologised for; it is what the platform genuinely does
most, on real readings. That makes it the strongest asset in this database rather than a
caveat, and it is why `AnswerState.NO_DIAGNOSIS` is a first-class outcome.

**Severity is not stored anywhere.** `gla_model_residuals_wc` holds `equipment`,
`slot_time`, six residuals and `fault_label` — and no severity column. `F17` is therefore a
code-discipline rule rather than a data fix: a fault class has exactly one severity, read
from one place. This module is that place.

**And only one class has a sourced severity.** `CONDENSER_LOW_FLOW` is recorded as the only
`critical` class. For the other six, no document states a value — so they are `UNRATED`
against `Q49` rather than assigned a plausible-looking `HIGH`. Two severity scales once
disagreed on four of seven classes, which is the failure `F17` exists to prevent; inventing
six values in the one authoritative place would reproduce it with more confidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """How bad the fault is. `W4` decides *when* the work happens; this says nothing about
    scheduling.

    Inherited constraint 3: severity comes from fault class plus persistence, **never**
    residual magnitude — non-faults were measured to deviate more than faults.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    UNRATED = "unrated"
    """No document states a severity for this class. `Q49`.

    Rendered as words — *"severity not yet agreed"* — never as a default. A class silently
    defaulted to `MEDIUM` is a number invented in the one place `F17` says must be
    authoritative.
    """


@dataclass(frozen=True)
class FaultClass:
    """One value of `fault_label`, and everything settled about it."""

    label: str

    is_fault: bool
    """`NO_DIAGNOSIS` and `NO_EFFICIENCY_FAULT` are outcomes, not faults. The case-inflation
    measurement excludes both, and so must any fault count."""

    severity: Severity

    declares_undecidable: bool
    """Does the class name say the model could not separate the causes?

    Four of the seven do — *ambiguous*, *unspecified*, *unexplained*, and *undercharge **or**
    restriction*. Inherited constraint 27: only these get a differential, because narrowing a
    class that already names a mechanism would invent ambiguity the model never reported."""

    measured_slots: int
    """Slots carrying this label in the measured window. Evidence, not configuration."""

    note: str = ""


# ── the two outcomes that are not faults ────────────────────────────────────────

NO_DIAGNOSIS = FaultClass(
    label="NO_DIAGNOSIS",
    is_fault=False,
    severity=Severity.UNRATED,
    declares_undecidable=False,
    measured_slots=5_309,
    note=(
        "The gates did not pass. Inherited constraint 7: NULL means not diagnosed, never "
        "healthy — a blind window once read as a clean plant."
    ),
)

NO_EFFICIENCY_FAULT = FaultClass(
    label="NO_EFFICIENCY_FAULT",
    is_fault=False,
    severity=Severity.UNRATED,
    declares_undecidable=False,
    measured_slots=943,
    note="Scored, and nothing wrong found. Distinct from NO_DIAGNOSIS, which did not score.",
)

# ── the seven fault classes ─────────────────────────────────────────────────────

HIGH_HEAD_AMBIGUOUS = FaultClass(
    label="HIGH_HEAD_AMBIGUOUS",
    is_fault=True,
    severity=Severity.UNRATED,
    declares_undecidable=True,
    measured_slots=430,
    note=(
        "The dominant fault class, and the least informative. It appeared on 12 of 12 fault "
        "days, which is why constraint 36 forbids event grouping from titling an event with "
        "the longest-running label."
    ),
)

REFRIGERANT_SIDE_HIGH_HEAD = FaultClass(
    label="REFRIGERANT_SIDE_HIGH_HEAD",
    is_fault=True,
    severity=Severity.UNRATED,
    declares_undecidable=False,
    measured_slots=104,
    note=(
        "Names a region rather than a mechanism: it probes five, and has no differential and "
        "no blocking items, so a case can conclude here with no evidence. That is Q37."
    ),
)

COMPRESSOR_INEFFICIENCY = FaultClass(
    label="COMPRESSOR_INEFFICIENCY",
    is_fault=True,
    severity=Severity.UNRATED,
    declares_undecidable=False,
    measured_slots=58,
    note="rDP normal with rAmp high. A determinate isolation path.",
)

STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION = FaultClass(
    label="STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
    is_fault=True,
    severity=Severity.UNRATED,
    declares_undecidable=True,
    measured_slots=32,
    note=(
        "Honest ambiguity, kept combined on purpose. Constraint 5 forbids automatic "
        "elimination on unreviewed thresholds, and F7 keeps the pair as one label."
    ),
)

CONDENSER_WATER_SIDE_UNSPECIFIED = FaultClass(
    label="CONDENSER_WATER_SIDE_UNSPECIFIED",
    is_fault=True,
    severity=Severity.UNRATED,
    declares_undecidable=True,
    measured_slots=25,
    note=(
        "Its differential's highest-power question — is condenser flow at design? — cannot "
        "be answered from telemetry here at all, because cond_flow has never been measured."
    ),
)

POWER_HIGH_UNEXPLAINED = FaultClass(
    label="POWER_HIGH_UNEXPLAINED",
    is_fault=True,
    severity=Severity.UNRATED,
    declares_undecidable=True,
    measured_slots=22,
    note="Four causes were closed by one estimated judgement. Constraint 20, and SME §1.4b.",
)

CONDENSER_LOW_FLOW = FaultClass(
    label="CONDENSER_LOW_FLOW",
    is_fault=True,
    severity=Severity.CRITICAL,
    declares_undecidable=False,
    measured_slots=3,
    note=(
        "The only class with a sourced severity: the data model records it as the only "
        "critical one. Three slots, and it is the rarest label that matters most."
    ),
)


FAULT_CLASSES: tuple[FaultClass, ...] = (
    NO_DIAGNOSIS,
    NO_EFFICIENCY_FAULT,
    HIGH_HEAD_AMBIGUOUS,
    REFRIGERANT_SIDE_HIGH_HEAD,
    COMPRESSOR_INEFFICIENCY,
    STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION,
    CONDENSER_WATER_SIDE_UNSPECIFIED,
    POWER_HIGH_UNEXPLAINED,
    CONDENSER_LOW_FLOW,
)

_BY_LABEL: dict[str, FaultClass] = {f.label: f for f in FAULT_CLASSES}

#: Slots in the measured window carrying no label at all. Not a fault class — the model
#: did not run on them. Kept here because a coverage figure that omits it overstates reach.
UNLABELLED_SLOTS: int = 7_662

#: Rendered wherever an UNRATED severity would otherwise print. Words, never a default.
UNRATED_SEVERITY_TEXT: str = "severity not yet agreed (Q49)"


def all_labels() -> tuple[str, ...]:
    return tuple(f.label for f in FAULT_CLASSES)


def fault_labels() -> tuple[str, ...]:
    """The seven that are actually faults. Excludes both non-fault outcomes."""
    return tuple(f.label for f in FAULT_CLASSES if f.is_fault)


def undecidable_labels() -> tuple[str, ...]:
    """The four whose own names say the model could not separate the causes."""
    return tuple(f.label for f in FAULT_CLASSES if f.declares_undecidable)


def by_label(label: str) -> FaultClass | None:
    return _BY_LABEL.get(label)


def severity_of(label: str) -> Severity:
    """One severity per class, from one place. `F17`.

    An unknown label is `UNRATED` rather than an exception: a label we have never seen is
    exactly the case where guessing is worst, and the caller renders the words.
    """
    fault = _BY_LABEL.get(label)
    return fault.severity if fault else Severity.UNRATED


def is_rated(label: str) -> bool:
    return severity_of(label) is not Severity.UNRATED
