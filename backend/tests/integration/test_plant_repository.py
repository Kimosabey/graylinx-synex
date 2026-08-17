"""The measured facts, asserted against the live database rather than against a document.

`tests/unit/test_measured_facts.py` asserts what the *documents* say. This file asserts what
the *database* returns, using the same numbers. That pairing is the point: a query bug now
surfaces as **5,308 instead of 5,309** rather than as a plausible answer nobody checks.

Marked `requires_box`, so a bare `pytest` skips them and CI never needs the 3.9 GB snapshot.
Run them with `pytest -m requires_box` when MySQL is up.

Writing these found a real error. The approved plan states *"a current residual of −25 is
NORMAL on chiller 1 and abnormal on chiller 2"*. Querying `gla_residual_stats_wc` disproves
it — chiller 2's robust band reaches 0.680, so −25 is normal on both. The unit test had been
written to the plan's version using an invented band, which made a false statement look
verified. `test_the_plan_is_wrong_about_minus_25` keeps the correction from regressing.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.analytics.bands import BandVerdict, classify, find_band
from app.config import Settings
from app.db.plant import UNFITTED_RESIDUAL_COLUMN, PlantRepository
from app.db.session import plant_repository
from app.domain import faults

pytestmark = pytest.mark.requires_box


@pytest.fixture
async def repo():
    async with plant_repository(Settings()) as r:
        yield r


# ── the fault inventory ─────────────────────────────────────────────────────────

async def test_the_documented_label_counts_are_what_the_database_returns(
    repo: PlantRepository,
) -> None:
    """Every one of the nine, exactly. This is the assertion the whole layer exists for."""
    counts = {c.label: c.slots for c in await repo.label_counts()}

    documented = {f.label: f.measured_slots for f in faults.FAULT_CLASSES}
    for label, expected in documented.items():
        assert counts.get(label) == expected, (
            f"{label}: database says {counts.get(label)}, the documents say {expected}"
        )


async def test_the_unlabelled_count_matches(repo: PlantRepository) -> None:
    counts = {c.label: c.slots for c in await repo.label_counts()}
    assert counts.get(None) == faults.UNLABELLED_SLOTS


async def test_the_refusal_really_is_the_modal_outcome(repo: PlantRepository) -> None:
    """5,309 against 674. The strongest asset in this database, verified rather than quoted."""
    counts = {c.label: c.slots for c in await repo.label_counts()}
    faulted = sum(
        n for label, n in counts.items()
        if label is not None and label not in ("NO_DIAGNOSIS", "NO_EFFICIENCY_FAULT")
    )
    assert faulted == 674
    assert counts["NO_DIAGNOSIS"] == 5_309
    assert counts["NO_DIAGNOSIS"] > faulted * 7


async def test_faulted_slots_excludes_both_non_fault_outcomes(repo: PlantRepository) -> None:
    rows = await repo.faulted_slots()
    assert len(rows) == 674
    assert all(r.is_fault for r in rows)
    assert not any(r.fault_label in ("NO_DIAGNOSIS", "NO_EFFICIENCY_FAULT") for r in rows)


# ── coverage ────────────────────────────────────────────────────────────────────

async def test_only_two_assets_have_any_scored_residual(repo: PlantRepository) -> None:
    """The 10-of-12 coverage fact, from the database rather than from a chapter."""
    assert set(await repo.scored_equipment_keys()) == {"chiller_1", "chiller_2"}


async def test_the_table_name_does_not_leak_upward(repo: PlantRepository) -> None:
    """`gla_model_residuals_wc.equipment` holds `chiller_1_normalized`. Callers see
    `chiller_1`, because database naming is not a domain concept."""
    keys = await repo.scored_equipment_keys()
    assert not any(k.endswith("_normalized") for k in keys)


async def test_the_sixth_model_is_entirely_null(repo: PlantRepository) -> None:
    """Every document saying "six models" is a claim the data contradicts. Asserted as a
    query, not trusted as prose.

    **Narrowed at the 2026-08-17 re-clone.** The rebuilt source carries 4,281 non-null
    values for this column, all beyond the measured window. Inside the window — everything
    the product shows — it is still entirely NULL, so the honest sentence is now *five
    models are fitted over the measured window; a sixth appears only in the derived tail.*
    Both halves are asserted, because a test that checked only the first would pass again
    the day the tail moved inside the clip.
    """
    assert await repo.unfitted_residual_is_entirely_null()
    assert UNFITTED_RESIDUAL_COLUMN == "compressor_power_residual"

    count, first = await repo.unfitted_residual_outside_the_window()
    assert count == 4_281, f"{count} values beyond the clip, expected 4,281 — the source moved"
    assert first is not None and first > repo._measured_window_end, (
        "the sixth model's values must stay outside the measured window; if they enter it, "
        "five-models-are-fitted stops being true of what the product shows"
    )


# ── bands ───────────────────────────────────────────────────────────────────────

async def test_there_are_exactly_ten_bands(repo: PlantRepository) -> None:
    """Five residuals for each of two chillers. Nothing for the other ten assets."""
    bands = await repo.residual_bands()
    assert len(bands) == 10
    assert {b.equipment_key for b in bands} == {"chiller_1", "chiller_2"}


async def test_the_measured_medians_match_the_documents(repo: PlantRepository) -> None:
    """`CONTEXT.md` §6 quotes four of these by name. If one drifts, a chapter is now wrong."""
    bands = await repo.residual_bands()
    c1_current = find_band(bands, "chiller_1", "chiller_current_residual")
    c2_current = find_band(bands, "chiller_2", "chiller_current_residual")
    c1_dp = find_band(bands, "chiller_1", "Dp_residual")
    c2_dp = find_band(bands, "chiller_2", "Dp_residual")

    assert c1_current.median == pytest.approx(-25.645, abs=1e-3)
    assert c2_current.median == pytest.approx(-30.010, abs=1e-3)
    assert c1_dp.median == pytest.approx(-7.53, abs=1e-2)
    assert c2_dp.median == pytest.approx(-27.86, abs=1e-2)


async def test_zero_is_abnormal_on_one_machine_and_normal_on_the_other(
    repo: PlantRepository,
) -> None:
    """`F15` against the real bands. The compare-to-zero bug, caught on live data.

    0.0 — the value a naive implementation reads as perfectly healthy — is HIGH on chiller 1
    and NORMAL on chiller 2. The naive reading is not imprecise, it is inverted.
    """
    bands = await repo.residual_bands()
    c1 = find_band(bands, "chiller_1", "chiller_current_residual")
    c2 = find_band(bands, "chiller_2", "chiller_current_residual")

    assert classify(0.0, c1) is BandVerdict.HIGH
    assert classify(0.0, c2) is BandVerdict.NORMAL


async def test_the_plan_is_wrong_about_minus_25(repo: PlantRepository) -> None:
    """The plan says −25 is abnormal on chiller 2. The measured band says otherwise.

    Kept as a test so nobody "fixes" the code to match the document. The document is the
    thing that was wrong, and this is the query that proves it.
    """
    bands = await repo.residual_bands()
    c2 = find_band(bands, "chiller_2", "chiller_current_residual")
    assert c2.upper == pytest.approx(0.680, abs=1e-3)
    assert classify(-25.0, c2) is BandVerdict.NORMAL


async def test_no_band_exists_for_the_unscoreable_ten(repo: PlantRepository) -> None:
    bands = await repo.residual_bands()
    for key in ("cooling_tower_1", "condenser_pump_2", "primary_pump_3", "plant"):
        assert find_band(bands, key, "chiller_current_residual") is None


# ── the window clip ─────────────────────────────────────────────────────────────

async def test_the_measured_window_is_the_default(repo: PlantRepository) -> None:
    """D-009. Reaching the simulated span must take an explicit flag at the call site."""
    clipped = {c.label: c.slots for c in await repo.label_counts()}
    widened = {c.label: c.slots for c in await repo.label_counts(include_simulated=True)}

    assert clipped["NO_DIAGNOSIS"] == 5_309
    assert widened["NO_DIAGNOSIS"] >= clipped["NO_DIAGNOSIS"]
    assert sum(widened.values()) > sum(clipped.values()), (
        "the simulated window should add slots; if it does not, the clip is not being applied "
        "and both queries are returning the same rows"
    )


async def test_a_day_query_returns_ordered_slots(repo: PlantRepository) -> None:
    """2026-04-15 — the day chiller 1 carried five labels at once."""
    rows = await repo.residuals_for_day("chiller_1", datetime(2026, 4, 15))
    assert rows
    assert [r.slot_time for r in rows] == sorted(r.slot_time for r in rows)
    assert {r.equipment_key for r in rows} == {"chiller_1"}


async def test_five_labels_on_the_fifteenth(repo: PlantRepository) -> None:
    """The case-inflation example, from the database. One repair, five naive work orders."""
    rows = await repo.residuals_for_day("chiller_1", datetime(2026, 4, 15))
    labels = {r.fault_label for r in rows if r.is_fault}
    assert len(labels) == 5
    assert "CONDENSER_LOW_FLOW" in labels
    assert "HIGH_HEAD_AMBIGUOUS" in labels


async def test_an_unscoreable_asset_returns_nothing_rather_than_raising(
    repo: PlantRepository,
) -> None:
    """Ten of twelve. Empty is the honest answer; the gate turns it into NO_DIAGNOSIS."""
    assert await repo.residuals_for_day("cooling_tower_1", datetime(2026, 4, 15)) == ()
    assert await repo.residuals_for_day("nonexistent_asset", datetime(2026, 4, 15)) == ()


async def test_a_null_residual_stays_none(repo: PlantRepository) -> None:
    """Constraint 7: a NULL means not diagnosed, never healthy — and never 0.0."""
    rows = await repo.residuals_for_day("chiller_1", datetime(2026, 4, 15))
    assert all(r.residuals[UNFITTED_RESIDUAL_COLUMN] is None for r in rows)
