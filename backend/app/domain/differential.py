"""`RC12` narrowing · `RC13` the elimination audit · `RC14` exhausted is not settled.

A flat checklist says *go and do all six of these*. A differential says *three causes fit;
this one test kills two of them.* Same library, different question — and it is what `F5`
hands off to once a class is named but ambiguous.

**Only a class the trained model declares undecidable gets one.** Inherited constraint 27:
narrowing a class that already names a mechanism would be inventing ambiguity the model
never reported. Four of our seven qualify — the ones whose names say *ambiguous*,
*unspecified*, *unexplained*, and *undercharge **or** restriction*.

**This is the highest-risk content in the programme, and the code is shaped by that.**
Thirty-one causes have already been eliminated on the reference queue, every one by a
discriminator no refrigeration engineer has reviewed. Elimination is irreversible and nobody
re-examines a settled question, so a wrong discriminator does not produce a wrong answer
once — it produces a **confident wrong answer that is never revisited**.

Five rules follow from that, and each is a constraint with a real failure behind it:

| | Rule | Why |
|---|---|---|
| 28 | A confirmation **never** eliminates siblings | Fouling on a machine also low on
  flow is *two real causes*; collapsing to the first is how the second is missed |
| 29 | Elimination is **final** | An answer never resurrects a ruled-out cause |
| 30 | *Can't tell* has **no effect at all** | Otherwise uncertainty silently eliminates |
| 31 | Every elimination records **the check and the answer** | *"Why did nobody look at
  the tower?"* deserves better than *"the software decided"* |
| 32 | **Exhausted** is not **settled** | Running out of questions establishes *"we cannot
  separate these"* — a different statement from a conclusion |

**Nothing here calls a model.** `RC12` and `RC14` are `R` in the register — rules. The
language model decides *what to ask*; it never decides *whether* to ask, and it never
decides what an answer eliminates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain import faults
from app.domain.cases import DEFAULT_CAPABILITY, Capability


class Effect(StrEnum):
    """What one answer does to one candidate cause. Three, and only one is irreversible."""

    CONFIRM = "confirm"
    """Positive evidence **for** this cause. Does not touch its siblings — constraint 28."""

    ELIMINATE = "eliminate"
    """Rules the cause out. **Irreversible** — constraint 29."""

    KEEP = "keep"
    """Consistent; neither confirms nor eliminates. The commonest and least interesting."""


class Outcome(StrEnum):
    """How a differential ended. The last two are deliberately distinct — constraint 32."""

    OPEN = "open"
    SETTLED = "settled"
    """One cause stands, and the eliminations that got there are recorded."""

    EXHAUSTED = "exhausted"
    """The questions ran out with more than one cause alive.

    **Not a conclusion.** It is the honest *"we cannot separate these with the checks we
    have"*, and reporting it as a conclusion on whichever cause happens to remain is the
    failure this outcome exists to name."""


#: The answer that must change nothing. Constraint 30: every discriminating question carries
#: an explicit *can't tell*, and it is not merely ignored — it is asserted to have empty
#: effects, because a question whose "don't know" quietly eliminated something would be
#: worse than no question.
CANNOT_TELL = "cannot_tell"


@dataclass(frozen=True)
class Answer:
    """One possible answer to a discriminating question, and what it does."""

    key: str
    text: str
    effects: dict[str, Effect] = field(default_factory=dict)
    """Cause id -> effect. `CANNOT_TELL` must map to an empty dict."""


@dataclass(frozen=True)
class Question:
    """One discriminating question. The unit of narrowing."""

    id: str
    text: str
    answers: tuple[Answer, ...]
    sme_reviewed: bool = False
    """No refrigeration engineer has reviewed a single discriminator. Defaults False, and
    `Differential.askable` hides anything unreviewed — so no elimination reaches a user
    before review, which is what makes the unreviewed library safe to ship behind."""

    capability: Capability = DEFAULT_CAPABILITY
    """Who can physically take this reading. `RC3`, and constraint 24 sets the direction of
    the default: an untagged check is a **technician** check, because mis-tagging a technician
    task as operator work puts an unqualified person on a pressurised circuit while the
    reverse merely wastes a callout."""

    source: str = ""
    """The file and heading this question was copied from.

    A discriminator that cannot name where it came from is indistinguishable from model
    output, and this content eliminates causes irreversibly — so provenance is a field rather
    than a comment. Empty only on questions constructed in tests."""

    def answer(self, key: str) -> Answer | None:
        return next((a for a in self.answers if a.key == key), None)

    @property
    def has_cannot_tell(self) -> bool:
        """Every question must offer one. A differential without it forces a guess."""
        return any(a.key == CANNOT_TELL for a in self.answers)

    def reach(self, live: frozenset[str]) -> int:
        """How many live causes this question could move.

        Constraint 39: the next question is the one that could move the most live
        candidates. A question whose every answer only *keeps* moves nothing, however
        cheap it is to ask.
        """
        movable: set[str] = set()
        for a in self.answers:
            movable |= {
                cause
                for cause, effect in a.effects.items()
                if cause in live and effect is not Effect.KEEP
            }
        return len(movable)


@dataclass(frozen=True)
class Cause:
    id: str
    text: str
    source: str = ""
    """Where this candidate was transcribed from. Same reasoning as `Question.source`: a
    cause nobody can trace is a cause nobody can review."""


@dataclass(frozen=True)
class Elimination:
    """`RC13`. Why a cause is gone — the check, the answer, and the question asked.

    *"Why did nobody look at the cooling tower?"* needs a better answer than *"the software
    decided"*, especially while the discriminators are unreviewed engineering judgement.
    """

    cause_id: str
    question_id: str
    question_text: str
    answer_key: str
    answer_text: str

    def render(self) -> str:
        return (
            f"{self.cause_id} was ruled out by {self.question_id} "
            f"(“{self.question_text}”) answered “{self.answer_text}”"
        )


@dataclass(frozen=True)
class Differential:
    """The candidate set for one undecidable class, and the questions that separate it."""

    fault_label: str
    causes: tuple[Cause, ...]
    questions: tuple[Question, ...]
    source: str = ""
    """The file and the fault-class heading the whole candidate set came from."""

    @property
    def askable(self) -> tuple[Question, ...]:
        """Only reviewed questions may be put to a person.

        Thirty-one causes were eliminated on the reference queue by discriminators nobody
        had read. Until the SME hour, this returns nothing and the differential reports
        `EXHAUSTED` — which is honest: with no reviewed question, we genuinely cannot
        separate the causes.
        """
        return tuple(q for q in self.questions if q.sme_reviewed)


@dataclass(frozen=True)
class DifferentialState:
    """Where a differential has got to. Immutable — each answer produces a new state."""

    differential: Differential
    live: frozenset[str]
    confirmed: frozenset[str] = frozenset()
    eliminations: tuple[Elimination, ...] = ()
    asked: frozenset[str] = frozenset()

    @property
    def outcome(self) -> Outcome:
        """`SETTLED` only when exactly one cause stands. Otherwise `EXHAUSTED` or `OPEN`.

        Note what does **not** settle it: a confirmation. Constraint 28 — a confirmed cause
        on a machine that also has a second real fault is still one of two.
        """
        if len(self.live) == 1:
            return Outcome.SETTLED
        if not self.remaining_questions:
            return Outcome.EXHAUSTED
        return Outcome.OPEN

    @property
    def remaining_questions(self) -> tuple[Question, ...]:
        """Reviewed, unasked, and still able to move something.

        A question that can no longer move any live cause is not "remaining" — offering it
        would send somebody to take a reading that changes nothing.
        """
        return tuple(
            q
            for q in self.differential.askable
            if q.id not in self.asked and q.reach(self.live) > 0
        )

    @property
    def next_question(self) -> Question | None:
        """Constraint 39: the one that could move the most live candidates.

        Ties break toward the lowest id so the sequence is reproducible — *"why was I asked
        this first?"* has to be answerable from the data, not from dict ordering.
        """
        candidates = self.remaining_questions
        if not candidates:
            return None
        return min(candidates, key=lambda q: (-q.reach(self.live), q.id))

    def render_outcome(self) -> str:
        if self.outcome is Outcome.SETTLED:
            only = next(iter(self.live))
            return (
                f"Settled on {only}. "
                f"{len(self.eliminations)} cause(s) were ruled out, each recording the "
                f"check and the answer that did it."
            )
        if self.outcome is Outcome.EXHAUSTED:
            if not self.differential.askable:
                return (
                    f"{len(self.live)} causes remain and there is no reviewed question to "
                    f"separate them. No discriminator in this library has been reviewed by "
                    f"a refrigeration engineer, so none is being put to anyone."
                )
            return (
                f"Exhausted, not settled: {len(self.live)} causes remain and the available "
                f"checks cannot separate them. That is a finding — it is not a conclusion "
                f"about whichever cause happens to be left."
            )
        return f"{len(self.live)} causes live, {len(self.remaining_questions)} question(s) left."


def start(differential: Differential) -> DifferentialState:
    return DifferentialState(
        differential=differential, live=frozenset(c.id for c in differential.causes)
    )


def apply(state: DifferentialState, question_id: str, answer_key: str) -> DifferentialState:
    """Apply one answer. Returns a new state; never mutates.

    Immutability is the mechanism behind constraint 29: there is no method that puts an
    eliminated cause back, because a state carrying its own history cannot be edited into
    one that never eliminated it.
    """
    question = next((q for q in state.differential.askable if q.id == question_id), None)
    if question is None:
        return state

    answer = question.answer(answer_key)
    if answer is None:
        return state

    # Constraint 30. `cannot_tell` marks the question asked so it is not offered again, and
    # changes nothing else — no elimination, no confirmation, no narrowing.
    if answer_key == CANNOT_TELL or not answer.effects:
        return DifferentialState(
            differential=state.differential,
            live=state.live,
            confirmed=state.confirmed,
            eliminations=state.eliminations,
            asked=state.asked | {question_id},
        )

    eliminated = {
        cause
        for cause, effect in answer.effects.items()
        if effect is Effect.ELIMINATE and cause in state.live
    }
    confirmed = {
        cause
        for cause, effect in answer.effects.items()
        if effect is Effect.CONFIRM and cause in state.live
    }

    return DifferentialState(
        differential=state.differential,
        # Only ELIMINATE removes a cause. A CONFIRM adds to `confirmed` and leaves every
        # sibling live — constraint 28, because a fouled condenser on a machine that is also
        # low on flow is two real causes.
        live=state.live - eliminated,
        confirmed=state.confirmed | confirmed,
        eliminations=state.eliminations
        + tuple(
            Elimination(
                cause_id=cause,
                question_id=question.id,
                question_text=question.text,
                answer_key=answer.key,
                answer_text=answer.text,
            )
            for cause in sorted(eliminated)
        ),
        asked=state.asked | {question_id},
    )


def has_differential(fault_label: str) -> bool:
    """Constraint 27: only a class the model itself declares undecidable gets one."""
    fault = faults.by_label(fault_label)
    return bool(fault and fault.declares_undecidable)


#: The authored candidate sets, by fault label. Filled from
#: `app/domain/library/differentials.py` by the import at the foot of this module.
#:
#: **The content is here; none of it is askable, and both halves of that are deliberate.**
#: The four differentials, 19 candidate causes and 19 discriminating questions are transcribed
#: verbatim from the review pack, with every question carrying the file and heading it came
#: from — because a discriminator that cannot name its source is indistinguishable from model
#: output. Every one of the 19 is `sme_reviewed=False`, so `askable` returns nothing, each
#: differential reports `EXHAUSTED`, and no elimination can reach a user. Thirty-one causes
#: were eliminated on the reference queue by these same discriminators, none of them read by a
#: refrigeration engineer; holding the content while refusing to ask it is what keeps that
#: from happening again here.
#:
#: **Not `is_sample`.** A sample *checklist item* is invented to demonstrate a mechanism and
#: wastes a walk to the machine. This is the real library awaiting review, and an illustrative
#: discriminator would rule a real cause out for ever. Different facts, different flags.
DIFFERENTIALS: dict[str, Differential] = {}


def differential_for(fault_label: str) -> Differential | None:
    """The authored candidate set for a class, or `None` when none has been authored.

    `None` here means **missing content**, never *"this class has no ambiguity"* — those are
    different facts and the caller must say which it is reporting. `has_differential` answers
    the second question; this one answers the first.
    """
    return DIFFERENTIALS.get(fault_label)


# The transcribed content, imported for one side effect: it fills `DIFFERENTIALS` above.
#
# **The import sits at the foot of the file, and that is structural rather than untidy.** The
# content is written in terms of the types defined here, so it must import upwards; the
# registry the rest of the code reads lives here too. Importing the module without touching a
# name on it is the only wiring that survives either import order — reaching for
# `differentials.LIBRARY` from this side would fail for anyone who imports the content module
# first, which the tests do.
from app.domain.library import differentials as _transcribed  # noqa: E402, F401
