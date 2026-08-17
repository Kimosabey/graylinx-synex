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
    """Present but **empty** since the 2026-08-17 re-clone: the rebuilt `graylinx_v2`
    carries no simulated rows at all. The table survives, the 156,129 rows do not."""
    assert await repo.marker_available() is True


async def test_the_simulation_is_gone_and_the_derivation_replaced_it(repo) -> None:
    """The whole point of the re-clone, asserted rather than assumed.

    Before: 156,129 simulated slots, 3,354 of them fabricating a `cond_flow` the plant
    cannot measure. After: zero simulated slots, and 12,589 derived ones instead.
    """
    assert await repo.derived_marker_available() is True
    assert await repo.simulated_row_count("chiller_1_normalized") == 0
    assert await repo.derived_row_count("chiller_1_normalized") > 6_000
    assert await repo.derivation_methods() == ("derived:tr_from_load_v1",)


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
    """The headline case, and **the re-clone made it simpler rather than weaker.**

    The plant does not measure condenser flow at all — the models use a constant of 100.
    Before 2026-08-17 the column was nonetheless full, because the simulation filled it, and
    the verdict had to explain that away. The rebuilt source fabricates nothing, so the
    column is now genuinely empty and the statement is unqualified.

    `cond_flow` is zero in all three databases. No restore was ever going to change that:
    it is instrumentation, not a data defect.
    """
    a = await repo.availability(equipment, table, "cond_flow")
    assert a.status is SignalStatus.NEVER_MEASURED
    assert not a.is_usable
    assert a.real_nonzero == 0
    assert a.simulated_nonzero == 0, "the simulation is gone; nothing fabricates this now"
    assert a.derived_nonzero == 0, "and the derivation does not touch it either"
    assert not a.filled_only_by_simulation


async def test_the_rendering_still_explains_an_empty_column(repo) -> None:
    """"never measured" must carry its own evidence, whichever way the column got empty."""
    a = await repo.availability("chiller_1", "chiller_1_normalized", "cond_flow")
    rendered = a.render()
    assert "never measured" in rendered
    assert "0 non-zero" in rendered
    # The real-slot count is now the whole table minus derived rows, not the old 31,884.
    assert f"{a.real_rows:,}" in rendered


async def test_a_derived_value_is_reported_as_derived_not_as_measured(repo) -> None:
    """Constraint, not preference: a computed number must never read as an instrument
    reading. `tr` is the column the derivation actually fills."""
    a = await repo.availability("chiller_1", "chiller_1_normalized", "tr")
    assert a.derived_nonzero > 0
    assert a.partly_derived, "real readings exist and some slots were computed"
    assert "derived rather than measured" in a.render()


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
    """Stated as a test because it is the reason the magnitude profile exists at all.

    The threshold dropped from 5,000 to 3,000 at the 2026-08-17 re-clone — not because
    fewer readings exist, but because 6,901 of them are now known to be derived and no
    longer count as measured. The argument is unchanged and slightly stronger: 3,868
    genuinely measured non-zero readings, and the instrument is still dead.
    """
    a = await repo.availability("chiller_1", "chiller_1_normalized", "chiller_flow")
    assert a.real_nonzero > 3_000, "plenty of non-zero readings — and the instrument is dead"
    assert a.derived_nonzero > 6_000, "and a derivation kept filling the column after it died"


# ── the fallback: a missing marker must not blind every signal ─────────────────

async def test_a_missing_marker_treats_every_row_as_real(repo) -> None:
    """Other sites will not have a simulation, and so will not have the table.

    Turning "we cannot tell which rows are synthetic" into "no signal is trustworthy" would
    be a different lie in the same family — and it would take out every site that never had
    the problem.
    """
    # Both markers absent — the state a site that never had a simulation is in. Setting
    # only the first would leave the derived join in place and prove nothing.
    ProvenanceRepository._marker_probe = False
    ProvenanceRepository._derived_probe = False
    a = await repo.availability("chiller_1", "chiller_1_normalized", "cond_flow")

    assert a.marker_available is False
    assert a.derived_marker_available is False
    assert a.simulated_rows == 0, "with no marker, nothing is known to be simulated"
    assert a.derived_rows == 0, "nor derived"
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

async def test_no_simulated_row_reaches_the_measured_window(repo) -> None:
    """Once a coincidence, now a certainty.

    Before the re-clone this test guarded an alignment: the clip ended 2026-06-23 11:50 and
    the first simulated slot began 11:55, so the two abutted by luck rather than by design.
    The rebuilt source carries **no simulated rows at all**, so the guard becomes trivially
    satisfied — and is kept, because a future restore from a simulating source must fail
    here rather than quietly put fabricated values into figures.
    """
    settings = Settings()
    async with plant_pool(settings) as pool, pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT MIN(slot_time) FROM snapshot_simulated_slots")
        first_simulated = (await cur.fetchone())[0]

    assert first_simulated is None or first_simulated > settings.synex_measured_window_end, (
        f"the marker flags {first_simulated}, which is at or before the measured-window "
        f"end {settings.synex_measured_window_end} — simulated rows are now inside the clip"
    )


async def test_derived_rows_do_reach_inside_the_clip_and_that_is_why_they_are_excluded(
    repo,
) -> None:
    """The one thing the re-clone genuinely changed, stated as a number.

    7,670 derived slots fall on or before the measured-window end — unlike the simulation,
    which the clip kept out by construction. They are *inside everything the product shows*,
    so excluding them from "measured" is load-bearing rather than tidy: without it, 7,670
    computed slots would count as instrument readings.
    """
    settings = Settings()
    async with plant_pool(settings) as pool, pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM snapshot_derived_slots WHERE slot_time <= %s",
            (settings.synex_measured_window_end,),
        )
        inside = (await cur.fetchone())[0]

    assert inside > 0, "if this ever reaches zero the exclusion below is dead code"
    assert inside == 7_670, (
        f"{inside} derived slots inside the clip, expected 7,670 — the source data moved, "
        f"and every figure computed over the measured window should be re-checked"
    )
