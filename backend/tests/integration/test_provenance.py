"""Signal availability derived from `snapshot_simulated_slots`.

The defect: availability was decided by arithmetic over column values, and a simulated row
carries a plausible value. A column filled entirely by the simulation read as a working
instrument.

Two failure shapes are covered, because they are different and only one is obvious:

- **`cond_flow` — full column, nothing real.** 0 non-zero in 31,884 real slots, 3,354
  non-zero in the simulated ones. A non-zero count sees a healthy signal.
- **`chiller_flow` — the instrument collapsed rather than stopped.** The real maximum runs
  at 107.0 through 22 April and then 1.2 in May, while still producing 1,799 non-zero values
  that month. A non-zero count sees a healthy signal here too.

Marked `requires_box`: these read the real database on purpose. The whole point is that the
verdict is computed from data rather than asserted, so asserting it against a fixture would
test nothing.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.db.provenance import ProvenanceRepository
from app.db.session import plant_pool
from app.domain.signals import SignalStatus

pytestmark = pytest.mark.requires_box


@pytest.fixture
async def repo():
    async with plant_pool(Settings()) as pool:
        ProvenanceRepository.reset_probe()
        yield ProvenanceRepository(pool)
        ProvenanceRepository.reset_probe()


# ── the marker itself ──────────────────────────────────────────────────────────

async def test_the_marker_table_is_present_and_readable(repo) -> None:
    """156,129 rows across 13 tables. Until this module, no code in the repo read it."""
    assert await repo.marker_available() is True


async def test_the_probe_runs_once(repo) -> None:
    """It is a schema question, not a data question. Asking per signal would cost a round
    trip each time."""
    await repo.marker_available()
    assert ProvenanceRepository._marker_probe is True
    # A second call must not re-query; the cached value is the class attribute.
    ProvenanceRepository._marker_probe = False
    assert await repo.marker_available() is False


# ── cond_flow: a full column with nothing real in it ───────────────────────────

@pytest.mark.parametrize(
    "equipment,table",
    [("chiller_1", "chiller_1_normalized"), ("chiller_2", "chiller_2_normalized")],
)
async def test_cond_flow_is_never_measured_once_simulated_rows_are_excluded(
    repo, equipment: str, table: str
) -> None:
    """The headline case. The plant does not measure condenser flow at all — the models use
    a constant of 100 — yet the column is full, because the simulation filled it."""
    a = await repo.availability(equipment, table, "cond_flow")
    assert a.status is SignalStatus.NEVER_MEASURED
    assert not a.is_usable
    assert a.real_nonzero == 0
    assert a.simulated_nonzero > 3_000
    assert a.filled_only_by_simulation


async def test_the_rendering_says_the_values_are_simulated(repo) -> None:
    """"never measured" alone invites "then why is the column full?". The answer travels
    with the verdict."""
    a = await repo.availability("chiller_1", "chiller_1_normalized", "cond_flow")
    rendered = a.render()
    assert "never measured" in rendered
    assert "all simulated" in rendered
    assert "31,884" in rendered


# ── chiller_flow: the instrument that collapsed instead of stopping ────────────

@pytest.mark.parametrize(
    "equipment,table,died",
    [
        ("chiller_1", "chiller_1_normalized", "2026-04-22"),
        ("chiller_2", "chiller_2_normalized", "2026-04-16"),
    ],
)
async def test_the_dead_flow_transmitter_becomes_visible(
    repo, equipment: str, table: str, died: str
) -> None:
    """A non-zero count would call this healthy: chiller 1 still produced 1,799 non-zero
    readings in May — every one of them at or below 1.2, against a historic 107.0."""
    a = await repo.availability(equipment, table, "chiller_flow")
    assert a.status is SignalStatus.SUSPECT
    assert not a.is_usable
    assert a.last_credible_slot is not None
    assert a.last_credible_slot.strftime("%Y-%m-%d") == died
    assert "stopped reading credibly" in a.render()


async def test_the_collapse_is_not_visible_from_non_zero_counts_alone(repo) -> None:
    """Stated as a test because it is the reason the magnitude profile exists at all."""
    a = await repo.availability("chiller_1", "chiller_1_normalized", "chiller_flow")
    assert a.real_nonzero > 5_000, "plenty of non-zero readings — and the instrument is dead"


# ── the fallback: a missing marker must not blind every signal ─────────────────

async def test_a_missing_marker_treats_every_row_as_real(repo) -> None:
    """Other sites will not have a simulation, and so will not have the table.

    Turning "we cannot tell which rows are synthetic" into "no signal is trustworthy" would
    be a different lie in the same family — and it would take out every site that never had
    the problem.
    """
    ProvenanceRepository._marker_probe = False  # pretend the table is absent
    a = await repo.availability("chiller_1", "chiller_1_normalized", "cond_flow")

    assert a.marker_available is False
    assert a.simulated_rows == 0, "with no marker, nothing is known to be simulated"
    # cond_flow is still correctly never-measured here, because it is genuinely empty in the
    # real rows — but note the count now spans the whole table rather than the real subset.
    assert a.real_rows > 40_000


async def test_a_missing_marker_does_not_make_a_working_signal_unknown(repo) -> None:
    """The regression this guards: every signal collapsing to "cannot tell"."""
    ProvenanceRepository._marker_probe = False
    a = await repo.availability("chiller_1", "chiller_1_normalized", "kw")
    assert a.status is not SignalStatus.NEVER_MEASURED
    assert a.real_nonzero > 0


# ── the boundary our repositories rely on ──────────────────────────────────────

async def test_the_measured_window_clip_and_the_marker_agree(repo) -> None:
    """`SYNEX_MEASURED_WINDOW_END` is 2026-06-23 11:50 and the first simulated slot is
    11:55. They abut exactly, which is why no simulated row reaches a figure today.

    That agreement is currently a **coincidence of two independently-set values**, so it is
    asserted here: if the marker ever starts earlier than the clip, simulated rows begin
    entering figures silently and this test is what catches it.
    """
    settings = Settings()
    async with plant_pool(settings) as pool, pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT MIN(slot_time) FROM snapshot_simulated_slots")
        first_simulated = (await cur.fetchone())[0]

    assert first_simulated > settings.synex_measured_window_end, (
        f"the marker flags {first_simulated}, which is at or before the measured-window "
        f"end {settings.synex_measured_window_end} — simulated rows are now inside the clip"
    )
