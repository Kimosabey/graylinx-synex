"""The equipment registry — twelve tables carry telemetry, two can be scored.

Measured on `graylinx_synex`, 2026-08-11, and recorded in
`docs/20-architecture/00-data-model.md` §4b. The numbers are here as data rather than as
prose because the scope argument rests on them: *"one asset class, done completely"* is
measurable, not rhetorical.

**Why refusing to score ten of twelve is the feature, not a limitation.**
`gla_residual_stats_wc` holds ten rows — five residuals for each of the two chillers — and
nothing for the three condenser pumps, three cooling towers, three primary pumps or
`plant_normalized`. A residual without a reference band cannot be judged high or normal for
*that asset*, and judging it against zero or against a shared threshold is the failure
`CONTEXT.md` §6 spends its longest paragraph on. So a missing band produces `NO_DIAGNOSIS`,
and that is the difference between two machines and twelve.

`domain` imports nothing. This module is plant fact, usable with everything switched off.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EquipmentKind(StrEnum):
    CHILLER = "chiller"
    CONDENSER_PUMP = "condenser_pump"
    COOLING_TOWER = "cooling_tower"
    PRIMARY_PUMP = "primary_pump"
    PLANT = "plant"


@dataclass(frozen=True)
class Equipment:
    """One normalized telemetry table, and whether anything can be judged about it."""

    key: str
    """Our stable identifier, e.g. `chiller_1`."""

    table: str
    """The normalized table in `graylinx_synex`, e.g. `chiller_1_normalized`."""

    kind: EquipmentKind

    display_name: str

    scoreable: bool
    """Does this asset have fitted model parameters, a reference band **and** scored
    residuals? All three, or it cannot be judged. Two of twelve qualify."""


CHILLER_1 = Equipment(
    key="chiller_1",
    table="chiller_1_normalized",
    kind=EquipmentKind.CHILLER,
    display_name="Chiller 1",
    scoreable=True,
)

CHILLER_2 = Equipment(
    key="chiller_2",
    table="chiller_2_normalized",
    kind=EquipmentKind.CHILLER,
    display_name="Chiller 2",
    scoreable=True,
)

_UNSCOREABLE: tuple[Equipment, ...] = (
    *(
        Equipment(
            key=f"condenser_pump_{i}",
            table=f"condenser_pump_{i}_normalized",
            kind=EquipmentKind.CONDENSER_PUMP,
            display_name=f"Condenser pump {i}",
            scoreable=False,
        )
        for i in (1, 2, 3)
    ),
    *(
        Equipment(
            key=f"cooling_tower_{i}",
            table=f"cooling_tower_{i}_normalized",
            kind=EquipmentKind.COOLING_TOWER,
            display_name=f"Cooling tower {i}",
            scoreable=False,
        )
        for i in (1, 2, 3)
    ),
    *(
        Equipment(
            key=f"primary_pump_{i}",
            table=f"primary_pump_{i}_normalized",
            kind=EquipmentKind.PRIMARY_PUMP,
            display_name=f"Primary pump {i}",
            scoreable=False,
        )
        for i in (1, 2, 3)
    ),
    Equipment(
        key="plant",
        table="plant_normalized",
        kind=EquipmentKind.PLANT,
        display_name="Plant",
        scoreable=False,
    ),
)

#: Every equipment table carrying telemetry. Twelve.
EQUIPMENT: tuple[Equipment, ...] = (CHILLER_1, CHILLER_2, *_UNSCOREABLE)

_BY_KEY: dict[str, Equipment] = {e.key: e for e in EQUIPMENT}
_BY_TABLE: dict[str, Equipment] = {e.table: e for e in EQUIPMENT}


def all_equipment() -> tuple[Equipment, ...]:
    return EQUIPMENT


def scoreable_equipment() -> tuple[Equipment, ...]:
    """The assets a residual can be judged against. Exactly two, and a test says so."""
    return tuple(e for e in EQUIPMENT if e.scoreable)


def by_key(key: str) -> Equipment | None:
    return _BY_KEY.get(key)


def by_table(table: str) -> Equipment | None:
    return _BY_TABLE.get(table)


def is_scoreable(key: str) -> bool:
    """False for ten of twelve, and that is the correct answer rather than a gap.

    Unknown equipment is also False: a key we do not recognise certainly has no fitted
    band, and defaulting the other way would score an asset we know nothing about.
    """
    equipment = _BY_KEY.get(key)
    return bool(equipment and equipment.scoreable)

#: Every column the normalized tables carry, read from the live schema on 2026-08-19. The
#: chiller tables hold 40 and the tower tables hold 11; this is the union, because the allow-list
#: a written statement is checked against must cover whichever table the question is about.
#:
#: **Held here rather than typed into the guard.** A hand-kept copy in the validator is a list
#: that drifts, and a column the guard does not know about is refused as invented even though it
#: is real — a refusal a reader cannot distinguish from the plant not having the signal.
#:
#: Note what being on this list does and does not mean. It means a statement naming the column
#: will not be refused as invented. It does **not** mean the reading is trustworthy:
#: `cond_flow` is never-measured, `kw_per_tr` and `chiller_flow` are suspect, and `dpt` is
#: constant. `app.domain.signals` owns that judgement and an answer must carry it.
TELEMETRY_COLUMNS: tuple[str, ...] = (
    "chiller_flow", "chw_delta_t", "comp1_discharge_temp", "comp1_kw", "comp1_load",
    "comp1_oil_pressure", "comp1_run_hours", "comp2_discharge_temp", "comp2_kw", "comp2_load",
    "comp2_oil_pressure", "comp2_run_hours", "compressor_power", "cond_entering_temp",
    "cond_flow", "cond_leaving_temp", "created_at", "cumulative_kwh", "cumulative_trh",
    "discharge_pressure", "discharge_temp", "dpt", "evap_entering_temp", "evap_flow",
    "evap_leaving_temp", "faulty", "id", "is_running", "kw", "kw_per_tr", "kwh", "manual",
    "percent_cooling_load", "run_hours", "slot_time", "ss_id", "suction_pressure",
    "temp_setpoint", "tr", "trh",
)
