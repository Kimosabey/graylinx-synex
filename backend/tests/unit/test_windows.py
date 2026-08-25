"""`C23` untrusted-window marking.

Inherited constraint 15: **every artefact states its data window.** The incident behind it —
anomaly counts shown on the database wall clock, under a heading describing a telemetry window
that did not overlap it at all.

Constraint 16 is the sharper half: the honesty layer **overrides** the model rather than
advising it. A reassuring headline over a blind window is replaced outright and the record
marked corrected. An advisory footnote under a reassuring headline leaves the reassuring
headline on the page.

The counts below are the measured ones: 31,884 in-window slots per chiller, of which **7,670
are derived** since the 2026-08-17 re-clone.
"""
from __future__ import annotations

from datetime import date, datetime

from app.analytics.windows import (
    Ground,
    WindowContents,
    assess,
    enforce_headline,
    reads_as_reassuring,
)
from app.domain.signals import SignalStatus
from app.services.evidence import window_for

WINDOW = window_for(date(2026, 4, 15), datetime(2026, 6, 23, 11, 50))
IN_WINDOW_SLOTS = 31_884
DERIVED_IN_WINDOW = 7_670


def _contents(**kw) -> WindowContents:
    base: dict = {"window": WINDOW, "total_slots": IN_WINDOW_SLOTS}
    base.update(kw)
    return WindowContents(**base)


# ── a clean window ─────────────────────────────────────────────────────────────

def test_a_clean_window_is_trusted_and_still_states_its_period() -> None:
    """Trusted is not the same as silent. Constraint 15 applies to every artefact, including
    the ones with nothing wrong."""
    trust = assess(_contents())
    assert trust.is_trusted
    assert trust.grounds == ()
    assert "Data window" in trust.window_statement()


# ── the grounds are kept apart ────────────────────────────────────────────────

def test_derived_slots_untrust_a_window() -> None:
    """The re-clone put 7,670 computed slots inside the measured window. They are calculated,
    not read, and nothing in the product labels them yet."""
    trust = assess(_contents(derived_slots=DERIVED_IN_WINDOW))
    assert not trust.is_trusted
    assert Ground.DERIVED_SLOTS in trust.ground_kinds


def test_a_single_derived_slot_is_still_worth_saying() -> None:
    """No threshold is invented for *how much* of a window must be computed. Any at all is
    reportable, because the reader is the one who decides whether it matters to their figure."""
    assert Ground.DERIVED_SLOTS in assess(_contents(derived_slots=1)).ground_kinds


def test_simulated_slots_untrust_a_window_even_though_there_are_none_today() -> None:
    """Zero since the re-clone, and the guard stays. A future restore from a simulating source
    must fail here rather than quietly putting fabricated values into figures."""
    assert Ground.SIMULATED_SLOTS in assess(_contents(simulated_slots=1)).ground_kinds


def test_a_blind_detector_is_its_own_ground() -> None:
    """Constraint 7: NULL means not diagnosed, never healthy. A two-month window was once
    blind rather than clean."""
    trust = assess(_contents(unlabelled_slots=IN_WINDOW_SLOTS))
    assert Ground.DETECTOR_BLIND in trust.ground_kinds


def test_a_never_measured_signal_untrusts_what_rests_on_it() -> None:
    """`cond_flow` is 0 non-zero in 37,430 measured slots and feeds four of the six models."""
    trust = assess(_contents(signal_statuses={"cond_flow": SignalStatus.NEVER_MEASURED}))
    assert Ground.SIGNAL_NEVER_MEASURED in trust.ground_kinds


def test_the_grounds_do_not_collapse_into_one_flag() -> None:
    """Derived, simulated, blind and a dead signal are different facts about a period. A
    reader sent to fix the wrong one has been misled by the summary rather than the data."""
    trust = assess(
        _contents(
            derived_slots=DERIVED_IN_WINDOW,
            simulated_slots=10,
            unlabelled_slots=1_000,
            signal_statuses={"cond_flow": SignalStatus.NEVER_MEASURED},
        )
    )
    assert len(set(trust.ground_kinds)) >= 4


def test_every_ground_carries_its_reason_in_words() -> None:
    """An absence is not a zero and not a dash."""
    trust = assess(_contents(derived_slots=DERIVED_IN_WINDOW, unlabelled_slots=1_000))
    for ground in trust.grounds:
        assert ground.words.strip(), f"{ground.ground} has no words"


# ── constraint 16: the honesty layer overrides, it does not advise ────────────

def test_a_reassuring_headline_over_a_blind_window_is_replaced() -> None:
    """**Replaced outright**, not annotated."""
    trust = assess(_contents(unlabelled_slots=IN_WINDOW_SLOTS))
    ruling = enforce_headline("No faults were detected this month.", trust)

    assert ruling.was_corrected
    assert ruling.headline != ruling.original
    assert ruling.words.strip()


def test_the_original_survives_the_correction() -> None:
    """*"The record marked corrected"* — a replacement nobody can see is indistinguishable
    from the model having written the honest version itself."""
    original = "Everything looks normal."
    ruling = enforce_headline(original, assess(_contents(unlabelled_slots=IN_WINDOW_SLOTS)))
    assert ruling.original == original
    assert ruling.was_corrected


def test_an_honest_headline_over_a_blind_window_is_left_alone() -> None:
    """Over-correcting would make the layer untrustworthy in the other direction."""
    honest = "The detector could not see this unit for most of the period."
    ruling = enforce_headline(honest, assess(_contents(unlabelled_slots=IN_WINDOW_SLOTS)))
    assert not ruling.was_corrected
    assert ruling.headline == honest


def test_a_reassuring_headline_over_a_trusted_window_is_left_alone() -> None:
    """A clean month may be reported as clean. The rule is about blindness, not optimism."""
    ruling = enforce_headline("No faults were detected this month.", assess(_contents()))
    assert not ruling.was_corrected


def test_reassuring_phrasings_are_recognised_and_honest_ones_are_not() -> None:
    """`reads_as_reassuring` returns the verdict **and its reason** — the phrase it matched,
    so a correction can say what it reacted to rather than asserting the headline was bad."""
    reassuring, why = reads_as_reassuring("No faults were detected.")
    assert reassuring
    assert "no faults" in why

    honest, why = reads_as_reassuring(
        "Three residuals sat outside this asset's own band on 15 April."
    )
    assert not honest
    assert why.strip()


def test_the_plainest_reassurance_of_all_is_recognised() -> None:
    """*"Everything looks normal"* is about as reassuring as English gets over a blind window,
    and the original twelve phrases all missed it — they were written around fault vocabulary
    rather than around reassurance. Found by writing this test; `Q67` owns the general
    problem, because a blacklist is a blacklist."""
    assert reads_as_reassuring("Everything looks normal.")[0]
    assert reads_as_reassuring("The plant looks fine this month.")[0]


# ── the artefact states its window ────────────────────────────────────────────

def test_the_window_statement_names_the_period_and_its_source() -> None:
    """The incident: a heading describing a telemetry window that did not overlap the data at
    all. Naming both is what makes that impossible to repeat."""
    statement = assess(_contents()).window_statement()
    assert "Data window" in statement
    assert assess(_contents()).contents.window.source in statement


def test_the_verdict_serialises_with_its_words() -> None:
    """A surface must be able to show the sentence rather than rebuild it from the counts."""
    payload = assess(_contents(derived_slots=DERIVED_IN_WINDOW)).as_dict()
    assert payload
    assert any(isinstance(v, str) and v.strip() for v in payload.values())


# ── the counts are validated rather than trusted ──────────────────────────────

def test_more_derived_slots_than_slots_is_refused() -> None:
    """Two numbers read from different places is a real failure mode here — the incident at
    the top of this file was exactly that. Refusing is better than reporting 240% derived."""
    import pytest

    with pytest.raises(ValueError):
        assess(_contents(total_slots=1_000, derived_slots=DERIVED_IN_WINDOW))
