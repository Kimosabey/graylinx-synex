"""`EV1` — the golden set as a gate, and `EV4` over that gate.

Inherited constraint 18: the evaluation suite has its own tests, and deliberately dishonest
inputs are fed to it so it cannot quietly start passing everything. Here the dishonest input is
a **decayed set** — one that has lost the property that made it worth running. Every case in
such a set still passes; that is exactly why the loss needs its own check.

Not marked `requires_box`. A gate whose meta-tests need a GPU is a gate whose meta-tests never
run, and this whole module is pure functions over data.
"""
from __future__ import annotations

from app.eval import golden
from app.eval.golden import (
    GOLDEN_CASES,
    SET_INVARIANTS,
    CaseCoverage,
    SetVerdict,
    check_set,
    needs_database,
    run,
)

ALL_NAMES = frozenset(c.name for c in GOLDEN_CASES)


# ── the real set ───────────────────────────────────────────────────────────────

def test_the_shipped_set_holds_every_registered_property() -> None:
    """If this fails, the set has decayed and every case in it is still green. That gap is the
    reason the invariants exist as registered data rather than as three assertions inside one
    test function."""
    broken = [r.invariant.id for r in check_set() if not r.held]
    assert not broken, f"the golden set has decayed: {broken}"


def test_the_set_covers_both_machines_and_both_outcomes() -> None:
    """The original three assertions, kept as a test as well as an invariant. Chiller 1's worst
    model runs at nRMSE 48.03 against chiller 2's 3.77, and the refusal is the modal outcome —
    5,309 slots against 674 faulted."""
    assert any(c.equipment_key == "chiller_1" for c in GOLDEN_CASES)
    assert any(c.equipment_key == "chiller_2" for c in GOLDEN_CASES)
    assert any(c.expect_state == "NO_DIAGNOSIS" for c in GOLDEN_CASES)
    assert any(c.expect_state == "BLOCKED" for c in GOLDEN_CASES)
    assert any(c.expect_poor_fit is True for c in GOLDEN_CASES)
    assert any(c.expect_poor_fit is False for c in GOLDEN_CASES)


def test_a_third_of_the_set_needs_nothing_to_run() -> None:
    """If the whole set needed the plant, none of it would run in the default gate — and the
    default gate is the one people actually run."""
    offline = [c for c in GOLDEN_CASES if not needs_database(c)]
    assert len(offline) >= len(GOLDEN_CASES) // 3


def test_every_invariant_says_what_its_loss_would_hide() -> None:
    """The `if_lost` field is the whole argument for the invariant existing. Without it the
    next person to find one inconvenient has nothing to weigh against deleting it."""
    for invariant in SET_INVARIANTS:
        assert len(invariant.because) > 40, f"{invariant.id} does not justify itself"
        assert len(invariant.if_lost) > 40, f"{invariant.id} does not say what it protects"


# ── EV4: the gate must catch a set that has quietly decayed ────────────────────

def test_a_set_that_lost_its_only_refusal_fails_the_gate() -> None:
    """The dishonest input. Drop the refusals and every remaining case still passes — while the
    platform's most common outcome has stopped being exercised at all."""
    without_refusals = tuple(
        c for c in GOLDEN_CASES if c.expect_state not in {"NO_DIAGNOSIS", "BLOCKED"}
    )
    report = run(cases=without_refusals)

    assert report.verdict is SetVerdict.FAILED
    broken = {r.invariant.id for r in report.broken}
    assert "a_refusal_is_covered" in broken
    assert "an_out_of_scope_refusal_is_covered" in broken


def test_a_set_reduced_to_the_clean_machine_fails_the_gate() -> None:
    """A set holding only chiller 2 would never catch the poor-fit badge disappearing —
    acceptance case 14 is the case that does, and it is on chiller 1."""
    report = run(cases=tuple(c for c in GOLDEN_CASES if c.equipment_key != "chiller_1"))

    assert report.verdict is SetVerdict.FAILED
    broken = {r.invariant.id for r in report.broken}
    assert "both_machines_present" in broken
    assert "a_badged_case_beside_a_clean_one" in broken


def test_a_duplicated_case_name_fails_the_gate() -> None:
    """Names are how a judged case is matched back to the set, so a duplicate would count one
    judgement twice and report more coverage than was ever run."""
    report = run(cases=(*GOLDEN_CASES, GOLDEN_CASES[0]))
    assert report.verdict is SetVerdict.FAILED
    assert "case_names_are_distinct" in {r.invariant.id for r in report.broken}


def test_a_case_added_without_a_reason_fails_the_gate() -> None:
    """A golden case without a reason is one nobody can decide to delete, so the set only ever
    grows."""
    silent = golden.GoldenCase(name="new_case", question="why?", why="because")
    report = run(cases=(*GOLDEN_CASES, silent))
    assert report.verdict is SetVerdict.FAILED
    assert "every_case_says_why_it_is_here" in {r.invariant.id for r in report.broken}


def test_the_gate_does_not_fail_everything() -> None:
    """The other half of `EV4`. A gate that fails every input is as useless as one that passes
    every input, and considerably more annoying."""
    report = run(judged=ALL_NAMES)
    assert report.verdict is SetVerdict.PASSED
    assert not report.broken


# ── coverage never travels apart from the verdict ──────────────────────────────

def test_no_recorded_judgement_is_incomplete_rather_than_passed() -> None:
    """`Q78`: a transcript is keyed by a hash of its prompt and nothing on disk records which
    golden case it belongs to. Calling that a pass is the reconciliation that claimed agreement
    while excluding what it could not check."""
    report = run()
    assert report.verdict is SetVerdict.INCOMPLETE
    assert len(report.unrecorded) == len(GOLDEN_CASES)
    assert not report.unjudged, "no mapping exists, so nothing is *known* to be unjudged"
    assert "Q78" in report.coverage_sentence()


def test_no_mapping_at_all_is_a_different_fact_from_an_empty_mapping() -> None:
    """The day somebody deletes every transcript must not look exactly like today. `None` means
    the question cannot be answered; an empty set means it was answered and the answer is none.
    """
    unrecorded = run()
    empty = run(judged=frozenset())

    assert unrecorded.unrecorded and not unrecorded.unjudged
    assert empty.unjudged and not empty.unrecorded
    assert unrecorded.verdict is empty.verdict is SetVerdict.INCOMPLETE
    assert CaseCoverage.NOT_RECORDED is not CaseCoverage.NOT_JUDGED


def test_a_partially_judged_set_reports_both_halves() -> None:
    """The count with its denominator attached. A judged figure printed alone is the `R10`
    failure at the scale of the acceptance set."""
    half = frozenset(c.name for c in GOLDEN_CASES[:4])
    report = run(judged=half)

    assert len(report.judged) == 4
    assert len(report.unjudged) == len(GOLDEN_CASES) - 4
    assert report.verdict is SetVerdict.INCOMPLETE
    sentence = report.coverage_sentence()
    assert f"of {len(GOLDEN_CASES)}" in sentence


def test_the_serialised_report_cannot_carry_a_verdict_without_its_coverage() -> None:
    """Enforced by shape rather than by discipline, because the two being separable is the
    defect itself."""
    payload = run(judged=ALL_NAMES).as_dict()
    assert payload["verdict"]
    assert payload["coverage"]["cases_total"] == len(GOLDEN_CASES)
    assert payload["coverage"]["note"]
    assert len(payload["invariants"]) == len(SET_INVARIANTS)


# ── it is genuinely runnable ───────────────────────────────────────────────────

def test_the_gate_runs_from_the_command_line_and_exits_zero_when_nothing_is_broken() -> None:
    """`EV1` says the set *must stay green before any change ships*, which needs something a
    person or a job can run. Until now the only way to reach it was pytest against a live
    application."""
    assert golden.main() == 0


def test_the_command_line_gate_exits_non_zero_when_the_set_has_decayed() -> None:
    """And it must actually fail, or it is a gate in name only."""
    decayed = tuple(c for c in GOLDEN_CASES if c.equipment_key != "chiller_1")
    assert golden.main(cases=decayed) == 1


# ── the set stays the single source of truth ───────────────────────────────────

def test_the_test_suite_reads_the_same_set_the_gate_does() -> None:
    """`CLAUDE.md` §2.8 — one source of truth per fact. Two copies of the acceptance set would
    drift on the day somebody adds a fourteenth case to one of them."""
    from tests.golden.cases import GOLDEN_CASES as FROM_TESTS

    assert FROM_TESTS is GOLDEN_CASES


def test_every_detected_fault_class_has_a_golden_case() -> None:
    """A gate that reports a pass rate over classes it never graded is the honesty gap this
    platform refuses to let a *report* get away with.

    **Found on 2026-08-18 by asking, not by failing.** The measured window holds seven fault
    classes and the set graded five: `COMPRESSOR_INEFFICIENCY` had four episodes and no case,
    `CONDENSER_WATER_SIDE_UNSPECIFIED` had one — and the scorecard still printed a percentage
    as though it covered the plant. Nothing was wrong with any case in the set; the set was
    simply silent about two branches, which is exactly the failure `R5` exists to prevent one
    layer up.

    Asserted against the **domain's** class list rather than the database, so it holds with
    MySQL stopped and fails the day a class is added to the taxonomy without a case behind it.
    """
    from app.domain import faults

    graded = {c.fault_label for c in GOLDEN_CASES if c.fault_label}
    # `NO_DIAGNOSIS` and `NO_EFFICIENCY_FAULT` are outcomes rather than faults: there is
    # nothing to explain about a slot the model declined to label, and the refusal cases
    # cover that path directly.
    detectable = {
        f.label
        for f in faults.FAULT_CLASSES
        if f.label not in {"NO_DIAGNOSIS", "NO_EFFICIENCY_FAULT"}
    }
    missing = sorted(detectable - graded)
    assert not missing, (
        f"{missing} can be detected on this plant and no golden case grades them — the "
        f"scorecard would report a pass rate over a branch nobody measured"
    )
