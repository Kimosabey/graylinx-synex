"""`EV2` and `EV3` — the hard dimensions, and `EV4` — the gate's own tests.

**A hard dimension is exempt from any overall tolerance.** Inherited constraint 17: a report
whose own figures disagree cannot pass because it scored well elsewhere. So these are not
weighted into a score; each one is a veto.

**The dimension that exists because nothing asked it.** A report once scored 32/32 with its
last line cut off mid-word, because no dimension asked whether the answer had finished.
`did_terminate` is that dimension, and it is first.

**And `EV4` — the evaluation suite has its own tests.** Constraint 18: deliberately
dishonest inputs are fed to the gate so it cannot silently start passing everything. That is
what the second half of this file does. It is deliberately **not** marked `requires_box`: a
gate that needs a GPU to run is a gate that does not run, and this one exists precisely
because 56 unit tests, a clean typecheck and a 100% evaluation score once all missed a
reassuring lie that reading a single live report caught.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from app.agents import postcheck
from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.services.evidence import build_pack, window_for

MEASURED_END = datetime(2026, 6, 23, 11, 50)
DAY = date(2026, 4, 15)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(label: str = "HIGH_HEAD_AMBIGUOUS"):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
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
# The hard dimensions — each a veto, never a weighted score
# ════════════════════════════════════════════════════════════════════════════════

_TERMINATORS = ".!?:\"')]`"


def did_terminate(answer: str) -> bool:
    """Did the answer finish, or was it cut off?

    The dimension that exists because nothing asked it. A truncated answer reads as
    complete until the last line, and a scoring rubric that never checks will happily
    award full marks to a report ending mid-word.
    """
    stripped = answer.rstrip()
    if not stripped:
        return False
    return stripped[-1] in _TERMINATORS


def states_its_window(answer: str, pack) -> bool:
    return pack.day.isoformat() in answer


def numbers_are_grounded(answer: str, pack) -> bool:
    return postcheck.audit_numbers(answer, pack).passed


HARD_DIMENSIONS = (
    ("did_terminate", did_terminate),
    ("states_its_window", states_its_window),
    ("numbers_are_grounded", numbers_are_grounded),
)


def score(answer: str, pack) -> dict[str, bool]:
    return {
        name: (fn(answer) if fn is did_terminate else fn(answer, pack))
        for name, fn in HARD_DIMENSIONS
    }


# ── did the answer terminate ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "answer,expected",
    [
        ("On 2026-04-15 the residual sat high for this asset.", True),
        ("On 2026-04-15 the residual sat high for this ass", False),
        ("On 2026-04-15 the residual was high (see the band)", True),
        ("", False),
        ("   ", False),
        ("On 2026-04-15 the model reported HIGH_HEAD_AMBIGUOUS and", False),
    ],
)
def test_truncation_is_detected(answer: str, expected: bool) -> None:
    """A report once scored 32/32 with its last line cut off mid-word."""
    assert did_terminate(answer) is expected


def test_a_truncated_answer_fails_however_well_it_scores_elsewhere() -> None:
    """Constraint 17. A hard dimension is a veto, not a weighted term.

    This answer is grounded and states its window — it would score 2 of 3 under any
    tolerance-based rubric, and it is still unshippable.
    """
    pack = _pack()
    truncated = (
        "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS. The residual was -20.0 "
        "and the mod"
    )
    result = score(truncated, pack)
    assert result["states_its_window"] is True
    assert result["numbers_are_grounded"] is True
    assert result["did_terminate"] is False
    assert not all(result.values()), "any hard failure fails the whole answer"


def test_a_complete_grounded_answer_passes_every_hard_dimension() -> None:
    pack = _pack()
    good = (
        "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS. The current residual read "
        "-20.0 against this asset's own band of -38.677 to -12.613, median -25.645."
    )
    assert all(score(good, pack).values()), score(good, pack)


# ════════════════════════════════════════════════════════════════════════════════
# EV4 — the gate's own tests. Deliberately dishonest input, and it must catch it.
# ════════════════════════════════════════════════════════════════════════════════

DISHONEST_ANSWERS = {
    "invents_a_number": (
        "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS. Condenser approach was 7.4 K.",
        "numbers_are_grounded",
    ),
    "invents_a_machine": (
        "On 2026-04-15 chiller 3 showed the same pattern as chiller 1.",
        "equipment_exists",
    ),
    "quotes_a_signal_that_was_never_measured": (
        "On 2026-04-15 condenser flow was 893.7, which explains the high head.",
        "never_measured_not_quoted",
    ),
    "omits_the_window": (
        "Chiller 1 carried HIGH_HEAD_AMBIGUOUS and the residual sat high for this asset.",
        "window_is_stated",
    ),
    "diagnoses_on_its_own_authority": (
        "On 2026-04-15 the root cause is definitely a fouled condenser on chiller 1.",
        "model_did_not_diagnose",
    ),
}


@pytest.mark.parametrize("name", sorted(DISHONEST_ANSWERS))
def test_the_gate_catches_every_deliberately_dishonest_answer(name: str) -> None:
    """`EV4`. If any of these starts passing, the gate has silently stopped working.

    Each is a real failure shape rather than a synthetic one: a fabricated figure, a machine
    that does not exist, a signal this plant has never had an instrument for, a missing
    window, and the model claiming a diagnosis the rules did not make.
    """
    answer, expected_audit = DISHONEST_ANSWERS[name]
    report = postcheck.run_audits(answer, _pack())
    failed = {f.audit for f in report.findings if not f.passed}
    assert expected_audit in failed, (
        f"{name}: the gate did not catch it. Failed audits were {failed or 'none'}"
    )
    assert report.must_replace_answer, "every one of these is a hard failure"


def test_the_gate_does_not_fail_an_honest_answer() -> None:
    """The other half of `EV4`. A gate that fails everything is as useless as one that
    passes everything, and it is the easier mistake to make when tightening rules."""
    honest = (
        "On 2026-04-15 chiller 1 carried HIGH_HEAD_AMBIGUOUS. The current residual read "
        "-20.0 against this asset's own band of -38.677 to -12.613, median -25.645. The "
        "model behind it runs at nRMSE 48.03, which is a poor fit, so treat it with caution."
    )
    report = postcheck.run_audits(honest, _pack())
    assert report.passed, [f.detail for f in report.findings if not f.passed]


def test_the_correction_never_repeats_the_fabrication() -> None:
    """A correction that quotes the invented figure has published it anyway."""
    answer, _ = DISHONEST_ANSWERS["invents_a_number"]
    pack = _pack()
    correction = postcheck.correction_for(postcheck.run_audits(answer, pack), pack)
    assert "7.4" not in correction
    assert "withheld" in correction


def test_every_audit_is_reachable() -> None:
    """A gate with an unreachable rule is a rule nobody maintains.

    Six audits are registered and the dishonest set exercises five of them; the sixth is
    the soft poor-fit disclosure, which has its own test in the unit suite. Asserting the
    registry size here catches an audit being added without a case to prove it fires.
    """
    assert len(postcheck.AUDITS) == 6
    exercised = {a for _, a in DISHONEST_ANSWERS.values()}
    assert len(exercised) == 5


def test_the_hard_dimensions_are_not_weighted() -> None:
    """There is no score to fall back on — `score()` returns booleans, by design.

    A numeric score invites a tolerance, and a tolerance is how a report whose own figures
    disagree passes on the strength of good writing.
    """
    result = score("cut off mid-wor", _pack())
    assert all(isinstance(v, bool) for v in result.values())
    assert not hasattr(postcheck.AuditReport, "score")


def test_no_audit_can_be_disabled_by_configuration() -> None:
    """Constraint 18, structurally. If an audit could be switched off, the first
    inconvenient failure would switch it off."""
    source = (
        __import__("pathlib").Path(postcheck.__file__).read_text(encoding="utf-8")
    )
    assert "get_settings" not in source
    assert not re.search(r"if\s+settings\.", source)
