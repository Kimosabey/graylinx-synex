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

**The turn now carries a scope, and that is what makes the tool loop reachable.** `react.py`
was built, tested with 32 green tests, and consumed by nothing — the sixth module in one day
built with no caller. It could not be called from here because a tool call needs an identity:
`Gateway.invoke` asks the Control Plane whether *this caller* may have *this capability*, and
a turn with no scope has nobody to ask. So `scope` travels into the turn, `investigate`
reaches the loop, and `POST /api/v1/ask` is the request path that gets there. A turn without a
scope still answers — it says which capability it could not check rather than pretending it
did, because a quieter answer and a smaller one look the same on a screen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.agents import arbiter, conversation, postcheck, skills
from app.agents import critique as critique_mod
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
from app.domain import plain
from app.domain.answer import AnswerState
from app.llm.client import ModelClient, ModelUnavailable
from app.prompts.explain import build_messages, build_no_diagnosis_messages
from app.services.control_plane import Scope
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
    critique: critique_mod.Critique | None = None
    """The second opinion, when one was taken. `None` means it was not attempted — which a
    surface must not render as a pass; `Critique.available` carries that distinction."""

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
    # **Our own filing is stripped from what a reader sees.** `Q49`, `F16`, `C21`, `D-009` are
    # this repository's questions, features, constraints and decisions. They belong in the
    # note — that is how somebody working here finds why a signal is distrusted — and to a
    # plant engineer reading about their chiller they are ticket numbers from another system.
    # The Inspector shows the full note; the sentence does not.
    lines = [
        f"{pack.equipment_display} on {pack.day.isoformat()} "
        f"({pack.slot_count} slot(s), {pack.window.render()}).",
        f"Detected label: {pack.fault_label or 'none on this slot'}. "
        f"Severity: {plain.for_reader(pack.severity_text)}.",
    ]
    if pack.is_undecidable:
        lines.append(
            "This label declares itself undecidable: the data could not separate the "
            "candidate causes, and narrowing it further would invent a certainty nobody has."
        )
    for evidence in pack.residual_evidence:
        lines.append(f"  - {plain.for_reader(evidence.render())}")
    if pack.other_labels_same_day:
        lines.append(
            "Other labels on this machine the same day: "
            + ", ".join(pack.other_labels_same_day)
            + ". One repair may explain several of them."
        )
    # One signal per line rather than a semicolon-joined paragraph. Five provenance notes run
    # together is the densest text on the screen and the least likely to be read, and each one
    # is a separate reason a separate reading cannot be trusted.
    absent = [plain.for_reader(s.render()) for s in pack.signal_notes]
    absent = [a for a in absent if a]
    if absent:
        lines.append("Signals that cannot be read on this plant:")
        lines.extend(f"  - {a}" for a in absent)
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


async def answer_turn(  # noqa: PLR0911
    *,
    question: str,
    pack: EvidencePack | None,
    client: ModelClient | None,
    mode_override: str | None = None,
    last_equipment: str | None = None,
    scope: Scope | None = None,
    plant_repo: object | None = None,
    history: list[conversation.Exchange] | None = None,
) -> Turn:
    """Run the turn. Never raises — a failure becomes a state, because a stack trace is not
    an answer and on a demonstration it reads as a broken product.

    **Seven exits, and the `PLR0911` suppression is the same argument `ruff.toml` already
    records for `PLR0912` and `PLR0913`.** Each return is a distinct answer state — refused,
    conversational, no scored evidence, settled by a skill, gates failed, corrected by the
    honesty layer, answered. Funnelling them through one exit would mean carrying the state in
    a mutable local and deciding it twice, which is how a corrected answer starts shipping as
    an answered one. The suppression is at this site rather than in the config, so it excuses
    this function and nothing else.

    `scope` is optional and defaults to `None` on purpose. It is what `investigate` needs to
    reach the tool loop, because `Gateway.invoke` asks the Control Plane whether *this caller*
    may have *this capability* — and a default persona would be an authorization decision made
    by a keyword argument, which is exactly the failure the separation law's seventh row
    exists to prevent. Absent, the turn says so; it never assumes one.
    """
    decision = route(question, mode_override=mode_override, last_equipment=last_equipment)

    # **Layer 4 has existed since the router was written and nothing ever filled it.** The
    # `arbiter` hook took a callable, defaulted to `None`, and no caller passed one — so every
    # question the keyword layers did not recognise fell to the deterministic default, and the
    # product only really answered questions somebody had written a phrase for. That is what
    # makes a chat feel like a menu: the first question phrased a way nobody anticipated comes
    # back visibly worse, and a reader who hits two of those stops exploring.
    #
    # **It runs only when everything cheaper was inconclusive**, which is what the ladder is
    # for: a question matching a keyword still routes in under a millisecond and never pays for
    # this. Routing once and re-routing on the default costs a second pass through pure
    # functions, which is cheaper than threading an await through every layer above.
    if decision.layer == "default":
        arbitration = await arbiter.arbitrate(
            question, client=client, last_equipment=last_equipment
        )
        if arbitration.decided:
            decision = route(
                question,
                mode_override=mode_override,
                last_equipment=last_equipment,
                arbiter=lambda _message: arbitration.skill,
            )

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

    # ── the catalogue path: questions with no episode ───────────────────────────
    # Asked before the no-pack refusal below, because that refusal answered *every* packless
    # question with "there is no scored evidence" — including the ones a registered tool could
    # have answered outright. "What equipment do we have?" is not a question about evidence.
    if pack is None:
        catalogue = await skills.answer_catalogue(
            question,
            scope=scope,
            plant_repo=plant_repo,
            client=client,
            history=conversation.render(history),
        )
        if catalogue is not None:
            return Turn(
                question=question,
                state=catalogue.state,
                text=catalogue.text,
                route=decision,
                used_model=catalogue.used_model,
            )

    if pack is None:
        # **Say which episode is missing, not that evidence is missing.** Four skills are built
        # from one episode's evidence — a work order, a checklist, a verification, a residual
        # read — and asking for any of them without one is a question the product can answer
        # *given a day*, not a question it cannot answer. The generic sentence below was
        # returned for all of them, so "raise a work order" came back as "there is no scored
        # evidence", which reads as a refusal about the plant rather than a missing input.
        needs_an_episode = {
            Skill.PREPARE_WORK: (
                "A work order is raised from one episode's evidence — the residuals, the gates "
                "and the provenance travel with the job. Open a case and the draft it would "
                "raise is there, with the evidence already attached."
            ),
            Skill.VERIFY: (
                "Verification compares an episode against the days after it, so it needs one "
                "episode to compare from. Open a case to see whether what was measured has "
                "returned to band."
            ),
            Skill.RESOLVE: (
                "The checklist belongs to one detected fault on one machine on one day. Open a "
                "case and the checks for your capability are there, with the blocking ones "
                "marked."
            ),
        }
        specific = needs_an_episode.get(decision.skill)
        return Turn(
            question=question,
            state=AnswerState.NO_DIAGNOSIS,
            text=specific
            or (
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
    #
    # `dispatch_with_tools` rather than `dispatch` since 2026-08-17: `investigate` runs the
    # bounded loop over the `C20` registry, through `G4`'s four gates, and every other skill
    # takes the identical deterministic path it always did. This call is the only thing
    # standing between a request and `react.py`, which until now had no caller at all.
    outcome = await skills.dispatch_with_tools(
        decision.skill.value,
        pack,
        scope=scope,
        question=question,
        plant_repo=plant_repo,
        # **What makes `investigate` an investigation rather than a script.** With a client the
        # loop asks devstral which tool to reach for next and follows what it finds; without
        # one it walks the deterministic plan, which is the same floor it falls back to on
        # every model failure. `tool` had no consumer at all until this line.
        client=client,
    )
    if outcome is not None:
        return Turn(
            question=question,
            state=outcome.state,
            text=outcome.text,
            route=decision,
            pack=pack,
            used_model=outcome.used_model,
            degraded_reason=outcome.degraded_reason,
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

    # ── the second opinion, on an answer the first model wrote ───────────────────
    # `postcheck` compares strings and cannot see a claim the evidence contradicts while every
    # figure in it is real. The auditor is `phi4` — not the brain that wrote this — which is
    # what `CONTEXT.md` §4 requires and what nothing exercised until now. It is a **soft** gate:
    # it never mutates or hides the answer, only badges it, because a hidden answer teaches a
    # reader the system is broken while a badged one teaches them what to check.
    second = await critique_mod.critique_answer(
        answer=text,
        evidence=postcheck.evidence_text(pack),
        client=client,
        postcheck_flags=len(report.soft_failures),
    )

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
            critique=second,
        )

    return Turn(
        question=question,
        state=AnswerState.ANSWERED,
        text=text,
        route=decision,
        critique=second,
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
