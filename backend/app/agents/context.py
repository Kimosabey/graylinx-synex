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
`max_input_chars` is 8,000 — both provisional against `Q48` — and before this module nothing
read either of them. They appeared in `config.py`, in a test asserting they exist, and nowhere
else. Measured on this repository on 2026-08-17: one episode's `to_prompt_data()` renders
2,936 characters and the whole explain message pair 5,551, so a single-shot turn sits well
inside the ceiling. A turn that composes several episodes, a task trail and retrieved passages
does not, and it would fail on an unpredictable turn — the worst possible place to discover a
limit, which is the same argument `MAX_REMEMBERED_TURNS` makes one module along.

**Dropping is allowed. Dropping silently is the failure.** An answer built on two thirds of
the evidence and presented as though built on all of it is the reassuring-lie shape constraint
16 exists to replace outright. So every drop is reported twice — to the caller, and inside the
context the model reads, so the answer itself can say so. Four things are never dropped, in
this order:

| | Never dropped | Because |
|---|---|---|
| 1 | the gate outcome | `NO_DIAGNOSIS` is the modal outcome, and a turn that lost the failed
  gate would answer as though the equipment had been fit to judge |
| 2 | any never-measured or suspect signal note | `cond_flow` has never recorded a non-zero
  value in 37,430 measured slots and feeds four of the six models |
| 3 | the data window | constraint 15 — anomaly counts were once shown under a heading
  describing a telemetry window that did not overlap them at all |
| 4 | the fault label | the trained model's own output, including the four class names that
  say `AMBIGUOUS` or `UNSPECIFIED` |

That order is not arbitrary. On the pack measured above, signal provenance alone is 1,552 of
the 2,936 characters — 53% of the whole, the most expensive thing in the pack and the least
droppable. A residual dropped to fit costs a reader one line; *"this signal was never
measured"* dropped to fit costs them the reason the branch cannot be judged at all.

**Nothing here calls a model, and nothing here decides.** Ordering is a fixed table, the
ceilings come from configuration, and a task's findings are recorded by whoever established
them. The language model never sets a priority and never grants itself more room: the budget
is plain software, like the Control Plane one row above it in the separation law.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum

from app.config import CONTEXT_TRUNCATION_MARKER, get_settings

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


# ── the context budget ─────────────────────────────────────────────────────────

SECTION_SEPARATOR = "\n"


class ContextTier(StrEnum):
    """What a piece of context *is*, which is what decides whether it may be given up.

    Held as a closed set rather than a number so the ordering is inspectable: a priority
    integer somebody nudges is how *"this signal was never measured"* ends up below a residual.
    """

    GATE_OUTCOME = "gate_outcome"
    SIGNAL_NOTE = "signal_note"
    DATA_WINDOW = "data_window"
    FAULT_LABEL = "fault_label"
    EVIDENCE = "evidence"
    SUPPORTING = "supporting"
    HISTORY = "history"


#: The honesty payload, **in the order the ceiling protects it**. Never dropped, whatever the
#: budget. Each entry is a measured failure: a lost gate outcome answers as though the machine
#: was fit to judge; a lost signal note lets `cond_flow` read as a reading rather than as an
#: instrument the plant does not have; a lost window is constraint 15's mismatched heading; a
#: lost label invents certainty the trained model never claimed.
HONESTY_PAYLOAD: tuple[ContextTier, ...] = (
    ContextTier.GATE_OUTCOME,
    ContextTier.SIGNAL_NOTE,
    ContextTier.DATA_WINDOW,
    ContextTier.FAULT_LABEL,
)

#: What is given up first when the budget bites. History before supporting detail, supporting
#: detail before evidence — a residual is the last thing surrendered, and it is surrendered
#: rather than the note that says a signal was never measured at all.
DROP_ORDER: tuple[ContextTier, ...] = (
    ContextTier.HISTORY,
    ContextTier.SUPPORTING,
    ContextTier.EVIDENCE,
)


@dataclass(frozen=True)
class ContextSection:
    """One labelled piece of what the model will read, and what kind of thing it is."""

    key: str
    tier: ContextTier
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def is_honesty_payload(self) -> bool:
        return self.tier in HONESTY_PAYLOAD


@dataclass(frozen=True)
class DroppedSection:
    """Something that did not fit, and why — in words, never a count on its own."""

    key: str
    tier: ContextTier
    chars: int
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError(
                f"section {self.key!r} was dropped with no reason. A silent drop is the whole "
                f"failure this module exists to prevent"
            )

    def render(self) -> str:
        return f"{self.key} ({self.chars} characters) — {self.reason}"


@dataclass(frozen=True)
class AssembledContext:
    """What fitted, what did not, and whether the turn may be sent at all."""

    text: str
    budget: int
    included: tuple[ContextSection, ...] = field(default_factory=tuple)
    dropped: tuple[DroppedSection, ...] = field(default_factory=tuple)
    must_refuse: bool = False
    refusal_reason: str = ""

    @property
    def used_chars(self) -> int:
        return len(self.text)

    @property
    def is_complete(self) -> bool:
        """Nothing was dropped, and the ceiling was not hit. The ordinary case."""
        return not self.dropped and not self.must_refuse

    @property
    def dropped_chars(self) -> int:
        return sum(d.chars for d in self.dropped)

    def render_drop_report(self) -> str:
        """What a route trace shows. An absence of drops is stated, not left blank."""
        if self.must_refuse:
            return self.refusal_reason
        if not self.dropped:
            return (
                f"nothing was dropped — {self.used_chars} of {self.budget} characters used, "
                f"and every section fitted"
            )
        return (
            f"{len(self.dropped)} section(s) totalling {self.dropped_chars} characters did not "
            f"fit the {self.budget}-character ceiling: "
            + "; ".join(d.render() for d in self.dropped)
        )

    def as_dict(self) -> dict:
        return {
            "budget": self.budget,
            "used_chars": self.used_chars,
            "is_complete": self.is_complete,
            "must_refuse": self.must_refuse,
            "refusal_reason": self.refusal_reason,
            "included": [s.key for s in self.included],
            "dropped": [
                {"key": d.key, "tier": d.tier.value, "chars": d.chars, "reason": d.reason}
                for d in self.dropped
            ],
        }


def _joined(sections: Sequence[ContextSection]) -> str:
    return SECTION_SEPARATOR.join(s.text for s in sections)


def _payload_first(sections: Sequence[ContextSection]) -> tuple[ContextSection, ...]:
    """The honesty payload in the order `HONESTY_PAYLOAD` fixes, original order within a tier."""
    return tuple(
        sorted(
            (s for s in sections if s.is_honesty_payload),
            key=lambda s: HONESTY_PAYLOAD.index(s.tier),
        )
    )


def _drop_rank(tier: ContextTier) -> int:
    """Where a tier sits in the surrender order — lower goes first.

    A tier in neither table is treated as the **last** droppable thing to give up. That is the
    safe direction for an unclassified piece of context, and it never becomes a quiet default:
    a test asserts every tier is in exactly one of the two tables, so an unclassified one is a
    failing build rather than a section that turns out to be protected by accident.
    """
    return DROP_ORDER.index(tier) if tier in DROP_ORDER else len(DROP_ORDER)


def _keep_order(sections: Sequence[ContextSection]) -> tuple[ContextSection, ...]:
    """Everything droppable, most-worth-keeping first — the reverse of the drop order."""
    return tuple(
        sorted(
            (s for s in sections if not s.is_honesty_payload),
            key=lambda s: -_drop_rank(s.tier),
        )
    )


def _drop_note(dropped: Sequence[DroppedSection], budget: int) -> str:
    """The note the **model** reads, so the answer can say what it was built on.

    Reporting the drop only to the caller would be half the fix: the caller can log it, but the
    sentence a reader sees is written by something that still believes it saw everything.

    **Keys only, and one shared reason.** The per-section reasons go to the caller, where they
    are read once; repeating them here costs about two hundred characters each, which on a
    tight budget makes the note the thing that pushed the evidence out. A note that grows
    faster than what it reports would have to be dropped, and then nothing says anything.
    """
    keys = ", ".join(d.key for d in dropped)
    return (
        f"{CONTEXT_TRUNCATION_MARKER}\n"
        f"{len(dropped)} section(s) did not fit the {budget}-character context ceiling and are "
        f"absent entirely rather than shortened: {keys}. This answer rests on what remains — "
        f"say so if it matters. The gate outcome, the signal provenance notes, the data window "
        f"and the fault label are never dropped, so those are complete above."
    )


def _dropped_for(section: ContextSection, budget: int, exhausted_at: str) -> DroppedSection:
    return DroppedSection(
        key=section.key,
        tier=section.tier,
        chars=section.chars,
        reason=(
            f"{section.tier.value} content, dropped to fit the {budget}-character context "
            f"ceiling. The budget was exhausted at {exhausted_at!r}, and everything with an "
            f"equal or weaker claim to the space went with it. None of it was shortened or "
            f"paraphrased — it is absent"
        ),
    )


def assemble(
    sections: Sequence[ContextSection], *, budget: int | None = None
) -> AssembledContext:
    """Fit the evidence into the ceiling and report what did not fit. Never raises.

    **Stop-on-first-miss, not a best packing.** Candidates are walked most-worth-keeping
    first, and once one does not fit, it and everything with a weaker claim to the space go
    with it — even where a smaller later section would have squeezed in. That is a deliberate
    loss of a few hundred characters in exchange for a result somebody can check: *"residuals 1
    to 4 are here, 5 and 6 are not"* is a sentence a reader can verify against the pack, and
    the output of a knapsack is not.
    """
    limit = budget if budget is not None else get_settings().max_context_chars
    payload = _payload_first(sections)
    payload_text = _joined(payload)

    if len(payload_text) > limit:
        return AssembledContext(
            text=payload_text,
            budget=limit,
            included=payload,
            dropped=(),
            must_refuse=True,
            refusal_reason=(
                f"the honesty payload alone is {len(payload_text)} characters against a "
                f"ceiling of {limit}. It is returned whole and unsent rather than trimmed: the "
                f"gate outcome, the signal notes, the data window and the fault label are the "
                f"four things that must never be dropped, so there is nothing left to give up. "
                f"Ask a narrower question, or raise the ceiling deliberately — "
                f"TBD (Q84) records which of those is correct."
            ),
        )

    kept = list(payload)
    dropped: list[DroppedSection] = []
    exhausted_at = ""
    for section in _keep_order(sections):
        if not exhausted_at and len(_joined([*kept, section])) <= limit:
            kept.append(section)
            continue
        exhausted_at = exhausted_at or section.key
        dropped.append(_dropped_for(section, limit, exhausted_at))

    return _with_room_for_the_note(kept, dropped, limit)


def _with_room_for_the_note(
    kept: list[ContextSection], dropped: list[DroppedSection], limit: int
) -> AssembledContext:
    """Make the note that reports the drops fit too, giving up more sections if it must.

    The note is part of the context, so a budget that leaves no room for it would produce the
    silent truncation the note exists to prevent — the failure re-entering through the door
    marked exit. Sections are surrendered from the least-kept end until it fits, and each one
    surrendered is itself reported.
    """
    while dropped:
        note = _drop_note(_in_drop_order(dropped), limit)
        body = _joined(kept)
        if len(body) + len(SECTION_SEPARATOR) + len(note) <= limit:
            return AssembledContext(
                text=f"{body}{SECTION_SEPARATOR}{note}",
                budget=limit,
                included=tuple(kept),
                dropped=_in_drop_order(dropped),
            )

        surrendered = next((s for s in reversed(kept) if not s.is_honesty_payload), None)
        if surrendered is None:
            return AssembledContext(
                text=f"{_joined(kept)}{SECTION_SEPARATOR}{note}",
                budget=limit,
                included=tuple(kept),
                dropped=_in_drop_order(dropped),
                must_refuse=True,
                refusal_reason=(
                    f"the honesty payload fits the {limit}-character ceiling but the note "
                    f"reporting {len(dropped)} dropped section(s) does not fit beside it. "
                    f"Sending the payload without the note would hide the drop, which is the "
                    f"failure this assembler exists to prevent — TBD (Q84)."
                ),
            )
        kept.remove(surrendered)
        dropped.append(
            _dropped_for(surrendered, limit, "the note that reports the dropped sections")
        )

    return AssembledContext(text=_joined(kept), budget=limit, included=tuple(kept))


def _in_drop_order(dropped: Sequence[DroppedSection]) -> tuple[DroppedSection, ...]:
    """Report the drops in the order they were surrendered, not in the order they were walked.

    The selection walks the candidates most-worth-keeping first, so the raw list reads
    evidence-then-history — the reverse of what happened. A reader checking *"what did this
    give up first"* against `DROP_ORDER` would find the two disagreeing, and the table is the
    thing that is supposed to be inspectable.
    """
    return tuple(sorted(dropped, key=lambda d: _drop_rank(d.tier)))


def fit_question(question: str, *, limit: int | None = None) -> tuple[str, str]:
    """`max_input_chars`, applied where the text arrives. Returns the text and the reason.

    A pasted wall of text is what the ceiling stops, and clipping it is fine — clipping it
    without saying so is not, because the model then answers a question it only half received
    and the answer reads as though it addressed the whole thing.

    At a ceiling shorter than the marker itself the marker is all that comes back, deliberately:
    a clipped question carrying no marker is the one output this function must never produce.
    """
    cap = limit if limit is not None else get_settings().max_input_chars
    if len(question) <= cap:
        return question, f"the question fitted the {cap}-character input ceiling whole"

    room = max(cap - len(CONTEXT_TRUNCATION_MARKER), 0)
    kept = question[:room]
    lost = len(question) - room
    return f"{kept}{CONTEXT_TRUNCATION_MARKER}", (
        f"the question was {len(question)} characters against an input ceiling of {cap}; the "
        f"last {lost} were not sent, and the text carries a marker saying so"
    )


# ── from the pack the model actually receives ──────────────────────────────────

#: Everything in `to_prompt_data()` that is real but surrenderable, in the order it is given
#: up. `sources` last because a lineage line is the least useful thing to a reader who has
#: already lost the residual it describes.
_SUPPORTING_KEYS: tuple[str, ...] = (
    "other_labels_same_day",
    "severity",
    "slots_in_episode",
    "sources",
)

#: Stated rather than omitted. A pack with no window is itself a defect — constraint 15 — and
#: the model is never left to supply "now" from its own head.
_NO_WINDOW = (
    "not stated by the evidence pack, which is itself a defect: every artefact states its "
    "data window, and this answer covers an unstated span"
)


def sections_from_prompt_data(prompt_data: dict) -> tuple[ContextSection, ...]:
    """Tier what `EvidencePack.to_prompt_data()` produces. Nothing is reformatted.

    Every value arrives as a display string because the pack carries display strings rather
    than floats, and this module keeps that true: it labels and orders, and never renders a
    number. Re-rendering would reintroduce a tolerance, and every tolerance forgives some
    fabrication.

    **`model_fit_warning` is tiered as a signal note rather than as evidence.** Chiller 1's
    current model runs at nRMSE 48.03 against chiller 2's 2.65, so a residual quoted without
    its fit warning is the *suspect* case the never-dropped rule names — the same defect as a
    never-measured signal reading as a measurement, arriving by a different door.
    """
    out: list[ContextSection] = []

    for i, line in enumerate(prompt_data.get("gates") or (), 1):
        out.append(ContextSection(f"gate.{i}", ContextTier.GATE_OUTCOME, f"gate — {line}"))
    may_diagnose = prompt_data.get("may_diagnose") or "not stated"
    out.append(
        ContextSection(
            "may_diagnose",
            ContextTier.GATE_OUTCOME,
            f"may a fault be named from this evidence: {may_diagnose}",
        )
    )

    for i, line in enumerate(prompt_data.get("signal_provenance") or (), 1):
        out.append(ContextSection(f"signal.{i}", ContextTier.SIGNAL_NOTE, f"signal — {line}"))
    if prompt_data.get("model_fit_warning"):
        out.append(
            ContextSection(
                "model_fit_warning", ContextTier.SIGNAL_NOTE, prompt_data["model_fit_warning"]
            )
        )

    out.append(
        ContextSection(
            "data_window",
            ContextTier.DATA_WINDOW,
            f"data window — {prompt_data.get('data_window') or _NO_WINDOW}",
        )
    )
    out.append(
        ContextSection(
            "fault_label",
            ContextTier.FAULT_LABEL,
            f"fault label — {prompt_data.get('fault_label', 'no label on this slot')}; the "
            f"trained model declares it undecidable: "
            f"{prompt_data.get('model_declares_undecidable', 'not stated')}",
        )
    )

    out.append(
        ContextSection(
            "equipment",
            ContextTier.EVIDENCE,
            f"equipment — {prompt_data.get('equipment', 'not stated')} on "
            f"{prompt_data.get('day', 'a day the pack did not state')}",
        )
    )
    for i, line in enumerate(prompt_data.get("residuals") or (), 1):
        out.append(ContextSection(f"residual.{i}", ContextTier.EVIDENCE, f"residual — {line}"))

    for key in _SUPPORTING_KEYS:
        value = prompt_data.get(key)
        if not value:
            continue
        rendered = "; ".join(str(v) for v in value) if isinstance(value, list) else str(value)
        out.append(ContextSection(key, ContextTier.SUPPORTING, f"{key} — {rendered}"))

    return tuple(out)


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
