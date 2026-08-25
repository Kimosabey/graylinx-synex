"""The context budget, wired into the prompt that is actually sent — and the no-op that proves it.

**Two failures meet here.** The first: `max_context_chars` is 24,000 and `max_input_chars` is
8,000, and until 2026-08-18 nothing in the request path read either. A budgeter existed in
`app/agents/context.py` and the only thing that imported it was its own test, which is the
defect this repository keeps finding — machinery with no consumer. It could not be wired where
it belonged either, because `app.prompts` sits below `app.agents` in the spine and
`build_messages` structurally could not see it; the module moved down rather than an import
contract being switched off.

**The second, and the one this file mostly guards: changing `build_messages` invalidates every
recorded transcript.** A transcript is keyed on a hash of the exact messages, so a payload
merely *reformatted* on the way through would rekey all eight recordings captured on the Jarvis
box on 2026-08-17 and take the offline replay with them — and with it the property that this
whole suite runs with the GPU terminated. The seven `diagnose` payloads measure 3,080 to 3,300
characters against a 24,000 ceiling, so nothing is dropped today. The first test below asserts
that against the recorded prompts themselves, byte for byte, rather than against a fixture of
what they might contain.

**What must never be dropped**, in this order: the gate outcome, any never-measured or suspect
signal note, the data window, the fault label. Dropping a residual to fit is acceptable;
dropping *"this signal was never measured"* is not, because one costs a reader a line and the
other costs them the reason the branch cannot be judged at all.
"""
from __future__ import annotations

import functools
import json
from datetime import date, datetime

import pytest

from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_running
from app.config import CONTEXT_TRUNCATION_MARKER, get_settings
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.llm.client import TRANSCRIPT_DIR
from app.prompts import budget, explain
from app.services.evidence import build_pack, window_for

DAY = date(2026, 4, 15)
MEASURED_END = datetime(2026, 6, 23, 11, 50)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(label: str | None = "CONDENSER_LOW_FLOW"):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = (ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), label or "", values),)
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=GateOutcome((check_running({"a": 141.0}),)),
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label=label,
        day=DAY,
    )


@functools.lru_cache(maxsize=1)
def _ceilings_where_the_trade_happens() -> tuple[int, ...]:
    """Every ceiling at which *some* residuals survive and some do not — derived, not chosen.

    **A literal ceiling here is a test that stops testing without failing.** The ceiling is
    measured on the whole message pair, so the room left for the payload is it minus the
    system prompt — and the system prompt is 2,434 characters of rules that grow when a rule
    is added. Three tests below were written against literals, and adding the rule about
    recalled numbers moved every one of them out of the band and into the refusal path: two
    went red honestly, and one kept passing while asserting nothing it was written to assert.

    So the band is measured against the prompt as it stands today, and the tests assert their
    property at *every* ceiling in it rather than at one number somebody picked.
    """
    pack = _pack()
    whole = len(budget.render_prompt_data(pack.to_prompt_data()))
    scaffold = len(explain.SYSTEM_PROMPT) + len(explain._user_message("", "why?"))
    total = len(pack.to_prompt_data()["residuals"])

    band = []
    for ceiling in range(scaffold, scaffold + whole + 1, 10):
        evidence = explain.build_fitted_messages(pack, "why?", context_budget=ceiling).evidence
        kept = [] if evidence.must_refuse else evidence.prompt_data.get("residuals", [])
        if 0 < len(kept) < total:
            band.append(ceiling)
    return tuple(band)


def _recorded_diagnose_prompts() -> list[tuple[str, str]]:
    """Every `diagnose` transcript on disk as (source, the exact user message it recorded)."""
    out: list[tuple[str, str]] = []
    for path in sorted(TRANSCRIPT_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("task") != "diagnose":
            continue
        out.append((path.name, str(record["messages"][-1]["content"])))
    return out


# ════════════════════════════════════════════════════════════════════════════════
# The no-op. Everything else in this file is downstream of it holding.
# ════════════════════════════════════════════════════════════════════════════════

def test_a_recorded_prompt_is_rebuilt_byte_for_byte_after_the_budgeter_was_wired_in() -> None:
    """**The load-bearing test.** If this fails, the eight transcripts no longer replay.

    Each recorded prompt is taken apart into the payload the model was handed and the question
    it was asked, put back through the fitted builder, and compared character for character
    with what the box received. Not *equivalent JSON* — the same string, because the key is a
    hash of the bytes and a reordered dict or a different separator is a different recording.
    """
    prompts = _recorded_diagnose_prompts()
    assert prompts, "no diagnose transcript is recorded here, so nothing was verified"

    for source, recorded in prompts:
        head, payload, tail = recorded.split(explain.FENCE)
        question = tail.split("The person asked: ", 1)[1].split("\n\n")[0]
        prompt_data = json.loads(payload)

        room = 24_000 - len(explain.SYSTEM_PROMPT) - len(explain._user_message("", question))
        fitted = budget.fit_prompt_data(prompt_data, budget=room)

        assert fitted.is_unchanged, (
            f"{source}: the payload was altered — {fitted.render_drop_report()}"
        )
        assert head == ""
        assert explain._user_message(fitted.rendered, question) == recorded, (
            f"{source}: the rebuilt prompt differs from the recorded one. The transcript is "
            f"keyed on these exact bytes and no longer replays."
        )


def test_a_pack_under_budget_produces_exactly_what_an_unbudgeted_build_produced() -> None:
    """The same guarantee, stated against the code rather than against the fixtures.

    The expected string is built the way `build_messages` built it before the budgeter existed
    — `json.dumps(sanitise(pack.to_prompt_data()), indent=2, ensure_ascii=False)` — so the
    assertion fails if the payload is ever normalised, re-keyed or re-indented on the way
    through, whatever the transcripts happen to hold.
    """
    pack = _pack()
    expected = json.dumps(
        explain.sanitise(pack.to_prompt_data()), indent=2, ensure_ascii=False
    )
    messages = explain.build_messages(pack, "why was this flagged?")

    assert messages[0]["content"] == explain.SYSTEM_PROMPT
    assert messages[1]["content"].split(explain.FENCE)[1] == f"\n{expected}\n"


def test_the_fitted_builder_says_plainly_that_it_changed_nothing() -> None:
    """An absence of drops is stated, not left blank. *"Nothing was dropped"* is a claim a
    reader can rely on only if the thing that fitted the prompt is the thing making it."""
    fitted = explain.build_fitted_messages(_pack(), "why was this flagged?")

    assert fitted.is_unchanged
    assert fitted.evidence.dropped == ()
    assert "nothing was dropped" in fitted.render_report()
    assert str(fitted.evidence.used_chars) in fitted.render_report()


def test_the_ceiling_counts_the_system_prompt_and_the_question_not_the_payload_alone() -> None:
    """A budget that ignored the 2,434-character system prompt would be a ceiling that does not
    hold. The measured pair on the box runs 5,712 to 5,929 characters, and the room left for
    the evidence is what is left after the rules, the fence and the question."""
    question = "why was this flagged?"
    fitted = explain.build_fitted_messages(_pack(), question)
    pair = sum(len(m["content"]) for m in fitted.messages)

    assert fitted.evidence.budget < get_settings().max_context_chars
    assert pair <= get_settings().max_context_chars


@pytest.mark.parametrize("ceiling", [5_000, 5_100, 5_400, 5_550, 24_000])
def test_the_whole_message_pair_stays_inside_the_ceiling(ceiling: int) -> None:
    """The bound is the point. A ceiling that holds for most inputs is one that fails on an
    unpredictable turn, which is the worst place to discover a limit."""
    fitted = explain.build_fitted_messages(
        _pack(), "why was this flagged?", context_budget=ceiling
    )
    pair = sum(len(m["content"]) for m in fitted.messages)

    if not fitted.evidence.must_refuse:
        assert pair <= ceiling


# ════════════════════════════════════════════════════════════════════════════════
# What is given up, and what never is
# ════════════════════════════════════════════════════════════════════════════════

def test_what_did_not_fit_is_written_into_the_payload_the_model_reads() -> None:
    """Reporting the drop only to the caller is half a fix: the caller can log it, but the
    sentence a reader sees is written by something that still believes it saw everything."""
    fitted = explain.build_fitted_messages(_pack(), "why?", context_budget=5_400)
    payload = json.loads(fitted.messages[1]["content"].split(explain.FENCE)[1])

    assert fitted.evidence.dropped, "this ceiling cannot hold the whole pack"
    assert budget.DROP_NOTE_KEY in payload
    assert CONTEXT_TRUNCATION_MARKER in payload[budget.DROP_NOTE_KEY]
    for drop in fitted.evidence.dropped:
        assert drop.reason.strip(), "every drop carries its reason in words"
        assert "ceiling" in drop.reason


@pytest.mark.parametrize("ceiling", [5_100, 5_200, 5_400, 5_550])
def test_the_honesty_payload_survives_every_ceiling_that_can_hold_it(ceiling: int) -> None:
    """The four that are never dropped. `cond_flow` has never recorded a non-zero value in
    37,430 measured slots and feeds four of the six models, so the note that says so is the
    least droppable thing in the pack — and on the measured pack the provenance lines are 1,552
    of 2,936 characters, which makes them the most tempting thing to give up."""
    fitted = explain.build_fitted_messages(_pack(), "why?", context_budget=ceiling)
    payload = json.loads(fitted.messages[1]["content"].split(explain.FENCE)[1])

    for key in ("gates", "may_diagnose", "signal_provenance", "data_window", "fault_label"):
        assert payload.get(key), f"{key} was dropped at a ceiling of {ceiling}"
    assert "never_measured" in json.dumps(payload["signal_provenance"])


def test_the_machine_and_the_day_are_protected_because_losing_them_breaks_a_gate() -> None:
    """Not honesty payload, and protected anyway. An answer that cannot name its machine fails
    `equipment_exists`, and one whose day is gone leaves `window_is_stated` with nothing to be
    checked against — so dropping either turns a budget problem into an honesty failure."""
    fitted = explain.build_fitted_messages(_pack(), "why?", context_budget=5_100)
    payload = json.loads(fitted.messages[1]["content"].split(explain.FENCE)[1])

    assert payload["equipment"] == "Chiller 1"
    assert payload["day"] == "2026-04-15"
    assert {"equipment", "day"} <= set(budget.PROTECTED_KEYS)


def test_a_residual_is_given_up_before_a_signal_note_and_from_the_end_first() -> None:
    """The specific trade, asserted rather than assumed — and the order within it.

    *"Residuals 1 to 4 are here, 5 and 6 are not"* is a sentence a reader can verify against
    the pack. The output of a knapsack is not, which is why the last residual goes first rather
    than the largest one.
    """
    whole = _pack().to_prompt_data()["residuals"]
    band = _ceilings_where_the_trade_happens()

    assert band, "no ceiling gives up some residuals and keeps others — the trade never happens"
    for ceiling in band:
        fitted = explain.build_fitted_messages(_pack(), "why?", context_budget=ceiling)
        payload = json.loads(fitted.messages[1]["content"].split(explain.FENCE)[1])
        kept = payload.get("residuals", [])

        assert 0 < len(kept) < len(whole), ceiling
        assert kept == whole[: len(kept)], f"at {ceiling} the kept set is not the opening run"
        assert payload["signal_provenance"], f"at {ceiling} a signal note went for a residual"


def test_supporting_detail_is_surrendered_before_any_residual() -> None:
    """Lineage and a severity that is not yet agreed are the cheapest things in the pack. A
    reader who has already lost the residual has no use for the line describing where it came
    from."""
    fitted = explain.build_fitted_messages(_pack(), "why?", context_budget=5_400)
    given_up = [d.key for d in fitted.evidence.dropped]

    assert given_up, "this ceiling cannot hold the whole pack"
    first_residual = next(
        (i for i, key in enumerate(given_up) if key.startswith("residuals")), len(given_up)
    )
    supporting = [
        i for i, key in enumerate(given_up) if key in budget._SUPPORTING_KEYS
    ]
    assert supporting, "the supporting keys go before the evidence does"
    assert max(supporting) < first_residual


def test_the_surrender_table_and_the_drop_order_do_not_disagree() -> None:
    """Two tables would drift, and the drift would be invisible: the prompt would give up
    evidence while the documented order still said history first."""
    ranks = [budget.DROP_ORDER.index(tier) for _, tier in budget.SURRENDER_ORDER]

    assert ranks == sorted(ranks), "the surrender table walks a different order to DROP_ORDER"
    assert {tier for _, tier in budget.SURRENDER_ORDER} == set(budget.DROP_ORDER)


def test_a_payload_that_cannot_fit_even_stripped_refuses_rather_than_trimming_the_payload() -> None:
    """The one case with no honest prompt inside the ceiling. Trimming would cut the part that
    must never be cut, so the payload comes back whole and marked unsendable — a refusal is not
    an error, and it is not a truncation either."""
    fitted = explain.build_fitted_messages(_pack(), "why?", context_budget=5_000)
    payload = json.loads(fitted.messages[1]["content"].split(explain.FENCE)[1])

    assert fitted.evidence.must_refuse
    assert "Q84" in fitted.evidence.refusal_reason
    assert "the never-measured and suspect signal notes" in fitted.evidence.refusal_reason
    for key in ("gates", "signal_provenance", "data_window", "fault_label", "equipment"):
        assert payload.get(key), f"{key} was trimmed rather than the turn being refused"


# ════════════════════════════════════════════════════════════════════════════════
# Presence, which ordering the payload first does nothing about
# ════════════════════════════════════════════════════════════════════════════════

def test_a_payload_missing_its_gate_outcome_is_reported_absent_not_answered_around() -> None:
    """The review's finding: `assemble()` protected the honesty payload and never checked it had
    arrived. A pack with no gate outcome came back complete and silent, which is the
    never-measured defect by its own door — an absence reading as *nothing to say*."""
    data = _pack().to_prompt_data()
    data["gates"] = []
    data["may_diagnose"] = ""
    fitted = budget.fit_prompt_data(data, budget=24_000)

    assert [a.tier for a in fitted.absent_payload] == [budget.ContextTier.GATE_OUTCOME]
    assert fitted.is_unchanged is False
    assert "5,309 slots against 674 faulted" in fitted.absent_payload[0].reason
    assert budget.ABSENCE_NOTE_KEY in fitted.prompt_data


def test_the_model_is_told_which_part_of_the_payload_never_arrived() -> None:
    """Told rather than left to infer, for the same reason the drop note exists: the answer is
    otherwise written by something that believes it saw everything it needed."""
    data = _pack().to_prompt_data()
    data["signal_provenance"] = []
    data["model_fit_warning"] = ""
    fitted = budget.fit_prompt_data(data, budget=24_000)

    note = fitted.prompt_data[budget.ABSENCE_NOTE_KEY]
    assert "signal_note" in note
    assert "37,430 measured slots" in note
    assert "Say what is missing rather than answering around it." in note


def test_an_empty_signal_list_is_an_absence_and_not_a_present_empty_thing() -> None:
    """A pack carrying `"signal_provenance": []` told the model nothing about provenance. The
    registry covers 5 of a normalized table's 38 columns, so *"no note"* and *"no signal has a
    problem"* are very different statements and only one of them is true."""
    assert budget.absent_payload_in(()) != ()
    absent = {a.tier for a in budget.absent_payload_in(())}
    assert absent == set(budget.HONESTY_PAYLOAD)


def test_an_absence_reported_without_a_reason_is_refused_at_construction() -> None:
    """An absence a reader cannot act on is a dash wearing a sentence. An invariant rather than
    an instruction, because an instruction is followed most of the time."""
    with pytest.raises(ValueError, match="dash wearing a sentence"):
        budget.AbsentPayload(tier=budget.ContextTier.DATA_WINDOW, reason="  ")


def test_assemble_carries_the_missing_payload_note_into_the_text_the_model_reads() -> None:
    """The same check on the section-based path, which `assemble_turn` uses for a turn that
    carries a task trail as well as a pack."""
    sections = (
        budget.ContextSection("data_window", budget.ContextTier.DATA_WINDOW, "window — 15 Apr"),
        budget.ContextSection("fault_label", budget.ContextTier.FAULT_LABEL, "label — X"),
        budget.ContextSection("signal.1", budget.ContextTier.SIGNAL_NOTE, "signal — never"),
    )
    result = budget.assemble(sections, budget=24_000)

    assert result.is_complete is False, "a missing gate outcome is not a complete context"
    assert [a.tier for a in result.absent_payload] == [budget.ContextTier.GATE_OUTCOME]
    assert "gate_outcome" in result.text
    assert "gate_outcome" in result.render_drop_report()
    assert result.as_dict()["absent_payload"][0]["reason"]


# ════════════════════════════════════════════════════════════════════════════════
# The input ceiling, which arrives with the question rather than with the pack
# ════════════════════════════════════════════════════════════════════════════════

def test_a_question_inside_the_input_ceiling_is_sent_untouched() -> None:
    """The ordinary path must not mark anything. A marker on an intact question would teach a
    reader to ignore markers, and it would rekey every transcript on disk."""
    fitted = explain.build_fitted_messages(_pack(), "why was this flagged?")

    assert fitted.question_was_clipped is False
    assert CONTEXT_TRUNCATION_MARKER not in fitted.messages[1]["content"]
    assert "fitted the" in fitted.question_note


def test_a_pasted_wall_of_text_is_clipped_and_the_prompt_says_it_was() -> None:
    """`max_input_chars` stops a pasted wall of text becoming a VRAM spike. Clipping is fine;
    clipping without saying so means the model answers a question it only half received, and
    the answer reads as though it addressed the whole thing."""
    fitted = explain.build_fitted_messages(_pack(), "why " * 4_000)

    assert fitted.question_was_clipped is True
    assert fitted.is_unchanged is False
    assert CONTEXT_TRUNCATION_MARKER in fitted.messages[1]["content"]
    assert "were not sent" in fitted.question_note


def test_both_ceilings_come_from_configuration_rather_than_from_here() -> None:
    """One source of truth per fact. `max_context_chars` and `max_input_chars` are provisional
    against `Q48`, and a second copy would let the two disagree the day somebody answers it."""
    settings = get_settings()
    _, reason = budget.fit_question("x")

    assert str(settings.max_input_chars) in reason
    assert budget.fit_prompt_data({"data_window": "x"}).budget == settings.max_context_chars


def test_the_fitting_is_the_same_code_the_agent_layer_re_exports() -> None:
    """`app/agents/context.py` re-exports this module so `C10` and the budget read as one idea
    from the agent layer. Two copies would be two ceilings, and the second one would be the one
    nobody had wired to a prompt."""
    from app.agents import context

    assert context.fit_prompt_data is budget.fit_prompt_data
    assert context.assemble is budget.assemble
    assert context.HONESTY_PAYLOAD is budget.HONESTY_PAYLOAD
