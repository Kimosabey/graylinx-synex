"""`W2` create from a fault · `W3` evidence auto-attached · `W4` priority.

**"Work that arrives carrying its own justification."** That is the pillar's promise in
`CONTEXT.md` §3, and this is where it becomes literal: a work order is built *from* an
evidence pack, so the residuals, their bands, the fit quality, the gates and the window
travel with the job rather than being looked up later by whoever opens it.

**Nothing here calls a model.** `W2`, `W3` and `W4` are `SW` and `R` in the register —
software and rules. `W1`, which drafts one from a sentence, is the only Work Order feature
in the cut that needs the language model, and it is not this.

**A draft, not a work order.** Nothing is persisted: Synex's own state lives in PostgreSQL
and that is not wired yet. `is_draft` is `True` on every one of these and the interface says
so, because a work order a technician cannot be dispatched against should not look like one
they can.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain import priority as prio
from app.services.evidence import EvidencePack


@dataclass(frozen=True)
class EvidenceLine:
    """One piece of justification travelling with the job. `W3`."""

    kind: str
    text: str
    source: str


@dataclass(frozen=True)
class WorkOrderDraft:
    """A work order as it would be raised, with everything it rests on attached."""

    equipment_key: str
    equipment_display: str
    fault_label: str
    day: str
    title: str
    priority: prio.Priority
    evidence: tuple[EvidenceLine, ...] = field(default_factory=tuple)
    cannot_close_until: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    #: Never persisted yet. See the module docstring.
    is_draft: bool = True

    def as_dict(self) -> dict:
        return {
            "is_draft": self.is_draft,
            "equipment_key": self.equipment_key,
            "equipment_display": self.equipment_display,
            "fault_label": self.fault_label,
            "day": self.day,
            "title": self.title,
            "priority": self.priority.as_dict(),
            "evidence": [
                {"kind": e.kind, "text": e.text, "source": e.source} for e in self.evidence
            ],
            "cannot_close_until": list(self.cannot_close_until),
            "warnings": list(self.warnings),
        }


#: `W9`'s promise, stated on the draft even though the gate itself is M3. A work order that
#: does not say what would close it is one somebody closes on a note.
CLOSE_CONDITIONS: tuple[str, ...] = (
    "Post-work residuals recomputed for this asset against its own band",
    "The result is PASS — not the closure note, and not the technician's opinion",
    "UNKNOWN is a permitted outcome and does not close the job",
)


def draft_from_pack(pack: EvidencePack) -> WorkOrderDraft:
    """Build the draft. `W2` and `W3` in one step, because they are the same step.

    Every evidence line carries its own source, so a technician can see not just what was
    claimed but where it came from — the same discipline the Reports drill-down applies to a
    reported figure.
    """
    lines: list[EvidenceLine] = []

    for residual in pack.residual_evidence:
        lines.append(
            EvidenceLine(
                kind="residual",
                text=residual.render(),
                source=residual.source.render(),
            )
        )

    for gate in pack.gates.results:
        lines.append(
            EvidenceLine(
                kind="gate",
                text=(
                    f"{gate.gate.value}: "
                    f"{'passed' if gate.passed else 'FAILED'} {gate.reason}"
                ).strip(),
                source="deterministic gate, evaluated before any diagnosis",
            )
        )

    for note in pack.signal_notes:
        lines.append(
            EvidenceLine(kind="signal", text=note.render(), source="per-signal provenance (C26)")
        )

    warnings: list[str] = []
    if pack.has_poor_fit:
        warnings.append(
            "At least one residual behind this job comes from a poorly fitted model. The "
            "alarm may be an artefact of the fit rather than a fault — check before "
            "dispatching anyone."
        )
    if pack.is_undecidable:
        warnings.append(
            f"{pack.fault_label} declares itself undecidable: the data could not separate "
            f"the candidate causes. This job investigates; it does not assume a mechanism."
        )
    if pack.other_labels_same_day:
        warnings.append(
            "This machine carried "
            + ", ".join(pack.other_labels_same_day)
            + " on the same day. One repair may explain several of them — raising a job per "
            "label is how one problem becomes several visits (RC19)."
        )
    if not pack.may_diagnose:
        warnings.append(
            "The gates did not pass, so no fault was diagnosed. A work order raised from "
            "this would be an investigation, not a repair."
        )

    return WorkOrderDraft(
        equipment_key=pack.equipment_key,
        equipment_display=pack.equipment_display,
        fault_label=pack.fault_label or "no label",
        day=pack.day.isoformat(),
        title=(
            f"{pack.equipment_display}: "
            f"{pack.fault_label or 'unlabelled finding'} on {pack.day.isoformat()}"
        ),
        priority=prio.compute(pack.fault_label or "", pack.slot_count),
        evidence=tuple(lines),
        cannot_close_until=CLOSE_CONDITIONS,
        warnings=tuple(warnings),
    )
