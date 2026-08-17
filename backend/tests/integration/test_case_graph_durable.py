"""The pause survives a restart — `RC1` on the Postgres checkpointer.

**Why this test is separate from `tests/unit/test_case_graph.py`.** An in-memory checkpointer
proves the graph pauses; it cannot prove the pause is *real*. Until today, "waiting for a
technician" survived exactly as long as the process did, because the case was rebuilt from
scratch on every request. That is the difference this file exists to assert.

The restart is simulated the only honest way: the saver is closed, a **new** saver is opened
and a **new** graph object compiled, and the case is resumed through those. Nothing from the
first run is in memory.

    docker compose -f infra/docker-compose.yml up -d postgres
"""
from __future__ import annotations

import uuid

import pytest
from langgraph.types import Command

from app.agents.case_graph import build_case_graph
from app.config import Settings
from app.db.session import graph_checkpointer
from app.domain.cases import CaseState
from app.services.cases import checklist_for

pytestmark = pytest.mark.requires_box

LABEL = "CONDENSER_LOW_FLOW"


def _seed(thread: str) -> tuple[dict, dict]:
    """A fresh thread id per run, and the reason is the feature under test.

    The checkpoint **persists across test runs** — which is the whole point of this file, and
    which made the first version of it pass once and fail for ever after: the second run found
    the case already root-caused and resumed nothing. A stable id would be testing yesterday's
    checkpoint. The suffix is the cheapest honest fix; the alternative is truncating LangGraph's
    own tables between runs, which would couple these tests to its schema.
    """
    return (
        {
            "seed_key": f"chiller_1|{LABEL}|2026-04-15",
            "fault_label": LABEL,
            "equipment_key": "chiller_1",
            "capability": "technician",
        },
        {"configurable": {"thread_id": f"{thread}-{uuid.uuid4().hex[:12]}"}},
    )


async def test_a_paused_case_survives_a_new_process(request) -> None:
    """The headline. 26 of 43 measured cases stop at the checks and wait for a person —
    sometimes for days. A pause that dies with the process is not a queue."""
    settings = Settings()
    state, config = _seed(f"durable-{request.node.name}")
    checklist = checklist_for(LABEL)

    async with graph_checkpointer(settings) as saver:
        graph = build_case_graph(checklist).compile(checkpointer=saver)
        first = await graph.ainvoke(state, config)
        assert "__interrupt__" in first
        open_items = first["__interrupt__"][0].value["open_items"]

    # Everything above is now out of scope: new saver, new connection, new graph object.
    async with graph_checkpointer(settings) as saver:
        graph = build_case_graph(checklist).compile(checkpointer=saver)

        snapshot = await graph.aget_state(config)
        assert snapshot.next, "the checkpoint must remember there is work left to do"

        answers = {i["id"]: {"kind": "measured", "value": "4.2 bar"} for i in open_items}
        resumed = await graph.ainvoke(Command(resume=answers), config)

    assert resumed["case_state"] == CaseState.ROOT_CAUSED.value
    assert "findings recorded on resume" in resumed["history"]


async def test_the_restart_does_not_lose_the_journey_classification(request) -> None:
    """The classification happens before the pause. If it did not survive, a broken-sensor
    case would come back from the pause looking like an ordinary one — and `F6`'s whole point
    is not dispatching a crew to a healthy machine."""
    settings = Settings()
    state, config = _seed(f"durable-{request.node.name}")
    state["instrument_fault"] = True
    checklist = checklist_for(LABEL)

    async with graph_checkpointer(settings) as saver:
        graph = build_case_graph(checklist).compile(checkpointer=saver)
        await graph.ainvoke(state, config)

    async with graph_checkpointer(settings) as saver:
        graph = build_case_graph(checklist).compile(checkpointer=saver)
        snapshot = await graph.aget_state(config)
        assert snapshot.values["journey"] == "broken_sensor"


async def test_an_unresumed_case_stays_paused_indefinitely(request) -> None:
    """It must not time out into a conclusion. Twenty cases on the reference queue had been
    waiting since April — `RC9` makes that *visible*, and nothing makes it decide."""
    settings = Settings()
    state, config = _seed(f"durable-{request.node.name}")
    checklist = checklist_for(LABEL)

    async with graph_checkpointer(settings) as saver:
        graph = build_case_graph(checklist).compile(checkpointer=saver)
        await graph.ainvoke(state, config)

    for _ in range(3):
        async with graph_checkpointer(settings) as saver:
            graph = build_case_graph(checklist).compile(checkpointer=saver)
            snapshot = await graph.aget_state(config)
            assert snapshot.next == ("collect_findings",)
            assert snapshot.values.get("case_state") != CaseState.ROOT_CAUSED.value
