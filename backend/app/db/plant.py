"""The plant repository — read-only, measured-window-clipped, and it cannot write.

`graylinx_synex` on port 3307. Synex connects as `synex_plant_ro`, which holds `SELECT` on
this one database and nothing else — verified as exactly two grants. That closes `Q42`: *"Synex
never writes to the plant"* is now a property of the database rather than a sentence in a
document, so a bad query cannot damage the reference snapshot the other databases were cloned
from.

**Every query clips to the measured window by default.** `SYNEX_MEASURED_WINDOW_END` is
2026-06-23 11:50, real readings stop there, and the simulation that continues past it
*invented* `cond_flow` — a signal this plant has never measured. Reaching past the boundary
takes an explicit `include_simulated=True` at every call site; there is no default, no
config flag and no ambient setting that turns it on. D-009.

**This module returns domain objects and plain rows, never `Figure`.** The plan asks for
repositories that return `Figure`, but the layering law puts `db` *below* `analytics`, where
`honesty.py` lives, so `db` importing it would be an upward import. Figures are assembled in
`app.services`, which sits above both. The enforced contract wins over the plan that predates
it — recorded rather than worked around.

**The schema, as it actually is.** `gla_model_residuals_wc` carries `equipment`, `slot_time`,
six residual columns and `fault_label`. `equipment` holds the *table* name
(`chiller_1_normalized`), which this module maps to the domain key (`chiller_1`) on the way
out, so database naming does not leak upward.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiomysql

from app.domain import equipment as eq
from app.domain.bands import ResidualBand

#: The six residual columns, in the order the table declares them. Five are fitted;
#: `compressor_power_residual` is 100% NULL and is listed so it can be reported as a stated
#: absence rather than quietly omitted — constraint 14.
RESIDUAL_COLUMNS: tuple[str, ...] = (
    "Dp_residual",
    "Sp_residual",
    "dt_residual",
    "chiller_current_residual",
    "compressor_power_residual",
    "cond_leaving_residual",
)

#: The one that never has a value. Named so a caller can assert its absence deliberately.
UNFITTED_RESIDUAL_COLUMN: str = "compressor_power_residual"

#: Labels that are outcomes rather than faults. Excluded from every fault count, because
#: including either would overstate the fault total by 6,252 slots.
NON_FAULT_LABELS: tuple[str, ...] = ("NO_DIAGNOSIS", "NO_EFFICIENCY_FAULT")


def _to_key(table_name: str) -> str:
    """`chiller_1_normalized` -> `chiller_1`, via the equipment registry.

    Falls back to the raw value rather than raising: an unknown equipment name is data we
    should surface, not an exception that hides the row. The caller sees a key it does not
    recognise, and `is_scoreable` returns False for it — which is the safe direction.
    """
    known = eq.by_table(table_name)
    return known.key if known else table_name


@dataclass(frozen=True)
class ResidualRow:
    """One scored slot. Residual values stay `float | None` — a NULL is not a zero."""

    equipment_key: str
    slot_time: datetime
    fault_label: str | None
    residuals: dict[str, float | None]

    @property
    def is_labelled(self) -> bool:
        return self.fault_label is not None

    @property
    def is_fault(self) -> bool:
        """`NO_DIAGNOSIS` is a label and not a fault. Constraint 7: a NULL means not
        diagnosed, never healthy — so an unlabelled slot is not a fault either."""
        return self.is_labelled and self.fault_label not in NON_FAULT_LABELS


@dataclass(frozen=True)
class LabelCount:
    label: str | None
    slots: int


class PlantRepository:
    """Read-only access to the plant snapshot.

    Holds a connection pool rather than a connection: the API is async and a shared
    connection would serialise every request behind whichever query is slowest.
    """

    def __init__(self, pool: aiomysql.Pool, measured_window_end: datetime) -> None:
        self._pool = pool
        self._measured_window_end = measured_window_end

    @property
    def pool(self) -> aiomysql.Pool:
        """The shared connection pool.

        Exposed so `ProvenanceRepository` can reuse it. Both live in `app.db` and there is
        one pool per process on purpose — opening a second to avoid sharing would cost a
        connection per request against a database Thermynx also uses.
        """
        return self._pool

    # ── the window clip, in one place ───────────────────────────────────────────

    def _window_clause(self, include_simulated: bool) -> tuple[str, list[object]]:
        """The only place the measured-window boundary is applied.

        One function, so a new query cannot quietly omit the clip — the plan's data
        discipline in executable form. A test asserts that no repository method can return a
        simulated slot without `include_simulated=True` being passed explicitly.
        """
        if include_simulated:
            return "", []
        return " AND slot_time <= %s", [self._measured_window_end]

    # ── residuals and labels ────────────────────────────────────────────────────

    async def label_counts(self, *, include_simulated: bool = False) -> tuple[LabelCount, ...]:
        """Every `fault_label` and its slot count, most common first.

        On the measured window this reproduces the documented inventory exactly, and the
        top row is the product: `NO_DIAGNOSIS` at 5,309 against 674 faulted slots.
        """
        clause, params = self._window_clause(include_simulated)
        sql = (
            "SELECT fault_label, COUNT(*) AS slots FROM gla_model_residuals_wc "
            f"WHERE 1=1{clause} GROUP BY fault_label ORDER BY slots DESC"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            return tuple(LabelCount(label=r[0], slots=r[1]) for r in await cur.fetchall())

    async def residuals_for_day(
        self,
        equipment_key: str,
        day: datetime,
        *,
        include_simulated: bool = False,
    ) -> tuple[ResidualRow, ...]:
        """Every scored slot for one asset on one calendar day."""
        table = eq.by_key(equipment_key)
        if table is None:
            return ()
        clause, params = self._window_clause(include_simulated)
        columns = ", ".join(f"`{c}`" for c in RESIDUAL_COLUMNS)
        sql = (
            f"SELECT equipment, slot_time, fault_label, {columns} "
            "FROM gla_model_residuals_wc "
            "WHERE equipment = %s AND DATE(slot_time) = DATE(%s)"
            f"{clause} ORDER BY slot_time"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, [table.table, day, *params])
            return tuple(
                ResidualRow(
                    equipment_key=_to_key(r[0]),
                    slot_time=r[1],
                    fault_label=r[2],
                    residuals=dict(zip(RESIDUAL_COLUMNS, r[3:], strict=True)),
                )
                for r in await cur.fetchall()
            )

    async def faulted_slots(
        self, *, include_simulated: bool = False
    ) -> tuple[ResidualRow, ...]:
        """Only genuinely faulted slots — both non-fault outcomes excluded.

        674 on the measured window, which is the denominator every case-inflation figure
        is computed against.
        """
        clause, params = self._window_clause(include_simulated)
        placeholders = ", ".join(["%s"] * len(NON_FAULT_LABELS))
        columns = ", ".join(f"`{c}`" for c in RESIDUAL_COLUMNS)
        sql = (
            f"SELECT equipment, slot_time, fault_label, {columns} "
            "FROM gla_model_residuals_wc "
            f"WHERE fault_label IS NOT NULL AND fault_label NOT IN ({placeholders})"
            f"{clause} ORDER BY slot_time"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, [*NON_FAULT_LABELS, *params])
            return tuple(
                ResidualRow(
                    equipment_key=_to_key(r[0]),
                    slot_time=r[1],
                    fault_label=r[2],
                    residuals=dict(zip(RESIDUAL_COLUMNS, r[3:], strict=True)),
                )
                for r in await cur.fetchall()
            )

    # ── bands ───────────────────────────────────────────────────────────────────

    async def residual_bands(self) -> tuple[ResidualBand, ...]:
        """The ten reference bands, keyed by domain equipment key.

        `robust_low`/`robust_high` are used rather than `sigma_low`/`sigma_high`. The robust
        pair is built from the median and MAD, so a handful of extreme readings cannot widen
        the band that judges them — and this plant has readings at −273.2 and +30,183. The
        sigma pair on chiller 2's current residual spans [−128.168, 34.846], which is wide
        enough to call almost anything normal.

        No band is fitted for the other ten equipment tables, and none is invented here.
        """
        sql = (
            "SELECT equipment, residual_name, med, robust_low, robust_high "
            "FROM gla_residual_stats_wc ORDER BY equipment, residual_name"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql)
            return tuple(
                ResidualBand(
                    equipment_key=_to_key(r[0]),
                    residual_name=r[1],
                    median=float(r[2]),
                    lower=float(r[3]),
                    upper=float(r[4]),
                )
                for r in await cur.fetchall()
            )

    # ── coverage ────────────────────────────────────────────────────────────────

    async def scored_equipment_keys(self) -> tuple[str, ...]:
        """Which assets have any scored residual at all. Two, and a test asserts it."""
        sql = "SELECT DISTINCT equipment FROM gla_model_residuals_wc ORDER BY equipment"
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql)
            return tuple(_to_key(r[0]) for r in await cur.fetchall())

    async def unfitted_residual_is_entirely_null(self) -> bool:
        """`compressor_power_residual` is 100% NULL **inside the measured window** — five
        models are fitted there, not six.

        Asserted as a query rather than trusted as a document, because every chapter saying
        "six models" is a claim the data contradicts.

        **Narrowed on 2026-08-17, and the narrowing matters.** The claim used to be global.
        After the re-clone from the rebuilt `graylinx_v2` the column holds 4,281 non-null
        values — every one of them after 2026-06-23 14:35, which is to say entirely in the
        derived tail beyond our clip. Inside the window the count is still exactly zero, so
        the product's behaviour is unchanged and the sixth model still renders as *"no model
        is fitted for this signal"*. What changed is the scope of the sentence, not the
        finding, and stating it globally would now be false.
        """
        sql = (
            f"SELECT COUNT(*), SUM(`{UNFITTED_RESIDUAL_COLUMN}` IS NOT NULL) "
            "FROM gla_model_residuals_wc WHERE slot_time <= %s"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, [self._measured_window_end])
            total, non_null = await cur.fetchone()
            return total > 0 and (non_null or 0) == 0

    async def unfitted_residual_outside_the_window(self) -> tuple[int, datetime | None]:
        """How many values the sixth model has beyond the clip, and where they start.

        Exists so the boundary is a reported number rather than a comment. If a future
        restore moves those values *into* the window, this is what makes it visible instead
        of letting a sixth model quietly appear in figures.
        """
        sql = (
            f"SELECT COUNT(`{UNFITTED_RESIDUAL_COLUMN}`), "
            f"       MIN(CASE WHEN `{UNFITTED_RESIDUAL_COLUMN}` IS NOT NULL THEN slot_time END) "
            "FROM gla_model_residuals_wc WHERE slot_time > %s"
        )
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, [self._measured_window_end])
            count, first = await cur.fetchone()
            return int(count or 0), first
