"""`U6`, `U7`, `U8` and `A1` on the wire.

**The gap these close.** `CONTEXT.md` §10d names eight surfaces and the product had routes for
two. All four services below were built with tests today and **none was reachable over HTTP** —
the same "machinery with no consumer" shape as a tool registry nothing calls, one layer up.

These tests run with Postgres possibly absent, deliberately: a surface that only works when
every store is up is a surface that goes blank in exactly the situation somebody needs it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── every surface answers, scoped ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "path", ["/api/v1/workspace", "/api/v1/supervisor", "/api/v1/administrator"]
)
def test_each_role_surface_answers(client: TestClient, path: str) -> None:
    """A route that 500s when a store is down is a surface nobody can rely on."""
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()


@pytest.mark.parametrize("path", ["/api/v1/workspace", "/api/v1/supervisor"])
def test_a_queue_says_who_is_looking(client: TestClient, path: str) -> None:
    """`G1`: scope is recomputed every turn and never inherited, so what a surface shows
    depends on who asked. A queue that did not say would be unauditable."""
    assert client.get(path).json()["viewing_as"]


def test_an_empty_queue_says_whether_it_was_read(client: TestClient) -> None:
    """**Empty and unread are different facts.** A workspace showing zero cases because the
    store is unreachable looks exactly like a plant with nothing wrong — inherited constraint
    7 arriving through a different door."""
    body = client.get("/api/v1/workspace").json()
    assert "store_note" in body
    if body["store_note"]:
        assert "not because nothing is open" in body["store_note"]


# ── constraint 25: the supervisor queue is not the workspace with more rows ───

def test_the_two_queues_are_different_shapes(client: TestClient) -> None:
    """A supervisor is not a more capable technician. Ranking by seniority once sent a
    filter-drier restriction to a supervisor because one incidental records question
    outranked three refrigeration measurements."""
    workspace = set(client.get("/api/v1/workspace").json())
    supervisor = set(client.get("/api/v1/supervisor").json())

    assert "faults" in workspace
    assert "approvals" in supervisor
    assert workspace != supervisor, "one queue is not a superset of the other"


def test_the_supervisor_queue_separates_the_two_kinds_of_stale(client: TestClient) -> None:
    """`RC9`. A condition that cleared is evidence about the plant; a case nobody has touched
    is evidence about the queue. One flag would let a fixed machine and a forgotten one look
    identical, and only the second needs a person."""
    body = client.get("/api/v1/supervisor").json()
    assert "condition_cleared" in body
    assert "untouched" in body
    assert "ageing" in body


# ── U8: the most misleading screen in the product, if it stayed silent ────────

def test_the_administrator_says_the_identity_is_not_production(client: TestClient) -> None:
    """`Q41`: `is_production_identity` is hard-wired `False`, so every decision recorded is
    attributable to a demonstration persona. An administrator screen that did not say so
    would be the most misleading screen here."""
    body = client.get("/api/v1/administrator").json()
    blob = str(body).lower()
    assert "identity_kind" in body
    assert "production" in blob


def test_the_policy_version_says_it_has_no_scheme(client: TestClient) -> None:
    """`Q74`: neither the format nor what advances it is defined. A version that looked real
    would be worse than one that says it is provisional — an audit row read years later
    cannot tell a placeholder from a release."""
    assert "Q74" in str(client.get("/api/v1/administrator").json())


def test_the_approval_matrix_maps_risk_to_a_capability(client: TestClient) -> None:
    """Constraints 13 and 25: capabilities, never an ordering of personas."""
    body = client.get("/api/v1/administrator").json()
    # `as_dict()` publishes it as `approval_matrix` rather than the field name `matrix` —
    # the wire name is the clearer one, and the route serialises through the service rather
    # than reaching into the dataclass.
    assert body["approval_matrix"], "the matrix must be readable data, not prose"
    assert body["is_production_identity"] is False


# ── A1: what cannot be said is the feature ────────────────────────────────────

def test_the_asset_story_carries_what_cannot_be_said(client: TestClient) -> None:
    """On this plant condenser flow was never measured and feeds four of six models, `dpt` is
    constant so approach cannot be computed at all, and one model runs at nRMSE 48.03 against
    the other's 2.65. A story listing capabilities without listing those is the reassuring
    lie."""
    body = client.get("/api/v1/asset/chiller_1").json()
    assert body["cannot_say"], "the last section is the point of the page"
    assert body["rendered"].strip()


def test_an_unknown_asset_is_refused_by_name(client: TestClient) -> None:
    """A 404 that names the real assets is actionable; a bare 404 is a dead end."""
    response = client.get("/api/v1/asset/turbine_9")
    assert response.status_code == 404
    assert "chiller_1" in response.json()["detail"]


def test_an_unread_history_is_not_reported_as_a_clean_asset(client: TestClient) -> None:
    """`episodes=None` and `episodes=()` mean different things — *nobody read the history*
    against *the history was read and held nothing*. Collapsing them would tell a reader an
    asset was clean when it was never checked."""
    body = client.get("/api/v1/asset/chiller_1").json()
    rendered = body["rendered"].lower()
    assert "nothing was read" in rendered or "diagnos" in rendered


def test_every_absence_on_the_page_is_words(client: TestClient) -> None:
    """An absence is not a zero and not a dash."""
    for entry in client.get("/api/v1/asset/chiller_1").json()["cannot_say"]:
        assert str(entry).strip() not in {"", "-", "—", "0", "None"}
