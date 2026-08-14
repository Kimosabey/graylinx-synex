"""The model client — and the wiring between the reasoning policy and the wire.

`tests/unit/test_role_table.py` proves the **policy** decides correctly. Nothing proved the
**client obeys it**, which is a different claim: a correct table read by nobody is a comment.

The failure this guards is specific and was expensive once. With thinking on and a tight
budget, the model spends the whole allowance in the think channel and returns **empty
content** — not a worse answer, no answer. An empty completion is indistinguishable from a
model that had nothing to say, so the client raises rather than returning it.

None of this needs the box: the payload is asserted at the boundary with a stubbed
transport, and stub mode is exercised against real transcript files in a temporary
directory.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.llm.client import (
    Completion,
    ModelClient,
    ModelUnavailable,
    transcript_key,
)

MESSAGES = [{"role": "user", "content": "why was chiller 1 flagged?"}]


def _client(tmp_path: Path, mode: str = "stub") -> ModelClient:
    return ModelClient(mode=mode, transcript_dir=tmp_path)


def _write_transcript(tmp_path: Path, role: str, task: str, text: str) -> str:
    key = transcript_key(role, task, MESSAGES)
    (tmp_path / f"{key}.json").write_text(
        json.dumps({"key": key, "role": role, "task": task, "text": text}),
        encoding="utf-8",
    )
    return key


# ── the wiring: does the client obey the policy? ───────────────────────────────

@pytest.mark.parametrize(
    "role,task,expect_think",
    [
        ("brain", "diagnose", True),
        ("brain", "root_cause", True),
        ("brain", "investigate", True),
        ("brain", "composer", False),
        ("brain", "narrate", False),
        ("brain", "planner", False),
        ("brain", "a_task_nobody_registered", False),
        ("text", "diagnose", False),
        ("tool", "diagnose", False),
        ("auditor", "audit", False),
    ],
)
async def test_the_think_flag_on_the_wire_matches_the_policy(
    tmp_path: Path, role: str, task: str, expect_think: bool
) -> None:
    """The payload is what actually reaches Ollama. This asserts it, not the table.

    `think` is **absent** rather than `false` when off — the other two models reject the
    key, and sending it anyway makes a 400 from the wrong model look like a network fault.
    """
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "an answer."}})

    transport = httpx.MockTransport(handler)
    client = _client(tmp_path, mode="live")

    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    httpx.AsyncClient = Patched  # type: ignore[misc]
    try:
        await client.complete(role=role, task=task, messages=MESSAGES)
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert seen.get("think", False) is expect_think, (
        f"role={role} task={task}: payload {'has' if 'think' in seen else 'lacks'} think"
    )
    if not expect_think:
        assert "think" not in seen, "the flag must be absent, not false"


async def test_the_completion_reports_whether_it_reasoned(tmp_path: Path) -> None:
    """Carried on the result so a trace can show it, rather than being inferred later."""
    _write_transcript(tmp_path, "brain", "diagnose", "an answer.")
    result = await _client(tmp_path).complete(role="brain", task="diagnose", messages=MESSAGES)
    assert isinstance(result, Completion)
    assert result.thinking_enabled is True

    _write_transcript(tmp_path, "text", "narrate", "an answer.")
    other = await _client(tmp_path).complete(role="text", task="narrate", messages=MESSAGES)
    assert other.thinking_enabled is False


# ── the failure the policy exists to prevent ───────────────────────────────────

async def test_empty_content_raises_rather_than_returning_nothing(tmp_path: Path) -> None:
    """The exact failure: with thinking on and a tight budget the model spends the whole
    allowance reasoning and returns nothing.

    An empty completion is indistinguishable from a model that had nothing to say, so it
    must be loud. The message names thinking when thinking was on, because that is the
    first thing to check.
    """
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "   "}})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    httpx.AsyncClient = Patched  # type: ignore[misc]
    try:
        with pytest.raises(ModelUnavailable, match="empty content"):
            await _client(tmp_path, mode="live").complete(
                role="brain", task="diagnose", messages=MESSAGES
            )
        with pytest.raises(ModelUnavailable, match="reasoning policy"):
            await _client(tmp_path, mode="live").complete(
                role="brain", task="diagnose", messages=MESSAGES
            )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]


# ── stub mode: the gate must never need a GPU ──────────────────────────────────

async def test_stub_replays_a_committed_transcript(tmp_path: Path) -> None:
    _write_transcript(tmp_path, "brain", "diagnose", "the recorded answer.")
    result = await _client(tmp_path).complete(role="brain", task="diagnose", messages=MESSAGES)
    assert result.text == "the recorded answer."
    assert result.from_transcript


async def test_a_missing_transcript_raises_rather_than_reaching_the_box(
    tmp_path: Path,
) -> None:
    """A silent fallback would mean CI quietly needing a GPU — the one thing the whole mode
    split exists to prevent."""
    with pytest.raises(ModelUnavailable, match="no transcript"):
        await _client(tmp_path).complete(role="brain", task="diagnose", messages=MESSAGES)


def test_stub_mode_reaches_nothing(tmp_path: Path) -> None:
    assert not _client(tmp_path, "stub").reaches_the_box
    assert _client(tmp_path, "record").reaches_the_box
    assert _client(tmp_path, "live").reaches_the_box


# ── the transcript key ─────────────────────────────────────────────────────────

def test_the_key_changes_when_the_prompt_changes() -> None:
    """The prompt is *in* the key on purpose.

    Keying by role and task alone would let an edited prompt keep replaying the old
    recording, and every evaluation after that edit would measure a question nobody was
    asking any more — invisibly.
    """
    a = transcript_key("brain", "diagnose", MESSAGES)
    b = transcript_key("brain", "diagnose", [{"role": "user", "content": "a different ask"}])
    assert a != b


def test_the_key_is_stable_for_the_same_input() -> None:
    assert transcript_key("brain", "diagnose", MESSAGES) == transcript_key(
        "brain", "diagnose", MESSAGES
    )


def test_role_and_task_both_change_the_key() -> None:
    base = transcript_key("brain", "diagnose", MESSAGES)
    assert transcript_key("text", "diagnose", MESSAGES) != base
    assert transcript_key("brain", "narrate", MESSAGES) != base


# ── record mode writes what it replayed ────────────────────────────────────────

async def test_record_mode_writes_a_transcript_stub_can_replay(tmp_path: Path) -> None:
    """The round trip that makes a box burst worth doing: record once, replay for ever."""
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "captured on the box."}})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    httpx.AsyncClient = Patched  # type: ignore[misc]
    try:
        recorded = await _client(tmp_path, "record").complete(
            role="brain", task="diagnose", messages=MESSAGES
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert not recorded.from_transcript
    replayed = await _client(tmp_path, "stub").complete(
        role="brain", task="diagnose", messages=MESSAGES
    )
    assert replayed.text == "captured on the box."
    assert replayed.from_transcript


async def test_a_transcript_records_whether_thinking_was_on(tmp_path: Path) -> None:
    """So a recording made with thinking on is not silently replayed as if it were off."""
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "captured."}})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    httpx.AsyncClient = Patched  # type: ignore[misc]
    try:
        await _client(tmp_path, "record").complete(
            role="brain", task="diagnose", messages=MESSAGES
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    written = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert written["thinking_enabled"] is True
    assert written["role"] == "brain"


# ── the box being down is a stated failure, not a silent one ───────────────────

async def test_an_unreachable_box_raises_with_the_host_named(tmp_path: Path) -> None:
    """`answer_turn` catches this and degrades to the deterministic answer — but it must
    know *why*, so the interface can say it rather than quietly producing less."""
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    httpx.AsyncClient = Patched  # type: ignore[misc]
    try:
        with pytest.raises(ModelUnavailable, match="did not answer"):
            await _client(tmp_path, "live").complete(
                role="brain", task="diagnose", messages=MESSAGES
            )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]
