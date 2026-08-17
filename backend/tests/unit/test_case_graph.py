"""`RC1` as a graph — the four journeys, and a pause that is the feature.

Two thirds of detected cases pause: 13 went straight through, 26 stopped at the checks, 2
arrived explained by a broken sensor and 2 by a blind model. A product built only for the
straight-through journey is a model viewer.

These run offline with an in-memory checkpointer. The **durable** half — a pause surviving a
process restart — is in `tests/integration/test_case_graph_durable.py`, because a checkpoint
that only exists in the process cannot prove anything about restarts.
"""
from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.case_graph import Journey, build_case_graph
from app.domain.cases import CaseState
from app.services.cases import checklist_for

LABEL = "CONDENSER_LOW_FLOW"


@pytest.fixture
def checklist():
    return checklist_for(LABEL)


@pytest.fixture
def graph(checklist):
    return build_case_graph(checklist).compile(checkpointer=InMemorySaver())


def _config(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}}


def _seed(**overrides) -> dict:
    return {
        "seed_key": f"chiller_1|{LABEL}|2026-04-15",
        "fault_label": LABEL,
        "equipment_key": "chiller_1",
        "capability": "technician",
        **overrides,
    }


def _answers(interrupt_payload: dict, kind: str, value: str | None = "4.2 bar") -> dict:
    return {
        item["id"]: {"kind": kind, "value": value}
        for item in interrupt_payload["open_items"]
    }


# ── the pause ──────────────────────────────────────────────────────────────────

async def test_the_graph_stops_when_a_blocking_item_has_no_measured_answer(graph) -> None:
    """**Stopping is the feature.** A graph that filled in a missing measurement to keep
    running would be the failure constraint 20 names — an untagged answer once defaulted to
    *estimated* and opened a blocking gate."""
    out = await graph.ainvoke(_seed(), _config("t1"))

    assert "__interrupt__" in out, "the graph must stop rather than proceed on no evidence"
    payload = out["__interrupt__"][0].value
    assert "no measured answer" in payload["reason"]
    assert payload["open_items"], "a pause must say what it is waiting for"


async def test_the_pause_names_what_it_is_waiting_for(graph) -> None:
    """A pause a person cannot act on is a hang with better manners."""
    out = await graph.ainvoke(_seed(), _config("t2"))
    payload = out["__interrupt__"][0].value

    assert payload["fault_label"] == LABEL
    assert payload["equipment_key"] == "chiller_1"
    for item in payload["open_items"]:
        assert item["text"].strip()
        assert item["capability"]


# ── only a measured reading settles a blocking check ───────────────────────────

async def test_a_measured_answer_root_causes_the_case(graph) -> None:
    out = await graph.ainvoke(_seed(), _config("t3"))
    resumed = await graph.ainvoke(
        Command(resume=_answers(out["__interrupt__"][0].value, "measured")), _config("t3")
    )
    assert resumed["case_state"] == CaseState.ROOT_CAUSED.value


@pytest.mark.parametrize("kind", ["estimated", "cannot_check", "not_applicable", "not_answered"])
async def test_nothing_but_a_measured_reading_opens_the_gate(graph, kind: str) -> None:
    """`RC5`, constraint 8 and constraint 20 in one test.

    Six "N/A" presses once opened a blocking gate with zero evidence behind it, and on the
    reference plant an untagged answer defaulted to *estimated* and did the same by a second
    route. All four of these leave the gate shut, and the case escalates rather than
    concluding.
    """
    thread = _config(f"t-{kind}")
    out = await graph.ainvoke(_seed(), thread)
    resumed = await graph.ainvoke(
        Command(resume=_answers(out["__interrupt__"][0].value, kind)), thread
    )

    assert resumed["case_state"] == CaseState.ESCALATED.value
    assert resumed["blocked_reason"]
    assert "Only a measured reading settles" in resumed["blocked_reason"]


async def test_an_escalation_carries_its_artefact_and_route(graph) -> None:
    """`RC7`: three routes, not interchangeable. A missing measurement wants a technician with
    a tool — a different artefact from a question of authority."""
    thread = _config("t-esc")
    out = await graph.ainvoke(_seed(), thread)
    resumed = await graph.ainvoke(
        Command(resume=_answers(out["__interrupt__"][0].value, "cannot_check", None)), thread
    )

    escalation = resumed["escalation"]
    assert escalation["artefact"], "an escalation with no artefact is a status change"
    assert escalation["goes_to"]
    assert escalation["note"]


# ── the four journeys ──────────────────────────────────────────────────────────

async def test_an_instrument_fault_is_classified_before_anything_else(graph) -> None:
    """`F6`. If the reading is wrong, every other conclusion on this machine may be an
    artefact of it — and dispatching a crew to a healthy compressor is the expensive mistake
    this exists to prevent."""
    out = await graph.ainvoke(_seed(instrument_fault=True), _config("t-inst"))
    assert out["journey"] == Journey.BROKEN_SENSOR.value
    assert "not the suspect yet" in out["history"][0]


async def test_a_blind_detector_is_its_own_journey(graph) -> None:
    """Inherited constraint 7: NULL means not diagnosed, never healthy. Absence of a fault
    over a blind window means nothing."""
    out = await graph.ainvoke(_seed(detector_blind=True), _config("t-blind"))
    assert out["journey"] == Journey.MODEL_BLIND.value
    assert "absence of a fault means nothing" in out["history"][0]


async def test_an_instrument_fault_outranks_a_blind_detector(graph) -> None:
    """Both true at once. Order is not arbitrary — the reading is checked first."""
    out = await graph.ainvoke(
        _seed(instrument_fault=True, detector_blind=True), _config("t-both")
    )
    assert out["journey"] == Journey.BROKEN_SENSOR.value


async def test_the_default_journey_needs_a_technician(graph) -> None:
    """26 of 43 — the modal journey, and the one the product must serve well."""
    out = await graph.ainvoke(_seed(), _config("t-default"))
    assert out["journey"] == Journey.NEEDS_A_TECHNICIAN.value


# ── findings accumulate ────────────────────────────────────────────────────────

async def test_findings_merge_across_resumes_rather_than_replacing(graph) -> None:
    """A resume that replaced the map would lose every answer recorded before the pause —
    which on the 26-case journey is every answer there is."""
    thread = _config("t-merge")
    out = await graph.ainvoke(_seed(), thread)
    first = _answers(out["__interrupt__"][0].value, "measured")
    resumed = await graph.ainvoke(
        Command(resume={**first, "extra-item": {"kind": "measured"}}), thread
    )

    assert set(resumed["findings"]) >= set(first)
    assert "extra-item" in resumed["findings"]


# ── the graph decides nothing ──────────────────────────────────────────────────

async def test_the_graph_never_writes_a_state_the_machine_forbids(graph) -> None:
    """Every state the graph produces must be a real `CaseState`. A graph that invented one
    would make the state machine advisory — contract 2 restated at the orchestration layer."""
    thread = _config("t-states")
    out = await graph.ainvoke(_seed(), thread)
    resumed = await graph.ainvoke(
        Command(resume=_answers(out["__interrupt__"][0].value, "measured")), thread
    )
    CaseState(resumed["case_state"])  # raises if the graph invented a state


async def test_no_node_calls_a_model() -> None:
    """`RC1` is `SW + R`. Asserted by reading the module rather than by trusting the docstring
    — the same shape as the role-table AST test."""
    from pathlib import Path

    source = Path("app/agents/case_graph.py").read_text(encoding="utf-8")
    for forbidden in ("app.llm", "app.prompts", "ollama", "ChatOllama"):
        assert forbidden not in source, f"{forbidden} must not appear in the case graph"
