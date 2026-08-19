"""Co-occurring labels collapsed into the events they actually describe.

**One real fault produces several labels at once, and a queue that lists labels overstates the
work.** Chiller 1 on 18 April carries four detected classes in the same day — high head,
refrigerant side, power, starved evaporator. Those are not four problems to dispatch four
people to; they are one machine having one bad day, seen through four detectors. A screen
listing 39 rows tells a planner there are 39 things to look at, and there are not.

**The lead label is never the biggest, and that rule is forced by the data.**
`HIGH_HEAD_AMBIGUOUS` appears on 12 of 12 fault days and usually carries the most slots — so
picking the largest would title every event on the plant with the class that says least, and a
queue where every row reads *"ambiguous"* is a queue nobody can triage. A class that names a
mechanism leads over one that admits it cannot decide; among equals, the one with more slots
leads, and ties break on the label text so the same window always produces the same order.

**Nothing is dropped and nothing is ranked.** Every label stays on the event that carries it,
because a co-occurring class is evidence about that event rather than noise around it. And the
events are not ordered by seriousness: severity is agreed for one fault class of nine, so an
ordering by importance would present a judgement the formula cannot make.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Event:
    """One machine, one day, and every class detected on it."""

    equipment_key: str
    day: date
    lead_label: str
    """The class that titles this event — determinate over undecidable, never the biggest."""

    labels: tuple[str, ...] = field(default_factory=tuple)
    slot_count: int = 0
    lead_is_undecidable: bool = True

    @property
    def also_detected(self) -> tuple[str, ...]:
        """The classes beside the lead one. Evidence about this event, not noise around it."""
        return tuple(label for label in self.labels if label != self.lead_label)

    def as_dict(self) -> dict:
        return {
            "equipment_key": self.equipment_key,
            "day": self.day.isoformat(),
            "lead_label": self.lead_label,
            "lead_is_undecidable": self.lead_is_undecidable,
            "also_detected": list(self.also_detected),
            "label_count": len(self.labels),
            "slot_count": self.slot_count,
        }


def to_events(episodes: list[dict], *, undecidable: frozenset[str]) -> tuple[Event, ...]:
    """Collapse episodes into one event per machine-day.

    `undecidable` is handed in rather than imported, so this stays a pure function over data —
    the same reason every other module in `app.analytics` takes its rules as arguments.
    """
    grouped: dict[tuple[str, str], list[dict]] = {}
    for episode in episodes:
        key = (str(episode.get("equipment_key", "")), str(episode.get("day", "")))
        grouped.setdefault(key, []).append(episode)

    events: list[Event] = []
    for (equipment_key, day_text), rows in grouped.items():
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue

        labels = tuple(
            sorted({str(r.get("fault_label", "")) for r in rows if r.get("fault_label")})
        )
        if not labels:
            continue

        slots_by_label = {
            label: sum(
                int(r.get("slot_count", 0) or 0)
                for r in rows
                if r.get("fault_label") == label
            )
            for label in labels
        }

        # Determinate first, then more slots, then the label text. The last is not decoration:
        # without it two equal classes order by dict insertion, and the same window renders
        # differently on two runs — which makes "why is this row first?" unanswerable.
        lead = min(
            labels,
            key=lambda label: (
                1 if label in undecidable else 0,
                -slots_by_label[label],
                label,
            ),
        )
        events.append(
            Event(
                equipment_key=equipment_key,
                day=day,
                lead_label=lead,
                labels=labels,
                slot_count=sum(int(r.get("slot_count", 0) or 0) for r in rows),
                lead_is_undecidable=lead in undecidable,
            )
        )

    # Newest first, then machine. Not by seriousness — severity is agreed for one class of nine.
    return tuple(sorted(events, key=lambda e: (-e.day.toordinal(), e.equipment_key)))
