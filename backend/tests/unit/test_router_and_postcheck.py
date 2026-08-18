"""The routing ladder and the honesty audits — both with the GPU off.

Two claims are tested here, and both are architectural rather than incidental.

**Routing is deterministic.** Fixed messages route the same way every time, at a named
layer, with no model involved. That makes routing a unit test rather than an evaluation, and
it is why the cheap layers stay even though a model is right there.

**The honesty layer overrides the model.** The audits are fed answers that deliberately
invent a number, name a machine that does not exist, quote `cond_flow` as a reading, omit
the window, diagnose on their own authority, and hide a poor fit. Each must be caught. That
is `EV4`, and it needs no GPU — which is the whole reason it is in M1 rather than last.

The sibling's honesty layer shipped a reassuring lie that 56 unit tests, a clean typecheck
and a 100% evaluation score all missed. These tests exist because *those* tests existed.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.agents.postcheck import (
    AuditSeverity,
    correction_for,
    run_audits,
)
from app.agents.router import RouteDecision, Skill, reconcile_equipment, route
from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.services.evidence import build_pack, window_for

MEASURED_END = datetime(2026, 6, 23, 11, 50)
DAY = date(2026, 4, 15)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(label: str = "HIGH_HEAD_AMBIGUOUS", current: float = -20.0):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = current
    rows = (ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), label, values),)
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=GateOutcome((check_running({"a": 141.0}),)),
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
    )


# ════════════════════════════════════════════════════════════════════════════════
# The routing ladder
# ════════════════════════════════════════════════════════════════════════════════

def test_the_router_never_raises() -> None:
    """A router that throws turns a mistyped question into a stack trace.

    Empty strings, control characters, very long input, and an arbiter that explodes — all
    must produce a decision.
    """
    for message in ("", "   ", "\x00\x01", "?" * 5000, "🙂", "SELECT * FROM users"):
        decision = route(message)
        assert isinstance(decision, RouteDecision)
        assert decision.skill in set(Skill)


def test_an_arbiter_that_explodes_does_not_break_routing() -> None:
    def broken(_message: str) -> str:
        raise RuntimeError("the box is down")

    decision = route("something ambiguous about the chiller", arbiter=broken)
    assert isinstance(decision, RouteDecision)
    assert not decision.used_model


# ── layer 0 ─────────────────────────────────────────────────────────────────────

def test_a_mode_chip_outranks_every_heuristic() -> None:
    decision = route("why is chiller 1 running hot", mode_override="look_up")
    assert decision.skill is Skill.LOOK_UP
    assert decision.layer.startswith("0")


def test_an_unknown_mode_chip_degrades_into_the_ladder() -> None:
    """It does not fail. A stale chip in a cached page is not the user's problem."""
    decision = route("why is chiller 1 running hot", mode_override="teleport")
    assert decision.skill is Skill.EXPLAIN


# ── layer 1: the deterministic refusals ─────────────────────────────────────────

@pytest.mark.parametrize(
    "message",
    ["turn off chiller 1", "restart the compressor", "change the setpoint to 6 degrees"],
)
def test_a_control_command_is_refused_before_any_inference(message: str) -> None:
    """Agents are read-only with respect to hardware, in every phase. `CONTEXT.md` §13."""
    decision = route(message)
    assert decision.skill is Skill.REFUSE
    assert decision.layer.startswith("1 ")
    assert "read-only" in decision.refusal_text
    assert not decision.used_model


@pytest.mark.parametrize("message", ["will it fail next week", "predict chiller 2 power"])
def test_a_prediction_request_is_refused(message: str) -> None:
    """This is a snapshot, not a forecast. A number presented as a prediction is a guess
    wearing a unit."""
    decision = route(message)
    assert decision.skill is Skill.REFUSE
    assert "does not forecast" in decision.refusal_text


# ── layer 1.5: the fast path ────────────────────────────────────────────────────

@pytest.mark.parametrize("message", ["hi", "Hello!", "hey", "thanks", "good morning"])
def test_a_greeting_never_meets_the_cold_refusal(message: str) -> None:
    """A greeting has no equipment and no domain term, so the scope gate would refuse it.

    That is the single worst first impression the product can make, and layer 1.5 exists
    ahead of the gate for exactly this. It costs one membership test.
    """
    decision = route(message)
    assert decision.skill is Skill.CONVERSE
    assert decision.layer.startswith("1.5")
    assert not decision.used_model


@pytest.mark.parametrize("message", ["what can you do", "help", "who are you"])
def test_a_capability_question_is_answered_without_touching_telemetry(message: str) -> None:
    assert route(message).skill is Skill.CONVERSE


# ── layer 2: extraction, and carrying the unit forward ──────────────────────────

@pytest.mark.parametrize(
    "message,expected",
    [
        ("why is chiller 1 running hot", "chiller_1"),
        ("explain chiller_2", "chiller_2"),
        ("what about ch2", "chiller_2"),
        ("Chiller 1 discharge pressure", "chiller_1"),
    ],
)
def test_equipment_is_extracted_deterministically(message: str, expected: str) -> None:
    assert route(message).equipment_key == expected


def test_the_last_mentioned_unit_carries_forward() -> None:
    """This is what makes *"and its ΔT?"* resolve. Deliberately narrow: only when the new
    message names none of its own."""
    assert route("and its delta T?", last_equipment="chiller_2").equipment_key == "chiller_2"


def test_a_named_unit_overrides_the_carried_one() -> None:
    decision = route("explain chiller 1", last_equipment="chiller_2")
    assert decision.equipment_key == "chiller_1"


# ── layer 3: keywords, ordered, first match wins ────────────────────────────────

@pytest.mark.parametrize(
    "message,expected",
    [
        ("why is chiller 1 in high head", Skill.EXPLAIN),
        ("did the repair work on chiller 1", Skill.VERIFY),
        ("raise a work order for chiller 2", Skill.PREPARE_WORK),
        ("what should i check on chiller 1", Skill.RESOLVE),
        ("compare both chillers over time", Skill.INVESTIGATE),
        ("how many faults on chiller 1", Skill.LOOK_UP),
    ],
)
def test_keyword_routing_is_deterministic(message: str, expected: Skill) -> None:
    decision = route(message)
    assert decision.skill is expected
    assert not decision.used_model


def test_verify_is_ordered_before_prepare_work() -> None:
    """"did the repair work" contains "work" and would otherwise be caught by prepare-work.

    Order is the entire mechanism at this layer, so it is asserted rather than assumed.
    """
    assert route("did the repair work on chiller 1").skill is Skill.VERIFY


def test_the_same_message_always_routes_the_same_way() -> None:
    """Routing is testable because it is deterministic. Forty runs, one answer."""
    decisions = {route("why is chiller 1 in high head").skill for _ in range(40)}
    assert decisions == {Skill.EXPLAIN}


# ── layer 3.5: the scope gate ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "message",
    ["what is the capital of France", "write me a poem", "what is 2 plus 2 times 7"],
)
def test_an_out_of_scope_question_is_refused_before_any_model_call(message: str) -> None:
    decision = route(message)
    assert decision.skill is Skill.REFUSE
    assert decision.layer.startswith("3.5")
    assert not decision.used_model


def test_the_scope_gate_does_not_fire_when_a_machine_is_named() -> None:
    assert route("chiller 1").skill is not Skill.REFUSE


# ── layers 4 and 5 ──────────────────────────────────────────────────────────────

def test_the_arbiter_is_only_reached_when_the_cheap_layers_are_inconclusive() -> None:
    calls: list[str] = []

    def arbiter(message: str) -> str:
        calls.append(message)
        return "investigate"

    route("why is chiller 1 in high head", arbiter=arbiter)
    assert calls == [], "a keyword match must not spend a model call"


def test_an_arbiter_returning_an_unknown_skill_is_ignored() -> None:
    """The model proposes a route; it never establishes one."""
    decision = route("chiller 1 something unusual", arbiter=lambda _m: "teleport")
    assert decision.skill is Skill.EXPLAIN
    assert not decision.used_model


def test_layer_5_refuses_equipment_the_catalog_does_not_confirm() -> None:
    """A model naming `chiller_3` on a two-chiller site is the most convincing kind of wrong."""
    assert reconcile_equipment("chiller_1") == "chiller_1"
    assert reconcile_equipment("chiller_3") is None
    assert reconcile_equipment(None) is None


# ════════════════════════════════════════════════════════════════════════════════
# The honesty audits — EV4
# ════════════════════════════════════════════════════════════════════════════════

GOOD_ANSWER = (
    "On 2026-04-15 chiller 1 carried the label HIGH_HEAD_AMBIGUOUS. The current residual "
    "read -20.0, against this asset's own healthy band of -38.677 to -12.613 with a median "
    "of -25.645, so it sits high for this machine. The model behind it has an nRMSE of "
    "48.03, which is a poor fit, so treat the reading with caution."
)


def test_a_clean_answer_passes_every_audit() -> None:
    report = run_audits(GOOD_ANSWER, _pack())
    assert report.passed, [f.detail for f in report.findings if not f.passed]
    assert not report.must_replace_answer


def test_an_invented_number_is_caught() -> None:
    """The headline of `EV4`. A number the pack does not contain was fabricated."""
    answer = GOOD_ANSWER + " Condenser approach temperature was 7.4 K."
    report = run_audits(answer, _pack())
    finding = next(f for f in report.findings if f.audit == "numbers_are_grounded")
    assert not finding.passed
    assert "7.4" in finding.offending
    assert report.must_replace_answer


def test_a_truncated_figure_counts_as_invented() -> None:
    """"-25.6" when the evidence says "-25.645" is a different claim, not a rounding.

    This is why the pack hands the model display strings: containment answers it exactly,
    where a float comparison would have to pick a tolerance and would forgive this.
    """
    report = run_audits("On 2026-04-15 the median was -25.6 for chiller 1.", _pack())
    assert not next(f for f in report.findings if f.audit == "numbers_are_grounded").passed


def test_equipment_that_does_not_exist_is_caught() -> None:
    answer = GOOD_ANSWER + " Chiller 3 shows the same pattern."
    finding = next(
        f for f in run_audits(answer, _pack()).findings if f.audit == "equipment_exists"
    )
    assert not finding.passed
    assert "chiller 3" in finding.offending


def test_the_other_real_chiller_may_be_mentioned_for_contrast() -> None:
    """A correct answer legitimately compares the two machines."""
    answer = GOOD_ANSWER + " Chiller 2 has its own band and is judged separately."
    assert next(
        f for f in run_audits(answer, _pack()).findings if f.audit == "equipment_exists"
    ).passed


def test_quoting_a_never_measured_signal_as_a_reading_is_caught() -> None:
    """The one that matters most here. `cond_flow` feeds four of the six models and has
    never recorded a non-zero value — quoting it asserts an instrumentation capability the
    site does not have."""
    answer = GOOD_ANSWER + " Condenser flow was 893.7 at the time."
    finding = next(
        f for f in run_audits(answer, _pack()).findings if f.audit == "never_measured_not_quoted"
    )
    assert not finding.passed
    assert "condenser flow" in finding.offending


def test_saying_condenser_flow_has_never_been_measured_is_correct_not_a_violation() -> None:
    """The audit must not punish the sentence the product exists to say."""
    answer = GOOD_ANSWER + " Condenser flow has never been measured on this plant."
    assert next(
        f for f in run_audits(answer, _pack()).findings
        if f.audit == "never_measured_not_quoted"
    ).passed


def test_an_answer_with_no_window_is_caught() -> None:
    """`C22`. Anomaly counts were once shown under a heading describing a telemetry window
    that did not overlap them at all."""
    answer = "Chiller 1 carried the label HIGH_HEAD_AMBIGUOUS and the residual sat high."
    assert not next(
        f for f in run_audits(answer, _pack()).findings if f.audit == "window_is_stated"
    ).passed


def test_the_model_diagnosing_on_its_own_authority_is_caught() -> None:
    """The separation law, enforced on the output. The FDD rules name the fault."""
    answer = GOOD_ANSWER + " The root cause is definitely a fouled condenser."
    finding = next(
        f for f in run_audits(answer, _pack()).findings if f.audit == "model_did_not_diagnose"
    )
    assert not finding.passed


def test_naming_the_label_the_rules_produced_is_explaining_not_diagnosing() -> None:
    assert next(
        f for f in run_audits(GOOD_ANSWER, _pack()).findings
        if f.audit == "model_did_not_diagnose"
    ).passed


def test_hiding_a_poor_fit_is_a_soft_failure_not_a_hard_one() -> None:
    """The answer is still useful and the interface badges it. Hiding it would be worse —
    acceptance case 14 shows a badged machine beside a clean one deliberately."""
    answer = (
        "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS. The current residual read "
        "-20.0 against a band of -38.677 to -12.613, median -25.645."
    )
    report = run_audits(answer, _pack())
    finding = next(f for f in report.findings if f.audit == "poor_fit_disclosed")
    assert not finding.passed
    assert finding.severity is AuditSeverity.SOFT
    assert not report.must_replace_answer, "a soft failure badges; it does not withhold"


def test_all_six_audits_run_even_after_the_first_failure() -> None:
    """The record should say everything wrong with an answer, not the first thing."""
    answer = "Chiller 3 flow was 893.7 and the root cause is definitely fouling."
    report = run_audits(answer, _pack())
    assert len(report.findings) == 7
    assert len(report.hard_failures) >= 3


def test_a_hard_failure_replaces_the_answer_rather_than_annotating_it() -> None:
    """Constraint 16: the honesty layer overrides the model, it does not advise it. A
    reassuring paragraph followed by a caveat is still read as reassuring."""
    report = run_audits(GOOD_ANSWER + " Approach was 7.4 K.", _pack())
    correction = correction_for(report, _pack())
    assert "withheld" in correction
    assert "HIGH_HEAD_AMBIGUOUS" in correction
    assert "2026-04-15" in correction
    assert "7.4" not in correction, "the correction must not repeat the invented figure"
