"""`RC18`. The database already held four of the readings the checklist sent someone to take.

**The failure.** Item 18 of the inherited gap register: oil pressure, compressor balance,
condenser approach and ambient temperature were all columns on the same normalised row the
model had just read — and the checklist still told a technician to go and take them. That is
two losses at once. Somebody walks to a panel to fetch a number the platform is holding, and
the model reasons about a fault while blind to a signal sitting in the row it read. It is the
`MODEL_BLIND` defect, diagnosed there as *"the library knew; the evidence pack did not carry
it"* and then fixed for that one fact rather than generalised. D-008.

**The failure the obvious fix causes.** A number in the snapshot is not a gauge reading now.
Of the five signals on this plant whose provenance has actually been measured, **not one is
offerable**: `cond_flow` is 0 non-zero in 37,430 measured slots, `dpt` is a flat 107.0 on
chiller 1 and 112.9 on chiller 2, and `chiller_flow`, `cond_leaving_temp` and `kw_per_tr` are
each contradicted by other signals on the same circuit. On a plant that reads like that,
showing a stored value as though it were a measurement is a worse hazard than the walk.

So `RC18` is two rules, and the second is what makes the first safe:

| | Rule | Why |
|---|---|---|
| 20 | A stored reading **never settles a blocking check** | An estimate does not settle a
  blocking gate — on the reference plant an untagged answer defaulted to `estimated` and
  opened one. A stored value is weaker still, because nobody has even looked. Accepting an
  offer here produces `ESTIMATED`, which `may_advance` already refuses |
| — | It is offered as a **confirmation**, never as the answer | *"the stored reading was X —
  confirm at the panel"*. Never *"this is"*. The wording is the feature as much as the
  behaviour is |

**Why a derived value is withheld rather than labelled.** The 2026-08-17 re-clone replaced
156,129 simulated slots with 12,589 **derived** ones, 7,670 of them inside the measured
window, all carrying the method `derived:tr_from_load_v1`. The rule inherited with the data
is *derived may be quoted, simulated may not* — quoted **with its label**, and nothing in
this product attaches one yet. A computed number rendered as *"the stored reading was X"*
reads as an instrument reading, which is the `cond_flow` defect entering by a different door.
So the derived path withholds and says the word rather than dressing the number up.

**Where provenance comes from, and what the registry is for here.** `app/db/provenance.py`
computes availability per column from the two marker tables, and it is the authority; that
verdict travels on the reading itself. `app/domain/signals.py` is used as a **veto**: where
it names a signal and calls it unusable, that overrules whatever the caller claims about the
value. An unregistered signal is judged on the reading's own provenance, because the registry
covers 5 of a normalised table's 38 columns and treating its silence as a refusal would
withhold every honest reading on the plant.

**Nothing here calls a model.** `RC18` is `SW` in the register, and this module imports only
its two domain siblings.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.domain import signals
from app.domain.cases import Checklist, ChecklistItem, Finding, FindingKind
from app.domain.signals import SignalStatus

#: How old a stored reading may be and still be worth offering as a confirmation.
#:
#: TBD (Q64). **No document fixes this**, so it is a named constant with the question against
#: it rather than a figure buried in a comparison. One day, because that is the unit the case
#: itself uses: inherited constraint 35 keys a case to one (equipment, fault, **day**), so a
#: reading from outside that span describes a different day's plant and comparing it to a
#: panel now claims more than anybody knows.
#:
#: The direction of the error is what makes the choice safe to make here rather than wait for
#: an answer. Withholding costs a look at a panel the checklist item already instructs;
#: offering a stale value anchors a technician to a number the machine has moved past. It
#: never opens a gate, never suppresses a check and never hides a reading — the item stands
#: as written either way. Every entry point takes it as a parameter.
MAX_OFFER_AGE: timedelta = timedelta(days=1)


class OfferState(StrEnum):
    """What became of one pairing. **Eight outcomes, and exactly one of them shows a value.**

    They are kept apart rather than collapsed into offered/not-offered because the reasons
    are not interchangeable: *we hold nothing* and *we hold something we will not show you*
    send a reader to different places, and *this was computed* is a statement about our own
    data that somebody needs to see.
    """

    OFFERED = "offered"
    """A measured, contemporaneous value, shown for confirmation at the panel."""

    NOT_PAIRED = "not_paired"
    """No signal is paired to this item. Not a refusal — the platform is not claiming to hold
    the answer. The pairing table grows with the curated library."""

    NOTHING_STORED = "nothing_stored"
    """The item is paired and no value was passed for it. Reported rather than skipped: a
    paired item with nothing behind it is a gap in the evidence pack, which is `Q39`."""

    WITHHELD_NEVER_MEASURED = "withheld_never_measured"
    """The site has never measured this signal. `cond_flow` is 0 non-zero in 37,430 measured
    slots — the tag is wired, the meter is not."""

    WITHHELD_DERIVED = "withheld_derived"
    """The value was computed, not read, and no rendering path labels it as such."""

    WITHHELD_CONSTANT = "withheld_constant"
    """The column never changes. Present, carrying nothing — `dpt` at a flat 107.0."""

    WITHHELD_SUSPECT = "withheld_suspect"
    """Other signals on the same circuit contradict it, so it is not evidence about the
    machine."""

    WITHHELD_STALE = "withheld_stale"
    """Older than `MAX_OFFER_AGE`. A real reading, about a different day."""


#: One withholding state per provenance that is not `MEASURED`, held as a map rather than as
#: a chain of comparisons so that a new `SignalStatus` forces a decision here. The failure
#: this shape prevents is a status nobody thought about falling through to *offered* — which
#: is exactly how `DERIVED` would have arrived, since it did not exist until 2026-08-17.
WITHHELD_STATE: dict[SignalStatus, OfferState] = {
    SignalStatus.NEVER_MEASURED: OfferState.WITHHELD_NEVER_MEASURED,
    SignalStatus.DERIVED: OfferState.WITHHELD_DERIVED,
    SignalStatus.CONSTANT: OfferState.WITHHELD_CONSTANT,
    SignalStatus.SUSPECT: OfferState.WITHHELD_SUSPECT,
}

#: Why each one is withheld, in the words a reader gets. Every refusal carries its reason —
#: never a dash, never a blank space where a number would have been.
WITHHELD_BECAUSE: dict[SignalStatus, str] = {
    SignalStatus.NEVER_MEASURED: (
        "this site has never measured it, so there is no stored value to confirm — the tag "
        "is wired and the meter is not"
    ),
    SignalStatus.DERIVED: (
        "the value held for it was computed from other signals rather than read from an "
        "instrument, and nothing on this screen can label it as derived. Shown as a stored "
        "reading it would pass for a measurement, which is the defect condenser flow taught "
        "us arriving through a different door"
    ),
    SignalStatus.CONSTANT: (
        "the column holds the same value in every slot, so it is present and carrying "
        "nothing. A tag frozen in software looks identical to a working one in the historian"
    ),
    SignalStatus.SUSPECT: (
        "the readings held for it are contradicted by other signals on the same circuit, so "
        "the stored value is not evidence about the machine"
    ),
}

#: Which checklist item asks for which signal. `RC18`'s mechanism is this map plus the
#: refusals above, held as data rather than written into the case builder so that it can be
#: reviewed line by line beside the library it belongs to.
#:
#: **It covers the sample items only, and that is the honest state.** The curated library is
#: 124 items across 11 fault classes plus a 7-item generic fallback, and no refrigeration
#: engineer has read one of them, so there are no reviewed item ids to pair against yet. The
#: table grows with the SME hour; until then an unpaired item reports `NOT_PAIRED` rather
#: than guessing at a column. The four readings the gap register found — oil pressure,
#: compressor balance, condenser approach and ambient — are `Q39`, and only the third has a
#: signal here whose provenance anybody has measured.
ITEM_SIGNAL: dict[str, str] = {
    # Condenser approach, and the one the gap register named. It resolves to a refusal
    # rather than to a number: `dpt` is a constant, which is why approach cannot be computed
    # at all (`Q8`). The right answer to "we already hold this" is sometimes "and it is
    # worthless".
    "op-approach": "dpt",
    # Never measured on this plant. Paired deliberately, so the case says so in words
    # instead of leaving a blank beside the item.
    "tech-flow": "cond_flow",
    # The measured case, on a blocking item. Discharge pressure feeds the DP model, so the
    # plant reads it — and the offer still does not settle the check.
    "tech-dp": "discharge_pressure",
}


def _plural(count: int, unit: str) -> str:
    return f"{count} {unit}" if count == 1 else f"{count} {unit}s"


def _age_words(age: timedelta) -> str:
    """A duration in words. Never a bare number, and never rounded up into a nicer one."""
    minutes = int(age.total_seconds() // 60)
    if minutes < 60:
        return _plural(minutes, "minute")
    hours = minutes // 60
    if hours < 24:
        return _plural(hours, "hour")
    return _plural(hours // 24, "day")


@dataclass(frozen=True)
class StoredReading:
    """One value the database already holds, carrying its own age and provenance.

    **`display` is a string and never a float.** The pack carries display strings so the
    numeric audit can compare exact values; a float would force a tolerance, and every
    tolerance forgives some fabrication. This module therefore never formats a number — it
    only decides whether the string the back end produced may be shown at all.
    """

    signal_key: str
    display: str
    recorded_at: datetime

    status: SignalStatus = SignalStatus.MEASURED
    """The verdict for **this value**, not for the column. `snapshot_derived_slots` marks
    slots rather than columns, and 7,670 of them fall inside the measured window — so a
    signal the plant genuinely measures can still hand back a computed reading."""

    method: str = ""
    """How the value got there when it was not read. `derived:tr_from_load_v1` is the only
    method on this database. Empty for a measured reading, because there is no method: an
    instrument reported it."""

    def age_at(self, now: datetime) -> timedelta:
        return now - self.recorded_at

    def is_stale_at(self, now: datetime, max_age: timedelta = MAX_OFFER_AGE) -> bool:
        return self.age_at(now) > max_age


@dataclass(frozen=True)
class Offer:
    """What the case shows beside one checklist item. Always words, never an empty space."""

    item_id: str
    state: OfferState
    text: str
    signal_key: str = ""
    reading: StoredReading | None = None
    item_is_blocking: bool = False

    @property
    def shows_a_value(self) -> bool:
        return self.state is OfferState.OFFERED

    @property
    def settles_a_blocking_item(self) -> bool:
        """**Always `False`, and it is a constant rather than a calculation.**

        Inherited constraint 20 by way of `RC10`: an estimate does not settle a blocking
        check, and a stored value is weaker than an estimate because nobody has looked yet.
        Deriving this from freshness and provenance would leave a combination that computes
        its way to `True` — a reading taken four minutes ago from a healthy instrument is
        still not a gauge reading now.
        """
        return False

    def as_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "signal_key": self.signal_key,
            "state": self.state.value,
            "text": self.text,
            "shows_a_value": self.shows_a_value,
            "settles_a_blocking_item": self.settles_a_blocking_item,
            "item_is_blocking": self.item_is_blocking,
            "recorded_at": self.reading.recorded_at.isoformat() if self.reading else None,
            "provenance": self.reading.status.value if self.reading else None,
            "method": self.reading.method if self.reading else "",
        }


#: What accepting an offer without going to the panel produces. **Never `MEASURED`**, and
#: named here so the claim is one line somebody can find rather than a literal in a function.
ACCEPTED_AS: FindingKind = FindingKind.ESTIMATED


def _display_name(signal_key: str) -> str:
    registered = signals.by_key(signal_key)
    return registered.display_name if registered else signal_key


def _withheld(
    item: ChecklistItem, signal_key: str, reading: StoredReading, status: SignalStatus, cited: str
) -> Offer:
    return Offer(
        item_id=item.id,
        state=WITHHELD_STATE[status],
        signal_key=signal_key,
        reading=reading,
        item_is_blocking=item.blocking,
        text=(
            f"No stored reading is offered for {_display_name(signal_key)}: "
            f"{WITHHELD_BECAUSE[status]} ({cited}). Take the reading at the panel, or record "
            f"cannot-check — the item stands as written."
        ),
    )


def offer_for(
    item: ChecklistItem,
    reading: StoredReading | None,
    *,
    now: datetime,
    max_age: timedelta = MAX_OFFER_AGE,
) -> Offer:
    """Pair one checklist item with one stored value, and decide whether it may be shown.

    Six outcomes and one refusal to guess, in this order:

    1. **No pairing.** The platform is not claiming to hold this. Not a refusal.
    2. **Nothing stored.** Paired and empty, which is a gap in the evidence pack (`Q39`).
    3. **The registry vetoes it.** Where `app/domain/signals.py` names the signal and calls
       it unusable, that overrules whatever the caller says about the value. A caller
       claiming a measured `cond_flow` is wrong about a plant that has never metered it.
    4. **This value was not read.** Derived, or from a column that is constant or
       contradicted. Withheld with the word said out loud.
    5. **Too old.** A real reading about a different day.
    6. **Offered** — for confirmation, never as the answer.

    A reading whose `signal_key` does not match the pairing raises, because the two disagree
    about which column the item is asking for and quietly trusting either one would put a
    number from the wrong instrument under the right question.
    """
    signal_key = ITEM_SIGNAL.get(item.id)
    if signal_key is None:
        return Offer(
            item_id=item.id,
            state=OfferState.NOT_PAIRED,
            item_is_blocking=item.blocking,
            text=(
                "No signal is paired to this item, so the platform is not holding an answer "
                "to it. Nothing is claimed either way."
            ),
        )

    if reading is None:
        return Offer(
            item_id=item.id,
            state=OfferState.NOTHING_STORED,
            signal_key=signal_key,
            item_is_blocking=item.blocking,
            text=(
                f"This item is paired to {_display_name(signal_key)} and no stored value was "
                f"carried into the case. Nothing is being withheld — there is nothing there."
            ),
        )

    if reading.signal_key != signal_key:
        raise ValueError(
            f"item {item.id!r} is paired to {signal_key!r} and was handed a reading for "
            f"{reading.signal_key!r}; one of the two is wrong and neither may be guessed"
        )

    registered = signals.by_key(signal_key)
    if registered is not None and not registered.is_usable:
        return _withheld(
            item, signal_key, reading, registered.status, "the measured provenance of this signal"
        )

    if reading.status is not SignalStatus.MEASURED:
        cited = f"method {reading.method}" if reading.method else "the provenance of this value"
        return _withheld(item, signal_key, reading, reading.status, cited)

    age = reading.age_at(now)
    if reading.is_stale_at(now, max_age):
        return Offer(
            item_id=item.id,
            state=OfferState.WITHHELD_STALE,
            signal_key=signal_key,
            reading=reading,
            item_is_blocking=item.blocking,
            text=(
                f"No stored reading is offered for {_display_name(signal_key)}: the newest "
                f"value held is {_age_words(age)} old, past the {_age_words(max_age)} this "
                f"case treats as contemporaneous, so it describes a different day's plant. "
                f"Take the reading at the panel."
            ),
        )

    # The words say it as well as the gate enforcing it. Leaving it to `may_advance` means
    # the person holding the gauge finds out by pressing accept and watching nothing happen.
    blocking_note = (
        " A blocking check — only a reading taken now settles it." if item.blocking else ""
    )
    return Offer(
        item_id=item.id,
        state=OfferState.OFFERED,
        signal_key=signal_key,
        reading=reading,
        item_is_blocking=item.blocking,
        text=(
            f"The stored reading for {_display_name(signal_key)} was {reading.display}, "
            f"recorded {reading.recorded_at:%Y-%m-%d %H:%M}, {_age_words(age)} ago — confirm "
            f"at the panel.{blocking_note}"
        ),
    )


def attach(
    checklist: Checklist,
    readings: dict[str, StoredReading],
    *,
    now: datetime,
    max_age: timedelta = MAX_OFFER_AGE,
) -> tuple[Offer, ...]:
    """Offers for the paired items on one checklist, keyed by signal.

    **Over `visible_items` rather than every item**, because that is the SME gate: an
    unreviewed instruction is not shown to anybody, so there is nothing for a stored reading
    to sit beside. Attaching to a hidden item would put library content on screen through a
    side door, which is inherited constraint 1 defeated by a helper.

    Unpaired items are dropped rather than returned. `offer_for` still answers for them, so
    the single-item call stays total, but a case listing *"no signal is paired to this"*
    against a strainer inspection is noise that buries the two lines that matter.
    """
    offers: list[Offer] = []
    for item in checklist.visible_items():
        signal_key = ITEM_SIGNAL.get(item.id)
        if signal_key is None:
            continue
        offers.append(
            offer_for(item, readings.get(signal_key), now=now, max_age=max_age)
        )
    return tuple(offers)


def accept_without_checking(offer: Offer, note: str = "") -> Finding:
    """Somebody took the stored reading as the answer instead of walking to the panel.

    That is an **estimate**, and tagging it as one is the whole of `RC18`'s half of `RC10`.
    On the reference plant an untagged answer defaulted to `estimated` and opened a blocking
    gate; here the tag is not a default that could drift but the only value this function can
    produce, so `may_advance` keeps the gate shut without knowing anything about `RC18`.
    """
    if not offer.shows_a_value or offer.reading is None:
        raise ValueError(
            f"no stored reading was offered for {offer.item_id!r} ({offer.state.value}), so "
            f"there is nothing to accept — this is a defect in the caller, not a finding"
        )
    return Finding(
        item_id=offer.item_id,
        kind=ACCEPTED_AS,
        value=offer.reading.display,
        note=(
            f"Taken from the stored reading of {offer.reading.recorded_at:%Y-%m-%d %H:%M} "
            f"without confirming at the panel, so it is recorded as an estimate and does not "
            f"settle a blocking check.{' ' + note if note else ''}"
        ),
    )


def confirm_at_the_panel(offer: Offer, display: str, note: str = "") -> Finding:
    """The reading was taken at the machine. **The only route here that opens a gate.**

    The stored value travels in the note beside the confirmed one, deliberately. This plant's
    instruments are demonstrably unreliable — a chilled-water transmitter read near zero for
    two months while ΔT and power stayed normal — so a confirmation that disagrees with the
    snapshot is a finding about the instrument, and losing the comparison would throw that
    away. Where nothing was stored, the note says that rather than leaving the field empty.

    **A withheld value stays withheld here.** Found in adversarial review, 2026-08-17: this
    used to print `offer.reading.display` whenever a reading existed, which quoted back the
    exact number `offer_for` had just refused to show — a never-measured, derived, constant,
    suspect or stale value arriving in the findings record as though it were a comparison.
    The gate is `shows_a_value`, the same property the case surface reads, so the two cannot
    disagree about what was shown.
    """
    if offer.shows_a_value and offer.reading is not None:
        stored = (
            f"the stored reading was {offer.reading.display} at "
            f"{offer.reading.recorded_at:%Y-%m-%d %H:%M}"
        )
    elif offer.reading is not None:
        stored = (
            f"a stored value exists and was not shown, because {offer.state.value}"
            f" — so there is nothing to compare this against"
        )
    else:
        stored = "nothing was stored for this item to compare against"
    return Finding(
        item_id=offer.item_id,
        kind=FindingKind.MEASURED,
        value=display,
        note=f"Confirmed at the panel; {stored}.{' ' + note if note else ''}",
    )


def offerable_signal_keys() -> tuple[str, ...]:
    """Registered signals a stored reading could ever be offered for. **Empty, today.**

    Every one of the five signals whose provenance has been hand-verified on this plant is
    unusable — never measured, constant, or contradicted by its neighbours — so `RC18`'s
    mechanism currently renders refusals and nothing else. That is not a shortcoming of the
    feature; it is the plant, stated rather than papered over, and it is what the case screen
    should be showing a reader today.
    """
    return tuple(s.key for s in signals.SIGNALS if s.is_usable)
