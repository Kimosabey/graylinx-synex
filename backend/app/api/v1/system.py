"""Health, the model roster, and the ten ceilings.

The roster and the ceilings are exposed because they are part of what is being demonstrated.
*"Code never names a model"* and *"every bound names the failure it prevents"* are claims
about the build, and a claim you can curl is stronger than one on a slide.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request

from app.agents import degraded_mode
from app.config import Settings, get_settings
from app.db import knowledge
from app.db.session import state_reachable, state_session
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
    degradation = await _probed_degradation(request, settings)
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
        # **Configured `live` and actually reachable are two different facts.** The mode says
        # what this process was told to do; this says whether the box answered when asked. A
        # bar reporting "live" while the tunnel is down is the same shape of untruth as the
        # one that reported "stub" while nobody noticed — a claim about intent presented as a
        # claim about the world. Probed, never assumed, and `null` when the mode is `stub`
        # because there is nothing to reach.
        "box_reachable": await _box_answers(settings),
        "box_host": settings.ollama_host,
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
    # **The probes happen here, not in the report.** `degraded_mode` opens no sockets by
    # design — it is imported by code that must stay pure — so the two capabilities that can
    # only be known by asking are asked at this layer and handed in. Four of seven used to read
    # `unknown` on a platform where three of them were up; that is honest but not useful, and
    # "nobody looked" is a poor answer to give somebody deciding whether to trust the screen.
    return (await _probed_degradation(request, settings)).as_dict()


async def _probed_degradation(request: Request, settings: Settings) -> DegradationReport:
    """The assessment, with the two capabilities that can only be known by asking, asked.

    **Both endpoints go through here, and that is the whole point.** `/health` summarises what
    `/degraded` details, and a test asserts they cannot disagree — so a probe added to one and
    not the other is not a cosmetic difference, it is the aggregate reporting a different
    platform than the detail behind it.
    """
    embed_ok, embed_why = await _embedder_answers(settings)
    store_ok, store_why = await _vector_store_answers(settings)
    return _degradation(
        request,
        settings,
        case_queue_session_opened=await state_reachable(settings),
        embeddings_reached=embed_ok,
        embeddings_detail=embed_why,
        retrieval_reached=store_ok,
        retrieval_detail=store_why,
        box_reached=await _box_answers(settings),
    )


async def _embedder_answers(settings: Settings) -> tuple[bool | None, str]:
    """Does the embedding host answer, and is the embedding model actually pulled?

    Two facts, not one: a host that answers while `nomic-embed-text` is absent produces a
    retrieval path that fails at the first passage, and reporting that as *available* would
    send somebody looking in the wrong place.
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.embed_host}/api/tags")
        if response.status_code != 200:
            return False, f"{settings.embed_host} answered HTTP {response.status_code}"
        names = {m.get("name", "") for m in response.json().get("models", [])}
        wanted = role_table.model_for("embed")
        if not any(n.split(":")[0] == wanted.split(":")[0] for n in names):
            return False, (
                f"{settings.embed_host} answered, but {wanted} is not pulled on it, so the "
                f"first passage would fail"
            )
        return True, f"{wanted} answered at {settings.embed_host}"
    except Exception as cause:
        return False, f"{settings.embed_host} did not answer: {cause}"


async def _vector_store_answers(settings: Settings) -> tuple[bool | None, str]:
    """Does pgvector hold approved passages, and how many?

    A store that is reachable and **empty** is not retrieval working — it is retrieval with
    nothing to retrieve, which returns no passages and reads as a plant with no documentation.
    The count travels so the difference is visible rather than inferred.
    """
    try:
        async with state_session(settings) as session:
            count = await knowledge.count_approved(session)
        if count == 0:
            return False, (
                "pgvector answered and holds no approved passages, so retrieval would return "
                "nothing — which reads as a plant with no documentation"
            )
        return True, f"pgvector answered and holds {count} approved passage(s)"
    except Exception as cause:
        return False, f"pgvector did not answer: {type(cause).__name__}"


def _degradation(
    request: Request,
    settings: Settings,
    *,
    case_queue_session_opened: bool | None = None,
    embeddings_reached: bool | None = None,
    embeddings_detail: str = "",
    retrieval_reached: bool | None = None,
    retrieval_detail: str = "",
    box_reached: bool | None = None,
) -> DegradationReport:
    """The observations this process can make, plus any measurement handed in.

    Shared by `/health` and `/degraded` so the two can never disagree — a summary computed
    separately from the detail it summarises is the defect the aggregate exists to remove.
    """
    return degraded_mode.assess_platform(
        case_queue_session_opened=case_queue_session_opened,
        box_reached=box_reached,
        embeddings_reached=embeddings_reached,
        embeddings_detail=embeddings_detail,
        retrieval_reached=retrieval_reached,
        retrieval_detail=retrieval_detail,
        plant_repo=getattr(request.app.state, "plant_repo", None),
        plant_error=getattr(request.app.state, "plant_error", None),
        model_mode=settings.synex_model_mode,
    )


async def _box_answers(settings: Settings) -> bool | None:
    """Does the model host answer right now? `None` when nothing is meant to be reached.

    One short request with a short timeout: this runs on every health poll, and a probe that
    can hang is a health endpoint that can hang. A failure of any kind is reported as *not
    reachable* rather than raised — the question asked is whether the box answers, and an
    exception is an answer of "no".
    """
    if settings.synex_model_mode == "stub":
        return None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


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
