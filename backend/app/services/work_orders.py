"""`W2` create from a fault · `W3` evidence auto-attached · `W4` priority · `C8` confirm.

**"Work that arrives carrying its own justification."** That is the pillar's promise in
`CONTEXT.md` §3, and this is where it becomes literal: a work order is built *from* an
evidence pack, so the residuals, their bands, the fit quality, the gates and the window
travel with the job rather than being looked up later by whoever opens it.

**Nothing here calls a model.** `W2`, `W3` and `W4` are `SW` and `R` in the register —
software and rules. `W1`, which drafts one from a sentence, is the only Work Order feature
in the cut that needs the language model, and it is not this.

**`C8` is two halves and the first one is the promise: the action is shown before it is
saved.** `draft_from_pack` renders; nothing it produces reaches a table. `confirm` is the
explicit act, and it is the only route from a draft to a row. The two must agree exactly —
what a person confirmed has to be what got stored, or the showing was a demonstration of a
different action — so the draft's own rendering travels into storage verbatim under
`shown_as` and a test compares them rather than trusting the claim.

**The draft rendering has not changed and must not.** Everything below `CLOSE_CONDITIONS` was
written before persistence existed and still produces the same dict; the confirm step reads it
and adds nothing to it.

**Confirming asks `G3` first.** Raising a work order dispatches a person, which is `Risk.HIGH`
by that enum's own definition, so an identity without `approve_work` gets a `C9` approval
request and no row. That is not this module refusing — it is the Control Plane's answer,
carried through.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.db.work_order_store import ConfirmedWorkOrder
from app.domain import priority as prio
from app.domain.authority import Action, Risk, Ruling, rule
from app.domain.idempotency import UNLABELLED, WorkOrderIdentity, WorkOrderKind
from app.services import approvals
from app.services.control_plane import Scope
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

    #: Always `True` on this object, and it stays `True` in the copy that gets stored under
    #: `shown_as`. That copy is a record of the rendering somebody confirmed, not a
    #: description of the row — the row's own `state` is what says it is no longer a draft.
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


# ── C8: the explicit act, and the key that makes a retry harmless ───────────────


class WorkOrderState(StrEnum):
    """Where a job stands. Three, and the third is only reachable through verification."""

    DRAFT = "draft"
    """Shown, never stored. `C8`: the action is shown before it is saved, and a draft that
    reached a table would make the showing decorative."""

    CONFIRMED = "confirmed"
    """Somebody with the `approve_work` capability performed the explicit act. This is the
    only state `confirm` can produce."""

    CLOSED = "closed"
    """`W9`. Post-work residuals recomputed against this asset's own band, and the result is
    PASS. **No transition table lives here**, deliberately: the close gate is M3, and writing
    one now would give something a route to closed before the gate that guards it exists."""


#: The action `G3` rules on. Named once so the ruling and the audit row cannot drift apart into
#: two spellings of the same act.
RAISE_WORK_ORDER: str = "raise_work_order"


def raise_action(draft: WorkOrderDraft) -> Action:
    """What is about to happen, classified for `G2`.

    `HIGH` by that enum's own definition — it *commits Synex to an action in the world:
    dispatches a person*. And `reverses_cleanly=False`, because deleting the row is not the
    thing that has to be undone: a technician who has already driven to the plant cannot be
    un-dispatched, and `classify` raises anything irreversible to `HIGH` regardless of what
    the caller declared.
    """
    return Action(
        name=RAISE_WORK_ORDER,
        risk=Risk.HIGH,
        target=draft.equipment_key,
        reverses_cleanly=False,
    )


#: What `draft_from_pack` renders when the pack carries no fault label. `WorkOrderIdentity`
#: refuses an empty label rather than defaulting one, so the placeholder is translated to that
#: module's declared sentinel here — deliberately, and with its consequence inherited: every
#: unlabelled finding on one machine-day then shares a job. `Q90` carries whether that is right.
UNLABELLED_DRAFT_TITLE: str = "no label"


def identity_for(
    draft: WorkOrderDraft, kind: WorkOrderKind = WorkOrderKind.CORRECTIVE
) -> WorkOrderIdentity:
    """`G5`. The four facts that make two requests the same job.

    **The derivation is not repeated here.** `app/domain/idempotency.py` owns it, including
    the two things this module would have got wrong on its own: `kind` belongs in the key
    because `RC7`'s inspection and authorisation artefacts are genuinely two jobs, and the
    fields are separated by a null byte so no pair of values can be rearranged into the same
    string. One source of truth per fact — a second SHA in this file is exactly the drift
    CLAUDE.md §2.8 forbids.

    The draft carries its day as an ISO string because that is what an interface renders; the
    identity wants a `date`, so it is parsed back rather than re-formatted at the other end.
    """
    label = draft.fault_label
    return WorkOrderIdentity(
        equipment_key=draft.equipment_key,
        fault_label=UNLABELLED if label == UNLABELLED_DRAFT_TITLE else label,
        day=date.fromisoformat(draft.day),
        kind=kind,
    )


@dataclass(frozen=True)
class ConfirmOutcome:
    """What the confirm step decided. Exactly one of a record or an approval request, never
    both and never neither — constraint 14's shape, applied to an act rather than a figure."""

    ruling: Ruling
    reason: str
    record: ConfirmedWorkOrder | None = None
    """Ready to store. `None` means nothing may be stored, and the reason says why."""

    approval: approvals.ApprovalRequest | None = None
    """`C9`. Present when the identity needs authority it does not hold. Unassigned, addressed
    to a capability — see `app/services/approvals.py`."""

    @property
    def will_persist(self) -> bool:
        return self.record is not None

    @property
    def needs_approval(self) -> bool:
        """Not a refusal. Somebody down the corridor can sign this."""
        return self.approval is not None

    def as_dict(self) -> dict:
        return {
            "will_persist": self.will_persist,
            "needs_approval": self.needs_approval,
            "reason": self.reason,
            "ruling": self.ruling.as_dict(),
            "approval": self.approval.as_dict() if self.approval else None,
            "idempotency_key": self.record.idempotency_key if self.record else "",
        }


def confirm(
    draft: WorkOrderDraft,
    requester: Scope,
    *,
    case_id: int | None = None,
    kind: WorkOrderKind = WorkOrderKind.CORRECTIVE,
) -> ConfirmOutcome:
    """The explicit act. **The only route from a draft to a stored row.**

    Nothing is written here — this returns a record for `WorkOrderStore.confirm` to store, so
    the decision is testable with Postgres stopped and the write is one statement in one place.

    The draft is read and never mutated: what comes back under `shown_as` is
    `draft.as_dict()`, unchanged, so *what was shown* and *what was saved* can be compared
    instead of trusted.
    """
    ruling = rule(raise_action(draft), frozenset(c.value for c in requester.capabilities))

    if ruling.is_refusal:
        return ConfirmOutcome(
            ruling=ruling,
            reason=(
                f"Nothing was stored and no approval was requested. {ruling.reason}"
            ),
        )

    if not ruling.may_proceed:
        return ConfirmOutcome(
            ruling=ruling,
            reason=(
                f"Nothing was stored. {ruling.reason} The draft stands and an approval "
                f"request has been raised against the {ruling.required_capability} "
                f"capability."
            ),
            approval=approvals.request_for(
                ruling,
                requester,
                target=draft.equipment_key,
                evidence=draft.evidence,
            ),
        )

    identity = identity_for(draft, kind)
    return ConfirmOutcome(
        ruling=ruling,
        reason=(
            f"{requester.identity.display_name} confirmed {identity.render()}, so it may be "
            f"stored. A retry with the same key returns that row rather than raising a second "
            f"job."
        ),
        record=ConfirmedWorkOrder(
            idempotency_key=identity.key,
            equipment_key=draft.equipment_key,
            confirmed_by=requester.identity.persona.value,
            evidence={
                # The draft exactly as it was rendered. Not a summary of it, and not a
                # re-derivation — `C8` promises the before looks identical to what is saved,
                # and the only way to keep that promise is to carry the rendering itself.
                "shown_as": draft.as_dict(),
                # What the key was derived from, in order. A hash nobody can invert is a hash
                # nobody can check, so the basis travels beside it.
                "key_basis": list(identity.basis),
                "identifies": identity.render(),
                "act": RAISE_WORK_ORDER,
                "confirmed_by": requester.identity.persona.value,
                "identity_kind": requester.identity.identity_kind,
                "authority": ruling.as_dict(),
            },
            kind=kind.value,
            state=WorkOrderState.CONFIRMED.value,
            priority=draft.priority.band.value,
            priority_is_complete=draft.priority.is_complete,
            case_id=case_id,
        ),
    )
