"""`C10` multi-step task memory · the context budget — what step three knows, and what fits.

Two gaps, both measured, both about the same thing: what a turn is allowed to carry.

**The first: step three cannot see step one.** `C15` in `memory.py` resolves what *"this"* and
*"the other one"* refer to, and it is deliberately shallow — six turns, equipment · label ·
day, and the wording of a question is never kept. A **task** is a different object. Two thirds
of measured cases pause: of 43 on the reference queue, 13 went straight through, 26 stopped at
the checks, 2 arrived already explained by a broken sensor and 2 by a blind model. The common
shape of real work is therefore an enquiry picked up later by somebody who needs what the
earlier steps *established* — not what was said about them. Nothing modelled that, so every
turn started again from the pack and the ordered findings existed only in a reader's head.

**Abandonment, and why it is not a flag.** Inherited constraint 22 exists because four open
cases described transmitters that had been repaired weeks earlier, and twenty had been waiting
since April. A task carries the same hazard one layer up: an enquiry quietly resumed three
weeks later stands on findings the plant has moved past. So a task can be **abandoned**, an
abandonment carries its reason in words, and resuming an abandoned task is refused rather than
performed — it takes an explicit reopening, which records what it overrode. `RC9`'s two kinds
of stale are kept apart here too: *abandoned* means somebody stopped it, *stale* means nobody
touched it. A single flag would let a settled enquiry and a forgotten one look identical, and
only the second needs a person.

**The second: nothing counted what goes into a prompt.** `max_context_chars` is 24,000 and
`max_input_chars` is 8,000 — both provisional against `Q48` — and before the budgeter nothing
read either of them. They appeared in `config.py`, in a test asserting they exist, and nowhere
else. Measured on this repository on 2026-08-17: one episode's `to_prompt_data()` renders
2,936 characters, and the seven `diagnose` turns recorded on the box carry message pairs of
5,712 to 5,929. A single-shot turn sits well inside the ceiling; a turn that composes several
episodes, a task trail and retrieved passages does not, and it would fail on an unpredictable
turn — the worst possible place to discover a limit, which is the same argument
`MAX_REMEMBERED_TURNS` makes one module along.

**The budgeter itself now lives in `app/prompts/budget.py`, and this module re-exports it.**
It spent its first day here with no consumer, and the reason is structural rather than an
oversight: `app.prompts` sits **below** `app.agents` in the spine, so `build_messages` — the
one function that assembles a prompt — could not import the thing that fits one. Moving it
down is what `importlinter.ini`'s preamble prescribes for exactly this shape, in preference to
an exception that quietly switches a contract off. `C10` and the budget still read as one idea
from here, because every name is re-exported below and `assemble_turn` is the place the two
actually meet.

**Dropping is allowed. Dropping silently is the failure.** An answer built on two thirds of
the evidence and presented as though built on all of it is the reassuring-lie shape constraint
16 exists to replace outright. The four things that are never dropped, why, and what happens
when one of them was never supplied in the first place, are all recorded in `app.prompts.budget`.

**Nothing here calls a model, and nothing here decides.** Ordering is a fixed table, the
ceilings come from configuration, and a task's findings are recorded by whoever established
them. The language model never sets a priority and never grants itself more room: the budget
is plain software, like the Control Plane one row above it in the separation law.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum

from app.prompts.budget import (
    DROP_ORDER,
    HONESTY_PAYLOAD,
    SECTION_SEPARATOR,
    AbsentPayload,
    AssembledContext,
    ContextSection,
    ContextTier,
    DroppedSection,
    FittedEvidence,
    absent_payload_in,
    assemble,
    fit_prompt_data,
    fit_question,
    sections_from_prompt_data,
)

#: Re-exported so the agent layer reads `C10` and the budget as one idea. The budgeter moved
#: down to `app.prompts` on 2026-08-18 so that `build_messages` could reach it at all; see the
#: module docstring above for why an import-linter exception was the wrong fix.
__all__ = [
    "DEFAULT_TASK_STALE_AFTER",
    "DROP_ORDER",
    "HONESTY_PAYLOAD",
    "MAX_TASK_STEPS",
    "SECTION_SEPARATOR",
    "AbsentPayload",
    "AssembledContext",
    "ContextSection",
    "ContextTier",
    "DroppedSection",
    "FittedEvidence",
    "StepOutcome",
    "Task",
    "TaskBook",
    "TaskState",
    "TaskStep",
    "absent_payload_in",
    "assemble",
    "assemble_turn",
    "fit_prompt_data",
    "fit_question",
    "sections_from_prompt_data",
]

# ── C10: a task, its ordered steps, and the two ways it stops ───────────────────

#: How many steps one task may hold before it stops rather than grows.
#:
#: TBD (Q82): no document states a depth for a multi-step task. Eight because that is
#: `max_react_steps`, the one bound in the product that already means "steps inside one piece
#: of work" — borrowing it keeps two ceilings from disagreeing, and inventing a second number
#: would be inventing a number. A task step is **not** a ReAct step, so Q82 asks whether the
#: two must differ; until it is answered they do not.
MAX_TASK_STEPS: int = 8

#: How long a task may sit untouched before it must be confirmed rather than continued.
#:
#: TBD (Q83): no document fixes this either. Seven days is `DEFAULT_AGEING_AFTER` from `RC9`'s
#: case ageing, deliberately reused so a task and the case it is about do not go stale on
#: different days. Q83 asks whether a conversation should age faster than the case it concerns
#: — it plausibly should. Going stale only ever *refuses to resume*; it closes nothing, hides
#: nothing and eliminates nothing.
DEFAULT_TASK_STALE_AFTER: timedelta = timedelta(days=7)


class StepOutcome(StrEnum):
    """What one step of a task actually settled.

    Four, and three of them are not failures. Kept separate from `AnswerState` on purpose: the
    answer contract describes how a *turn* ended, and this describes whether a **later step may
    stand on this one**. A turn that ended `NO_DIAGNOSIS` established something real — that a
    gate did not pass — and a task that recorded it as a failure would go looking for the same
    answer again.
    """

    ESTABLISHED = "established"
    """Something a later step may rely on. The only outcome that carries forward."""

    REFUSED = "refused"
    """The platform said no and said why. A refusal is not an error, and it is not an absence
    of information — *"the gates did not pass"* is a finding a later step must not overwrite."""

    WAITING = "waiting"
    """Asked of a person and not yet answered. `RC1`'s pause, one layer up: 26 of 43 cases stop
    here, and a task holding one is unfinished rather than stalled."""

    FAILED = "failed"
    """The software broke. The only outcome here that is a bug."""


class TaskState(StrEnum):
    """Where the whole task stands. Three, and two of them mean *do not simply carry on*."""

    OPEN = "open"
    COMPLETE = "complete"
    ABANDONED = "abandoned"
    """Somebody stopped it, or a bound did. Distinct from stale, which is nobody touching it —
    constraint 22 keeps those two apart because a settled enquiry and a forgotten one need
    different things from a reader."""


@dataclass(frozen=True)
class TaskStep:
    """One step, what it set out to establish, and what it found — in words, always.

    The finding is a sentence rather than a value because a later step reads it, and a step
    recorded as `REFUSED` with a blank finding is the dash this product does not print. The
    constructor refuses it, in the same way `Figure` refuses a value with no basis: an
    instruction is followed most of the time, and an invariant is followed always.
    """

    ordinal: int
    intent: str
    outcome: StepOutcome
    finding: str
    at: datetime

    def __post_init__(self) -> None:
        if not self.intent.strip():
            raise ValueError("a task step must say what it set out to establish")
        if not self.finding.strip():
            raise ValueError(
                f"step {self.ordinal} ({self.intent!r}) records the outcome "
                f"{self.outcome.value!r} with no finding. Every outcome carries its reason in "
                f"words — a later step reads this, and a blank reads as nothing happened"
            )

    @property
    def is_load_bearing(self) -> bool:
        """Whether a later step may stand on this one. Only `ESTABLISHED` may be."""
        return self.outcome is StepOutcome.ESTABLISHED

    def render(self) -> str:
        return f"{self.ordinal}. {self.intent} — {self.outcome.value}: {self.finding}"


@dataclass(frozen=True)
class Task:
    """`C10`. An ordered enquiry that outlives the turn that started it. Immutable throughout.

    Every mutator returns a new task, like `TurnMemory`, so a step can never be edited after
    the fact — a findings record that can be rewritten is one nobody can audit.
    """

    id: str
    goal: str
    opened_at: datetime
    steps: tuple[TaskStep, ...] = field(default_factory=tuple)
    state: TaskState = TaskState.OPEN
    abandoned_reason: str = ""
    abandoned_at: datetime | None = None
    overrides: tuple[str, ...] = field(default_factory=tuple)
    """Every abandonment this task was reopened past, kept verbatim. The record survives the
    reopening, because *"why was this picked up again"* needs a better answer than silence."""

    # ── reading ────────────────────────────────────────────────────────────────

    @property
    def next_ordinal(self) -> int:
        return len(self.steps) + 1

    @property
    def last_touched_at(self) -> datetime:
        return self.steps[-1].at if self.steps else self.opened_at

    @property
    def established(self) -> tuple[TaskStep, ...]:
        """The steps a later step may stand on. Refused, waiting and failed ones are carried
        in the trail but never offered as ground — that is the difference between *"we asked
        and could not tell"* and *"we know"*."""
        return tuple(s for s in self.steps if s.is_load_bearing)

    @property
    def is_waiting_on_a_person(self) -> bool:
        return any(s.outcome is StepOutcome.WAITING for s in self.steps)

    def is_stale_at(
        self, now: datetime, stale_after: timedelta = DEFAULT_TASK_STALE_AFTER
    ) -> bool:
        return self.state is TaskState.OPEN and (now - self.last_touched_at) >= stale_after

    def where_we_got_to(self, now: datetime | None = None) -> str:
        """What a turn shows when somebody asks. Ordered, with every outcome named.

        `now` is optional and its absence is stated rather than assumed: whether the task has
        gone stale is a question about a moment, and a renderer that quietly skipped the check
        would let a three-week-old trail read as current.
        """
        head = f"Task {self.id} — {self.goal} ({self.state.value})"
        if self.state is TaskState.ABANDONED:
            head += f". Abandoned: {self.abandoned_reason}"
        elif now is None:
            head += ". How long it has sat was not checked — no moment was supplied"
        elif self.is_stale_at(now):
            head += (
                f". Nobody has touched this since {self.last_touched_at:%Y-%m-%d}; it must be "
                f"confirmed before it is continued"
            )

        if not self.steps:
            return f"{head}\nNo step has been recorded yet, so nothing has been established."

        body = "\n".join(s.render() for s in self.steps)
        ground = len(self.established)
        return (
            f"{head}\n{body}\n"
            f"{ground} of {len(self.steps)} step(s) established something a later step may "
            f"stand on."
        )

    def resume(
        self, now: datetime, *, stale_after: timedelta = DEFAULT_TASK_STALE_AFTER
    ) -> tuple[Task | None, str]:
        """May this task be continued, and the reason either way. Never raises.

        The reading path, shaped like `TurnMemory.resolve`: a value and the words that justify
        it, so a route trace can show *why* a task was picked up or left alone. Three refusals,
        kept distinct because they call for different things — reopen it, start a new one, or
        confirm it is still the situation on the plant.
        """
        if self.state is TaskState.ABANDONED:
            when = f" on {self.abandoned_at:%Y-%m-%d}" if self.abandoned_at else ""
            return None, (
                f"task {self.id} was abandoned{when} because {self.abandoned_reason} It is not "
                f"resumed on its own — reopen it explicitly, which records what that overrode."
            )
        if self.state is TaskState.COMPLETE:
            return None, (
                f"task {self.id} is complete, with {len(self.steps)} recorded step(s). A new "
                f"question opens a new task rather than extending a settled one."
            )
        if self.is_stale_at(now, stale_after):
            return None, (
                f"task {self.id} has not been touched since "
                f"{self.last_touched_at:%Y-%m-%d}, longer than {stale_after.days} day(s). Four "
                f"open cases once described transmitters repaired weeks earlier, so it is "
                f"offered for confirmation rather than continued."
            )
        return self, (
            f"task {self.id} continues at step {self.next_ordinal}; "
            f"{len(self.established)} earlier step(s) established something to stand on."
        )

    # ── writing ────────────────────────────────────────────────────────────────

    def record(
        self, *, intent: str, outcome: StepOutcome, finding: str, at: datetime
    ) -> Task:
        """Append one step and return a new task.

        **Recording onto a task that is not open raises.** That is deliberate and it is not the
        "a refusal is not an error" rule being broken: a refusal is a *turn outcome*, and this
        is an invariant, like `Figure` refusing a value with no basis. A caller reaching here
        has skipped `resume()`, and silently appending would be exactly the quiet resumption
        constraint 22 forbids — the failure would then surface as a confident answer weeks
        later rather than as a stack trace now.
        """
        if self.state is not TaskState.OPEN:
            why = self.abandoned_reason or "it is no longer open"
            raise ValueError(
                f"task {self.id} is {self.state.value} — {why} Recording a step would resume "
                f"it silently. Call resume() to read the reason in words, or reopen() to "
                f"override it on the record."
            )
        if len(self.steps) >= MAX_TASK_STEPS:
            return self._abandoned_by_the_ceiling(intent, at)

        step = TaskStep(
            ordinal=self.next_ordinal,
            intent=intent,
            outcome=outcome,
            finding=finding,
            at=at,
        )
        return replace(self, steps=(*self.steps, step))

    def _abandoned_by_the_ceiling(self, refused_intent: str, at: datetime) -> Task:
        """The step bound, and why hitting it abandons rather than truncates.

        `TurnMemory` drops its oldest turn when it fills, and that is right there: forgetting
        the wording of an old question costs nothing. Here it would cost everything — step
        three needs what step one established, and dropping step one to make room for step nine
        loses precisely what step nine came for. So the task stops, says so, and the step that
        did not fit is named.
        """
        return replace(
            self,
            state=TaskState.ABANDONED,
            abandoned_at=at,
            abandoned_reason=(
                f"it reached its ceiling of {MAX_TASK_STEPS} steps without concluding, and the "
                f"step {refused_intent!r} was not recorded. It is abandoned rather than "
                f"truncated: dropping an earlier step to make room would lose exactly what a "
                f"later step needs. Open a new task carrying the findings that matter."
            ),
        )

    def abandon(self, reason: str, at: datetime) -> Task:
        """Stop this task, on the record. The reason is required and is not decorative."""
        if not reason.strip():
            raise ValueError(
                "an abandoned task with no reason is a row nobody can act on. Say why — it is "
                "what tells the next reader whether to reopen it or start again"
            )
        return replace(
            self, state=TaskState.ABANDONED, abandoned_reason=reason.strip(), abandoned_at=at
        )

    def complete(self, at: datetime) -> tuple[Task | None, str]:
        """Settle the task, or refuse and say why. Never raises.

        A task still waiting on a person is not complete, however much has been established.
        `RC1` pauses in 26 of 43 cases and the pause is the feature; a task that closed over
        one would turn *"waiting for a technician"* back into a value in a response.
        """
        if self.state is not TaskState.OPEN:
            return None, f"task {self.id} is already {self.state.value}"
        if self.is_waiting_on_a_person:
            pending = next(s for s in self.steps if s.outcome is StepOutcome.WAITING)
            return None, (
                f"task {self.id} cannot complete: step {pending.ordinal} is still waiting — "
                f"{pending.finding}"
            )
        return replace(self, state=TaskState.COMPLETE), (
            f"task {self.id} is complete after {len(self.steps)} step(s), "
            f"{len(self.established)} of which established something."
        )

    def reopen(self, reason: str, at: datetime) -> Task:
        """Override an abandonment, keeping the abandonment on the record.

        The point of the whole mechanism: an abandoned task **can** be continued, but only
        deliberately, and never in a way that erases why it stopped. Elimination is final in
        `RC13` for the same reason — a settled question nobody re-examines is dangerous exactly
        because the settling is invisible.
        """
        if not reason.strip():
            raise ValueError(
                "reopening an abandoned task needs a reason — it is the only record that "
                "somebody decided the earlier stop no longer applies"
            )
        if self.state is not TaskState.ABANDONED:
            return self
        return replace(
            self,
            state=TaskState.OPEN,
            abandoned_reason="",
            abandoned_at=None,
            overrides=(
                *self.overrides,
                f"{at:%Y-%m-%d}: reopened because {reason.strip()} "
                f"It had been abandoned because {self.abandoned_reason}",
            ),
        )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "state": self.state.value,
            "opened_at": self.opened_at.isoformat(),
            "last_touched_at": self.last_touched_at.isoformat(),
            "abandoned_reason": self.abandoned_reason,
            "overrides": list(self.overrides),
            "steps": [
                {
                    "ordinal": s.ordinal,
                    "intent": s.intent,
                    "outcome": s.outcome.value,
                    "finding": s.finding,
                    "at": s.at.isoformat(),
                }
                for s in self.steps
            ],
        }


@dataclass(frozen=True)
class TaskBook:
    """Every task this conversation opened, newest last. The object a router holds.

    Separate from `TurnMemory` rather than folded into it, because the two are bounded
    differently and for different reasons: turn memory forgets its oldest turn silently and
    that is harmless, while a task must never lose a step. Folding them would force one policy
    onto both.
    """

    tasks: tuple[Task, ...] = field(default_factory=tuple)

    def open_task(self, *, id: str, goal: str, at: datetime) -> tuple[TaskBook, Task]:
        task = Task(id=id, goal=goal, opened_at=at)
        return replace(self, tasks=(*self.tasks, task)), task

    def by_id(self, id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == id), None)

    def updated(self, task: Task) -> TaskBook:
        """Replace one task by id. Appends it when the book has never seen it."""
        if self.by_id(task.id) is None:
            return replace(self, tasks=(*self.tasks, task))
        return replace(
            self, tasks=tuple(task if t.id == task.id else t for t in self.tasks)
        )

    def resumable(
        self, now: datetime, *, stale_after: timedelta = DEFAULT_TASK_STALE_AFTER
    ) -> tuple[Task | None, str]:
        """The task a new turn may continue, and the reason in words when none may.

        Newest first, and the reason returned is the newest task's own — a reader asking
        *"where had we got to"* is asking about the thing they were last doing, and answering
        with a refusal from three tasks ago would name the wrong enquiry.
        """
        if not self.tasks:
            return None, "no task has been opened in this conversation"
        for task in reversed(self.tasks):
            resumed, reason = task.resume(now, stale_after=stale_after)
            if resumed is not None:
                return resumed, reason
        _, newest_reason = self.tasks[-1].resume(now, stale_after=stale_after)
        return None, (
            f"none of the {len(self.tasks)} task(s) here may be continued. The most recent: "
            f"{newest_reason}"
        )

    def where_we_got_to(self, now: datetime | None = None) -> str:
        if not self.tasks:
            return "no task has been opened in this conversation"
        return "\n\n".join(t.where_we_got_to(now) for t in self.tasks)


# ── where the two halves meet ──────────────────────────────────────────────────

def assemble_turn(
    prompt_data: dict,
    *,
    task: Task | None = None,
    now: datetime | None = None,
    budget: int | None = None,
) -> AssembledContext:
    """The whole turn's context: the pack, plus where a multi-step task had got to.

    The trail enters as `HISTORY` and is therefore the **first** thing surrendered, which is
    the right trade: losing *"step two established the flow reads zero"* costs a turn some
    continuity, and losing *"that flow has never been measured at all"* costs a reader the
    reason the branch cannot be judged.

    A task that may not be resumed still enters — marked, with the refusal attached — because
    a trail silently omitted reads as a conversation that never happened, and an abandoned
    enquiry is exactly the thing a reader needs told rather than hidden.
    """
    sections = list(sections_from_prompt_data(prompt_data))
    if task is not None:
        sections.append(
            ContextSection("task_trail", ContextTier.HISTORY, _task_section_text(task, now))
        )
    return assemble(sections, budget=budget)


def _task_section_text(task: Task, now: datetime | None) -> str:
    trail = task.where_we_got_to(now)
    if now is None:
        return f"where we had got to:\n{trail}"
    _, reason = task.resume(now)
    return f"where we had got to:\n{trail}\nWhether it may be continued: {reason}"
