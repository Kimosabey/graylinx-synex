"""Tests for the settings class.

Two things are being defended here, and only one of them is ordinary.

The ordinary one: the ten ceilings exist, and each carries the failure it prevents. A bound
whose `stops` text went missing is a bound somebody raises without knowing what it was for.

The unusual one: **the measured-window end is a fact, not a preference.** D-009 says the
simulation invented `cond_flow` — a signal this plant has never measured — so a config edit
that pushes the window forward does not degrade an answer, it fabricates an instrumentation
capability. That validator is asserted from both sides.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.config import (
    CONTEXT_TRUNCATION_MARKER,
    RESOURCE_CEILINGS_PROVISIONAL,
    Settings,
    get_settings,
)

# The ten bounds from `docs/20-architecture/03-from-thermynx.md` §7, in its order.
EXPECTED_BOUNDS = [
    "max_input_chars",
    "max_context_chars",
    "max_react_steps",
    "graph_timeout_s",
    "tool_timeout_s",
    "max_specialists",
    "max_grounding_retries",
    "router_arbiter_timeout_s",
    "max_sql_rows",
    "max_sql_repairs",
]


# ── the ceilings ────────────────────────────────────────────────────────────────

def test_there_are_exactly_ten_ceilings() -> None:
    """Ten. The architecture record says copy the table, so the count is part of the copy."""
    assert [c["bound"] for c in Settings().ceilings()] == EXPECTED_BOUNDS


def test_every_ceiling_names_the_failure_it_prevents() -> None:
    for c in Settings().ceilings():
        assert c["stops"], f"{c['bound']} has no stated failure"
        assert len(str(c["stops"])) > 15, f"{c['bound']}'s reason is too thin to be useful"


def test_the_sourced_ceilings_match_the_architecture_record() -> None:
    """Seven values are inherited and quoted. If one drifts, the document is now wrong.

    These are not preferences. They came from a running system with its reasons recorded,
    and CLAUDE.md 2.2 makes them unchangeable here without a source.
    """
    s = Settings()
    assert s.max_react_steps == 8
    assert s.graph_timeout_s == 150.0
    assert s.tool_timeout_s == 30.0
    assert s.max_specialists == 4
    assert s.max_grounding_retries == 1
    assert s.router_arbiter_timeout_s == 3.0
    assert s.max_sql_repairs == 1


def test_exactly_three_ceilings_are_provisional() -> None:
    """Q48. This set must shrink as answers arrive, never grow.

    A fourth provisional ceiling would mean a number was invented, which is the rule
    CLAUDE.md 2.2 exists to enforce.
    """
    assert {
        "max_input_chars",
        "max_context_chars",
        "max_sql_rows",
    } == RESOURCE_CEILINGS_PROVISIONAL
    flagged = {c["bound"] for c in Settings().ceilings() if c["provisional"]}
    assert flagged == RESOURCE_CEILINGS_PROVISIONAL


def test_provisional_ceilings_cite_their_question() -> None:
    """A provisional number that does not say so is just a number."""
    for c in Settings().ceilings():
        if c["provisional"]:
            assert c["question"] == "Q48"
        else:
            assert c["question"] is None


@pytest.mark.parametrize("field", sorted(RESOURCE_CEILINGS_PROVISIONAL))
def test_a_ceiling_cannot_be_disabled_by_setting_it_to_zero(field: str) -> None:
    """`max_sql_rows=0` reads as "no limit" to whoever types it. It is rejected."""
    with pytest.raises(ValidationError):
        Settings(**{field: 0})


def test_truncation_marking_is_a_constant_not_a_setting() -> None:
    """Section 7 names silent partial context one of the two easy failures.

    A switch labelled "mark truncation" is a switch somebody turns off to make an output
    look tidier, so there is no switch.
    """
    assert not hasattr(Settings(), "context_truncation_marked")
    assert "truncated" in CONTEXT_TRUNCATION_MARKER


# ── the measured window ─────────────────────────────────────────────────────────

def test_the_measured_window_ends_where_real_data_ends() -> None:
    assert Settings().synex_measured_window_end == datetime(2026, 6, 23, 11, 50, 0)


def test_the_window_cannot_be_pushed_into_the_simulated_span() -> None:
    """D-009, enforced. This is the edit that would demonstrate fabricated `cond_flow`."""
    with pytest.raises(ValidationError) as exc:
        Settings(synex_measured_window_end=datetime(2026, 8, 5, 0, 0, 0))
    assert "cond_flow" in str(exc.value)


def test_the_window_may_be_pulled_back() -> None:
    """Narrowing is always safe — it asks about less data, never about invented data."""
    s = Settings(synex_measured_window_end=datetime(2026, 4, 15, 0, 0, 0))
    assert s.synex_measured_window_end == datetime(2026, 4, 15, 0, 0, 0)


# ── mode ────────────────────────────────────────────────────────────────────────

def test_the_default_mode_needs_no_gpu() -> None:
    """The gate must be the run that needs nothing. `pytest.ini` makes the same argument."""
    s = Settings()
    assert s.synex_model_mode == "stub"
    assert s.gpu_required is False


@pytest.mark.parametrize("mode,needs_box", [("stub", False), ("record", True), ("live", True)])
def test_only_stub_avoids_the_box(mode: str, needs_box: bool) -> None:
    assert Settings(synex_model_mode=mode).gpu_required is needs_box


def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(synex_model_mode="offline")


# ── connection strings ──────────────────────────────────────────────────────────

def test_the_plant_url_uses_the_read_only_user_and_port_3307() -> None:
    """Port 3307 because the service is MySQL80_1, and `synex_plant_ro` because of Q42."""
    url = Settings().mysql_url
    assert ":3307/" in url
    assert "synex_plant_ro" in url
    assert "root" not in url


def test_settings_are_cached() -> None:
    """One instance per process, so "which bound applied" stays answerable after the fact."""
    assert get_settings() is get_settings()
