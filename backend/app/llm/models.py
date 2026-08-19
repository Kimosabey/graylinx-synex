"""The role table — the reason code never names a model.

Every call site asks for a **role**; this module resolves it. Ported from the sibling, where
the indirection earned its keep the day the previous SQL model was retired: *"retiring it was
one line — `sql` now resolves to `tool`. Nothing else changed, because the security guarantee
never lived in the model choice."*

Three roles are aliases rather than models of their own, and they are aliases **here** rather
than in configuration. Making them configurable would let someone point the auditor at the
brain, which would break the rule that the auditor must never be the model that wrote the
answer — a guarantee, not a preference.

`app.llm` is the only package permitted to import a model client. Contract 5 in
`importlinter.ini` enforces it, and `tests/unit/test_role_table.py` asserts no model string
appears anywhere else.
"""
from __future__ import annotations

from typing import Literal

Role = Literal[
    "brain",      # reasoning and the final answer
    "planner",    # decomposition — an alias
    "composer",   # final composition — an alias
    "tool",       # decides which tools to call
    "sql",        # writes the SELECT — an alias
    "auditor",    # critique, routing arbitration, ranking
    "text",       # narration
    "rag",        # grounding
    "embed",      # retrieval vectors
]

# The four models, and nowhere else. CONTEXT.md section 4: do not invent a fifth.
BRAIN = "gemma4:26b-a4b-it-qat"
TOOL = "devstral:latest"
TEXT = "phi4"
EMBED = "nomic-embed-text"

# Aliases resolve before the lookup, so the table below has one row per real model.
#
# **`planner` points at `brain`, matching the v4 roster.** The division of labour Synex is
# built around, and the one Thermynx settled on: **gemma plans, composes and reasons; devstral
# executes and writes SQL; phi4 audits** — from a different family, so it never grades its own
# output. Thermynx's roster says it in one line: *"the brain takes planning + composition +
# reasoning (planner/composer→brain)"*.
#
# **This sat on `text` for a day, on a half-read finding.** The 26B model was recorded
# degenerating into a repetition loop while emitting JSON — *"…pressure-driven work to
# pressure-driven work conversion efficiency loss in pressure-driven work to pressure-"* — the
# object never closing, and **every plan silently becoming empty**. Not a crash and not a
# refusal: an empty result that reads as "nothing to plan". All true, and none of it an
# argument for a different model. The same roster records the cause: the brain *"works in
# JSON-mode (thinks AND emits JSON), goes BLANK in a tight plain-text cap"*.
#
# **So the fix is in the call, not the table.** Every caller that parses a reply as JSON sets
# `json_only`, which constrains Ollama's decode so an unterminated object cannot be produced,
# and takes the ~25s the roster budgets for a plan. Asking a thinking model for JSON in free
# text with no room to think is the failure — the mode, not the model.
_ALIASES: dict[str, str] = {
    "planner": "brain",
    "composer": "brain",
    "sql": "tool",
}

_ROLE_MODEL: dict[str, str] = {
    "brain": BRAIN,
    "tool": TOOL,
    "auditor": TEXT,
    "text": TEXT,
    "rag": TEXT,
    "embed": EMBED,
}

# Which roles a human may repoint at run time. `embed` is excluded on purpose: changing the
# embedding model invalidates every vector already stored, so it is a migration, not a setting.
EDITABLE: frozenset[str] = frozenset({"brain", "tool", "auditor", "text", "rag"})


def effective_role(role: str) -> str:
    """Resolve an alias to the role that owns a model."""
    return _ALIASES.get(role, role)


def model_for(role: str) -> str:
    """The model behind a role.

    Raises rather than falling back. A silent default here would mean a call site quietly
    running on the wrong model, which is the failure this whole indirection exists to prevent.
    """
    resolved = effective_role(role)
    try:
        return _ROLE_MODEL[resolved]
    except KeyError:
        raise ValueError(
            f"unknown role {role!r} (resolved to {resolved!r}); "
            f"known roles are {sorted(set(_ROLE_MODEL) | set(_ALIASES))}"
        ) from None


def roster() -> dict[str, str]:
    """Every role and the model it currently resolves to. Powers the models endpoint."""
    return {role: model_for(role) for role in (*_ROLE_MODEL, *_ALIASES)}


def all_model_names() -> frozenset[str]:
    """The four strings that may appear in this module and nowhere else."""
    return frozenset({BRAIN, TOOL, TEXT, EMBED})
