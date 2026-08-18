"""Layer 4, and every way it is allowed to fail.

The arbiter is the layer that stops the Copilot being a menu — but it is a model, and a model
in a routing path is only safe if every failure it can have degrades to the deterministic
default. These tests are that argument, made with the box off.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.agents import arbiter


@dataclass
class _Reply:
    text: str


class _Box:
    """A model that says whatever the test needs, or misbehaves on request."""

    def __init__(self, text: str = "", *, raises: Exception | None = None, hangs: bool = False):
        self._text = text
        self._raises = raises
        self._hangs = hangs
        self.asked_role: str | None = None
        self.prompt: str = ""

    async def complete(self, *, role, task, messages):  # noqa: ARG002
        self.asked_role = role
        self.prompt = "\n".join(m["content"] for m in messages)
        if self._raises is not None:
            raise self._raises
        if self._hangs:
            await asyncio.sleep(3600)
        return _Reply(self._text)


async def test_a_clean_choice_is_taken() -> None:
    box = _Box('{"skill": "investigate", "why": "it spans several days"}')
    got = await arbiter.arbitrate("has it been getting worse?", client=box)
    assert got.skill == "investigate"
    assert got.decided is True
    assert "several days" in got.why


async def test_the_small_model_does_the_routing() -> None:
    """`planner`'s lesson, applied.

    The 26B brain was recorded degenerating into a repetition loop on exactly this job — a
    short strict schema — and every plan silently became empty. Routing takes the `text` role.
    """
    box = _Box('{"skill": "look_up", "why": "a recorded fact"}')
    await arbiter.arbitrate("how many chillers?", client=box)
    assert box.asked_role == "text"


async def test_json_wrapped_in_prose_is_still_read() -> None:
    """Models fence and preamble however they feel; the first object is taken."""
    box = _Box('Sure! Here you go:\n```json\n{"skill": "verify", "why": "after a repair"}\n```')
    assert (await arbiter.arbitrate("did it hold?", client=box)).skill == "verify"


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "I think this is an investigate question.",
        "{}",
        '{"skill": null}',
        '{"skill": "refuse", "why": "out of scope"}',
        '{"skill": "delete_everything"}',
        "[1, 2, 3]",
        '{"skill": 7}',
    ],
)
async def test_anything_unusable_leaves_the_route_undecided(reply: str) -> None:
    """**Undecided is not a refusal.** The caller falls through to its default and answers."""
    got = await arbiter.arbitrate("something", client=_Box(reply))
    assert got.skill is None
    assert got.decided is False


async def test_refuse_is_not_on_the_menu() -> None:
    """The layers that refuse have already run, and their decisions are not reconsidered.

    If a model could route an out-of-scope question back into an answering skill, the scope
    gate would be advisory — and this product has already shipped one leak of that exact shape.
    """
    assert "refuse" not in {name for name, _ in arbiter.CHOICES}


async def test_an_unreachable_box_does_not_fail_the_turn() -> None:
    got = await arbiter.arbitrate("something", client=_Box(raises=OSError("no route to host")))
    assert got.skill is None
    assert "could not be reached" in got.why


async def test_a_hanging_box_gives_up_rather_than_hanging_the_turn(monkeypatch) -> None:
    """A router that can hang is a product that appears to hang."""
    monkeypatch.setattr(arbiter, "TIMEOUT_S", 0.05)
    got = await arbiter.arbitrate("something", client=_Box(hangs=True))
    assert got.skill is None
    assert "in time" in got.why


async def test_no_client_is_undecided_rather_than_an_error() -> None:
    got = await arbiter.arbitrate("something", client=None)
    assert got.skill is None


async def test_the_previous_machine_reaches_the_prompt() -> None:
    """A follow-up naming no machine is the case this exists for."""
    box = _Box('{"skill": "explain", "why": "about the last one"}')
    await arbiter.arbitrate("why is that?", client=box, last_equipment="chiller_1")
    assert "chiller_1" in box.prompt


async def test_the_prompt_forbids_the_things_the_separation_reserves() -> None:
    """Choosing who answers is not answering, and the prompt has to say so.

    `CONTEXT.md` §5: the model never names a fault, grants a permission or sets a priority. A
    router prompt that did not say this invites the model to explain its choice by diagnosing.
    """
    box = _Box('{"skill": "look_up"}')
    await arbiter.arbitrate("anything", client=box)
    lowered = box.prompt.lower()
    assert "never decide what is wrong" in lowered
    assert "how urgent" in lowered
