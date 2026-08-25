"""The layering law, as a test rather than as a document.

Decision D-012. This runs `lint-imports` in-process so a violation shows up in `pytest`
rather than only in CI — the difference between finding out in ten seconds and finding out
after a push.

The contracts and the reasoning behind each are in `backend/importlinter.ini`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
CONFIG = BACKEND / "importlinter.ini"


def test_config_exists() -> None:
    """A missing config would make the contract test pass by accident."""
    assert CONFIG.is_file(), f"expected the layering contracts at {CONFIG}"


def test_import_contracts_hold() -> None:
    """Every contract in importlinter.ini is satisfied."""
    pytest.importorskip(
        "importlinter",
        reason="import-linter is not installed; the CI 'contracts' job runs it regardless",
    )
    # `python -m importlinter.cli lint-imports` exits 0 having done NOTHING — the package has
    # no `__main__`, and the arguments are silently discarded. This test therefore passed for
    # the whole life of the repository while the config was refused as misconfigured by the
    # real CLI, so all seven contracts went unchecked. Found 2026-08-17 when CI ran it.
    #
    # `lint-imports` is the console script the `contracts` job runs, so the test and the gate
    # now execute the same thing.
    result = subprocess.run(
        ["lint-imports", "--config", str(CONFIG)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        # Explicit: a non-zero exit is the interesting case, and `pytest.fail` below
        # reports the linter's own output, which names the offending import chain.
        check=False,
    )
    # A run that checked nothing must not read as a pass. The linter always reports how much
    # it looked at, and its absence means the config was refused before any contract ran.
    if "Analyzed" not in result.stdout:
        pytest.fail(
            "the linter produced no analysis, so nothing was checked. That is how this test "
            "passed while every contract was unenforced.\n\n"
            f"{result.stdout}\n{result.stderr}",
            pytrace=False,
        )

    if result.returncode != 0:
        # The linter's own output names the offending import chain, which is the useful part.
        pytest.fail(
            "the layering contracts are broken.\n\n"
            f"{result.stdout}\n{result.stderr}\n"
            "If the violation is legitimate, it is a decision — amend importlinter.ini and "
            "record why in decisions/DECISIONS.md, as D-012 did.",
            pytrace=False,
        )
