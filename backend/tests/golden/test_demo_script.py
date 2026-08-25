"""The demonstration script cannot rot.

`mvp/DEMO-SCRIPT.md` names exact equipment, dates and slot counts so that nobody picks a
window in front of an audience. That only helps if the named episodes still exist — so this
reads the script itself and checks every claim against the database.

If the snapshot is re-cloned and an episode moves, **the build fails rather than the
demonstration**. That is the whole point: the failure should happen on a laptop days
earlier, not in the room.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from app.config import Settings
from app.db.session import plant_repository

SCRIPT = Path(__file__).resolve().parents[3] / "mvp" / "DEMO-SCRIPT.md"

#: Every episode the script tells the presenter to select, with the slot count it claims.
#: Written here rather than parsed loosely, because a regex over prose that silently matches
#: nothing would make this test pass by finding no claims to check.
SCRIPTED_EPISODES = (
    ("chiller_2", "REFRIGERANT_SIDE_HIGH_HEAD", "2026-04-12", 30),
    ("chiller_1", "CONDENSER_LOW_FLOW", "2026-04-15", 3),
)


def test_the_script_exists_and_names_its_episodes() -> None:
    """A missing script is a demonstration improvised live."""
    assert SCRIPT.exists(), "mvp/DEMO-SCRIPT.md is missing"
    text = SCRIPT.read_text(encoding="utf-8")
    for equipment, label, day, _ in SCRIPTED_EPISODES:
        assert label in text, f"{label} is not named in the script"
        assert day in text, f"{day} is not named in the script"
        assert equipment.replace("_", " ") in text.lower(), f"{equipment} is not named"


@pytest.mark.requires_box
@pytest.mark.parametrize(
    "equipment,label,day,slots",
    SCRIPTED_EPISODES,
    ids=[f"{e}-{lab}-{d}" for e, lab, d, _ in SCRIPTED_EPISODES],
)
async def test_every_scripted_episode_still_exists(
    equipment: str, label: str, day: str, slots: int
) -> None:
    """The episode the presenter will click on is still there, with the slot count claimed."""
    settings = Settings()
    async with plant_repository(settings) as repo:
        d = datetime.fromisoformat(day)
        rows = await repo.residuals_for_day(equipment, d)
        matching = [r for r in rows if r.fault_label == label]

    assert matching, (
        f"the script tells the presenter to select {equipment} · {label} · {day}, "
        f"and no such episode exists in the measured window"
    )
    assert len(matching) == slots, (
        f"the script claims {slots} slots for {equipment} · {label} · {day}; "
        f"the database has {len(matching)}"
    )


@pytest.mark.requires_box
async def test_the_hero_machine_really_is_the_well_fitted_one() -> None:
    """The script says chiller 2's worst model runs at nRMSE 3.77 against chiller 1's 48.03.

    If a refit ever inverted that, the script would be walking the audience onto the badly
    fitted machine while calling it the clean one.
    """
    from app.domain import residuals

    assert residuals.worst_nrmse_for("chiller_2") == 3.77
    assert residuals.worst_nrmse_for("chiller_1") == 48.03
    assert not residuals.has_poor_fit("chiller_2")
    assert residuals.has_poor_fit("chiller_1")


@pytest.mark.requires_box
async def test_the_refusal_case_still_has_nothing_to_judge() -> None:
    """Step 6 asks about cooling tower 1 and expects a refusal. If a band ever appeared for
    it, the demonstration's best moment would quietly become an ordinary answer."""
    settings = Settings()
    async with plant_repository(settings) as repo:
        bands = await repo.residual_bands()
    assert not any(b.equipment_key == "cooling_tower_1" for b in bands)
    assert {b.equipment_key for b in bands} == {"chiller_1", "chiller_2"}


def test_the_script_states_the_measured_boundary() -> None:
    """The date the room will be told is synthetic-after must match the config."""
    text = SCRIPT.read_text(encoding="utf-8")
    boundary = Settings().synex_measured_window_end
    assert boundary.strftime("%Y-%m-%d") in text
    assert re.search(r"11:50", text), "the script must state the exact boundary time"


def test_the_script_says_what_to_do_when_the_box_is_down() -> None:
    """The likeliest failure on the day, and the one where a prepared sentence turns an
    outage into a feature demonstration."""
    text = SCRIPT.read_text(encoding="utf-8").lower()
    assert "box is down" in text
    assert "degraded" in text
