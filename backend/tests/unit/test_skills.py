"""The skill dispatch — the end of the five-skill fall-through.

`SESSION-HANDOFF.md` §8 said since M1 that *five of seven skills route correctly then fall
into the same explain path*. The router was never the problem: it resolved the skill, carried
it into the route frame, and the turn ignored it. **A router whose decision changes nothing
only looks like a router**, and these tests are what makes the decision load-bearing.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.agents import skills
from app.analytics.bands import ResidualBand
from app.analytics.gates import Gate, GateOutcome, GateResult, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.domain.answer import AnswerState
from app.services.evidence import build_pack, window_for

DAY = date(2026, 4, 15)
MEASURED_END = datetime(2026, 6, 23, 11, 50)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(label: str | None = "CONDENSER_LOW_FLOW", *, blind: bool = False, others=()):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = (ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), label or "", values),)
    gates = (
        GateOutcome(
            (GateResult(Gate.RUNNING, passed=False, reason="no readings", remedy="check feed"),)
        )
        if blind
        else GateOutcome((check_running({"a": 141.0}),))
    )
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=gates,
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
        other_labels_same_day=others,
    )


# ── the dispatch is a table, not a chain ──────────────────────────────────────

def test_explain_is_the_only_skill_that_falls_through_to_the_model() -> None:
    """`explain` is the model's job — the rest are deterministic and must not spend one."""
    assert skills.dispatch("explain", _pack()) is None
    assert skills.dispatch("converse", _pack()) is None


@pytest.mark.parametrize("skill", sorted(skills.DETERMINISTIC_SKILLS))
def test_every_registered_skill_produces_a_terminal_outcome(skill: str) -> None:
    """A skill that is routed but not dispatched is a silent fall-through, which is exactly
    how five skills went a whole milestone without one. The table makes it a visible key."""
    outcome = skills.dispatch(skill, _pack())
    assert outcome is not None
    assert outcome.is_terminal
    assert outcome.text.strip()


@pytest.mark.parametrize("skill", sorted(skills.DETERMINISTIC_SKILLS))
def test_no_deterministic_skill_spends_a_model(skill: str) -> None:
    """Four of these need no model, and `verify` refuses without one. Spending a model to
    read a number back is where a number gets rounded — `C21`."""
    assert skills.dispatch(skill, _pack()).used_model is False


# ── look_up: the figures, exactly ─────────────────────────────────────────────

def test_look_up_never_reformats_a_figure() -> None:
    """The pack carries display strings rather than floats so the numeric audit can compare
    exact values. Re-rendering would reintroduce a tolerance, and every tolerance forgives
    some fabrication."""
    pack = _pack()
    outcome = skills.look_up(pack)
    for evidence in pack.residual_evidence:
        assert evidence.render() in outcome.text


def test_look_up_counts_the_absences_rather_than_hiding_them() -> None:
    """Five of six residuals are absent on this plant — the sixth model is unfitted and most
    columns are NULL. A look-up that listed only the values present would read as a full set."""
    outcome = skills.look_up(_pack())
    assert "stated absence rather than a value" in outcome.text
    assert "An absence is not a zero" in outcome.text


# ── investigate: the two facts a single-label answer hides ────────────────────

def test_investigate_names_the_other_labels_on_the_same_day() -> None:
    """On 2026-04-15 chiller 1 carried five labels at once. One repair may explain several,
    and a reader who does not know that raises several jobs."""
    outcome = skills.investigate(_pack(others=("HIGH_HEAD_AMBIGUOUS", "POWER_HIGH_UNEXPLAINED")))
    assert "2 other label(s)" in outcome.text
    assert "raises several jobs" in outcome.text


def test_investigate_says_a_determinate_class_gets_no_differential() -> None:
    """Constraint 27 — narrowing a class that already names a mechanism would invent
    ambiguity the trained model never reported."""
    outcome = skills.investigate(_pack("CONDENSER_LOW_FLOW"))
    assert "does not get a differential" in outcome.text


def test_investigate_separates_missing_content_from_no_ambiguity() -> None:
    """The two must never look alike: one says *we have not written it*, the other says
    *there is nothing to investigate*, and only one of them means stop looking.

    `HIGH_HEAD_AMBIGUOUS` is now authored, so it reports the third state — narrowable once
    reviewed. `REFRIGERANT_SIDE_HIGH_HEAD` is the live *qualifies-but-unauthored* case: it
    names a region, probes five mechanisms and deliberately has no differential (`Q37`)."""
    authored = skills.investigate(_pack("HIGH_HEAD_AMBIGUOUS"))
    assert authored.payload["qualifies_for_differential"] is True
    assert authored.payload["differential_authored"] is True
    assert "once the discriminators have been reviewed" in authored.text

    determinate = skills.investigate(_pack("CONDENSER_LOW_FLOW"))
    assert determinate.payload["qualifies_for_differential"] is False
    assert "does not get a differential" in determinate.text


# ── prepare_work: a draft that says it is a draft ─────────────────────────────

def test_prepare_work_needs_approval_rather_than_answering() -> None:
    """A work order that reads as dispatchable when nothing is persisted and nobody approved
    it is worse than none, because somebody plans against it."""
    outcome = skills.prepare_work(_pack())
    assert outcome.state is AnswerState.NEEDS_APPROVAL
    assert "This is a draft" in outcome.text
    assert "Nothing is persisted" in outcome.text


def test_prepare_work_states_what_the_priority_could_not_use() -> None:
    """`W4`/`Q51`: three of four inputs do not exist in this snapshot. A formula that silently
    dropped them would produce a severity wearing a rank, which a planner would schedule
    against."""
    outcome = skills.prepare_work(_pack())
    assert "priority is incomplete" in outcome.text


# ── resolve: the common outcome is a pause ────────────────────────────────────

def test_resolve_blocks_rather_than_concluding() -> None:
    """26 of 43 measured cases stop at the checks. The pause is the feature — only a measured
    reading settles a blocking item."""
    outcome = skills.resolve(_pack())
    assert outcome.state is AnswerState.BLOCKED
    assert outcome.text.strip()


def test_resolve_says_the_checklist_content_is_sample() -> None:
    """Nothing in the 124-item library has been reviewed, so no real item reaches anyone."""
    assert "sample content" in skills.resolve(_pack()).text


# ── verify: refuses rather than guessing ──────────────────────────────────────

def test_verify_refuses_without_an_after_window() -> None:
    """`V1` found this in live data: a class disappeared after 2026-04-22 and never returned,
    which looks exactly like a repair — while the residual got *worse*, because the gates had
    stopped passing and nothing was being judged at all."""
    outcome = skills.verify(_pack())
    assert outcome.state is AnswerState.BLOCKED
    assert "is not evidence that a repair worked" in outcome.text


# ── a skill failure is a state, not a crash ───────────────────────────────────

def test_a_failing_skill_becomes_an_answer_state() -> None:
    """The router's rule — no layer may raise — one layer along. A stack trace is not an
    answer, and on a demonstration it reads as a broken product."""

    def _boom(pack):
        raise RuntimeError("the service went away")

    skills.DETERMINISTIC_SKILLS["_boom"] = _boom
    try:
        outcome = skills.dispatch("_boom", _pack())
        assert outcome.state is AnswerState.FAILED
        assert "the service went away" in outcome.text
        assert "Nothing was assumed in its place" in outcome.text
    finally:
        del skills.DETERMINISTIC_SKILLS["_boom"]


def test_an_unknown_skill_falls_through_rather_than_failing() -> None:
    """An unrecognised skill is not an error — it is a skill the model handles."""
    assert skills.dispatch("something_new", _pack()) is None
