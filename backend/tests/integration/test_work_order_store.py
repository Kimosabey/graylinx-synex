"""`C8` the write · `G5` idempotency — against the index, not against a fake.

Marked `requires_box` on purpose, for the same reason `test_case_store.py` is. `G5` is a
**unique index**, not a code path: the whole point is that it has no window between a read and
a write, so asserting it against an in-memory double would assert the double's `if`. What is
being tested here is that two confirms of the same draft produce one row in a real database.

    docker compose -f infra/docker-compose.yml up -d postgres redis

The decision half — who may confirm, what the key is, whether the rendering survived — is
tested offline in `tests/unit/test_work_order_confirm.py` and needs nothing running.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import delete

from app.analytics.bands import ResidualBand
from app.analytics.gates import GateOutcome, check_band_available, check_running
from app.config import Settings
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.db.session import create_state_schema, state_session
from app.db.state import WorkOrderRow
from app.db.work_order_store import ConfirmedWorkOrder, WorkOrderStore
from app.services.control_plane import Persona, compute_scope
from app.services.evidence import build_pack, window_for
from app.services.work_orders import confirm, draft_from_pack

pytestmark = pytest.mark.requires_box

MEASURED_END = datetime(2026, 6, 23, 11, 50)
DAY = date(2026, 4, 15)
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)

SUPERVISOR = compute_scope(Persona.SUPERVISOR)


def _draft(label: str = "CONDENSER_LOW_FLOW", day: date = DAY):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = tuple(
        ResidualRow("chiller_1", datetime(day.year, day.month, day.day, 9, i), label, values)
        for i in range(3)
    )
    return draft_from_pack(
        build_pack(
            rows=rows,
            bands=(BAND,),
            gates=GateOutcome(
                (check_running({"a": 141.0}), check_band_available(BAND, "Chiller 1"))
            ),
            window=window_for(day, MEASURED_END),
            equipment_key="chiller_1",
            fault_label=label,
            day=day,
        )
    )


def _record(draft) -> ConfirmedWorkOrder:
    outcome = confirm(draft, SUPERVISOR)
    assert outcome.record is not None, outcome.reason
    return outcome.record


@pytest.fixture
async def store():
    """A clean table per test. Deletes rather than drops, so the schema is created once."""
    settings = Settings()
    await create_state_schema(settings)
    async with state_session(settings) as session:
        await session.execute(delete(WorkOrderRow))
        yield WorkOrderStore(session)


# ── C8: a draft becomes a row only on the act ──────────────────────────────────

async def test_a_confirmed_draft_becomes_one_row(store: WorkOrderStore) -> None:
    outcome = await store.confirm(_record(_draft()))

    assert outcome.created is True
    assert outcome.is_replay is False
    assert await store.count() == 1
    assert "explicit confirmation of supervisor" in outcome.reason


async def test_the_stored_row_carries_the_rendering_that_was_confirmed(
    store: WorkOrderStore,
) -> None:
    """`C8`'s promise, all the way to the table: the before looks identical to what got
    saved. Asserted after a round trip through JSON, because that is where a tuple becomes a
    list and a float becomes something else."""
    draft = _draft()
    shown = draft.as_dict()
    outcome = await store.confirm(_record(draft))

    stored = await store.by_idempotency_key(outcome.row.idempotency_key)
    assert stored is not None
    assert stored.evidence["shown_as"] == shown


# ── G5: a retry can never raise a second job ───────────────────────────────────

async def test_a_retry_with_the_same_key_returns_the_first_row(store: WorkOrderStore) -> None:
    """`G5`'s headline, and the failure it prevents is two technicians arriving at one
    machine. On 2026-04-15 chiller 1 carried five labels at once and one fault spanned 412
    consecutive readings, so the same job is reachable from hundreds of places."""
    first = await store.confirm(_record(_draft()))
    second = await store.confirm(_record(_draft()))

    assert first.created is True
    assert second.created is False
    assert second.is_replay is True
    assert second.row.id == first.row.id
    assert await store.count() == 1
    assert "already exists" in second.reason
    assert "returned that row unchanged" in second.reason


async def test_the_retry_returns_the_first_row_rather_than_the_second_payload(
    store: WorkOrderStore,
) -> None:
    """The retry must not overwrite. Whoever retried sees the job that actually exists,
    including the evidence it was raised on — a row whose stored justification is not the one
    anybody confirmed is worse than a duplicate."""
    original = _record(_draft())
    await store.confirm(original)

    tampered = ConfirmedWorkOrder(
        idempotency_key=original.idempotency_key,
        equipment_key=original.equipment_key,
        confirmed_by="somebody_else",
        evidence={"shown_as": {"title": "a different job entirely"}},
        priority="P2",
    )
    replay = await store.confirm(tampered)

    assert replay.created is False
    assert replay.row.evidence == original.evidence
    assert replay.row.priority == original.priority
    assert await store.count() == 1


async def test_two_genuinely_different_jobs_are_two_rows(store: WorkOrderStore) -> None:
    """Idempotency must not become suppression. Constraint 28: a fouled condenser on a
    machine that is also low on flow is two real causes."""
    await store.confirm(_record(_draft()))
    await store.confirm(_record(_draft(label="HIGH_HEAD_AMBIGUOUS")))
    await store.confirm(_record(_draft(day=date(2026, 6, 15))))

    assert await store.count() == 3
    assert len(await store.for_equipment("chiller_1")) == 3


async def test_a_retry_does_not_poison_the_rest_of_the_batch(store: WorkOrderStore) -> None:
    """The savepoint. Without it the expected integrity error would roll back whatever else
    the caller is writing in the same session — the case transition and the audit row."""
    await store.confirm(_record(_draft()))

    replay = await store.confirm(_record(_draft()))
    fresh = await store.confirm(_record(_draft(label="HIGH_HEAD_AMBIGUOUS")))

    assert replay.is_replay
    assert fresh.created is True
    assert await store.count() == 2
