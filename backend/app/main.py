"""The Synex back end.

At this milestone the application answers with the GPU terminated and no model configured.
That is the demonstration of the layering law rather than a temporary state: the
deterministic half — what the data says, which gates passed, what may not be claimed —
stands on its own, and the language model is added to *explain* it, never to produce it.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import ask, episodes, personas, reports, system
from app.config import get_settings
from app.db.plant import PlantRepository
from app.db.session import plant_pool
from app.runtime import use_psycopg_compatible_event_loop

# Before uvicorn creates its loop, not inside `lifespan` — by then the loop exists and the
# policy no longer applies to it. See `app/runtime.py`; a no-op off Windows.
use_psycopg_compatible_event_loop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """One connection pool for the process, opened at startup.

    If MySQL is unreachable the application still starts. The routes that need it return
    503 naming the reason, and the ones that do not — the roster, the ceilings, the
    equipment registry — keep working. A back end that refuses to boot because a database
    is down cannot tell anybody why.
    """
    settings = get_settings()
    app.state.plant_repo = None
    app.state.plant_error = None
    try:
        async with plant_pool(settings) as pool:
            app.state.plant_repo = PlantRepository(
                pool, settings.synex_measured_window_end
            )
            yield
    except Exception as exc:  # reported on /api/v1/health, never swallowed
        app.state.plant_error = f"{type(exc).__name__}: {exc}"
        yield


app = FastAPI(
    title="Graylinx Synex",
    version="0.18.0",
    summary="The intelligent operating layer for Graylinx.",
    lifespan=lifespan,
)

# The front end runs on 3100, not the Next.js default 3000 — 3000 through 3003 are occupied
# on the development machine, checked rather than assumed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3100", "http://127.0.0.1:3100"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(personas.router)
app.include_router(episodes.router)
app.include_router(ask.router)
app.include_router(reports.router)
