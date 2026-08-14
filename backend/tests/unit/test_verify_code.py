"""Tests for the source compliance gate.

A gate that always passes is worse than no gate, and this one is easy to break in a way
that leaves it green: exclude one directory too many, import a rule table that has been
renamed, or let the Ragas pattern stop matching the form somebody actually types. So the
gate is fed known-bad text and must fail on it.

The scan-set tests matter as much as the rule tests. `verify_code.py` was written to skip
`node_modules`, `.venv` and recorded fixtures, and every one of those exclusions is a place
a real violation could hide if the *pattern* were slightly wrong — `fixtures` excluding
`app/fixtures_loader.py`, say. They are asserted by path rather than by eye.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


def _load_verify_code():
    """Load `scripts/verify_code.py` as a module.

    It is a script rather than a package — `scripts/` has no `__init__.py`, deliberately,
    because the documentation gates are run as files. Loading it by spec keeps that true
    while still letting the gate be tested.
    """
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "synex_verify_code", SCRIPTS / "verify_code.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vc = _load_verify_code()


def _check(text: str, name: str = "sample.py") -> list[str]:
    rep = vc.Report()
    vc.check_file(Path(name), text, rep)
    return rep.errors


# ── the rules that must fire ────────────────────────────────────────────────────

def test_banned_phrase_in_a_docstring_fails() -> None:
    errors = _check('"""Runs the checking that the work really worked step."""')
    assert errors, "a damaged phrase in a docstring must fail the gate"
    assert "verification" in errors[0]


def test_legacy_name_in_a_ui_string_fails() -> None:
    errors = _check('BUTTON_LABEL = "Ask the AI Copilot"')
    assert errors
    assert "Synex Copilot" in errors[0]


def test_synex_ai_fails() -> None:
    errors = _check("# Synex AI handles this")
    assert any("the AI is implied" in e for e in errors)


def test_separation_law_in_a_module_docstring_fails() -> None:
    errors = _check('"""This module lets the language model diagnose the chiller."""')
    assert any("separation law" in e for e in errors)


def test_separation_law_respects_a_denial() -> None:
    """The rule being *stated* is not the rule being broken.

    This is the phrasing the codebase should be full of, and a gate that failed on it
    would train people to stop writing it down.
    """
    assert not _check('"""The language model never diagnoses; the FDD rules name the fault."""')


@pytest.mark.parametrize(
    "line",
    [
        "import ragas",
        "from ragas import evaluate",
        "from ragas.metrics import faithfulness",
        "ragas==0.1.7",
        'ragas = "^0.1.0"',
        "  - ragas>=0.2",
        'const r = require("ragas")',
    ],
)
def test_ragas_is_banned_in_every_form_it_arrives_in(line: str) -> None:
    errors = _check(line)
    assert errors, f"the Ragas ban must catch {line!r}"
    assert "DeepEval" in errors[0]


def test_ragas_ban_explains_itself() -> None:
    """The message must carry the reason, or the next person just deletes the rule."""
    errors = _check("import ragas")
    assert "LangChain" in errors[0]


# ── the rules that must NOT fire, because they are wrong over code ──────────────

def test_lowercase_synex_is_allowed_in_code() -> None:
    """`graylinx_synex` is the database name. It is an identifier, not a sentence."""
    assert not _check('MYSQL_DB = "graylinx_synex"')
    assert not _check("from graylinx_synex import nothing  # a path, not prose")


def test_env_var_prefix_is_not_an_all_caps_violation() -> None:
    """`\\bSYNEX\\b` must not match inside `SYNEX_MODEL_MODE` — `_` is a word character.

    If this ever fails, the all-caps rule has to be dropped from the code gate: every
    setting in the product is prefixed this way.
    """
    assert not _check('mode = os.environ["SYNEX_MODEL_MODE"]')
    assert not _check("SYNEX_MEASURED_WINDOW_END=2026-06-23T11:50:00", "sample.env")


def test_feature_ids_are_not_checked_in_code() -> None:
    """`C1` is Copilot 1 in the register and an ordinary local name here."""
    assert not _check("C1 = 4.18  # specific heat\nRC1 = compute()\nF15 = band(x)")


def test_the_word_ragas_in_prose_is_not_an_import() -> None:
    """A comment explaining the ban must not trip it, or the ban cannot be documented."""
    assert not _check("# We do not use ragas here; DeepEval with a local judge instead.")


# ── the scan set ────────────────────────────────────────────────────────────────

def test_the_gate_actually_scans_the_backend() -> None:
    scanned = {vc.rel(p) for p in vc.targets()}
    assert "backend/app/analytics/honesty.py" in scanned
    assert "backend/app/llm/models.py" in scanned
    assert "backend/importlinter.ini" in scanned


def test_dependencies_and_build_output_are_excluded() -> None:
    for path in vc.targets():
        parts = set(path.parts)
        assert "node_modules" not in parts
        assert ".venv" not in parts
        assert "__pycache__" not in parts


def test_the_dependency_manifests_are_actually_found() -> None:
    """Found by name, not by suffix — `.txt` is not in `CODE_SUFFIXES`.

    This check reported "0 dependency manifest(s)" when `requirements.txt` existed, which
    meant the Ragas ban could not see the one file it most needs to read.
    """
    found = {vc.rel(p) for p in vc.manifests()}
    assert "backend/requirements.txt" in found
    assert "backend/requirements-dev.txt" in found


def test_a_bare_dependency_line_is_caught() -> None:
    """`ragas` alone, unpinned, matches none of the line patterns. It is the trying-it-out
    form, so the manifest rule is looser than the source rule."""
    rep = vc.Report()
    manifest = ROOT / "backend" / "requirements.txt"
    original = manifest.read_text(encoding="utf-8")
    try:
        manifest.write_text(original + "\nragas\n", encoding="utf-8")
        vc.check_manifests(rep)
        assert rep.errors, "a bare banned dependency must fail the gate"
        assert "DeepEval" in rep.errors[0]
    finally:
        manifest.write_text(original, encoding="utf-8")


def test_a_comment_mentioning_a_banned_dependency_is_not_a_dependency() -> None:
    """`requirements.txt` explains why Ragas is absent. Explaining must stay possible."""
    rep = vc.Report()
    manifest = ROOT / "backend" / "requirements.txt"
    original = manifest.read_text(encoding="utf-8")
    try:
        manifest.write_text(original + "\n# ragas is banned, see D-010\n", encoding="utf-8")
        vc.check_manifests(rep)
        assert rep.errors == [], "\n".join(rep.errors)
    finally:
        manifest.write_text(original, encoding="utf-8")


def test_the_rule_tables_are_imported_not_copied() -> None:
    """If `verify.py` renames a table, this gate must break loudly rather than drift.

    The whole reason the tables are imported is CLAUDE.md 2.8 — one source of truth per
    fact. A copy would rot silently, which is the exact failure the tables prevent in prose.
    """
    import verify

    assert vc.BANNED_PHRASES is verify.BANNED_PHRASES
    assert vc.LEGACY_NAMES is verify.LEGACY_NAMES


def test_only_the_lowercase_synex_rule_is_dropped() -> None:
    """Exactly one naming rule is excused over code, and it is excused by identity.

    Asserting the count stops a future edit to `verify.py` from quietly widening what
    the code gate ignores.
    """
    import verify

    assert len(vc.CODE_NAMING_VIOLATIONS) == len(verify.NAMING_VIOLATIONS) - 1
    dropped = {p for p, _ in verify.NAMING_VIOLATIONS} - {
        p for p, _ in vc.CODE_NAMING_VIOLATIONS
    }
    assert dropped == {vc.LOWERCASE_SYNEX_PATTERN}


def test_the_repository_is_currently_clean() -> None:
    """The gate must pass on the tree as it stands, or CI is red the moment it lands."""
    rep = vc.Report()
    for path in vc.targets():
        vc.check_file(path, path.read_text(encoding="utf-8", errors="replace"), rep)
    assert rep.errors == [], "\n".join(rep.errors)
