"""Request dependencies — the persona, the scope, and the repository.

**Scope is recomputed on every request, never carried in the session.** A scope that
outlives the request it was granted for is a scope that outlives its reason, and in a
conversation the previous turn may have been a different persona entirely.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request

from app.config import Settings, get_settings
from app.db.plant import PlantRepository
from app.services.control_plane import (
    Persona,
    PersonaTokenError,
    Scope,
    compute_scope,
    read_persona_token,
)

#: The cookie the switcher sets. Named for what it is, so nobody reads it as a session.
PERSONA_COOKIE = "synex_persona"

#: Used when no cookie is present. The Reliability Engineer is the persona whose surface the
#: demonstration opens on — they judge the fault and open the case, which is where the loop
#: starts. It is a *display* default and grants nothing: capabilities still come from the
#: table, and this persona cannot approve, close or edit policy.
DEFAULT_PERSONA = Persona.RELIABILITY_ENGINEER


async def current_scope(
    persona_token: Annotated[str | None, Cookie(alias=PERSONA_COOKIE)] = None,
    settings: Settings = Depends(get_settings),
) -> Scope:
    """Resolve the persona and compute its scope for this request alone.

    A malformed or tampered token is a 400, never a silent fall back to the default. Falling
    back would let a corrupted cookie choose an identity, which is an authorization decision
    made by accident.
    """
    if persona_token is None:
        return compute_scope(DEFAULT_PERSONA)
    try:
        return compute_scope(read_persona_token(persona_token, settings.jwt_secret))
    except PersonaTokenError as exc:
        raise HTTPException(400, f"persona token rejected: {exc}") from exc


async def get_repo(request: Request) -> PlantRepository:
    """The plant repository, built once at startup and held on the app state.

    A pool per request would open and close a connection on every read against a database
    shared with Thermynx.
    """
    repo = getattr(request.app.state, "plant_repo", None)
    if repo is None:
        raise HTTPException(503, "the plant database is not connected")
    return repo


async def get_optional_repo(request: Request) -> PlantRepository | None:
    """The repository if it is connected, and `None` if it is not — **without raising.**

    **Why this exists.** `get_repo` is a hard dependency, so a route declaring it returns 503
    before its handler runs. On `/ask` that was wrong in a way CI caught and local runs never
    could: a question needing no telemetry at all — *"what is the capital of France"*, a
    request to change a setpoint, a request for a prediction — was refused with a database
    error instead of the refusal it had earned.

    That contradicts the property this whole product is built around. **The refusal is the
    modal outcome** — 5,309 `NO_DIAGNOSIS` slots against 674 faulted — and the refusal path
    must work with MySQL stopped and the GPU terminated, exactly like every gate here.

    Routes that genuinely need telemetry keep using `get_repo` and keep returning 503. This is
    for the one route where whether the database is needed depends on the *question*.
    """
    return getattr(request.app.state, "plant_repo", None)


CurrentScope = Scope
Repo = PlantRepository
