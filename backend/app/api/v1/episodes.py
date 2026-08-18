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
from app.analytics.verification import verify
from app.api.deps import CurrentScope, Repo, current_scope, get_repo
from app.config import Settings, get_settings
from app.db.plant import RESIDUAL_COLUMNS
from app.db.provenance import ProvenanceRepository
from app.db.session import work_order_store
from app.domain import equipment as eq
from app.domain.answer import AnswerState
from app.services import audit_log, work_orders
from app.services import cases as case_svc
from app.services.control_plane import Capability, audit_row
from app.services.evidence import build_pack, window_for

router = APIRouter(prefix="/api/v1", tags=["episodes"])


#: The signals worth recomputing per request. Not all 38 columns — these are the ones an
#: answer about high head or efficiency can actually lean on, and the ones the simulation
#: filled. Recomputing every column on every turn would cost 38 round trips to say the same
#: thing about `id` and `ss_id`.
_PROVENANCE_COLUMNS: tuple[str, ...] = ("cond_flow", "chiller_flow", "dpt", "kw_per_tr")


async def _availability(repo: Repo, equipment_key: str) -> tuple:
    """Derived signal availability, or nothing if this asset has no table.

    Failures here degrade to the hand-written registry rather than to an error: an answer
    that cannot be given because a provenance probe timed out is worse than one carrying a
    registry note, and the note is still true.
    """
    known = eq.by_key(equipment_key)
    if known is None:
        return ()
    # Both repositories are owned by the db layer and share one pool by design;
    # opening a second pool per request to avoid touching the attribute would cost a
    # connection on every turn to satisfy a naming convention.
    prov = ProvenanceRepository(repo.pool)
    out = []
    for column in _PROVENANCE_COLUMNS:
        try:
            out.append(await prov.availability(equipment_key, known.table, column))
        except Exception:  # a probe failure must not lose the answer
            continue
    return tuple(out)


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
        availability=await _availability(repo, equipment_key),
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


@router.get("/episodes/{episode_id}/series")
async def episode_series(
    episode_id: str,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    residual: str = Query(
        "chiller_current_residual",
        description="Which residual column to plot. Defaults to the current residual.",
    ),
) -> dict:
    """One residual over one day, with **that asset's own band** to draw it against.

    The band is the entire point. A residual plotted against zero would show chiller 1's
    ordinary running as a large excursion — its healthy median is −25.645 and its band never
    approaches zero. Plotted against its own band, the same series reads correctly, and the
    reader can see what "high for this asset" means rather than being told.

    Nulls are returned as `null` and counted separately. A gap in a line is ambiguous —
    it reads as "no fault here" — so the caller renders the count as a stated absence.
    """
    if not scope.allows(Capability.VIEW_RESIDUALS):
        raise HTTPException(403, "this persona may not view residuals")

    equipment_key, label, day_str = _parse_episode_id(episode_id)
    day = date.fromisoformat(day_str)
    rows = await repo.residuals_for_day(
        equipment_key, datetime(day.year, day.month, day.day)
    )
    if residual not in RESIDUAL_COLUMNS:
        raise HTTPException(400, f"unknown residual {residual!r}")

    bands = await repo.residual_bands()
    band = next(
        (b for b in bands if b.equipment_key == equipment_key and b.residual_name == residual),
        None,
    )
    points = [
        {"t": r.slot_time.isoformat(), "v": r.residuals.get(residual), "label": r.fault_label}
        for r in rows
    ]
    return {
        "episode_id": episode_id,
        "equipment_key": equipment_key,
        "fault_label": label,
        "residual": residual,
        "day": day.isoformat(),
        "points": points,
        "null_count": sum(1 for p in points if p["v"] is None),
        "band": (
            {"median": band.median, "lower": band.lower, "upper": band.upper}
            if band
            else None
        ),
        "band_absent_reason": (
            None
            if band
            else "no reference band is fitted for this asset, so nothing can be judged"
        ),
    }


@router.get("/episodes/{episode_id}/work-order")
async def episode_work_order(
    episode_id: str,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
) -> dict:
    """`W2`, `W3`, `W4` — the work order this episode would raise, with its evidence.

    A draft. Nothing is persisted, because Synex's own state belongs in PostgreSQL and that
    is not wired yet — and a work order nobody can be dispatched against should not look
    like one they can. `is_draft` says so in the payload.
    """
    if not scope.allows(Capability.VIEW_FAULTS):
        raise HTTPException(403, "this persona may not view faults")

    equipment_key, label, day_str = _parse_episode_id(episode_id)
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
    others = tuple(sorted({r.fault_label for r in rows if r.is_fault and r.fault_label != label}))
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
    return work_orders.draft_from_pack(pack).as_dict()


@router.post("/episodes/{episode_id}/work-order/confirm")
async def confirm_episode_work_order(
    episode_id: str,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
) -> dict:
    """`C8`/`C9`/`G3`/`G5` — the act that turns a draft into a row, and the only one.

    **A separate route because it is a separate act.** Reading the draft computes it from the
    evidence and writes nothing; this is where somebody takes responsibility. A single endpoint
    that returned a draft *and* stored it would make every reader an author.

    **What was shown is what gets saved.** The draft is rebuilt from the same pack the GET
    returns and travels into the row verbatim under `evidence.shown_as`, so the promise that the
    stored job matches the one on screen is kept literally rather than by care.

    **Three outcomes, and only one writes.** The identity holds `approve_work`, so the row is
    stored. It does not, so an approval request comes back — unassigned and addressed to a
    *capability*, never to a person (constraint 9), which is not a refusal because somebody down
    the corridor can sign it. Or the action is refused outright, and no approval is offered at
    all, because an approval against a safety-critical action would imply a sufficiently senior
    signature exists.

    **`G5`.** A second confirm of the same episode returns the first row unmodified with a reason
    in words rather than raising a duplicate job. A duplicate dispatch is two visits for one
    problem; a row whose stored justification is not the one anybody confirmed is worse.
    """
    if not scope.allows(Capability.VIEW_FAULTS):
        raise HTTPException(403, "this persona may not view faults")

    equipment_key, label, day_str = _parse_episode_id(episode_id)
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
    others = tuple(sorted({r.fault_label for r in rows if r.is_fault and r.fault_label != label}))
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

    draft = work_orders.draft_from_pack(pack)
    outcome = work_orders.confirm(draft, scope)

    body: dict = {
        "episode_id": episode_id,
        # The whole ruling, not a label. `G3` always carries its reason in words and the
        # capability it required, and a surface that shows only "refused" cannot tell somebody
        # what would let them proceed.
        "ruling": outcome.ruling.as_dict(),
        "may_proceed": outcome.ruling.may_proceed,
        "required_capability": outcome.ruling.required_capability,
        "reason": outcome.reason,
        "will_persist": outcome.will_persist,
        "needs_approval": outcome.needs_approval,
        "stored": False,
        "viewing_as": scope.identity.persona.value,
    }

    if outcome.approval is not None:
        body["approval"] = outcome.approval.as_dict()
        return body

    if outcome.record is None:
        return body

    try:
        async with work_order_store(settings) as store:
            write = await store.confirm(outcome.record)
        body["stored"] = True
        body["work_order"] = write.as_dict() if hasattr(write, "as_dict") else str(write)
    except Exception as exc:
        # The decision stands and the write did not happen. Reporting a store outage as a
        # refusal would tell somebody they may not raise a job they are entitled to raise.
        body["stored"] = False
        body["store_note"] = (
            f"The decision was made and the row could not be written "
            f"({type(exc).__name__}). Nothing was stored; the job was not refused."
        )
    return body


@router.get("/episodes/{episode_id}/verification")
async def episode_verification(
    episode_id: str,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
    after_days: int = Query(
        7, ge=1, le=60,
        description="Days after the episode to read as the post-work window",
    ),
) -> dict:
    """`V1`-`V4` — did it work? Post-work residuals against this asset's own band.

    The post-work window is taken as the days following the episode. On this snapshot no
    repair was ever recorded, so what is being verified is a **natural clearing** — and the
    honest answer for the one this data offers is `UNKNOWN`, because the label disappears
    while the gates stop passing and the residual gets worse.
    """
    if not scope.allows(Capability.VIEW_RESIDUALS):
        raise HTTPException(403, "this persona may not view residuals")

    equipment_key, label, day_str = _parse_episode_id(episode_id)
    day = date.fromisoformat(day_str)
    residual_name = "chiller_current_residual"

    before_rows = await repo.residuals_for_day(
        equipment_key, datetime(day.year, day.month, day.day)
    )
    before = tuple(r.residuals.get(residual_name) for r in before_rows if r.fault_label == label)

    after: list[float | None] = []
    diagnosable = False
    for offset in range(1, after_days + 1):
        d = date.fromordinal(day.toordinal() + offset)
        rows = await repo.residuals_for_day(equipment_key, datetime(d.year, d.month, d.day))
        for r in rows:
            after.append(r.residuals.get(residual_name))
            # The window counts as diagnosable only where the engine actually reached a
            # judgement. NO_DIAGNOSIS and an absent label are both "not judged".
            if r.fault_label not in (None, "NO_DIAGNOSIS"):
                diagnosable = True

    bands = await repo.residual_bands()
    band = next(
        (b for b in bands if b.equipment_key == equipment_key and b.residual_name == residual_name),
        None,
    )
    result = verify(
        residual_name=residual_name,
        before=before,
        after=tuple(after),
        band=band,
        after_was_diagnosable=diagnosable,
    )
    return {
        "episode_id": episode_id,
        "post_work_window_days": after_days,
        "post_work_was_diagnosable": diagnosable,
        **result.as_dict(),
    }


@router.get("/episodes/{episode_id}/case")
async def episode_case(
    episode_id: str,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
    viewing_as: str = Query(
        "technician",
        description=(
            "Which capability's task list to render. RC3 — the list is theirs, "
            "not everyone's."
        ),
    ),
) -> dict:
    """`RC1`, `RC3`, `RC5` — the case this episode seeds, for one capability.

    The checklist content is **sample content and says so**. The curated library is 124
    items and none has been reviewed by a refrigeration engineer, so no real item is shown
    to anyone — the mechanism is real, the content is illustrative, and the response
    carries `content_is_sample` so no surface can render it as the library.
    """
    if not scope.allows(Capability.VIEW_FAULTS):
        raise HTTPException(403, "this persona may not view faults")

    try:
        capability = case_svc.Capability(viewing_as)
    except ValueError as exc:
        raise HTTPException(400, f"unknown capability {viewing_as!r}") from exc

    equipment_key, label, day_str = _parse_episode_id(episode_id)
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
        )
    )
    pack = build_pack(
        rows=matching,
        bands=bands,
        gates=gates,
        window=window_for(day, settings.synex_measured_window_end),
        equipment_key=equipment_key,
        fault_label=label,
        day=day,
    )
    return case_svc.case_from_pack(pack).as_dict(capability)


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
