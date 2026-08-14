"""`RC7` three routes · `RC15` three artefacts · `RC16` a deterministic assignee.

**Three escalation routes, not one.** Inherited constraint 9: sideways (wrong skill), up
(authority or judgement) and defer (right person, wrong moment) are not interchangeable, and
collapsing them into a single "escalate" button loses the distinction that decides who gets
called and what they are handed.

| Blocker | Goes to | Case state | Artefact |
|---|---|---|---|
| No tool | a technician, by skill | `escalated` | an **inspection** work order —
  the open checks are its task list |
| No authority, or cannot interpret | a supervisor | `escalated` | an
  **authorisation** work order — the task is the *question*, not a measurement |
| Wrong moment | nobody — parked with a reason and a date | `deferred` | none |
| Not sure | stays with you, for confirmation | unchanged | none; it eliminates nothing |

**The system offers the handoff rather than waiting to be asked**, because a worker often
does not know they are out of their depth, that a handoff exists, or which one is right.

**`RC16`: the assignee is deterministic, never chosen by a model.** Matched by skill against
the fault, so it works with the GPU off and *"why this person"* is answerable without
replaying a prompt. Constraint 25: targeting is by **workload**, blocking items weighted
double, ties broken toward whoever can physically measure — never by seniority, because
ranking that way once sent a filter-drier restriction to a supervisor.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.cases import Capability, CaseState, ChecklistItem


class Blocker(StrEnum):
    """Why the person in front of the case cannot proceed."""

    NO_TOOL = "no_tool"
    NO_AUTHORITY = "no_authority"
    CANNOT_INTERPRET = "cannot_interpret"
    WRONG_MOMENT = "wrong_moment"
    NOT_SURE = "not_sure"


class Artefact(StrEnum):
    INSPECTION_WORK_ORDER = "inspection_work_order"
    AUTHORISATION_WORK_ORDER = "authorisation_work_order"
    NONE = "none"


@dataclass(frozen=True)
class Route:
    blocker: Blocker
    goes_to: Capability | None
    case_state: CaseState | None
    """`None` means the case does not move — *not sure* changes nothing, deliberately."""
    artefact: Artefact
    task_is_a_question: bool = False
    """True for the authorisation route. The supervisor is asked to *decide*, not to
    measure — handing them a measurement task is how the wrong person ends up at a gauge."""
    note: str = ""

    @property
    def lands_unassigned(self) -> bool:
        """Constraint 9: escalating **up** lands unassigned and says so.

        A named supervisor implies somebody accepted it. Nobody has.
        """
        return self.artefact is Artefact.AUTHORISATION_WORK_ORDER


ROUTES: dict[Blocker, Route] = {
    Blocker.NO_TOOL: Route(
        blocker=Blocker.NO_TOOL,
        goes_to=Capability.TECHNICIAN,
        case_state=CaseState.ESCALATED,
        artefact=Artefact.INSPECTION_WORK_ORDER,
        note="The open checks become its task list — nothing is re-derived by whoever picks it up.",
    ),
    Blocker.NO_AUTHORITY: Route(
        blocker=Blocker.NO_AUTHORITY,
        goes_to=Capability.SUPERVISOR,
        case_state=CaseState.ESCALATED,
        artefact=Artefact.AUTHORISATION_WORK_ORDER,
        task_is_a_question=True,
        note="Lands unassigned and says so. The task is the question, not a measurement.",
    ),
    Blocker.CANNOT_INTERPRET: Route(
        blocker=Blocker.CANNOT_INTERPRET,
        goes_to=Capability.SUPERVISOR,
        case_state=CaseState.ESCALATED,
        artefact=Artefact.AUTHORISATION_WORK_ORDER,
        task_is_a_question=True,
        note="A judgement is being asked for, so the artefact carries the question.",
    ),
    Blocker.WRONG_MOMENT: Route(
        blocker=Blocker.WRONG_MOMENT,
        goes_to=None,
        case_state=CaseState.DEFERRED,
        artefact=Artefact.NONE,
        note="Parked with a reason and a date. Nobody was called — that is the point.",
    ),
    Blocker.NOT_SURE: Route(
        blocker=Blocker.NOT_SURE,
        goes_to=None,
        case_state=None,
        artefact=Artefact.NONE,
        note=(
            "Stays with you, offered for confirmation. It eliminates nothing and moves "
            "nothing — constraint 30: 'can't tell' must have no effect at all, or "
            "uncertainty silently rules something out."
        ),
    ),
}


def route_for(blocker: Blocker) -> Route:
    return ROUTES[blocker]


@dataclass(frozen=True)
class Candidate:
    """Someone who could take the work, and the load they already carry."""

    name: str
    capability: Capability
    open_items: int = 0
    open_blocking_items: int = 0
    can_measure: bool = False
    """Tie-break. Constraint 25: ties break toward whoever can physically measure."""

    @property
    def load(self) -> int:
        """Blocking items count double — they are what actually stops other cases moving."""
        return self.open_items + self.open_blocking_items


def choose_assignee(
    candidates: tuple[Candidate, ...], capability: Capability
) -> Candidate | None:
    """`RC16`. By workload, never by seniority — and never by a model.

    Deterministic and total: the same candidate list always yields the same person, so
    *"why this person"* is answerable from the data rather than from a replayed prompt.
    """
    eligible = [c for c in candidates if c.capability is capability]
    if not eligible:
        return None
    # Lowest load first; ties toward whoever can measure; then by name so the result is
    # stable rather than dependent on input order.
    return min(eligible, key=lambda c: (c.load, not c.can_measure, c.name))


def inspection_tasks(open_items: tuple[ChecklistItem, ...]) -> tuple[str, ...]:
    """The open checks, as the inspection work order's task list. `RC15`.

    The job carries the questions rather than a summary of them, so the technician is not
    asked to work out what was already established.
    """
    return tuple(item.text for item in open_items)
