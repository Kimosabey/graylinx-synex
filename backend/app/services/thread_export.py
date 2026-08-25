"""`C19` thread export — the conversation and the evidence behind it, leaving as one record
that somebody who was not there can check.

**The failure this prevents, with the numbers on it.** Inherited constraint 15 says every
artefact states its data window, and it exists because anomaly counts were once shown on the
database wall clock under a heading describing a telemetry window that did not overlap them at
all. An export is an artefact of exactly that kind: it is read weeks later, by someone who was
not in the conversation, against a snapshot whose measured window ended at 2026-06-23 11:50
and whose chilled-water flow stopped reading credibly after 2026-04-22 00:00. A reader with no
window supplies *now* from their own head, and every tense in the transcript inherits it.

**The second failure, and it is the worse one.** A thread export that silently drops a turn is
worse than no export, because it reads as complete. This is not hypothetical either: `C15`
turn memory is bounded by count, the oldest turn falls off deliberately and silently, and an
export built from memory alone would hand somebody a six-turn record of a nine-turn
conversation with nothing on its face to say so. So this module refuses to state completeness
it was not given: the caller supplies how many turns the conversation actually ran to, and
when it does not, the export says *that* rather than implying the count it holds is the count
there was.

**What an exported turn must carry**, and every one of these is a place an omission hides:

| Carried | Absent when | Rendered as |
|---|---|---|
| the question and the answer state | never | the six states of `CONTEXT.md` §7 |
| the evidence pack behind the answer | the turn never gathered one | a named omission |
| which audits passed and failed | the turn ended before the audits ran | *"no audit ran"* —
  never *"none failed"* |
| whether a model was spent | never | words, plus the degradation reason when it was not |
| the data window | there is no pack to carry one | a named omission, constraint 15 |
| claims with no supporting evidence line | never | `C24`, via `inline_evidence` |

**"No audit failed" and "no audit ran" are different statements**, and collapsing them is the
shape of inherited constraint 8 — six `not applicable` presses once opened a blocking gate
with zero evidence behind it. Four of the six skills are deterministic and never reach the
honesty audits at all, so the empty-failure-set case is the common one rather than the edge.

**Turns arrive structurally, not by import.** Contract 2 in `importlinter.ini` forbids
`app.services` importing `app.agents`, which is what keeps this module testable with the GPU
off and MySQL stopped. `app.agents.answer.Turn` satisfies the protocol below and is passed
straight in; the dependency simply points the other way, exactly as `domain.correlation` does
with an episode.

**Nothing here calls a model, and nothing here decides anything.** The export records what
already happened, including what it could not record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from app.analytics.honesty import DataWindow
from app.services.evidence import EvidencePack
from app.services.inline_evidence import pair_claims


class AuditFindingLike(Protocol):
    """One honesty audit's verdict. `app.agents.postcheck.AuditFinding` satisfies this."""

    audit: str
    passed: bool
    detail: str


class AuditReportLike(Protocol):
    """The six audits' verdicts. `app.agents.postcheck.AuditReport` satisfies this."""

    findings: tuple[AuditFindingLike, ...]


class ExportableTurn(Protocol):
    """What this module needs of a turn, and nothing more.

    `state` is typed `str` rather than `AnswerState` because the protocol describes a shape,
    and `AnswerState` is a `StrEnum` that satisfies it. The export renders whatever it is
    handed rather than re-deriving a state, since re-deriving one here would give the record
    a second opinion about how a turn ended.
    """

    question: str
    state: str
    text: str
    pack: EvidencePack | None
    audit: AuditReportLike | None
    used_model: bool
    degraded_reason: str


# ── what could not be exported ──────────────────────────────────────────────────

class OmissionReason(StrEnum):
    """Why a thing is missing from the export. Never a blank, never a dash.

    Each is a separate value because each needs a different action from the reader, and a
    single "incomplete" flag would tell them only that something is wrong.
    """

    NO_EVIDENCE_PACK = "no_evidence_pack"
    """The turn produced an answer without gathering evidence — a greeting, a refusal on an
    out-of-scope question, a request that named no asset with a fitted model. There is nothing
    to check the answer against, and that is a fact about the turn rather than a fault in the
    export."""

    NO_AUDIT_RUN = "no_audit_run"
    """The turn ended before the honesty audits. Four of the six skills are deterministic and
    never reach them, so an empty failure list here means *nothing was checked* — the
    `cannot_check` versus `not applicable` distinction of inherited constraint 8, one layer
    up."""

    NO_DATA_WINDOW = "no_data_window"
    """The turn carries no pack, so it carries no window. Constraint 15 is not satisfiable for
    this turn and the export says so rather than lending it the thread's window — a window
    borrowed from a different turn is the heading that did not overlap its counts."""

    TURN_NOT_RETAINED = "turn_not_retained"
    """The conversation ran longer than the turns handed to this export. `C15` memory is
    bounded by count and the oldest turn falls off silently, which is correct behaviour for a
    conversation and a defect in a record."""

    COMPLETENESS_UNKNOWN = "completeness_unknown"
    """Nobody told the export how many turns the conversation ran to, so it cannot state
    whether it is complete. This is the omission that must never be silent: an export with no
    completeness statement reads as complete."""


@dataclass(frozen=True)
class ExportOmission:
    """One thing the export could not carry, what it was about, and why.

    `subject` and `detail` are both required in practice: *"turn 3"* and *"the honesty audits
    never ran on it"* answer different halves of the reader's question.
    """

    reason: OmissionReason
    subject: str
    detail: str

    def render(self) -> str:
        return f"{self.subject}: {self.detail} [{self.reason.value}]"

    def as_dict(self) -> dict:
        return {"reason": self.reason.value, "subject": self.subject, "detail": self.detail}


# ── one turn ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExportedTurn:
    """One turn as it leaves, with everything a reader needs to check it — or the reason they
    cannot."""

    index: int
    question: str
    answer_state: str
    answer_text: str
    model_statement: str
    audit_statement: str
    window_statement: str
    claim_statement: str
    used_model: bool
    window: DataWindow | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    audits_passed: tuple[str, ...] = field(default_factory=tuple)
    audits_failed: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    unsupported_claims: tuple[str, ...] = field(default_factory=tuple)
    omissions: tuple[ExportOmission, ...] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        """No omission was recorded against this turn.

        A property rather than a stored flag so it cannot disagree with the list it summarises.
        """
        return not self.omissions

    def render(self) -> str:
        out = [
            f"── Turn {self.index + 1} ─────────────────────────────────────────────",
            f"Asked: {self.question}",
            f"Ended: {self.answer_state}",
            f"Window: {self.window_statement}",
            f"Model: {self.model_statement}",
            f"Audits: {self.audit_statement}",
            f"Claims: {self.claim_statement}",
            "",
            self.answer_text,
        ]
        if self.evidence:
            out.append("")
            out.append(f"Evidence behind this answer ({len(self.evidence)} line(s)):")
            out += [f"  - {line}" for line in self.evidence]
        if self.audits_failed:
            out.append("")
            out.append("Audits that did NOT pass:")
            out += [f"  - {name}: {detail}" for name, detail in self.audits_failed]
        if self.unsupported_claims:
            out.append("")
            out.append("Claims in this answer with no supporting evidence line:")
            out += [f"  - {claim}" for claim in self.unsupported_claims]
        if self.omissions:
            out.append("")
            out.append("This turn could not be exported in full:")
            out += [f"  - {o.render()}" for o in self.omissions]
        return "\n".join(out)

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "question": self.question,
            "answer_state": self.answer_state,
            "answer_text": self.answer_text,
            "window": self.window.as_dict() if self.window else None,
            "window_statement": self.window_statement,
            "used_model": self.used_model,
            "model_statement": self.model_statement,
            "evidence": list(self.evidence),
            "audits_passed": list(self.audits_passed),
            "audits_failed": [{"audit": a, "detail": d} for a, d in self.audits_failed],
            "audit_statement": self.audit_statement,
            "unsupported_claims": list(self.unsupported_claims),
            "claim_statement": self.claim_statement,
            "omissions": [o.as_dict() for o in self.omissions],
            "is_complete": self.is_complete,
        }


# ── the thread ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ThreadExport:
    """A whole conversation, its evidence, and a statement of what it could not carry."""

    turns: tuple[ExportedTurn, ...]
    omissions: tuple[ExportOmission, ...] = field(default_factory=tuple)
    turns_in_conversation: int | None = None

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def model_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.used_model)

    @property
    def windows(self) -> tuple[DataWindow, ...]:
        """The distinct windows this thread actually read, in first-seen order.

        Distinct rather than merged. Two turns about 15 April and 3 June do **not** make a
        thread covering April to June — the span between them was never read, and reporting it
        as one window is constraint 15's incident reproduced exactly.
        """
        seen: list[DataWindow] = []
        for turn in self.turns:
            if turn.window is not None and turn.window not in seen:
                seen.append(turn.window)
        return tuple(seen)

    def window_statement(self) -> str:
        """Constraint 15, at the level of the whole artefact."""
        windows = self.windows
        if not windows:
            return (
                "no turn in this thread gathered evidence, so this export covers no data "
                "window at all — that is an absence, not a window of zero length"
            )
        if len(windows) == 1:
            return windows[0].render()
        rendered = "; ".join(w.render() for w in windows)
        return (
            f"{len(windows)} distinct data windows, deliberately not merged into one span — "
            f"the period between them was never read: {rendered}"
        )

    def completeness_statement(self) -> str:
        """Whether this is the whole conversation, and how the export knows.

        Never silently affirmative. An export that cannot tell says it cannot tell, because a
        record with no completeness statement is read as complete.
        """
        if self.turns_in_conversation is None:
            return (
                f"{self.turn_count} turn(s) are in this export, and the number of turns the "
                f"conversation actually ran to was not supplied — so whether anything is "
                f"missing cannot be stated"
            )
        if self.turns_in_conversation > self.turn_count:
            missing = self.turns_in_conversation - self.turn_count
            return (
                f"{self.turn_count} of {self.turns_in_conversation} turn(s) are in this "
                f"export. {missing} turn(s) are MISSING — they fell out of the bounded turn "
                f"memory before the export was taken"
            )
        if self.turns_in_conversation < self.turn_count:
            return (
                f"{self.turn_count} turn(s) were handed to this export while the conversation "
                f"was said to run to {self.turns_in_conversation} — the two disagree, so "
                f"neither count is trustworthy and completeness is not claimed"
            )
        return f"all {self.turn_count} turn(s) of this conversation are in this export"

    def model_statement(self) -> str:
        spent = self.model_turn_count
        if spent == 0:
            return (
                f"no model was spent on any of {self.turn_count} turn(s) — every answer here "
                f"is deterministic, which is a fact about the record rather than a shortfall"
            )
        return f"a model composed the answer on {spent} of {self.turn_count} turn(s)"

    def all_omissions(self) -> tuple[ExportOmission, ...]:
        """Thread-level omissions first, then every turn's, in turn order.

        Gathered into one list because a reader checks *"what is missing"* once. Leaving them
        scattered through the turns is how an omission gets read past.
        """
        out = list(self.omissions)
        for turn in self.turns:
            out.extend(turn.omissions)
        return tuple(out)

    @property
    def unsupported_claim_count(self) -> int:
        return sum(len(t.unsupported_claims) for t in self.turns)

    def render(self) -> str:
        """The export as text. Every turn appears, whole or not."""
        header = [
            "Synex Copilot — thread export",
            "",
            f"Completeness: {self.completeness_statement()}.",
            f"Data window: {self.window_statement()}.",
            f"Model spend: {self.model_statement()}.",
            f"Claims with no supporting evidence line: {self.unsupported_claim_count}.",
            "",
        ]
        body = [t.render() for t in self.turns] or [
            "This export carries no turns at all. That is an empty conversation, not a "
            "conversation whose turns were all clean."
        ]
        omissions = self.all_omissions()
        tail = ["", "── What this export could not carry ──────────────────────────"]
        tail += (
            [f"  - {o.render()}" for o in omissions]
            if omissions
            else ["  Nothing. Every turn carried its evidence, its window and its audits."]
        )
        return "\n".join([*header, "\n\n".join(body), *tail])

    def as_dict(self) -> dict:
        return {
            "turn_count": self.turn_count,
            "turns_in_conversation": self.turns_in_conversation,
            "completeness_statement": self.completeness_statement(),
            "window_statement": self.window_statement(),
            "windows": [w.as_dict() for w in self.windows],
            "model_statement": self.model_statement(),
            "model_turn_count": self.model_turn_count,
            "unsupported_claim_count": self.unsupported_claim_count,
            "turns": [t.as_dict() for t in self.turns],
            "omissions": [o.as_dict() for o in self.all_omissions()],
        }


# ── assembly ────────────────────────────────────────────────────────────────────

def _model_statement(turn: ExportableTurn) -> str:
    """Whether a model was spent, and — when it was not — why not.

    The reason is carried rather than swallowed. *"The box is down"* and *"no transcript was
    recorded for this prompt"* are different problems, and a record that says only "no model"
    teaches a later reader neither.
    """
    if turn.used_model:
        return "a model composed this answer, over evidence it did not assemble"
    if turn.degraded_reason:
        return f"no model was spent — {turn.degraded_reason}"
    return (
        "no model was spent — this turn was answered deterministically, which is the design "
        "rather than a degradation"
    )


def _audit_lines(
    report: AuditReportLike | None,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...], str]:
    """`(passed, failed, statement)`.

    The statement is the load-bearing return value. An empty `failed` tuple means one of two
    entirely different things — every audit passed, or no audit ran — and a reader given only
    the tuple would read the second as the first.
    """
    if report is None:
        return (), (), (
            "no audit ran on this turn — it ended before the honesty layer, so this is not a "
            "record of six audits passing"
        )
    passed = tuple(f.audit for f in report.findings if f.passed)
    failed = tuple((f.audit, f.detail) for f in report.findings if not f.passed)
    if failed:
        return passed, failed, (
            f"{len(passed)} audit(s) passed and {len(failed)} did not: "
            + ", ".join(name for name, _ in failed)
        )
    return passed, failed, f"all {len(passed)} audit(s) that ran on this turn passed"


def _evidence_of(pack: EvidencePack) -> tuple[str, ...]:
    """The pack's own display strings, in the pack's own order, unaltered.

    Nothing is reformatted. The pack carries display strings rather than floats so that a
    figure can be compared by exact value, and re-rendering on the way into an export would
    reintroduce the tolerance that discipline exists to remove.
    """
    lines = [e.render() for e in pack.residual_evidence]
    lines += [
        (
            f"{g.gate.value}: {'passed' if g.passed else 'FAILED'}"
            + (f" — {g.reason}" if g.reason else "")
        )
        for g in pack.gates.results
    ]
    lines += [s.render() for s in pack.signal_notes]
    lines += [s.render() for s in pack.sources]
    return tuple(lines)


def export_turn(turn: ExportableTurn, index: int) -> ExportedTurn:
    """One turn, with an omission recorded for every part of it that does not exist.

    A turn with no pack is exported rather than skipped. Skipping it would produce a record
    whose turn numbering silently disagrees with the conversation, and a reader comparing the
    two would find a turn missing with no reason attached to the gap.
    """
    omissions: list[ExportOmission] = []
    subject = f"turn {index + 1}"

    pack = turn.pack
    if pack is None:
        omissions.append(
            ExportOmission(
                reason=OmissionReason.NO_EVIDENCE_PACK,
                subject=subject,
                detail=(
                    "no evidence pack was gathered, so this answer cannot be checked against "
                    "anything — the turn either named no asset with a fitted model, or was "
                    "answered without touching telemetry"
                ),
            )
        )
        omissions.append(
            ExportOmission(
                reason=OmissionReason.NO_DATA_WINDOW,
                subject=subject,
                detail=(
                    "with no pack there is no data window, and this turn is deliberately not "
                    "given another turn's window — constraint 15"
                ),
            )
        )

    passed, failed, audit_statement = _audit_lines(turn.audit)
    if turn.audit is None:
        omissions.append(
            ExportOmission(
                reason=OmissionReason.NO_AUDIT_RUN,
                subject=subject,
                detail=(
                    "the honesty audits never ran on this turn, so no audit result can be "
                    "reported — that is not the same as no audit failing"
                ),
            )
        )

    if pack is None:
        unsupported: tuple[str, ...] = ()
        claim_statement = (
            "claims cannot be paired to evidence on this turn, because there is no evidence "
            "pack to pair them against"
        )
        window_statement = "none — this turn gathered no evidence and states no window"
        evidence: tuple[str, ...] = ()
    else:
        rendering = pair_claims(turn.text, pack)
        unsupported = tuple(c.text for c in rendering.unsupported)
        claim_statement = rendering.support_statement()
        window_statement = pack.window.render()
        evidence = _evidence_of(pack)

    return ExportedTurn(
        index=index,
        question=turn.question,
        answer_state=str(turn.state),
        answer_text=turn.text,
        model_statement=_model_statement(turn),
        audit_statement=audit_statement,
        window_statement=window_statement,
        claim_statement=claim_statement,
        used_model=turn.used_model,
        window=pack.window if pack is not None else None,
        evidence=evidence,
        audits_passed=passed,
        audits_failed=failed,
        unsupported_claims=unsupported,
        omissions=tuple(omissions),
    )


def export(
    turns: tuple[ExportableTurn, ...], *, turns_in_conversation: int | None = None
) -> ThreadExport:
    """`C19`. Export the thread, and state what it could not carry.

    `turns_in_conversation` is the count the *conversation* reached, which is not necessarily
    the number of turns handed over: `C15` memory is bounded by count and drops its oldest
    turn silently. Supplying it is what lets the export say *"6 of 9, and 3 are missing"*.
    Omitting it is allowed and produces an explicit *"cannot state whether anything is
    missing"* — an export that quietly assumed it had everything would be the exact artefact
    this feature exists to replace.
    """
    exported = tuple(export_turn(turn, index) for index, turn in enumerate(turns))
    thread: list[ExportOmission] = []

    if turns_in_conversation is None:
        thread.append(
            ExportOmission(
                reason=OmissionReason.COMPLETENESS_UNKNOWN,
                subject="the thread",
                detail=(
                    "the number of turns this conversation ran to was not supplied, so this "
                    "export cannot state whether it holds all of them"
                ),
            )
        )
    elif turns_in_conversation > len(exported):
        missing = turns_in_conversation - len(exported)
        thread.append(
            ExportOmission(
                reason=OmissionReason.TURN_NOT_RETAINED,
                subject="the thread",
                detail=(
                    f"{missing} earlier turn(s) are not in this export — turn memory is "
                    f"bounded by count and the oldest falls off silently, which is correct "
                    f"for a conversation and a defect in a record"
                ),
            )
        )
    elif turns_in_conversation < len(exported):
        thread.append(
            ExportOmission(
                reason=OmissionReason.COMPLETENESS_UNKNOWN,
                subject="the thread",
                detail=(
                    f"{len(exported)} turn(s) were handed over while the conversation was "
                    f"said to run to {turns_in_conversation}; the counts disagree, so "
                    f"completeness is not claimed either way"
                ),
            )
        )

    return ThreadExport(
        turns=exported,
        omissions=tuple(thread),
        turns_in_conversation=turns_in_conversation,
    )
