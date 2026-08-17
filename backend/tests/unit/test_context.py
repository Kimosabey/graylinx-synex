"""`C10` multi-step task memory, and the context budget nothing was enforcing.

Two gaps closed here, and both are the kind that pass every test until the day they do not.
A task with no memory of its own steps answers step three from scratch and nobody notices,
because the answer is well formed. A prompt that exceeds `max_context_chars` fails on an
unpredictable turn — and worse, one that quietly drops a third of the evidence never fails at
all, it just answers as though it had read everything.

These tests exist to make both visible: what a task established, and what did not fit.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.agents.context import (
    DROP_ORDER,
    HONESTY_PAYLOAD,
    MAX_TASK_STEPS,
    AssembledContext,
    ContextSection,
    ContextTier,
    DroppedSection,
    StepOutcome,
    Task,
    TaskBook,
    TaskState,
    assemble,
    assemble_turn,
    fit_question,
    sections_from_prompt_data,
)
from app.analytics.bands import ResidualBand
from app.analytics.gates import Gate, GateOutcome, GateResult, check_running
from app.config import CONTEXT_TRUNCATION_MARKER, get_settings
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.services.evidence import build_pack, window_for

DAY = date(2026, 4, 15)
MEASURED_END = datetime(2026, 6, 23, 11, 50)
T0 = datetime(2026, 4, 15, 9, 0)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _task(**kw) -> Task:
    return Task(id="T-1", goal="why is chiller 1 running hot", opened_at=T0, **kw)


def _worked(task: Task, steps: int = 1, *, at: datetime = T0) -> Task:
    for i in range(steps):
        task = task.record(
            intent=f"check residual {i + 1}",
            outcome=StepOutcome.ESTABLISHED,
            finding=f"the residual sits inside this asset's own band on reading {i + 1}",
            at=at + timedelta(minutes=i),
        )
    return task


def _pack(label: str | None = "CONDENSER_LOW_FLOW", *, blind: bool = False):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = (ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), label or "", values),)
    gates = (
        GateOutcome(
            (GateResult(Gate.RUNNING, passed=False, reason="no readings", remedy="check feed"),)
        )
        if blind
        else GateOutcome((check_running({"a": 141.0}),))
    )
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=gates,
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
    )


# ── C10: a task remembers what its steps established ───────────────────────────

def test_a_task_carries_what_each_step_established_in_order() -> None:
    """The whole gap. `C15` remembers what *"this"* refers to across six turns; it has no way
    to say that step one settled the flow reading and step two ruled the tower out. Step three
    then re-derives both, or worse, assumes them."""
    task = _task().record(
        intent="check whether the machine was running",
        outcome=StepOutcome.ESTABLISHED,
        finding="141 kW draw over the whole episode, so the running gate passed",
        at=T0,
    ).record(
        intent="check the condenser flow",
        outcome=StepOutcome.REFUSED,
        finding="condenser flow has never recorded a non-zero value on this plant",
        at=T0 + timedelta(minutes=5),
    )

    assert [s.ordinal for s in task.steps] == [1, 2]
    assert "141 kW" in task.where_we_got_to(T0)
    assert "never recorded a non-zero value" in task.where_we_got_to(T0)


def test_only_an_established_step_is_offered_as_ground_to_a_later_step() -> None:
    """*"We asked and could not tell"* is not *"we know"*. A refused or waiting step stays in
    the trail — a reader needs it — but a later step must never stand on it, which is the same
    rule as constraint 30: *can't tell* has no effect at all."""
    task = _task().record(
        intent="ask whether the tower fans were running",
        outcome=StepOutcome.WAITING,
        finding="nobody at the machine has answered yet",
        at=T0,
    ).record(
        intent="read the discharge pressure residual",
        outcome=StepOutcome.ESTABLISHED,
        finding="high against this asset's own band",
        at=T0 + timedelta(minutes=1),
    )

    assert len(task.steps) == 2
    assert [s.ordinal for s in task.established] == [2]


def test_a_step_recorded_with_no_finding_is_refused_at_construction() -> None:
    """An outcome with a blank finding is the dash this product does not print. Refused in the
    constructor rather than discouraged in a docstring, because an instruction is followed most
    of the time and an invariant is followed always — the argument `Figure` already makes."""
    with pytest.raises(ValueError, match="no finding"):
        _task().record(
            intent="check the condenser flow",
            outcome=StepOutcome.REFUSED,
            finding="   ",
            at=T0,
        )


def test_a_task_with_no_steps_says_so_rather_than_rendering_an_empty_list() -> None:
    """An absence is not a zero and not a dash. *"Nothing has been established"* is a fact a
    reader can act on; an empty section is one they will fill in from their own head."""
    assert "No step has been recorded yet" in _task().where_we_got_to(T0)


def test_where_we_got_to_states_that_the_age_was_not_checked_when_no_moment_is_given() -> None:
    """Whether a trail has gone stale is a question about a moment. A renderer given no moment
    and quietly skipping the check would let a three-week-old enquiry read as current."""
    assert "was not checked" in _worked(_task()).where_we_got_to(None)


# ── C10: abandoned, and it does not silently resume ────────────────────────────

def test_an_abandoned_task_refuses_to_resume_and_names_the_reason() -> None:
    """Constraint 22, one layer up. Four open cases described transmitters repaired weeks
    earlier; an enquiry quietly picked up later stands on findings the plant moved past."""
    task = _worked(_task()).abandon("the machine was taken off line for a retrofit", T0)
    resumed, reason = task.resume(T0 + timedelta(hours=1))

    assert resumed is None
    assert "taken off line for a retrofit" in reason
    assert "reopen it explicitly" in reason


def test_recording_onto_an_abandoned_task_raises_rather_than_resuming_it() -> None:
    """The guard that makes *"must not silently resume"* true of the mechanism rather than of
    everybody's care. A caller reaching here has skipped `resume()`, and appending anyway would
    surface as a confident answer weeks later instead of a failure now."""
    task = _worked(_task()).abandon("the reading turned out to be an instrument fault", T0)

    with pytest.raises(ValueError, match="silently"):
        task.record(
            intent="check the approach temperature",
            outcome=StepOutcome.ESTABLISHED,
            finding="it cannot be computed — dpt never changes on this chiller",
            at=T0 + timedelta(days=1),
        )


def test_reopening_keeps_the_abandonment_on_the_record() -> None:
    """An abandoned task can be continued — deliberately, and never in a way that erases why it
    stopped. `RC13` requires every elimination to record the check that caused it for the same
    reason: a settled question nobody re-examines is dangerous because the settling is
    invisible."""
    task = (
        _worked(_task())
        .abandon("the technician went home", T0)
        .reopen("the same fault reappeared the next morning", T0 + timedelta(days=1))
    )

    assert task.state is TaskState.OPEN
    assert task.overrides, "the override is the record that somebody decided"
    assert "the technician went home" in task.overrides[0]
    assert "reappeared the next morning" in task.overrides[0]


def test_abandoning_without_a_reason_is_refused() -> None:
    """A stale row with no reason is one nobody can act on — the `RC9` column carries words for
    exactly this reason, and a task is no different."""
    with pytest.raises(ValueError, match="no reason"):
        _worked(_task()).abandon("  ", T0)


def test_a_task_nobody_has_touched_goes_stale_and_stale_is_not_abandoned() -> None:
    """`RC9`'s two kinds, kept apart here too. *Abandoned* means somebody stopped it; *stale*
    means nobody looked. A single flag would let a settled enquiry and a forgotten one look
    identical, and only the second needs a person."""
    task = _worked(_task())
    later = T0 + timedelta(days=30)

    resumed, reason = task.resume(later)

    assert resumed is None
    assert task.state is TaskState.OPEN, "stale is a verdict against a moment, not a state"
    assert "has not been touched since" in reason
    assert "offered for confirmation" in reason


def test_a_task_inside_the_ageing_window_resumes_and_says_what_it_stands_on() -> None:
    """The other half: a task that may continue must say so in words a route trace can show. A
    resumption nobody can inspect is indistinguishable from a guess."""
    resumed, reason = _worked(_task(), 2).resume(T0 + timedelta(hours=2))

    assert resumed is not None
    assert "continues at step 3" in reason
    assert "2 earlier step(s) established" in reason


def test_a_complete_task_does_not_extend_itself() -> None:
    """A new question opens a new task. Extending a settled one would make the record of what
    was concluded depend on what was asked afterwards."""
    settled, _ = _worked(_task()).complete(T0)
    resumed, reason = settled.resume(T0 + timedelta(minutes=1))

    assert resumed is None
    assert "is complete" in reason


def test_a_task_waiting_on_a_person_cannot_complete() -> None:
    """26 of 43 measured cases stop at the checks, and the pause is the feature. A task that
    closed over one would turn *"waiting for a technician"* back into a value in a response."""
    task = _task().record(
        intent="ask for a superheat measurement",
        outcome=StepOutcome.WAITING,
        finding="a technician with gauges has not been to the machine yet",
        at=T0,
    )
    done, reason = task.complete(T0 + timedelta(hours=1))

    assert done is None
    assert "still waiting" in reason
    assert "gauges" in reason


def test_the_step_ceiling_abandons_rather_than_dropping_the_earliest_step() -> None:
    """`TurnMemory` drops its oldest turn when it fills and that is right there — forgetting the
    wording of an old question costs nothing. Here it costs everything: step three needs what
    step one established, so the task stops and names the step that did not fit."""
    task = _worked(_task(), MAX_TASK_STEPS)
    full = task.record(
        intent="one step too many",
        outcome=StepOutcome.ESTABLISHED,
        finding="this should never be recorded",
        at=T0 + timedelta(hours=1),
    )

    assert full.state is TaskState.ABANDONED
    assert len(full.steps) == MAX_TASK_STEPS, "no earlier step was given up"
    assert "one step too many" in full.abandoned_reason
    assert "abandoned rather than truncated" in full.abandoned_reason


def test_a_book_offers_the_open_task_and_never_the_abandoned_one() -> None:
    """What a router actually holds. The failure this prevents is a new turn continuing the
    enquiry somebody explicitly stopped, because it was simply the most recent one."""
    book, first = TaskBook().open_task(id="T-1", goal="high head on chiller 1", at=T0)
    book = book.updated(_worked(first).abandon("superseded by an instrument fault", T0))
    book, second = book.open_task(id="T-2", goal="why does the flow read zero", at=T0)
    book = book.updated(_worked(second))

    resumable, reason = book.resumable(T0 + timedelta(hours=1))

    assert resumable is not None
    assert resumable.id == "T-2"
    assert "T-2" in reason


def test_a_book_whose_every_task_is_stopped_explains_the_most_recent_one() -> None:
    """A reader asking *"where had we got to"* is asking about the thing they were last doing.
    Answering with a refusal from three tasks ago names the wrong enquiry."""
    book, task = TaskBook().open_task(id="T-1", goal="high head", at=T0)
    book = book.updated(_worked(task).abandon("the case was closed as an instrument fault", T0))

    resumable, reason = book.resumable(T0 + timedelta(hours=1))

    assert resumable is None
    assert "closed as an instrument fault" in reason


def test_an_empty_book_says_so_in_words() -> None:
    """An absence is not a zero."""
    _, reason = TaskBook().resumable(T0)
    assert "no task has been opened" in reason


# ── the budget: the ordering is a closed, inspectable table ────────────────────

def test_every_tier_is_either_never_dropped_or_has_a_place_in_the_drop_order() -> None:
    """A tier in neither table would be dropped by accident or kept by accident, and both are
    silent. This test is what makes adding a tier a decision rather than an edit."""
    assert set(HONESTY_PAYLOAD) | set(DROP_ORDER) == set(ContextTier)
    assert not set(HONESTY_PAYLOAD) & set(DROP_ORDER), "a tier cannot be both"


def test_the_honesty_payload_is_ordered_gate_signal_window_label() -> None:
    """The order is the specification, not a preference: the gate outcome first because
    `NO_DIAGNOSIS` is the modal outcome, and the signal notes second because `cond_flow` has
    never recorded a non-zero value in 37,430 measured slots."""
    assert HONESTY_PAYLOAD == (
        ContextTier.GATE_OUTCOME,
        ContextTier.SIGNAL_NOTE,
        ContextTier.DATA_WINDOW,
        ContextTier.FAULT_LABEL,
    )


def test_a_dropped_section_with_no_reason_is_refused() -> None:
    """A silent drop is the whole failure. A drop recorded as a bare count is a silent drop
    with a number next to it."""
    with pytest.raises(ValueError, match="no reason"):
        DroppedSection(key="residual.1", tier=ContextTier.EVIDENCE, chars=40, reason="")


# ── the budget: what fits, and what is said about what does not ────────────────

def _sections(residuals: int = 6, *, history: bool = False) -> list[ContextSection]:
    out = [
        ContextSection("gate.1", ContextTier.GATE_OUTCOME, "gate — running: passed"),
        ContextSection(
            "signal.1",
            ContextTier.SIGNAL_NOTE,
            "signal — condenser flow: never measured, 0 non-zero in 37,430 measured slots",
        ),
        ContextSection("data_window", ContextTier.DATA_WINDOW, "data window — 2026-04-15"),
        ContextSection("fault_label", ContextTier.FAULT_LABEL, "fault label — CONDENSER_LOW_FLOW"),
    ]
    out += [
        ContextSection(f"residual.{i}", ContextTier.EVIDENCE, f"residual — line {i} " + "x" * 40)
        for i in range(1, residuals + 1)
    ]
    out.append(ContextSection("sources", ContextTier.SUPPORTING, "sources — " + "y" * 60))
    if history:
        out.append(ContextSection("task_trail", ContextTier.HISTORY, "trail — " + "z" * 60))
    return out


def test_a_context_that_fits_is_assembled_whole_and_says_nothing_was_dropped() -> None:
    """The ordinary case must state its own completeness. *"Nothing was dropped"* is a claim a
    reader can rely on only if the assembler is the thing making it."""
    result = assemble(_sections(), budget=24_000)

    assert result.is_complete
    assert result.dropped == ()
    assert CONTEXT_TRUNCATION_MARKER not in result.text
    assert "nothing was dropped" in result.render_drop_report()


def test_what_did_not_fit_is_reported_to_the_caller_with_its_reason() -> None:
    """Dropping is allowed. Dropping silently is the failure — an answer built on two thirds of
    the evidence, presented as though built on all of it."""
    result = assemble(_sections(residuals=12, history=True), budget=1_000)

    assert result.dropped, "this budget cannot hold everything"
    assert not result.is_complete
    assert not result.must_refuse, "the honesty payload and the note both fit here"
    for drop in result.dropped:
        assert drop.reason.strip(), "every drop carries its reason in words"
        assert "ceiling" in drop.reason


def test_what_was_dropped_is_written_into_the_context_the_model_reads() -> None:
    """Reporting the drop only to the caller is half a fix: the caller can log it, but the
    sentence a reader sees is written by something that still believes it saw everything."""
    result = assemble(_sections(residuals=12, history=True), budget=1_000)

    assert CONTEXT_TRUNCATION_MARKER in result.text
    assert "did not fit" in result.text
    for drop in result.dropped:
        assert drop.key in result.text


@pytest.mark.parametrize("budget", [300, 400, 600, 800, 1_000, 1_200, 24_000])
def test_the_assembled_context_never_exceeds_the_budget(budget: int) -> None:
    """The bound is the point. A ceiling that holds for most inputs is a ceiling that fails on
    an unpredictable turn, which is the worst place to discover a limit."""
    result = assemble(_sections(history=True), budget=budget)
    if not result.must_refuse:
        assert result.used_chars <= budget


def test_the_note_reporting_the_drops_is_itself_counted_against_the_budget() -> None:
    """Otherwise the failure re-enters through the door marked exit: a context that overflows
    by exactly the length of the note explaining that it did not overflow."""
    budget = 1_200
    result = assemble(_sections(residuals=20, history=True), budget=budget)

    assert result.dropped
    assert result.used_chars <= budget
    assert CONTEXT_TRUNCATION_MARKER in result.text


# ── the budget: what must never be dropped ─────────────────────────────────────

@pytest.mark.parametrize("budget", [800, 1_000, 1_200, 24_000])
def test_the_honesty_payload_survives_every_budget_that_can_hold_it(budget: int) -> None:
    """The four that are never dropped: the gate outcome, the signal notes, the data window and
    the fault label. Dropping a residual to fit is acceptable; dropping *"this signal was never
    measured"* is not, because one costs a reader a line and the other costs them the reason
    the branch cannot be judged at all."""
    result = assemble(_sections(residuals=12, history=True), budget=budget)
    kept = {s.key for s in result.included}

    assert {"gate.1", "signal.1", "data_window", "fault_label"} <= kept
    assert "never measured" in result.text


def test_a_residual_is_given_up_before_a_signal_note() -> None:
    """The specific trade, asserted rather than assumed. On the measured pack the signal notes
    are 1,552 of 2,936 characters — the most expensive thing in it, and the least droppable."""
    result = assemble(_sections(residuals=12, history=True), budget=800)
    dropped = {d.key for d in result.dropped}

    assert any(key.startswith("residual.") for key in dropped)
    assert "signal.1" not in dropped


def test_history_is_given_up_before_evidence() -> None:
    """The task trail goes first. Losing *"step two established the flow reads zero"* costs a
    turn some continuity; losing the residual costs the answer its evidence."""
    result = assemble(_sections(residuals=20, history=True), budget=1_200)
    dropped = [d.key for d in result.dropped]

    assert "task_trail" in dropped
    assert dropped.index("task_trail") == 0, "history is surrendered first"


def test_a_budget_too_small_for_the_honesty_payload_refuses_rather_than_trimming_it() -> None:
    """The one case with no honest answer inside the ceiling. Trimming would drop the part that
    must never be dropped, so the assembler returns the payload **whole** and marks the turn
    unsendable — a refusal is not an error, and it is not a truncation either."""
    sections = _sections(residuals=2)
    result = assemble(sections, budget=40)

    assert result.must_refuse
    assert "never be dropped" in result.refusal_reason
    assert "never measured" in result.text, "the payload was returned whole, not trimmed"
    assert result.used_chars > result.budget, "it is returned unsent rather than cut to fit"


def test_the_refusal_names_the_question_rather_than_choosing_for_itself() -> None:
    """`Q84` is unanswered: whether a turn too large for its own honesty payload should refuse
    or raise the ceiling is a decision, and the assembler is not the thing that makes it."""
    result = assemble(_sections(), budget=40)
    assert "Q84" in result.refusal_reason


# ── the input ceiling ──────────────────────────────────────────────────────────

def test_a_question_within_the_input_ceiling_is_untouched() -> None:
    """The ordinary path must not mark anything — a marker on an intact question would teach a
    reader to ignore markers."""
    text, reason = fit_question("why was this flagged?", limit=8_000)

    assert text == "why was this flagged?"
    assert "fitted" in reason
    assert CONTEXT_TRUNCATION_MARKER not in text


def test_a_question_over_the_input_ceiling_is_marked_rather_than_silently_clipped() -> None:
    """`max_input_chars` stops a pasted wall of text becoming a VRAM spike. Clipping is fine;
    clipping without saying so means the model answers a question it only half received, and
    the answer reads as though it addressed the whole thing."""
    text, reason = fit_question("q" * 900, limit=200)

    assert len(text) <= 200
    assert text.endswith(CONTEXT_TRUNCATION_MARKER)
    assert "900 characters against an input ceiling of 200" in reason


def test_the_ceilings_come_from_configuration_rather_than_from_here() -> None:
    """One source of truth per fact. `max_context_chars` and `max_input_chars` are provisional
    against `Q48`, and a second copy would let the two disagree the day somebody answers it."""
    settings = get_settings()
    assert assemble(_sections()).budget == settings.max_context_chars
    _, reason = fit_question("x")
    assert str(settings.max_input_chars) in reason


# ── against the pack the model actually receives ───────────────────────────────

def test_the_sections_are_built_from_the_real_prompt_data() -> None:
    """Built against `to_prompt_data()` rather than a fixture of what it might contain, so a
    key renamed in the pack breaks here rather than quietly dropping a whole tier."""
    sections = sections_from_prompt_data(_pack().to_prompt_data())
    tiers = {s.tier for s in sections}

    assert ContextTier.GATE_OUTCOME in tiers
    assert ContextTier.SIGNAL_NOTE in tiers
    assert ContextTier.DATA_WINDOW in tiers
    assert ContextTier.FAULT_LABEL in tiers
    assert any(s.key.startswith("residual.") for s in sections)


def test_a_real_pack_fits_the_configured_ceiling_whole() -> None:
    """Measured: one episode's prompt data is 2,936 characters against a ceiling of 24,000. The
    ceiling bites on composition, not on a single episode — so if this ever starts dropping,
    something upstream grew and this is where it is noticed."""
    result = assemble_turn(_pack().to_prompt_data())

    assert result.is_complete
    assert result.used_chars < result.budget


def test_a_failed_gate_reaches_the_model_even_on_a_tiny_budget() -> None:
    """`NO_DIAGNOSIS` is the modal outcome — 5,309 slots against 674 faulted. A turn that lost
    the failed gate would answer as though the equipment had been fit to judge."""
    result = assemble_turn(_pack(blind=True).to_prompt_data(), budget=2_000)

    assert "no readings" in result.text
    assert "check feed" in result.text


def test_a_pack_with_no_data_window_says_so_rather_than_omitting_it() -> None:
    """Constraint 15. Anomaly counts were once shown on the database wall clock under a heading
    describing a telemetry window that did not overlap them at all — an omitted window is one
    the reader supplies from their own head."""
    data = _pack().to_prompt_data()
    data["data_window"] = ""
    sections = sections_from_prompt_data(data)
    window = next(s for s in sections if s.key == "data_window")

    assert "not stated by the evidence pack" in window.text


def test_the_task_trail_reaches_the_context_and_says_whether_it_may_continue() -> None:
    """The two halves meeting. A trail carried into a prompt without its resumability is how an
    abandoned enquiry gets continued by a model that had no way to know it was stopped."""
    task = _worked(_task()).abandon("the machine was taken off line", T0)
    result = assemble_turn(_pack().to_prompt_data(), task=task, now=T0 + timedelta(hours=1))

    assert "where we had got to" in result.text
    assert "taken off line" in result.text
    assert "Whether it may be continued" in result.text


def test_an_assembled_context_serialises_what_it_dropped() -> None:
    """The route trace and the Inspector read this. A drop nobody can see after the fact is a
    drop that did not happen, as far as anyone reviewing the answer is concerned."""
    result: AssembledContext = assemble(_sections(residuals=12, history=True), budget=1_000)
    payload = result.as_dict()

    assert payload["is_complete"] is False
    assert payload["dropped"], "the dropped sections travel with the result"
    assert all(d["reason"] for d in payload["dropped"])
