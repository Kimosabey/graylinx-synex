"""The layering law, as a test rather than as a document.

Decision D-012. This runs `lint-imports` in-process so a violation shows up in `pytest`
rather than only in CI — the difference between finding out in ten seconds and finding out
after a push.

The contracts and the reasoning behind each are in `backend/importlinter.ini`.
"""
from __future__ import annotations

import subprocess
import sys
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
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint-imports",
         "--config", str(CONFIG)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
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
