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

from app.agents.answer import answer_turn, build_gates
from app.agents.sse_contract import FRAMES
from app.api.deps import CurrentScope, Repo, current_scope, get_repo
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
    repo: Repo = Depends(get_repo),
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


async def _stream(
    body: AskRequest,
    request_id: str,
    repo: Repo,
    scope: CurrentScope,
    settings: Settings,
) -> AsyncIterator[str]:
    if not scope.allows(Capability.VIEW_FAULTS):
        yield _frame("state", {"state": AnswerState.BLOCKED.value})
        yield _frame("token", {"text": "This persona may not view faults."})
        yield _frame("done", {"request_id": request_id})
        return

    yield _frame("stage", {"stage": "routing", "detail": "eight layers, cheapest first"})

    pack = None
    if body.equipment_key and body.fault_label and body.day:
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
        last_equipment=body.last_equipment or body.equipment_key,
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
    """Split for streaming. Word-aware, so a token frame never splits a number in half.

    That is not cosmetic: `FigureView` is the only component allowed to render a number, and
    a figure arriving as "-25.6" then "45" would defeat both that rule and the numeric audit
    that reads the assembled text.
    """
    words, out, current = text.split(" "), [], ""
    for word in words:
        if len(current) + len(word) + 1 > size and current:
            out.append(current + " ")
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        out.append(current)
    return out
