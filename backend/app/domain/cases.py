"""`RC1` the case state machine, `RC3` capability routing, `RC4`/`RC10` findings.

The case is the object between a named fault and a closed work order. It is one state
machine with **several routes through it**, and the routes matter more than the states:
measured on the reference queue, 13 cases went straight through, 26 stopped at the checks,
2 arrived already explained by a broken sensor and 2 by a blind model. **Two thirds pause.**
A product built only for the straight-through journey is a model viewer.

**Nothing here calls a model, and a test asserts it.** `RC1` is `SW + R`. The state machine
must be testable with the GPU off, and a prompt change must never be able to alter a state
transition — that is contract 2 in `importlinter.ini`, and it is why this lives in `domain`.

**The checklist library is curated content, never model output.** Inherited constraint 1: a
checklist directs physical work on pressurised refrigerant equipment, and a
plausible-but-wrong item is worse than no item. Constraint 26: the language model *selects
and contextualises* library content; it never authors a field instruction.

**Nothing unreviewed reaches a user.** 131 items exist and no refrigeration engineer has read
one of them. `sme_reviewed` defaults to `False`, `visible_items` returns only reviewed ones,
and the unreviewed count is exposed so the gap is a visible number rather than a silent
omission. That turns the SME hour from a blocker into a counter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CaseState(StrEnum):
    """`RC1`. Seven states, and the three that are not `closed` matter most."""

    DETECTED = "detected"
    """Seeded from an episode. `RC8`: a rescan must never open a second."""

    AWAITING_FINDINGS = "awaiting_findings"
    """Someone has to go and look. 26 of 43 measured cases stop here."""

    ESCALATED = "escalated"
    """Handed on — sideways for skill, up for authority. `RC7` keeps those distinct."""

    DEFERRED = "deferred"
    """Parked with a reason and a date. Nobody was called; that is the point."""

    ROOT_CAUSED = "root_caused"
    """A cause is established, with the checks that established it. `RC13`."""

    ACTIONED = "actioned"
    """Work raised and done. Not yet proved."""

    CLOSED = "closed"
    """Only reachable through verification. `W9`: a case cannot close unproven."""

    STALE = "stale"
    """`RC9`. The condition cleared, or nobody has touched it. Four open cases once
    described transmitters repaired weeks earlier, and twenty had waited since April."""


#: Which states may follow which. Written as data so the machine is inspectable and a
#: forbidden transition is a lookup rather than a branch somebody forgot.
TRANSITIONS: dict[CaseState, frozenset[CaseState]] = {
    CaseState.DETECTED: frozenset(
        {CaseState.AWAITING_FINDINGS, CaseState.ESCALATED, CaseState.DEFERRED, CaseState.STALE}
    ),
    CaseState.AWAITING_FINDINGS: frozenset(
        {CaseState.ROOT_CAUSED, CaseState.ESCALATED, CaseState.DEFERRED, CaseState.STALE}
    ),
    CaseState.ESCALATED: frozenset(
        {CaseState.AWAITING_FINDINGS, CaseState.ROOT_CAUSED, CaseState.DEFERRED, CaseState.STALE}
    ),
    CaseState.DEFERRED: frozenset({CaseState.AWAITING_FINDINGS, CaseState.STALE}),
    CaseState.ROOT_CAUSED: frozenset({CaseState.ACTIONED, CaseState.STALE}),
    # The only route to `closed`, and it runs through verification rather than through a
    # closure note. `W9`. It can also go stale: work done and never verified is exactly the
    # case that sits silently, and `RC9` exists because four open cases once described
    # transmitters that had been repaired weeks earlier.
    CaseState.ACTIONED: frozenset(
        {CaseState.CLOSED, CaseState.AWAITING_FINDINGS, CaseState.STALE}
    ),
    CaseState.CLOSED: frozenset(),
    CaseState.STALE: frozenset({CaseState.AWAITING_FINDINGS, CaseState.DEFERRED}),
}


def can_transition(current: CaseState, target: CaseState) -> bool:
    return target in TRANSITIONS[current]


class Capability(StrEnum):
    """`RC3`. Five capabilities — who can *answer* a checklist item.

    Not a ladder, and not the persona system. Inherited constraint 25: a supervisor is not
    a more capable technician; it is authority and records, not gauges.
    """

    OPERATOR = "operator"
    MAINTENANCE = "maintenance"
    TECHNICIAN = "technician"
    SUPERVISOR = "supervisor"
    VENDOR = "vendor"


#: Constraint 24, and the asymmetry is deliberate. Mis-tagging a technician task as operator
#: puts an unqualified person on a pressurised circuit; the reverse wastes a callout.
#: Over-escalating is the cheap error.
DEFAULT_CAPABILITY: Capability = Capability.TECHNICIAN


class FindingKind(StrEnum):
    """`RC4` and `RC10`. Five answers, and the distinctions between them are load-bearing."""

    MEASURED = "measured"
    """A reading taken now. **The only kind that settles a blocking check.**"""

    ESTIMATED = "estimated"
    """A judgement. Constraint 20: an estimate does not settle a blocking check — on the
    reference plant an untagged answer defaulted to estimated and opened a blocking gate."""

    CANNOT_CHECK = "cannot_check"
    """This person cannot perform this check. **Not the same as not applicable.**
    Constraint 8: six "N/A" presses once opened a blocking gate with zero evidence."""

    NOT_APPLICABLE = "not_applicable"
    """This check does not apply to this machine. A statement about the equipment."""

    NOT_ANSWERED = "not_answered"
    """Nobody has looked yet."""


#: Only this settles a blocking item. Held as a set of one so the rule is a lookup rather
#: than an `==` somebody later widens.
SETTLING_KINDS: frozenset[FindingKind] = frozenset({FindingKind.MEASURED})


@dataclass(frozen=True)
class ChecklistItem:
    """One curated instruction. Human-written; never model output."""

    id: str
    text: str
    capability: Capability = DEFAULT_CAPABILITY
    blocking: bool = False
    """A blocking item stops the case advancing until it is *settled*. `RC5`."""

    sme_reviewed: bool = False
    """**Defaults to False.** No refrigeration engineer has reviewed the 131-item library,
    and an unreviewed instruction directing physical work is the risk constraint 1 names."""

    is_sample: bool = False
    """**Illustrative content, not the curated library.**

    A separate flag from `sme_reviewed` on purpose. To show a case screen at all, some item
    has to be visible — and setting `sme_reviewed=True` on invented content to achieve that
    would be claiming a refrigeration engineer had read it. This flag lets sample content be
    visible *and* labelled as sample, so the mechanism can be demonstrated without the
    content pretending to be the library."""

    stored_reading: str | None = None
    """`RC18`. Where the database already holds a value this item asks for, it is offered as
    *"the stored reading was X — confirm at the panel"*. A stored value is not a gauge
    reading now, so it never settles a blocking check on its own."""


@dataclass(frozen=True)
class Finding:
    item_id: str
    kind: FindingKind = FindingKind.NOT_ANSWERED
    value: str | None = None
    note: str = ""

    @property
    def settles_a_blocking_item(self) -> bool:
        return self.kind in SETTLING_KINDS


@dataclass(frozen=True)
class Checklist:
    """The items for one fault class, and what the reader may actually see."""

    fault_label: str
    items: tuple[ChecklistItem, ...] = field(default_factory=tuple)

    def visible_items(self) -> tuple[ChecklistItem, ...]:
        """Only reviewed items reach a user. The rest are counted, not shown.

        This is the mechanism that lets M2 proceed before the SME hour: the library is
        gated rather than the milestone.
        """
        return tuple(i for i in self.items if i.sme_reviewed)

    @property
    def unreviewed_count(self) -> int:
        return sum(1 for i in self.items if not i.sme_reviewed)

    def for_capability(self, capability: Capability) -> tuple[ChecklistItem, ...]:
        """What this person can actually do.

        Constraint 38: a check the reader cannot perform **collapses, it does not grey
        out** — a greyed-out *"oil analysis — acid, moisture, metals"* still reads as a
        demand on whoever is standing there. So it is filtered out of their list entirely,
        and `blocked_for` reports it separately rather than hiding it from the case.
        """
        return tuple(i for i in self.visible_items() if i.capability is capability)

    def blocked_for(self, capability: Capability) -> tuple[ChecklistItem, ...]:
        """Items this person cannot answer. Shown on the case, never in their task list."""
        return tuple(i for i in self.visible_items() if i.capability is not capability)

    def blocking_items(self) -> tuple[ChecklistItem, ...]:
        return tuple(i for i in self.visible_items() if i.blocking)


def may_advance(checklist: Checklist, findings: dict[str, Finding]) -> tuple[bool, str]:
    """`RC5`. May the case leave `awaiting_findings`?

    A blocking item settled by anything other than a measured reading does not count.
    Constraint 20: on the reference plant an untagged answer defaulted to `estimated` and
    opened a blocking gate, which is constraint 8's failure arriving by a second route.
    """
    unsettled = [
        item
        for item in checklist.blocking_items()
        if not findings.get(item.id, Finding(item.id)).settles_a_blocking_item
    ]
    if not unsettled:
        return True, "every blocking item has a measured answer"

    reasons = []
    for item in unsettled:
        kind = findings.get(item.id, Finding(item.id)).kind
        reasons.append(f"{item.id} ({kind.value})")
    return False, (
        f"{len(unsettled)} blocking item(s) have no measured answer: {', '.join(reasons)}. "
        f"Only a measured reading settles a blocking check — an estimate, a cannot-check "
        f"and a not-applicable all leave it open."
    )


def operator_can_start(checklist: Checklist) -> bool:
    """Constraint 37: **every fault class must carry at least one check the operator can
    do.** Otherwise somebody starts stuck rather than getting stuck partway."""
    return bool(checklist.for_capability(Capability.OPERATOR))
