"""The plan over several reads, and the ways a broad answer can quietly narrow."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.agents import orchestrate


@dataclass
class _Reply:
    text: str


@dataclass
class _Spec:
    name: str
    description: str = "does a thing"


class _Box:
    def __init__(self, text: str = "", *, raises: Exception | None = None, hangs: bool = False):
        self._text = text
        self._raises = raises
        self._hangs = hangs
        self.asked_role: str | None = None
        self.json_only: bool = False

    async def complete(self, *, role, task, messages, json_only=False):
        self.asked_role = role
        self.json_only = json_only
        if self._raises is not None:
            raise self._raises
        if self._hangs:
            await asyncio.sleep(3600)
        return _Reply(self._text)


SPECS = [_Spec("plant_overview"), _Spec("reconciliation_report"), _Spec("signal_standing")]


async def test_a_clean_plan_is_taken_in_order() -> None:
    box = _Box('{"steps": [{"tool": "plant_overview"}, {"tool": "signal_standing"}]}')
    assert await orchestrate.plan("review the plant", specs=SPECS, client=box) == (
        "plant_overview",
        "signal_standing",
    )


async def test_the_plan_is_the_brains_job_in_json_mode() -> None:
    """Planning is reasoning about what to do next, and the roster puts that on the brain.

    `json_only` is asserted beside the role because it is what makes it safe: the recorded
    failure is a thinking model asked for JSON in free text, not a thinking model planning.
    """
    box = _Box('{"steps": [{"tool": "plant_overview"}]}')
    await orchestrate.plan("anything", specs=SPECS, client=box)
    assert box.asked_role == "planner"
    assert box.json_only is True


async def test_a_tool_that_does_not_exist_is_dropped() -> None:
    """The planner names capabilities; it does not get to invent one."""
    box = _Box('{"steps": [{"tool": "plant_overview"}, {"tool": "delete_everything"}]}')
    assert await orchestrate.plan("anything", specs=SPECS, client=box) == ("plant_overview",)


async def test_a_repeated_tool_is_read_once() -> None:
    """A plan naming the same lookup twice reads it twice and says the same thing twice."""
    box = _Box('{"steps": [{"tool": "plant_overview"}, {"tool": "plant_overview"}]}')
    assert await orchestrate.plan("anything", specs=SPECS, client=box) == ("plant_overview",)


async def test_the_plan_is_bounded() -> None:
    """Past the ceiling the results crowd the evidence out of the composer's window."""
    many = [_Spec(f"tool_{i}") for i in range(10)]
    steps = ", ".join(f'{{"tool": "tool_{i}"}}' for i in range(10))
    box = _Box(f'{{"steps": [{steps}]}}')
    planned = await orchestrate.plan("anything", specs=many, client=box)
    assert len(planned) == orchestrate.MAX_STEPS


async def test_an_unusable_reply_plans_nothing() -> None:
    """Empty rather than a default plan.

    A planner that fell back to reading everything would turn one model failure into four
    unnecessary round trips, and the caller has a single-tool path that is better than a
    guessed multi-tool one.
    """
    for reply in ("", "I would read the plant overview", "{}", '{"steps": "everything"}'):
        assert await orchestrate.plan("anything", specs=SPECS, client=_Box(reply)) == ()


async def test_an_unreachable_planner_plans_nothing() -> None:
    box = _Box(raises=OSError("no route"))
    assert await orchestrate.plan("anything", specs=SPECS, client=box) == ()


async def test_a_hanging_planner_gives_up(monkeypatch) -> None:
    monkeypatch.setattr(orchestrate, "TIMEOUT_S", 0.05)
    assert await orchestrate.plan("anything", specs=SPECS, client=_Box(hangs=True)) == ()


async def test_the_reads_run_at_once_rather_than_in_turn() -> None:
    """**Sequence is four round trips for one answer.**

    Asserted by timing rather than by inspection: a sequential implementation would take four
    times the per-read delay, and this must not.
    """
    async def slow(name: str) -> dict:
        await asyncio.sleep(0.05)
        return {"read": name}

    loop = asyncio.get_running_loop()
    started = loop.time()
    got = await orchestrate.gather(("a", "b", "c", "d"), run=slow)
    elapsed = loop.time() - started

    assert len(got.steps) == 4
    assert all(s.answered for s in got.steps)
    assert elapsed < 0.15, "the reads did not overlap"


async def test_a_failed_read_is_named_rather_than_dropped() -> None:
    """**The failure this is most likely to hide.**

    A review silently assembled from three quarters of what it meant to gather reads exactly
    like a complete one, and a reader cannot tell which quarter is missing.
    """
    async def flaky(name: str) -> dict:
        if name == "reconciliation_report":
            raise OSError("pgvector refused")
        return {"read": name}

    got = await orchestrate.gather(("plant_overview", "reconciliation_report"), run=flaky)
    evidence = got.as_evidence()
    assert "plant_overview" in evidence["gathered"]
    assert "reconciliation_report" in evidence["could_not_read"]
    assert got.any_answered is True


async def test_a_read_returning_nothing_is_a_failure_not_an_empty_result() -> None:
    async def empty(name: str) -> None:
        return None

    got = await orchestrate.gather(("plant_overview",), run=empty)
    assert got.any_answered is False
    assert "returned nothing" in got.steps[0].failed


async def test_no_plan_gathers_nothing() -> None:
    async def never_called(name: str) -> dict:  # pragma: no cover - must not run
        raise AssertionError("nothing should be read without a plan")

    got = await orchestrate.gather((), run=never_called)
    assert got.steps == ()
    assert got.any_answered is False
