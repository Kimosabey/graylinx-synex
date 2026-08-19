"""Co-occurring labels, and the ordering rule the data forces."""
from __future__ import annotations

from datetime import date

from app.analytics.events import to_events

UNDECIDABLE = frozenset(
    {
        "HIGH_HEAD_AMBIGUOUS",
        "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        "CONDENSER_WATER_SIDE_UNSPECIFIED",
        "POWER_HIGH_UNEXPLAINED",
    }
)


def _episode(equipment: str, label: str, day: str, slots: int = 1) -> dict:
    return {
        "equipment_key": equipment,
        "fault_label": label,
        "day": day,
        "slot_count": slots,
    }


def test_one_machine_day_is_one_event() -> None:
    """**A queue listing labels overstates the work.**

    Chiller 1 on 18 April carries four detected classes. That is not four people to dispatch;
    it is one machine having one bad day seen through four detectors.
    """
    events = to_events(
        [
            _episode("chiller_1", "HIGH_HEAD_AMBIGUOUS", "2026-04-18", 75),
            _episode("chiller_1", "REFRIGERANT_SIDE_HIGH_HEAD", "2026-04-18", 13),
            _episode("chiller_1", "POWER_HIGH_UNEXPLAINED", "2026-04-18", 2),
            _episode("chiller_1", "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION", "2026-04-18", 2),
        ],
        undecidable=UNDECIDABLE,
    )
    assert len(events) == 1
    assert events[0].label_count if hasattr(events[0], "label_count") else True
    assert len(events[0].labels) == 4
    assert events[0].slot_count == 92


def test_the_lead_is_never_simply_the_biggest() -> None:
    """**The rule the data forces, and the reason it exists.**

    `HIGH_HEAD_AMBIGUOUS` appears on 12 of 12 fault days and usually carries the most slots.
    Picking the largest would title every event on the plant with the class that says least,
    and a queue where every row reads "ambiguous" is a queue nobody can triage.
    """
    events = to_events(
        [
            _episode("chiller_1", "HIGH_HEAD_AMBIGUOUS", "2026-04-18", 75),
            _episode("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-18", 3),
        ],
        undecidable=UNDECIDABLE,
    )
    # Determinate, and twenty-five times smaller.
    assert events[0].lead_label == "CONDENSER_LOW_FLOW"
    assert events[0].lead_is_undecidable is False
    assert events[0].also_detected == ("HIGH_HEAD_AMBIGUOUS",)


def test_among_determinate_classes_the_larger_leads() -> None:
    """Size decides only once the honest-versus-ambiguous question is settled."""
    events = to_events(
        [
            _episode("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-18", 3),
            _episode("chiller_1", "COMPRESSOR_INEFFICIENCY", "2026-04-18", 40),
        ],
        undecidable=UNDECIDABLE,
    )
    assert events[0].lead_label == "COMPRESSOR_INEFFICIENCY"


def test_an_all_undecidable_day_still_gets_a_lead() -> None:
    """Every event needs a title, including the ones where nothing is determinate."""
    events = to_events(
        [
            _episode("chiller_1", "HIGH_HEAD_AMBIGUOUS", "2026-04-18", 10),
            _episode("chiller_1", "POWER_HIGH_UNEXPLAINED", "2026-04-18", 40),
        ],
        undecidable=UNDECIDABLE,
    )
    assert events[0].lead_label == "POWER_HIGH_UNEXPLAINED"
    assert events[0].lead_is_undecidable is True


def test_the_order_is_reproducible() -> None:
    """**Ties break on the label text, and that is not decoration.**

    Without it two equal classes order by dict insertion and the same window renders
    differently on two runs — which makes "why is this row first?" unanswerable.
    """
    rows = [
        _episode("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-18", 5),
        _episode("chiller_1", "COMPRESSOR_INEFFICIENCY", "2026-04-18", 5),
    ]
    first = to_events(rows, undecidable=UNDECIDABLE)[0].lead_label
    second = to_events(list(reversed(rows)), undecidable=UNDECIDABLE)[0].lead_label
    assert first == second


def test_nothing_is_dropped() -> None:
    """A co-occurring class is evidence about the event, not noise around it."""
    events = to_events(
        [
            _episode("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-18", 3),
            _episode("chiller_1", "HIGH_HEAD_AMBIGUOUS", "2026-04-18", 75),
            _episode("chiller_1", "POWER_HIGH_UNEXPLAINED", "2026-04-18", 2),
        ],
        undecidable=UNDECIDABLE,
    )
    assert set(events[0].labels) == {
        "CONDENSER_LOW_FLOW",
        "HIGH_HEAD_AMBIGUOUS",
        "POWER_HIGH_UNEXPLAINED",
    }
    assert len(events[0].also_detected) == 2


def test_different_machines_and_days_stay_separate() -> None:
    events = to_events(
        [
            _episode("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-18"),
            _episode("chiller_2", "CONDENSER_LOW_FLOW", "2026-04-18"),
            _episode("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-19"),
        ],
        undecidable=UNDECIDABLE,
    )
    assert len(events) == 3
    # Newest first, then machine — never by seriousness, which is agreed for one class of nine.
    assert events[0].day == date(2026, 4, 19)


def test_an_unparseable_day_is_skipped_rather_than_guessed() -> None:
    events = to_events(
        [_episode("chiller_1", "CONDENSER_LOW_FLOW", "not-a-date")],
        undecidable=UNDECIDABLE,
    )
    assert events == ()
