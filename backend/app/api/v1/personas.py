"""The persona switcher. **A demonstration affordance, and it says so in the response.**

D-013 closes `Q41` for the MVP without answering it: there is no authentication library in
the backend and the snapshot's user tables hold zero rows, so a labelled switcher lets `G1`'s
scoping logic be built and tested against a known identity without committing to any of the
three identity routes.

Every response from these routes carries `is_production_identity: false` and an explicit
warning string. The danger with a stand-in is that it quietly becomes the real thing, and the
defence is that it is impossible to read this output and believe it is authentication.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import PERSONA_COOKIE, CurrentScope, current_scope
from app.config import Settings, get_settings
from app.services.control_plane import (
    PERSONA_DISPLAY,
    Capability,
    Persona,
    compute_scope,
    issue_persona_token,
)

router = APIRouter(prefix="/api/v1", tags=["personas"])

WARNING = (
    "This is a demonstration persona switcher, not authentication. Anyone who can reach "
    "this endpoint can select any persona. The signature protects the cookie in transit; it "
    "does not establish identity. Q41 is unanswered — see D-013."
)


@router.get("/personas")
async def list_personas() -> dict:
    """Every persona and what it may do, so the capability model is inspectable.

    Capabilities are listed rather than a rank, because they are not a ladder: a supervisor
    is not a more capable technician, it is a different capability — authority and records,
    not gauges.
    """
    return {
        "warning": WARNING,
        "personas": [
            {
                "key": p.value,
                "display_name": PERSONA_DISPLAY[p],
                "capabilities": sorted(c.value for c in compute_scope(p).capabilities),
            }
            for p in Persona
        ],
        "capabilities": [c.value for c in Capability],
    }


@router.post("/personas/{persona_key}")
async def switch_persona(
    persona_key: str,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Set the signed persona cookie.

    `httponly` so page scripts cannot read it, and `samesite=lax` so it is not sent from a
    third-party context. Both are transport hygiene rather than identity guarantees, and the
    warning in the body says so.
    """
    try:
        persona = Persona(persona_key)
    except ValueError as exc:
        raise HTTPException(
            404, f"unknown persona {persona_key!r}; see GET /api/v1/personas"
        ) from exc

    token = issue_persona_token(persona, settings.jwt_secret)
    response.set_cookie(
        PERSONA_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return {"warning": WARNING, "scope": compute_scope(persona).as_dict()}


@router.get("/me")
async def me(scope: CurrentScope = Depends(current_scope)) -> dict:
    """Who the back end thinks is asking, recomputed for this request alone."""
    return {"warning": WARNING, "scope": scope.as_dict()}
