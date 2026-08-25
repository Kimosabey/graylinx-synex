"""`/api/v1/degraded` — `CONTEXT.md` §13 reachable with curl.

**Why an endpoint and not a log line.** *"The platform must state when it is in degraded mode"*
is a claim about what a **surface** can find out. Before this, a surface could ask one question
— is the plant connected — and got one word back. MySQL down, the roster replayed, PostgreSQL
unprobed and the audit sink not durable are four different situations, and a screen that cannot
tell them apart cannot say anything true about the fourth.

Deliberately **not** marked `requires_box`: the endpoint's whole point is to work when its
dependencies do not, so a test that needed them would be testing the opposite property.
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.domain.degradation import PROFILES
from app.main import app


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c


async def test_every_capability_is_reported_with_its_reason(client: httpx.AsyncClient) -> None:
    """The report's length must not depend on how much the caller checked. A list that shrinks
    to what was easy to probe is the reconciliation failure `R10` exists for."""
    body = (await client.get("/api/v1/degraded")).json()

    assert body["capabilities_reported"] == len(PROFILES)
    assert len(body["states"]) == len(PROFILES)
    for state in body["states"]:
        assert state["reason"].strip(), f"{state['capability']} has no reason"
        assert state["availability"] in {"available", "substituted", "unavailable", "unknown"}
        if state["availability"] == "substituted":
            assert state["substitution"].strip(), (
                f"{state['capability']} is substituted and does not say by what — which is "
                f"exactly what §13 forbids"
            )


async def test_health_carries_the_aggregate_and_points_at_the_detail(
    client: httpx.AsyncClient,
) -> None:
    """`status` still answers the plant question it always answered. `degraded_mode` answers the
    one nobody could ask: *which capabilities am I running without.*"""
    body = (await client.get("/api/v1/health")).json()

    summary = body["degraded_mode"]
    assert f"of {len(PROFILES)}" in summary["headline"]
    assert summary["detail_at"] == "/api/v1/degraded"
    assert isinstance(summary["degraded"], list)
    assert isinstance(summary["unknown"], list)


async def test_the_summary_and_the_detail_cannot_disagree(client: httpx.AsyncClient) -> None:
    """Both are computed by one call in one place. A summary derived separately from the detail
    it summarises is the defect this aggregate exists to remove."""
    health = (await client.get("/api/v1/health")).json()["degraded_mode"]
    detail = (await client.get("/api/v1/degraded")).json()

    assert health["degraded"] == detail["degraded"]
    assert health["unknown"] == detail["unknown"]
    assert health["headline"] == detail["headline"]


async def test_an_unreachable_plant_is_reported_as_unavailable_not_substituted(
    monkeypatch,
) -> None:
    """There is no second copy of what the instruments read. Reporting the plant as
    *substituted* would imply something is standing in for a reading — which is precisely what
    the fabricated `cond_flow` window looked like before the re-clone removed it."""
    from app import main

    monkeypatch.setattr(main, "get_settings", lambda: Settings(mysql_port=1))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            body = (await c.get("/api/v1/degraded")).json()

    plant = next(s for s in body["states"] if s["capability"] == "plant_telemetry")
    assert plant["availability"] == "unavailable"
    assert plant["substitution"] == ""
    assert "Nothing stands in for it" in plant["reason"]
    assert body["fully_available"] is False
