"""Connections. The only module permitted to open one — contract 6 in `importlinter.ini`.

One consequence worth knowing: `app.api` cannot annotate a connection type directly. Re-export
what is needed from here and annotate with that. Mildly annoying, and exactly the discipline
that keeps the routers thin.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiomysql

from app.config import Settings
from app.db.plant import PlantRepository


@asynccontextmanager
async def plant_pool(settings: Settings) -> AsyncIterator[aiomysql.Pool]:
    """A pool against the plant snapshot, as the read-only user.

    `autocommit=True` on a connection that holds only `SELECT` is not a write risk; it
    avoids leaving idle transactions open against a database shared with Thermynx, which
    is what holds read locks and confuses anyone watching the process list.
    """
    pool = await aiomysql.create_pool(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_db,
        autocommit=True,
        minsize=1,
        maxsize=5,
        connect_timeout=10,
    )
    try:
        yield pool
    finally:
        pool.close()
        await pool.wait_closed()


@asynccontextmanager
async def plant_repository(settings: Settings) -> AsyncIterator[PlantRepository]:
    """The repository, with the measured-window boundary already bound to it.

    Bound at construction rather than passed per call, so a caller cannot forget it and
    silently query into the simulated span. Widening still takes an explicit
    `include_simulated=True` on the individual method.
    """
    async with plant_pool(settings) as pool:
        yield PlantRepository(pool, settings.synex_measured_window_end)
