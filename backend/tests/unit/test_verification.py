"""`V1`–`V4` — and the case where a cleared label is not a repair.

The test that matters is `test_a_cleared_label_over_a_blind_window_is_unknown`. It reproduces
a real shape in this snapshot: `HIGH_HEAD_AMBIGUOUS` on chiller 1 disappears after 22 April
and never returns, which looks exactly like a successful repair — and over the following week
the current residual is *worse* (3 of 709 readings in band, against 3 of 67 before), because
the gates stopped passing and nothing was being judged at all.

A verification that read "the label is gone" as PASS would have closed a work order on a
deteriorating machine. Inherited constraint 7: a NULL means not diagnosed, never healthy.
"""
from __future__ import annotations

from app.analytics.bands import ResidualBand
from app.analytics.verification import Outcome, verify

BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)
IN_BAND = (-25.0, -20.0, -30.0)
OUT_OF_BAND = (79.7, 105.5, 66.0)


def _verify(before, after, *, band=BAND, diagnosable=True):
    return verify(
        residual_name="chiller_current_residual",
        before=before,
        after=after,
        band=band,
        after_was_diagnosable=diagnosable,
    )


# ── the one that matters ───────────────────────────────────────────────────────

def test_a_cleared_label_over_a_blind_window_is_unknown() -> None:
    """The measured failure shape. The label goes; the machine does not get better."""
    result = _verify(OUT_OF_BAND, OUT_OF_BAND, diagnosable=False)
    assert result.outcome is Outcome.UNKNOWN
    assert not result.closes_the_work_order
    assert "not evidence of a repair" in result.reason
    assert "never healthy" in result.reason


def test_clean_looking_data_over_a_blind_window_is_still_unknown() -> None:
    """Even when every post-work reading is inside the band.

    If the gates did not pass, nothing was judged — and readings that happen to look fine
    are not evidence, they are unexamined. This is the tempting case, and the one where a
    weaker check would hand back a PASS.
    """
    result = _verify(OUT_OF_BAND, IN_BAND, diagnosable=False)
    assert result.outcome is Outcome.UNKNOWN
    assert not result.closes_the_work_order


# ── the three outcomes ─────────────────────────────────────────────────────────

def test_residuals_still_outside_the_band_is_a_fail() -> None:
    result = _verify(OUT_OF_BAND, OUT_OF_BAND, diagnosable=True)
    assert result.outcome is Outcome.FAIL
    assert "still outside" in result.reason
    assert not result.closes_the_work_order


def test_a_full_return_to_band_is_still_unknown_until_q15() -> None:
    """`Q15` blocks the PASS threshold, not the mechanism.

    Nobody has agreed how far inside the band a residual must return, or for how long, to
    count as fixed. The reason says what it saw *and* why it is not a PASS, so the reader
    can tell a missing threshold from a failed repair.
    """
    result = _verify(OUT_OF_BAND, IN_BAND, diagnosable=True)
    assert result.outcome is Outcome.UNKNOWN
    assert result.blocked_by == "Q15"
    assert "what a repair looks like" in result.reason
    assert not result.closes_the_work_order


def test_pass_is_currently_unreachable_and_that_is_deliberate() -> None:
    """Not a bug. Until Q15 exists there is no defensible route to PASS, and inventing a
    threshold would make every closure rest on a number nobody agreed."""
    outcomes = {
        _verify(b, a, diagnosable=d).outcome
        for b in (IN_BAND, OUT_OF_BAND)
        for a in (IN_BAND, OUT_OF_BAND, ())
        for d in (True, False)
    }
    assert Outcome.PASS not in outcomes


# ── only a PASS closes ─────────────────────────────────────────────────────────

def test_unknown_never_closes_the_work_order() -> None:
    """`W9` and `AC5`. The tempting shortcut is treating "no evidence of a problem" as
    "evidence of no problem"; this pairing is what forbids it."""
    for result in (
        _verify(OUT_OF_BAND, IN_BAND, diagnosable=True),
        _verify(OUT_OF_BAND, OUT_OF_BAND, diagnosable=False),
        _verify(OUT_OF_BAND, ()),
        _verify(OUT_OF_BAND, IN_BAND, band=None),
    ):
        assert result.outcome is not Outcome.PASS
        assert not result.closes_the_work_order


# ── the honest absences ────────────────────────────────────────────────────────

def test_no_band_means_nothing_can_be_proved() -> None:
    """Ten of twelve assets. A repair on one of them cannot be verified at all, and saying
    so is better than a green tick."""
    result = _verify(OUT_OF_BAND, IN_BAND, band=None)
    assert result.outcome is Outcome.UNKNOWN
    assert "cannot be judged" in result.reason


def test_no_post_work_readings_is_unknown() -> None:
    assert _verify(OUT_OF_BAND, ()).outcome is Outcome.UNKNOWN


def test_all_null_post_work_readings_is_unknown_not_pass() -> None:
    """`compressor_power_residual` is NULL in every row. A residual that cannot be read is
    not a residual that returned to band."""
    result = _verify(OUT_OF_BAND, (None, None, None))
    assert result.outcome is Outcome.UNKNOWN
    assert "never healthy" in result.reason


def test_every_outcome_explains_itself() -> None:
    """A verification a supervisor cannot act on is one they will override."""
    for result in (
        _verify(OUT_OF_BAND, OUT_OF_BAND, diagnosable=True),
        _verify(OUT_OF_BAND, IN_BAND, diagnosable=True),
        _verify(OUT_OF_BAND, OUT_OF_BAND, diagnosable=False),
        _verify(OUT_OF_BAND, IN_BAND, band=None),
    ):
        assert len(result.reason) > 60, result.reason


def test_the_closure_note_is_nowhere_in_this_module() -> None:
    """Separation law, last row: the repair is proved by post-work residuals and a
    deterministic rule — never by the closure note and never by the language model."""
    import pathlib

    from app.analytics import verification

    source = pathlib.Path(verification.__file__).read_text(encoding="utf-8")
    for banned in ("app.llm", "ModelClient", "closure_note"):
        assert banned not in source.replace("the closure note", "")
