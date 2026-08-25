"""`RC1` as a graph — the four journeys, and a pause that survives a restart.

**Why the case lifecycle is where LangGraph earns its place, and the Copilot turn is not.**
A Copilot turn is single-shot: route, gather, explain, audit, answer. Wrapping that in a
graph would be ceremony. A **case** is the opposite — measured on the reference queue, 13
cases went straight through, 26 stopped at the checks, 2 arrived already explained by a broken
sensor and 2 by a blind model. **Two thirds pause.** A product built only for the
straight-through journey is a model viewer.

Until now those pauses were computed and discarded: the case was rebuilt from scratch on
every request, so "waiting for a technician" was a value in a response rather than a state in
the world. `langgraph-checkpoint-postgres` is what makes it a state — the graph stops at an
interrupt, the checkpoint lands in the Postgres that came up today, and the process can be
restarted underneath it.

**The graph decides nothing.** Every branch calls into `app/domain` — `can_transition` owns
the state machine, `may_advance` owns the blocking gate, `escalation` owns the routes. That is
contract 2 in `importlinter.ini` restated at the orchestration layer: a prompt change must
never alter a state transition, and here a *graph* change must not either. The nodes are
plumbing; the rules are elsewhere and are unit-tested with the GPU terminated.

**No node calls a model.** `RC1` is `SW + R` in the register. The language model decides what
to *ask* a person, never whether to ask — inherited constraint 33, and the pause points are
fixed per fault class because the trained model already declares which classes it cannot
resolve.

**The interrupt is the honest part.** A graph that filled in a missing measurement to keep
running would be exactly the failure `RC5` and constraint 20 exist to prevent: only a measured
reading settles a blocking check, and an estimate, a cannot-check and a not-applicable all
leave the gate shut. So the graph stops. Stopping is the feature.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.domain.cases import CaseState, Checklist, Finding, FindingKind, may_advance
from app.domain.escalation import Blocker, route_for


class Journey(StrEnum):
    """The four routes through `RC1`, measured on the reference queue rather than imagined."""

    STRAIGHT_THROUGH = "straight_through"
    """13 cases. The data is conclusive and nothing is asked of anybody."""

    NEEDS_A_TECHNICIAN = "needs_a_technician"
    """26 cases — the modal journey. Pauses at the checks and refuses to proceed."""

    BROKEN_SENSOR = "broken_sensor"
    """2 cases. Arrives already explained; waits for someone at the panel. `F6` routes here
    rather than dispatching a crew to a healthy machine."""

    MODEL_BLIND = "model_blind"
    """2 cases. The same, except the detector itself is the problem."""


def _merge(existing: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    """Findings accumulate across resumes rather than replacing each other.

    A resume that replaced the map would lose every answer recorded before the pause — which
    on the 26-case journey is every answer there is.
    """
    return {**(existing or {}), **(incoming or {})}


class CaseGraphState(TypedDict, total=False):
    """What travels through the graph. Serialisable, because it is checkpointed."""

    seed_key: str
    fault_label: str
    equipment_key: str
    capability: str
    journey: str
    case_state: str
    findings: Annotated[dict[str, Any], _merge]
    instrument_fault: bool
    detector_blind: bool
    blocked_reason: str
    escalation: dict[str, Any]
    history: Annotated[list[str], lambda a, b: [*(a or []), *(b or [])]]


@dataclass(frozen=True)
class CaseGraphResult:
    """Where a run stopped, and whether it stopped because it was finished."""

    state: CaseGraphState
    paused: bool
    pause_reason: str = ""

    @property
    def case_state(self) -> str:
        return self.state.get("case_state", CaseState.DETECTED.value)

    @property
    def journey(self) -> str:
        return self.state.get("journey", "")


def _classify_journey(state: CaseGraphState) -> CaseGraphState:
    """Which of the four routes this case is on.

    Order matters and is not arbitrary: an instrument fault is checked **before** anything
    else, because if the reading is wrong every other conclusion on this machine may be an
    artefact of it — and dispatching a crew to a healthy compressor is `F6`'s whole reason
    for existing.
    """
    if state.get("instrument_fault"):
        journey = Journey.BROKEN_SENSOR
        note = "an instrument contradiction was found, so the machine is not the suspect yet"
    elif state.get("detector_blind"):
        journey = Journey.MODEL_BLIND
        note = "the detector could not see this unit; absence of a fault means nothing here"
    else:
        journey = Journey.NEEDS_A_TECHNICIAN
        note = "the data does not settle this on its own"

    return {
        "journey": journey.value,
        "case_state": CaseState.DETECTED.value,
        "history": [f"classified as {journey.value}: {note}"],
    }


def _gate(state: CaseGraphState, checklist: Checklist) -> tuple[bool, str]:
    """`RC5`. Only a measured reading settles a blocking item."""
    findings = {
        item_id: Finding(
            item_id=item_id,
            kind=FindingKind(payload.get("kind", "not_answered")),
            value=payload.get("value"),
            note=payload.get("note", ""),
        )
        for item_id, payload in (state.get("findings") or {}).items()
    }
    return may_advance(checklist, findings)


def build_case_graph(checklist: Checklist):
    """Compile the graph for one fault class.

    The checklist is bound at build time rather than carried in the state, because it is
    **curated content**: putting it in a checkpoint would freeze an unreviewed library into
    every stored case, and the SME hour would then not reach cases already open.
    """

    def classify(state: CaseGraphState) -> CaseGraphState:
        return _classify_journey(state)

    def collect_findings(state: CaseGraphState) -> CaseGraphState:
        """The pause. **This is the feature, not a limitation.**

        `interrupt` suspends the graph and checkpoints it. A graph that instead filled in a
        missing measurement to keep running would be the failure constraint 20 names: an
        untagged answer once defaulted to *estimated* and opened a blocking gate.
        """
        passes, reason = _gate(state, checklist)
        if passes:
            return {
                "case_state": CaseState.AWAITING_FINDINGS.value,
                "history": [f"gate open: {reason}"],
            }

        answer = interrupt(
            {
                "reason": reason,
                "fault_label": state.get("fault_label", ""),
                "equipment_key": state.get("equipment_key", ""),
                "capability": state.get("capability", ""),
                "open_items": [
                    {
                        "id": i.id,
                        "text": i.text,
                        "capability": i.capability.value,
                        "blocking": i.blocking,
                    }
                    for i in checklist.blocking_items()
                ],
            }
        )
        return {
            "case_state": CaseState.AWAITING_FINDINGS.value,
            "findings": answer if isinstance(answer, dict) else {},
            "history": ["findings recorded on resume"],
        }

    def decide(state: CaseGraphState) -> CaseGraphState:
        """Root-caused, or escalated with the right artefact. Never 'best guess'."""
        passes, reason = _gate(state, checklist)
        if passes:
            return {
                "case_state": CaseState.ROOT_CAUSED.value,
                "blocked_reason": "",
                "history": [f"root caused: {reason}"],
            }

        # `RC7`: three routes, and they are not interchangeable. A missing *measurement* wants
        # a technician with a tool; that is a different artefact from a question of authority.
        route = route_for(Blocker.NO_TOOL)
        return {
            "case_state": CaseState.ESCALATED.value,
            "blocked_reason": reason,
            "escalation": {
                "blocker": Blocker.NO_TOOL.value,
                "goes_to": route.goes_to.value if route.goes_to else "",
                "artefact": route.artefact.value,
                "task_is_a_question": route.task_is_a_question,
                "lands_unassigned": route.lands_unassigned,
                "note": route.note,
            },
            "history": [f"escalated: {reason}"],
        }

    def route_after_findings(state: CaseGraphState) -> str:
        return "decide"

    graph = StateGraph(CaseGraphState)
    graph.add_node("classify", classify)
    graph.add_node("collect_findings", collect_findings)
    graph.add_node("decide", decide)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "collect_findings")
    graph.add_conditional_edges("collect_findings", route_after_findings, {"decide": "decide"})
    graph.add_edge("decide", END)
    return graph
