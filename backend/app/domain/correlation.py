"""`RC19`. One problem must not become five work orders — and grouping must never be silent.

**The measurement that made this a feature.** Twelve equipment-days carried a fault in the
measured window, and a naive case per (equipment, day, label) gives **39** — a 3.25× ratio.
On 2026-04-15 chiller 1 held **five labels at once**, so one plausible repair could raise
five work orders and send five visits to the same machine.

**The asymmetry that shapes every rule here.** Over-grouping hides a real second fault;
under-grouping wastes a morning. A fouled condenser on a machine that is *also* low on flow
is two real causes (inherited constraint 28), so a duplicate visit is the cheap error and a
hidden undercharge costs a compressor. Everything below is biased accordingly: this module
**proposes** and never disposes.

Three constraints do the work, and each has an incident behind it:

| | Rule | Why |
|---|---|---|
| 12 | Grouping is **display-level only** | The per-label cases are the trained model's actual
  output. Rewriting them destroys the record of what it emitted, so a proposal carries the
  episodes rather than replacing them |
| 36 | The primary is **never the longest-running label** | The ambiguous class is usually
  both the longest-running and the least informative — it appeared on 12 of 12 fault days.
  Picking "the biggest" would title every event with the label that says least |
| — | Grouping is **proposed, never applied** | `RC19` states it outright, and `Q47` — which
  labels must never be grouped — is unanswered. A wrong grouping made silently is one nobody
  goes back to check |

**What this module deliberately does not do.** `RC19` also says *different labels sharing a
candidate cause are grouped under one investigation*. Shared candidate causes come from the
differentials, and no differential carries reviewed content yet — the library is the SME
hour. Grouping on unreviewed shared causes would be exactly the elimination-by-unread-
judgement failure that `differential.py` exists to prevent, one level up. So the shared-cause
route is **not implemented**, its absence is reported on every proposal, and `Q47` is named
rather than guessed at.

**Nothing here calls a model.** `RC19` is `R` in the register — rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Protocol

from app.domain import faults


class Episode(Protocol):
    """What this module needs of an episode, and nothing more.

    **Structural rather than imported.** `app.domain` imports nothing — contract 4 — and it
    is what lets every rule here run with the GPU down, MySQL stopped and no configuration
    loaded. `app.analytics.episodes.Episode` satisfies this shape and is passed straight in;
    the dependency simply points the other way.

    Caught on 2026-08-17 when the layering contract ran for the first time. The whole config
    had been refused as misconfigured since it was written, so nothing was checked.
    """

    equipment_key: str
    fault_label: str
    day: date
    slot_count: int


class Relation(StrEnum):
    """How a new episode stands against what is already open."""

    REOPEN = "reopen"
    """Same equipment, same label, inside the window. `RC19`: the same label reopens rather
    than opening a second case. The only relation this module resolves on its own, because
    it is an identity question rather than a judgement."""

    PROPOSED_GROUP = "proposed_group"
    """Same equipment and day, different labels. **A proposal for a human**, never applied."""

    SEPARATE = "separate"
    """Different equipment, or outside the window. Nothing to decide."""


#: How far back an open case is considered the same problem. `RC19` says "in a window" and
#: fixes no number.
#:
#: TBD (Q54). Chosen at one day because that is the granularity the episodes themselves use —
#: a case is opened per (equipment, label, **day**), so anything wider would be comparing
#: units the detector does not produce. It only ever affects whether a case *reopens* or
#: opens fresh; it never eliminates anything and never suppresses a detection.
REOPEN_WINDOW: timedelta = timedelta(days=1)


@dataclass(frozen=True)
class GroupProposal:
    """Several labels on one machine on one day, and which one should lead.

    Carries the episodes rather than replacing them — constraint 12. Splitting is always
    available because the proposal never became a fact.
    """

    equipment_key: str
    day: date
    primary: Episode
    held: tuple[Episode, ...]
    primary_reason: str

    #: Always `True`. Held as a field rather than a constant so it appears in the rendered
    #: proposal and in any serialisation, where a reader can see it.
    requires_confirmation: bool = True

    #: `RC19`'s shared-candidate-cause route needs reviewed differential content, which does
    #: not exist. Reported so a reader knows the grouping is by equipment-day alone.
    shared_cause_route_available: bool = False

    @property
    def episode_count(self) -> int:
        return 1 + len(self.held)

    @property
    def work_orders_avoided(self) -> int:
        """What the grouping would save if a human accepts it. Zero until they do."""
        return len(self.held)

    def render(self) -> str:
        held = ", ".join(e.fault_label for e in self.held)
        return (
            f"{self.equipment_key} on {self.day:%Y-%m-%d} carries {self.episode_count} "
            f"labels. Proposed: lead with {self.primary.fault_label} ({self.primary_reason}); "
            f"hold {held}. Nothing is grouped until someone accepts this, and it can be "
            f"split back into {self.episode_count} cases."
        )


def _is_determinate(label: str) -> bool:
    """A class that names a mechanism, rather than one whose own name says it cannot."""
    fault = faults.by_label(label)
    return bool(fault and not fault.declares_undecidable)


def choose_primary(
    episodes: tuple[Episode, ...], instrument_fault_label: str | None = None
) -> tuple[Episode, str]:
    """Which label leads, and the reason in words. Constraint 36.

    Order, and each step is a rule with a source rather than a preference:

    1. **An instrument fault leads.** `RC19` says so outright: if the reading is wrong,
       every other label on the machine may be an artefact of it, so they hold. The caller
       supplies the label because the taxonomy has no instrument-fault class — that verdict
       comes from `F16` and the signal provenance, not from `fault_label`.
    2. **A determinate class beats an undecidable one.** Constraint 36. The ambiguous class
       appeared on 12 of 12 fault days and is usually the longest-running; leading with it
       would title every event with the label that says least.
    3. **Alphabetical.** Deliberately arbitrary, and stated as such — see below.

    **Step 3 is a stable tie-break, not a ranking.** Sorting by severity would need severities
    that do not exist: only `CONDENSER_LOW_FLOW` has a sourced value and the rest render as
    words (`Q49`). Sorting by slot count is what constraint 36 forbids. So the order is
    alphabetical, which is reproducible and claims nothing — and `Q47` is where the real
    answer comes from.
    """
    if not episodes:
        raise ValueError("choose_primary needs at least one episode")

    if instrument_fault_label:
        for episode in episodes:
            if episode.fault_label == instrument_fault_label:
                return episode, (
                    "an instrument fault leads — the other labels on this machine may be "
                    "artefacts of the bad reading, so they hold rather than close"
                )

    determinate = [e for e in episodes if _is_determinate(e.fault_label)]
    pool = determinate or list(episodes)
    reason = (
        "a determinate class leads over one whose own name says it cannot separate the "
        "causes"
        if determinate
        else "every label here declares itself undecidable, so none of them leads on "
        "content; this is a stable order, not a ranking"
    )
    return min(pool, key=lambda e: e.fault_label), reason


def propose(
    episodes: tuple[Episode, ...], instrument_fault_label: str | None = None
) -> tuple[GroupProposal, ...]:
    """One proposal per equipment-day that carries more than one fault label.

    Days with a single label produce nothing — there is no grouping to propose, and
    manufacturing a one-episode "group" would inflate the saving this reports.
    """
    faulted = [e for e in episodes if _counts_as_fault(e.fault_label)]

    by_day: dict[tuple[str, date], list[Episode]] = {}
    for episode in faulted:
        by_day.setdefault((episode.equipment_key, episode.day), []).append(episode)

    proposals: list[GroupProposal] = []
    for (equipment_key, day), group in sorted(by_day.items()):
        if len(group) < 2:
            continue
        primary, reason = choose_primary(tuple(group), instrument_fault_label)
        held = tuple(sorted((e for e in group if e is not primary), key=lambda e: e.fault_label))
        proposals.append(
            GroupProposal(
                equipment_key=equipment_key,
                day=day,
                primary=primary,
                held=held,
                primary_reason=reason,
            )
        )
    return tuple(proposals)


def _counts_as_fault(label: str) -> bool:
    fault = faults.by_label(label)
    return bool(fault and fault.is_fault)


def relation_to_open(
    new_episode: Episode,
    open_episodes: tuple[Episode, ...],
    window: timedelta = REOPEN_WINDOW,
) -> tuple[Relation, Episode | None]:
    """Where a newly detected episode belongs. The `RC8` companion at the case layer.

    The same label on the same machine inside the window **reopens** — resolved here without
    asking anyone, because "is this the same label on the same machine" is identity rather
    than judgement. Everything else is either separate or a proposal.
    """
    for existing in open_episodes:
        if existing.equipment_key != new_episode.equipment_key:
            continue
        same_label = existing.fault_label == new_episode.fault_label
        if same_label and abs(new_episode.day - existing.day) <= window:
            return Relation.REOPEN, existing

    for existing in open_episodes:
        if (
            existing.equipment_key == new_episode.equipment_key
            and existing.day == new_episode.day
        ):
            return Relation.PROPOSED_GROUP, existing

    return Relation.SEPARATE, None


def inflation(episodes: tuple[Episode, ...]) -> tuple[int, int, int]:
    """`(naive cases, equipment-days, cases after every proposal is accepted)`.

    The third number is a **ceiling on the saving, not a plan**. Every proposal needs a human,
    so the real figure sits between the first and the third until someone works the queue —
    and reporting the third as though it had happened is the silent grouping `RC19` forbids.
    """
    faulted = tuple(e for e in episodes if _counts_as_fault(e.fault_label))
    naive = len(faulted)
    days = len({(e.equipment_key, e.day) for e in faulted})
    accepted = naive - sum(p.work_orders_avoided for p in propose(episodes))
    return naive, days, accepted
