"""`RC12`, `RC13`, `RC14` — narrowing, the audit, and exhausted-is-not-settled.

Every test here corresponds to a constraint with a real failure behind it. The three that
matter most, because each is a way a wrong answer becomes permanent:

- **A confirmation must not eliminate its siblings** (28). A fouled condenser on a machine
  also low on flow is two real causes.
- **"Can't tell" must change nothing** (30). Otherwise uncertainty silently rules something
  out, and nobody re-examines a settled question.
- **Exhausted is not settled** (32). Running out of checks establishes *"we cannot separate
  these"* — reporting that as a conclusion on whichever cause is left is the failure.
"""
from __future__ import annotations

from app.domain.differential import (
    CANNOT_TELL,
    Answer,
    Cause,
    Differential,
    Effect,
    Outcome,
    Question,
    apply,
    has_differential,
    start,
)

CAUSES = (
    Cause("fouling", "condenser fouling"),
    Cause("low_flow", "low condenser water flow"),
    Cause("air", "non-condensables"),
)


def _q(qid: str, *, effects: dict[str, Effect], reviewed: bool = True, text: str = "") -> Question:
    return Question(
        id=qid,
        text=text or f"question {qid}",
        sme_reviewed=reviewed,
        answers=(
            Answer("yes", "yes", effects),
            Answer("no", "no", {}),
            Answer(CANNOT_TELL, "can't tell", {}),
        ),
    )


def _diff(*questions: Question) -> Differential:
    return Differential("HIGH_HEAD_AMBIGUOUS", CAUSES, questions)


# ── constraint 27: only an undecidable class gets one ──────────────────────────

def test_only_a_class_that_declares_itself_undecidable_gets_a_differential() -> None:
    """Narrowing a class that already names a mechanism invents ambiguity the model never
    reported."""
    assert has_differential("HIGH_HEAD_AMBIGUOUS")
    assert has_differential("POWER_HIGH_UNEXPLAINED")
    assert not has_differential("CONDENSER_LOW_FLOW")
    assert not has_differential("COMPRESSOR_INEFFICIENCY")


# ── constraint 28: a confirmation never eliminates siblings ────────────────────

def test_confirming_one_cause_leaves_every_sibling_live() -> None:
    """A fouled condenser on a machine that is also low on flow is two real causes, and
    collapsing to the first confirmation is how the second gets missed."""
    state = start(_diff(_q("q1", effects={"fouling": Effect.CONFIRM})))
    after = apply(state, "q1", "yes")

    assert "fouling" in after.confirmed
    assert after.live == {"fouling", "low_flow", "air"}, "no sibling may be removed"
    assert after.eliminations == ()


def test_a_confirmation_alone_does_not_settle_the_differential() -> None:
    state = start(_diff(_q("q1", effects={"fouling": Effect.CONFIRM})))
    assert apply(state, "q1", "yes").outcome is not Outcome.SETTLED


# ── constraint 30: can't tell must change nothing ──────────────────────────────

def test_cannot_tell_has_no_effect_at_all() -> None:
    """Not merely ignored — asserted. A question whose "don't know" quietly eliminated
    something would be worse than no question."""
    state = start(_diff(_q("q1", effects={"fouling": Effect.ELIMINATE, "air": Effect.CONFIRM})))
    after = apply(state, "q1", CANNOT_TELL)

    assert after.live == state.live
    assert after.confirmed == state.confirmed
    assert after.eliminations == ()


def test_cannot_tell_still_marks_the_question_asked() -> None:
    """It changes nothing about the causes, but re-offering a question somebody could not
    answer is how a differential loops."""
    state = start(_diff(_q("q1", effects={"fouling": Effect.ELIMINATE})))
    after = apply(state, "q1", CANNOT_TELL)
    assert "q1" in after.asked
    assert after.next_question is None


def test_every_question_offers_a_cannot_tell() -> None:
    """A differential without it forces a guess, and a guessed answer eliminates for real."""
    assert _q("q1", effects={"fouling": Effect.ELIMINATE}).has_cannot_tell


# ── constraint 29: elimination is final ────────────────────────────────────────

def test_an_eliminated_cause_never_returns() -> None:
    """No method puts one back. A state carrying its own history cannot be edited into one
    that never eliminated it."""
    d = _diff(
        _q("q1", effects={"fouling": Effect.ELIMINATE}),
        _q("q2", effects={"fouling": Effect.CONFIRM, "air": Effect.ELIMINATE}),
    )
    after = apply(apply(start(d), "q1", "yes"), "q2", "yes")
    assert "fouling" not in after.live, "a later confirm must not resurrect it"
    assert "air" not in after.live


def test_applying_an_answer_returns_a_new_state() -> None:
    state = start(_diff(_q("q1", effects={"fouling": Effect.ELIMINATE})))
    after = apply(state, "q1", "yes")
    assert after is not state
    assert state.live == {"fouling", "low_flow", "air"}, "the original is untouched"


# ── constraint 31: every elimination records why ───────────────────────────────

def test_an_elimination_records_the_check_and_the_answer() -> None:
    """"Why did nobody look at the cooling tower?" needs a better answer than "the software
    decided" — especially while the discriminators are unreviewed."""
    d = _diff(_q("q1", effects={"low_flow": Effect.ELIMINATE}, text="is flow at design?"))
    after = apply(start(d), "q1", "yes")

    assert len(after.eliminations) == 1
    e = after.eliminations[0]
    assert e.cause_id == "low_flow"
    assert e.question_id == "q1"
    assert e.question_text == "is flow at design?"
    assert e.answer_text == "yes"
    assert "is flow at design?" in e.render()


# ── constraint 32: exhausted is not settled ────────────────────────────────────

def test_running_out_of_questions_is_exhausted_not_settled() -> None:
    """Two causes and no checks left establishes "we cannot separate these" — a different
    statement from a conclusion about whichever is left."""
    d = _diff(_q("q1", effects={"fouling": Effect.ELIMINATE}))
    after = apply(start(d), "q1", "yes")

    assert after.outcome is Outcome.EXHAUSTED
    assert len(after.live) == 2
    assert "not settled" in after.render_outcome()


def test_one_cause_standing_is_settled() -> None:
    d = _diff(
        _q("q1", effects={"fouling": Effect.ELIMINATE}),
        _q("q2", effects={"air": Effect.ELIMINATE}),
    )
    after = apply(apply(start(d), "q1", "yes"), "q2", "yes")
    assert after.outcome is Outcome.SETTLED
    assert after.live == {"low_flow"}
    assert "Settled on low_flow" in after.render_outcome()


# ── the SME gate ───────────────────────────────────────────────────────────────

def test_an_unreviewed_question_is_never_asked() -> None:
    """Thirty-one causes were eliminated on the reference queue by discriminators nobody had
    read. Until review, this differential asks nothing."""
    d = _diff(_q("q1", effects={"fouling": Effect.ELIMINATE}, reviewed=False))
    state = start(d)
    assert state.next_question is None
    assert state.outcome is Outcome.EXHAUSTED
    assert "no reviewed question" in state.render_outcome()


def test_an_unreviewed_question_cannot_eliminate_even_if_answered() -> None:
    """The gate is on `apply`, not only on display — an answer posted directly must not
    slip past it."""
    d = _diff(_q("q1", effects={"fouling": Effect.ELIMINATE}, reviewed=False))
    after = apply(start(d), "q1", "yes")
    assert after.live == {"fouling", "low_flow", "air"}
    assert after.eliminations == ()


# ── constraint 39: which question comes next ───────────────────────────────────

def test_the_next_question_is_the_one_that_moves_the_most_causes() -> None:
    """On the weakest class the opener can settle the whole thing alone, so asking the
    narrow question first wastes a visit."""
    d = _diff(
        _q("narrow", effects={"air": Effect.ELIMINATE}),
        _q("broad", effects={"fouling": Effect.ELIMINATE, "low_flow": Effect.ELIMINATE}),
    )
    assert start(d).next_question.id == "broad"


def test_a_question_that_can_move_nothing_is_not_offered() -> None:
    """Offering it would send somebody to take a reading that changes nothing."""
    d = _diff(
        _q("q1", effects={"fouling": Effect.ELIMINATE}),
        _q("q2", effects={"fouling": Effect.ELIMINATE}),
    )
    after = apply(start(d), "q1", "yes")
    assert after.remaining_questions == ()


def test_question_order_is_reproducible() -> None:
    """"Why was I asked this first?" must be answerable from the data, not dict ordering."""
    d = _diff(
        _q("b", effects={"fouling": Effect.ELIMINATE}),
        _q("a", effects={"low_flow": Effect.ELIMINATE}),
    )
    assert {start(d).next_question.id for _ in range(20)} == {"a"}


# ── nothing here reaches a model ───────────────────────────────────────────────

def test_the_differential_never_calls_a_model() -> None:
    """`RC12` and `RC14` are R — rules. The language model decides what to ask; it never
    decides whether to ask, and never what an answer eliminates."""
    import pathlib

    from app.domain import differential

    code = " ".join(
        line
        for line in pathlib.Path(differential.__file__).read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    for banned in ("app.llm", "ModelClient", "import openai", "langchain"):
        assert banned not in code
