"""Two rules that only hold if a test holds them: the role table, and the reasoning policy.

The first turns *"code never names a model"* from a convention into a gate — a model string
appearing outside `app/llm/models.py` fails the build. The second locks the default that stops
an empty answer.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.llm import models as role_table
from app.llm.reasoning_policy import should_think

APP = Path(role_table.__file__).resolve().parents[1]
ROLE_TABLE = Path(role_table.__file__).resolve()


# ── code never names a model ───────────────────────────────────────────────────

def test_no_module_but_the_role_table_names_a_model() -> None:
    """The guarantee. Retiring a model must cost one line, in one place."""
    names = role_table.all_model_names()
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        if path.resolve() == ROLE_TABLE:
            continue
        text = path.read_text(encoding="utf-8")
        for literal in ast.walk(ast.parse(text)):
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                if literal.value in names:
                    offenders.append(f"{path.relative_to(APP.parent)}:{literal.lineno}")
    assert not offenders, (
        "a model name appears outside the role table:\n  "
        + "\n  ".join(offenders)
        + "\nAsk for a role instead; app.llm.models resolves it."
    )


def test_aliases_resolve_to_a_real_model() -> None:
    """`planner` and `composer` are the brain; `sql` is the tool model."""
    assert role_table.model_for("planner") == role_table.model_for("brain")
    assert role_table.model_for("composer") == role_table.model_for("brain")
    assert role_table.model_for("sql") == role_table.model_for("tool")


def test_the_auditor_is_not_the_brain() -> None:
    """The auditor must never be the model that wrote the answer. That is why the aliasing
    lives in code rather than in configuration."""
    assert role_table.model_for("auditor") != role_table.model_for("brain")


def test_there_are_exactly_four_models() -> None:
    """CONTEXT.md section 4: do not invent a fifth."""
    assert len(role_table.all_model_names()) == 4


def test_an_unknown_role_raises_rather_than_defaulting() -> None:
    """A silent default would mean a call site quietly running on the wrong model."""
    with pytest.raises(ValueError, match="unknown role"):
        role_table.model_for("oracle")


def test_embeddings_are_not_editable_at_run_time() -> None:
    """Changing the embedding model invalidates every stored vector — a migration, not a knob."""
    assert "embed" not in role_table.EDITABLE


# ── reasoning on or off ───────────────────────────────────────────────────────

def test_reasoning_is_on_for_diagnosis() -> None:
    assert should_think("root_cause")
    assert should_think("diagnose")
    assert should_think("investigate")


def test_reasoning_is_off_for_composition() -> None:
    """Composition is the common case and the one that breaks."""
    assert not should_think("composer")
    assert not should_think("synthesis")
    assert not should_think("sql")
    assert not should_think("auditor")


def test_an_unknown_task_defaults_off() -> None:
    """The important default. On, it would return empty content rather than a worse answer."""
    assert not should_think("some_task_nobody_registered")


def test_the_planner_is_exempt() -> None:
    """Forced-JSON output has no free-form channel to starve."""
    assert not should_think("planner")


def test_the_flag_is_only_sent_to_the_brain() -> None:
    """The other two models reject it."""
    assert should_think("root_cause", role="brain")
    assert not should_think("root_cause", role="tool")
    assert not should_think("root_cause", role="auditor")
