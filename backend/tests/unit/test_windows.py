"""`C23` untrusted-window marking.

Inherited constraint 15: **every artefact states its data window.** The incident behind it —
anomaly counts shown on the database wall clock, under a heading describing a telemetry window
that did not overlap it at all.

Constraint 16 is the sharper half: the honesty layer **overrides** the model rather than
advising it. A reassuring headline over a blind window is replaced outright and the record
marked corrected.
"""
from __future__ import annotations

from datetime import datetime

from app.analytics.windows import (
    Ground,
    Untrust,
    WindowContents,
    assess,
    enforce_headline,
    reads_as_reassuring,
)
from app.services.evidence import window_for

WINDOW = window_for(datetime(2026, 4, 15).date(), datetime(2026, 6, 23, 11, 50))


def _contents(**kw) -> WindowContents:
    base = dict(window=WINDOW, total_slots=1_000)
    base.update(kw)
    return WindowContents(**base)


# ── the four grounds are kept apart ────────────────────────────────────────────

def test_a_clean_window_is_trusted_and_says_why() -> None:
    trust = assess(_contents(derived_slots=0, simulated_slots=0))
    assert trust.untrust is Untrust.NONE
    assert trust.trust_statement().strip()


def test_derived_slots_untrust_a_window() -> None:
    """The 2026-08-17 re-clone put **7,670 derived slots inside the measured window**. They
    are computed, not read, and nothing in the product labels them yet."""
    trust = assess(_contents(derived_slots=7_670))
    assert trust.untrust is not Untrust.NONE
    assert Ground.DERIVED in trust.grounds


def test_any_derived_slot_at_all_is_worth_saying(  # noqa: D103
) -> None:
    assert Ground.DERIVED in assess(_contents(derived_slots=1)).grounds


def test_simulated_slots_untrust_a_window_even_though_there_are_none_today() -> None:
    """Zero since the re-clone, and the guard stays. A future restore from a simulating
    source must fail here rather than quietly putting fabricated values into figures."""
    assert Ground.SIMULATED in assess(_contents(simulated_slots=1)).grounds


def test_a_blind_detector_is_its_own_ground() -> None:
    """Constraint 7: NULL means not diagnosed, never healthy. A two-month window was once
    blind rather than clean, and 5,309 slots are `NO_DIAGNOSIS` against 674 faulted."""
    trust = assess(_contents(unlabelled_slots=1_000))
    assert Ground.DETECTOR_BLIND in trust.grounds


def test_the_grounds_do_not_collapse_into_one_flag() -> None:
    """Derived, simulated and blind are different facts about a period, and a reader sent to
    fix the wrong one has been misled by the summary rather than by the data."""
    trust = assess(_contents(derived_slots=10, simulated_slots=10, unlabelled_slots=1_000))
    assert len(trust.grounds) >= 3


# ── constraint 16: the honesty layer overrides, it does not advise ────────────

def test_a_reassuring_headline_over_a_blind_window_is_replaced() -> None:
    """**Replaced outright**, not annotated. An advisory note under a reassuring headline
    leaves the reassuring headline on the page."""
    trust = assess(_contents(unlabelled_slots=1_000))
    ruling = enforce_headline("No faults were detected this month.", trust)

    assert ruling.was_corrected is True
    assert ruling.headline != "No faults were detected this month."
    assert ruling.reason.strip()


def test_an_honest_headline_over_a_blind_window_is_left_alone() -> None:
    """Over-correcting would make the layer untrustworthy in the other direction."""
    honest = "The detector could not see this unit for most of the period."
    ruling = enforce_headline(honest, assess(_contents(unlabelled_slots=1_000)))
    assert ruling.was_corrected is False
    assert ruling.headline == honest


def test_a_reassuring_headline_over_a_trusted_window_is_left_alone() -> None:
    """A clean month may be reported as clean. The rule is about blindness, not optimism."""
    ruling = enforce_headline("No faults were detected this month.", assess(_contents()))
    assert ruling.was_corrected is False


def test_the_correction_is_recorded_rather_than_silent() -> None:
    """*"The record marked corrected"* — a replacement nobody can see is indistinguishable
    from the model having written the honest version itself."""
    ruling = enforce_headline("Everything looks normal.", assess(_contents(unlabelled_slots=1_000)))
    assert ruling.was_corrected
    assert ruling.original, "the original must survive the correction"


def test_reassuring_phrasings_are_recognised() -> None:
    assert reads_as_reassuring("No faults were detected.")
    assert not reads_as_reassuring("Three residuals sat outside this asset's own band.")


# ── constraint 15: every artefact states its window ───────────────────────────

def test_the_window_statement_names_the_period_and_its_source() -> None:
    """The incident: a heading describing a telemetry window that did not overlap the data
    at all. Naming both is what makes that impossible to repeat."""
    statement = assess(_contents()).window_statement()
    assert "Data window" in statement
    assert statement.strip().endswith(assess(_contents()).contents.window.source)
