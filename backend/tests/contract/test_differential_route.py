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

def test_an_authored_class_exposes_its_candidates(client: TestClient) -> None:
    """The candidate set was transcribed from the curated library on 2026-08-17. Before that
    this route reported *missing content* — a state deliberately kept distinct from *no
    ambiguity*, because one of them is an instruction to stop looking."""
    body = _post(client, "HIGH_HEAD_AMBIGUOUS").json()

    assert body["has_differential"] is True
    assert body["content_available"] is True
    assert body["causes"], "an authored differential must expose its candidates"
    assert all(c["live"] for c in body["causes"]), "nothing is eliminated before a question"


def test_nothing_is_askable_because_nothing_has_been_reviewed(client: TestClient) -> None:
    """**The content arrived; the review did not.** `Differential.askable` returns only
    SME-reviewed questions, so every differential reports EXHAUSTED before a single question
    is put to anyone. Thirty-one causes were eliminated on the reference queue by
    discriminators nobody had read, and elimination is irreversible."""
    body = _post(client, "HIGH_HEAD_AMBIGUOUS").json()

    assert body["reviewed_questions_available"] == 0
    assert body["next_question"] is None
    assert body["exhausted_not_settled"] is True
    assert "no discriminator" in body["unreviewed_note"].lower()


def test_the_registry_matches_the_documented_scale() -> None:
    """`CONTEXT.md` §10b: 4 differentials, 19 candidate causes, 19 discriminating questions.
    Asserted against the transcription so a paraphrase that dropped or invented one shows up
    as a count rather than as prose nobody re-reads."""
    assert len(diff.DIFFERENTIALS) == 4
    assert sum(len(d.causes) for d in diff.DIFFERENTIALS.values()) == 19
    assert sum(len(d.questions) for d in diff.DIFFERENTIALS.values()) == 19


def test_only_undecidable_classes_are_authored() -> None:
    """Constraint 27. A determinate class with a differential would be inventing ambiguity
    the trained model never reported."""
    for label in diff.DIFFERENTIALS:
        assert diff.has_differential(label), f"{label} is authored but does not qualify"


def test_qualifying_and_being_authored_stay_separate_questions() -> None:
    """`has_differential` answers *does this class have ambiguity*; `differential_for` answers
    *have we written the candidate set*. Collapsing them would report a content gap as a
    property of the plant — and `REFRIGERANT_SIDE_HIGH_HEAD` is the live case: it names a
    region, probes five mechanisms, and deliberately has no differential (`Q37`)."""
    assert diff.has_differential("HIGH_HEAD_AMBIGUOUS") is True
    assert diff.differential_for("HIGH_HEAD_AMBIGUOUS") is not None

    assert diff.has_differential("REFRIGERANT_SIDE_HIGH_HEAD") is False
    assert diff.differential_for("REFRIGERANT_SIDE_HIGH_HEAD") is None


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
