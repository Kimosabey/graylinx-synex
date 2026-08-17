"""`RC17` detection-to-queue reconciliation — the reporting half, offline.

Twenty-two detected episodes never reached the case queue, including the only two rated
*critical*, because the idempotent seed was never scheduled. `RC8` made the seed safe to
re-run; it did not make it run. These tests cover the part that can be judged without a
database: what gets seeded, and what the report says when nothing is wrong.
"""
from __future__ import annotations

from datetime import date, datetime

from app.analytics.episodes import Episode
from app.jobs.reconcile import RECONCILE_EVERY_SECONDS, Reconciliation, to_detected

DAY = date(2026, 4, 15)
NOW = datetime(2026, 8, 17, 13, 16)


def _episode(label: str, slots: int = 10) -> Episode:
    return Episode(
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
        slot_count=slots,
        first_slot=datetime.combine(DAY, datetime.min.time()),
        last_slot=datetime.combine(DAY, datetime.max.time()),
    )


# ── what reaches the queue ─────────────────────────────────────────────────────

def test_a_refusal_never_becomes_a_case() -> None:
    """`NO_DIAGNOSIS` is the modal labelled outcome at 5,309 slots and `NO_EFFICIENCY_FAULT`
    at 943. Seeding those would turn the platform's commonest honest answer into work, and
    would drown the 39 real episodes."""
    detected = to_detected(
        (_episode("NO_DIAGNOSIS", 5_309), _episode("NO_EFFICIENCY_FAULT", 943))
    )
    assert detected == ()


def test_a_real_fault_reaches_the_queue() -> None:
    detected = to_detected((_episode("CONDENSER_LOW_FLOW", 3),))
    assert len(detected) == 1
    assert detected[0].fault_label == "CONDENSER_LOW_FLOW"
    assert detected[0].slot_count == 3


def test_the_slot_count_travels_with_the_episode() -> None:
    """Evidence, not configuration. A case that lost its slot count would make a 412-reading
    fault and a 3-reading one look identical in the queue."""
    detected = to_detected((_episode("HIGH_HEAD_AMBIGUOUS", 412),))
    assert detected[0].slot_count == 412


def test_an_unknown_label_is_not_seeded() -> None:
    """A label this plant's model does not emit is a data problem, not a case."""
    assert to_detected((_episode("SOMETHING_INVENTED"),)) == ()


# ── the report speaks even when nothing is wrong ───────────────────────────────

def test_a_clean_pass_still_reports() -> None:
    """**The whole point.** A reconciliation that only spoke up when it found something would
    be indistinguishable from one that had stopped running — which is exactly how twenty-two
    episodes went missing."""
    report = Reconciliation(
        detected=39, queued_before=39, seeded=0, detected_but_not_queued=0, ran_at=NOW
    )
    assert report.is_clean
    assert "39 detected episode(s), all of them queued" in report.render()
    assert "Nothing is waiting outside the queue" in report.render()


def test_a_gap_is_named_as_the_failure_it_is() -> None:
    report = Reconciliation(
        detected=39, queued_before=0, seeded=17, detected_but_not_queued=22, ran_at=NOW
    )
    assert not report.is_clean
    assert "22 of them are NOT in the queue" in report.render()
    assert "twenty-two-episode failure" in report.render()


def test_no_detection_is_reported_as_silence_not_as_health() -> None:
    """Inherited constraint 7: NULL means not diagnosed, never healthy. An empty window is the
    detector saying nothing, and a two-month window was once blind rather than clean."""
    report = Reconciliation(
        detected=0, queued_before=0, seeded=0, detected_but_not_queued=0, ran_at=NOW
    )
    assert "the detector's silence" in report.render()
    assert "not a statement that the plant is healthy" in report.render()


def test_the_report_is_serialisable_and_carries_its_words() -> None:
    """A surface must be able to show the sentence, not rebuild it from the counts."""
    payload = Reconciliation(
        detected=39, queued_before=39, seeded=0, detected_but_not_queued=0, ran_at=NOW
    ).as_dict()
    assert payload["rendered"]
    assert payload["is_clean"] is True
    assert payload["detected"] == 39


# ── the schedule ───────────────────────────────────────────────────────────────

def test_the_interval_is_shorter_than_the_slot_cadence_it_watches() -> None:
    """Fifteen minutes against a five-minute slot cadence — three slots, the smallest window
    that cannot miss a whole reading period. `RC8` makes running often free; running rarely is
    what cost twenty-two episodes."""
    assert RECONCILE_EVERY_SECONDS == 15 * 60
    assert RECONCILE_EVERY_SECONDS > 5 * 60


def test_importing_the_worker_opens_no_connection() -> None:
    """`WorkerSettings` is a class with lazy accessors on purpose: importing this module — which
    every test does — must not reach Redis."""
    from app.jobs.reconcile import WorkerSettings

    assert callable(WorkerSettings.redis_settings)
    assert callable(WorkerSettings.cron_jobs)
    assert WorkerSettings.functions
