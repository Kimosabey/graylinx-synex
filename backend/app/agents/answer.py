"""One turn, end to end — and the deterministic answer it falls back to.

The order matters and is the product:

    route → assemble the pack → check the gates → (model explains) → audit → state

**The model is reached at exactly one point**, and only after the gates have already decided
whether anything may be claimed. It explains a verdict it did not produce. If it is
unreachable, the turn still completes with a deterministic summary built from the pack —
`CONTEXT.md` §13 requires stating degraded mode rather than silently substituting a weaker
capability, and a demonstration where the box wedges should lose its prose, not its answer.

**A refusal is composed, not assembled.** `NO_DIAGNOSIS` gets its own prompt and its own SSE
frame (D-015), because rendering a refusal through the answer path softens it by
presentation — and on this data the refusal is the modal outcome, 5,309 slots against 674.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.agents import postcheck, skills
from app.agents.router import RouteDecision, Skill, route
from app.analytics.bands import ResidualBand
from app.analytics.gates import (
    GateOutcome,
    check_band_available,
    check_measured_window,
    check_physically_plausible,
    check_running,
)
from app.db.plant import ResidualRow
from app.domain import equipment as eq
from app.domain.answer import AnswerState
from app.llm.client import ModelClient, ModelUnavailable
from app.prompts.explain import build_messages, build_no_diagnosis_messages
from app.services.evidence import EvidencePack

CONVERSE_REPLY = (
    "I read this plant's chiller telemetry and the faults detected on it. Ask me why a "
    "machine was flagged on a given day, what a residual means for that specific asset, or "
    "what the evidence does and does not support. I will tell you when the data cannot "
    "answer — on this snapshot that is the most common outcome, and it is a real answer "
    "rather than a failure."
)


@dataclass
class Turn:
    """Everything one turn produced. Serialised into SSE frames by the API layer."""

    question: str
    state: AnswerState
    text: str
    route: RouteDecision
    pack: EvidencePack | None = None
    audit: postcheck.AuditReport | None = None
    used_model: bool = False
    degraded_reason: str = ""
    badges: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_refusal(self) -> bool:
        return self.state is AnswerState.NO_DIAGNOSIS


def build_gates(
    rows: tuple[ResidualRow, ...],
    band: ResidualBand | None,
    equipment_key: str,
    day: date,
    measured_window_end: datetime,
) -> GateOutcome:
    """The four evaluable gates, in evaluation order.

    The threshold gates (`Q3` load floor, `Q6` persistence) are deliberately absent: they
    refuse by design because nobody has agreed their numbers, and including them would make
    every single turn refuse for a reason no reader could act on.
    """
    representative = rows[-1] if rows else None
    signal_values = dict(representative.residuals) if representative else {}
    slot_time = representative.slot_time if representative else datetime(
        day.year, day.month, day.day
    )
    known = eq.by_key(equipment_key)
    return GateOutcome(
        (
            check_running(signal_values),
            check_band_available(band, known.display_name if known else equipment_key),
            check_measured_window(slot_time, measured_window_end),
            check_physically_plausible(),
        )
    )


def deterministic_answer(pack: EvidencePack) -> str:
    """The answer when no model is available — assembled, not composed.

    Deliberately flat. It is not trying to sound like the model; it is trying to be
    unambiguously correct, so that a reader can tell at a glance that the prose layer is
    absent rather than wonder why the writing got worse.
    """
    lines = [
        f"{pack.equipment_display} on {pack.day.isoformat()} "
        f"({pack.slot_count} slot(s), {pack.window.render()}).",
        f"Detected label: {pack.fault_label or 'none on this slot'}. "
        f"Severity: {pack.severity_text}.",
    ]
    if pack.is_undecidable:
        lines.append(
            "This label declares itself undecidable: the data could not separate the "
            "candidate causes, and narrowing it further would invent a certainty nobody has."
        )
    for evidence in pack.residual_evidence:
        lines.append(f"  - {evidence.render()}")
    if pack.other_labels_same_day:
        lines.append(
            "Other labels on this machine the same day: "
            + ", ".join(pack.other_labels_same_day)
            + ". One repair may explain several of them."
        )
    absent = [s.render() for s in pack.signal_notes]
    if absent:
        lines.append("Signals that cannot be read on this plant: " + "; ".join(absent))
    return "\n".join(lines)


def deterministic_refusal(pack: EvidencePack) -> str:
    failed = [g for g in pack.gates.results if not g.passed]
    lines = [
        f"No diagnosis for {pack.equipment_display} on {pack.day.isoformat()}. "
        f"{len(failed)} check(s) did not pass:"
    ]
    for gate in failed:
        lines.append(f"  - {gate.gate.value}: {gate.reason}")
        if gate.remedy:
            lines.append(f"    What would change this: {gate.remedy}")
    return "\n".join(lines)


async def answer_turn(
    *,
    question: str,
    pack: EvidencePack | None,
    client: ModelClient | None,
    mode_override: str | None = None,
    last_equipment: str | None = None,
) -> Turn:
    """Run the turn. Never raises — a failure becomes a state, because a stack trace is not
    an answer and on a demonstration it reads as a broken product."""
    decision = route(question, mode_override=mode_override, last_equipment=last_equipment)

    if decision.skill is Skill.REFUSE:
        return Turn(
            question=question,
            state=AnswerState.BLOCKED,
            text=decision.refusal_text,
            route=decision,
        )

    if decision.skill is Skill.CONVERSE:
        return Turn(
            question=question,
            state=AnswerState.ANSWERED,
            text=CONVERSE_REPLY,
            route=decision,
        )

    if pack is None:
        return Turn(
            question=question,
            state=AnswerState.NO_DIAGNOSIS,
            text=(
                "There is no scored evidence for that request. Only chiller 1 and chiller 2 "
                "have a fitted model and a reference band; the other ten equipment tables "
                "carry telemetry and nothing that can be judged against it."
            ),
            route=decision,
        )

    # ── the skill decides which question is being answered ──────────────────────
    # Until 2026-08-17 every skill below `converse` fell through to the explain path, so the
    # router resolved `look_up`, `prepare_work`, `resolve` and `verify` correctly, carried the
    # skill into the route frame, and then ignored it. A router whose decision changes nothing
    # only looks like a router. Four of the five spend no model at all.
    outcome = skills.dispatch(decision.skill.value, pack)
    if outcome is not None:
        return Turn(
            question=question,
            state=outcome.state,
            text=outcome.text,
            route=decision,
            pack=pack,
            used_model=outcome.used_model,
        )

    # ── the gates decide before the model is reached ────────────────────────────
    if not pack.may_diagnose:
        text, used_model, degraded = await _compose(
            client,
            build_no_diagnosis_messages(pack, question),
            fallback=deterministic_refusal(pack),
            task="narrate",
            role="text",
        )
        return Turn(
            question=question,
            state=AnswerState.NO_DIAGNOSIS,
            text=text,
            route=decision,
            pack=pack,
            used_model=used_model,
            degraded_reason=degraded,
        )

    # ── the model explains a verdict it did not produce ─────────────────────────
    text, used_model, degraded = await _compose(
        client,
        build_messages(pack, question),
        fallback=deterministic_answer(pack),
        task="diagnose",
        role="brain",
    )

    # ── the honesty layer overrides the model ───────────────────────────────────
    report = postcheck.run_audits(text, pack)
    badges = tuple(f.audit for f in report.soft_failures)

    if report.must_replace_answer:
        # Constraint 16. Replaced outright, and the record marks it corrected — a reassuring
        # paragraph followed by a caveat is still read as reassuring.
        return Turn(
            question=question,
            state=AnswerState.PARTIAL,
            text=postcheck.correction_for(report, pack),
            route=decision,
            pack=pack,
            audit=report,
            used_model=used_model,
            degraded_reason=degraded,
            badges=badges,
        )

    return Turn(
        question=question,
        state=AnswerState.ANSWERED,
        text=text,
        route=decision,
        pack=pack,
        audit=report,
        used_model=used_model,
        degraded_reason=degraded,
        badges=badges,
    )


async def _compose(
    client: ModelClient | None,
    messages: list[dict[str, str]],
    *,
    fallback: str,
    task: str,
    role: str,
) -> tuple[str, bool, str]:
    """Ask the model, and fall back to the deterministic text if it cannot answer.

    Returns the text, whether a model produced it, and — when it did not — why. The reason
    is carried rather than swallowed: "the box is down" and "no transcript was recorded for
    this prompt" are different problems, and a demonstration that silently degrades teaches
    nobody which one happened.
    """
    if client is None:
        return fallback, False, "no model client configured"
    try:
        completion = await client.complete(role=role, task=task, messages=messages)
    except ModelUnavailable as exc:
        return fallback, False, str(exc)
    return completion.text, True, ""
