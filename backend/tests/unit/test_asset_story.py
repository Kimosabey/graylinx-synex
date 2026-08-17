"""`A1` one equipment story — and the section that says what cannot be said about the asset.

**The failure these tests exist to prevent** is a one-page asset view that lists health,
models, faults and open work and stops there. On this plant that page is a lie of omission,
and every omission has been measured: condenser flow has **0 non-zero values in 37,430
measured slots** while feeding four of the five fitted models; `dpt` is a flat constant so
condenser approach temperature cannot be computed at all (`Q8`); the chilled-water flow
transmitter died on **2026-04-22** while its column went on filling; the same model runs at
**nRMSE 48.03** on chiller 1 against **2.65** on chiller 2; and the sixth designed model is
not fitted anywhere in the measured window.

A page listing five models, nine labels and a work queue would tell a reader the machine is
understood. That is the reassuring lie, and the tests below are what keep it unavailable.

Three defects were found by writing them, all of the same shape — **two different absences
rendered as one**. They are named in the tests that caught them:
`test_a_dead_instrument_is_not_a_contradicted_signal`,
`test_nobody_looked_and_we_looked_and_found_nothing_do_not_render_alike`, and
`test_an_asset_carrying_no_fit_is_not_told_how_far_apart_two_other_fits_are`.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.analytics.episodes import Episode
from app.domain import correlation, faults, residuals, signals
from app.domain import equipment as eq
from app.domain.signals import SignalStatus
from app.services import asset_story
from app.services.asset_story import (
    CannotSay,
    DiagnosisLine,
    ModelLine,
    OpenItem,
    SignalNote,
    Silence,
    build,
    cannot_say_for,
    diagnosis_lines,
    model_lines,
    widest_fit_gap,
)
from app.services.evidence import window_for

WINDOW = window_for(date(2026, 4, 15), datetime(2026, 6, 23, 11, 50))

#: 31,884 in-window slots per chiller, of which 7,670 are derived since the 2026-08-17
#: re-clone. Carried here because several tests below are about what those two numbers mean
#: when a page reports a window rather than a machine.
IN_WINDOW_SLOTS = 31_884
DERIVED_IN_WINDOW = 7_670

DAY = date(2026, 4, 15)

#: The measured labels, with the slot counts the trained model actually emitted. Nine classes:
#: 5,309 `NO_DIAGNOSIS` and 943 `NO_EFFICIENCY_FAULT` against **674 faulted slots** across the
#: seven fault classes. Taken from `app.domain.faults` rather than typed again, so a change to
#: the measured truth breaks these tests instead of quietly disagreeing with them.
MEASURED_SLOTS: dict[str, int] = {f.label: f.measured_slots for f in faults.FAULT_CLASSES}


def _episode(label: str, equipment: str = "chiller_1", day: date = DAY) -> Episode:
    return Episode(
        equipment_key=equipment,
        fault_label=label,
        day=day,
        slot_count=MEASURED_SLOTS[label],
        first_slot=datetime.combine(day, datetime.min.time()),
        last_slot=datetime.combine(day, datetime.max.time()),
    )


#: Every label the reference plant produced, on one machine on one day. Real classes and real
#: counts — no invented label appears anywhere in this file.
ALL_LABELS: tuple[Episode, ...] = tuple(_episode(label) for label in MEASURED_SLOTS)


def _story(key: str = "chiller_1", **kw):
    kw.setdefault("episodes", ALL_LABELS)
    return build(key, window=WINDOW, **kw)


def _subjects(story, kind: Silence) -> set[str]:
    return {c.subject for c in story.silences_of(kind)}


def _section(story, heading: str) -> list[str]:
    """The lines under one heading of the rendered page, without the heading itself."""
    lines = story.render().splitlines()
    start = lines.index(f"{heading}:") + 1
    body: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            break
        body.append(line.strip())
    return body


# ── the claim the module makes about itself ────────────────────────────────────

@pytest.mark.parametrize("key", [e.key for e in eq.scoreable_equipment()])
def test_the_last_section_is_never_empty_for_a_scoreable_asset(key: str) -> None:
    """The module's central promise, and the only thing separating this page from the
    reassuring lie. A scoreable chiller on this plant has a never-measured meter, a frozen
    transmitter, a dead flow instrument and a model that was never fitted — so a page with
    nothing in its last section has stopped assembling that section, not found a clean
    machine."""
    assert _story(key).cannot_say


def test_what_cannot_be_said_is_the_last_thing_on_the_page() -> None:
    """Order is the argument. A reader who stops halfway has read the capabilities and not the
    limits, so the limits are not halfway — they are where a reader stops."""
    rendered = _story().render()
    assert rendered.index("What cannot be said about it") > rendered.index("Models:")
    assert rendered.index("What cannot be said about it") > rendered.index("Open against it:")
    assert rendered.rstrip().endswith(_story().cannot_say[-1].render())


def test_the_silence_that_removes_the_most_from_the_page_leads_the_section() -> None:
    """*No reference band* changes what every other line on the page means, so it cannot sit
    below a note about one signal. The order is a fixed reading order and never a ranking by
    magnitude — constraint 3 forbids importance derived from size, and it would be the same
    mistake wearing a different hat here."""
    story = _story("condenser_pump_1")
    assert story.cannot_say[0].silence is Silence.NO_REFERENCE_BAND
    order = [asset_story.SILENCE_ORDER.index(c.silence) for c in story.cannot_say]
    assert order == sorted(order)


def test_every_page_states_its_data_window() -> None:
    """Constraint 15. Anomaly counts were once shown on the database wall clock under a
    heading describing a telemetry window that did not overlap it at all."""
    assert WINDOW.render() in _story().render()


# ── two absences must not become one ───────────────────────────────────────────

def test_a_dead_instrument_is_not_a_contradicted_signal() -> None:
    """**Defect found by this test.** `SignalStatus.SUSPECT` is one word covering two
    different failures, and `_signal_silence` mapped every one of them to
    `SIGNAL_CONTRADICTED`. `Silence.INSTRUMENT_STOPPED` was defined, documented and placed in
    the reading order, and nothing could ever produce it.

    The two send a reader to different places, which is the module's own stated reason for
    keeping twelve kinds apart: `chiller_flow`'s transmitter *died* on a date this module
    already knows and prints, and that is a work order somebody raises; `cond_leaving_temp` is
    *contradicted* by its own circuit, and that is `F16` and a mislabelled column. Fixed with
    `SUSPECT_SILENCE`."""
    story = _story()
    assert "chiller_flow" in _subjects(story, Silence.INSTRUMENT_STOPPED)
    assert "chiller_flow" not in _subjects(story, Silence.SIGNAL_CONTRADICTED)
    assert "cond_leaving_temp" in _subjects(story, Silence.SIGNAL_CONTRADICTED)


def test_every_kind_of_silence_the_module_names_can_actually_be_reached() -> None:
    """A distinction nothing can produce is a vocabulary word, not a distinction — and it is
    indistinguishable from the collapse it was written to prevent. This is the test that found
    `INSTRUMENT_STOPPED` unreachable, so it is kept general: any future kind added to
    `Silence` and never emitted fails here rather than reading as a promise the page keeps."""
    reachable: set[Silence] = set()
    for key in ("chiller_1", "condenser_pump_1"):
        for supplied in (ALL_LABELS, None):
            story = build(
                key,
                window=WINDOW,
                episodes=supplied,
                signal_notes=(
                    SignalNote("tr", SignalStatus.DERIVED, "computed by derived:tr_from_load_v1"),
                ),
            )
            reachable |= {c.silence for c in story.cannot_say}

    missing = sorted(s.value for s in Silence if s not in reachable)
    assert not missing, f"these kinds of silence can never be produced: {missing}"


def test_nobody_looked_and_we_looked_and_found_nothing_do_not_render_alike() -> None:
    """**Defect found by this test.** `build` keeps the two apart — `episodes=None` for
    *nobody read the fault history*, `episodes=()` for *it was read and this asset carried
    nothing* — and records the first as `NOTHING_WAS_READ`. The rendered page then printed the
    *nobody looked* sentence for both, so an asset whose history genuinely had been read was
    told in words that it had not been.

    Neither reading means the machine is clean. They differ in what the reader does next, and
    a page that cannot tell them apart sends half its readers to the wrong place."""
    never_looked = build("chiller_1", window=WINDOW, episodes=None)
    looked_found_nothing = build("chiller_1", window=WINDOW, episodes=())

    assert never_looked.silences_of(Silence.NOTHING_WAS_READ)
    assert not looked_found_nothing.silences_of(Silence.NOTHING_WAS_READ)

    said_when_blind = _section(never_looked, "Diagnosed with")
    said_when_empty = _section(looked_found_nothing, "Diagnosed with")
    assert said_when_blind != said_when_empty
    assert "nobody having looked" in " ".join(said_when_empty)


def test_neither_absence_of_a_diagnosis_is_reported_as_a_healthy_machine() -> None:
    """Constraint 7: `NULL` means not diagnosed, never healthy. A two-month window was blind
    rather than clean, and an empty queue read as a clean plant. Whichever of the two absences
    it is, the page must refuse the healthy reading."""
    for episodes in (None, ()):
        body = " ".join(_section(build("chiller_1", window=WINDOW, episodes=episodes),
                                 "Diagnosed with"))
        assert "not a clean machine" in body or "never healthy" in body


def test_nothing_open_is_reported_as_quiet_rather_than_clean() -> None:
    """An empty queue is the shape of absence that reads best and means least. The window
    carries 7,662 slots the model never labelled at all, so the page says what the emptiness
    is sitting on top of rather than letting it read as a settled machine."""
    body = " ".join(_section(_story(open_items=()), "Open against it"))
    assert f"{faults.UNLABELLED_SLOTS:,}" in body
    assert "quiet rather than clean" in body


def test_a_case_with_no_recorded_blocker_does_not_read_as_unblocked() -> None:
    """The same collapse one level down. *Nobody wrote down what is blocking it* and *nothing
    is blocking it* are opposite facts about a case, and an interface that leaves the line to
    trail off has chosen the reassuring one on the reader's behalf."""
    unrecorded = OpenItem(
        reference="CASE-4",
        kind="case",
        fault_label="HIGH_HEAD_AMBIGUOUS",
        opened_on=date(2026, 4, 15),
        state="open",
    )
    recorded = OpenItem(
        reference="CASE-5",
        kind="case",
        fault_label="CONDENSER_LOW_FLOW",
        opened_on=date(2026, 4, 15),
        state="open",
        blocked_on="a technician with gauges has not been to the machine",
    )
    assert "not the same as nothing blocking it" in unrecorded.render(date(2026, 4, 20))
    assert "a technician with gauges" in recorded.render(date(2026, 4, 20))


def test_a_page_with_no_reference_date_states_that_rather_than_showing_no_age() -> None:
    """Constraint 22 is why an age is shown at all: four open cases once described transmitters
    repaired weeks earlier and twenty had been waiting since April. A snapshot has no *now*,
    and a blank where the age goes lets a reader supply one from their own head — which is the
    failure constraint 15 exists to prevent one level up."""
    item = OpenItem(
        reference="WO-9",
        kind="work order",
        fault_label="CONDENSER_LOW_FLOW",
        opened_on=date(2026, 4, 15),
        state="open",
    )
    assert "without a reference date" in item.age_text(None)
    assert item.age_text(date(2026, 4, 15)) == "opened on the day this page was built against"
    assert item.age_text(date(2026, 4, 20)) == "open for 5 days"


def test_the_page_reports_an_age_it_cannot_believe_rather_than_a_negative_one() -> None:
    """An item dated after the page's own reference date is a data defect, not an item aged
    minus four days. Reporting it as a negative number would put a figure on the page that
    describes nothing in the world."""
    item = OpenItem(
        reference="WO-10",
        kind="work order",
        fault_label="CONDENSER_LOW_FLOW",
        opened_on=date(2026, 4, 20),
        state="open",
    )
    assert "after the date this page was built against" in item.age_text(date(2026, 4, 15))
    assert "-" not in item.age_text(date(2026, 4, 15))


# ── the signals ────────────────────────────────────────────────────────────────

def test_condenser_flow_names_the_models_it_takes_down_rather_than_saying_unavailable() -> None:
    """`Q1`, the highest-leverage open question in the programme. *"condenser flow:
    unavailable"* is true and useless; four of the five fitted models on this asset take it as
    an input, so the efficiency and high-head branch is `NO_DIAGNOSIS` plus a data-quality work
    order by design on day one, and the page has to say which four."""
    (entry,) = [c for c in _story().cannot_say if c.subject == "cond_flow"]
    assert entry.silence is Silence.NEVER_MEASURED
    for model in asset_story.MODELS_TAKING_COND_FLOW:
        assert model in entry.consequence
    assert "NO_DIAGNOSIS" in entry.consequence
    assert "Q1" in entry.consequence


def test_the_count_of_blocked_models_carries_how_it_was_read() -> None:
    """No document states the correspondence between the six models `CONTEXT.md` §6 names and
    the five the metrics table holds. A bare *four* would be a number with no source behind it,
    so the page prints the reading it took and marks it unconfirmed (`Q73`)."""
    (entry,) = [c for c in _story().cannot_say if c.subject == "cond_flow"]
    assert asset_story.COND_FLOW_MAPPING_CAVEAT in entry.consequence
    assert "Q73" in entry.consequence


def test_four_of_the_five_fitted_models_stand_on_a_signal_never_measured_here() -> None:
    """The dependency that shapes everything. Five models are fitted on a chiller and four of
    them take condenser flow — a signal with 0 non-zero values in 37,430 measured slots."""
    story = _story()
    assert story.fitted_model_count == residuals.FITTED_MODEL_COUNT == 5
    assert story.blocked_model_count == 4


def test_the_condenser_approach_question_is_reported_as_unanswerable_not_as_missing() -> None:
    """`dpt` is present and carries nothing — a flat 107.0 on chiller 1 against 112.9 on
    chiller 2, and two different flat numbers are themselves the evidence that neither is a
    reading. What it costs is specific: condenser approach temperature cannot be computed at
    all, which is both the fouling threshold and a question inside a differential (`Q8`)."""
    (entry,) = [c for c in _story().cannot_say if c.subject == "dpt"]
    assert entry.silence is Silence.CONSTANT_SIGNAL
    assert "107.0" in entry.consequence
    assert "cannot be computed at all" in entry.consequence
    assert "Q8" in entry.consequence


def test_the_dead_flow_transmitter_carries_the_day_it_stopped_being_believable() -> None:
    """*"Suspect"* on its own tells a reader to distrust the whole column. The transmitter read
    credibly until 2026-04-22, and the re-clone moved that boundary earlier within the day
    because the rest of it was computed rather than read — a verdict that got more honest when
    a marker arrived is the one worth carrying."""
    (entry,) = [c for c in _story().cannot_say if c.subject == "chiller_flow"]
    assert "2026-04-22" in entry.consequence
    assert "F16" in entry.consequence


def test_a_signal_the_plant_later_commissions_stops_being_told_it_never_had_one() -> None:
    """The registry is five signals somebody verified by hand; `app/db/provenance.py` computes
    availability from the marker tables and is the authority. A page that preferred the hardcoded
    verdict would go on reporting a meter as absent after it was fitted — the same defect as
    asserting availability instead of deriving it, arriving through the page instead of the
    audit."""
    story = _story(
        signal_notes=(
            SignalNote("cond_flow", SignalStatus.MEASURED, "31,884 non-zero slots since April"),
        )
    )
    assert "cond_flow" not in {c.subject for c in story.cannot_say}
    assert "cond_flow" in {c.subject for c in _story().cannot_say}


def test_a_computed_note_never_narrows_the_page_to_what_the_caller_queried() -> None:
    """Computed verdicts win where they overlap, and registry entries nothing computed still
    appear. Dropping the registry the moment a note arrives would silently reduce the page to
    whatever the caller happened to ask about — and the caller is not the authority on what
    this plant cannot measure."""
    story = _story(
        signal_notes=(SignalNote("tr", SignalStatus.DERIVED, "computed, not read"),)
    )
    said_about = {c.subject for c in story.cannot_say}
    for registered in signals.unusable_keys():
        assert registered in said_about
    assert "tr" in said_about


def test_a_derived_value_is_neither_a_reading_nor_a_gap() -> None:
    """The 2026-08-17 re-clone substituted 12,589 derived slots for the simulation, 7,670 of
    them inside the measured window, and our code had no concept of *derived* — which would
    have made all 7,670 read as measured. Derived may be quoted and simulated may not, but
    quoting it requires a label and no rendering path attaches one yet."""
    story = _story(
        signal_notes=(
            SignalNote(
                "tr",
                SignalStatus.DERIVED,
                f"{DERIVED_IN_WINDOW:,} of the {IN_WINDOW_SLOTS:,} in-window slots are "
                f"computed by derived:tr_from_load_v1",
            ),
        )
    )
    (entry,) = [c for c in story.cannot_say if c.subject == "tr"]
    assert entry.silence is Silence.VALUE_WAS_COMPUTED
    assert entry.silence is not Silence.NEVER_MEASURED
    assert f"{DERIVED_IN_WINDOW:,}" in entry.because


def test_a_signal_nobody_wrote_a_consequence_for_claims_nothing_either_way() -> None:
    """The registry covers 5 of a normalised table's 38 columns. Inventing what the other 33
    cost this page would be a second fabrication stacked on the absence it describes — so the
    line says the working-out has not been done and makes no claim about the plant."""
    story = _story(
        signal_notes=(SignalNote("oil_pressure", SignalStatus.CONSTANT, "flat all window"),)
    )
    (entry,) = [c for c in story.cannot_say if c.subject == "oil_pressure"]
    assert entry.consequence == asset_story.UNWRITTEN_CONSEQUENCE
    assert entry.because == "flat all window"


def test_a_working_signal_produces_no_line_at_all() -> None:
    """Manufacturing a reassuring line for every healthy signal would bury the four that
    matter under thirty-four that do not."""
    story = _story(
        signal_notes=(SignalNote("suct_pres", SignalStatus.MEASURED, "reads normally"),)
    )
    assert "suct_pres" not in {c.subject for c in story.cannot_say}


# ── the roster ─────────────────────────────────────────────────────────────────

def test_the_roster_lists_the_model_the_design_names_and_nobody_fitted() -> None:
    """The design names six models per chiller and five are fitted. Returning only the five
    would make the roster agree with itself and disagree with the specification, and a reader
    counting five has no way to learn that a sixth was designed and never arrived."""
    lines = model_lines("chiller_1")
    assert len(lines) == residuals.DESIGNED_MODEL_COUNT == 6
    assert sum(1 for m in lines if m.is_fitted) == residuals.FITTED_MODEL_COUNT == 5
    (absent,) = [m for m in lines if not m.is_fitted]
    assert absent.model_name == residuals.ABSENT_RESIDUAL_COLUMN


def test_an_unfitted_model_is_not_a_model_with_a_clean_bill_of_health() -> None:
    """`is_poor_fit` is `False` for an absent model because there is no fit to be poor, and
    that boolean read alone says *this one is fine*. The page has to carry the absence on its
    own line, or the sixth model reads as the best-behaved of the six."""
    (absent,) = [m for m in model_lines("chiller_1") if not m.is_fitted]
    assert absent.is_poor_fit is False
    assert residuals.ABSENT_RESIDUAL_COLUMN in _subjects(_story(), Silence.MODEL_NOT_FITTED)


def test_the_unfitted_model_says_what_the_isolation_path_loses() -> None:
    """Constraint 34: where the trained model has a verdict, consume it rather than inventing a
    second opinion. With no compressor-amps residual this page can neither re-derive a
    compressor label nor contradict one, and that is what constraint 34 costs here."""
    (entry,) = _story().silences_of(Silence.MODEL_NOT_FITTED)
    assert "compressor" in entry.consequence
    assert str(residuals.DESIGNED_MODEL_COUNT) in entry.because
    assert str(residuals.FITTED_MODEL_COUNT) in entry.because


def test_a_model_line_says_one_thing_never_both_and_never_neither() -> None:
    """Constraint 14: a figure is a value or a stated absence, never both and never neither.
    Enforced in the constructor rather than asked for, because the alternative is a page that
    reads as informative and is not."""
    with pytest.raises(ValueError, match="no fit and no reason"):
        ModelLine(model_name="Suction_Pres")
    with pytest.raises(ValueError, match="say one thing"):
        ModelLine(model_name="Suction_Pres", nrmse=7.93, absence="not fitted")


def test_a_fit_of_zero_is_a_number_and_not_an_absence() -> None:
    """A falsy value is still a value. A truthiness check here would turn a perfect fit into a
    model that was never fitted — the absence and the number swapping places silently."""
    line = ModelLine(model_name="Suction_Pres", nrmse=0.0)
    assert line.is_fitted
    assert "nRMSE 0.0" in line.render()


def test_a_poor_fit_is_badged_and_never_suppressed() -> None:
    """`F10` model health and `F11` quarantine are load-bearing rather than hygiene: one model
    runs at nRMSE 48.03 and its residual is partly its own error. Hiding it would be the worse
    error, because a hidden fault is worse than a flagged artefact."""
    (chiller_current,) = [
        m for m in model_lines("chiller_1") if m.model_name == "Chiller_Current"
    ]
    assert chiller_current.nrmse == 48.03
    assert chiller_current.is_poor_fit
    assert "partly its own error" in chiller_current.render()
    assert "Chiller_Current" in _subjects(_story(), Silence.FIT_IS_PARTLY_ERROR)


def test_the_poor_fit_threshold_is_marked_unagreed_rather_than_stated_as_settled() -> None:
    """`Q50`. Nobody has agreed what nRMSE this product should stop trusting, so the line names
    the threshold it used and the question it belongs to instead of presenting 10.0 as a
    sourced fact."""
    (entry,) = [c for c in _story().cannot_say if c.subject == "Chiller_Current"]
    assert str(residuals.POOR_FIT_NRMSE) in entry.because
    assert "Q50" in entry.because


# ── the same model on two machines ─────────────────────────────────────────────

def test_the_same_model_is_eighteen_times_worse_on_one_machine_than_the_other() -> None:
    """Two machines of one type, one model, nRMSE 48.03 against 2.65. Models are fitted per
    asset and never per fleet, so an identical fault label on the two does not mean the same
    thing and no figure here may be compared with the same figure there."""
    gap = widest_fit_gap()
    assert gap is not None
    assert (gap.worse_key, gap.worse_nrmse) == ("chiller_1", 48.03)
    assert (gap.better_key, gap.better_nrmse) == ("chiller_2", 2.65)
    assert gap.ratio == pytest.approx(48.03 / 2.65)
    assert "18 times the error" in gap.render()


def test_the_gap_is_computed_from_the_fits_rather_than_quoted_from_a_document() -> None:
    """`CONTEXT.md` records the 48.03-against-2.65 case in prose. Deriving it means the
    sentence changes when the data does, instead of a document and a page disagreeing about a
    machine — which is the shape of every stale figure in this repository."""
    gap = widest_fit_gap()
    assert gap is not None
    ratios = {
        name: max(f.nrmse for f in fits) / min(f.nrmse for f in fits)
        for name in residuals.FITTED_MODEL_NAMES
        if len(fits := [residuals.fit_for(k.key, name) for k in eq.scoreable_equipment()]) > 1
        and all(f is not None for f in fits)
    }
    assert gap.model_name == max(ratios, key=lambda n: ratios[n])


def test_an_asset_carrying_no_fit_is_not_told_how_far_apart_two_other_fits_are() -> None:
    """**Defect found by this test.** `widest_fit_gap` is a fleet-level fact and takes no
    equipment key, and `_model_silences` appended it to every asset. A condenser pump's page —
    no models, no fits, nothing to compare — carried *"no figure on this page may be compared
    with the same figure on the other"* about `Chiller_Current`.

    That is a claim about one machine assembled entirely from another machine's data, in the
    section whose whole purpose is to refuse exactly that. Both chillers keep the line, because
    both carry the fit."""
    assert _story("condenser_pump_1").silences_of(Silence.NOT_COMPARABLE_ACROSS_ASSETS) == ()
    for key in ("chiller_1", "chiller_2"):
        assert _story(key).silences_of(Silence.NOT_COMPARABLE_ACROSS_ASSETS)


# ── what was diagnosed ─────────────────────────────────────────────────────────

def test_the_modal_outcome_is_on_the_page_rather_than_filtered_out() -> None:
    """`NO_DIAGNOSIS` is the commonest thing this platform says — 5,309 slots against 674
    faulted. A page that filtered refusals out would show a machine with a handful of fault
    labels and no sign that the platform spent most of the window declining to judge it."""
    labels = {d.fault_label for d in _story().diagnoses}
    assert "NO_DIAGNOSIS" in labels
    (refusal,) = [d for d in _story().diagnoses if d.fault_label == "NO_DIAGNOSIS"]
    assert refusal.slot_count == 5_309


def test_a_refusal_is_never_counted_as_a_fault() -> None:
    """A refusal is not an error and not a fault. Counting `NO_DIAGNOSIS` and
    `NO_EFFICIENCY_FAULT` into the fault total would put 6,252 slots of honest silence into a
    number a manager reads as breakage — the modal outcome inflating the fault count more than
    twelvefold over the 674 slots genuinely faulted."""
    story = _story()
    assert story.fault_count == len(faults.fault_labels()) == 7
    faulted = sum(d.slot_count for d in story.diagnoses if d.is_fault)
    assert faulted == 674


def test_severity_is_words_and_never_a_plausible_looking_middle_value() -> None:
    """`Q49`: no document states a severity for six of the seven fault classes. A silent
    default to `MEDIUM` is a number invented in the one place `F17` says must be authoritative,
    and it would look exactly like a sourced one."""
    story = _story()
    unrated = [d for d in story.diagnoses if not faults.is_rated(d.fault_label)]
    assert unrated
    for line in unrated:
        assert line.severity_text == faults.UNRATED_SEVERITY_TEXT
        assert "Q49" in line.severity_text
    assert _subjects(story, Silence.SEVERITY_NOT_AGREED)


def test_the_one_class_with_a_sourced_severity_carries_it() -> None:
    """`CONDENSER_LOW_FLOW` is the only class with a severity behind it. If everything rendered
    as *not yet agreed* the honesty would be free and would prove nothing — the distinction
    only counts because one class really does have an answer."""
    (rated,) = [d for d in _story().diagnoses if d.fault_label == "CONDENSER_LOW_FLOW"]
    assert rated.severity_text == f"severity {faults.Severity.CRITICAL.value}"
    assert "CONDENSER_LOW_FLOW severity" not in _subjects(_story(), Silence.SEVERITY_NOT_AGREED)


def test_an_undecidable_class_says_so_on_its_line_and_again_in_the_last_section() -> None:
    """Four of the seven fault names declare in their own name that the model could not
    separate the causes, and they are the median outcome rather than an edge case. Constraint
    27: only these get a differential, and none of them names a mechanism."""
    story = _story()
    (ambiguous,) = [d for d in story.diagnoses if d.fault_label == "HIGH_HEAD_AMBIGUOUS"]
    assert ambiguous.declares_undecidable
    assert "could not separate the causes" in ambiguous.render()
    assert set(faults.undecidable_labels()) <= _subjects(story, Silence.NOT_SEPARABLE)


def test_a_differential_that_runs_out_is_reported_as_different_from_a_conclusion() -> None:
    """Constraint 32: exhausted is not settled. *"We cannot separate these with the checks we
    have"* is a finding, and a page that let it read as a conclusion would hand a technician a
    settled answer nobody reached."""
    (entry,) = [
        c for c in _story().silences_of(Silence.NOT_SEPARABLE)
        if c.subject == "HIGH_HEAD_AMBIGUOUS"
    ]
    assert "exhausted rather than settled" in entry.consequence
    assert "different statement from a conclusion" in entry.consequence


def test_both_the_slot_count_and_the_day_count_are_carried() -> None:
    """*"High head, ambiguous"* over 430 slots on ten days is one machine misbehaving for a
    fortnight; the same label on three slots is an afternoon. An interface showing one of the
    two cannot tell them apart — and 39 episodes over 12 equipment-days is what the measured
    queue actually holds."""
    spread = (
        _episode("HIGH_HEAD_AMBIGUOUS", day=DAY),
        _episode("HIGH_HEAD_AMBIGUOUS", day=date(2026, 4, 16)),
    )
    (line,) = diagnosis_lines("chiller_1", spread)
    assert line.episode_count == 2
    assert line.slot_count == MEASURED_SLOTS["HIGH_HEAD_AMBIGUOUS"] * 2
    assert "2026-04-15 to 2026-04-16" in line.render()
    assert "2 days" in line.render()


def test_only_this_asset_s_episodes_reach_its_page() -> None:
    """Models are fitted per asset and two identical chillers do not share one, so a label read
    off the other machine on this page would be attributing a fault to the wrong equipment."""
    mixed = (_episode("CONDENSER_LOW_FLOW"), _episode("HIGH_HEAD_AMBIGUOUS", "chiller_2"))
    assert [d.fault_label for d in diagnosis_lines("chiller_1", mixed)] == ["CONDENSER_LOW_FLOW"]
    assert [d.fault_label for d in diagnosis_lines("chiller_2", mixed)] == ["HIGH_HEAD_AMBIGUOUS"]


def test_the_display_order_of_the_labels_is_not_a_ranking() -> None:
    """Constraint 36: the ambiguous class is usually both the longest-running and the least
    informative, and it appeared on 12 of 12 fault days. It leads this list because the list is
    sorted by size for reading, and `correlation.choose_primary` — which answers *which one
    leads* with a reason attached — deliberately picks something else. If those two ever agreed
    by construction, position would have quietly become importance."""
    story = _story()
    assert story.diagnoses[0].fault_label == "NO_DIAGNOSIS"
    faulty = [d for d in story.diagnoses if d.is_fault]
    assert faulty[0].fault_label == "HIGH_HEAD_AMBIGUOUS"

    primary, reason = correlation.choose_primary(
        tuple(e for e in ALL_LABELS if faults.by_label(e.fault_label).is_fault)
    )
    assert primary.fault_label != faulty[0].fault_label
    assert reason.strip()


# ── a refusal, an error, and the difference ────────────────────────────────────

def test_an_asset_with_no_reference_band_gets_a_page_rather_than_an_error() -> None:
    """Ten of the twelve equipment tables have no model, no band and no scored residual. That
    is the correct answer rather than a gap, so the pump gets a page that says nothing may be
    diagnosed on it — refusing to judge is an outcome, not a failure."""
    story = _story("condenser_pump_1")
    assert story.scoreable is False
    assert story.models == ()
    (entry,) = story.silences_of(Silence.NO_REFERENCE_BAND)
    assert "judged high or normal" in entry.consequence
    assert "against zero" in entry.consequence


def test_an_asset_that_is_not_in_the_registry_raises_instead_of_returning_a_page() -> None:
    """The other direction, and it must not be softened into a refusal. A story about a machine
    nobody registered is a page describing something that does not exist, and returning one
    would be worse than a stack trace — this is a defect in the caller, not an absence in the
    plant."""
    with pytest.raises(ValueError, match="not in the equipment registry"):
        build("chiller_9", window=WINDOW, episodes=())


def test_an_unscoreable_asset_is_not_told_which_models_it_lacks() -> None:
    """A pump has no compressor-amps model to be missing. Listing the chiller roster's gaps
    against it would invent a specification the asset was never held to."""
    story = _story("condenser_pump_1")
    assert story.silences_of(Silence.MODEL_NOT_FITTED) == ()
    assert story.silences_of(Silence.FIT_IS_PARTLY_ERROR) == ()
    assert "No model is fitted for this asset" in " ".join(_section(story, "Models"))


# ── every absence is words ─────────────────────────────────────────────────────

def test_no_absence_on_this_page_is_a_bare_flag_a_zero_or_a_dash() -> None:
    """*"An absence is not a zero and not a dash."* Three fields rather than one sentence,
    because an interface carrying only the first produces *"efficiency: unavailable"* — which is
    the dash this module exists to refuse, spelled out in letters."""
    for entry in _story().cannot_say:
        assert entry.subject.strip()
        assert len(entry.because.split()) > 3, f"{entry.subject} has no reason in words"
        assert len(entry.consequence.split()) > 3, f"{entry.subject} states no consequence"
        assert entry.render().startswith(entry.subject)


def test_the_rendered_page_never_prints_a_python_none() -> None:
    """A `None` reaching the page is an unstated absence wearing the costume of a value, and it
    is what a reader sees when a field was left to trail off."""
    rendered = _story(open_items=(), episodes=None).render()
    assert "None" not in rendered
    assert "N/A" not in rendered


def test_the_dictionary_never_carries_a_null_without_the_words_that_replace_it() -> None:
    """A surface must be able to show the sentence rather than rebuild it from the pieces, and
    a serialised `null` with no words beside it is how constraint 14 gets broken across an API
    boundary rather than inside a dataclass."""
    payload = _story().as_dict()
    for model in payload["models"]:
        assert (model["nrmse"] is None) != (model["absence"] == "")
        assert model["text"].strip()
    for entry in payload["cannot_say"]:
        assert entry["because"].strip() and entry["consequence"].strip()
        assert entry["silence"] in {s.value for s in Silence}
    assert payload["window"]


def test_the_page_does_not_rearrange_itself_between_two_readings_of_one_window() -> None:
    """Stable order is what makes the section quotable. A reader who screenshots the first
    three lines and comes back to a different three has no way to tell whether the machine
    changed or the page did."""
    assert _story().render() == _story().render()
    assert cannot_say_for("chiller_1") == cannot_say_for("chiller_1")


def test_a_cannot_say_renders_its_subject_its_reason_and_its_cost_in_one_sentence() -> None:
    """All three, because a reader needs all three. The failure the shape prevents is a line
    that names the subject and stops."""
    entry = CannotSay(
        subject="cond_flow",
        silence=Silence.NEVER_MEASURED,
        because="0 non-zero in 37,430 measured slots",
        consequence="four of the five fitted models take it as an input",
    )
    assert entry.render() == (
        "cond_flow — 0 non-zero in 37,430 measured slots. "
        "four of the five fitted models take it as an input."
    )


def test_a_diagnosis_line_states_its_own_span_as_well_as_the_page_window() -> None:
    """Constraint 15 applies per artefact, and a label's own days are not the window's days.
    A single-day label reading as though it ran the whole window is the same class of error as
    a count shown under a heading that did not overlap it."""
    (line,) = diagnosis_lines("chiller_1", (_episode("CONDENSER_LOW_FLOW"),))
    assert isinstance(line, DiagnosisLine)
    assert "2026-04-15" in line.render()
    assert "1 day" in line.render()
