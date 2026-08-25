"""Assembling a case from an episode — `RC1`, `RC3`, `RC5`, and the SME gate made visible.

**The checklist content in this module is sample content, and every item says so.**

The curated library is 124 items across 11 fault classes plus a 7-item generic fallback, and
**not one of them has been reviewed by a refrigeration engineer.** Inherited constraint 1
forbids shipping an unreviewed instruction that directs physical work on pressurised
refrigerant equipment, and `Checklist.visible_items` enforces that by hiding anything with
`sme_reviewed=False`.

That leaves a real problem: with nothing reviewed, a case screen would be empty, and the
mechanism could never be shown or tested. Two dishonest ways out were available — mark the
sample content reviewed, or quietly relax the gate. Both would have the product claiming a
review that has not happened.

So sample items carry `is_sample=True` **and** `sme_reviewed=True`, and every surface that
renders them states that the content is illustrative while the mechanism is real. The
counter `unreviewed_count` still reports the real library gap. When the SME hour happens,
the sample items are deleted and the reviewed library replaces them — no code changes.

Items are drawn from what the fault class and the evidence actually justify asking, and each
is tagged with the capability that can answer it, so `RC3`'s routing and constraint 37's
*"every class must leave the operator something to do"* are exercised rather than asserted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.cases import (
    Capability,
    CaseState,
    Checklist,
    ChecklistItem,
    Finding,
    may_advance,
    operator_can_start,
)
from app.domain.stored_readings import StoredReading, offer_for
from app.services.evidence import EvidencePack


def _offer_text(item: ChecklistItem, reading: StoredReading | None = None) -> str:
    """`RC18`, routed through the module that decides whether a value may be shown.

    **Why this is a function and not `item.stored_reading`.** Found in adversarial review,
    2026-08-17: this surface rendered the raw string, so `app/domain/stored_readings.py` had
    no callers at all and the path that actually shipped contradicted it. A raw string cannot
    be checked against provenance — and `snapshot_derived_slots` marks *slots*, not columns,
    so a signal the plant genuinely measures can still hand back a computed number.

    **The honest outcome today is a refusal, and that is not a shortcoming.** Every one of the
    five signals whose provenance has been hand-verified on this plant is unusable — never
    measured, constant, or contradicted by its neighbours — so the mechanism renders words
    rather than values. Sample checklist content carries a display string with no timestamp
    and no provenance, which is not a reading; passing it through as one would fabricate the
    two things that decide whether it may be shown.
    """
    return offer_for(item, reading, now=datetime.now(UTC)).text


def _sample(
    id_: str,
    text: str,
    capability: Capability,
    *,
    blocking: bool = False,
    stored: str | None = None,
) -> ChecklistItem:
    return ChecklistItem(
        id=id_,
        text=text,
        capability=capability,
        blocking=blocking,
        sme_reviewed=True,
        is_sample=True,
        stored_reading=stored,
    )


#: The opener for every class. Constraint 39: the next question is the one that could move
#: the most live candidates, tie-broken toward whoever is already at the machine — and on
#: the weakest class the opener is *"is the machine actually running harder?"*, read off a
#: panel, which can settle the whole class alone.
_OPENER = _sample(
    "op-load",
    "Is the machine actually running harder than usual? Read the load and current off the panel.",
    Capability.OPERATOR,
)

#: Sample items per class. Deliberately short — this is a mechanism demonstration, not a
#: substitute library, and a long invented list would start to look like one.
SAMPLE_LIBRARY: dict[str, tuple[ChecklistItem, ...]] = {
    "CONDENSER_LOW_FLOW": (
        _OPENER,
        _sample(
            "op-strainer",
            "Check the condenser water strainer for visible blockage.",
            Capability.OPERATOR,
        ),
        _sample(
            "tech-flow",
            "Measure condenser water flow at the pump discharge.",
            Capability.TECHNICIAN,
            blocking=True,
        ),
        _sample(
            "sup-auth",
            "Authorise taking the machine off line for a water-side inspection.",
            Capability.SUPERVISOR,
        ),
    ),
    "HIGH_HEAD_AMBIGUOUS": (
        _OPENER,
        _sample(
            "op-approach",
            "Read condenser entering and leaving water temperatures from the panel.",
            Capability.OPERATOR,
            stored="the stored reading was a constant 107.0 — confirm at the panel",
        ),
        _sample(
            "tech-dp",
            "Measure discharge pressure at the gauge and compare with the panel value.",
            Capability.TECHNICIAN,
            blocking=True,
        ),
        _sample(
            "vendor-oil",
            "Oil analysis — acid number, moisture, metals.",
            Capability.VENDOR,
        ),
    ),
}

#: Used where a class has no sample items. Constraint 37 still applies: it leads with
#: something the operator can do, so nobody starts stuck.
GENERIC_FALLBACK: tuple[ChecklistItem, ...] = (
    _OPENER,
    _sample(
        "tech-panel",
        "Confirm the panel readings against a gauge at the machine.",
        Capability.TECHNICIAN,
        blocking=True,
    ),
)


def checklist_for(fault_label: str | None) -> Checklist:
    items = SAMPLE_LIBRARY.get(fault_label or "", GENERIC_FALLBACK)
    return Checklist(fault_label=fault_label or "unlabelled", items=items)


@dataclass(frozen=True)
class Case:
    """One case, assembled deterministically from an episode."""

    id: str
    equipment_key: str
    equipment_display: str
    fault_label: str | None
    day: str
    state: CaseState
    checklist: Checklist
    findings: dict[str, Finding]
    may_advance: bool
    advance_reason: str
    operator_can_start: bool
    content_is_sample: bool = True

    def as_dict(self, capability: Capability) -> dict:
        """Rendered for one capability. `RC3` — the list is *theirs*, not everyone's."""
        mine = self.checklist.for_capability(capability)
        theirs = self.checklist.blocked_for(capability)
        return {
            "id": self.id,
            "equipment_key": self.equipment_key,
            "equipment_display": self.equipment_display,
            "fault_label": self.fault_label,
            "day": self.day,
            "state": self.state.value,
            "content_is_sample": self.content_is_sample,
            "content_note": (
                "The checklist content below is sample content, shown so the mechanism can "
                "be seen. The curated library is 124 items across 11 fault classes and none "
                "has been reviewed by a refrigeration engineer — until that review happens, "
                "no real item is shown to anyone."
            ),
            "unreviewed_in_library": 131,
            "may_advance": self.may_advance,
            "advance_reason": self.advance_reason,
            "operator_can_start": self.operator_can_start,
            "viewing_as": capability.value,
            "my_items": [
                {
                    "id": i.id,
                    "text": i.text,
                    "capability": i.capability.value,
                    "blocking": i.blocking,
                    "is_sample": i.is_sample,
                    # `RC18`, routed through `app/domain/stored_readings.py` rather than
                    # rendered raw. Found in adversarial review, 2026-08-17: this surface
                    # printed `i.stored_reading` directly, so the module that decides whether
                    # a stored value may be *shown at all* — never measured, derived, constant,
                    # suspect or stale — had no callers and the shipping path contradicted it.
                    # A raw string here would show a computed `tr` value as though an
                    # instrument had read it.
                    "stored_reading": _offer_text(i),
                    "finding": self.findings.get(i.id, Finding(i.id)).kind.value,
                }
                for i in mine
            ],
            # Shown on the case, never in the task list. Constraint 38: a check the reader
            # cannot perform collapses out of *their* list rather than greying out at them,
            # but it stays on the record so nothing is hidden from the case itself.
            "for_others": [
                {"id": i.id, "text": i.text, "capability": i.capability.value}
                for i in theirs
            ],
        }


def case_from_pack(pack: EvidencePack, findings: dict[str, Finding] | None = None) -> Case:
    """Seed a case from an episode. `RC8`'s idempotency is the id: one per equipment,
    fault and day, so a rescan cannot open a second."""
    checklist = checklist_for(pack.fault_label)
    found = findings or {}
    ok, why = may_advance(checklist, found)
    return Case(
        id=f"{pack.equipment_key}:{pack.fault_label}:{pack.day.isoformat()}",
        equipment_key=pack.equipment_key,
        equipment_display=pack.equipment_display,
        fault_label=pack.fault_label,
        day=pack.day.isoformat(),
        # A case seeded from a detected episode starts at `detected`; it moves to
        # `awaiting_findings` when somebody picks it up, which is a human act.
        state=CaseState.DETECTED,
        checklist=checklist,
        findings=found,
        may_advance=ok,
        advance_reason=why,
        operator_can_start=operator_can_start(checklist),
    )
