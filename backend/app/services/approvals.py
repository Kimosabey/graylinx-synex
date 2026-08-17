"""`C9` — the approval request. Addressed to a capability, unassigned, and it says so.

**The failure this prevents, and it has an incident behind it.** Inherited constraint 13:
roles are capabilities, not ranks. Ranking by seniority once sent a filter-drier restriction
to a supervisor because one incidental records question outranked three refrigeration
measurements. A request that names a person has already made that routing decision, silently,
before anybody could check it — so this one names a **capability**. There is no field on
`ApprovalRequest` that can hold a person, and a test asserts there is not.

**Constraint 9: escalating up lands unassigned and says so.** That is the whole of it. A named
approver implies somebody accepted the request; nobody has. The measured shape of the problem:
of the 124 curated checklist items, **38 carry a supervisor tag**, almost all of them in the
preventive stage — so supervisor work already lands on the one role that had no queue to
receive it (`U7`). Addressing a request to a named supervisor on top of that is how an
approval sits in nobody's list while reading as though it is in somebody's.

**The second rule, and it is the one an implementation gets wrong quietly.** The identity that
raised a request can never satisfy it. The dangerous case is not somebody without authority
trying to sign — that fails on the capability anyway. It is a Supervisor raising a job and
approving it in the same breath, because every capability check they meet says yes. So
self-approval is tested **before** the capability, and refused with its own reason.

**Which of the three role systems this uses.** `CONTEXT.md` §11 warns that three different
things are called roles and that conflating them causes real routing bugs. This is the
authorization capability — `Capability.APPROVE_WORK` from the Control Plane — not the
capability role that decides who may answer a checklist item (`RC3`), and not the agent-skill
registry. Addressing an approval to `technician` would be the second system answering the
first system's question.

**Nothing here decides who is allowed.** `G3` did that, in `app/domain/authority.py`, and this
module renders a `NEEDS_APPROVAL` ruling into something a person can act on. It calls no
model: the separation law's seventh row leaves authorization to plain software, and contract 2
in `importlinter.ini` makes that a build failure rather than a convention.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from app.domain.authority import Decision, Ruling
from app.services.control_plane import Capability, Identity, Scope


class EvidenceItem(Protocol):
    """What this module needs of one line of justification, and nothing more.

    Structural rather than imported, the same way `correlation.Episode` is: the evidence a
    request carries comes from `app.services.work_orders`, which imports *this* module, so an
    import the other way would be a cycle. `EvidenceLine` satisfies this shape and is passed
    straight in.
    """

    kind: str
    text: str
    source: str


class ApprovalRoutingError(ValueError):
    """A ruling was handed here that must never become an approval request.

    Two shapes, and both are programming errors rather than user outcomes: a ruling that
    already allows the action, and one that no approval clears. Producing a request for the
    second would imply somebody sufficiently senior could sign a safety stop, which is exactly
    the reading `S1` exists to prevent.
    """


#: Constraint 9, in the words a reader sees. Held as a constant rather than formatted at each
#: call site so the request cannot be rendered somewhere without it.
UNASSIGNED_NOTE: str = (
    "Unassigned. This is addressed to a capability, not to a person — nobody has accepted "
    "it, and naming an approver would imply somebody had."
)


class GrantDecision(StrEnum):
    """What happened when somebody tried to satisfy the request. Two of the three are refusals
    and each carries a different reason, because *you are not allowed* and *you are the person
    who asked* need different next steps."""

    GRANTED = "granted"
    """The approver holds the capability and is not the requester."""

    REFUSED_SELF_APPROVAL = "refused_self_approval"
    """The requesting identity tried to satisfy its own request. Refused even when the
    capability is held — especially then."""

    REFUSED_LACKS_CAPABILITY = "refused_lacks_capability"
    """This identity does not hold what the request asks for. **Not a dead end** — the request
    stands, unassigned, and somebody who holds it can still act on it."""


def identity_ref(identity: Identity) -> str:
    """Who this is, for the purpose of *not the same person*.

    **This is coarser than it should be, and the direction of the error is deliberate.** D-013
    says the Control Plane is a persona switcher rather than authentication (`Q41`), so the
    persona is the only identity the platform has. Two Supervisors are therefore
    indistinguishable here, and one signing the other's request reads as self-approval and is
    refused. The cost of that is a second person being asked; the cost of the opposite
    asymmetry is a self-approval slipping through. Over-refusing is the cheap error, the same
    way constraint 24 makes over-escalating the cheap error. `Q80` carries the real fix.
    """
    return f"{identity.identity_kind}:{identity.persona.value}"


@dataclass(frozen=True)
class ApprovalRequest:
    """`C9`. The action, its evidence, the capability required, and the reason.

    **There is no assignee field, and that is the design rather than an omission.** Constraint
    9: escalating up lands unassigned. A person can be added only by adding a field, which is
    a visible act somebody has to justify.
    """

    action: str
    target: str
    """What the action acts on — an equipment key, a case id. Scope, never risk."""

    risk: str
    required_capability: Capability
    """The Control Plane's authorization capability. Not the `RC3` checklist role."""

    reason: str
    """`G3`'s own words, carried through rather than re-worded. A request whose reason was
    rewritten here is a request whose reason two modules could disagree about."""

    requested_by: str
    """The requester's reference, from `identity_ref`. Recorded so the self-approval check has
    something to compare against — never so somebody can be addressed."""

    requested_by_display: str = ""
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    was_unclassified: bool = False
    """Constraint 24. Nobody classified this action, so it was treated as the stricter side.
    Reported rather than absorbed, or the register quietly stops matching the code."""

    @property
    def is_unassigned(self) -> bool:
        """Always `True`, and held as a property rather than assumed.

        It appears in `as_dict` and in `render` so a reader sees the claim, rather than having
        to infer it from the absence of a name.
        """
        return True

    @property
    def addressed_to(self) -> str:
        """The capability, as the string an interface shows. Never a person."""
        return self.required_capability.value

    def render(self) -> str:
        evidence_note = (
            f"{len(self.evidence)} evidence line(s) travel with it, each naming its source."
            if self.evidence
            else (
                "No evidence line travels with this request. That is a stated absence, not an "
                "empty list — whoever approves it is being asked to decide on the reason alone."
            )
        )
        unclassified = (
            " Nobody classified this action, so it was treated as the stricter side."
            if self.was_unclassified
            else ""
        )
        return (
            f"{self.action} on {self.target or 'no stated target'} needs the "
            f"{self.addressed_to} capability. {self.reason}{unclassified} {evidence_note} "
            f"{UNASSIGNED_NOTE}"
        )

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "target": self.target,
            "risk": self.risk,
            "required_capability": self.required_capability.value,
            "addressed_to": self.addressed_to,
            "is_unassigned": self.is_unassigned,
            "unassigned_note": UNASSIGNED_NOTE,
            "reason": self.reason,
            "requested_by": self.requested_by,
            "requested_by_display": self.requested_by_display,
            "was_unclassified": self.was_unclassified,
            "evidence": [
                {"kind": e.kind, "text": e.text, "source": e.source} for e in self.evidence
            ],
        }


@dataclass(frozen=True)
class GrantOutcome:
    """The result of somebody trying to satisfy a request. Always carries its reason."""

    request: ApprovalRequest
    decision: GrantDecision
    reason: str
    granted_by: str = ""
    """Empty on both refusals, and empty means *nobody granted this* — which is why the
    decision is read rather than this field being tested for truth."""

    @property
    def is_granted(self) -> bool:
        return self.decision is GrantDecision.GRANTED

    def as_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "granted_by": self.granted_by,
            "is_granted": self.is_granted,
            "request": self.request.as_dict(),
        }


def request_for(
    ruling: Ruling,
    requester: Scope,
    *,
    target: str = "",
    evidence: tuple[EvidenceItem, ...] = (),
) -> ApprovalRequest:
    """Turn a `NEEDS_APPROVAL` ruling into something a person can act on.

    Takes the requester's `Scope` rather than an identity, so a caller cannot pair one
    person's name with another's capabilities — the scope is computed as one thing, every
    turn, and stays one thing here.

    Refuses two rulings outright. An `ALLOWED` action needs no request, and manufacturing one
    would put an approval in front of somebody who was already permitted. A `REFUSED` action
    is refused by kind: `S1` says the platform stops rather than weighing the risk itself, and
    an approval request against it would imply a sufficiently senior signature exists.
    """
    if ruling.decision not in {Decision.NEEDS_APPROVAL, Decision.UNCLASSIFIED}:
        raise ApprovalRoutingError(
            f"{ruling.action} was ruled {ruling.decision.value}, which is not a request for "
            f"authority. {ruling.reason} An approval request built from this ruling would "
            f"imply somebody can sign it."
        )

    try:
        capability = Capability(ruling.required_capability)
    except ValueError as exc:
        raise ApprovalRoutingError(
            f"{ruling.action} asks for the capability "
            f"{ruling.required_capability!r}, which the Control Plane does not define. A "
            f"request addressed to a capability nobody can hold is one nobody can clear."
        ) from exc

    return ApprovalRequest(
        action=ruling.action,
        target=target,
        risk=ruling.risk.value,
        required_capability=capability,
        reason=ruling.reason,
        requested_by=identity_ref(requester.identity),
        requested_by_display=requester.identity.display_name,
        evidence=evidence,
        was_unclassified=ruling.was_unclassified,
    )


def grant(request: ApprovalRequest, approver: Scope) -> GrantOutcome:
    """May this identity satisfy this request?

    **The self-approval check runs first, deliberately.** Running the capability check first
    would let the ordering hide the interesting failure: a Supervisor raising a job holds
    `approve_work`, so every capability test they meet says yes and the only thing standing
    between them and their own signature is this comparison. Checked first, the refusal also
    reports the right reason — *you are the person who asked* rather than a capability
    complaint that is not true.
    """
    approver_ref = identity_ref(approver.identity)

    if approver_ref == request.requested_by:
        return GrantOutcome(
            request=request,
            decision=GrantDecision.REFUSED_SELF_APPROVAL,
            reason=(
                f"{approver.identity.display_name} raised this request and cannot satisfy it. "
                f"Holding the {request.addressed_to} capability does not change that — an "
                f"approval the requester can sign is not an approval. It stays unassigned and "
                f"waits for somebody else."
            ),
        )

    if request.required_capability not in approver.capabilities:
        return GrantOutcome(
            request=request,
            decision=GrantDecision.REFUSED_LACKS_CAPABILITY,
            reason=(
                f"{approver.identity.display_name} does not hold the "
                f"{request.addressed_to} capability. This is not a refusal of the request: it "
                f"stands, unassigned, and anyone holding {request.addressed_to} can act on it."
            ),
        )

    return GrantOutcome(
        request=request,
        decision=GrantDecision.GRANTED,
        reason=(
            f"{approver.identity.display_name} holds {request.addressed_to} and did not raise "
            f"this request. {request.action} may proceed."
        ),
        granted_by=approver_ref,
    )
