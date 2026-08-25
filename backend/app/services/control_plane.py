"""The Control Plane — who is asking, what they may see, and the record that they asked.

**Plain software decides this. Never ML, never the language model.** Separation law, row 7.
There is no prompt in this module and no model call, and contract 2 in `importlinter.ini`
makes that a build failure rather than a convention.

**D-013: this is a persona switcher, not authentication.** `Q41` is unanswered — there is no
authentication library in the backend and `gl_user`/`gl_role`/`gl_access` hold zero rows —
so the demonstration-safe fallback is a labelled switcher that lets `G1`'s scoping logic be
built and tested against a known identity without committing to any of the three routes.

The danger with a stand-in is that it stops being one. So every identity this module issues
carries `identity_kind='demonstration_persona'`, every audit row records it, and
`is_production_identity` is hard-wired `False`. Turning this into real authentication has to
be a deliberate act that changes these lines, not a config flag someone flips.

**Scope is recomputed every turn, never inherited.** A scope carried forward from a previous
turn is a scope that outlives the reason it was granted — and in a conversation the previous
turn may have been a different persona entirely.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain import equipment as eq

#: Stamped on every identity and every audit row. The string is deliberately ugly and
#: specific: nobody reads `demonstration_persona` in a production log and assumes it is fine.
IDENTITY_KIND: str = "demonstration_persona"


class Persona(StrEnum):
    """The four personas that need a surface of their own, plus the read-only ones.

    `CONTEXT.md` §11 warns that three different things are called roles. This is the *user
    persona* system — it decides scope and answer depth. It is not the capability-role system
    that decides who can answer a checklist item, and it is not the agent-skill registry.
    """

    RELIABILITY_ENGINEER = "reliability_engineer"
    TECHNICIAN = "technician"
    SUPERVISOR = "supervisor"
    ADMINISTRATOR = "administrator"
    ANALYST = "analyst"


#: Display names. Held here rather than derived from the enum so that "Reliability Engineer"
#: does not become "Reliability_Engineer" in an interface through a `.title()` call.
PERSONA_DISPLAY: dict[Persona, str] = {
    Persona.RELIABILITY_ENGINEER: "Reliability Engineer",
    Persona.TECHNICIAN: "Technician",
    Persona.SUPERVISOR: "Supervisor",
    Persona.ADMINISTRATOR: "Administrator",
    Persona.ANALYST: "Analyst",
}


class Capability(StrEnum):
    """What a persona may do. Capabilities, not ranks.

    Inherited constraint 13, and constraint 25: a supervisor is not a more capable
    technician, it is a different capability — authority and records, not gauges. Ranking by
    seniority once sent a filter-drier restriction to a supervisor because one incidental
    records question outranked three refrigeration measurements.
    """

    VIEW_FAULTS = "view_faults"
    VIEW_RESIDUALS = "view_residuals"
    OPEN_CASE = "open_case"
    RECORD_FINDINGS = "record_findings"
    APPROVE_WORK = "approve_work"
    CLOSE_WORK = "close_work"
    EDIT_POLICY = "edit_policy"


_CAPABILITIES: dict[Persona, frozenset[Capability]] = {
    Persona.RELIABILITY_ENGINEER: frozenset(
        {Capability.VIEW_FAULTS, Capability.VIEW_RESIDUALS, Capability.OPEN_CASE}
    ),
    Persona.TECHNICIAN: frozenset({Capability.VIEW_FAULTS, Capability.RECORD_FINDINGS}),
    Persona.SUPERVISOR: frozenset(
        {
            Capability.VIEW_FAULTS,
            Capability.APPROVE_WORK,
            Capability.CLOSE_WORK,
        }
    ),
    Persona.ADMINISTRATOR: frozenset({Capability.VIEW_FAULTS, Capability.EDIT_POLICY}),
    Persona.ANALYST: frozenset({Capability.VIEW_FAULTS, Capability.VIEW_RESIDUALS}),
}


@dataclass(frozen=True)
class Identity:
    """Who is asking. Never a production identity, and it says so in three places."""

    persona: Persona
    display_name: str
    identity_kind: str = IDENTITY_KIND

    @property
    def is_production_identity(self) -> bool:
        """Hard-wired `False`. Not a setting, and not derived from anything.

        If this ever needs to return `True`, `Q41` has been answered and somebody has
        deliberately replaced this module — which is exactly the size of act it should be.
        """
        return False


@dataclass(frozen=True)
class Scope:
    """What this identity may see, recomputed for this turn only."""

    identity: Identity
    equipment_keys: frozenset[str]
    capabilities: frozenset[Capability]
    computed_at: float

    def allows(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def covers(self, equipment_key: str) -> bool:
        return equipment_key in self.equipment_keys

    def as_dict(self) -> dict:
        return {
            "persona": self.identity.persona.value,
            "display_name": self.identity.display_name,
            "identity_kind": self.identity.identity_kind,
            "is_production_identity": self.identity.is_production_identity,
            "equipment": sorted(self.equipment_keys),
            "capabilities": sorted(c.value for c in self.capabilities),
        }


def compute_scope(persona: Persona) -> Scope:
    """Build the scope for this turn. Called every turn; never cached.

    The single site: one facility, roughly ten units, and every persona sees all of it. That
    is honest for the demonstration rather than a simplification hidden behind a flag — a
    second site is one of the triggers `CONTEXT.md` §12 names as out of scope.
    """
    return Scope(
        identity=Identity(persona=persona, display_name=PERSONA_DISPLAY[persona]),
        equipment_keys=frozenset(e.key for e in eq.all_equipment()),
        capabilities=_CAPABILITIES[persona],
        computed_at=time.time(),
    )


# ── the signed persona cookie ───────────────────────────────────────────────────

class PersonaTokenError(ValueError):
    """The token was absent, malformed, tampered with, or signed with another secret."""


def issue_persona_token(persona: Persona, secret: str) -> str:
    """An HMAC-signed persona claim.

    Signed rather than plain so a viewer cannot silently become an Administrator by editing
    a cookie during a demonstration. It is **not** authentication: anyone who can reach the
    switcher can pick any persona. The signature protects the transport, not the identity,
    and that distinction is the whole of D-013.
    """
    payload = json.dumps(
        {"persona": persona.value, "kind": IDENTITY_KIND}, separators=(",", ":"), sort_keys=True
    )
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{signature}"


def read_persona_token(token: str, secret: str) -> Persona:
    """Verify and decode. Raises rather than falling back to a default persona.

    A malformed token that quietly became `TECHNICIAN` would be an authorization decision
    made by a parsing accident, which is the failure the separation law's seventh row exists
    to prevent.
    """
    try:
        payload, signature = token.rsplit("|", 1)
    except ValueError as exc:
        raise PersonaTokenError("token is not payload|signature") from exc

    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise PersonaTokenError("signature does not match")

    try:
        claim = json.loads(payload)
        return Persona(claim["persona"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise PersonaTokenError(f"token payload is not a known persona: {exc}") from exc


# ── the audit trail ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AuditRow:
    """One row per request. `G6`, and it is M1 rather than later for a reason.

    An audit trail added after the fact records only what somebody remembered to log. Written
    from the start, it records every turn including the ones nobody expected.
    """

    request_id: str
    persona: str
    identity_kind: str
    action: str
    equipment_key: str | None
    answer_state: str
    policy_version: str
    gates_failed: tuple[str, ...] = field(default_factory=tuple)
    at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "persona": self.persona,
            "identity_kind": self.identity_kind,
            "action": self.action,
            "equipment_key": self.equipment_key,
            "answer_state": self.answer_state,
            "policy_version": self.policy_version,
            "gates_failed": list(self.gates_failed),
            "at": self.at,
        }


def audit_row(
    *,
    request_id: str,
    scope: Scope,
    action: str,
    answer_state: str,
    policy_version: str,
    equipment_key: str | None = None,
    gates_failed: tuple[str, ...] = (),
) -> AuditRow:
    """Build the row. `identity_kind` comes from the scope, never from the caller.

    Letting a caller pass it would allow a route to log a demonstration turn as something
    else, which is precisely the drift the field exists to make visible.
    """
    return AuditRow(
        request_id=request_id,
        persona=scope.identity.persona.value,
        identity_kind=scope.identity.identity_kind,
        action=action,
        equipment_key=equipment_key,
        answer_state=answer_state,
        policy_version=policy_version,
        gates_failed=gates_failed,
    )
