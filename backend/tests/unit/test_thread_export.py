"""`C19` thread export — the conversation and its evidence leaving as one record, and the
record saying what it could not carry.

Two failures are being guarded against here and only one of them is obvious. The obvious one
is inherited constraint 15: an artefact with no data window is read against whatever *now*
the reader supplies from their own head. The second is worse — **an export that silently drops
a turn reads as complete**, and `C15` turn memory drops its oldest turn deliberately and
without a sound. A six-turn record of a nine-turn conversation is not a shorter truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.analytics.bands import ResidualBand
from app.analytics.gates import Gate, GateOutcome, GateResult, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.domain.answer import AnswerState
from app.services.evidence import EvidencePack, build_pack, window_for
from app.services.thread_export import (
    OmissionReason,
    export,
    export_turn,
)

MEASURED_END = datetime(2026, 6, 23, 11, 50)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(day: date = date(2026, 4, 15), *, blind: bool = False) -> EvidencePack:
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = (
        ResidualRow(
            "chiller_1",
            datetime(day.year, day.month, day.day, 9, 0),
            "CONDENSER_LOW_FLOW",
            values,
        ),
    )
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
        window=window_for(day, MEASURED_END),
        equipment_key="chiller_1",
        fault_label="CONDENSER_LOW_FLOW",
        day=day,
    )


# ── stand-ins for the agent-layer types ───────────────────────────────────────
# `app.services` may not import `app.agents` — contract 2 — so the export takes turns
# structurally. These are the shapes `Turn` and `AuditReport` present, and nothing more.


@dataclass(frozen=True)
class _Finding:
    audit: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class _Report:
    findings: tuple[_Finding, ...]


@dataclass
class _Turn:
    question: str = "why was chiller 1 flagged?"
    state: str = AnswerState.ANSWERED
    text: str = "The residual read -20.0 on 2026-04-15."
    pack: EvidencePack | None = field(default_factory=_pack)
    audit: _Report | None = None
    used_model: bool = False
    degraded_reason: str = ""


_CLEAN_AUDIT = _Report(
    (
        _Finding("numbers_are_grounded", True, "every number appears in the evidence"),
        _Finding("window_is_stated", True, "the answer states the window it covers"),
    )
)

_FAILED_AUDIT = _Report(
    (
        _Finding("numbers_are_grounded", False, "1 number appears in the answer and not in it"),
        _Finding("window_is_stated", True, "the answer states the window it covers"),
    )
)


# ── every turn appears, whole or not ──────────────────────────────────────────

def test_no_turn_is_ever_dropped_from_the_export() -> None:
    """A thread export that silently omits a turn is worse than none, because it reads as
    complete. A turn with nothing behind it is still exported — with the reason attached to
    the gap, rather than as a gap."""
    thread = export(
        (_Turn(), _Turn(question="hello", pack=None, text="I read this plant's telemetry.")),
        turns_in_conversation=2,
    )

    assert thread.turn_count == 2
    assert "hello" in thread.render()


def test_a_turn_without_a_pack_carries_its_reason_rather_than_a_blank() -> None:
    """A greeting gathers no evidence. That is a fact about the turn, not a fault in the
    export, and it must be said in words — an absence is not a zero and not a dash."""
    exported = export_turn(_Turn(pack=None, text="Ask me why a machine was flagged."), 0)

    reasons = {o.reason for o in exported.omissions}
    assert OmissionReason.NO_EVIDENCE_PACK in reasons
    assert exported.is_complete is False
    assert "cannot be checked against anything" in exported.render()


# ── constraint 15, at both levels ─────────────────────────────────────────────

def test_a_turn_without_a_pack_is_never_lent_another_turns_window() -> None:
    """Constraint 15's incident exactly: anomaly counts under a heading describing a window
    that did not overlap them. Borrowing a neighbouring turn's window would reproduce it
    inside a single record."""
    exported = export_turn(_Turn(pack=None, text="Hello."), 3)

    assert exported.window is None
    assert OmissionReason.NO_DATA_WINDOW in {o.reason for o in exported.omissions}
    assert "states no window" in exported.window_statement


def test_two_days_are_two_windows_and_are_never_merged_into_a_span() -> None:
    """April and June do not make a thread covering April to June. The period between them was
    never read, and reporting it as one window is the constraint-15 incident with a wider
    heading."""
    thread = export(
        (_Turn(pack=_pack(date(2026, 4, 15))), _Turn(pack=_pack(date(2026, 6, 3)))),
        turns_in_conversation=2,
    )

    assert len(thread.windows) == 2
    assert "deliberately not merged" in thread.window_statement()


def test_a_thread_with_no_evidence_states_the_absence_rather_than_omitting_the_window() -> None:
    """The export is an artefact, so it states a window even when there is none — and the
    words say absence rather than a window of zero length."""
    thread = export((_Turn(pack=None, text="Hello."),), turns_in_conversation=1)

    assert "covers no data window at all" in thread.window_statement()
    assert "Data window:" in thread.render()


# ── no audit ran is not no audit failed ───────────────────────────────────────

def test_a_turn_that_never_reached_the_audits_says_so_rather_than_reporting_none_failed() -> None:
    """Four of the six skills are deterministic and never reach the honesty layer, so the
    empty-failure-set case is the common one. Reading it as "nothing failed" is inherited
    constraint 8's failure — a gate opened by six `not applicable` presses."""
    exported = export_turn(_Turn(audit=None), 0)

    assert exported.audits_failed == ()
    assert "no audit ran on this turn" in exported.audit_statement
    assert "not a record of six audits passing" in exported.audit_statement
    assert OmissionReason.NO_AUDIT_RUN in {o.reason for o in exported.omissions}


def test_a_clean_audit_and_an_absent_one_do_not_read_alike() -> None:
    """The two produce identical `audits_failed` tuples, so the statement is the only thing
    telling them apart. It must."""
    ran = export_turn(_Turn(audit=_CLEAN_AUDIT), 0)
    never = export_turn(_Turn(audit=None), 0)

    assert ran.audits_failed == never.audits_failed == ()
    assert ran.audit_statement != never.audit_statement
    assert "passed" in ran.audit_statement


def test_a_failed_audit_travels_with_its_detail() -> None:
    """"An audit failed" is not checkable by somebody who was not there. Which audit, and what
    it found, is."""
    exported = export_turn(_Turn(audit=_FAILED_AUDIT), 0)

    assert exported.audits_failed[0][0] == "numbers_are_grounded"
    assert "not in it" in exported.audits_failed[0][1]
    assert "Audits that did NOT pass" in exported.render()


# ── completeness is never assumed ─────────────────────────────────────────────

def test_an_export_that_was_not_told_the_conversation_length_refuses_to_claim_completeness(
) -> None:
    """The omission that must never be silent. A record with no completeness statement is read
    as complete, and `C15` memory drops its oldest turn without a sound."""
    thread = export((_Turn(),))

    assert "cannot be stated" in thread.completeness_statement()
    assert OmissionReason.COMPLETENESS_UNKNOWN in {o.reason for o in thread.all_omissions()}


def test_missing_turns_are_counted_and_named() -> None:
    """Six of nine is the shape this feature exists for: turn memory is bounded by count, the
    oldest falls off deliberately, and the export is the place that has to say so."""
    thread = export((_Turn(), _Turn()), turns_in_conversation=5)

    assert "3 turn(s) are MISSING" in thread.completeness_statement()
    assert OmissionReason.TURN_NOT_RETAINED in {o.reason for o in thread.all_omissions()}


def test_a_complete_thread_says_so_plainly() -> None:
    """The affirmative case must be reachable, or the statement is decoration nobody reads."""
    thread = export((_Turn(audit=_CLEAN_AUDIT),), turns_in_conversation=1)

    assert "all 1 turn(s) of this conversation" in thread.completeness_statement()
    assert thread.all_omissions() == ()


def test_a_count_smaller_than_the_turns_handed_over_is_reported_not_trusted() -> None:
    """The two sources disagree, so neither is trustworthy. Picking one silently would put a
    false completeness claim on the record; raising would lose the export entirely."""
    thread = export((_Turn(), _Turn(), _Turn()), turns_in_conversation=1)

    assert "the counts disagree" in thread.all_omissions()[0].detail
    assert "not claimed either way" in thread.all_omissions()[0].detail


def test_an_empty_export_says_the_conversation_was_empty_rather_than_clean() -> None:
    """Zero unsupported claims across zero turns is not a clean thread, and a reader skimming
    the header would take it for one."""
    rendered = export((), turns_in_conversation=0).render()
    assert "not a conversation whose turns were all clean" in rendered


# ── the model spend ───────────────────────────────────────────────────────────

def test_a_turn_that_spent_no_model_says_why_not() -> None:
    """"The box is down" and "no transcript was recorded for this prompt" are different
    problems. A record saying only "no model" teaches a later reader neither."""
    exported = export_turn(_Turn(degraded_reason="no transcript recorded for this prompt"), 0)
    assert "no transcript recorded for this prompt" in exported.model_statement


def test_a_deterministic_turn_is_not_reported_as_a_degradation() -> None:
    """Four of the six skills spend no model by design. Reporting that as degradation would
    describe the architecture as a fault on every look-up the platform serves."""
    exported = export_turn(_Turn(used_model=False, degraded_reason=""), 0)
    assert "the design rather than a degradation" in exported.model_statement


def test_the_thread_states_whether_a_model_was_spent_at_all() -> None:
    """`C19` requires it per turn; a reader wants it once, at the top."""
    thread = export((_Turn(), _Turn(used_model=True)), turns_in_conversation=2)

    assert thread.model_turn_count == 1
    assert "1 of 2 turn(s)" in thread.model_statement()


# ── the evidence, and the claims with none ────────────────────────────────────

def test_the_evidence_pack_behind_each_answer_travels_with_the_turn() -> None:
    """"Somebody who was not there can check it" is the whole feature. An export carrying the
    prose and not the evidence is a transcript."""
    exported = export_turn(_Turn(), 0)
    assert exported.evidence
    assert any("chiller_current_residual" in line for line in exported.evidence)


def test_an_unsupported_claim_is_carried_into_the_export() -> None:
    """`C24` inside `C19`. A reader weeks later cannot re-derive which sentences had nothing
    behind them, so the export has to have recorded it at the time."""
    exported = export_turn(_Turn(text="Efficiency reached 1.40 that month."), 0)

    assert exported.unsupported_claims == ("Efficiency reached 1.40 that month.",)
    assert "no supporting evidence line" in exported.render()


def test_claims_cannot_be_paired_without_a_pack_and_the_export_says_which() -> None:
    """Zero unsupported claims because there was nothing to pair against is not zero
    unsupported claims because every claim was supported."""
    exported = export_turn(_Turn(pack=None, text="Efficiency reached 1.40."), 0)

    assert exported.unsupported_claims == ()
    assert "no evidence pack to pair them against" in exported.claim_statement


# ── the serialised shape ──────────────────────────────────────────────────────

def test_the_serialised_export_carries_the_omissions_and_not_just_the_turns() -> None:
    """An API consumer that reads only `turns` would rebuild the silent-omission failure on
    the far side of the wire."""
    payload = export((_Turn(pack=None, text="Hello."),)).as_dict()

    assert payload["omissions"], "omissions must survive serialisation"
    assert payload["completeness_statement"]
    assert payload["window_statement"]
    assert payload["turns"][0]["window"] is None


def test_the_rendered_export_always_has_a_could_not_carry_section() -> None:
    """Present even when it is empty, so its absence is never what a reader has to notice."""
    rendered = export((_Turn(audit=_CLEAN_AUDIT),), turns_in_conversation=1).render()

    assert "What this export could not carry" in rendered
    assert "Nothing. Every turn carried its evidence" in rendered
