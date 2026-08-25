"""`C23` untrusted-window marking — the heading that described a window the figures were not from.

**The failure this exists to prevent.** Anomaly counts were once shown on the database wall
clock under a heading describing a telemetry window that **did not overlap it at all**.
Nothing in that artefact was false on its own: the counts were real counts, the heading named
a real period, and the reader supplied the join between them. Inherited constraint 15 is the
answer — *every artefact states its data window* — and this module is where a window states
what is actually inside it.

**Our own measured window is untrusted on four separate counts.** It runs 2026-03-04 18:55 to
2026-06-23 11:50, 31,884 slots per chiller, and every one of these is true of it at once:

| Ground | On this window |
|---|---|
| It contains **derived** slots | The 2026-08-17 re-clone put **7,670** computed slots inside
  it, all carrying the method `derived:tr_from_load_v1` |
| It contains **simulated** slots | **Zero** today — the rebuilt source carries none. The
  guard stays, because a restore from a simulating source must fail here rather than quietly
  enter figures |
| The **detector was blind** over it | **5,309** slots are `NO_DIAGNOSIS` against **674**
  faulted, and **7,662** carry no label at all. Constraint 7: `NULL` means not diagnosed,
  never healthy — a two-month window was once blind rather than clean |
| A **signal it rests on** is unusable | `cond_flow` is `NEVER_MEASURED` — 0 non-zero in
  31,884 measured slots — and `chiller_flow` is `SUSPECT` |

**Collapsing those into one flag is the defect, not the tidy-up.** "Some of this was computed"
and "the detector said nothing here" are different statements with different remedies: the
first is fixed by labelling a figure, the second cannot be fixed at all and must be said out
loud. A single `untrusted=True` would let a reader who fixes one believe they had fixed the
other, so each ground is carried separately, in its own words, with its own count.

**No threshold, deliberately.** Nothing in the record says how much of a window may be
computed before it stops being a measurement, and inventing a fraction here would put a number
between the reader and a fact. **Any derived slot at all is worth saying so**, and the same
holds for every other ground.

**Constraint 16 — the honesty layer overrides the model, it does not advise it.** A reassuring
headline over a blind window is **replaced outright** and the record marked corrected. That is
`enforce_headline`: it returns the headline or its replacement, plus the fact that a correction
happened, so the correction is a record rather than a warning somebody may ignore.

**What this module deliberately does not decide.** What a report, an efficiency figure or a
model should *do* about an untrusted window is `Q26`, and it is open. This marks and states;
it never suppresses a figure and never withholds an artefact.

Pure functions and frozen dataclasses. No database, no model, no settings — contract 3.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.analytics.honesty import DataWindow
from app.domain.signals import SignalStatus


class Ground(StrEnum):
    """Why a window is untrusted. Five members for four causes, and the split is the point.

    The fourth cause — *a signal it rests on is `NEVER_MEASURED` or `SUSPECT`* — is carried as
    two grounds rather than one, because they are not the same claim. `cond_flow` has never
    been metered at this site and no restore will ever fix that; `chiller_flow` has an
    instrument that read credibly and then stopped. One is a capability the plant does not
    have, the other is a repair somebody could book.
    """

    DERIVED_SLOTS = "derived_slots"
    """Some values here were computed rather than read by an instrument.

    Derived is not simulated: a derivation is calibrated against readings the plant genuinely
    took, so the rule inherited with the data is *derived may be quoted, simulated may not*.
    It is still not a measurement, and quoting it requires a label no rendering path attaches
    yet."""

    SIMULATED_SLOTS = "simulated_slots"
    """Some values here were generated. They may not be quoted at all.

    Zero of these exist today. The guard is not dead code — the first clone carried 156,129
    simulated slots and fabricated `cond_flow` to a maximum of 893.7, a signal the site cannot
    measure. A future restore from a simulating source must fail on this ground."""

    DETECTOR_BLIND = "detector_blind"
    """The detector reached no verdict over part or all of this window.

    Constraint 7. An empty queue on a blind window reads as a clean plant, and a two-month
    window was blind rather than clean. A fault count here counts what was found, never what
    is there."""

    SIGNAL_NEVER_MEASURED = "signal_never_measured"
    """A signal this window rests on has never recorded a credible value at this site.

    Instrumentation, not a data defect. `cond_flow` feeds four of the six models and is 0
    non-zero in 31,884 measured slots of all three databases."""

    SIGNAL_SUSPECT = "signal_suspect"
    """A signal this window rests on reads, and other signals contradict it.

    Both chilled-water flow transmitters read near zero since May while ΔT and power stayed
    normal. Physically impossible, and a single-signal check did not catch it — `F16`."""


@dataclass(frozen=True)
class StatusRuling:
    """What one `SignalStatus` does to a window, and the words that say why.

    A table rather than a chain of comparisons, for the reason `authority.py` gives: a chain
    acquires an implicit ordering nobody declared, and a status that is *different in kind*
    then reads as *worse by degree*.
    """

    ground: Ground | None
    words: str


#: The decision table. Total over every `SignalStatus` member, and a test fails if a new one
#: is added without a ruling — silence about a status is the shape of the defect this feature
#: exists for, one level up.
SIGNAL_STATUS_RULING: dict[SignalStatus, StatusRuling] = {
    SignalStatus.MEASURED: StatusRuling(
        ground=None,
        words=(
            "an instrument reports it and the readings are usable, so it is not a ground for "
            "untrusting this window"
        ),
    ),
    SignalStatus.DERIVED: StatusRuling(
        ground=Ground.DERIVED_SLOTS,
        words=(
            "no instrument reports it; the value was computed from one that is. It may be "
            "quoted only as derived, and no rendering path attaches that label yet"
        ),
    ),
    SignalStatus.NEVER_MEASURED: StatusRuling(
        ground=Ground.SIGNAL_NEVER_MEASURED,
        words=(
            "no credible value has ever been recorded — the tag is wired and the meter is "
            "not. That is instrumentation, and no restore of the data will change it"
        ),
    ),
    SignalStatus.SUSPECT: StatusRuling(
        ground=Ground.SIGNAL_SUSPECT,
        words=(
            "readings exist and other signals contradict them, so the instrument may be the "
            "fault rather than the machine"
        ),
    ),
    # A constant tag is deliberately **not** a ground, and the words say so rather than the
    # table staying silent. It is not folded into `SIGNAL_SUSPECT` either: a frozen tag and a
    # contradicted one are different facts, and collapsing them here would be the exact defect
    # this module exists to prevent, committed inside its own decision table.
    #
    # TBD (Q68): whether a constant signal untrusts the *window* it rests on, or only the
    # figures computed from it. `dpt` is a flat 107.0 on chiller 1 and 112.9 on chiller 2, so
    # condenser approach temperature cannot be computed at all — that is a figure refusing,
    # which `honesty.Figure` already handles, and it is not obviously a statement about the
    # period. Answered the narrow way until somebody decides, and the words carry the doubt.
    SignalStatus.CONSTANT: StatusRuling(
        ground=None,
        words=(
            "the column never changes value — present, and carrying no information. Every "
            "figure computed from it is a stated absence, but that is a fact about the figure "
            "rather than about this period, so it is not counted as a ground here (`Q68`)"
        ),
    ),
}

#: Constraint 24's asymmetry, applied to a status nobody classified. Over-stating an untrusted
#: window costs a sentence a reader did not need; under-stating one is the incident at the top
#: of this file. Over-marking is the cheap error, so the default is a ground rather than
#: silence.
UNRULED_STATUS: StatusRuling = StatusRuling(
    ground=Ground.SIGNAL_SUSPECT,
    words=(
        "nobody has said what this signal's availability is, so it is treated as unusable — "
        "the stricter side, deliberately"
    ),
)

#: Headline wording that tells a reader there is nothing to worry about. Held as data so the
#: set is inspectable and widening it is a decision somebody made rather than a regular
#: expression that grew.
#:
#: TBD (Q67). No document fixes which phrasings count as reassuring, and this list is
#: engineering judgement rather than reviewed content. It can only ever cause a correction
#: that was not needed — a phrasing it misses is a headline that ships as written, which is
#: the pre-existing behaviour, so the failure direction is the safe one.
REASSURING_PHRASES: frozenset[str] = frozenset(
    {
        "all clear",
        "clean bill",
        "healthy",
        "no anomalies",
        "no faults",
        "no issues",
        "no problems",
        "nothing to report",
        "operating normally",
        "running normally",
        "within limits",
        "within normal",
        # Added 2026-08-17 after a test asked the obvious question and the list said no.
        # "Everything looks normal" is about as reassuring as English gets over a blind
        # window, and the original twelve phrases all missed it — they were written around
        # *fault* vocabulary rather than around reassurance. `Q67` is exactly this: which
        # phrasings count, and a blacklist is a blacklist. The three below are the ones a
        # model actually writes when it has nothing to say.
        "looks normal",
        "looks fine",
        "no concerns",
    }
)


@dataclass(frozen=True)
class Untrust:
    """One ground, with its count and the words a reader can act on.

    `slots` is `None` when the ground is not a count of slots — a never-measured signal is not
    *some slots*, it is the whole window resting on a measurement that does not exist. `None`
    renders as words and never as `0`, because zero would say the ground was checked and found
    empty.
    """

    ground: Ground
    words: str
    slots: int | None = None
    signal: str = ""

    def render(self) -> str:
        extent = f" ({self.slots:,} slots)" if self.slots is not None else ""
        subject = f"{self.signal}: " if self.signal else ""
        return f"{subject}{self.words}{extent}"


@dataclass(frozen=True)
class WindowContents:
    """What is actually inside a period, as counted rather than as claimed.

    The counts are supplied by whoever read the database; nothing here queries anything. That
    is contract 3, and it is also what lets the whole feature be tested with MySQL stopped.
    """

    window: DataWindow
    total_slots: int
    derived_slots: int = 0
    simulated_slots: int = 0
    unlabelled_slots: int = 0
    """Slots the detector produced no label for at all. 7,662 on the measured window."""

    refused_slots: int = 0
    """Slots labelled `NO_DIAGNOSIS`. **5,309** on the measured window, against 674 faulted.

    Counted separately from `unlabelled_slots` rather than added to it, because a refusal is
    not an error and it is not the same event as silence: the gates ran and closed. Both mean
    *not diagnosed*, so both feed the same ground — and the words keep them apart."""

    signal_statuses: Mapping[str, SignalStatus] = field(default_factory=dict)
    """The signals this window's figures rest on, and what the plant can say about each."""

    def __post_init__(self) -> None:
        """Refuse an impossible window at construction, the way `Figure` refuses a blank.

        A count larger than the window it sits in is a reading error somewhere upstream, and
        the one thing that must not happen is that it renders as a confident percentage.
        """
        counts = {
            "total_slots": self.total_slots,
            "derived_slots": self.derived_slots,
            "simulated_slots": self.simulated_slots,
            "unlabelled_slots": self.unlabelled_slots,
            "refused_slots": self.refused_slots,
        }
        for name, value in counts.items():
            if value < 0:
                raise ValueError(f"{name} is {value}; a slot count cannot be negative")
        for name, value in counts.items():
            if name != "total_slots" and value > self.total_slots:
                raise ValueError(
                    f"{name} is {value} in a window of {self.total_slots} slots — one of the "
                    f"two was read from somewhere else"
                )

    @property
    def undiagnosed_slots(self) -> int:
        """Slots carrying no verdict, by either route. Never read as *healthy* — constraint 7."""
        return self.unlabelled_slots + self.refused_slots

    @property
    def is_empty(self) -> bool:
        """No slots at all. Not a clean window — a window with nothing in it."""
        return self.total_slots == 0


@dataclass(frozen=True)
class WindowTrust:
    """`C23`'s verdict: the window, and every separate reason it may not be read plainly."""

    contents: WindowContents
    grounds: tuple[Untrust, ...]

    @property
    def is_trusted(self) -> bool:
        return not self.grounds

    @property
    def ground_kinds(self) -> tuple[Ground, ...]:
        """The distinct kinds present, in a stable order. Used where a caller needs the shape
        of the problem rather than the prose."""
        seen: list[Ground] = []
        for g in self.grounds:
            if g.ground not in seen:
                seen.append(g.ground)
        return tuple(seen)

    def window_statement(self) -> str:
        """Constraint 15. What every artefact over this window must carry, before anything else.

        The period, its source, and whether it is a snapshot — the three things the incident
        at the top of this file was missing.
        """
        return (
            f"Data window: {self.contents.window.render()}, "
            f"from the {self.contents.window.source}"
        )

    def trust_statement(self) -> str:
        """The verdict in words, in both directions.

        A trusted window says what it was checked *for*, deliberately. "Trusted" with nothing
        behind it reads as a certificate, and no window on this plant has earned one.
        """
        if self.is_trusted:
            return (
                "no ground for untrusting this window was found: it contains no derived and "
                "no simulated slots, the detector reached a verdict on every slot in it, and "
                "every signal it rests on is measured. That is the absence of a known "
                "problem, not a guarantee about the plant."
            )
        return (
            f"this window is untrusted on {len(self.ground_kinds)} separate grounds, and they "
            f"are different facts with different remedies: "
            + "; ".join(g.render() for g in self.grounds)
        )

    def render(self) -> str:
        return f"{self.window_statement()}. {self.trust_statement()}"

    def as_dict(self) -> dict:
        return {
            "window": self.contents.window.as_dict(),
            "window_statement": self.window_statement(),
            "trusted": self.is_trusted,
            "trust_statement": self.trust_statement(),
            "grounds": [
                {
                    "ground": g.ground.value,
                    "signal": g.signal,
                    "slots": g.slots,
                    "words": g.words,
                    "rendered": g.render(),
                }
                for g in self.grounds
            ],
        }


def assess(contents: WindowContents) -> WindowTrust:
    """Every reason this window may not be read plainly, each stated once and separately.

    Order is fixed rather than by severity: provenance first (*can these numbers be quoted at
    all?*), then the detector (*was anything actually judged here?*), then the signals
    underneath. That is the same reading order `validity.py` uses, and for the same reason —
    interpreting a number before establishing whether it can be believed is the ordering that
    produced two months of invalid efficiency figures.
    """
    grounds: list[Untrust] = []

    if contents.derived_slots:
        grounds.append(
            Untrust(
                ground=Ground.DERIVED_SLOTS,
                slots=contents.derived_slots,
                words=(
                    f"{contents.derived_slots:,} of {contents.total_slots:,} slots in this "
                    f"window were computed rather than read by an instrument. A derivation is "
                    f"calibrated against readings the plant genuinely took, so it may be "
                    f"quoted — but only as derived, and no rendering path attaches that label "
                    f"yet. No amount is small enough to go unsaid, because nothing states how "
                    f"much of a window may be computed before it stops being a measurement"
                ),
            )
        )

    if contents.simulated_slots:
        grounds.append(
            Untrust(
                ground=Ground.SIMULATED_SLOTS,
                slots=contents.simulated_slots,
                words=(
                    f"{contents.simulated_slots:,} of {contents.total_slots:,} slots in this "
                    f"window were generated rather than measured, and a generated value may "
                    f"not be quoted at all. The rebuilt source carries none of these; a "
                    f"restore that reintroduces them fails here rather than entering figures "
                    f"quietly"
                ),
            )
        )

    if contents.is_empty:
        grounds.append(
            Untrust(
                ground=Ground.DETECTOR_BLIND,
                slots=0,
                words=(
                    "this window contains no slots at all, so nothing in it was judged. An "
                    "empty window is not a clean one, and a count of faults over it is a "
                    "count of nothing rather than a finding of nothing"
                ),
            )
        )
    elif contents.undiagnosed_slots:
        grounds.append(
            Untrust(
                ground=Ground.DETECTOR_BLIND,
                slots=contents.undiagnosed_slots,
                words=(
                    f"the detector reached no verdict on {contents.undiagnosed_slots:,} of "
                    f"{contents.total_slots:,} slots — {contents.unlabelled_slots:,} carry no "
                    f"label at all and {contents.refused_slots:,} are NO_DIAGNOSIS, which is "
                    f"a refusal rather than a silence. NULL means not diagnosed, never "
                    f"healthy: a fault count over this window counts what was found, not what "
                    f"is there"
                ),
            )
        )

    for key in sorted(contents.signal_statuses):
        ruling = SIGNAL_STATUS_RULING.get(contents.signal_statuses[key], UNRULED_STATUS)
        if ruling.ground is None:
            continue
        grounds.append(Untrust(ground=ruling.ground, words=ruling.words, signal=key))

    return WindowTrust(contents=contents, grounds=tuple(grounds))


@dataclass(frozen=True)
class HeadlineRuling:
    """Constraint 16's output: what ships, what was written, and whether it was replaced.

    `was_corrected` never travels alone. A record that says only *corrected* leaves the next
    reader with a flag and no way to find out what happened — which is how a correction turns
    into folklore about the tool being fussy.
    """

    headline: str
    original: str
    was_corrected: bool
    words: str

    @property
    def survived(self) -> bool:
        return not self.was_corrected

    def render(self) -> str:
        if not self.was_corrected:
            return self.headline
        return f"{self.headline} [corrected: {self.words}]"

    def as_dict(self) -> dict:
        return {
            "headline": self.headline,
            "original": self.original,
            "was_corrected": self.was_corrected,
            "words": self.words,
        }


def reads_as_reassuring(headline: str) -> tuple[bool, str]:
    """Does this headline tell a reader there is nothing to worry about, and which words did it?

    Returns the matched phrases with the verdict, because a correction a reader cannot trace
    to a phrase is one they will read as arbitrary.
    """
    lowered = headline.lower()
    hits = tuple(sorted(p for p in REASSURING_PHRASES if p in lowered))
    if not hits:
        return False, "this headline claims nothing reassuring about the window"
    return True, "it says " + ", ".join(f"{h!r}" for h in hits)


def enforce_headline(
    headline: str,
    trust: WindowTrust,
    *,
    stated_window: DataWindow | None = None,
) -> HeadlineRuling:
    """Constraint 16. The honesty layer **overrides** the headline; it does not annotate it.

    Two corrections, in this order, and each replaces the headline outright:

    1. **The heading names a period the figures are not from.** This is the incident constraint
       15 exists for, and it is checked first because it is a mislabelling rather than an
       overstatement: correcting the tone of a headline that is attached to the wrong window
       would leave the worse error in place.
    2. **A reassuring headline sits over an untrusted window.** Replaced, and the record marked
       corrected.

    Anything else survives as written — including a non-reassuring headline over an untrusted
    window, which is honest already. The window statement still travels with it, because
    constraint 15 applies to every artefact and not only to corrected ones.
    """
    if stated_window is not None and not _overlaps(stated_window, trust.contents.window):
        replacement = (
            f"{trust.window_statement()}. The heading described "
            f"{stated_window.render()}, which does not overlap the window these figures were "
            f"computed over, so the heading was replaced rather than the figures reinterpreted"
        )
        return HeadlineRuling(
            headline=replacement,
            original=headline,
            was_corrected=True,
            words=(
                f"the heading named {stated_window.render()} while the figures come from "
                f"{trust.contents.window.render()}, and the two periods do not overlap at all"
            ),
        )

    reassuring, why = reads_as_reassuring(headline)

    if reassuring and not trust.is_trusted:
        replacement = f"{trust.window_statement()}. {trust.trust_statement()}"
        return HeadlineRuling(
            headline=replacement,
            original=headline,
            was_corrected=True,
            words=(
                f"the headline reassured over an untrusted window — {why} — and this window "
                f"is untrusted on {len(trust.ground_kinds)} grounds. It was replaced rather "
                f"than flagged, because a flag beside a reassuring sentence is still a "
                f"reassuring sentence"
            ),
        )

    if reassuring:
        return HeadlineRuling(
            headline=headline,
            original=headline,
            was_corrected=False,
            words=(
                "the headline reassures, and no ground for untrusting this window was found, "
                "so it stands as written"
            ),
        )

    return HeadlineRuling(
        headline=headline,
        original=headline,
        was_corrected=False,
        words=why,
    )


def _overlaps(stated: DataWindow, actual: DataWindow) -> bool:
    """Do the heading's period and the figures' period share any instant at all?

    Overlap rather than equality, deliberately. A heading that rounds *2026-03-04 18:55 to
    2026-06-23 11:50* to *March to June* is describing the same data and is not the incident;
    a heading naming a period the figures never touched is.
    """
    return stated.start <= actual.end and actual.start <= stated.end
