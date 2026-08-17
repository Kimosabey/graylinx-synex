"""Health, the model roster, and the ten ceilings.

The roster and the ceilings are exposed because they are part of what is being demonstrated.
*"Code never names a model"* and *"every bound names the failure it prevents"* are claims
about the build, and a claim you can curl is stronger than one on a slide.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.agents import degraded_mode
from app.config import Settings, get_settings
from app.domain import equipment as eq
from app.domain.answer import ANSWER_STATES
from app.domain.degradation import DegradationReport
from app.llm import models as role_table
from app.services import audit_log

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health")
async def health(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """What is actually up, and what is not.

    The plant connection is reported rather than assumed: the application starts without it
    so it can say *why* it is degraded, which `CONTEXT.md` §13 requires — the platform states
    when it is in degraded mode rather than silently substituting a weaker capability.

    **`status` answers one question and `degraded_mode` answers a different one.** `status` is
    about the plant connection and has always been; it stays that way because callers depend on
    it. It is not the whole answer: with MySQL up it reads `ok` while the audit trail is not
    durable and `G5`'s ledger is in memory. `degraded_mode` is the aggregate over all seven
    capabilities, with the substitutions named — `/api/v1/degraded` carries it in full.
    """
    repo = getattr(request.app.state, "plant_repo", None)
    degradation = _degradation(request, settings)
    return {
        "status": "ok" if repo is not None else "degraded",
        "degraded_mode": {
            "headline": degradation.headline(),
            "degraded": [s.capability.value for s in degradation.degraded],
            "unknown": [s.capability.value for s in degradation.unknown],
            "detail_at": "/api/v1/degraded",
        },
        "plant_database": {
            "connected": repo is not None,
            "host": f"{settings.mysql_host}:{settings.mysql_port}",
            "database": settings.mysql_db,
            "user": settings.mysql_user,
            "read_only_by_grant": settings.mysql_user != "root",
            "error": getattr(request.app.state, "plant_error", None),
        },
        "model_mode": settings.synex_model_mode,
        "gpu_required": settings.gpu_required,
        "measured_window_end": settings.synex_measured_window_end.isoformat(),
        "policy_version": settings.policy_version,
        "audit_trail": {"rows": audit_log.count(), "durable": audit_log.IS_DURABLE},
        "answer_states": list(ANSWER_STATES),
        "equipment": {
            "total": len(eq.all_equipment()),
            "scoreable": len(eq.scoreable_equipment()),
        },
    }


@router.get("/degraded")
async def degraded(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """`CONTEXT.md` §13 in full — every capability, its standing, and what is standing in.

    Seven capabilities, and the point of the endpoint is that they are *seven*: MySQL down, the
    box down, the embedder down and PostgreSQL down are four different situations, and until
    this existed a surface could only ask whether the plant was connected. Every entry carries
    its reason in words, a substituted one names the substitution, and one that nobody probed
    says so rather than being counted as working.
    """
    return _degradation(request, settings).as_dict()


def _degradation(request: Request, settings: Settings) -> DegradationReport:
    """The observations this process can make without opening a socket.

    Shared by `/health` and `/degraded` so the two can never disagree — a summary computed
    separately from the detail it summarises is the defect the aggregate exists to remove.
    """
    return degraded_mode.assess_platform(
        plant_repo=getattr(request.app.state, "plant_repo", None),
        plant_error=getattr(request.app.state, "plant_error", None),
        model_mode=settings.synex_model_mode,
    )


@router.get("/models")
async def models(settings: Settings = Depends(get_settings)) -> dict:
    """Every role and the model it resolves to.

    Nine roles, four models. Three of the roles are aliases resolved in the table rather than
    in configuration, because making them configurable would let someone point the auditor at
    the brain — and the auditor must never be the model that wrote the answer.
    """
    return {
        "roster": role_table.roster(),
        "editable_roles": sorted(role_table.EDITABLE),
        "mode": settings.synex_model_mode,
        "note": (
            "Code never names a model; every call site asks for a role. A test walks the AST "
            "of every module and fails if a model name appears outside the role table."
        ),
    }


@router.get("/ceilings")
async def ceilings(settings: Settings = Depends(get_settings)) -> dict:
    """The ten bounds, each with the failure it prevents and whether its value is sourced.

    Three are provisional against `Q48`: the architecture record gives the bound without a
    number. Showing which is which is the point — a reader can tell our numbers from our
    guesses without reading the code.
    """
    rows = settings.ceilings()
    return {
        "ceilings": rows,
        "provisional_count": sum(1 for r in rows if r["provisional"]),
        "note": (
            "Raising a bound should require reading what it protected, so the failure it "
            "prevents travels with the number."
        ),
    }


@router.get("/audit")
async def audit(limit: int = 50) -> dict:
    """The trail. Every request writes exactly one row, including refusals.

    `durable=false` is stated rather than implied: this sink does not survive a restart yet,
    and a trail that quietly forgets is worse than one that says it will.
    """
    rows = audit_log.rows()[-limit:]
    return {
        "durable": audit_log.IS_DURABLE,
        "total": audit_log.count(),
        "rows": [r.as_dict() for r in rows],
    }
