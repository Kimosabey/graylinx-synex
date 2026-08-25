"""`RC8` idempotent seeding · `RC9` case ageing · `G6` the audit trail.

**The first thing in this product that persists.** Before this, cases, work orders, findings
and audit rows were computed and discarded — which made `RC8` and `RC9` meaningless, because
neither says anything about a queue that does not survive the request.

Marked `requires_box`: these run against the real Postgres in `infra/docker-compose.yml`, on
purpose. `RC8`'s idempotency is a **unique index**, not a code path, and asserting it against
a fake would test the fake.

    docker compose -f infra/docker-compose.yml up -d postgres redis
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.config import Settings
from app.db.case_store import CaseStore, DetectedEpisode
from app.db.session import create_state_schema, state_session
from app.db.state import AuditRow, CaseRow, FindingRow
from app.domain.cases import CaseState

pytestmark = pytest.mark.requires_box

DAY = date(2026, 4, 15)

EPISODES = (
    DetectedEpisode("chiller_1", "HIGH_HEAD_AMBIGUOUS", DAY, 412),
    DetectedEpisode("chiller_1", "CONDENSER_LOW_FLOW", DAY, 3),
    DetectedEpisode("chiller_2", "COMPRESSOR_INEFFICIENCY", DAY, 58),
)


@pytest.fixture
async def store():
    """A clean queue per test. Deletes rather than drops, so the schema is created once."""
    settings = Settings()
    await create_state_schema(settings)
    async with state_session(settings) as session:
        await session.execute(delete(FindingRow))
        await session.execute(delete(CaseRow))
        await session.execute(delete(AuditRow))
        yield CaseStore(session)


# ── RC8: detection is not seeding ──────────────────────────────────────────────

async def test_seeding_opens_one_case_per_episode(store: CaseStore) -> None:
    """Inherited constraint 21. Twenty-two detected episodes once sat outside the queue
    because nothing called the seed, and an empty queue reads as a clean plant."""
    outcome = await store.seed(EPISODES)
    assert outcome.seeded == 3
    assert outcome.already_present == 0
    assert outcome.considered == 3
    assert len(await store.open_cases()) == 3


async def test_a_rescan_can_never_open_a_second_case(store: CaseStore) -> None:
    """`RC8`'s headline. `RC17` makes the seed a scheduled job, so it runs repeatedly."""
    await store.seed(EPISODES)
    replay = await store.seed(EPISODES)

    assert replay.seeded == 0
    assert replay.already_present == 3
    assert replay.is_idempotent_replay
    assert len(await store.open_cases()) == 3
    assert "A re-run opens nothing" in replay.render()


async def test_idempotency_survives_a_partially_new_batch(store: CaseStore) -> None:
    """The realistic case: yesterday's episodes plus one new one. The savepoint per row is
    why the new case lands rather than the whole batch failing on the duplicates."""
    await store.seed(EPISODES)
    extra = DetectedEpisode("chiller_2", "POWER_HIGH_UNEXPLAINED", DAY, 22)

    outcome = await store.seed((*EPISODES, extra))
    assert outcome.seeded == 1
    assert outcome.already_present == 3
    assert len(await store.open_cases()) == 4


async def test_the_seed_key_is_constraint_35(store: CaseStore) -> None:
    """One case per equipment, fault and day. A single real fault spans hundreds of
    consecutive readings — up to 412 observed — and per-slot cases would bury one afternoon
    under five hundred rows."""
    assert CaseRow.make_seed_key("chiller_1", "HIGH_HEAD_AMBIGUOUS", DAY) == (
        "chiller_1|HIGH_HEAD_AMBIGUOUS|2026-04-15"
    )
    await store.seed(EPISODES)
    found = await store.by_seed_key("chiller_1|HIGH_HEAD_AMBIGUOUS|2026-04-15")
    assert found is not None
    assert found.slot_count == 412


async def test_the_same_fault_on_a_different_day_is_a_different_case(store: CaseStore) -> None:
    await store.seed(EPISODES)
    tomorrow = DetectedEpisode("chiller_1", "HIGH_HEAD_AMBIGUOUS", DAY + timedelta(days=1), 5)
    outcome = await store.seed((tomorrow,))
    assert outcome.seeded == 1


# ── the state machine stays in the domain layer ────────────────────────────────

async def test_a_forbidden_transition_is_refused_with_its_reason(store: CaseStore) -> None:
    """A store that could write any state would make the machine advisory. The only route to
    closed runs through verification — `W9`."""
    await store.seed(EPISODES)
    case = await store.by_seed_key("chiller_1|CONDENSER_LOW_FLOW|2026-04-15")

    moved, reason = await store.transition(case, CaseState.CLOSED)
    assert moved is False
    assert "cannot go from detected to closed" in reason
    assert "through verification" in reason
    assert case.state == CaseState.DETECTED.value


async def test_a_permitted_transition_is_recorded(store: CaseStore) -> None:
    await store.seed(EPISODES)
    case = await store.by_seed_key("chiller_1|CONDENSER_LOW_FLOW|2026-04-15")

    moved, reason = await store.transition(case, CaseState.AWAITING_FINDINGS)
    assert moved is True
    assert case.state == CaseState.AWAITING_FINDINGS.value
    assert "detected to awaiting_findings" in reason


# ── RC9: two kinds of stale, kept apart ────────────────────────────────────────

async def test_a_cleared_condition_marks_a_case_stale(store: CaseStore) -> None:
    """Four open cases once described transmitters repaired weeks earlier."""
    await store.seed(EPISODES)
    outcome = await store.age(
        cleared_seed_keys=["chiller_1|CONDENSER_LOW_FLOW|2026-04-15"]
    )

    assert outcome.cleared == 1
    case = await store.by_seed_key("chiller_1|CONDENSER_LOW_FLOW|2026-04-15")
    assert case.state == CaseState.STALE.value
    assert case.condition_cleared is True
    assert "no longer detected" in case.stale_reason


async def test_a_cleared_condition_is_not_proof_the_repair_worked(store: CaseStore) -> None:
    """`V1` found exactly this in live data: a label disappearing looked like a successful
    repair while the residual got worse, because the gates had stopped passing."""
    await store.seed(EPISODES)
    await store.age(cleared_seed_keys=["chiller_1|CONDENSER_LOW_FLOW|2026-04-15"])
    case = await store.by_seed_key("chiller_1|CONDENSER_LOW_FLOW|2026-04-15")
    assert "not proof the repair worked" in case.stale_reason
    assert case.state != CaseState.CLOSED.value


async def test_an_untouched_case_ages_visibly_without_closing(store: CaseStore) -> None:
    """Twenty cases had been waiting since April. Ageing shows a case; it never closes one —
    that needed a person, not a status."""
    await store.seed(EPISODES)
    later = datetime.now(UTC) + timedelta(days=30)

    outcome = await store.age(now=later)
    assert outcome.untouched == 3
    assert outcome.cleared == 0

    case = await store.by_seed_key("chiller_1|CONDENSER_LOW_FLOW|2026-04-15")
    assert case.stale_at is not None
    assert case.state != CaseState.STALE.value, "ageing surfaces a case, it does not close it"
    assert "It is still open." in case.stale_reason


async def test_the_two_kinds_of_stale_are_counted_separately(store: CaseStore) -> None:
    """One is evidence about the plant, the other about the queue. A single flag would let a
    fixed machine and a forgotten one look identical."""
    await store.seed(EPISODES)
    later = datetime.now(UTC) + timedelta(days=30)

    outcome = await store.age(
        cleared_seed_keys=["chiller_1|CONDENSER_LOW_FLOW|2026-04-15"], now=later
    )
    assert outcome.cleared == 1
    assert outcome.untouched == 2
    assert "condition cleared" in outcome.render()
    assert "nobody has touched" in outcome.render()


async def test_a_fresh_case_does_not_age(store: CaseStore) -> None:
    await store.seed(EPISODES)
    assert (await store.age()).untouched == 0


# ── RC4 / RC10: one answer per item ────────────────────────────────────────────

async def test_a_second_answer_updates_rather_than_appends(store: CaseStore) -> None:
    """Otherwise a `cannot_check` and a later `measured` both exist and the gate has to guess
    which is current — which is how a blocking gate gets walked past."""
    await store.seed(EPISODES)
    case = await store.by_seed_key("chiller_1|CONDENSER_LOW_FLOW|2026-04-15")

    await store.record_finding(case, "item-1", "cannot_check", note="no gauge")
    await store.record_finding(case, "item-1", "measured", value="4.2 bar")

    findings = await store.findings_for(case)
    assert len(findings) == 1
    assert findings[0].kind == "measured"
    assert findings[0].value == "4.2 bar"


# ── G6: the audit trail ────────────────────────────────────────────────────────

async def test_every_audit_row_records_that_the_identity_is_not_production(
    store: CaseStore,
) -> None:
    """Recorded per row rather than assumed, so a future reader cannot mistake a
    demonstration trail for a production one — the exact mistake an audit trail exists to
    make impossible."""
    row = await store.record_audit(
        action="seed_cases", persona="reliability_engineer", decision="allowed"
    )
    assert row.is_production_identity is False
    assert row.at is not None


async def test_the_audit_row_carries_its_reason_in_words(store: CaseStore) -> None:
    row = await store.record_audit(
        action="refuse_tool",
        decision="refused",
        reason="set_chiller_setpoint controls equipment and is refused in every phase",
    )
    assert "refused in every phase" in row.reason
