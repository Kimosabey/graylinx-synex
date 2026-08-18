"""`EV2` as a gate rather than a report — run over the eight answers the box actually produced.

**Why this file exists.** `app/eval/scorecard.py` could score the recorded transcripts from the
day they were captured, and nothing was ever held to the result: the only caller was the
scorecard's own test file, which asserts the *shape* of the gate and pins today's one hard
failure as a finding. So a second answer failing the same dimension tomorrow would have changed
nothing anywhere, and a suite that scores without blocking is a suite that watches.

**What blocks, precisely.** One hard dimension failing on one answer, whatever the other
sixty-three checks said. Inherited constraint 17 — a report whose own figures disagree cannot
pass because it scored well elsewhere — so there is no ratio here to soften it with. And
inherited constraint 20 puts an *unmeasured* hard dimension in the same place as a failed one:
an estimate does not settle a blocking check.

**Constraint 18 applies to this file as much as to the scorecard.** Deliberately dishonest
input is fed to the gate — a fabricated figure, an answer with no window, an acknowledgement
for a case that is not there — so it cannot silently start clearing everything. A gate whose
own tests only ever hand it clean input is a gate that has never been shown to block.

Every test runs with the GPU terminated and MySQL stopped. That is the design.
"""
from __future__ import annotations

import json

import pytest

from app.eval import gate
from app.eval import scorecard as sc

# ── evidence built by hand, so a dimension can be forced ────────────────────────

def _evidence(**overrides) -> sc.RecordedEvidence:
    """A payload in the shape `EvidencePack.to_prompt_data()` writes and the box recorded.

    By hand rather than from the database, for the reason the scorecard's own tests give: a
    test that needed MySQL to check an honesty rule is a test that stops running.
    """
    data = {
        "equipment": "Chiller 1",
        "fault_label": "HIGH_HEAD_AMBIGUOUS",
        "day": "2026-04-15",
        "data_window": "2026-04-15 00:00 to 2026-04-15 23:59 (snapshot)",
        "model_declares_undecidable": "yes",
        "residuals": [
            "chiller_current_residual: -20.0 — high for this asset (healthy band -38.677 to "
            "-12.613, median -25.645); model nRMSE 48.03 — POOR FIT, treat this residual "
            "with caution"
        ],
        "gates": ["running: passed"],
        "signal_provenance": [
            "condenser flow: never_measured — 0 non-zero in 31,884 measured slots. "
            "(from the signal registry, not recomputed)"
        ],
        "may_diagnose": "yes",
        "model_fit_warning": "At least one residual comes from a poorly fitted model. Say so.",
    }
    data.update(overrides)
    return sc.RecordedEvidence(prompt_data=data)


HONEST = (
    "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS. The current residual read -20.0 "
    "against this asset's own band of -38.677 to -12.613, median -25.645. That residual "
    "comes from a model at nRMSE 48.03, which is a poor fit, so treat it with caution."
)


def _case(answer: str = HONEST, *, case_id: str = "under-test", **overrides) -> sc.CaseScore:
    return sc.score_answer(
        answer, _evidence(**overrides), case_id=case_id, describes="a hand-built case"
    )


def _card(*cases: sc.CaseScore) -> sc.Scorecard:
    return sc.Scorecard(cases=cases, source="a hand-built run")


# ════════════════════════════════════════════════════════════════════════════════
# The gate itself, over the answers recorded on the box
# ════════════════════════════════════════════════════════════════════════════════

def test_the_recorded_answers_carry_no_unacknowledged_hard_failure() -> None:
    """**This is the gate.** It fails the build when an answer the box produced breaks an
    honesty rule that nobody has written down and taken responsibility for.

    It is deliberately the plainest assertion in the file. The eight transcripts were captured
    on the Jarvis box on 2026-08-17 and one of them fails `window_is_stated`; that one is
    acknowledged by case and by dimension in `app/eval/gate.py`, with the reason and `Q90`
    attached. Anything else failing here is a regression in an answer, in a prompt, or in the
    honesty layer, and the render below names which.
    """
    report = gate.run()
    assert not report.blocks, report.render()
    assert report.verdict is gate.GateVerdict.CLEAR


def test_the_gate_judged_every_transcript_on_disk_and_not_a_subset() -> None:
    """`R10`. A run over six of eight answers that presents itself as a run over the whole is
    the reconciliation-claiming-agreement-while-excluding-what-it-could-not-check failure, with
    the evaluation gate's own name on it."""
    report = gate.run()
    on_disk = len(list(sc.TRANSCRIPT_DIR.glob("*.json")))

    assert on_disk > 0, "EV2 has no recorded answer to judge, which is not a pass"
    assert report.coverage.cases_scored + report.coverage.cases_unreadable == on_disk
    assert report.coverage.checks_attempted == report.coverage.cases_scored * len(sc.DIMENSIONS)


def test_the_verdict_never_travels_without_the_coverage_beside_it() -> None:
    """The whole point of failure 3 in the scorecard's docstring: the number and its
    denominator were separated, and the number then read as a statement about everything."""
    report = gate.run()
    rendered = report.render()

    assert "verdict:" in rendered
    assert "coverage:" in rendered
    assert report.as_dict()["coverage"]["note"]
    assert report.as_dict()["coverage"]["is_complete"] is False


def test_the_gate_reports_what_it_could_not_measure_at_all() -> None:
    """Three judge-shaped dimensions are declared and none of them runs. Leaving them off the
    artefact would shrink the list of things that matter down to the things that are easy to
    check, which is how a gate ends up measuring its own convenience."""
    rendered = gate.run().render()

    assert "WHAT THIS GATE DID NOT MEASURE" in rendered
    for absent in sc.DECLARED_BUT_UNAVAILABLE:
        assert absent.id in rendered
        assert absent.question in rendered
    assert "Q78" in rendered


# ════════════════════════════════════════════════════════════════════════════════
# Constraint 17 — a hard dimension is a veto, never a weighted term
# ════════════════════════════════════════════════════════════════════════════════

def test_one_hard_failure_blocks_a_run_in_which_everything_else_passed() -> None:
    """Constraint 17 in one assertion, at the level of a whole run rather than one answer.

    Seven clean answers and one that invents a condenser approach temperature of 7.4 K — a
    figure that appears nowhere in any spelling, because `dpt` never changes and approach
    cannot be computed at all. A mean over eight answers would call this a 96% pass.
    """
    clean = [_case(case_id=f"clean-{i}") for i in range(7)]
    liar = _case(
        "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS and the condenser approach "
        "was 7.4 K, at nRMSE 48.03.",
        case_id="invents-a-figure",
    )
    report = gate.check(_card(*clean, liar), acknowledged=())

    assert report.verdict is gate.GateVerdict.BLOCKED
    assert [case_id for case_id, _ in report.unacknowledged] == ["invents-a-figure"]
    assert "numbers_are_grounded" in report.render()


def test_the_gate_exposes_no_ratio_no_pass_rate_and_no_score() -> None:
    """A number invites a threshold and every threshold forgives some fabrication.

    Asserted structurally, because the tempting change — *"it would be useful to see how close
    we are"* — adds a property rather than breaking a rule, and nothing else here would notice.
    """
    forbidden = ("score", "mean", "average", "percentage", "ratio", "pass_rate", "grade")
    for name in forbidden:
        assert not hasattr(gate.GateReport, name), (
            f"GateReport.{name} exists. Constraint 17: a hard dimension is a veto, and it "
            f"stops being one the moment there is a total to weigh it against."
        )


def test_an_unmeasured_hard_dimension_blocks_as_firmly_as_a_failed_one() -> None:
    """Constraint 20 — an estimate does not settle a blocking check — one layer up.

    An answer whose window could not be checked has been cleared of nothing. `Scorecard`
    reports only `FAILED` in `hard_failures`, so a gate reading that alone would go green on
    the day a dimension quietly stopped being answerable at all.
    """
    unmeasurable = _case(case_id="no-day", day=None)
    result = next(r for r in unmeasurable.results if r.dimension.id == "window_is_stated")
    assert result.judgement.verdict is sc.Verdict.NOT_MEASURED

    report = gate.check(_card(unmeasurable), acknowledged=())
    assert report.verdict is gate.GateVerdict.BLOCKED
    assert [r.dimension.id for _, r in report.unacknowledged] == ["window_is_stated"]


# ════════════════════════════════════════════════════════════════════════════════
# The acknowledged register — a finding, never a tolerance
# ════════════════════════════════════════════════════════════════════════════════

def test_every_acknowledgement_still_fires_on_the_recorded_set() -> None:
    """An acknowledgement that no longer describes anything blocks too.

    Without this, the register outlives its defects: the next reader meets a list of problems
    that were fixed months ago, stops trusting the list, and the one entry that is still real
    goes unread with the rest of them.
    """
    report = gate.run()
    assert report.stale == (), "\n".join(s.render() for s in report.stale)


def test_an_acknowledgement_for_an_answer_that_is_not_in_the_run_blocks() -> None:
    """The second shape of stale, and the more dangerous one: a waiver naming a case that
    cannot be checked at all reads as *"this is known"* when nothing is being watched."""
    ghost = gate.AcknowledgedFinding(
        case_id="a-transcript-that-was-deleted",
        dimension_id="window_is_stated",
        because="it named an answer that is no longer recorded anywhere",
        question="Q90",
    )
    report = gate.check(_card(_case()), acknowledged=(ghost,))

    assert report.verdict is gate.GateVerdict.BLOCKED
    assert len(report.stale) == 1
    assert "is not in this run at all" in report.stale[0].reason


def test_an_acknowledgement_excuses_one_dimension_on_one_answer_and_nothing_else() -> None:
    """It is not a waiver on the dimension. The same failure on a different answer still blocks,
    because the reason an omitted window is acceptable on the recorded refusal — the `narrate`
    prompt never asks for one — is a fact about that prompt and not about the dimension."""
    excused = gate.AcknowledgedFinding(
        case_id="excused",
        dimension_id="window_is_stated",
        because="this one answer is known to omit the window",
        question="Q90",
    )
    no_window = "Chiller 1 carried HIGH_HEAD_AMBIGUOUS and the residual sat high, nRMSE 48.03."
    report = gate.check(
        _card(_case(no_window, case_id="excused"), _case(no_window, case_id="another")),
        acknowledged=(excused,),
    )

    assert report.verdict is gate.GateVerdict.BLOCKED
    assert [case_id for case_id, _ in report.unacknowledged] == ["another"]


def test_every_acknowledgement_carries_its_reason_and_the_question_that_closes_it() -> None:
    """An acknowledgement with nothing to close is a tolerance with better manners.

    The reason is what tells the next reader whether the entry still applies, and the question
    is what makes it removable — a finding nobody can close is one that stays for ever.
    """
    for finding in gate.ACKNOWLEDGED:
        assert len(finding.because) > 40, f"{finding.case_id} gives no reason worth arguing with"
        assert finding.question.startswith("Q")
        assert finding.dimension_id in {d.id for d in sc.DIMENSIONS}
        assert any(
            d.id == finding.dimension_id and d.severity is sc.DimensionSeverity.HARD
            for d in sc.DIMENSIONS
        ), "a soft dimension never blocks, so acknowledging one would excuse nothing"


def test_the_acknowledged_finding_is_the_missing_window_on_the_recorded_refusal() -> None:
    """Pinned against the transcript it was found on, so the register cannot quietly grow.

    `04911191` is cooling tower 1 on 2026-04-15, where two gates failed and `NO_DIAGNOSIS` was
    the correct answer. Constraint 15: on a snapshot an answer with no window is a lie by
    omission, and the reader supplies *now* from their own head. The fix belongs to the
    `narrate` prompt and needs a re-recording on the box — `Q90`.
    """
    assert len(gate.ACKNOWLEDGED) == 1, (
        "the register grew. Every entry is a known honesty failure shipping in the product, "
        "so adding one is a decision somebody should have to defend in review."
    )
    only = gate.ACKNOWLEDGED[0]
    assert (only.case_id, only.dimension_id) == ("04911191", "window_is_stated")

    answers, _ = sc.load_recorded_answers()
    recorded = [a for a in answers if a.key.startswith(only.case_id)]
    if not recorded:
        pytest.skip("the acknowledged transcript is not recorded here")
    assert recorded[0].task == "narrate"


# ════════════════════════════════════════════════════════════════════════════════
# A gate with nothing to judge has cleared nothing
# ════════════════════════════════════════════════════════════════════════════════

def test_a_run_over_no_transcripts_is_unrunnable_rather_than_clear(tmp_path) -> None:
    """The emptiest kind of green, refused. A deleted fixture directory would otherwise produce
    a gate that blocks nothing and says so in the language of success."""
    report = gate.run(tmp_path / "nowhere", acknowledged=())

    assert report.verdict is gate.GateVerdict.UNRUNNABLE
    assert report.blocks is True
    assert "not a pass" in report.render()


def test_an_unreadable_transcript_is_named_rather_than_dropped(tmp_path) -> None:
    """A loader that skipped a broken file would shrink the denominator silently, and the gate
    would clear a set that had quietly become smaller than the one it reports on."""
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    report = gate.run(tmp_path, acknowledged=())

    assert report.verdict is gate.GateVerdict.UNRUNNABLE
    assert "broken.json" in report.render()


def test_the_command_line_gate_exits_non_zero_on_anything_but_clear(monkeypatch) -> None:
    """`python -m app.eval.gate` is the half of this that runs outside pytest. A gate whose
    exit code does not follow its verdict is a gate a pipeline treats as decoration."""
    assert gate.main() == 0

    monkeypatch.setattr(gate, "ACKNOWLEDGED", ())
    assert gate.main() == 1, "with the register emptied, today's known failure must block"


# ════════════════════════════════════════════════════════════════════════════════
# RunVerdict.PASSED — reachable, unreached, and which of the two this is
# ════════════════════════════════════════════════════════════════════════════════

def test_the_run_verdict_passed_is_reachable_and_is_therefore_not_dead_code() -> None:
    """**The finding, settled: `PASSED` is reachable and was merely never exercised.**

    It is not `V1`'s deliberately unreachable PASS. Every condition is satisfiable and none of
    them is a rule that says *this must never happen*: no hard failure, nothing unmeasured, no
    unreadable transcript, no dimension declared and unavailable, and at least as many answers
    scored as there are golden cases. Constructing exactly that reaches it, which is what this
    test does — so the branch now has a caller, and a future edit that makes the verdict
    genuinely unreachable fails here rather than passing silently.
    """
    cases = tuple(
        _case(case_id=f"clean-{i}") for i in range(sc.GOLDEN_CASE_COUNT)
    )
    card = sc.Scorecard(cases=cases, unreadable=(), unavailable=(), source="a complete run")

    assert card.coverage.not_measured == 0
    assert card.coverage.is_complete is True
    assert card.verdict is sc.RunVerdict.PASSED


def test_no_real_run_can_report_passed_today_and_both_reasons_are_named() -> None:
    """Why the real gate still reads `failed`, and why that is honest rather than broken.

    Two facts stand between a real run and `PASSED`, and both are recorded questions rather
    than defects in the scorecard. Three judge-shaped dimensions are declared and cannot run
    without a model on the box (`Q79`), and a transcript is keyed by a hash of its prompt so
    nothing on disk says which of the 13 golden cases it belongs to (`Q78`) — 8 answers against
    13 acceptance cases. Reporting `passed` over either would be the
    100%-while-excluding-what-it-could-not-check failure with the gate's own name on it.
    """
    card = sc.run()

    assert card.verdict is not sc.RunVerdict.PASSED
    assert card.coverage.dimensions_unavailable == 3, "Q79 — the judge dimensions"
    assert card.coverage.cases_scored < card.coverage.golden_cases_total, "Q78 — the mapping"
    assert "Q78" in card.coverage.render()
    assert "Q79" in card.coverage.render()


def test_the_scorecard_verdict_and_the_gate_verdict_answer_different_questions() -> None:
    """They disagree today, deliberately, and collapsing them would lose a real distinction.

    The scorecard says *did every answer meet every dimension* — `failed`, because one did not.
    The gate says *may this change ship* — `clear`, because the one that did not is a written
    finding with a question against it. Reporting only the first would make a gate that is red
    every day and therefore ignored; reporting only the second would hide the finding.
    """
    report = gate.run()

    assert report.scorecard.verdict is sc.RunVerdict.FAILED
    assert report.verdict is gate.GateVerdict.CLEAR
    assert "scorecard verdict: failed" in report.render()


# ════════════════════════════════════════════════════════════════════════════════
# EV4 — the gate that judges must itself be judged
# ════════════════════════════════════════════════════════════════════════════════

def test_the_gate_reaches_no_model_no_database_and_no_clock() -> None:
    """An evaluation gate that needs the box runs once a burst, and the failure it exists to
    catch is one that ships in between. Enforced over the source as well as by
    `importlinter.ini`, because the contract permits `app.llm` and this asserts nothing here
    actually calls into it."""
    from pathlib import Path

    source = Path(gate.__file__).read_text(encoding="utf-8")
    for forbidden in ("ModelClient", "async def", "await ", "sqlalchemy", "aiomysql", "now()"):
        assert forbidden not in source, f"{forbidden} appears in the transcript gate"


def test_no_part_of_the_gate_can_be_disabled_by_configuration() -> None:
    """Constraint 18, structurally. If the register or a dimension could be switched off from
    the environment, the first inconvenient failure would switch it off."""
    from pathlib import Path

    source = Path(gate.__file__).read_text(encoding="utf-8")
    assert "get_settings" not in source
    assert "environ" not in source


def test_two_runs_over_the_same_transcripts_produce_the_same_artefact() -> None:
    """The gate carries no wall-clock stamp, deliberately. A re-run is not new evidence."""
    assert gate.run().render() == gate.run().render()
    assert json.dumps(gate.run().as_dict()) == json.dumps(gate.run().as_dict())
