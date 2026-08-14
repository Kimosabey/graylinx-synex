"""Slot runs collapse into episodes — one case per equipment, fault and day.

Inherited constraint 35, and it is a measurement rather than a preference: a single real
fault spans hundreds of consecutive readings, **up to 412 observed**. Per-slot cases would
bury one afternoon under five hundred rows, and the queue would read as a catastrophe.

`HIGH_HEAD_AMBIGUOUS` on chiller 1 spans 2026-04-09 to 2026-04-22 — **ten days and 412
slots**, and it *clears and returns* rather than persisting. So "is this one case reopened
or a new case?" is not hypothetical, and the day boundary is what answers it.

**Grouping is display-level only** — inherited constraint 12. The per-label episodes are the
trained model's actual output, and rewriting them destroys the record of what it emitted.
This module derives a view; it never edits a label.

Pure functions. The input is whatever the repository read; nothing here touches a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class LabelledSlot:
    """One row of `gla_model_residuals_wc`, reduced to what grouping needs."""

    equipment_key: str
    slot_time: datetime
    fault_label: str


@dataclass(frozen=True)
class Episode:
    """One equipment, one label, one day — the unit a case is opened against.

    Not "one fault". Twelve equipment-days produce **39** naive episodes because a machine
    carries several labels at once, and on 2026-04-15 chiller 1 held five. Collapsing those
    five into one physical problem is `RC19`, and it is a separate decision that needs
    Vishnu's answer to `Q47` — over-grouping hides a real second fault, and a hidden
    undercharge costs a compressor where a duplicate visit costs a morning.
    """

    equipment_key: str
    fault_label: str
    day: date
    slot_count: int
    first_slot: datetime
    last_slot: datetime

    @property
    def key(self) -> tuple[str, str, date]:
        return (self.equipment_key, self.fault_label, self.day)


def to_episodes(slots: tuple[LabelledSlot, ...]) -> tuple[Episode, ...]:
    """Collapse labelled slots into one episode per (equipment, label, day).

    Sorted by day, then equipment, then label — a stable order, so the same window always
    produces the same list. An unstable order here would make the demonstration different
    every time it is run, which is the failure the committed demonstration script exists to
    prevent at a larger scale.
    """
    grouped: dict[tuple[str, str, date], list[datetime]] = {}
    for s in slots:
        grouped.setdefault(
            (s.equipment_key, s.fault_label, s.slot_time.date()), []
        ).append(s.slot_time)

    episodes = [
        Episode(
            equipment_key=equipment_key,
            fault_label=fault_label,
            day=day,
            slot_count=len(times),
            first_slot=min(times),
            last_slot=max(times),
        )
        for (equipment_key, fault_label, day), times in grouped.items()
    ]
    return tuple(sorted(episodes, key=lambda e: (e.day, e.equipment_key, e.fault_label)))


def naive_case_count(episodes: tuple[Episode, ...]) -> int:
    """One case per episode — what happens with no correlation at all.

    Measured at **39** on this window against 12 equipment-days: a 3.25x inflation, and on
    one day five work orders against one plausible repair. This function exists so that
    number is computed rather than quoted.
    """
    return len(episodes)


def equipment_days(episodes: tuple[Episode, ...]) -> int:
    """Distinct (equipment, day) pairs carrying any fault. Measured at 12.

    The denominator of the inflation ratio, and the count `RC19` is trying to get back to.
    """
    return len({(e.equipment_key, e.day) for e in episodes})


def inflation_ratio(episodes: tuple[Episode, ...]) -> float | None:
    """Naive cases per equipment-day. `None` rather than a division by zero on an empty set.

    An empty window is not a ratio of 1.0, and returning one would report a healthy-looking
    figure for a window in which nothing was detected at all.
    """
    days = equipment_days(episodes)
    return len(episodes) / days if days else None


def labels_on(episodes: tuple[Episode, ...], equipment_key: str, day: date) -> tuple[str, ...]:
    """Every label one machine carried on one day. Five, on chiller 1 on 2026-04-15.

    Sorted, so the list is stable — and deliberately *not* ordered by slot count, because
    constraint 36 forbids picking the longest-running label as primary: the ambiguous class
    is usually both the longest-running and the least informative, and it appeared on 12 of
    12 fault days.
    """
    return tuple(
        sorted(
            e.fault_label
            for e in episodes
            if e.equipment_key == equipment_key and e.day == day
        )
    )


def multi_label_days(episodes: tuple[Episode, ...]) -> tuple[tuple[str, date], ...]:
    """The (equipment, day) pairs carrying more than one label — where `RC19` earns its keep.

    Ten of chiller 1's twelve fault days qualify.
    """
    counts: dict[tuple[str, date], int] = {}
    for e in episodes:
        counts[(e.equipment_key, e.day)] = counts.get((e.equipment_key, e.day), 0) + 1
    return tuple(sorted(k for k, n in counts.items() if n > 1))
