"""`C15` turn memory.

What was here before was a single `last_equipment` string — carry-forward, not memory.
`SESSION-HANDOFF.md` §8 named it as the gap and said M1's count should honestly read 26 of 27
because of it. These tests are what makes the difference real rather than asserted.
"""
from __future__ import annotations

from datetime import date

from app.agents.memory import (
    MAX_REMEMBERED_TURNS,
    ResolvedContext,
    TurnMemory,
)

DAY = date(2026, 4, 15)
BOTH = ("chiller_1", "chiller_2")


def _memory_about(equipment: str = "chiller_1", **kw) -> TurnMemory:
    return TurnMemory().remember(
        question="why was this flagged?",
        skill="explain",
        answer_state="ANSWERED",
        context=ResolvedContext(equipment_key=equipment, **kw),
        equipment_offered=BOTH,
    )


# ── it is memory, not carry-forward ────────────────────────────────────────────

def test_a_new_conversation_resolves_nothing_and_says_so() -> None:
    """An empty memory that answered anyway would be inventing a subject."""
    context, reason = TurnMemory().resolve("why was this flagged?")
    assert context.is_empty
    assert "nothing has been established yet" in reason


def test_a_question_that_names_its_own_subject_inherits_nothing() -> None:
    """The failure this prevents: a question about chiller 2 quietly answered about chiller 1
    because chiller 1 was mentioned six turns ago."""
    context, reason = _memory_about("chiller_1").resolve("how is chiller_2 doing?")
    assert context.is_empty
    assert "names its own subject" in reason


def test_more_than_the_equipment_is_remembered() -> None:
    """The whole point. Carry-forward held one noun; a case needs the label and the day too,
    because *"why was this flagged"* with an equipment and no day answers about the wrong
    afternoon."""
    memory = _memory_about(fault_label="CONDENSER_LOW_FLOW", day=DAY)
    context, _ = memory.resolve("and what did that mean?")

    assert context.equipment_key == "chiller_1"
    assert context.fault_label == "CONDENSER_LOW_FLOW"
    assert context.day == DAY


def test_a_new_fault_on_the_same_machine_does_not_clear_the_machine() -> None:
    """Field-wise merge, not wholesale replacement."""
    memory = _memory_about(fault_label="CONDENSER_LOW_FLOW", day=DAY).remember(
        question="what about the ambiguous one?",
        skill="explain",
        answer_state="ANSWERED",
        context=ResolvedContext(fault_label="HIGH_HEAD_AMBIGUOUS"),
    )
    assert memory.context.equipment_key == "chiller_1"
    assert memory.context.fault_label == "HIGH_HEAD_AMBIGUOUS"
    assert memory.context.day == DAY


# ── "the other one" ────────────────────────────────────────────────────────────

def test_the_other_one_resolves_when_the_set_has_exactly_two() -> None:
    """The site runs two chillers, so this is the common case rather than an edge one."""
    context, reason = _memory_about("chiller_1").resolve("what about the other one?", BOTH)
    assert context.equipment_key == "chiller_2"
    assert "resolved to chiller_2" in reason


def test_switching_machines_drops_the_fault_and_the_day() -> None:
    """Models are fitted per asset. Carrying chiller 1's fault label onto chiller 2 would
    assert a fault the second machine may not have — and 0.0 is HIGH on one and NORMAL on the
    other, so nothing about one transfers."""
    memory = _memory_about(fault_label="CONDENSER_LOW_FLOW", day=DAY)
    context, _ = memory.resolve("and the other one?", BOTH)

    assert context.equipment_key == "chiller_2"
    assert context.fault_label is None
    assert context.day is None


def test_the_other_one_is_refused_when_ambiguous() -> None:
    """Three assets in scope and no way to know which. Guessing would be a confident wrong
    answer about a machine nobody asked about."""
    memory = _memory_about("chiller_1")
    context, reason = memory.resolve(
        "the other one?", ("chiller_1", "chiller_2", "chiller_3")
    )
    assert context.equipment_key == "chiller_1", "unchanged — nothing was assumed"
    assert "ambiguous" in reason


def test_the_other_one_with_no_alternative_says_so() -> None:
    _, reason = _memory_about("chiller_1").resolve("the other one?", ("chiller_1",))
    assert "no referent" in reason


# ── bounded, and the bound is invisible ────────────────────────────────────────

def test_memory_is_bounded_by_turn_count() -> None:
    """An unbounded transcript grows until it exceeds `max_context_chars` and then fails on a
    turn nobody can predict — the worst possible place to discover a ceiling."""
    memory = TurnMemory()
    for i in range(MAX_REMEMBERED_TURNS + 4):
        memory = memory.remember(
            question=f"question {i}", skill="explain", answer_state="ANSWERED"
        )
    assert memory.depth == MAX_REMEMBERED_TURNS


def test_dropping_an_old_turn_never_drops_the_resolved_context() -> None:
    """Forgetting the wording of turn one must not forget which machine it established. A
    conversation that lost its subject after six turns would be worse than one with no memory,
    because the loss is invisible."""
    memory = _memory_about("chiller_1", fault_label="CONDENSER_LOW_FLOW")
    for i in range(MAX_REMEMBERED_TURNS + 3):
        memory = memory.remember(
            question=f"follow-up {i}", skill="explain", answer_state="ANSWERED"
        )

    assert memory.depth == MAX_REMEMBERED_TURNS
    assert memory.context.equipment_key == "chiller_1"
    assert memory.context.fault_label == "CONDENSER_LOW_FLOW"


# ── memory never becomes an authorisation ──────────────────────────────────────

def test_forget_clears_everything() -> None:
    """A persona switch must not carry one person's context into another's. `G1` recomputes
    scope every turn and never inherits it; memory must not be the thing that leaks around
    that."""
    memory = _memory_about("chiller_1", fault_label="CONDENSER_LOW_FLOW", day=DAY)
    cleared = memory.forget()

    assert cleared.is_new_conversation
    assert cleared.context.is_empty


def test_memory_records_what_was_established_not_what_was_said() -> None:
    """Storing generated prose would let a model's own phrasing become the evidence for the
    next answer — the grounding failure, one turn removed."""
    memory = _memory_about("chiller_1")
    turn = memory.turns[-1]

    assert not hasattr(turn, "answer")
    assert not hasattr(turn, "answer_text")
    assert turn.answer_state == "ANSWERED", "the outcome is kept; the prose is not"


# ── the resolution is inspectable ──────────────────────────────────────────────

def test_the_resolution_renders_what_this_became() -> None:
    """A resolution nobody can inspect is indistinguishable from a guess, and the route trace
    is where a reader checks it."""
    memory = _memory_about("chiller_1", fault_label="CONDENSER_LOW_FLOW", day=DAY)
    context, reason = memory.resolve("why was this flagged?")

    assert "chiller_1" in context.render()
    assert "CONDENSER_LOW_FLOW" in context.render()
    assert "2026-04-15" in context.render()
    assert "resolved from the conversation" in reason


def test_an_empty_context_renders_words_rather_than_a_dash() -> None:
    """An absence is not a zero and not a dash."""
    assert "nothing has been established" in ResolvedContext().render()
