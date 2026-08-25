"""`W4` — the priority formula. Deterministic, hand-recomputable, and honest about its gaps.

**A deterministic formula sets priority. Never the language model.** Separation law, row 6.
So this is arithmetic a planner can redo on paper, and every term is named.

**The formula the register asks for cannot be fully computed on this data, and that is
stated rather than worked around.** `W4` specifies *"criticality, risk, SLA and production
impact"*. Of those four:

| Term | Available? |
|---|---|
| Risk — class severity plus persistence | **partly**: one class of nine has a
  sourced severity (`Q49`) |
| Criticality | **no**: the snapshot has no equipment master and no rating |
| SLA | **no**: no service-level target is recorded anywhere |
| Production impact | **no**: no production schedule is joined to this plant |

Three of four inputs do not exist. A formula that silently dropped them would produce a
number that looks like a priority and is really a severity wearing a rank — which is worse
than no number, because a planner would schedule against it.

So `compute` returns a `Priority` that carries **what it used and what it could not**, and
`is_complete` is `False` until the missing inputs arrive. `Q51`.

**Severity never comes from residual magnitude.** Inherited constraint 3: non-faults were
measured to deviate *more* than faults, so ranking by how far a residual sits from its band
would put ordinary operation above a real fault. Persistence — how long the pattern held —
is the second term, and it is the one this data can supply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain import faults


class Band(StrEnum):
    """The priority label a planner sees. `P0`/`P1`/`P2` are priority labels, which is why
    no feature prefix may be a bare `P` — CLAUDE.md §2.7."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    UNRATED = "unrated"
    """The severity of this fault class has not been agreed, so no priority follows. `Q49`."""


#: The one sourced severity maps to the top band. Nothing else is mapped, because nothing
#: else has a severity to map from — see the module docstring.
_SEVERITY_BAND: dict[faults.Severity, Band] = {
    faults.Severity.CRITICAL: Band.P0,
    faults.Severity.HIGH: Band.P0,
    faults.Severity.MEDIUM: Band.P1,
    faults.Severity.LOW: Band.P2,
}

#: Persistence, in slots, above which a pattern is treated as sustained rather than
#: momentary. **Not a threshold for diagnosis** — that is `Q6` and unagreed. This one only
#: decides whether persistence *raises* an already-established priority, so being wrong
#: moves a job up or down one band rather than creating or hiding a fault.
SUSTAINED_SLOTS: int = 12

#: The inputs `W4` names that this plant does not record. Held as data so the interface can
#: list them rather than a comment nobody reads.
MISSING_INPUTS: tuple[tuple[str, str], ...] = (
    ("criticality", "no equipment master and no criticality rating in the snapshot"),
    ("sla", "no service-level target is recorded for this plant"),
    ("production_impact", "no production schedule is joined to this plant"),
)


@dataclass(frozen=True)
class Priority:
    """A priority, the arithmetic behind it, and what the arithmetic could not include."""

    band: Band
    fault_label: str
    severity: str
    slot_count: int
    sustained: bool
    used: tuple[str, ...] = field(default_factory=tuple)
    missing: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        """`False` while any input `W4` names is unavailable.

        A planner reading a priority is entitled to know whether it accounted for everything
        it claims to. This is the field that tells them.
        """
        return not self.missing and self.band is not Band.UNRATED

    @property
    def explanation(self) -> str:
        """The formula in words, so it can be recomputed by hand.

        `W4` is `R` — a rule, not a model — and a rule a planner cannot redo is
        indistinguishable from one.
        """
        if self.band is Band.UNRATED:
            return (
                f"No priority. {self.fault_label} has no agreed severity (Q49), and "
                f"priority is derived from severity — so there is nothing to derive it "
                f"from. Severity is never taken from how far a residual sits outside its "
                f"band: non-faults were measured to deviate more than faults."
            )
        parts = [
            f"{self.fault_label} carries severity '{self.severity}', which maps to "
            f"{self.band.value}."
        ]
        if self.sustained:
            parts.append(
                f"The pattern held for {self.slot_count} slots, over the {SUSTAINED_SLOTS}-slot "
                f"sustained mark, so it is not treated as momentary."
            )
        else:
            parts.append(
                f"The pattern held for {self.slot_count} slots, under the "
                f"{SUSTAINED_SLOTS}-slot sustained mark."
            )
        if self.missing:
            parts.append(
                "This is incomplete: "
                + "; ".join(f"{name} — {why}" for name, why in self.missing)
                + ". Q51."
            )
        return " ".join(parts)

    def as_dict(self) -> dict:
        return {
            "band": self.band.value,
            "fault_label": self.fault_label,
            "severity": self.severity,
            "slot_count": self.slot_count,
            "sustained": self.sustained,
            "used": list(self.used),
            "missing": [{"input": n, "why": w} for n, w in self.missing],
            "is_complete": self.is_complete,
            "explanation": self.explanation,
        }


def compute(fault_label: str, slot_count: int) -> Priority:
    """The formula. Two terms available, three inputs absent, all four accounted for.

    Deliberately takes the label and a slot count — not a residual. Passing a residual here
    would invite ranking by magnitude, which constraint 3 forbids for a measured reason.
    """
    severity = faults.severity_of(fault_label)
    sustained = slot_count >= SUSTAINED_SLOTS

    if severity is faults.Severity.UNRATED:
        return Priority(
            band=Band.UNRATED,
            fault_label=fault_label,
            severity=faults.UNRATED_SEVERITY_TEXT,
            slot_count=slot_count,
            sustained=sustained,
            used=("fault class",),
            missing=MISSING_INPUTS,
        )

    band = _SEVERITY_BAND[severity]
    return Priority(
        band=band,
        fault_label=fault_label,
        severity=severity.value,
        slot_count=slot_count,
        sustained=sustained,
        used=("fault class severity", "persistence"),
        missing=MISSING_INPUTS,
    )
