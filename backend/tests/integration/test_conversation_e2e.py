"""A conversation, not a sequence of questions.

`test_conversation.py` holds `conversation.py` to its contract with the transcript in hand.
This holds the **request** to the claim that matters: that what was said before reaches the
model, in the right place, without becoming a source of readings.

Run against the app rather than the module, because the transcript crosses three boundaries —
the request body, the turn, the prompt — and every defect this product has had in that area
lived in one of the joins rather than in a unit.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents import conversation
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _ask(client: TestClient, question: str, history: list[dict] | None = None):
    """One turn, with whatever conversation preceded it."""
    return client.post(
        "/api/v1/ask",
        json={"question": question, "history": history or []},
    )


def test_a_turn_accepts_a_transcript(client: TestClient) -> None:
    """The field exists on the wire and the request is not rejected for carrying it."""
    response = _ask(
        client,
        "and chiller 2?",
        [{"question": "what happened on chiller 1?", "answer": "Seven fault classes."}],
    )
    assert response.status_code == 200


def test_a_transcript_longer_than_the_bound_is_refused_at_the_boundary(
    client: TestClient,
) -> None:
    """**Bounded on the wire, not trimmed silently.**

    Every token of history is a token not spent on evidence. A request carrying fifty
    exchanges is either a bug or an attempt to crowd the evidence out of the window, and
    quietly keeping the last six would hide both.
    """
    too_many = [{"question": f"q{i}", "answer": f"a{i}"} for i in range(20)]
    response = _ask(client, "why?", too_many)
    assert response.status_code == 422


def test_an_empty_transcript_is_the_ordinary_first_turn(client: TestClient) -> None:
    response = _ask(client, "what equipment do we have?")
    assert response.status_code == 200


def test_the_rendered_block_is_what_reaches_a_prompt() -> None:
    """The join the request depends on, asserted where it is cheap to assert.

    The API converts wire exchanges into `conversation.Exchange`; this is the other end of
    that conversion, so a change to either shape breaks a test rather than a demonstration.
    """
    rendered = conversation.render(
        [
            conversation.Exchange(
                question="what happened on chiller 1?", answer="Seven fault classes."
            ),
            conversation.Exchange(question="and chiller 2?", answer="Four."),
        ]
    )
    assert "They asked: what happened on chiller 1?" in rendered
    assert "You answered: Seven fault classes." in rendered
    assert "and chiller 2?" in rendered
    # Newest last: a model resolves "that one" against what was said most recently.
    assert rendered.index("chiller 1") < rendered.index("and chiller 2")


def test_a_number_typed_into_the_chat_is_never_a_reading() -> None:
    """**The claim the whole fence exists for.**

    A reader can type anything into a chat, including a sentence shaped like a measurement.
    Without the framing beside the transcript, a pasted figure is indistinguishable from one
    the plant recorded — and this product's entire argument is that it never states a figure
    nobody measured.
    """
    rendered = conversation.render(
        [conversation.Exchange(question="the condenser flow is 412 m3/h", answer="Noted.")]
    )
    assert "412" in rendered, "the words are carried, so a follow-up can resolve against them"
    assert "not a source of readings" in rendered
    assert "must come from the result below" in rendered


def test_a_stopped_turn_does_not_enter_the_transcript() -> None:
    """A question with silence after it teaches a model that questions here go unanswered."""
    kept = conversation.recent(
        [
            conversation.Exchange(question="what happened?", answer="Seven classes."),
            conversation.Exchange(question="and the tower?", answer=""),
        ]
    )
    assert len(kept) == 1
    assert kept[0].question == "what happened?"
