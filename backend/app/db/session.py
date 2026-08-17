"""Connections. The only module permitted to open one — contract 6 in `importlinter.ini`.

One consequence worth knowing: `app.api` cannot annotate a connection type directly. Re-export
what is needed from here and annotate with that. Mildly annoying, and exactly the discipline
that keeps the routers thin.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiomysql
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.db.case_store import CaseStore
from app.db.plant import PlantRepository
from app.db.state import Base


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


# ── Synex's own state ───────────────────────────────────────────────────────────
# A second store, and the split is deliberate. `graylinx_synex` is the plant snapshot and is
# routinely dropped and re-cloned — it happened on 2026-08-17. Anything of ours living inside
# it would be destroyed by the next restore, so Synex writes here and reads there.


def state_engine(settings: Settings) -> AsyncEngine:
    """An engine against Synex's own Postgres.

    `pool_pre_ping` because this runs against a container that a developer stops and starts,
    and a stale connection surfacing as a request failure is a debugging hour nobody needs.
    """
    return create_async_engine(settings.postgres_url, pool_pre_ping=True, future=True)


@asynccontextmanager
async def state_session(settings: Settings) -> AsyncIterator[AsyncSession]:
    """One session, committed on success and rolled back on anything else.

    The commit is here rather than in the store so a caller cannot half-write a case: the
    seed, its findings and its audit row land together or not at all.
    """
    engine = state_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


@asynccontextmanager
async def case_store(settings: Settings) -> AsyncIterator[CaseStore]:
    """The case queue, ready to use."""
    async with state_session(settings) as session:
        yield CaseStore(session)


@asynccontextmanager
async def graph_checkpointer(settings: Settings) -> AsyncIterator[object]:
    """The durable checkpoint store for `RC1`'s graph. **This is what makes a pause real.**

    Two thirds of detected cases pause — 26 of 43 stop at the checks. Until this existed the
    pause was a value in a response: the case was rebuilt from scratch on every request, so
    "waiting for a technician" survived exactly as long as the process did.

    Lives here rather than in `app.agents` because contract 6 says only `app.db` opens a
    connection, and a checkpointer is a connection. `psycopg` rather than `asyncpg` — the
    LangGraph saver is built on psycopg3, so the URL's SQLAlchemy dialect suffix is stripped.
    Same database, different client, deliberately.
    """
    from langgraph.checkpoint.postgres.aio import (  # noqa: PLC0415 — see below
        AsyncPostgresSaver,
    )

    # Imported inside the function on purpose. `app.db.session` is imported by `app.main` at
    # startup and by every offline test through the plant pool; a module-level LangGraph
    # import would pull the graph runtime and psycopg into the gate that exists to prove the
    # product runs with nothing installed and nothing running.
    dsn = settings.postgres_url.replace("+asyncpg", "").replace("+psycopg", "")
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        yield saver


async def create_state_schema(settings: Settings) -> None:
    """Create Synex's tables if they are absent.

    **This is the migration path until Alembic, and saying so is the point** — a reader who
    assumes migrations exist will write one that never runs. It is safe to call repeatedly and
    it never drops or alters anything, so a column change needs a real migration rather than
    a restart.
    """
    engine = state_engine(settings)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()
