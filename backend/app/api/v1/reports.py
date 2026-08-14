"""Reports — `R5` and `R10`. The second P0 pillar.

`R10` recomputes every headline figure from source on each request and shows it beside what
the documents claim. `R5` gives each figure its source table, its row count and the plain
English basis of the count, so a number can be opened rather than taken on trust.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import CurrentScope, Repo, current_scope, get_repo
from app.config import Settings, get_settings
from app.domain.answer import AnswerState
from app.services import audit_log, reports
from app.services.control_plane import Capability, audit_row

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/reports/reconciliation")
async def reconciliation(
    request: Request,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
    settings: Settings = Depends(get_settings),
) -> dict:
    """`R10`. Every reported number, recomputed from source.

    The answer state is `PARTIAL` when anything disagrees, not `FAILED`: a document that has
    drifted from the data is a finding this report exists to surface, not a fault in the
    report. It is also `PARTIAL` rather than `ANSWERED` when some figures could not be
    recomputed — counting an unchecked figure as agreeing is precisely the reassuring lie
    the honesty layer exists to refuse.
    """
    if not scope.allows(Capability.VIEW_FAULTS):
        raise HTTPException(403, "this persona may not view reports")

    report = reports.ReconciliationReport(await reports.reconcile(repo))
    body = report.as_dict()

    state = (
        AnswerState.ANSWERED
        if body["all_agree"] and not report.not_checkable
        else AnswerState.PARTIAL
    )

    audit_log.record(
        audit_row(
            request_id=request.headers.get("x-request-id") or str(uuid.uuid4()),
            scope=scope,
            action="reports_reconciliation",
            answer_state=state.value,
            policy_version=settings.policy_version,
        )
    )

    return {
        "answer_state": state.value,
        "window": {
            "end": settings.synex_measured_window_end.isoformat(),
            "note": "Measured readings only; the simulated span is excluded",
        },
        "summary": (
            f"{report.agreeing} of {report.checked} recomputed figures agree with the "
            f"documented value"
            + (
                f"; {len(report.not_checkable)} "
                + ("figure" if len(report.not_checkable) == 1 else "figures")
                + " could not be recomputed and "
                + ("is" if len(report.not_checkable) == 1 else "are")
                + " marked as such rather than counted as agreeing"
                if report.not_checkable
                else ""
            )
            + "."
        ),
        **body,
    }


@router.get("/reports/figures/{key}/source")
async def figure_source(
    key: str,
    repo: Repo = Depends(get_repo),
    scope: CurrentScope = Depends(current_scope),
) -> dict:
    """`R5`. Open one figure onto the records that produced it.

    Returns the basis and a bounded sample of the underlying rows. Bounded deliberately: a
    drill-down that returns everything is a drill-down nobody opens twice, and the row count
    beside it says how much was not shown rather than implying the sample is the whole.
    """
    if not scope.allows(Capability.VIEW_RESIDUALS):
        raise HTTPException(403, "this persona may not view source records")

    rows = await reports.reconcile(repo)
    match = next((r for r in rows if r.key == key), None)
    if match is None:
        raise HTTPException(404, f"no reconciled figure with key {key!r}")

    sample: list[dict] = []
    if key.startswith("label."):
        label = key.split(".", 1)[1]
        faulted = await repo.faulted_slots()
        sample = [
            {
                "equipment": r.equipment_key,
                "slot_time": r.slot_time.isoformat(),
                "fault_label": r.fault_label,
            }
            for r in faulted
            if r.fault_label == label
        ][:20]

    return {
        "figure": match.as_dict(),
        "sample": sample,
        "sample_size": len(sample),
        "sample_note": (
            f"showing {len(sample)} of {match.source_rows} rows"
            if sample
            else "no per-row sample is available for this figure"
        ),
    }
