"""Smoke — the assembled product over HTTP, because everything else here tests the parts.

**The failure this catches, and nothing else in the suite does.** 393 offline tests pass with
MySQL stopped and the GPU terminated, which is the design; the consequence is that every one
of them exercises a module rather than the thing a person opens. A router mounted at the wrong
prefix, a dependency that raises at startup, a response model that drops a field, a stream
whose frames arrive out of order — none of those is visible from inside a unit test, and all
of them are the whole product being down.

The honesty layer already shipped one reassuring lie that **56 unit tests, a clean typecheck
and a 100% evaluation score all missed, and reading one live report caught**. That is the
argument for this file: some defects are only visible from outside.

**Marked `requires_box`, so a bare `pytest` skips it.** `pytest.ini` makes the offline subset
the default — the honest run is the one nobody has to remember flags for — and these need a
back end running:

    cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
    python -m pytest tests/smoke -m requires_box

**If it is not reachable these skip with the command to start it**, never fail. A red suite
that means *you did not start the server* teaches people to ignore red, and then the run that
means something gets ignored too.

What is asserted is what the numbers in `CONTEXT.md` say the product must show:

| Route | Claim | Source |
|---|---|---|
| `/api/v1/episodes` | 39 episodes over 12 equipment-days | `RC19` — the 3.25x that makes
  correlation a feature rather than tidying |
| `/api/v1/differential` | 5 causes for `HIGH_HEAD_AMBIGUOUS`, outcome `exhausted`, 0 reviewed
  questions | `RC14` and the SME hour: exhausted-not-settled is a finding, and no
  discriminator has been read by a refrigeration engineer |
| `/api/v1/ask` | the frames arrive in contract order | `app/agents/sse_contract.py` — exactly
  one `state`, `done` always last, evidence before prose |
"""
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from app.agents.sse_contract import FRAMES, STREAM_CLOSING_FRAME, TERMINAL_STATE_FRAME
from app.domain.answer import ANSWER_STATES

pytestmark = pytest.mark.requires_box

#: Where the back end runs. `SESSION-HANDOFF.md` §1 fixes the port: 8001 for the API, 3100 for
#: the web surface, because 3000-3003 are occupied on this machine.
BASE_URL = "http://127.0.0.1:8001"

#: How long to wait on a request before treating the box as absent.
#:
#: TBD (Q80). **No document fixes this**, so it is a named constant with the question against
#: it rather than a literal inside a client. The direction of the error is what makes it safe
#: to pick one meanwhile: too short and a warm-up skips a suite that would have passed, too
#: long and a wedged server stalls the run instead of reporting. Both are recoverable; a
#: silent pass is not, and neither outcome can make a failing assertion look like a passing
#: one. The `/ask` stream gets its own budget below because it may reach a model.
REQUEST_TIMEOUT_S = 10.0

#: The stream may cross the network to Ollama and back, which the read routes never do.
STREAM_TIMEOUT_S = 120.0

#: What a skip says. It names the command rather than the fact, because "the back end is not
#: running" tells a reader something they can already see.
NOT_RUNNING = (
    f"no back end answered on {BASE_URL}. These tests read the assembled product over HTTP "
    f"and are skipped rather than failed when it is absent — a red suite meaning 'you did "
    f"not start the server' teaches people to ignore red. Start it with:\n"
    f"    cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
)

#: Measured on `graylinx_synex` after the 2026-08-17 re-clone, and the number `RC19` is built
#: on: 39 episodes against 12 equipment-days is a 3.25x ratio, so one plausible repair could
#: raise several work orders and send several visits to the same machine.
EXPECTED_EPISODES = 39
EXPECTED_EQUIPMENT_DAYS = 12

#: `HIGH_HEAD_AMBIGUOUS` is the authored differential. Five candidate causes, and **not one of
#: its discriminating questions has been read by a refrigeration engineer** — so the outcome
#: is `exhausted` before anybody is asked anything. That is a finding, not an empty screen.
DIFFERENTIAL_LABEL = "HIGH_HEAD_AMBIGUOUS"
EXPECTED_CAUSES = 5
EXPECTED_OUTCOME = "exhausted"
EXPECTED_REVIEWED_QUESTIONS = 0


def _client(timeout: float = REQUEST_TIMEOUT_S) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=timeout)


@pytest.fixture(scope="module")
def live() -> Iterator[httpx.Client]:
    """A client against the running back end, or a skip naming how to start one.

    Module-scoped so the reachability probe runs once. The probe is `/api/v1/health` rather
    than a bare TCP connect: something listening on the port that is not this application
    would otherwise let every test below fail with a confusing 404.
    """
    client = _client()
    try:
        response = client.get("/api/v1/health")
    except httpx.HTTPError as exc:
        client.close()
        pytest.skip(f"{NOT_RUNNING}\n\n(the connection failed with: {exc})")

    if response.status_code != 200:
        body = response.text[:200]
        client.close()
        pytest.skip(
            f"something is listening on {BASE_URL} but it is not this back end — "
            f"/api/v1/health answered {response.status_code}: {body!r}"
        )

    yield client
    client.close()


# ── the read surface ────────────────────────────────────────────────────────────

def test_the_episode_list_holds_the_39_episodes_that_make_correlation_a_feature(
    live: httpx.Client,
) -> None:
    """`RC19` rests on this number. 39 episodes across 12 equipment-days is 3.25 cases per
    machine-day, and on 2026-04-15 chiller 1 carried five labels at once — so one repair could
    raise five work orders and send five visits.

    If this count moves, the correlation feature is arguing about a plant that no longer
    exists, and the demonstration says a number the screen contradicts.
    """
    response = live.get("/api/v1/episodes")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["episode_count"] == EXPECTED_EPISODES, (
        f"the measured window holds {body['episode_count']} episodes, and RC19, the demo "
        f"script and CONTEXT.md all say {EXPECTED_EPISODES}"
    )
    assert body["equipment_days"] == EXPECTED_EQUIPMENT_DAYS
    assert len(body["episodes"]) == EXPECTED_EPISODES, "the count and the list disagree"


def test_the_episode_list_states_that_the_simulated_span_is_excluded(
    live: httpx.Client,
) -> None:
    """`C22` and D-009. The default excludes the simulated span, and the response says so in
    words — a window nobody states is one the reader supplies from their own head, and the
    simulated span invented condenser flow, a signal this plant has never measured."""
    body = live.get("/api/v1/episodes").json()

    assert body["window"]["includes_simulated"] is False
    assert body["window"]["note"].strip(), "the window carries its reason in words"
    assert body["window"]["end"], "an answer over a snapshot always states its boundary"


def test_the_differential_reports_five_causes_and_refuses_to_ask_an_unreviewed_question(
    live: httpx.Client,
) -> None:
    """`RC12`-`RC14`, and the honest state of the content.

    Five candidate causes exist for the ambiguous class, and zero discriminating questions
    have been reviewed — so the differential is `exhausted` before a single question is put to
    anyone. An unreviewed discriminator eliminates irreversibly and nobody re-examines a
    settled question, which is why the refusal to ask is the correct behaviour rather than a
    gap. It must arrive as words on the wire, because an empty candidate list reads as
    *nothing to investigate*.
    """
    response = live.post(
        "/api/v1/differential", json={"fault_label": DIFFERENTIAL_LABEL, "answers": []}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["has_differential"] is True
    assert body["content_available"] is True
    assert len(body["causes"]) == EXPECTED_CAUSES
    assert body["outcome"] == EXPECTED_OUTCOME
    assert body["exhausted_not_settled"] is True
    assert body["settled"] is False, (
        "running out of questions establishes 'we cannot separate these', which is not a "
        "conclusion — reporting it as settled would put a verdict on whichever cause was left"
    )
    assert body["reviewed_questions_available"] == EXPECTED_REVIEWED_QUESTIONS
    assert body["next_question"] is None
    assert body["unreviewed_note"].strip(), (
        "the review backlog must reach the wire in words; an empty question list alone reads "
        "as a class with nothing left to ask"
    )


def test_a_determinate_class_is_refused_a_differential_with_the_reason_attached(
    live: httpx.Client,
) -> None:
    """Constraint 27. Narrowing a class that already names a mechanism invents ambiguity the
    trained model never reported, and the refusal names which classes do qualify — because
    *this class does not get one* is a fact about the model, not a hole in our content."""
    body = live.post(
        "/api/v1/differential", json={"fault_label": "CONDENSER_LOW_FLOW", "answers": []}
    ).json()

    assert body["has_differential"] is False
    assert body["causes"] == []
    assert "already names a mechanism" in body["reason"]


def test_an_unknown_label_is_refused_rather_than_answered_about(live: httpx.Client) -> None:
    """A 404 naming the labels this plant's model actually emits. Answering about a label the
    model never produces would be the most convincing kind of wrong."""
    response = live.post(
        "/api/v1/differential", json={"fault_label": "COMPRESSOR_ON_FIRE", "answers": []}
    )
    assert response.status_code == 404
    assert "is not a label this plant's model emits" in response.json()["detail"]


# ── the stream ──────────────────────────────────────────────────────────────────

def _stream_frames(client: httpx.Client, payload: dict) -> list[tuple[str, dict]]:
    """Every `(event, data)` pair the ask stream emitted, in arrival order.

    Parsed by hand rather than with an SSE library: the thing under test is the byte format
    the web client reads, and a library that tolerated a malformed frame would hide exactly
    the defect this exists to catch.
    """
    frames: list[tuple[str, dict]] = []
    with client.stream("POST", "/api/v1/ask", json=payload) as response:
        assert response.status_code == 200, response.read()[:400]
        assert response.headers["content-type"].startswith("text/event-stream")
        event = ""
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                frames.append((event, json.loads(line[len("data: ") :])))
    return frames


@pytest.fixture(scope="module")
def stream_frames(live: httpx.Client) -> list[tuple[str, dict]]:
    """One real turn over a **real episode**, streamed once.

    The episode is read from `/api/v1/episodes` rather than hard-coded, so this follows the
    same path a person clicking the screen takes and picks up the `figure` and `evidence`
    frames — which is where the ordering rule that matters lives. Hard-coding one would also
    make this file a second place the demonstration's episodes are written down, and
    `CLAUDE.md` §2.8 allows exactly one.

    Asked once and asserted from several angles: the turn may reach a model, and re-asking
    would spend one per assertion.
    """
    episodes = live.get("/api/v1/episodes").json()["episodes"]
    assert episodes, "the measured window holds no episodes, so there is no turn to stream"
    first = episodes[0]

    with _client(STREAM_TIMEOUT_S) as client:
        return _stream_frames(
            client,
            {
                "question": "why was this flagged, and what does the evidence support?",
                "equipment_key": first["equipment_key"],
                "fault_label": first["fault_label"],
                "day": first["day"],
            },
        )


def test_the_ask_stream_emits_only_frames_the_contract_declares(
    stream_frames: list[tuple[str, dict]],
) -> None:
    """`app/agents/sse_contract.py` is the single source of truth for both halves of the
    product. A frame the back end sends and the contract does not name is one the web client
    silently ignores, which renders as a turn missing its evidence rather than as an error."""
    assert stream_frames, "the stream produced no frames at all"
    for name, _ in stream_frames:
        assert name in FRAMES, f"{name!r} is not in the streaming contract"


def test_the_ask_stream_emits_exactly_one_state_and_ends_with_done(
    stream_frames: list[tuple[str, dict]],
) -> None:
    """Two rules that only exist as ordering, so only a live stream can check them.

    *Exactly one* `state` is what stops a turn narrowing from `ANSWERED` to `PARTIAL` halfway
    through and leaving the interface showing whichever arrived last. `done` last is what lets
    a client tell a completed turn from a dropped connection — and those must never look alike,
    because a refusal is not an error.
    """
    names = [name for name, _ in stream_frames]

    assert names.count(TERMINAL_STATE_FRAME) == 1, f"frames were {names}"
    assert names.count(STREAM_CLOSING_FRAME) == 1
    assert names[-1] == STREAM_CLOSING_FRAME, f"the stream ended on {names[-1]!r}"

    state_payload = next(p for n, p in stream_frames if n == TERMINAL_STATE_FRAME)
    assert state_payload["state"] in ANSWER_STATES


def test_the_ask_stream_puts_its_evidence_before_its_prose_and_its_verdict_last(
    stream_frames: list[tuple[str, dict]],
) -> None:
    """The contract order, which is the product's argument in the shape of a stream:
    **route, then evidence, then the answer, then the verdict**.

    A turn that streamed prose before its figures would let a reader form a conclusion and
    then meet the evidence — which is the reassuring-headline failure the honesty layer exists
    to prevent, arriving through presentation rather than through wording.
    """
    names = [name for name, _ in stream_frames]
    # Both ends of each frame kind: a `token` run spans many frames, and "evidence came
    # first" and "the verdict came last" are questions about opposite ends of it.
    first_at = {name: names.index(name) for name in set(names)}
    last_at = {name: len(names) - 1 - names[::-1].index(name) for name in set(names)}

    assert names[0] in {"stage", "state"}, (
        f"a turn opens with progress, or with a refusal's state; this opened with {names[0]!r}"
    )

    answer_frames = [n for n in ("token", "no_diagnosis") if n in first_at]
    assert answer_frames, "the turn produced neither an answer nor a refusal"

    if "route" in first_at:
        for answer in answer_frames:
            assert first_at["route"] < first_at[answer], (
                "the route is decided before anything is said"
            )

    for evidence in ("figure", "evidence"):
        if evidence in first_at:
            for answer in answer_frames:
                assert last_at[evidence] < first_at[answer], (
                    f"{evidence!r} arrived after {answer!r}; the reader met the conclusion "
                    f"before the numbers behind it"
                )

    for answer in answer_frames:
        assert last_at[answer] < first_at[TERMINAL_STATE_FRAME]
    assert first_at[TERMINAL_STATE_FRAME] < first_at[STREAM_CLOSING_FRAME]

    assert not ("token" in first_at and "no_diagnosis" in first_at), (
        "a refusal streamed as tokens as well as its own frame lets an interface render it in "
        "the same typeface as an answer, which softens it by presentation"
    )


def test_a_question_outside_the_plant_is_refused_over_the_wire_without_a_database(
    live: httpx.Client,
) -> None:
    """The refusal path must survive MySQL being stopped — it is the modal outcome, 5,309
    slots against 674 faulted. Asking something the product does not cover names no episode,
    so it must never touch the plant at all."""
    with _client(STREAM_TIMEOUT_S) as client:
        frames = _stream_frames(client, {"question": "what is the capital of France?"})

    names = [name for name, _ in frames]
    assert names.count(TERMINAL_STATE_FRAME) == 1
    assert names[-1] == STREAM_CLOSING_FRAME
    assert "error" not in names, "a refusal is not an error, and must not arrive as one"

    text = " ".join(p.get("text", "") for _, p in frames)
    assert "outside what Synex can answer" in text
