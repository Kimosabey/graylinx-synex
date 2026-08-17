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

**A second marker arrived on 2026-08-17, and it is the same defect wearing different
clothes.** The re-clone from the rebuilt `graylinx_v2` replaced every simulated slot with a
**derived** one: `snapshot_derived_slots`, 12,589 rows carrying the method
`derived:tr_from_load_v1`, of which **7,670 fall inside the measured window**. Nothing in
this repository knew the word *derived*, so those rows would have been counted as real —
a computed value reading as an instrument reading.

Derived is not simulated, and the distinction is honest rather than convenient: a derivation
is calibrated against readings the plant genuinely took, so the inherited rule is *derived
may be quoted, simulated may not*. But it is still not a measurement, so it is excluded from
"has this signal ever been measured" and counted separately. Both markers are optional and
independent — a site may have either, both or neither.

**What the second marker did not change.** `cond_flow` is still `NEVER_MEASURED` — zero
non-zero in every slot of all three databases, because the plant does not meter it. And
`chiller_flow` is still `SUSPECT`; excluding derived rows moves its last credible reading
*earlier*, from 2026-04-22 17:35 to 2026-04-22 00:00, because the rest of that day was
derived. Both verdicts got more honest, neither got weaker.

The probes run **once per process** and are cached, because it is a schema question rather
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
    derived_rows: int = 0
    derived_nonzero: int = 0

    last_credible_slot: datetime | None = None
    marker_available: bool = False
    derived_marker_available: bool = False

    @property
    def is_usable(self) -> bool:
        """`DERIVED` is deliberately **not** usable.

        The inherited rule allows a derived value to be quoted *with its label*, and this
        product has no rendering path that attaches one. Widening `is_usable` to include it
        would let computed values through every gate that asks this question, silently —
        which is precisely how `cond_flow` got into figures in the first place.
        """
        return self.status is SignalStatus.MEASURED

    @property
    def filled_only_by_simulation(self) -> bool:
        """The exact shape of the `cond_flow` defect: nothing real, plenty synthetic.

        This is the case a column-value check cannot see, because the column is full.
        """
        return self.real_nonzero == 0 and self.simulated_nonzero > 0

    @property
    def filled_only_by_derivation(self) -> bool:
        """Nothing measured, but a calibrated derivation filled it.

        Weaker than `filled_only_by_simulation` and reported differently, because the value
        stands on real readings rather than on nothing.
        """
        return self.real_nonzero == 0 and self.derived_nonzero > 0

    @property
    def partly_derived(self) -> bool:
        """Real readings exist *and* some slots were computed. The common case after the
        2026-08-17 re-clone, and the one a reader must be told about."""
        return self.real_nonzero > 0 and self.derived_nonzero > 0

    def _derived_suffix(self) -> str:
        if not self.derived_nonzero:
            return ""
        return (
            f"; a further {self.derived_nonzero:,} non-zero values in this column were "
            f"derived rather than measured"
        )

    def render(self) -> str:
        if self.filled_only_by_simulation:
            return (
                f"{self.column}: never measured — 0 non-zero in {self.real_rows:,} real "
                f"slots, and the {self.simulated_nonzero:,} non-zero values in this column "
                f"are all simulated"
            )
        if self.filled_only_by_derivation:
            return (
                f"{self.column}: not measured — 0 non-zero in {self.real_rows:,} measured "
                f"slots. The {self.derived_nonzero:,} values present were derived from "
                f"signals that are measured, and may be quoted only as derived"
            )
        if self.status is SignalStatus.NEVER_MEASURED:
            return f"{self.column}: never measured — 0 non-zero in {self.real_rows:,} real slots"
        if self.status is SignalStatus.SUSPECT and self.last_credible_slot:
            return (
                f"{self.column}: the instrument stopped reading credibly after "
                f"{self.last_credible_slot:%Y-%m-%d %H:%M} — later real values are present "
                f"but collapsed against a historic maximum of {self.real_max}"
                f"{self._derived_suffix()}"
            )
        if self.status is SignalStatus.CONSTANT:
            return (
                f"{self.column}: constant across every real slot — present, carrying nothing"
                f"{self._derived_suffix()}"
            )
        return (
            f"{self.column}: measured across {self.real_nonzero:,} real slots"
            f"{self._derived_suffix()}"
        )

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
            "derived_rows": self.derived_rows,
            "derived_nonzero": self.derived_nonzero,
            "filled_only_by_simulation": self.filled_only_by_simulation,
            "filled_only_by_derivation": self.filled_only_by_derivation,
            "partly_derived": self.partly_derived,
            "derived_marker_available": self.derived_marker_available,
            "last_credible_slot": (
                self.last_credible_slot.isoformat() if self.last_credible_slot else None
            ),
            "marker_available": self.marker_available,
            "rendered": self.render(),
        }


class ProvenanceRepository:
    """Reads the two provenance markers — the only thing in this repository that does."""

    #: Cached across instances: whether the table exists is a property of the schema, and
    #: re-probing per repository would cost a round trip on every request.
    _marker_probe: bool | None = None

    #: The same, for `snapshot_derived_slots`. Kept separate rather than folded into one
    #: probe because the two markers are genuinely independent: `graylinx_v2` before the
    #: rebuild had the first and not the second, and after it has the second and not the
    #: first. A single flag would have to guess which.
    _derived_probe: bool | None = None

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

    async def derived_marker_available(self) -> bool:
        """Probe once for `snapshot_derived_slots`. Absent means nothing is derived.

        Same shape and same reasoning as `marker_available`, and the same refusal to turn a
        missing table into a blanket "cannot tell".
        """
        if ProvenanceRepository._derived_probe is None:
            async with self._pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'snapshot_derived_slots'"
                )
                row = await cur.fetchone()
                ProvenanceRepository._derived_probe = bool(row and row[0])
        return ProvenanceRepository._derived_probe

    @classmethod
    def reset_probe(cls) -> None:
        """Test-only. Never called in service — the schema does not change under us."""
        cls._marker_probe = None
        cls._derived_probe = None

    @staticmethod
    def _slot_joins(
        table: str, marker: bool, derived: bool
    ) -> tuple[str, list[object], str, str, str]:
        """The join and predicates that separate measured slots from marked ones.

        **A real slot is one that is neither simulated nor derived.** Both markers are
        optional and independent, so all four combinations are live and each is one branch
        rather than a nested condition somebody later mis-reads.
        """
        joins: list[str] = []
        params: list[object] = []
        if marker:
            joins.append(
                "LEFT JOIN snapshot_simulated_slots s "
                "ON s.equipment = %s AND s.slot_time = n.slot_time"
            )
            params.append(table)
        if derived:
            joins.append(
                "LEFT JOIN snapshot_derived_slots d "
                "ON d.equipment = %s AND d.slot_time = n.slot_time"
            )
            params.append(table)

        # No marker at all: every row is real. Pre-existing behaviour, kept deliberately —
        # a site with neither table must not have every signal downgraded to "cannot tell".
        real_parts = []
        if marker:
            real_parts.append("s.slot_time IS NULL")
        if derived:
            real_parts.append("d.slot_time IS NULL")
        real_pred = " AND ".join(real_parts) if real_parts else "1=1"

        sim_pred = "s.slot_time IS NOT NULL" if marker else "1=0"
        der_pred = "d.slot_time IS NOT NULL" if derived else "1=0"
        return " ".join(joins), params, real_pred, sim_pred, der_pred

    async def availability(
        self, equipment_key: str, table: str, column: str
    ) -> SignalAvailability:
        """Compute one signal's availability over **measured slots only**.

        Measured means neither simulated nor derived. A derived value is reported alongside
        rather than counted in, because "has an instrument ever read this" and "is there a
        number here" are different questions and only the first belongs in a status.
        """
        marker = await self.marker_available()
        derived = await self.derived_marker_available()
        join, params, real_pred, sim_pred, der_pred = self._slot_joins(table, marker, derived)

        sql = (
            f"SELECT "
            f"  SUM({real_pred}), "
            f"  SUM(CASE WHEN {real_pred} AND n.`{column}` <> 0 THEN 1 ELSE 0 END), "
            f"  MAX(CASE WHEN {real_pred} THEN ABS(n.`{column}`) END), "
            f"  MIN(CASE WHEN {real_pred} AND n.`{column}` <> 0 THEN n.`{column}` END), "
            f"  MAX(CASE WHEN {real_pred} AND n.`{column}` <> 0 THEN n.`{column}` END), "
            f"  SUM({sim_pred}), "
            f"  SUM(CASE WHEN {sim_pred} AND n.`{column}` <> 0 THEN 1 ELSE 0 END), "
            f"  SUM({der_pred}), "
            f"  SUM(CASE WHEN {der_pred} AND n.`{column}` <> 0 THEN 1 ELSE 0 END) "
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
        der_rows = int(row[7] or 0)
        der_nonzero = int(row[8] or 0)

        last_credible: datetime | None = None
        if real_nonzero == 0:
            # Nothing measured. Which of the two absences it is matters: a derivation stands
            # on real readings, an empty column stands on nothing, and a reader told
            # "never measured" about a column a derivation filled would go looking for a
            # fault in the instrument instead of in the derivation.
            status = (
                SignalStatus.DERIVED if der_nonzero > 0 else SignalStatus.NEVER_MEASURED
            )
        elif real_min is not None and real_max is not None and real_min == real_max:
            status = SignalStatus.CONSTANT
        else:
            last_credible = await self._last_credible(
                table, column, real_absmax, marker, derived
            )
            # A signal whose last credible reading is not its last reading has an instrument
            # that stopped working while the column kept filling.
            status = (
                SignalStatus.SUSPECT
                if last_credible is not None
                and await self._has_real_rows_after(table, last_credible, marker, derived)
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
            derived_rows=der_rows,
            derived_nonzero=der_nonzero,
            last_credible_slot=last_credible,
            marker_available=marker,
            derived_marker_available=derived,
        )

    async def _last_credible(
        self, table: str, column: str, absmax: float | None, marker: bool, derived: bool
    ) -> datetime | None:
        """The last measured slot at or above `COLLAPSE_FRACTION` of the historic maximum.

        Derived slots are excluded here too, and that is the point rather than a detail: a
        derivation that keeps filling a column after the instrument died would otherwise
        push this date forward and hide the death.
        """
        if not absmax:
            return None
        join, params, pred, _, _ = self._slot_joins(table, marker, derived)
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT MAX(n.slot_time) FROM `{table}` n {join} "
                f"WHERE {pred} AND ABS(n.`{column}`) >= %s",
                [*params, absmax * COLLAPSE_FRACTION],
            )
            row = await cur.fetchone()
        return row[0] if row else None

    async def _has_real_rows_after(
        self, table: str, when: datetime, marker: bool, derived: bool
    ) -> bool:
        join, params, pred, _, _ = self._slot_joins(table, marker, derived)
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT COUNT(*) FROM `{table}` n {join} "
                f"WHERE {pred} AND n.slot_time > %s",
                [*params, when],
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

    async def derived_row_count(self, table: str) -> int:
        """How many of this table's rows were computed rather than read. 0 with no marker."""
        if not await self.derived_marker_available():
            return 0
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM snapshot_derived_slots WHERE equipment = %s",
                (table,),
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def derivation_methods(self) -> tuple[str, ...]:
        """The distinct methods present, so a figure can name *how* it was derived.

        One method exists today — `derived:tr_from_load_v1` — but reading it rather than
        hardcoding it is the whole lesson of this module's first version.
        """
        if not await self.derived_marker_available():
            return ()
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT DISTINCT method FROM snapshot_derived_slots ORDER BY method")
            rows = await cur.fetchall()
        return tuple(r[0] for r in rows if r and r[0])
