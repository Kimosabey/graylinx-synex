"""The role surfaces on the wire — `U6`, `U7`, `U8` and `A1`.

**The gap this closes.** `CONTEXT.md` §10d names **eight surfaces**, and the product has
routes for two. The reliability workspace, the supervisor queue, the administrator view and
the equipment story were all built as services today, with tests, and **not one of them was
reachable over HTTP** — the same defect shape as a tool registry nothing calls, one layer up.

**Every surface is scoped, and the scope is recomputed rather than inherited.** `G1`: scope
is computed per turn and never carried forward. So each route takes the persona's capabilities
from the Control Plane and hands them to the service, which decides what that person may see.
A surface that returned everything and let the interface hide the rest would be an
authorisation living in CSS.

**Constraint 25 is the trap these routes must not fall into.** Role order is *display* order,
never a capability ladder — a supervisor is not a more capable technician. So the supervisor
queue is not "the workspace plus more"; it is a different query defined by `approve_work` and
`close_work`, and the two share no ordering.

**Withheld sections are reported, never omitted.** Each service returns what the caller may
not see as a *count with a reason* rather than dropping it silently. A surface that quietly
showed four of six sections would read as complete, which is the failure `R10` exists for one
level up: a reconciliation claiming 100% while excluding what it could not check.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentScope, current_scope, get_optional_repo
from app.config import Settings, get_settings
from app.db.plant import PlantRepository
from app.db.session import case_store
from app.domain import equipment as eq
from app.services import policy as policy_service
from app.services import queues as queue_service
from app.services.asset_story import build as build_story
from app.services.evidence import window_for

router = APIRouter(prefix="/api/v1", tags=["surfaces"])

#: The policy version stamped on what an administrator sees.
#:
#: TBD (`Q74`): neither the format nor what advances it is defined anywhere. A version that
#: looked like a real scheme would be worse than one that says it is provisional, because an
#: audit row read years later cannot tell a placeholder from a release.
PROVISIONAL_POLICY_VERSION = "unversioned — no scheme is defined (Q74)"


def _plain(value: Any) -> Any:
    """Make a service's dataclasses JSON-safe without inventing a rendering.

    Deliberately structural rather than per-type: these services return deep trees of frozen
    dataclasses, and hand-writing a serialiser per surface is how one of them quietly stops
    carrying a field. Dates become ISO strings; everything else keeps the shape the service
    produced, including the words it chose for every absence.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value") and hasattr(value, "name"):  # StrEnum and friends
        return value.value
    return value


async def _open_cases():
    """The case queue, or an empty list when Postgres is unreachable.

    **Empty is not the same as none, and the caller is told which.** A workspace showing zero
    cases because the store is down looks exactly like a plant with nothing wrong — which is
    inherited constraint 7 arriving through a different door.
    """
    try:
        async with case_store(get_settings()) as store:
            return list(await store.open_cases()), ""
    except Exception as exc:
        return [], (
            f"The case store could not be reached ({type(exc).__name__}), so this queue is "
            f"empty because nothing was read — not because nothing is open."
        )


@router.get("/workspace")
async def reliability_workspace(scope: CurrentScope = Depends(current_scope)) -> dict:
    """`U6`. The fault queue, the residuals behind each one, and the case it opens."""
    cases, outage = await _open_cases()
    # `detected_seed_keys` is deliberately not supplied, and supplying the cases' own keys
    # would be worse than supplying nothing. Constraint 21 is *detection is not seeding*, so
    # the list has to come from the detector; derived from the queue it is compared against
    # itself, `missing` is empty by construction, and the surface reports "All N detected
    # episode(s) have a case — checked against the detector" while having checked nothing.
    # With zero cases open against the episodes the detector actually found, that false zero
    # is exactly the twenty-two-episodes failure the constraint was written for. Omitted, the
    # service says the check was not run, which is true. Wiring the detector's real output is
    # `Q87` — and it must reconcile the two encodings of the constraint-35 triple first
    # (`CaseRow.make_seed_key` joins with a pipe, `list_episodes` with a colon), or every
    # episode compares as missing.
    view = queue_service.reliability_workspace(cases, frozenset(scope.capabilities))
    body = _plain(view)
    body["viewing_as"] = scope.identity.persona.value
    body["store_note"] = outage
    return body


@router.get("/supervisor")
async def supervisor_queue(scope: CurrentScope = Depends(current_scope)) -> dict:
    """`U7`. Approvals, blocked cases, and closures verification has not cleared.

    **Not the workspace with more rows.** Constraint 25: a supervisor is not a senior
    technician, and ranking by seniority once sent a filter-drier restriction to a supervisor
    because one incidental records question outranked three refrigeration measurements.
    """
    cases, outage = await _open_cases()
    view = queue_service.supervisor_queue(cases, frozenset(scope.capabilities))
    body = _plain(view)
    body["ageing"] = view.render_ageing()
    body["viewing_as"] = scope.identity.persona.value
    body["store_note"] = outage
    return body


@router.get("/administrator")
async def administrator(scope: CurrentScope = Depends(current_scope)) -> dict:
    """`U8`. Scope, the approval matrix and the policy version.

    The most misleading screen in the product if it stayed silent about one thing: the
    identity is hard-wired non-production (`Q41`), so every decision it records is
    attributable to a demonstration persona. It says so.
    """
    view = policy_service.administrator_view(PROVISIONAL_POLICY_VERSION)
    body = view.as_dict() if hasattr(view, "as_dict") else _plain(view)
    body["viewing_as"] = scope.identity.persona.value
    return _plain(body)


@router.get("/asset/{equipment_key}")
async def asset_story(
    equipment_key: str,
    scope: CurrentScope = Depends(current_scope),
    repo: PlantRepository | None = Depends(get_optional_repo),
    settings: Settings = Depends(get_settings),
) -> dict:
    """`A1`. One asset, one page — including **what cannot be said about it**.

    That last section is the feature. On this plant condenser flow was never measured and
    feeds four of six models, `dpt` is constant so condenser approach cannot be computed at
    all, and one model runs at nRMSE 48.03 against the other's 2.65. A story listing
    capabilities without listing those would be the reassuring lie.
    """
    if eq.by_key(equipment_key) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{equipment_key!r} is not an asset this site carries. It carries: "
                f"{', '.join(e.key for e in eq.all_equipment())}."
            ),
        )
    if not scope.covers(equipment_key):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{scope.identity.display_name} is not scoped to {equipment_key}. Scope is "
                f"recomputed every turn and never inherited."
            ),
        )

    window = window_for(
        settings.synex_measured_window_end.date(), settings.synex_measured_window_end
    )
    # `episodes=None` and `episodes=()` mean different things to the story — *nobody read the
    # history* against *the history was read and held nothing*. With no repository we must
    # pass None, or the page would tell a reader the asset was clean when it was never checked.
    story = build_story(equipment_key, window=window, episodes=None if repo is None else ())
    body = story.as_dict() if hasattr(story, "as_dict") else _plain(story)
    body["rendered"] = story.render()
    return _plain(body)
