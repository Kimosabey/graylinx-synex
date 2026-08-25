"""`G2` risk classification · `G3` the approval engine — who must approve what, and why.

**The separation law's seventh row, made mechanical.** *Is this person allowed?* is decided
by plain software — never by ML, never by the language model. This module is that software.
It holds no prompts, calls nothing, and lives in `domain` so a prompt change cannot reach it.

**Risk is a property of the action, not of the answer.** `G2` classifies what is *about to
happen* — five levels — and the classification comes from the action's own declared side
effect and target, never from how confident anything is. Confidence is qualitative by
inherited constraint 2, and deriving an approval threshold from a word would be the numeric
confidence score that constraint forbids, wearing a different hat.

**Two failure shapes this is shaped around, both with incidents behind them:**

| | Rule | Why |
|---|---|---|
| 13 | Roles are **capabilities, not ranks** | Ranking by seniority once sent a filter-drier
  restriction to a supervisor because one incidental records question outranked three
  refrigeration measurements. So an approval asks for a **named capability**, never for
  "someone more senior" |
| 24 | An untagged action defaults to the **stricter** side | Mis-tagging a high-risk action
  as low puts an unqualified decision into production; the reverse wastes an approval. Over-
  escalating is the cheap error, and the asymmetry is deliberate |

**`SAFETY_CRITICAL` is not the top of a scale — it is a different kind.** `S1` says the
platform stops and does not weigh the risk itself. A safety-critical action is therefore
never approvable by anybody in this module: it is refused and routed to a human process.
Making it "the highest level" would imply a sufficiently senior person could sign it off,
which is exactly the reading `S1` exists to prevent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Risk(StrEnum):
    """`G2`. Five levels, and the last two are kinds rather than degrees."""

    LOW = "low"
    """Reads something. No record changes, no person is dispatched."""

    MEDIUM = "medium"
    """Changes a Synex record that a human can undo — a draft, a note, a proposed grouping."""

    HIGH = "high"
    """Commits Synex to an action in the world: dispatches a person, closes a job, eliminates
    a candidate cause. Elimination is irreversible (constraint 29), which is why it lands
    here rather than at `MEDIUM`."""

    SAFETY_CRITICAL = "safety_critical"
    """Touches whether a machine keeps running, or whether somebody approaches one. **Never
    approvable here.** `S1`: the platform stops; it does not weigh the risk itself."""

    SYSTEM_CRITICAL = "system_critical"
    """Changes the rules themselves — scope, the approval matrix, the policy version. Also
    never approvable inside a turn: `G8` policy simulation is Phase 3, so a rule change today
    happens deliberately and outside the agent."""


#: Constraint 24, and the asymmetry is deliberate. An action nobody classified is treated as
#: `HIGH`, so the cost of forgetting is an approval nobody needed rather than an unreviewed
#: dispatch. Held as a constant so the default is a decision rather than a fallthrough.
DEFAULT_RISK: Risk = Risk.HIGH

#: Levels no approval can clear. Not "very high" — a different kind, and the distinction is
#: what stops somebody senior enough signing off a safety stop.
NEVER_APPROVABLE: frozenset[Risk] = frozenset({Risk.SAFETY_CRITICAL, Risk.SYSTEM_CRITICAL})


class Decision(StrEnum):
    """What the approval engine concluded. Four, and three of them are not 'no'."""

    ALLOWED = "allowed"
    """Proceed. Either the risk needs no approval, or this identity holds what it needs."""

    NEEDS_APPROVAL = "needs_approval"
    """A named capability is required and this identity does not hold it. **Not a refusal** —
    the answer state is `NEEDS_APPROVAL`, and somebody can grant it."""

    REFUSED = "refused"
    """No approval clears this. Routed to a human process outside the agent."""

    UNCLASSIFIED = "unclassified"
    """Nobody said what this action is, so it was treated as `HIGH`. Reported distinctly so
    the gap is visible rather than absorbed — an unclassified action that quietly behaved
    like a classified one is how the register stops matching the code."""


@dataclass(frozen=True)
class Action:
    """What is about to happen. The unit `G2` classifies and `G3` rules on."""

    name: str
    risk: Risk | None = None
    """`None` means unclassified. Kept nullable rather than defaulted at construction so the
    difference between *classified as high* and *nobody said* survives to the decision."""

    target: str = ""
    """What it acts on — an equipment key, a case id. Used for scope, not for risk."""

    reverses_cleanly: bool = True
    """Whether a human can undo it. An irreversible action never sits below `HIGH`."""


@dataclass(frozen=True)
class Ruling:
    """`G3`'s output. Always carries the reason in words — an absence is not a dash."""

    action: str
    risk: Risk
    decision: Decision
    required_capability: str = ""
    reason: str = ""
    was_unclassified: bool = False

    @property
    def may_proceed(self) -> bool:
        return self.decision is Decision.ALLOWED

    @property
    def is_refusal(self) -> bool:
        """`NEEDS_APPROVAL` is deliberately excluded. A refusal is not an error, and neither
        is a request for authority — collapsing them would tell a caller to give up when
        somebody down the corridor could sign."""
        return self.decision is Decision.REFUSED

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "risk": self.risk.value,
            "decision": self.decision.value,
            "required_capability": self.required_capability,
            "reason": self.reason,
            "may_proceed": self.may_proceed,
            "was_unclassified": self.was_unclassified,
        }


#: `G3`, and it is a **table rather than a chain of comparisons** on purpose. Constraint 13:
#: roles are capabilities, not ranks. A comparison like `persona >= SUPERVISOR` would rebuild
#: the seniority ladder that sent a filter-drier restriction to a supervisor, and it would do
#: it invisibly. A named capability per risk level cannot degrade into a ladder.
REQUIRED_CAPABILITY: dict[Risk, str] = {
    Risk.LOW: "",
    Risk.MEDIUM: "open_case",
    Risk.HIGH: "approve_work",
}


def classify(action: Action) -> tuple[Risk, bool]:
    """`G2`. Return the risk and whether it had to be defaulted.

    An irreversible action is raised to at least `HIGH` even when it was declared lower —
    constraint 29 makes elimination final, and a caller that under-declares a one-way door
    should not be the last word on it.
    """
    if action.risk is None:
        return DEFAULT_RISK, True

    if not action.reverses_cleanly and action.risk in {Risk.LOW, Risk.MEDIUM}:
        return Risk.HIGH, False
    return action.risk, False


def rule(action: Action, held_capabilities: frozenset[str]) -> Ruling:
    """`G3`. May this identity take this action?

    `held_capabilities` is passed in as plain strings rather than the Control Plane's enum,
    because `domain` imports nothing (contract 4) — and because that keeps this table
    testable without constructing a scope.
    """
    risk, defaulted = classify(action)

    if risk in NEVER_APPROVABLE:
        return Ruling(
            action=action.name,
            risk=risk,
            decision=Decision.REFUSED,
            reason=(
                f"{action.name} is classified {risk.value} and no approval clears it. The "
                f"platform stops here rather than weighing the risk itself; this goes to a "
                f"human process outside the agent."
            ),
            was_unclassified=defaulted,
        )

    required = REQUIRED_CAPABILITY.get(risk, "approve_work")
    if not required:
        return Ruling(
            action=action.name,
            risk=risk,
            decision=Decision.ALLOWED,
            reason=f"{action.name} is {risk.value} risk and needs no approval.",
            was_unclassified=defaulted,
        )

    if required in held_capabilities:
        return Ruling(
            action=action.name,
            risk=risk,
            decision=Decision.ALLOWED,
            required_capability=required,
            reason=f"{action.name} is {risk.value} risk and this identity holds {required!r}.",
            was_unclassified=defaulted,
        )

    unclassified_note = (
        " Nobody classified this action, so it was treated as high — the stricter side, "
        "deliberately."
        if defaulted
        else ""
    )
    return Ruling(
        action=action.name,
        risk=risk,
        decision=Decision.UNCLASSIFIED if defaulted else Decision.NEEDS_APPROVAL,
        required_capability=required,
        reason=(
            f"{action.name} is {risk.value} risk and needs the {required!r} capability, which "
            f"this identity does not hold.{unclassified_note}"
        ),
        was_unclassified=defaulted,
    )
