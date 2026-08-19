"""The pass that reads the evidence before the answer is written."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.agents import analyst


@dataclass
class _Reply:
    text: str


class _Box:
    def __init__(self, text: str = "", *, raises: Exception | None = None, hangs: bool = False):
        self._text = text
        self._raises = raises
        self._hangs = hangs
        self.asked_role: str | None = None
        self.asked_task: str | None = None
        self.prompt: str = ""

    async def complete(self, *, role, task, messages, json_only=False):
        self.asked_role = role
        self.asked_task = task
        self.prompt = "\n".join(m["content"] for m in messages)
        if self._raises is not None:
            raise self._raises
        if self._hangs:
            await asyncio.sleep(3600)
        return _Reply(self._text)


NOTE = (
    "The discharge-pressure residual is furthest outside its band, and its model fits well "
    "enough to lean on. The delta-T residual sits inside its band but its model has a high "
    "nRMSE, so it carries little either way."
)


async def test_a_usable_note_comes_back() -> None:
    got = await analyst.assess(evidence="some evidence", question="what is wrong?", client=_Box(NOTE))
    assert got == NOTE


async def test_it_runs_on_the_brain_with_thinking_on() -> None:
    """**`domain_analyst` is what turns the thinking channel on.**

    `reasoning_policy` has listed it since it was written and nothing called it. The task name
    is load-bearing rather than descriptive: rename it and the pass silently stops thinking.
    """
    box = _Box(NOTE)
    await analyst.assess(evidence="e", question="q", client=box)
    assert box.asked_role == "brain"
    assert box.asked_task == "domain_analyst"

    from app.llm.reasoning_policy import should_think

    assert should_think(box.asked_task, role=box.asked_role) is True


async def test_the_prompt_forbids_naming_a_cause() -> None:
    """**The boundary that makes this safe to add.**

    This is the one pass whose output reads most like a diagnosis, so the prohibition is
    explicit rather than implied.
    """
    box = _Box(NOTE)
    await analyst.assess(evidence="e", question="q", client=box)
    lowered = box.prompt.lower()
    assert "do not name a cause or a fault" in lowered
    assert "do not recommend an action" in lowered
    assert "do not rank by seriousness" in lowered


async def test_an_empty_or_tiny_reply_is_no_note() -> None:
    """A one-word note is a note that lost its content, and the composer is better without it."""
    for reply in ("", "   ", "Nothing.", "ok"):
        assert await analyst.assess(evidence="e", question="q", client=_Box(reply)) == ""


async def test_no_evidence_means_no_pass() -> None:
    """There is nothing to assess, and the call would cost a round trip to say so."""
    assert await analyst.assess(evidence="", question="q", client=_Box(NOTE)) == ""
    assert await analyst.assess(evidence="   ", question="q", client=_Box(NOTE)) == ""


async def test_every_failure_yields_no_note_rather_than_raising() -> None:
    """**The pass can make an answer better informed; it cannot make the turn fail.**"""
    assert await analyst.assess(evidence="e", question="q", client=None) == ""
    assert await analyst.assess(evidence="e", question="q", client=_Box(raises=OSError())) == ""


async def test_a_hanging_analyst_gives_up(monkeypatch) -> None:
    """It sits in front of the answer — a reader is already waiting when it runs."""
    monkeypatch.setattr(analyst, "TIMEOUT_S", 0.05)
    assert await analyst.assess(evidence="e", question="q", client=_Box(hangs=True)) == ""


async def test_a_long_note_is_cut() -> None:
    """Longer than a paragraph and it competes with the answer for the composer's attention."""
    got = await analyst.assess(evidence="e", question="q", client=_Box("word " * 5000))
    assert len(got) <= analyst.MAX_CHARS


def test_the_block_frames_the_note_as_an_opinion_not_a_source() -> None:
    """**An unlabelled paragraph in a prompt reads as more evidence.**

    This is one model's reading *of* evidence, which is a different thing — so the frame says
    that the evidence wins if the two disagree.
    """
    block = analyst.as_prompt_block(NOTE)
    assert NOTE in block
    assert "not a source" in block
    assert "the evidence is right" in block


def test_no_note_produces_no_block() -> None:
    """A heading with nothing under it tells the composer it failed to read something."""
    assert analyst.as_prompt_block("") == ""
