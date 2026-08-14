"""Whether the brain's thinking channel is on, per task.

Ported verbatim in spirit from the sibling's 43 lines. The failure mode is the reason this is
a table rather than a flag: **getting it wrong does not produce a worse answer, it produces an
empty one.** With a tight `num_predict` the model spends the whole allowance in the think
channel and returns no content at all.

So anything unrecognised defaults **OFF**, because composition is the common case and the one
that breaks. This is question `Q28`, with that answer already proposed.

Two safety rules ride along, both in `should_think`:
  * the flag is only ever sent when the effective model is actually the brain — the other two
    reject it;
  * the planner is exempt, because forced-JSON output has no free-form channel to starve.

Pure. No settings, no I/O — a table of task names is code, not configuration.
"""
from __future__ import annotations

from app.llm.models import effective_role

# Thinking pays where the task is decomposition or diagnosis.
_THINK_TASKS: frozenset[str] = frozenset({
    "root_cause",
    "diagnose",
    "diagnosis",
    "domain_analyst",
    "domain_analysis",
    "investigate",
    "plan_reasoning",
})

# Named explicitly so the intent is visible, even though the default already covers them.
_NO_THINK_TASKS: frozenset[str] = frozenset({
    "composer",
    "compose",
    "synthesis",
    "quick",
    "brief",
    "narrate",
    "sql",
    "auditor",
    "audit",
    "route",
    "planner",          # exempt: forced JSON has no free-form channel to starve
})


def should_think(task: str, *, role: str = "brain") -> bool:
    """Is the thinking channel on for this task?

    Unknown tasks return False deliberately. An unrecognised task that silently enabled
    thinking would return an empty answer, and an empty answer is harder to debug than a
    shallow one.
    """
    if effective_role(role) != "brain":
        return False
    if task in _NO_THINK_TASKS:
        return False
    return task in _THINK_TASKS


def think_tasks() -> frozenset[str]:
    """The tasks that reason. Exposed so a test can assert the table rather than the behaviour."""
    return _THINK_TASKS
