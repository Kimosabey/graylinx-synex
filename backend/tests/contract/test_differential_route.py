"""`RC12`–`RC14` on the wire.

The differential is the most dangerous content in the programme: thirty-one causes have
already been eliminated on the reference queue, every one by a discriminator no refrigeration
engineer has reviewed. Elimination is irreversible and nobody re-examines a settled question,
so a wrong discriminator produces a **confident wrong answer that is never revisited**.

These tests are about what the wire refuses to say, more than what it says.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain import differential as diff
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _post(client: TestClient, label: str, answers: list[dict] | None = None):
    return client.post(
        "/api/v1/differential", json={"fault_label": label, "answers": answers or []}
    )


# ── constraint 27: only an undecidable class gets one ──────────────────────────

def test_a_determinate_class_is_refused_a_differential(client: TestClient) -> None:
    """Narrowing a class that already names a mechanism would invent ambiguity the trained
    model never reported."""
    body = _post(client, "CONDENSER_LOW_FLOW").json()

    assert body["has_differential"] is False
    assert body["causes"] == []
    assert "already names a mechanism" in body["reason"]
    assert "HIGH_HEAD_AMBIGUOUS" in body["reason"], "the refusal names which classes do"


@pytest.mark.parametrize(
    "label",
    [
        "HIGH_HEAD_AMBIGUOUS",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        "CONDENSER_WATER_SIDE_UNSPECIFIED",
        "POWER_HIGH_UNEXPLAINED",
    ],
)
def test_every_undecidable_class_qualifies(client: TestClient, label: str) -> None:
    """Four of seven declare themselves undecidable in their own names — *ambiguous*,
    *unspecified*, *unexplained*, and *undercharge **or** restriction*."""
    assert _post(client, label).json()["has_differential"] is True


def test_an_unknown_label_is_refused_rather_than_guessed(client: TestClient) -> None:
    response = _post(client, "TOTALLY_MADE_UP")
    assert response.status_code == 404
    assert "is not a label this plant's model emits" in response.json()["detail"]


# ── missing content is not the same as no ambiguity ───────────────────────────

def test_missing_content_is_reported_as_missing_not_as_settled(client: TestClient) -> None:
    """**The distinction this route exists to protect.** A class that qualifies but has no
    authored candidate set must not look like a class with nothing to investigate — those
    are opposite statements, and one of them is an instruction to stop looking."""
    body = _post(client, "HIGH_HEAD_AMBIGUOUS").json()

    assert body["has_differential"] is True
    assert body["content_available"] is False
    assert "missing content, not a class without ambiguity" in body["reason"]
    assert body["next_question"] is None


def test_the_registry_is_empty_and_that_is_deliberate() -> None:
    """A sample *discriminator* is not the same kind of object as a sample *checklist item*.
    An illustrative instruction wastes a walk to the machine; an illustrative discriminator
    rules a real cause out for ever."""
    assert diff.DIFFERENTIALS == {}
    assert diff.differential_for("HIGH_HEAD_AMBIGUOUS") is None


def test_qualifying_and_being_authored_are_separate_questions() -> None:
    """`has_differential` answers *does this class have ambiguity*; `differential_for` answers
    *have we written the candidate set*. Collapsing them would report our content gap as a
    property of the plant."""
    assert diff.has_differential("HIGH_HEAD_AMBIGUOUS") is True
    assert diff.differential_for("HIGH_HEAD_AMBIGUOUS") is None


# ── the shape the screen depends on ───────────────────────────────────────────

def test_the_payload_carries_both_terminal_states_separately(client: TestClient) -> None:
    """Constraint 32. `settled` and `exhausted_not_settled` are different fields, never one
    `done` flag — running out of questions establishes *"we cannot separate these with the
    checks we have"*, which is not a conclusion about whichever cause is left."""
    body = _post(client, "HIGH_HEAD_AMBIGUOUS").json()
    assert "settled" not in body or body.get("settled") is not True

    # And on a class that reaches the state machine, both keys exist independently.
    diff.DIFFERENTIALS["__probe__"] = diff.Differential(
        fault_label="__probe__",
        causes=(diff.Cause("a", "cause a"), diff.Cause("b", "cause b")),
        questions=(),
    )
    try:
        state = diff.start(diff.DIFFERENTIALS["__probe__"])
        assert state.outcome is diff.Outcome.EXHAUSTED
        assert state.outcome is not diff.Outcome.SETTLED
        # Two causes stand and neither has been ruled out. Reporting this as settled would
        # put a conclusion on whichever one happened to be listed first.
        assert len(state.live) == 2
        assert state.eliminations == ()
    finally:
        del diff.DIFFERENTIALS["__probe__"]


def test_an_exhausted_differential_says_no_discriminator_was_reviewed() -> None:
    """The honest reason. It is not that the checks ran out — it is that none may be asked."""
    probe = diff.Differential(
        fault_label="__probe__",
        causes=(diff.Cause("a", "cause a"), diff.Cause("b", "cause b")),
        questions=(),
    )
    assert "no reviewed question" in diff.start(probe).render_outcome()
