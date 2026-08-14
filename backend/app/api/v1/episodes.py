"""Read routes for episodes and evidence packs. **No model is called by anything here.**

That is the point of the milestone rather than an incidental property. If these routes can
answer with the GPU terminated, the layering held: the deterministic half of the product —
what the data says, which gates passed, what may not be claimed — stands on its own, and the
language model is added later to *explain* it rather than to produce it.

Every response carries its data window (`C22`), and every request writes exactly one audit
row (`G6`), including the ones that refuse.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.analytics.episodes import LabelledSlot, to_episodes
from app.analytics.gates import (
    GateOutcome,
    check_band_available,
    check_measured_window,
    check_running,
)
from app.api.deps import CurrentScope, Repo, current_scope, get_repo
from app.config import Settings, get_settings
from app.domain import equipment as eq
from app.domain.answer import AnswerState
from app.services import audit_log
from app.services.control_plane import Capability, audit_row
from app.services.evidence import build_pack, window_for

router = APIRouter(prefix="/api/v1", tags=["episodes"])


@router.get("/equipment")
async def list_equipment(scope: CurrentScope = Depends(current_scope)) -> dict:
    """The twelve assets, and which two can be scored.

    `scoreable=false` on ten of them is a first-class part of the answer, not a filter to
    apply. A list showing only the two would imply the plant has two assets.
    """
    return {
        "scope": scope.as_dict(),
        "equipment": [
            {
                "key": e.key,
                "display_name": e.display_name,
                "kind": e.kind.value,
                "scoreable": e.scoreable,
                "why_not": (
                    None
                    if e.scoreable
                    else "no fitted model, no reference band and no scored residual"
                ),
            }
            for e in eq.all_equipment()
        ],
        "scoreable_count": len(eq.scoreable_equipment()),
        "total_count": len(eq.all_equipment()),
    }


@router.get("/episodes")
async def list_episodes(
    request: Request,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
    include_simulated: bool = Query(
        False,
        description=(
            "Reach past the measured window. Never a default: the simulated span invented "
            "condenser flow, a signal this plant has never measured (D-009)."
        ),
    ),
) -> dict:
    """Every faulted episode in the measured window — one per equipment, label and day.

    39 of them, against 12 equipment-days. That 3.25x is the `RC19` problem stated as data.
    """
    if not scope.allows(Capability.VIEW_FAULTS):
        raise HTTPException(403, "this persona may not view faults")

    rows = await repo.faulted_slots(include_simulated=include_simulated)
    episodes = to_episodes(
        tuple(
            LabelledSlot(r.equipment_key, r.slot_time, r.fault_label or "")
            for r in rows
        )
    )

    audit_log.record(
        audit_row(
            request_id=_request_id(request),
            scope=scope,
            action="list_episodes",
            answer_state=AnswerState.ANSWERED.value,
            policy_version=settings.policy_version,
        )
    )

    return {
        "window": {
            "end": settings.synex_measured_window_end.isoformat(),
            "includes_simulated": include_simulated,
            "note": (
                "Simulated slots included — condenser flow in this span is fabricated"
                if include_simulated
                else "Measured readings only; the simulated span is excluded"
            ),
        },
        "episode_count": len(episodes),
        "equipment_days": len({(e.equipment_key, e.day) for e in episodes}),
        "episodes": [
            {
                "id": f"{e.equipment_key}:{e.fault_label}:{e.day.isoformat()}",
                "equipment_key": e.equipment_key,
                "fault_label": e.fault_label,
                "day": e.day.isoformat(),
                "slot_count": e.slot_count,
                "first_slot": e.first_slot.isoformat(),
                "last_slot": e.last_slot.isoformat(),
            }
            for e in episodes
        ],
    }


@router.get("/episodes/{episode_id}/pack")
async def episode_pack(
    episode_id: str,
    request: Request,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
) -> dict:
    """The evidence pack for one episode — everything the model will later be handed.

    Exposed as its own route deliberately. Being able to read the pack without an answer
    over it is what makes "the model only ever saw this" checkable by a person rather than
    only by a test.
    """
    if not scope.allows(Capability.VIEW_FAULTS):
        raise HTTPException(403, "this persona may not view faults")

    equipment_key, label, day_str = _parse_episode_id(episode_id)
    if not scope.covers(equipment_key):
        raise HTTPException(403, f"{equipment_key} is outside this persona's scope")

    day = date.fromisoformat(day_str)
    rows = await repo.residuals_for_day(equipment_key, datetime(day.year, day.month, day.day))
    matching = tuple(r for r in rows if r.fault_label == label)
    bands = await repo.residual_bands()

    band = next(
        (b for b in bands if b.equipment_key == equipment_key
         and b.residual_name == "chiller_current_residual"),
        None,
    )
    signal_values = dict(matching[-1].residuals) if matching else {}
    gates = GateOutcome(
        (
            check_running(signal_values),
            check_band_available(band, _display(equipment_key)),
            check_measured_window(
                matching[-1].slot_time if matching else datetime(day.year, day.month, day.day),
                settings.synex_measured_window_end,
            ),
        )
    )

    others = tuple(
        sorted({r.fault_label for r in rows if r.is_fault and r.fault_label != label})
    )
    pack = build_pack(
        rows=matching,
        bands=bands,
        gates=gates,
        window=window_for(day, settings.synex_measured_window_end),
        equipment_key=equipment_key,
        fault_label=label,
        day=day,
        other_labels_same_day=others,
    )

    state = AnswerState.ANSWERED if pack.may_diagnose else AnswerState.NO_DIAGNOSIS
    audit_log.record(
        audit_row(
            request_id=_request_id(request),
            scope=scope,
            action="episode_pack",
            answer_state=state.value,
            policy_version=settings.policy_version,
            equipment_key=equipment_key,
            gates_failed=tuple(g.gate.value for g in gates.failures),
        )
    )

    return {
        "episode_id": episode_id,
        "answer_state": state.value,
        "window": pack.window.as_dict(),
        "may_diagnose": pack.may_diagnose,
        "has_poor_fit": pack.has_poor_fit,
        "severity": {"value": pack.severity, "text": pack.severity_text},
        "model_declares_undecidable": pack.is_undecidable,
        "residuals": [
            {
                "name": r.residual_name,
                "figure": r.figure.as_dict(),
                "verdict": r.verdict.value,
                "model_nrmse": r.model_nrmse,
                "poor_fit": r.is_from_a_poor_fit,
                "rendered": r.render(),
                "source": r.source.render(),
            }
            for r in pack.residual_evidence
        ],
        "gates": [
            {
                "gate": g.gate.value,
                "passed": g.passed,
                "reason": g.reason,
                "remedy": g.remedy,
                "unresolved_question": g.unresolved_question,
            }
            for g in pack.gates.results
        ],
        "signal_provenance": [s.render() for s in pack.signal_notes],
        "sources": [s.render() for s in pack.sources],
        "other_labels_same_day": list(pack.other_labels_same_day),
        # Exactly what the language model will be handed in M1.4, verbatim. Returned so a
        # person can read it — the strongest form of "the model only ever saw this".
        "prompt_data": pack.to_prompt_data(),
    }


def _parse_episode_id(episode_id: str) -> tuple[str, str, str]:
    parts = episode_id.split(":")
    if len(parts) != 3:
        raise HTTPException(400, "episode id must be equipment:label:YYYY-MM-DD")
    return parts[0], parts[1], parts[2]


def _display(equipment_key: str) -> str:
    known = eq.by_key(equipment_key)
    return known.display_name if known else equipment_key


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())
