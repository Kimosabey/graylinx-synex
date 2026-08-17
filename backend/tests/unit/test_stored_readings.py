"""`RC18` — a stored reading is a confirmation, never the answer.

Two incidents sit behind these tests and they pull in opposite directions, which is why the
feature needs proving in both directions at once.

**The first.** Four readings the checklist sent a technician to take — oil pressure,
compressor balance, condenser approach, ambient — were columns on the same normalised row the
model had just read. Somebody walked to a panel for a number the platform was holding.

**The second.** On the reference plant an untagged answer defaulted to `estimated` and opened
a blocking gate. A number in the snapshot is not a gauge reading now, and this plant's
instruments are demonstrably unreliable: condenser flow is 0 non-zero in 37,430 measured
slots, `dpt` is a flat 107.0, and a chilled-water transmitter read near zero for two months
while ΔT and power stayed normal.

So the proof that matters is not that a stored value appears. It is that it appears **and
settles nothing** — and that the values this plant should never show do not appear at all.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain import stored_readings
from app.domain.cases import (
    Capability,
    Checklist,
    ChecklistItem,
    FindingKind,
    may_advance,
)
from app.domain.signals import SignalStatus
from app.domain.stored_readings import (
    ITEM_SIGNAL,
    MAX_OFFER_AGE,
    WITHHELD_BECAUSE,
    WITHHELD_STATE,
    Offer,
    OfferState,
    StoredReading,
    accept_without_checking,
    attach,
    confirm_at_the_panel,
    offer_for,
    offerable_signal_keys,
)

#: A moment inside the measured window, so nothing here depends on a wall clock.
NOW = datetime(2026, 4, 15, 14, 30)
RECENT = datetime(2026, 4, 15, 14, 25)

#: The real sample items. `tech-dp` is blocking, which is the one that matters: it is the
#: item where an offer that settled anything would open a gate on a value nobody read.
TECH_DP = ChecklistItem(
    id="tech-dp",
    text="Measure discharge pressure at the gauge and compare with the panel value.",
    capability=Capability.TECHNICIAN,
    blocking=True,
    sme_reviewed=True,
    is_sample=True,
)
TECH_FLOW = ChecklistItem(
    id="tech-flow",
    text="Measure condenser water flow at the pump discharge.",
    capability=Capability.TECHNICIAN,
    blocking=True,
    sme_reviewed=True,
    is_sample=True,
)
OP_APPROACH = ChecklistItem(
    id="op-approach",
    text="Read condenser entering and leaving water temperatures from the panel.",
    capability=Capability.OPERATOR,
    sme_reviewed=True,
    is_sample=True,
)
OP_STRAINER = ChecklistItem(
    id="op-strainer",
    text="Check the condenser water strainer for visible blockage.",
    capability=Capability.OPERATOR,
    sme_reviewed=True,
    is_sample=True,
)

#: **The pressure strings below are placeholders, not plant readings.** No document states a
#: discharge pressure for these machines, and `RC18` never formats, compares or interprets a
#: value — it decides whether the string the back end produced may be shown at all. So the
#: fixture needs a string and nothing more, and putting an invented figure forward as a
#: measurement would be the failure the tests above are about. Every number that *is* real
#: here — 107.0, 0.0, 893.7, 1.40 — is quoted from `CONTEXT.md`.
FRESH_DP = StoredReading(
    signal_key="discharge_pressure",
    display="812.4 kPa",
    recorded_at=RECENT,
)


def _offer(item: ChecklistItem, reading: StoredReading | None, now: datetime = NOW) -> Offer:
    return offer_for(item, reading, now=now)


# ── the rule the feature exists for ────────────────────────────────────────────

def test_a_stored_reading_never_settles_a_blocking_check() -> None:
    """Constraint 20, by way of `RC10`. The reading is real, fresh and measured, sitting on a
    blocking item — every reason a design might have to let it count — and it still does not.

    Written as an assertion on the property rather than on the state, because the failure to
    prevent is a future combination of freshness and provenance computing its way to `True`.
    """
    offer = _offer(TECH_DP, FRESH_DP)
    assert offer.state is OfferState.OFFERED
    assert offer.shows_a_value is True
    assert offer.settles_a_blocking_item is False


def test_accepting_the_offer_leaves_the_blocking_gate_exactly_where_it_was() -> None:
    """The end-to-end version, through the gate `RC5` already owns.

    On the reference plant an untagged answer defaulted to `estimated` and opened a blocking
    gate. `may_advance` knows nothing about `RC18`; it only knows that a blocking item needs a
    measured answer — so the protection holds without the gate being taught a new rule.
    """
    checklist = Checklist(fault_label="CONDENSER_LOW_FLOW", items=(TECH_DP,))
    finding = accept_without_checking(_offer(TECH_DP, FRESH_DP))

    assert finding.kind is FindingKind.ESTIMATED
    assert finding.settles_a_blocking_item is False

    ok, why = may_advance(checklist, {finding.item_id: finding})
    assert ok is False
    assert "tech-dp (estimated)" in why
    assert "Only a measured reading settles a blocking check" in why


def test_only_a_reading_taken_at_the_panel_opens_the_gate() -> None:
    """The other half of the same proof. If nothing opened the gate the feature would be
    indistinguishable from refusing to show stored readings at all."""
    checklist = Checklist(fault_label="CONDENSER_LOW_FLOW", items=(TECH_DP,))
    finding = confirm_at_the_panel(_offer(TECH_DP, FRESH_DP), "804.1 kPa")

    assert finding.kind is FindingKind.MEASURED
    ok, why = may_advance(checklist, {finding.item_id: finding})
    assert ok is True
    assert why


def test_a_confirmation_records_the_stored_value_it_disagreed_with() -> None:
    """A chilled-water transmitter read near zero for two months while ΔT and power stayed
    normal. A panel reading that disagrees with the snapshot is a finding about the
    instrument, and dropping the comparison would throw that away."""
    finding = confirm_at_the_panel(_offer(TECH_DP, FRESH_DP), "804.1 kPa")
    assert "812.4 kPa" in finding.note
    assert finding.value == "804.1 kPa"


def test_a_confirmation_with_nothing_stored_says_so_rather_than_leaving_it_blank() -> None:
    """An absence is a stated absence, not an empty field — including inside a note."""
    finding = confirm_at_the_panel(_offer(OP_STRAINER, None), "clear")
    assert "nothing was stored" in finding.note


# ── what must never be offered at all ──────────────────────────────────────────

def test_a_never_measured_signal_is_not_offered_at_all() -> None:
    """Condenser flow is 0 non-zero in 37,430 measured slots. Offering *"the stored reading
    was 0"* would imply an instrumentation capability the site does not have, which is the
    claim `C26` and D-009 exist to make impossible."""
    reading = StoredReading(
        signal_key="cond_flow", display="0.0 m3/h", recorded_at=RECENT
    )
    offer = _offer(TECH_FLOW, reading)
    assert offer.state is OfferState.WITHHELD_NEVER_MEASURED
    assert offer.shows_a_value is False
    assert "0.0 m3/h" not in offer.text
    assert "never measured it" in offer.text


def test_a_derived_value_is_withheld_because_computed_is_not_read() -> None:
    """The re-clone put 7,670 derived slots inside the measured window, all carrying
    `derived:tr_from_load_v1`. Derived may be quoted *with its label*, and nothing on this
    screen attaches one — so rendering it as *"the stored reading"* would be the condenser
    flow defect entering through a different door."""
    reading = StoredReading(
        signal_key="discharge_pressure",
        display="790.0 kPa",
        recorded_at=RECENT,
        status=SignalStatus.DERIVED,
        method="derived:tr_from_load_v1",
    )
    offer = _offer(TECH_DP, reading)
    assert offer.state is OfferState.WITHHELD_DERIVED
    assert "790.0 kPa" not in offer.text
    assert "derived:tr_from_load_v1" in offer.text
    assert "computed" in offer.text


def test_a_constant_column_is_withheld_because_a_stuck_tag_reads_like_a_working_one() -> None:
    """`dpt` is a flat 107.0 on chiller 1 and 112.9 on chiller 2, which is why condenser
    approach cannot be computed at all (`Q8`). The gap register named this reading as one the
    platform already held — and the honest answer is that holding it is worth nothing."""
    reading = StoredReading(signal_key="dpt", display="107.0 kPa", recorded_at=RECENT)
    offer = _offer(OP_APPROACH, reading)
    assert offer.state is OfferState.WITHHELD_CONSTANT
    assert "107.0" not in offer.text
    assert "frozen in software" in offer.text


def test_the_provenance_registry_overrules_a_caller_claiming_a_measured_condenser_flow() -> None:
    """The veto, and the reason it is not merely advice. A caller that computed availability
    wrongly, or a fixture written from the simulated window, would hand back `MEASURED` for a
    signal the plant has never metered — and the case would show a fabricated capability."""
    reading = StoredReading(
        signal_key="cond_flow",
        display="893.7 m3/h",
        recorded_at=RECENT,
        status=SignalStatus.MEASURED,
    )
    offer = _offer(TECH_FLOW, reading)
    assert offer.state is OfferState.WITHHELD_NEVER_MEASURED
    assert "893.7" not in offer.text


def test_an_unregistered_signal_is_judged_on_the_readings_own_provenance() -> None:
    """The registry covers 5 of a normalised table's 38 columns. Treating its silence as a
    refusal would withhold every honest reading on the plant, so the computed provenance that
    travels with the reading decides — and `app/db/provenance.py` is where it comes from."""
    from app.domain import signals

    assert signals.by_key("discharge_pressure") is None
    assert _offer(TECH_DP, FRESH_DP).state is OfferState.OFFERED


def test_no_signal_on_this_plant_is_currently_offerable() -> None:
    """Stated rather than papered over: every one of the five signals whose provenance has
    been hand-verified is never-measured, constant or contradicted. `RC18`'s mechanism today
    renders refusals and nothing else, and that is the plant rather than the feature."""
    assert offerable_signal_keys() == ()


# ── the staleness window ───────────────────────────────────────────────────────

def test_a_reading_older_than_the_window_is_withheld_rather_than_shown() -> None:
    """A real, measured value about a different day. Constraint 35 keys a case to one
    (equipment, fault, day), so a reading outside that span is not describing this case."""
    old = StoredReading(
        signal_key="discharge_pressure",
        display="812.4 kPa",
        recorded_at=NOW - timedelta(days=3),
    )
    offer = _offer(TECH_DP, old)
    assert offer.state is OfferState.WITHHELD_STALE
    assert "812.4 kPa" not in offer.text
    assert "3 days old" in offer.text
    assert "different day's plant" in offer.text


def test_an_offered_reading_states_its_own_age_rather_than_implying_it_is_now() -> None:
    """*"The stored reading was X"* with no timestamp reads as *"X is the reading"*. The age
    is what makes the sentence a confirmation instead of an answer."""
    offer = _offer(TECH_DP, FRESH_DP)
    assert "5 minutes ago" in offer.text
    assert "2026-04-15 14:25" in offer.text


def test_the_staleness_window_is_a_parameter_because_no_document_fixes_it() -> None:
    """`MAX_OFFER_AGE` is `TBD (Q64)`. It carries a default so the behaviour is defined, and
    it is a parameter everywhere so the answer costs one call site rather than an edit."""
    old = StoredReading(
        signal_key="discharge_pressure",
        display="812.4 kPa",
        recorded_at=NOW - timedelta(days=3),
    )
    assert MAX_OFFER_AGE.days == 1
    assert offer_for(TECH_DP, old, now=NOW, max_age=timedelta(days=7)).state is OfferState.OFFERED
    assert offer_for(TECH_DP, FRESH_DP, now=NOW, max_age=timedelta(minutes=1)).state is (
        OfferState.WITHHELD_STALE
    )


def test_widening_the_window_still_does_not_let_a_stored_reading_settle_anything() -> None:
    """Whatever `Q64` is answered with, the constraint above it does not move."""
    old = StoredReading(
        signal_key="discharge_pressure",
        display="812.4 kPa",
        recorded_at=NOW - timedelta(days=3),
    )
    offer = offer_for(TECH_DP, old, now=NOW, max_age=timedelta(days=365))
    assert offer.shows_a_value is True
    assert offer.settles_a_blocking_item is False


# ── the pairing, held as data ──────────────────────────────────────────────────

def test_an_unpaired_item_claims_nothing_rather_than_guessing_a_column() -> None:
    """The curated library has not been reviewed, so most items have no pairing yet. *"No
    signal is paired to this"* is a different statement from *"we hold nothing"*, and guessing
    a column would put a number from the wrong instrument under the right question."""
    offer = _offer(OP_STRAINER, None)
    assert offer.state is OfferState.NOT_PAIRED
    assert offer.signal_key == ""
    assert "not holding an answer" in offer.text


def test_a_paired_item_with_nothing_stored_says_so_rather_than_going_quiet() -> None:
    """A paired item with nothing behind it is a gap in the evidence pack — `Q39`, which is
    the question `RC18` was registered against. Silence there reads as *checked and clean*."""
    offer = _offer(TECH_FLOW, None)
    assert offer.state is OfferState.NOTHING_STORED
    assert offer.signal_key == "cond_flow"
    assert "there is nothing there" in offer.text


def test_a_reading_for_the_wrong_column_is_a_defect_and_not_a_silent_mismatch() -> None:
    """The pairing table and the reading disagree about which instrument the item asks for.
    Trusting either one would file a number from one signal under a question about another."""
    wrong = StoredReading(signal_key="kw_per_tr", display="1.40 kW/TR", recorded_at=RECENT)
    with pytest.raises(ValueError, match="one of the two is wrong"):
        _offer(TECH_DP, wrong)


def test_accepting_an_offer_that_was_never_made_is_refused() -> None:
    """A withheld offer has no value in it. Letting the caller accept one would manufacture a
    finding out of a refusal, which is the shape of every failure in this module."""
    withheld = _offer(TECH_FLOW, StoredReading("cond_flow", "0.0 m3/h", RECENT))
    with pytest.raises(ValueError, match="nothing to accept"):
        accept_without_checking(withheld)


def test_every_provenance_that_is_not_measured_has_a_state_and_a_reason_in_words() -> None:
    """`DERIVED` did not exist until 2026-08-17 and arrived carrying 7,670 slots inside the
    measured window. A status nobody thought about must not fall through to *offered*, so the
    map is asserted complete rather than the branches being trusted."""
    for status in SignalStatus:
        if status is SignalStatus.MEASURED:
            continue
        assert status in WITHHELD_STATE, f"{status.value} would fall through to offered"
        assert WITHHELD_BECAUSE[status].strip(), f"{status.value} withholds without a reason"


def test_the_pairing_table_names_only_signals_that_exist_or_are_measured_columns() -> None:
    """A pairing to a column nobody can produce would render `NOTHING_STORED` for ever and
    look like a data gap rather than a typing mistake."""
    assert ITEM_SIGNAL["op-approach"] == "dpt"
    assert ITEM_SIGNAL["tech-flow"] == "cond_flow"
    assert ITEM_SIGNAL["tech-dp"] == "discharge_pressure"


# ── the wording, which is half the feature ─────────────────────────────────────

def test_the_offer_asks_for_confirmation_and_never_asserts_the_value() -> None:
    """D-008 fixed the wording as well as the behaviour. *"This is 812.4"* about a value
    nobody has looked at is the hazard; *"the stored reading was 812.4 — confirm at the
    panel"* is the same information without the claim."""
    text = _offer(TECH_DP, FRESH_DP).text
    assert "The stored reading for" in text
    assert "confirm at the panel" in text
    assert "this is" not in text.lower()


def test_a_blocking_item_says_out_loud_that_only_a_reading_taken_now_settles_it() -> None:
    """The person holding the gauge is the one who has to know. Leaving it to the gate means
    they find out by pressing accept and watching nothing happen."""
    assert "only a reading taken now settles it" in _offer(TECH_DP, FRESH_DP).text
    assert "settles it" not in _offer(OP_APPROACH, None).text


@pytest.mark.parametrize(
    "item,reading",
    [
        (TECH_DP, FRESH_DP),
        (TECH_FLOW, StoredReading("cond_flow", "0.0 m3/h", RECENT)),
        (OP_APPROACH, StoredReading("dpt", "107.0 kPa", RECENT)),
        (TECH_FLOW, None),
        (OP_STRAINER, None),
        (
            TECH_DP,
            StoredReading("discharge_pressure", "812.4 kPa", NOW - timedelta(days=3)),
        ),
    ],
)
def test_every_outcome_carries_its_reason_in_words(
    item: ChecklistItem, reading: StoredReading | None
) -> None:
    """Never a bare bool, never a dash, never a zero standing in for an absence. Every one of
    the eight outcomes has to be readable by whoever is standing at the machine."""
    offer = _offer(item, reading)
    assert offer.text.strip()
    assert offer.text.rstrip().endswith("."), "a truncated sentence reads as a failed render"
    assert offer.as_dict()["text"] == offer.text
    assert offer.as_dict()["settles_a_blocking_item"] is False


# ── attaching to a checklist ───────────────────────────────────────────────────

def test_an_unreviewed_item_gets_no_offer_because_it_is_not_on_screen() -> None:
    """Inherited constraint 1: no unreviewed instruction directing physical work reaches a
    user. Attaching a stored reading to a hidden item would put library content on screen
    through a side door — the gate defeated by a helper rather than by a decision."""
    hidden = ChecklistItem(
        id="tech-dp",
        text="Measure discharge pressure at the gauge.",
        capability=Capability.TECHNICIAN,
        blocking=True,
        sme_reviewed=False,
    )
    checklist = Checklist(fault_label="HIGH_HEAD_AMBIGUOUS", items=(hidden,))
    assert attach(checklist, {"discharge_pressure": FRESH_DP}, now=NOW) == ()


def test_attach_returns_one_offer_per_paired_item_and_stays_quiet_about_the_rest() -> None:
    """A case listing *"no signal is paired to this"* against a strainer inspection buries the
    two lines that matter under noise nobody reads."""
    checklist = Checklist(
        fault_label="CONDENSER_LOW_FLOW",
        items=(OP_STRAINER, TECH_FLOW, TECH_DP),
    )
    offers = attach(
        checklist,
        {
            "cond_flow": StoredReading("cond_flow", "0.0 m3/h", RECENT),
            "discharge_pressure": FRESH_DP,
        },
        now=NOW,
    )
    assert [o.item_id for o in offers] == ["tech-flow", "tech-dp"]
    assert [o.state for o in offers] == [
        OfferState.WITHHELD_NEVER_MEASURED,
        OfferState.OFFERED,
    ]


def test_the_module_calls_no_model_and_reaches_nothing() -> None:
    """`RC18` is `SW`. It must decide the same way with the GPU terminated and MySQL stopped,
    which is contract 4 in `importlinter.ini` — asserted here as well, because a domain module
    that grew an import would fail the layering test with a message about layers rather than
    about this feature."""
    source = stored_readings.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in ("app.llm", "app.services", "app.db", "httpx", "sqlalchemy"):
        assert forbidden not in text, f"{forbidden} reached a domain module"
