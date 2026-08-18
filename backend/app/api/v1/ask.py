"""The Copilot turn, streamed. Ten frames, exactly one `state`, `done` always last.

`app/agents/sse_contract.py` owns the frame names and `scripts/verify_sse_contract.py` fails
the build if this file emits one that is not in it — the check that kills "the web renders a
frame the API stopped sending".

**`no_diagnosis` is its own frame.** D-015. The inherited implementation emitted a refusal as
a `token` frame, which leaves the interface unable to style a refusal differently from an
answer — and `CLAUDE.md` §2.6 says `NO_DIAGNOSIS` must never be softened. Rendering a
refusal in the same typeface as a confident answer softens it by presentation. On this data
the refusal is also the modal outcome, so a state that common needs to look deliberate.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents import episode_ref
from app.agents.answer import answer_turn, build_gates
from app.agents.router import names_equipment as router_names_equipment
from app.agents.sse_contract import FRAMES
from app.analytics.episodes import LabelledSlot, to_episodes
from app.api.deps import CurrentScope, Repo, current_scope, get_optional_repo
from app.config import Settings, get_settings
from app.domain.answer import AnswerState
from app.llm.client import ModelClient
from app.services import audit_log
from app.services.control_plane import Capability, audit_row
from app.services.evidence import build_pack, window_for

router = APIRouter(prefix="/api/v1", tags=["copilot"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8_000)
    equipment_key: str | None = None
    fault_label: str | None = None
    day: date | None = None
    mode: str | None = None
    last_equipment: str | None = None


def _frame(name: str, payload: dict) -> str:
    """One SSE frame. The name is asserted against the contract at emit time.

    A typo'd frame name would otherwise reach the client as an event it silently ignores,
    which renders as a turn that is simply missing its evidence — the failure mode the
    contract gate exists for, caught here as well because a stream is not typed.
    """
    if name not in FRAMES:
        raise ValueError(f"{name!r} is not in the streaming contract")
    return f"event: {name}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.post("/ask")
async def ask(
    body: AskRequest,
    request: Request,
    repo: Repo | None = Depends(get_optional_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Ask a question about a fault. Streams the turn.

    `text/event-stream` with buffering disabled — `X-Accel-Buffering: no` because a proxy
    that buffers turns a streamed answer into a long pause followed by a wall of text, which
    is worse than not streaming at all.
    """
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    return StreamingResponse(
        _stream(body, request_id, repo, scope, settings),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream(  # noqa: PLR0915
    body: AskRequest,
    request_id: str,
    repo: Repo | None,
    scope: CurrentScope,
    settings: Settings,
) -> AsyncIterator[str]:
    if not scope.allows(Capability.VIEW_FAULTS):
        yield _frame("state", {"state": AnswerState.BLOCKED.value})
        yield _frame("token", {"text": "This persona may not view faults."})
        yield _frame("done", {"request_id": request_id})
        return

    yield _frame("stage", {"stage": "routing", "detail": "eight layers, cheapest first"})

    # **A machine named in the question outranks the one on screen.** The selection used to
    # decide the pack outright, so with chiller 1 loaded, *"how is chiller 2 doing?"* assembled
    # chiller 1's evidence and answered about chiller 1 — confidently, with every figure
    # correct, about a machine nobody asked about. The same shape as the scope leak: context
    # overriding intent. When the question names a different machine the selection is dropped
    # and the plant-level paths answer, which is what the question actually asked for.
    named_in_question = router_names_equipment(body.question)

    # **An episode named in the question beats anything on screen.** Until now the only way to
    # reach one episode's evidence was to have it selected, so the interface carried a picker
    # and the starter chips carried a fixed episode — both the same workaround for the same
    # gap: the product could not understand "raise a work order for chiller 1 on 9 April".
    # Resolution is against episodes that exist, so an unmatched day is reported as a day with
    # no detected fault rather than becoming an empty pack that reads as a clean machine.
    spoken = None
    said_day, said_relative = episode_ref.day_in(body.question)
    if repo is not None and (said_day is not None or said_relative):
        # Read the episodes through the repository rather than the HTTP handler: the handler
        # takes a Request it would only use to write an audit row, and calling it from here
        # audits a listing nobody asked for.
        rows = await repo.faulted_slots(include_simulated=False)
        detected = to_episodes(
            tuple(
                LabelledSlot(r.equipment_key, r.slot_time, r.fault_label or "")
                for r in rows
            )
        )
        spoken = episode_ref.resolve(
            body.question,
            equipment_key=named_in_question,
            episodes=[
                {
                    "equipment_key": e.equipment_key,
                    "fault_label": e.fault_label,
                    "day": e.day.isoformat(),
                }
                for e in detected
            ],
        )
    selection_contradicted = bool(
        named_in_question and body.equipment_key and named_in_question != body.equipment_key
    )

    # A resolved episode replaces the selection outright; an ambiguous one is reported rather
    # than guessed, because a confident answer about the wrong one of four is worse than a
    # question; and a relative date is refused, because on a snapshot it matches nothing while
    # looking like it worked.
    if spoken is not None and spoken.relative_term:
        yield _frame("state", {"state": AnswerState.BLOCKED.value})
        yield _frame("token", {"text": (
            f"This is a snapshot, not a live feed — it ends on a fixed date, so "
            f"{spoken.relative_term!r} has nothing to point at. Name a day, or ask about the "
            f"plant, a machine or a fault class and no day is needed."
        )})
        yield _frame("done", {"request_id": request_id})
        return

    if (
        spoken is not None
        and spoken.is_ambiguous
        and episode_ref.needs_one_episode(body.question)
    ):
        yield _frame("state", {"state": AnswerState.PARTIAL.value})
        yield _frame("token", {"text": spoken.render_ambiguity()})
        yield _frame("done", {"request_id": request_id})
        return

    # A single match is adopted whatever the question was — it is the episode the words name,
    # and there is nothing to be ambiguous about.
    if spoken is not None and spoken.is_resolved:
        found = spoken.matches[0]
        body = body.model_copy(update={
            "equipment_key": found["equipment_key"],
            "fault_label": found["fault_label"],
            "day": date.fromisoformat(str(found["day"])),
        })
        selection_contradicted = False

    pack = None
    if body.equipment_key and body.fault_label and body.day and not selection_contradicted:
        # Only *this* branch needs telemetry. A question that names no episode never touches
        # the plant, and refusing it with a database error was the defect CI caught — the
        # refusal is the modal outcome and must survive MySQL being stopped.
        if repo is None:
            yield _frame("state", {"state": AnswerState.BLOCKED.value})
            yield _frame(
                "token",
                {
                    "text": (
                        "The plant database is not connected, so the evidence behind this "
                        "episode cannot be read. This is a stated absence rather than a "
                        "finding about the equipment — nothing was examined."
                    )
                },
            )
            yield _frame("done", {"request_id": request_id})
            return
        yield _frame("stage", {"stage": "assembling evidence", "detail": "no model involved"})
        pack = await _pack_for(body, repo, settings)

    client = ModelClient(
        mode=settings.synex_model_mode,
        host=settings.ollama_host,
        timeout_s=settings.graph_timeout_s,
    )

    turn = await answer_turn(
        question=body.question,
        pack=pack,
        client=client,
        mode_override=body.mode,
        # Selecting an episode **is** naming the equipment. Without this the scope gate
        # refuses the most natural question in the product — "why was this flagged?" — which
        # contains no machine name and no domain word, because the machine is on screen and
        # already selected. The router reads text only, so the selection has to reach it.
        last_equipment=(
            None if selection_contradicted else (body.last_equipment or body.equipment_key)
        ),
        # The plant repository this request already holds, carried down so a tool can be handed
        # one rather than building it. Tools are forbidden from importing a driver at all, so
        # injection is the only route by which a capability may read the plant.
        plant_repo=repo,
        # The scope this request already computed, carried into the turn rather than
        # recomputed inside it. `investigate` runs the bounded tool loop, and every call it
        # makes goes through `G4`, which asks the Control Plane whether *this caller* may
        # have *this capability*. Without this line the loop has nobody to ask and the turn
        # says so — which is honest, and is not the product.
        scope=scope,
    )

    # ── route ───────────────────────────────────────────────────────────────────
    yield _frame(
        "route",
        {
            "skill": turn.route.skill.value,
            "layer": turn.route.layer,
            "reason": turn.route.reason,
            "equipment_key": turn.route.equipment_key,
            "used_model": turn.route.used_model,
        },
    )

    # ── the evidence, before the prose ──────────────────────────────────────────
    if turn.pack is not None:
        for evidence in turn.pack.residual_evidence:
            yield _frame(
                "figure",
                {
                    "name": evidence.residual_name,
                    **evidence.figure.as_dict(),
                    "verdict": evidence.verdict.value,
                    "model_nrmse": evidence.model_nrmse,
                    "poor_fit": evidence.is_from_a_poor_fit,
                },
            )
        yield _frame(
            "evidence",
            {
                "window": turn.pack.window.as_dict(),
                "sources": [s.render() for s in turn.pack.sources],
                "signal_provenance": [s.render() for s in turn.pack.signal_notes],
                "other_labels_same_day": list(turn.pack.other_labels_same_day),
                "severity": turn.pack.severity_text,
            },
        )

    # ── the answer, or the refusal in its own frame ─────────────────────────────
    if turn.is_refusal and turn.pack is not None:
        failed = [g for g in turn.pack.gates.results if not g.passed]
        yield _frame(
            "no_diagnosis",
            {
                "text": turn.text,
                "failed_gates": [
                    {
                        "gate": g.gate.value,
                        "why": g.reason,
                        "what_would_change_it": g.remedy,
                        "unresolved_question": g.unresolved_question,
                    }
                    for g in failed
                ],
            },
        )
    else:
        for chunk in _chunks(turn.text):
            yield _frame("token", {"text": chunk})

    # ── the audits ──────────────────────────────────────────────────────────────
    if turn.audit is not None:
        yield _frame(
            "audit",
            {
                "passed": turn.audit.passed,
                "replaced": turn.audit.must_replace_answer,
                "badges": list(turn.badges),
                "findings": [
                    {
                        "audit": f.audit,
                        "passed": f.passed,
                        "severity": f.severity.value,
                        "detail": f.detail,
                    }
                    for f in turn.audit.findings
                ],
            },
        )

    if turn.degraded_reason:
        # Degraded mode is stated, never silent. CONTEXT.md §13.
        yield _frame(
            "audit",
            {
                "passed": True,
                "degraded": True,
                "detail": (
                    "The prose layer was unavailable, so this answer was assembled "
                    f"deterministically from the evidence: {turn.degraded_reason}"
                ),
            },
        )

    # ── exactly one state, then done ────────────────────────────────────────────
    yield _frame("state", {"state": turn.state.value, "used_model": turn.used_model})

    audit_log.record(
        audit_row(
            request_id=request_id,
            scope=scope,
            action="ask",
            answer_state=turn.state.value,
            policy_version=settings.policy_version,
            equipment_key=turn.route.equipment_key,
            gates_failed=(
                tuple(g.gate.value for g in turn.pack.gates.failures) if turn.pack else ()
            ),
        )
    )
    yield _frame("done", {"request_id": request_id})


async def _pack_for(body: AskRequest, repo: Repo, settings: Settings):
    day = body.day
    rows = await repo.residuals_for_day(
        body.equipment_key, datetime(day.year, day.month, day.day)
    )
    matching = tuple(r for r in rows if r.fault_label == body.fault_label)
    bands = await repo.residual_bands()
    band = next(
        (
            b
            for b in bands
            if b.equipment_key == body.equipment_key
            and b.residual_name == "chiller_current_residual"
        ),
        None,
    )
    others = tuple(
        sorted(
            {r.fault_label for r in rows if r.is_fault and r.fault_label != body.fault_label}
        )
    )
    return build_pack(
        rows=matching,
        bands=bands,
        gates=build_gates(
            matching, band, body.equipment_key, day, settings.synex_measured_window_end
        ),
        window=window_for(day, settings.synex_measured_window_end),
        equipment_key=body.equipment_key,
        fault_label=body.fault_label,
        day=day,
        other_labels_same_day=others,
    )


def _chunks(text: str, size: int = 48) -> list[str]:
    """Split for streaming, **without touching a single character of the text**.

    Word-aware, because `FigureView` is the only component allowed to render a number and a
    figure arriving as "-25.6" then "45" would defeat both that rule and the numeric audit that
    reads the assembled text.

    **Whitespace-preserving, and that is the fix.** The previous version did
    `text.split(" ")` and rebuilt each chunk with `f"{current} {word}".strip()`. Every residual
    line begins `"
  - "` — two spaces — which `split(" ")` turns into an *empty* token, and
    the `strip()` that followed then ate the newline in front of it. Six residual lines
    collapsed onto the end of the preceding sentence, and the answer arrived as a paragraph
    with `- Dp_residual: 80.7 - Sp_residual: 78.5` run together inside it.

    That was invisible to every test: the assembled text still contained every number, so the
    numeric audit passed, the golden set passed, and only a reader could see it. The
    concatenation of these chunks is now `text` exactly, asserted by a test.
    """
    if not text:
        return []

    out: list[str] = []
    start = 0
    cut = 0  # the last index at which a break would fall on whitespace

    for i, ch in enumerate(text):
        if ch.isspace():
            cut = i
        if i - start >= size and cut > start:
            out.append(text[start : cut + 1])
            start = cut + 1

    if start < len(text):
        out.append(text[start:])
    return out
