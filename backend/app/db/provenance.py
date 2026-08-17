"""Signal availability, computed from the data — with simulated rows excluded.

**The defect this fixes.** `app/domain/signals.py` holds a registry of five signals with
their availability written down by hand. It happens to be *correct* about `cond_flow`, but
correct by assertion rather than by mechanism, and that hides three problems:

1. A normalized table has **38 columns**. The registry covers five. The other 33 return
   `None` — "no claim made" — and are silently unprotected.
2. Nothing recomputes it. If a signal changed, or a new one arrived, the registry would go
   on saying whatever it said.
3. It cannot see the marker. `snapshot_simulated_slots` has **156,129 rows** identifying
   every synthetic `(equipment, slot_time)` pair, and until this module no code in the
   repository read it.

**Availability is now computed over real slots only.** A column filled entirely by the
simulation reads as never measured, because that is what it is.

**Verified on this database, 2026-08-14:**

| | real slots | non-zero | simulated slots | non-zero |
|---|--:|--:|--:|--:|
| `chiller_1.cond_flow` | 31,884 | **0** | 12,529 | 3,354 |
| `chiller_2.cond_flow` | 31,884 | **0** | 12,529 | 3,592 |

**A dead instrument does not read zero — it collapses.** The chilled-water flow transmitter
is the case that proves a non-zero count is not enough: on chiller 1 the real maximum runs
at 107.0 through 22 April and then **1.2** in May, while still producing 1,799 non-zero
values that month. Counting non-zeros would call it healthy. So the magnitude profile is
reported too, and `last_credible_slot` is the last real reading at or above a stated
fraction of the historic maximum.

**A missing marker table must not blind every signal.** Other sites will not have one. When
it is absent this module computes over all rows — the behaviour before it existed — sets
`marker_available=False`, and says so on every result. Turning "we cannot tell which rows
are synthetic" into "no signal is trustworthy" would be a different lie in the same family.

The probe runs **once per process** and is cached, because it is a schema question rather
than a data question and asking it per signal would cost a round trip each time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiomysql

from app.domain.signals import SignalStatus

#: A real reading below this fraction of the signal's own historic maximum is treated as an
#: instrument that has collapsed rather than a plant that got quieter.
#:
#: TBD (Q52). No document fixes it. Chosen at 5% because the observed failure is not
#: marginal — 107.0 to 1.2 is a factor of 89 — so any value between about 2% and 20% gives
#: the same verdict on the case we have. It only ever affects `last_credible_slot`, which is
#: evidence shown to a reader, never a gate that suppresses a fault.
COLLAPSE_FRACTION: float = 0.05

#: Columns that are identifiers or flags rather than measurements. Excluded from
#: availability entirely — "is_running has never been measured" is a category error.
NON_SIGNAL_COLUMNS: frozenset[str] = frozenset(
    {"id", "ss_id", "equipment", "slot_time", "is_running", "faulty", "manual"}
)


@dataclass(frozen=True)
class SignalAvailability:
    """What this plant can actually say about one column of one asset."""

    equipment_key: str
    column: str
    status: SignalStatus

    real_rows: int
    real_nonzero: int
    real_max: float | None
    simulated_rows: int
    simulated_nonzero: int

    last_credible_slot: datetime | None
    marker_available: bool

    @property
    def is_usable(self) -> bool:
        return self.status is SignalStatus.MEASURED

    @property
    def filled_only_by_simulation(self) -> bool:
        """The exact shape of the `cond_flow` defect: nothing real, plenty synthetic.

        This is the case a column-value check cannot see, because the column is full.
        """
        return self.real_nonzero == 0 and self.simulated_nonzero > 0

    def render(self) -> str:
        if self.filled_only_by_simulation:
            return (
                f"{self.column}: never measured — 0 non-zero in {self.real_rows:,} real "
                f"slots, and the {self.simulated_nonzero:,} non-zero values in this column "
                f"are all simulated"
            )
        if self.status is SignalStatus.NEVER_MEASURED:
            return f"{self.column}: never measured — 0 non-zero in {self.real_rows:,} real slots"
        if self.status is SignalStatus.SUSPECT and self.last_credible_slot:
            return (
                f"{self.column}: the instrument stopped reading credibly after "
                f"{self.last_credible_slot:%Y-%m-%d %H:%M} — later real values are present "
                f"but collapsed against a historic maximum of {self.real_max}"
            )
        if self.status is SignalStatus.CONSTANT:
            return f"{self.column}: constant across every real slot — present, carrying nothing"
        return f"{self.column}: measured across {self.real_nonzero:,} real slots"

    def as_dict(self) -> dict:
        return {
            "equipment_key": self.equipment_key,
            "column": self.column,
            "status": self.status.value,
            "usable": self.is_usable,
            "real_rows": self.real_rows,
            "real_nonzero": self.real_nonzero,
            "simulated_rows": self.simulated_rows,
            "simulated_nonzero": self.simulated_nonzero,
            "filled_only_by_simulation": self.filled_only_by_simulation,
            "last_credible_slot": (
                self.last_credible_slot.isoformat() if self.last_credible_slot else None
            ),
            "marker_available": self.marker_available,
            "rendered": self.render(),
        }


class ProvenanceRepository:
    """Reads `snapshot_simulated_slots` — the one thing in this repository that does."""

    #: Cached across instances: whether the table exists is a property of the schema, and
    #: re-probing per repository would cost a round trip on every request.
    _marker_probe: bool | None = None

    def __init__(self, pool: aiomysql.Pool) -> None:
        self._pool = pool

    async def marker_available(self) -> bool:
        """Probe once. A missing table is a normal condition, not an error.

        Sites without the simulation have no marker, and on those every row is real. The
        probe is cached on the class so a second repository in the same process reuses it.
        """
        if ProvenanceRepository._marker_probe is None:
            async with self._pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'snapshot_simulated_slots'"
                )
                row = await cur.fetchone()
                ProvenanceRepository._marker_probe = bool(row and row[0])
        return ProvenanceRepository._marker_probe

    @classmethod
    def reset_probe(cls) -> None:
        """Test-only. Never called in service — the schema does not change under us."""
        cls._marker_probe = None

    async def availability(
        self, equipment_key: str, table: str, column: str
    ) -> SignalAvailability:
        """Compute one signal's availability over **real slots only**."""
        marker = await self.marker_available()

        if marker:
            join = (
                "LEFT JOIN snapshot_simulated_slots s "
                "ON s.equipment = %s AND s.slot_time = n.slot_time"
            )
            params: list[object] = [table]
            real_pred, sim_pred = "s.slot_time IS NULL", "s.slot_time IS NOT NULL"
        else:
            # No marker: every row is real. This is the pre-existing behaviour, kept
            # deliberately — a site without the simulation must not have every signal
            # downgraded to "cannot tell".
            join, params = "", []
            real_pred, sim_pred = "1=1", "1=0"

        sql = (
            f"SELECT "
            f"  SUM({real_pred}), "
            f"  SUM(CASE WHEN {real_pred} AND n.`{column}` <> 0 THEN 1 ELSE 0 END), "
            f"  MAX(CASE WHEN {real_pred} THEN ABS(n.`{column}`) END), "
            f"  MIN(CASE WHEN {real_pred} AND n.`{column}` <> 0 THEN n.`{column}` END), "
            f"  MAX(CASE WHEN {real_pred} AND n.`{column}` <> 0 THEN n.`{column}` END), "
            f"  SUM({sim_pred}), "
            f"  SUM(CASE WHEN {sim_pred} AND n.`{column}` <> 0 THEN 1 ELSE 0 END) "
            f"FROM `{table}` n {join}"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()

        real_rows = int(row[0] or 0)
        real_nonzero = int(row[1] or 0)
        real_absmax = float(row[2]) if row[2] is not None else None
        real_min = float(row[3]) if row[3] is not None else None
        real_max = float(row[4]) if row[4] is not None else None
        sim_rows = int(row[5] or 0)
        sim_nonzero = int(row[6] or 0)

        last_credible: datetime | None = None
        if real_nonzero == 0:
            status = SignalStatus.NEVER_MEASURED
        elif real_min is not None and real_max is not None and real_min == real_max:
            status = SignalStatus.CONSTANT
        else:
            last_credible = await self._last_credible(
                table, column, real_absmax, marker
            )
            # A signal whose last credible reading is not its last reading has an instrument
            # that stopped working while the column kept filling.
            status = (
                SignalStatus.SUSPECT
                if last_credible is not None
                and await self._has_real_rows_after(table, last_credible, marker)
                else SignalStatus.MEASURED
            )

        return SignalAvailability(
            equipment_key=equipment_key,
            column=column,
            status=status,
            real_rows=real_rows,
            real_nonzero=real_nonzero,
            real_max=real_max,
            simulated_rows=sim_rows,
            simulated_nonzero=sim_nonzero,
            last_credible_slot=last_credible,
            marker_available=marker,
        )

    async def _last_credible(
        self, table: str, column: str, absmax: float | None, marker: bool
    ) -> datetime | None:
        """The last real slot at or above `COLLAPSE_FRACTION` of the historic maximum."""
        if not absmax:
            return None
        floor = absmax * COLLAPSE_FRACTION
        join = (
            "LEFT JOIN snapshot_simulated_slots s "
            "ON s.equipment = %s AND s.slot_time = n.slot_time"
            if marker
            else ""
        )
        pred = "s.slot_time IS NULL" if marker else "1=1"
        params: list[object] = ([table] if marker else []) + [floor]
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT MAX(n.slot_time) FROM `{table}` n {join} "
                f"WHERE {pred} AND ABS(n.`{column}`) >= %s",
                params,
            )
            row = await cur.fetchone()
        return row[0] if row else None

    async def _has_real_rows_after(
        self, table: str, when: datetime, marker: bool
    ) -> bool:
        join = (
            "LEFT JOIN snapshot_simulated_slots s "
            "ON s.equipment = %s AND s.slot_time = n.slot_time"
            if marker
            else ""
        )
        pred = "s.slot_time IS NULL" if marker else "1=1"
        params: list[object] = ([table] if marker else []) + [when]
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT COUNT(*) FROM `{table}` n {join} "
                f"WHERE {pred} AND n.slot_time > %s",
                params,
            )
            row = await cur.fetchone()
        return bool(row and row[0])

    async def simulated_row_count(self, table: str) -> int:
        """How many of this table's rows are synthetic. 0 when there is no marker."""
        if not await self.marker_available():
            return 0
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM snapshot_simulated_slots WHERE equipment = %s",
                (table,),
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0
