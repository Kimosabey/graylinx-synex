"""The defects found on 2026-08-17, one named test each. **These keep fixed bugs fixed.**

Every test below fails against the version of the code that shipped that morning. That is the
entry requirement for this file: a regression guard that passes against the broken code is a
comment with a test framework around it — and that has already happened here once, when the
unit test written to catch a truncated figure passed against the containment bug it was
written for.

Five defects, and **four of them are the same defect wearing different clothes**: an operator
that was nearly right. Containment instead of a word boundary. Containment instead of value
comparison. An exemption scoped to the answer instead of to the sentence. One absence standing
in for two. In each case the code did something reasonable to the case somebody tested and
something confidently wrong to its neighbour.

| Defect | Where | Found by |
|---|---|---|
| `"chiller 1" in "chiller 12"` routed a question to the wrong machine | `app/agents/router.py`
  | the adversarial suite |
| A figure typeset with U+2212 was reported as fabricated | `app/agents/postcheck.py` | the
  first real box run |
| The no-diagnosis exemption was answer-wide, so one honest sentence excused every other one |
  `app/agents/postcheck.py` | the adversarial suite |
| A review backlog was reported as a hole in the library | `app/domain/followup.py` |
  adversarial review |
| A withheld reading was echoed in the note explaining why it was withheld | `RC18` | this
  session's review |

The last one is the odd one out and the most dangerous shape: the refusal itself leaked the
thing it was refusing.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pytest

from app.agents.postcheck import (
    _pack_strings,
    audit_never_measured,
    audit_no_diagnosis_by_model,
    audit_numbers,
)
from app.agents.router import _extract_equipment
from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.domain import followup
from app.domain.cases import Checklist, ChecklistItem, Stage
from app.domain.signals import SignalStatus
from app.domain.stored_readings import (
    ITEM_SIGNAL,
    MAX_OFFER_AGE,
    OfferState,
    StoredReading,
    offer_for,
)
from app.services.evidence import build_pack, window_for

DAY = date(2026, 4, 15)
MEASURED_END = datetime(2026, 6, 23, 11, 50)

#: Chiller 1's own reference band. The healthy median is −25.645 and the band never approaches
#: zero, which is why a residual is judged against this rather than against nothing.
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(label: str = "HIGH_HEAD_AMBIGUOUS"):
    """An evidence pack for one slot on chiller 1 — the real builder, not a stub.

    The signal registry's notes travel in it, and those notes are where the typeset minus
    actually lives: `condenser leaving temperature ... reaches −273.2 on both chillers`.
    A stub would have to fake that character, and then the test would be about the stub.
    """
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    return build_pack(
        rows=(ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), label, values),),
        bands=(BAND,),
        gates=GateOutcome((check_running({"chiller_current": 141.0}),)),
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
    )


# ── 1 · containment is the wrong operator for an identifier ─────────────────────

def test_a_question_about_chiller_12_is_not_answered_about_chiller_1() -> None:
    """**Found 2026-08-17 by the adversarial suite.** `"chiller 1" in "chiller 12"` is `True`.

    The router matched equipment by containment, so a question naming a machine that does not
    exist on this two-chiller site was answered about chiller 1 — confidently, with real
    figures, about the wrong asset. The worst class of wrong answer: everything in it is true
    of something.

    The fix is a word boundary. This test fails against the containment version.
    """
    assert _extract_equipment("how is chiller 12 doing?", None) is None, (
        "a machine that does not exist resolved to one that does"
    )
    assert _extract_equipment("how is chiller 1 doing?", None) == "chiller_1"
    assert _extract_equipment("how is chiller 2 doing?", None) == "chiller_2"


def test_the_containment_operator_really_does_get_this_wrong() -> None:
    """The control. Without it this file would assert a fix against a bug it never had.

    Containment says yes; a word boundary says no. The same two operators disagree on
    `-25.6` inside `-25.645`, which is defect 2 below — the shape has now appeared twice.
    """
    text = "how is chiller 12 doing?"
    assert "chiller 1" in text, "containment matches, which is exactly the defect"
    assert re.search(r"\bchiller 1\b", text) is None, "a word boundary does not"


def test_a_machine_that_does_not_exist_is_still_refused_at_the_audit() -> None:
    """The second half of the same failure, one layer along. Even if a wrong machine reached
    an answer, naming it must fail a hard audit — a model naming `chiller 3` on a two-chiller
    site is the most convincing kind of wrong."""
    finding = audit_numbers("nothing numeric here", _pack())
    assert finding.passed, "the fixture itself must not be the thing that fails"

    from app.agents.postcheck import audit_equipment

    assert audit_equipment("chiller 3 is running hot", _pack()).passed is False
    assert audit_equipment("chiller 1 is running hot", _pack()).passed is True


# ── 2 · a typeset minus is the same number as an ASCII one ──────────────────────

def test_a_figure_the_pack_states_with_a_unicode_minus_is_not_reported_as_invented() -> None:
    """**Found 2026-08-17 on the first real box run.**

    The pack said `−273.2` with U+2212 MINUS SIGN, because the signal registry's notes are
    typeset prose quoting a measured fact. The model replied `-273.2` with an ASCII hyphen.
    The tokeniser read the pack's copy as *positive* 273.2, so the same figure appeared on the
    two sides as two different numbers and the audit reported a fabrication.

    **That failure is worse than the one the audit guards against.** A fabricated number is
    caught by a reader who checks. A false accusation of fabrication silently withholds a
    correct answer, and nobody ever looks at what was suppressed.
    """
    pack = _pack()
    pack_text = _pack_strings(pack)

    assert "−273.2" in pack_text, "the fixture must genuinely carry the typeset character"
    assert "-273.2" not in pack_text, (
        "if the pack held the ASCII form too, this test would pass without the translation "
        "and prove nothing"
    )

    answer = (
        "Condenser leaving temperature reaches -273.2 on both chillers, which is absolute "
        "zero used as a sensor sentinel rather than a temperature. Window: 2026-04-15."
    )
    finding = audit_numbers(answer, pack)
    assert finding.passed, (
        f"a correctly quoted figure was reported as invented: {finding.offending}"
    )


def test_a_truncated_figure_is_still_caught_now_that_the_minus_is_normalised() -> None:
    """The fix must not have widened the audit. `−6,265` is in the pack; `-6,26` is not, and
    a truncated figure in a report about instrumentation is a different claim.

    Exact equality, never a tolerance — a tolerance has to be chosen, and every choice
    forgives some fabrication.
    """
    finding = audit_numbers("efficiency ranges from -6,26 upward. Window: 2026-04-15.", _pack())
    assert finding.passed is False
    assert "-626" in finding.offending, finding.offending


def test_normalising_the_minus_did_not_start_quoting_a_never_measured_signal() -> None:
    """The audit next door, checked because the two read the same answer text. Condenser flow
    has never recorded a non-zero value, and a normalisation change must not make a sentence
    quoting it as a reading start to pass."""
    quoted = audit_never_measured(
        "condenser flow is -12.5 on this machine", _pack()
    )
    assert quoted.passed is False
    assert "condenser flow" in quoted.offending

    stated = audit_never_measured(
        "condenser flow has never been measured on this plant", _pack()
    )
    assert stated.passed is True, "mentioning it is correct; quoting a value for it is not"


# ── 3 · the no-diagnosis exemption is scoped to the sentence ────────────────────

def test_naming_the_pack_label_in_one_sentence_does_not_excuse_a_diagnosis_in_another() -> None:
    """**Found 2026-08-17 by the adversarial suite.**

    The exemption was answer-wide: any answer mentioning the pack's own label *anywhere* had
    every non-"definitely" diagnosis phrase filtered out. So this shipped —

        "The rules flagged HIGH_HEAD_AMBIGUOUS. The root cause is a fouled condenser."

    The first sentence explains. The second narrows an undecidable class into a specific
    mechanism the trained model explicitly declined to name, which is the separation law's
    fourth row and precisely what this audit exists to catch.

    The label is written with spaces rather than underscores because that is the only form
    the exemption recognises — `audit_no_diagnosis_by_model` compares against
    `fault_label.lower().replace("_", " ")`. Written with underscores this test would pass
    against the broken version too, since the exemption would never have fired at all. That
    mismatch is itself a defect, and it is `Q82`.
    """
    finding = audit_no_diagnosis_by_model(
        "The rules flagged HIGH HEAD AMBIGUOUS. The root cause is a fouled condenser.",
        _pack("HIGH_HEAD_AMBIGUOUS"),
    )
    assert finding.passed is False, (
        "one honest sentence excused a diagnosis in the next one — the exemption is "
        "answer-wide again"
    )
    assert "the root cause is" in finding.offending


def test_the_exemption_still_works_where_the_label_and_the_phrase_share_a_sentence() -> None:
    """The fix must not have removed the exemption, only scoped it. Explaining the label the
    rules produced is the model's whole job, and an audit that forbade that would push every
    honest answer into evasive phrasing."""
    finding = audit_no_diagnosis_by_model(
        "HIGH HEAD AMBIGUOUS means the root cause is not separable from this evidence.",
        _pack("HIGH_HEAD_AMBIGUOUS"),
    )
    assert finding.passed is True, finding.offending


def test_no_phrasing_excuses_a_first_person_verdict() -> None:
    """Some phrases assert a verdict whatever else is in the sentence. There is no reading of
    *"I diagnose"* in which the model is relaying somebody else's conclusion, so naming the
    pack's label in the same sentence must not launder it."""
    for answer in (
        "HIGH HEAD AMBIGUOUS was flagged and I diagnose a fouled condenser.",
        "HIGH HEAD AMBIGUOUS was flagged and this is definitely a fouled condenser.",
    ):
        finding = audit_no_diagnosis_by_model(answer, _pack("HIGH_HEAD_AMBIGUOUS"))
        assert finding.passed is False, answer


# ── 4 · a review backlog is not a hole in the library ───────────────────────────

def test_a_review_backlog_is_not_reported_as_a_content_hole() -> None:
    """**Found 2026-08-17 in adversarial review.**

    `obligation_gap`'s empty branch asserted *"no preventive item was attached, so there is
    nothing to own"* outright. Since `sme_reviewed` defaults to `False` and nothing in the
    124-item library has been read by a refrigeration engineer, that fired for **all 30
    preventive items** — reporting a hole in the content where the truth was a queue of
    review work that will clear.

    They are opposite situations and only one of them is somebody's next task. A hole in the
    library is content nobody has written; a backlog is content nobody has read.
    """
    owned, text_only, why = followup.obligation_gap((), unreviewed_preventive=30)

    assert (owned, text_only) == (0, 0)
    assert "the review is missing, not the content" in why
    assert "30 preventive item(s) exist" in why


def test_a_genuine_content_hole_still_says_so() -> None:
    """The other half. If the fix had made every empty result read as a backlog, the real gap
    — a fault class the library never covered — would have become invisible instead."""
    owned, text_only, why = followup.obligation_gap((), unreviewed_preventive=0)

    assert (owned, text_only) == (0, 0)
    assert "an absence of content" in why
    assert "review" not in why, "an unwritten item is not an unread one"


def test_the_two_absences_never_produce_the_same_sentence() -> None:
    """Stated as the property rather than as two examples, because the whole argument of
    `app/domain/followup.py` is that these must never look identical on a screen."""
    backlog = followup.obligation_gap((), unreviewed_preventive=30)[2]
    hole = followup.obligation_gap((), unreviewed_preventive=0)[2]
    assert backlog != hole
    assert backlog.strip() and hole.strip(), "an absence is words, never a blank"


def test_an_unreviewed_stage_attachment_names_the_review_rather_than_the_library() -> None:
    """The same distinction one level up, where a case attaches its follow-ups. A stage whose
    items exist but are unread reports the review; a stage with no items reports the gap."""
    unread = Checklist(
        fault_label="CONDENSER_LOW_FLOW",
        items=(
            ChecklistItem(
                id="prev-1",
                text="trend the condenser approach weekly",
                stage=Stage.PREVENTIVE,
                sme_reviewed=False,
            ),
        ),
    )
    follow_up = followup.attach_follow_ups(_root_cause(), unread)
    attachments = {a.stage: a for a in follow_up.attachments}

    preventive = attachments[Stage.PREVENTIVE].absence_reason
    assert "none has been read by a refrigeration engineer" in preventive
    assert "Nothing is missing from the library; the review is." in preventive

    corrective = attachments[Stage.CORRECTIVE].absence_reason
    assert "gap in the library" in corrective, (
        "a stage the library never covered must not borrow the backlog's wording"
    )


def _root_cause() -> followup.RootCause:
    """The confirmed cause a follow-up hangs off.

    `confirmed_by` is populated because an unevidenced confirmation reports itself in words,
    and that sentence would then be the one under test instead of the absence reasons.
    """
    return followup.RootCause(
        cause_id="fouled-condenser",
        label="Fouled condenser",
        confirmed_by=("approach temperature measured at the panel",),
    )


# ── 5 · a refusal must not leak the thing it is refusing ────────────────────────

def _item(item_id: str, *, blocking: bool = False) -> ChecklistItem:
    return ChecklistItem(
        id=item_id,
        text="read the value at the panel and record it",
        blocking=blocking,
        sme_reviewed=True,
        is_sample=True,
    )


#: The value a withheld reading is holding. Chosen because it is the one the simulation
#: fabricated for `cond_flow` — a maximum of 893.7 on a plant with no condenser flow meter.
WITHHELD_DISPLAY = "893.7"


@pytest.mark.parametrize(
    "status,method",
    [
        (SignalStatus.NEVER_MEASURED, ""),
        (SignalStatus.DERIVED, "derived:tr_from_load_v1"),
    ],
    ids=["never-measured", "derived"],
)
def test_a_withheld_stored_reading_is_never_echoed_in_the_note_that_withholds_it(
    status: SignalStatus, method: str
) -> None:
    """**Found 2026-08-17 in review of `RC18`.**

    A refusal that quotes the number it is refusing to show has not refused anything. The
    reader takes the figure and discards the sentence around it — *"the stored reading was
    893.7, but we cannot vouch for it"* is read as *"893.7"*, and then a technician carries a
    fabricated condenser flow to a panel that has no flow meter behind it.

    This is the `cond_flow` defect arriving through the door marked *helpfulness*. The
    withholding branch states the reason in words and shows no value at all.
    """
    reading = StoredReading(
        signal_key=ITEM_SIGNAL["tech-flow"],
        display=WITHHELD_DISPLAY,
        recorded_at=datetime(2026, 4, 15, 9, 0),
        status=status,
        method=method,
    )
    offer = offer_for(_item("tech-flow"), reading, now=datetime(2026, 4, 15, 9, 30))

    assert offer.shows_a_value is False
    assert WITHHELD_DISPLAY not in offer.text, (
        f"the withholding note quoted the value it withheld: {offer.text!r}"
    )
    assert offer.state is not OfferState.OFFERED
    assert offer.text.strip(), "a refusal carries its reason in words, never a blank"
    assert "confirm at the panel" not in offer.text, (
        "confirmation wording beside a withheld value reads as an offer to confirm it"
    )


def test_a_stale_reading_states_its_age_without_stating_its_value() -> None:
    """The same rule for the fourth withholding reason. A real reading about a different day
    is still a number a reader will anchor to, and the age is the part that matters."""
    recorded = datetime(2026, 4, 12, 9, 0)
    now = recorded + MAX_OFFER_AGE + timedelta(hours=2)
    reading = StoredReading(
        signal_key=ITEM_SIGNAL["tech-dp"], display="141.0", recorded_at=recorded
    )
    offer = offer_for(_item("tech-dp", blocking=True), reading, now=now)

    assert offer.state is OfferState.WITHHELD_STALE
    assert offer.shows_a_value is False
    assert "141.0" not in offer.text, offer.text
    assert "day" in offer.text, "the age is what a reader needs instead of the number"


def test_an_offered_reading_does_show_its_value_and_still_settles_nothing() -> None:
    """The control, and `RC18`'s second rule. If withholding were the only path this file
    would pass against a module that never offered anything — and the feature exists to save
    a walk to a panel.

    A shown value is still not a gauge reading now: constraint 20, and `settles_a_blocking_item`
    is a constant rather than a calculation so that no combination of freshness and provenance
    can compute its way to `True`.
    """
    reading = StoredReading(
        signal_key=ITEM_SIGNAL["tech-dp"],
        display="141.0",
        recorded_at=datetime(2026, 4, 15, 9, 0),
    )
    offer = offer_for(
        _item("tech-dp", blocking=True), reading, now=datetime(2026, 4, 15, 9, 30)
    )

    assert offer.state is OfferState.OFFERED
    assert "141.0" in offer.text
    assert "confirm at the panel" in offer.text
    assert offer.settles_a_blocking_item is False
    assert "only a reading taken now settles it" in offer.text
