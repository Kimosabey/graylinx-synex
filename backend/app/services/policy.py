"""`U8` administrator scope, the approval matrix and the policy version.

**The failure this prevents: a governance screen that reads as a seniority ladder.** Ranking
capability by seniority once sent a filter-drier restriction to a supervisor, because one
incidental records question outranked three refrigeration measurements. That was a routing
decision taken by an ordering nobody intended to be an ordering, and the Administrator screen
is precisely where such an ordering gets re-established — a list of roles down a page reads as
a chain of command whatever the caption says. Inherited constraints 13 and 25: a supervisor is
not a more capable technician, it is a different capability, authority and records rather than
gauges. The evidence that the ordering is not a chain is computed here rather than asserted,
because the sentence was already written in the sibling implementation and did not hold.

**The second failure: a screen that governs nothing and does not say so.** `gl_user`, `gl_role`
and `gl_access` hold zero rows, so nothing authenticates behind this surface (`Q41`). Every
identity Synex issues is stamped `demonstration_persona` and `is_production_identity` is
hard-wired `False`. An approval matrix presented without that line would be the most misleading
screen in the product: an authoritative-looking record of who may act on a live plant, backed
by a switcher anyone reaching the page can turn.

**The third: a rule change with no way to try it first.** `G8` policy versioning and simulation
is Phase 3 and is not built, so a change to scope or to the approval matrix takes effect on its
first application and not before. That absence is reported in words on every change this module
describes, rather than left to be noticed — silence about a dry run reads as a dry run having
happened, and the review pass over the reference plant's role tags ran once, over one class, and
found an oil analysis being shown to whoever opened a compressor case. Unreviewed governance
content is not a hypothetical failure here; it is the measured state of the library.

**A change is a versioned event, never an edit.** `G2` classifies a change to the rules
`SYSTEM_CRITICAL`, and `G3` refuses it — refuses it *inside a turn*, which is a narrower
statement than forbidding it. The Administrator authors these deliberately and outside the
agent. So `PolicyChange` records an intent, carries what it supersedes and what it would become,
and has no method that applies one.

**What this module is over.** `app/services/control_plane.py` computes a scope per turn (`G1`)
and `app/domain/authority.py` classifies risk and rules on approvals (`G2`, `G3`). This is the
read surface over both, and it **restates nothing**: the matrix rows are the approval engine's
own output against a probe action, and the capability holders come from `compute_scope`, the
same path a live turn uses. A capability added to the Control Plane therefore appears here
without an edit, and the two cannot disagree. `CLAUDE.md` §2.8, one source of truth per fact.

**Nothing here calls a model, and the policy version is a string rather than a count.** `U8`
and `G1`/`G3` are `SW` in the register; `G2` is `R`. There is no prompt in this module, and
contract 2 in `importlinter.ini` makes that a build failure rather than a convention.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.authority import (
    Action,
    Decision,
    Risk,
    Ruling,
    rule,
)
from app.services.control_plane import (
    IDENTITY_KIND,
    Capability,
    Persona,
    Scope,
    compute_scope,
)

# ── what this surface is honest about not having ────────────────────────────────


@dataclass(frozen=True)
class MissingCapability:
    """Something a reader would reasonably expect an Administrator screen to offer.

    Held as a record with the reason in words rather than as a flag, because a governance
    surface that is merely silent about a missing control is read as having it. Every field is
    prose a person can act on — there is no bare `False` anywhere in this module's absences.
    """

    name: str
    source: str
    """The feature or question this absence traces to — `G8`, `Q41`, `Q76`."""

    reason: str

    def render(self) -> str:
        return f"{self.name} — not available. {self.reason}"


#: The sentence `G8`'s absence requires, held once because two places need it: the missing-
#: capability list a reader sees, and every `PolicyChange` that records why it was not tried
#: beforehand. A second copy would let one of them go stale when Phase 3 lands.
NO_DRY_RUN: str = (
    "Policy versioning and simulation is Phase 3 and is not built. There is no dry run: a "
    "change to scope or to the approval matrix takes effect the first time it is applied, "
    "against real cases, with no prior comparison of what would have been decided differently. "
    "This is stated rather than omitted because a governance screen that says nothing about "
    "testing a rule change is read as having tested it."
)

#: `G8` is Phase 3, `Q41` is unanswered, and authoring today means editing Python. Named
#: individually so a reader sees three distinct gaps rather than one vague disclaimer.
NOT_AVAILABLE: tuple[MissingCapability, ...] = (
    MissingCapability(
        name="Try a rule change before it goes live",
        source="G8",
        reason=NO_DRY_RUN,
    ),
    MissingCapability(
        name="Authenticate an administrator",
        source="Q41",
        reason=(
            "There is no authentication library in the back end and `gl_user`, `gl_role` and "
            "`gl_access` hold zero rows. D-013 makes this a labelled persona switcher instead, "
            "so anyone who can reach the switcher can select Administrator. The signature on "
            "the persona token protects the transport, never the identity."
        ),
    ),
    MissingCapability(
        name="Edit scope or the approval matrix from this surface",
        source="Q76",
        reason=(
            "The persona-to-capability map is a module-level constant in the Control Plane and "
            "the required capability per risk level is a constant in the authority table, so "
            "authoring either one is a code change reviewed like any other. No document states "
            "whether an Administrator edits capabilities at run time, or which capabilities one "
            "may grant — so this surface reads them and does not offer to write them. "
            "TBD (Q76)."
        ),
    ),
)


# ── the policy version ──────────────────────────────────────────────────────────

#: Why a policy version is a string. `2026-08-13.1` is date-and-counter shaped, but no document
#: states the scheme, what increments it, or who may. Treating it as a number would invite
#: arithmetic on it — "two versions behind" — which nothing in the programme has defined.
#:
#: TBD (Q74): the versioning scheme and the trigger that advances it are both unstated.
VERSION_IS_A_STRING: str = (
    "The policy version is an opaque string. Nothing compares two of them for order, because "
    "no document defines the scheme or what advances it (Q74) — it exists to be stamped on "
    "every audit row and quoted back, so that a decision can be traced to the rules in force "
    "when it was taken."
)

#: A change cannot be attributed to a person, and that is a property of `Q41` rather than of
#: this module. Recorded as the identity kind, which is true, instead of a name, which would
#: not be — an audit row naming an author it cannot verify is worse than one naming none.
#:
#: TBD (Q75): who a policy change is attributable to once identity is real.
UNATTRIBUTABLE_AUTHOR: str = (
    f"recorded as {IDENTITY_KIND!r} — no person can be named, because nothing authenticates "
    f"one yet (Q41, Q75)"
)


@dataclass(frozen=True)
class PolicyVersion:
    """The string every decision is stamped with.

    Absence is a sentence, not an empty field: a screen showing a blank policy version implies
    a version too dull to print, when in fact nothing was stamped and no decision taken under
    it can be traced to a rule set.
    """

    version: str

    @property
    def is_stated(self) -> bool:
        return bool(self.version.strip())

    def render(self) -> str:
        if not self.is_stated:
            return (
                "No policy version is set, so decisions taken now cannot be traced back to the "
                "rules that were in force. This is a configuration gap, not a version of zero."
            )
        return f"policy version {self.version}, in force for every decision stamped with it"

    def as_dict(self) -> dict:
        return {
            "version": self.version if self.is_stated else None,
            "is_stated": self.is_stated,
            "statement": self.render(),
            "version_is_a_string": VERSION_IS_A_STRING,
        }


@dataclass(frozen=True)
class PolicyChange:
    """An intent to change the rules. Recorded as an event, never applied as an edit.

    `G2` classifies this `SYSTEM_CRITICAL` and `G3` refuses it inside a turn, so this object
    describes a change and offers no way to make one. It carries `supersedes` and `becomes`
    together because that pair is what makes the change a version rather than a mutation — a
    record showing only the new state cannot answer *what did this replace*, which is the
    question an audit asks first.
    """

    what_changes: str
    reason: str
    supersedes: str
    becomes: str
    authored_by: str = UNATTRIBUTABLE_AUTHOR
    tried_first: str = NO_DRY_RUN
    """Why this change was not tested beforehand, in words. Never a flag — `G8` is Phase 3, and
    a boolean `False` here would be read as a step somebody skipped rather than one that does
    not exist."""

    @property
    def risk(self) -> Risk:
        """Always `SYSTEM_CRITICAL`. A property rather than a field so a caller cannot declare
        a rule change as anything milder."""
        return Risk.SYSTEM_CRITICAL

    @property
    def action(self) -> Action:
        """The unit `G2` classifies and `G3` rules on. `reverses_cleanly` is `False`: decisions
        already taken under the superseded version stay taken, so withdrawing a rule change
        does not withdraw its consequences."""
        return Action(
            name=f"change policy: {self.what_changes}",
            risk=self.risk,
            target=self.becomes,
            reverses_cleanly=False,
        )

    def render(self) -> str:
        return (
            f"{self.what_changes}: {self.supersedes} would become {self.becomes}. "
            f"Reason: {self.reason} Authored by {self.authored_by}. This is a new version of "
            f"the policy, not an edit to the current one — the superseded version stays on "
            f"record, and every decision already stamped with it stays stamped. "
            f"Not tried beforehand: {self.tried_first}"
        )

    def as_dict(self) -> dict:
        return {
            "what_changes": self.what_changes,
            "reason": self.reason,
            "supersedes": self.supersedes,
            "becomes": self.becomes,
            "authored_by": self.authored_by,
            "risk": self.risk.value,
            "tried_first": self.tried_first,
            "statement": self.render(),
        }


def ruling_on(change: PolicyChange, scope: Scope) -> Ruling:
    """May this identity apply this change inside a turn? Always no, and `G3` says so.

    Delegated in full to `app/domain/authority.py` rather than decided here: this module is a
    surface, and a surface that reached its own authorisation conclusion would be a second
    approval engine — the shape of drift the separation law's seventh row exists to prevent.

    The refusal is narrow and worth reading precisely. It says the change cannot be made
    *inside the agent*, holding `edit_policy` or not. It does not say the Administrator may not
    author policy; that is their job, and it happens deliberately, outside a turn, reviewed.
    """
    return rule(change.action, frozenset(c.value for c in scope.capabilities))


# ── the approval matrix, as data ────────────────────────────────────────────────


class Requirement(StrEnum):
    """What a risk level asks for. Four, and only one of them is a refusal."""

    NO_APPROVAL = "no_approval"
    """Anyone in scope may proceed. Nothing is dispatched and no record changes."""

    NAMED_CAPABILITY = "named_capability"
    """A specific capability clears it. **Never "someone more senior"** — constraint 13, and
    the filter-drier restriction is what a rank-shaped requirement produced."""

    NO_APPROVAL_CLEARS_IT = "no_approval_clears_it"
    """A different kind rather than a higher degree. Nobody can sign this off here."""

    UNSTATED = "unstated"
    """The approval engine returned something this matrix has no row shape for. Reported as a
    gap rather than absorbed into the strictest row, so a new risk level shows up as an
    unanswered question instead of quietly behaving like an answered one."""


#: `Decision` to `Requirement`, held as a table so the mapping is inspectable and so adding a
#: decision is a visible edit rather than a branch somebody forgets. `UNCLASSIFIED` cannot
#: reach here — every probe declares its risk — and is mapped anyway, because a missing key
#: that silently became the strictest row is the mis-count `CLAUDE.md` §2.7 warns about.
_DECISION_REQUIREMENT: dict[Decision, Requirement] = {
    Decision.ALLOWED: Requirement.NO_APPROVAL,
    Decision.NEEDS_APPROVAL: Requirement.NAMED_CAPABILITY,
    Decision.REFUSED: Requirement.NO_APPROVAL_CLEARS_IT,
    Decision.UNCLASSIFIED: Requirement.UNSTATED,
}

#: Why each never-approvable level is a *kind* and not the top of a scale. Held per level
#: because the two reasons are unrelated and collapsing them to "refused" would leave a reader
#: assuming a sufficiently senior person could sign either one off — the reading `S1` exists to
#: prevent. Sourced: `CONTEXT.md` §10a for the missing safety class, `G8`'s phase for the other.
NEVER_APPROVABLE_BECAUSE: dict[Risk, str] = {
    Risk.SAFETY_CRITICAL: (
        "Whether a machine keeps running, or whether somebody approaches one. The platform "
        "stops and does not weigh the risk itself (`S1`), so this leaves Synex for a human "
        "process — it does not travel up to a more senior approver. The reference plant's fault "
        "taxonomy carries no safety impact class at all: every escalation route ended in a work "
        "order, with no way to say stop the machine now, which is why `S6` exists."
    ),
    Risk.SYSTEM_CRITICAL: (
        "A change to scope, to the approval matrix or to the policy version. Refused inside a "
        "turn rather than forbidden outright: the Administrator authors these, deliberately and "
        "outside the agent. It cannot happen within a turn because `G8` simulation is Phase 3, "
        "so there would be no way to see what the change would have decided differently."
    ),
}


@dataclass(frozen=True)
class ApprovalRow:
    """One risk level, and what clears it. The row is the engine's output, not a paraphrase.

    `risk` carries the level and nothing restates what that level *means* — that definition
    lives on `authority.Risk` and belongs in one place. What is added here is `who`: the names
    of the personas that currently hold the required capability, which the authority table
    cannot know because `domain` imports nothing.
    """

    risk: Risk
    requirement: Requirement
    required_capability: str
    holders: tuple[str, ...]
    who: str

    def render(self) -> str:
        return f"{self.risk.value}: {self.who}"

    def as_dict(self) -> dict:
        return {
            "risk": self.risk.value,
            "requirement": self.requirement.value,
            "required_capability": self.required_capability or None,
            "holders": list(self.holders),
            "who": self.who,
        }


def capability_holders() -> dict[str, tuple[str, ...]]:
    """Which personas hold each capability, by capability value.

    Derived by asking `compute_scope` for every persona — the same call a live turn makes — so
    this cannot drift from what the Control Plane actually grants. A hand-written table here
    would be a second source of truth for the one fact that decides routing.

    **Holders are listed alphabetically, and that claims nothing.** Any other order would be
    read as a ranking; see `ORDER_NOTE`.
    """
    holders: dict[str, list[str]] = {c.value: [] for c in Capability}
    for persona in Persona:
        scope = compute_scope(persona)
        for capability in scope.capabilities:
            holders[capability.value].append(scope.identity.display_name)
    return {name: tuple(sorted(names)) for name, names in holders.items()}


def _row_for(risk: Risk, holders: dict[str, tuple[str, ...]]) -> ApprovalRow:
    """One matrix row, obtained by putting a probe action through `G3` itself.

    The probe is why this module restates nothing. Reading `REQUIRED_CAPABILITY` directly would
    reproduce the engine's table without its rules — the raise-to-`HIGH` on an irreversible
    action, the never-approvable refusal — and a matrix that disagreed with the engine on a
    corner would be worse than no matrix, because a reader would trust it.
    """
    ruling = rule(Action(name=f"any {risk.value} action", risk=risk), frozenset())
    requirement = _DECISION_REQUIREMENT.get(ruling.decision, Requirement.UNSTATED)

    if requirement is Requirement.NO_APPROVAL_CLEARS_IT:
        return ApprovalRow(
            risk=risk,
            requirement=requirement,
            required_capability="",
            holders=(),
            who=NEVER_APPROVABLE_BECAUSE.get(
                risk,
                "no approval clears this level, and no reason has been recorded for why — "
                "which is itself the finding. TBD (Q76).",
            ),
        )

    if requirement is Requirement.NO_APPROVAL:
        return ApprovalRow(
            risk=risk,
            requirement=requirement,
            required_capability="",
            holders=(),
            who=(
                "No approval is required, so no capability gates it and no persona is named. "
                "Nothing is dispatched and no record changes."
            ),
        )

    who_holds = holders.get(ruling.required_capability, ())
    if who_holds:
        named = ", ".join(who_holds)
        who = (
            f"Cleared by the {ruling.required_capability!r} capability, held by {named}. A "
            f"named capability, never seniority — nobody clears this by being more senior."
        )
    else:
        who = (
            f"Cleared by the {ruling.required_capability!r} capability, which no persona "
            f"currently holds. Every action at this level would wait for an approval nobody "
            f"can give — a gap in the capability map, not a refusal."
        )
    return ApprovalRow(
        risk=risk,
        requirement=requirement,
        required_capability=ruling.required_capability,
        holders=who_holds,
        who=who,
    )


def approval_matrix() -> tuple[ApprovalRow, ...]:
    """`G3` as a table a person can read, one row per risk level.

    Row order follows `Risk`'s own declaration so the matrix cannot fall out of step with the
    enum. That order is deliberately *not* a ranking past the third row: the first three levels
    are degrees of consequence, and the last two are different kinds — which is exactly why
    they carry their own words instead of an empty approval cell.
    """
    holders = capability_holders()
    return tuple(_row_for(risk, holders) for risk in Risk)


# ── personas and their capabilities, with no ordering implied ───────────────────

#: Read out beside any list of personas on this surface. Constraints 13 and 25, and the reason
#: the note is a constant rather than a caption somebody may drop when the layout changes.
ORDER_NOTE: str = (
    "Personas are listed alphabetically, which claims nothing. Roles are capabilities, not "
    "ranks, and the order they appear in is display order rather than a ladder: a supervisor is "
    "not a more capable technician but a different capability — authority and records, not "
    "gauges. Reading the list as seniority once sent a filter-drier restriction to a supervisor, "
    "because one incidental records question outranked three refrigeration measurements."
)


@dataclass(frozen=True)
class PersonaCapabilities:
    """One persona and what it may do. Capabilities sorted alphabetically, for the same reason."""

    persona: Persona
    display_name: str
    capabilities: tuple[str, ...]

    def render(self) -> str:
        if not self.capabilities:
            return (
                f"{self.display_name} holds no capabilities at all, which is a gap in the "
                f"capability map rather than a restriction somebody chose."
            )
        return f"{self.display_name} holds {', '.join(self.capabilities)}"

    def as_dict(self) -> dict:
        return {
            "persona": self.persona.value,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
        }


def persona_capabilities() -> tuple[PersonaCapabilities, ...]:
    """Every persona and its capabilities, derived from `compute_scope`.

    Sorted by display name. Sorting by the number of capabilities held would rebuild the ladder
    in a single line of code, invisibly, and it would look like a helpful default.
    """
    rows = []
    for persona in Persona:
        scope = compute_scope(persona)
        rows.append(
            PersonaCapabilities(
                persona=persona,
                display_name=scope.identity.display_name,
                capabilities=tuple(sorted(c.value for c in scope.capabilities)),
            )
        )
    return tuple(sorted(rows, key=lambda r: r.display_name))


@dataclass(frozen=True)
class OrderingReport:
    """Whether the personas can be laid out as a ladder at all — computed, not asserted.

    Containment is reported honestly because some of it is real: one persona's capabilities may
    genuinely be a subset of another's. What matters is that no single chain covers everybody,
    and the incomparable pairs are the arithmetic that proves it. A test asserts this rather
    than trusting the sentence, because the sentence was already written elsewhere and the code
    beneath it ranked by seniority anyway.
    """

    contained_pairs: tuple[tuple[str, str], ...]
    """`(inner, outer)` — every capability the first holds, the second also holds."""

    incomparable_pairs: tuple[tuple[str, str], ...]
    """Each holds something the other does not. Neither can be above the other."""

    finding: str

    @property
    def forms_a_ladder(self) -> bool:
        """`True` only if every pair is comparable. It is not, and it must not become so."""
        return not self.incomparable_pairs


def ordering_report() -> OrderingReport:
    """The proof that the capability sets are not a ranking.

    Constraint 25 says role order is display order and not a capability ladder. This computes
    whether that holds: if every pair of personas were comparable by containment, the sets
    *would* form a chain and any display order would read correctly as seniority. They are not,
    and naming which pairs are incomparable is what makes the claim checkable.
    """
    rows = persona_capabilities()
    contained: list[tuple[str, str]] = []
    incomparable: list[tuple[str, str]] = []

    for i, first in enumerate(rows):
        for second in rows[i + 1 :]:
            left, right = set(first.capabilities), set(second.capabilities)
            if left < right:
                contained.append((first.display_name, second.display_name))
            elif right < left:
                contained.append((second.display_name, first.display_name))
            elif left != right:
                incomparable.append((first.display_name, second.display_name))

    if incomparable:
        pairs = "; ".join(f"{a} and {b}" for a, b in incomparable)
        finding = (
            f"These capability sets do not form a ladder. {len(incomparable)} pair(s) are "
            f"incomparable — each holds something the other does not, so neither is above the "
            f"other: {pairs}. Any display order is therefore a display order."
        )
    else:
        finding = (
            "Every pair of personas is comparable by containment, so this list would read "
            "correctly as a ladder — and constraint 25 says it must not. That is a finding "
            "about the capability map, not a feature of this surface."
        )
    return OrderingReport(
        contained_pairs=tuple(sorted(contained)),
        incomparable_pairs=tuple(sorted(incomparable)),
        finding=finding,
    )


# ── the surface itself ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AdministratorView:
    """`U8`. Everything the Administrator surface holds, in one immutable read.

    The identity lines come first in `render` on purpose. Every other line on this screen is
    only as true as the identity behind it, and the identity is a demonstration persona.
    """

    policy: PolicyVersion
    identity_kind: str
    identity_note: str
    matrix: tuple[ApprovalRow, ...]
    personas: tuple[PersonaCapabilities, ...]
    ordering: OrderingReport
    order_note: str
    not_available: tuple[MissingCapability, ...]

    @property
    def is_production_identity(self) -> bool:
        """Hard-wired `False`, mirroring `Identity.is_production_identity` deliberately.

        Not read from a setting and not derived. If this ever returns `True`, `Q41` has been
        answered and somebody has replaced these lines on purpose — which is the size of act it
        should be, on the one screen where getting it wrong is worst.
        """
        return False

    def as_dict(self) -> dict:
        return {
            "policy": self.policy.as_dict(),
            "identity_kind": self.identity_kind,
            "identity_note": self.identity_note,
            "is_production_identity": self.is_production_identity,
            "approval_matrix": [row.as_dict() for row in self.matrix],
            "personas": [row.as_dict() for row in self.personas],
            "order_note": self.order_note,
            "ordering": {
                "forms_a_ladder": self.ordering.forms_a_ladder,
                "contained_pairs": [list(p) for p in self.ordering.contained_pairs],
                "incomparable_pairs": [list(p) for p in self.ordering.incomparable_pairs],
                "finding": self.ordering.finding,
            },
            "not_available": [
                {"name": m.name, "source": m.source, "reason": m.reason}
                for m in self.not_available
            ],
        }

    def render(self) -> str:
        lines = [
            self.identity_note,
            self.policy.render(),
            *(f"{row.risk.value}: {row.who}" for row in self.matrix),
            self.order_note,
            *(row.render() for row in self.personas),
            self.ordering.finding,
            *(m.render() for m in self.not_available),
        ]
        return "\n".join(lines)


#: The line that must appear on the Administrator screen before anything else on it is read.
IDENTITY_NOTE: str = (
    f"Identity kind {IDENTITY_KIND!r}. This is not a production identity and cannot become one "
    f"from a setting: there is no authentication in the back end and `gl_user`, `gl_role` and "
    f"`gl_access` hold zero rows (Q41). Everything below describes the rules Synex applies to a "
    f"selected demonstration persona, not a record of who may act on a live plant."
)


def administrator_view(policy_version: str) -> AdministratorView:
    """Build the `U8` surface.

    `policy_version` is passed in rather than read from configuration, following `audit_row` in
    the Control Plane — the routes already hold the setting, and a service that reached for
    configuration itself would make this untestable without one. `CLAUDE.md` §2.8 again: the
    version has one home, and this is a reader of it.
    """
    return AdministratorView(
        policy=PolicyVersion(version=policy_version),
        identity_kind=IDENTITY_KIND,
        identity_note=IDENTITY_NOTE,
        matrix=approval_matrix(),
        personas=persona_capabilities(),
        ordering=ordering_report(),
        order_note=ORDER_NOTE,
        not_available=NOT_AVAILABLE,
    )
