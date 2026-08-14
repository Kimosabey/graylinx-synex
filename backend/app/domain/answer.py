"""The answer contract — the six states a turn may end in.

`CONTEXT.md` §7 is the authority and this is its executable form. It lives in `domain`
because `domain` is the leaf: the agent graph, the API and the streaming contract all need
these six, and a leaf is the only place all three can reach without an upward import.

**Six states, and `NO_DIAGNOSIS` is one of them rather than a variety of failure.** That
distinction is the product. A refusal means *the gates did not pass, and here is which one*;
a failure means *the software broke*. Collapsing them makes an honest refusal look like a
bug — and on this data the refusal is the modal outcome, 5,309 slots against 674 faulted
ones, so the collapse would mis-describe most of what the platform does.
"""
from __future__ import annotations

from enum import StrEnum


class AnswerState(StrEnum):
    """How a turn ended. Exactly one per turn — see `TERMINAL_STATE_FRAME`."""

    ANSWERED = "ANSWERED"
    """The question was answered, grounded, and every audit passed."""

    PARTIAL = "PARTIAL"
    """Some of the question was answered. What was not is named, not omitted.

    Constraint 14: a figure is a value or a stated absence, never neither. The same rule
    applied to a whole turn."""

    NO_DIAGNOSIS = "NO_DIAGNOSIS"
    """A gate did not pass, so no fault is named. **This is a feature.**

    `CLAUDE.md` §2.6 forbids softening it. It carries the gate that failed, the reason, and
    what would change the answer — which is what makes it useful rather than a shrug."""

    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    """The action is prepared and waits on a human with the authority to permit it.

    The Control Plane decides this, never the language model — separation law, row 7."""

    BLOCKED = "BLOCKED"
    """Policy or scope forbids it. The person is not allowed, or the data is out of scope."""

    FAILED = "FAILED"
    """The software broke. Distinct from every state above, and the only one that is a bug."""


#: Iteration order for display and for the evaluation suite. Declaration order, held
#: explicitly so a future reorder of the enum cannot silently reorder a report.
ANSWER_STATES: tuple[str, ...] = tuple(s.value for s in AnswerState)

#: The states in which the platform declined to produce an answer for an *honest* reason.
#: `FAILED` is deliberately absent: a crash is not honesty.
NON_ANSWER_STATES: frozenset[str] = frozenset(
    {AnswerState.NO_DIAGNOSIS.value, AnswerState.BLOCKED.value}
)

#: The one state that must never be styled like the others. D-015.
REFUSAL_STATE: str = AnswerState.NO_DIAGNOSIS.value


def is_answer_state(value: str) -> bool:
    return value in ANSWER_STATES
