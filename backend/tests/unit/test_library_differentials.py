"""The transcribed differentials: is the copy faithful, and is it still unaskable?

Two different jobs, and both matter. The first is arithmetic — `CONTEXT.md` §10b states the
scale of the reference queue, and a transcription that quietly drops a question or a cause
would be a smaller, more confident library than the one a refrigeration engineer is being
asked to read. The second is the gate: this content eliminates causes irreversibly, nothing
in it has been reviewed, and the tests below assert that **nothing can be asked** rather than
trusting a flag to stay `False`.

The constraint tests are the ones with a real failure behind them:

- **A confirmation must not eliminate its siblings** (28). Asserted over the real content by
  applying every answer in the library, not over a fixture.
- **"Can't tell" must change nothing** (30). Every question offered one in the source; every
  one is asserted to carry no effects at all.
- **Exhausted is not settled** (32). With nothing reviewed, every differential reports
  `EXHAUSTED` — the honest *"we cannot separate these"*, and the state that must hold until
  the SME hour.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import fields, replace

from app.domain import faults
from app.domain.cases import Capability
from app.domain.differential import (
    CANNOT_TELL,
    DIFFERENTIALS,
    Differential,
    Effect,
    Outcome,
    apply,
    start,
)
from app.domain.library.differentials import LIBRARY, SOURCE_FILE

QUESTIONS = [q for d in LIBRARY.values() for q in d.questions]
ANSWERS = [(q, a) for q in QUESTIONS for a in q.answers]


# ── the scale, against CONTEXT §10b ─────────────────────────────────────────────

def test_the_library_holds_four_differentials() -> None:
    """§10b: 4 differentials. Only the classes the trained model declares undecidable."""
    assert len(LIBRARY) == 4


def test_nineteen_candidate_causes_and_nineteen_questions() -> None:
    """§10b: 19 candidate causes · 19 discriminating questions.

    A dropped question is a library that looks more decisive than it is, and the reviewer
    would never know which line was missing.
    """
    assert sum(len(d.causes) for d in LIBRARY.values()) == 19
    assert len(QUESTIONS) == 19


def test_the_effect_count_is_what_the_source_tables_actually_carry() -> None:
    """§10b says *about 41 effects*; the tables carry **58**, of which 48 are not `keep`.

    The transcription is faithful to the source rather than to the estimate, and the gap is
    reported rather than closed — dropping 17 effects to hit a rounded figure in a document
    would be editing engineering content to match prose about it.
    """
    effects = [(cause, e) for _, a in ANSWERS for cause, e in a.effects.items()]
    assert len(effects) == 58
    assert sum(1 for _, e in effects if e is not Effect.KEEP) == 48


def test_only_a_class_that_declares_itself_undecidable_has_one() -> None:
    """Constraint 27. Narrowing a class that already names a mechanism would invent
    ambiguity the model never reported."""
    assert set(LIBRARY) == set(faults.undecidable_labels())


def test_the_refrigerant_side_hole_is_left_open() -> None:
    """`Q37`, preserved rather than fixed. `REFRIGERANT_SIDE_HIGH_HEAD` names a region and
    carries no blocking item, so a case can conclude there with no evidence. Authoring a
    differential to close that gap would be the unreviewed judgement this library avoids."""
    assert "REFRIGERANT_SIDE_HIGH_HEAD" not in LIBRARY


# ── constraint 30: every question carries a "can't tell" that moves nothing ─────

def test_every_question_offers_a_cannot_tell_with_no_effects() -> None:
    """All 19 offered one in the source, so none was added here. Its absence would let
    uncertainty silently eliminate a cause, which nobody would ever re-open."""
    for q in QUESTIONS:
        assert q.has_cannot_tell, f"{q.id} has no can't-tell"
        assert q.answer(CANNOT_TELL).effects == {}, f"{q.id}'s can't-tell moves something"


def test_no_other_answer_is_silently_empty() -> None:
    """A transcribed answer with an empty effect row would be a table copied wrongly, and it
    would read as a question worth asking that can settle nothing."""
    for q, a in ANSWERS:
        if a.key != CANNOT_TELL:
            assert a.effects, f"{q.id}/{a.key} carries no effects"


# ── constraint 28: a confirmation never eliminates a sibling ────────────────────

def test_no_confirmation_removes_a_sibling() -> None:
    """Applied over the real content, one answer at a time.

    A fouled condenser on a machine that is *also* low on flow is two real causes. The one
    answer in the library that confirms and eliminates in the same row —
    `POWER_HIGH_UNEXPLAINED.Q1`, four eliminations at once — is the source's own table, and
    the reviewer is asked about it explicitly. This test proves the eliminations are written
    down rather than produced by the confirmation.
    """
    for label, d in LIBRARY.items():
        for q in d.questions:
            reviewed = Differential(
                fault_label=d.fault_label,
                causes=d.causes,
                questions=(replace(q, sme_reviewed=True),),
                source=d.source,
            )
            for a in q.answers:
                after = apply(start(reviewed), q.id, a.key)
                removed = {c.id for c in d.causes} - after.live
                spelt_out = {c for c, e in a.effects.items() if e is Effect.ELIMINATE}

                assert removed == spelt_out, f"{label}/{q.id}/{a.key} removed {removed}"
                for confirmed in (c for c, e in a.effects.items() if e is Effect.CONFIRM):
                    assert confirmed in after.live, "a confirmation must not remove anything"


def test_every_question_could_move_something() -> None:
    """A question whose every answer only *keeps* sends somebody to take a reading that
    changes nothing. `Question.reach` drops those from the queue; none was transcribed."""
    for d in LIBRARY.values():
        live = frozenset(c.id for c in d.causes)
        for q in d.questions:
            assert q.reach(live) > 0, q.id


# ── constraint 31: an elimination has to be traceable to a source line ──────────

def test_every_effect_names_a_cause_that_exists_in_its_differential() -> None:
    """The typo test, and it is not cosmetic: an effect naming a cause id that does not exist
    is an elimination the source wrote and this library silently does not perform."""
    for label, d in LIBRARY.items():
        ids = {c.id for c in d.causes}
        for q in d.questions:
            for a in q.answers:
                unknown = set(a.effects) - ids
                assert not unknown, f"{label}/{q.id}/{a.key} names {unknown}"


def test_ids_and_answer_keys_are_unique() -> None:
    for label, d in LIBRARY.items():
        assert len({c.id for c in d.causes}) == len(d.causes), label
        assert len({q.id for q in d.questions}) == len(d.questions), label
    for q in QUESTIONS:
        assert len({a.key for a in q.answers}) == len(q.answers), q.id


def test_every_transcribed_object_names_where_it_came_from() -> None:
    """A curated item that cannot name its source is indistinguishable from model output —
    and constraint 1 is that this library is curated content, never model output."""
    for d in LIBRARY.values():
        assert d.source.startswith(SOURCE_FILE)
        for c in d.causes:
            assert c.source.startswith(SOURCE_FILE), c.id
        for q in d.questions:
            assert q.source.startswith(SOURCE_FILE), q.id
            assert d.fault_label in q.id, "the audit line must name the check"


# ── constraint 24: the role tag, and where it came from ─────────────────────────

def test_every_question_carries_the_role_tag_the_source_gave_it() -> None:
    """All 19 headings were tagged, so the technician default never fired here.

    Constraint 24's asymmetry is why that matters: mis-tagging a technician task as operator
    work puts an unqualified person on a pressurised circuit. A guessed tag is worse than a
    defaulted one, and neither was needed.
    """
    tally = Counter(q.capability for q in QUESTIONS)
    assert tally == {
        Capability.TECHNICIAN: 12,
        Capability.OPERATOR: 6,
        Capability.SUPERVISOR: 1,
    }


def test_at_least_one_question_can_be_answered_without_tools() -> None:
    """Constraint 37's shape, applied to narrowing: on the electrical class the operator's
    panel reading is the opener, and a differential nobody present can start is one that
    stalls at the first question."""
    for label, d in LIBRARY.items():
        assert any(q.capability is Capability.OPERATOR for q in d.questions), label


# ── the SME gate: transcribed, and unaskable ────────────────────────────────────

def test_not_one_question_is_marked_reviewed() -> None:
    """No refrigeration engineer has read any of this. The flag is the whole gate."""
    assert not [q.id for q in QUESTIONS if q.sme_reviewed]


def test_every_differential_reports_exhausted_because_nothing_is_reviewed() -> None:
    """Constraint 32, and the state that must hold until the SME hour: with no reviewed
    question there is genuinely nothing that separates these causes, and saying so is a
    finding rather than a conclusion about whichever cause happens to remain."""
    for label, d in LIBRARY.items():
        state = start(d)
        assert d.askable == (), label
        assert state.next_question is None, label
        assert state.outcome is Outcome.EXHAUSTED, label
        assert "no reviewed question" in state.render_outcome()


def test_answering_a_transcribed_question_directly_still_eliminates_nothing() -> None:
    """The gate is on `apply`, not only on display. Thirty-one causes were eliminated on the
    reference queue by discriminators nobody had read; posting an answer straight at this
    library must not add to that count."""
    for d in LIBRARY.values():
        state = start(d)
        for q in d.questions:
            for a in q.answers:
                after = apply(state, q.id, a.key)
                assert after.live == state.live
                assert after.eliminations == ()


# ── the registry the rest of the code reads ─────────────────────────────────────

def test_the_domain_registry_is_populated_from_this_library() -> None:
    """`DIFFERENTIALS` was empty on purpose while the content was untranscribed. It is filled
    now, and safely — because the content arrives unreviewed and therefore unaskable, not
    because the risk went away."""
    assert DIFFERENTIALS == LIBRARY


def test_the_content_is_not_marked_as_sample() -> None:
    """`is_sample` means *invented to demonstrate the mechanism*, and this is the real library
    awaiting review. The two facts stay apart: a question has no such flag to set, so the only
    thing standing between this content and a user is `sme_reviewed`, which is `False`."""
    assert "is_sample" not in {f.name for f in fields(QUESTIONS[0])}
