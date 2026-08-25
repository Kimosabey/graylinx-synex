"""`C9` — the approval request, and the two rules that have incidents behind them.

Constraint 9 says escalating up lands unassigned and says so. Constraint 13 says roles are
capabilities rather than ranks, and ranking by seniority once sent a filter-drier restriction
to a supervisor. Both collapse the same way in code: an `assignee` field appears, somebody
fills it in, and the request reads as though a person has accepted it.

The second half of this file is the self-approval rule. It has no incident yet, which is the
reason to test it hardest — the failure it prevents is a Supervisor raising a job and signing
it in the same breath, and every capability check they meet says yes.
"""
from __future__ import annotations

import dataclasses
import pathlib

import pytest

from app.domain.authority import Action, Decision, Risk, Ruling, rule
from app.services import approvals
from app.services.approvals import (
    ApprovalRequest,
    ApprovalRoutingError,
    GrantDecision,
    grant,
    identity_ref,
    request_for,
)
from app.services.control_plane import Capability, Persona, compute_scope

ENGINEER = compute_scope(Persona.RELIABILITY_ENGINEER)
SUPERVISOR = compute_scope(Persona.SUPERVISOR)
TECHNICIAN = compute_scope(Persona.TECHNICIAN)
ANALYST = compute_scope(Persona.ANALYST)


class _Line:
    """One evidence line, satisfying the `EvidenceItem` shape structurally.

    Written here rather than imported from `work_orders` on purpose: `approvals` must stay
    usable by anything that can produce a kind, a text and a source, and a test that imports
    the one real producer would not notice if that stopped being true.
    """

    def __init__(self, kind: str, text: str, source: str) -> None:
        self.kind = kind
        self.text = text
        self.source = source


EVIDENCE = (
    _Line("residual", "chiller current residual −20.0", "measured, 2026-04-15"),
    _Line("gate", "running: passed", "deterministic gate, evaluated before any diagnosis"),
)


def _needs_approval_ruling(scope=TECHNICIAN) -> Ruling:
    """A real `G3` ruling rather than a hand-built one — the request must survive whatever
    the authority engine actually emits, not a convenient shape."""
    held = frozenset(c.value for c in scope.capabilities)
    return rule(Action(name="raise_work_order", risk=Risk.HIGH, target="chiller_1"), held)


# ── constraint 9: addressed to a capability, and unassigned ────────────────────

def test_an_approval_request_has_no_field_that_can_hold_a_person() -> None:
    """Constraint 13's failure enters through a field name. A `assignee`, `approver` or
    `assigned_to` field is all it takes for somebody to fill one in, and then the request
    reads as accepted when nobody has accepted it.

    Asserted structurally rather than by reading the class, so adding one later fails here
    rather than in a review nobody scheduled.
    """
    names = {f.name for f in dataclasses.fields(ApprovalRequest)}
    forbidden = {"assignee", "assigned_to", "approver", "person", "owner", "user", "supervisor"}
    assert not (names & forbidden), (
        f"an approval request must not be addressed to a person; found {names & forbidden}"
    )


def test_an_approval_request_is_addressed_to_a_capability() -> None:
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    assert request.required_capability is Capability.APPROVE_WORK
    assert request.addressed_to == "approve_work"


def test_an_approval_request_says_it_is_unassigned_in_words() -> None:
    """Constraint 9: escalating up lands unassigned **and says so**. A reader who has to
    infer it from a missing name will assume somebody is holding it."""
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    assert request.is_unassigned is True
    assert "Unassigned" in request.render()
    assert "not to a person" in request.render()
    assert request.as_dict()["is_unassigned"] is True


def test_the_capability_is_the_authorization_one_not_the_checklist_role() -> None:
    """`CONTEXT.md` §11: three different things are called roles, and conflating them causes
    real routing bugs. Addressing an approval to `technician` would be the capability-role
    system answering the Control Plane's question."""
    from app.domain.cases import Capability as ChecklistRole

    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    assert request.required_capability in set(Capability)
    assert request.addressed_to not in {r.value for r in ChecklistRole}


def test_the_request_carries_the_action_its_evidence_the_capability_and_the_reason() -> None:
    """`C9`'s four contents. A request missing any of them asks somebody to decide on less
    than the person who raised it could see."""
    request = request_for(
        _needs_approval_ruling(), ENGINEER, target="chiller_1", evidence=EVIDENCE
    )
    assert request.action == "raise_work_order"
    assert request.target == "chiller_1"
    assert request.risk == Risk.HIGH.value
    assert len(request.evidence) == 2
    assert "approve_work" in request.reason
    assert all(line["source"] for line in request.as_dict()["evidence"])


def test_a_request_with_no_evidence_says_so_rather_than_showing_an_empty_list() -> None:
    """An absence is not a zero and not a dash. Whoever approves it is being asked to decide
    on the reason alone, and that is a different request from one carrying six residuals."""
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    assert "No evidence line travels with this request" in request.render()
    assert "stated absence" in request.render()


# ── the rulings that must never become a request ───────────────────────────────

def test_a_never_approvable_ruling_never_becomes_a_request() -> None:
    """`S1`: the platform stops rather than weighing the risk itself. An approval request
    against a safety-critical action would imply a sufficiently senior signature exists,
    which is the exact reading `SAFETY_CRITICAL` is a *kind* rather than a level to prevent.
    """
    ruling = rule(Action(name="stop_the_machine", risk=Risk.SAFETY_CRITICAL), frozenset())
    assert ruling.decision is Decision.REFUSED

    with pytest.raises(ApprovalRoutingError) as caught:
        request_for(ruling, ENGINEER)
    assert "imply somebody can sign it" in str(caught.value)


def test_an_allowed_ruling_never_becomes_a_request() -> None:
    """Putting an approval in front of somebody who was already permitted trains them to
    click through approvals, which is how the ones that matter get clicked through."""
    ruling = rule(Action(name="raise_work_order", risk=Risk.HIGH), frozenset({"approve_work"}))
    assert ruling.may_proceed

    with pytest.raises(ApprovalRoutingError):
        request_for(ruling, SUPERVISOR)


def test_an_unclassified_ruling_still_produces_a_request_and_says_it_was_unclassified() -> None:
    """Constraint 24. An action nobody classified is treated as the stricter side, and the
    request reports that distinctly — absorbed into an ordinary approval it would be
    invisible, and the register would stop matching the code."""
    held = frozenset(c.value for c in TECHNICIAN.capabilities)
    ruling = rule(Action(name="mystery_action"), held)
    assert ruling.decision is Decision.UNCLASSIFIED

    request = request_for(ruling, TECHNICIAN)
    assert request.was_unclassified is True
    assert "treated as the stricter side" in request.render()


def test_a_capability_the_control_plane_does_not_define_is_refused() -> None:
    """A request addressed to a capability nobody can hold is one nobody can clear — it
    would sit unassigned for ever and read as though it were waiting for a person."""
    ruling = Ruling(
        action="do_a_thing",
        risk=Risk.HIGH,
        decision=Decision.NEEDS_APPROVAL,
        required_capability="bless_the_machine",
        reason="invented capability",
    )
    with pytest.raises(ApprovalRoutingError) as caught:
        request_for(ruling, ENGINEER)
    assert "does not define" in str(caught.value)


# ── the requesting identity can never satisfy its own request ──────────────────

def test_the_requesting_identity_can_never_satisfy_its_own_request() -> None:
    """The rule this module exists for as much as constraint 9.

    A Supervisor holds `approve_work`, so every capability test they meet says yes. The only
    thing standing between them and their own signature is this comparison.
    """
    ruling = _needs_approval_ruling(TECHNICIAN)
    request = request_for(ruling, SUPERVISOR, target="chiller_1")

    outcome = grant(request, SUPERVISOR)
    assert outcome.decision is GrantDecision.REFUSED_SELF_APPROVAL
    assert outcome.is_granted is False
    assert outcome.granted_by == ""


def test_self_approval_is_refused_before_the_capability_is_even_considered() -> None:
    """Order matters, and not only for tidiness. Checked second, the refusal would report a
    capability complaint that is not true — the requester does hold it — and the next person
    to read the code would 'fix' the wrong thing."""
    request = request_for(_needs_approval_ruling(), SUPERVISOR, target="chiller_1")
    outcome = grant(request, SUPERVISOR)

    assert "raised this request and cannot satisfy it" in outcome.reason
    assert "Holding the approve_work capability does not change that" in outcome.reason
    assert "does not hold" not in outcome.reason


def test_a_different_identity_holding_the_capability_may_grant() -> None:
    """The rule must not become 'nobody may ever approve anything'."""
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    outcome = grant(request, SUPERVISOR)

    assert outcome.decision is GrantDecision.GRANTED
    assert outcome.is_granted
    assert outcome.granted_by == identity_ref(SUPERVISOR.identity)
    assert "did not raise this request" in outcome.reason


def test_lacking_the_capability_is_not_a_refusal_of_the_request() -> None:
    """`NEEDS_APPROVAL` is not `BLOCKED`. Telling a Technician they cannot sign must not read
    as telling them the job is dead — somebody down the corridor can still act on it."""
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    outcome = grant(request, TECHNICIAN)

    assert outcome.decision is GrantDecision.REFUSED_LACKS_CAPABILITY
    assert "This is not a refusal of the request" in outcome.reason
    assert "stands, unassigned" in outcome.reason


def test_two_of_the_same_persona_read_as_one_person_and_the_error_is_the_safe_one() -> None:
    """D-013: the Control Plane is a persona switcher, not authentication (`Q41`), so the
    persona is the only identity there is. Two Supervisors are indistinguishable here.

    The consequence is over-refusal — a second person gets asked — never a self-approval
    slipping through. That asymmetry is the same one constraint 24 chooses, and `Q80` carries
    the real fix.
    """
    other_supervisor = compute_scope(Persona.SUPERVISOR)
    request = request_for(_needs_approval_ruling(), SUPERVISOR, target="chiller_1")

    assert identity_ref(other_supervisor.identity) == identity_ref(SUPERVISOR.identity)
    assert grant(request, other_supervisor).decision is GrantDecision.REFUSED_SELF_APPROVAL


@pytest.mark.parametrize("approver", [SUPERVISOR, TECHNICIAN, ENGINEER, ANALYST])
def test_every_grant_outcome_carries_its_reason_in_words(approver) -> None:
    """A refusal is not an error, and a bare decision is not an answer. Whoever is looking at
    the screen has to be told what to do next."""
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    outcome = grant(request, approver)

    assert len(outcome.reason) > 40, "a decision without its reason is a shrug"
    assert outcome.reason.endswith("."), "the reason is a sentence, not a fragment"
    assert outcome.as_dict()["request"]["is_unassigned"] is True


def test_an_identity_that_holds_nothing_at_all_still_gets_a_reason() -> None:
    """The scope with the fewest capabilities in the product. It must not fall through to a
    bare `False`."""
    request = request_for(_needs_approval_ruling(), ENGINEER, target="chiller_1")
    outcome = grant(request, ANALYST)
    assert outcome.decision is GrantDecision.REFUSED_LACKS_CAPABILITY
    assert "approve_work" in outcome.reason


# ── the separation law ─────────────────────────────────────────────────────────

def test_nothing_in_the_approval_path_calls_a_model() -> None:
    """Separation law, row 7: *is this person allowed?* is decided by plain software. The
    language model never grants permission, and the cheapest way to keep that true is to give
    this module no way to reach one."""
    source = pathlib.Path(approvals.__file__).read_text(encoding="utf-8")
    for banned in ("ModelClient", "app.llm", "app.prompts", "langchain", "complete("):
        assert banned not in source, f"approvals reaches {banned}"
