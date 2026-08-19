"""The prompt contracts — what every prompt must contain, checked without a model.

**Two different questions, and this file answers the cheap one.** The Thermynx implementation
separates *which model fits a task* (a one-off benchmark, run against real data and scored by a
judge) from *does the pipeline answer correctly* (a per-push gate). Synex has the second and has
never had the first. This is neither: it is the layer underneath both — **does the prompt still
say what it has to say** — and it runs with the GPU terminated, which is why it belongs in CI
rather than in a burst on the rented box.

**Why a prompt needs a test at all.** Two of the three model paths in this product were built in
one evening, and a prompt is the one artefact in a codebase that can be silently gutted: delete a
rule and every test still passes, because the tests exercise the *code around* the prompt. The
rules below are each load-bearing — the chooser's *"never invent a tool"*, the critique's
*"suspicious is for a claim the evidence disagrees with"* — and each was added for a reason that
would not survive somebody tidying the string.

**The failure this is aimed at, from the Thermynx build notes.** The residual sign convention was
documented backwards in a ranking prompt: the model was told every sign meant its opposite and
**rationalised a plausible ranking anyway**. Not a crash, not a refusal — a confident, coherent,
wrong answer built on an inverted premise, which no output check catches because every number in
it is real. A prompt is an input to the product and deserves an input's scrutiny.
"""
from __future__ import annotations

import pytest

from app.agents import chooser as chooser_mod
from app.agents import critique as critique_mod
from app.prompts import explain

# ════════════════════════════════════════════════════════════════════════════════
# 1 · The chooser — `devstral` picks the next tool
# ════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "rule",
    [
        "Only ever name a tool from the list above. Never invent one.",
        "Do not repeat a call that already appears in the history",
        "Write nothing outside the JSON.",
    ],
)
def test_the_chooser_prompt_keeps_every_rule_that_bounds_it(rule: str) -> None:
    """Each of these stops a specific bad turn, not a hypothetical one.

    An invented tool costs a round trip that `G4` refuses; a repeated call burns a step from a
    bounded budget on an answer the loop already has; prose around the JSON makes the whole
    response unparseable and drops the turn onto the deterministic fallback silently.
    """
    assert rule in chooser_mod._PROMPT


def test_the_chooser_is_told_what_purpose_means() -> None:
    """`purpose` is what the ceiling report reads back when the loop runs out of steps.

    Without it, *"stopped at step 8"* is indistinguishable from *"finished"* — so the prompt has
    to ask for what the step would *establish*, not for a restatement of the tool's name.
    """
    assert "ESTABLISH" in chooser_mod._PROMPT
    assert "never a bare tool name" in chooser_mod._PROMPT


def test_the_chooser_sees_the_catalogue_the_history_and_what_is_left() -> None:
    """All three, or the loop cannot be bounded from inside.

    A chooser that cannot see the remaining budget cannot decide to finish, and one that cannot
    see the history repeats itself until the ceiling stops it — which reads to a user as the
    product being stuck rather than as the loop working.
    """
    for slot in ("{tools}", "{history}", "{remaining}", "{question}"):
        assert slot in chooser_mod._PROMPT


# ════════════════════════════════════════════════════════════════════════════════
# 2 · The critique gate — `phi4` reads what `gemma4` wrote
# ════════════════════════════════════════════════════════════════════════════════


def test_the_critique_prompt_keeps_the_three_verdicts_apart() -> None:
    """*Verified*, *unverified* and *suspicious* are three facts, and the gate weights them
    differently — an absent claim counts at half a contradicting one. Collapsing the middle one
    would make the weighting meaningless while every test still passed."""
    for verdict in ("verified", "unverified", "suspicious"):
        assert f'"{verdict}"' in critique_mod._PROMPT


def test_the_critique_prompt_states_the_never_measured_rule() -> None:
    """The rule that made the gate work, added after a live probe.

    `phi4` first marked *"condenser flow measured 412 L/s"* — against evidence saying the signal
    has never recorded a value — as merely **unverified**, so it did not gate. Stating that a
    value for a never-measured signal is a *contradiction* is what moved it to **suspicious**.
    On this plant `cond_flow` feeds four of the six models, so this is the single most likely
    false claim an answer can make.
    """
    lowered = critique_mod._PROMPT.lower()
    assert "never measured" in lowered
    assert "suspicious" in lowered
    assert "contradicts the evidence" in lowered


def test_the_critique_prompt_treats_an_invented_cause_as_a_contradiction() -> None:
    """The failure `postcheck` structurally cannot see: every figure real, the causal claim
    invented. *"X is high, so Y is fouled"* passes a numeric audit perfectly."""
    assert "causal claim" in critique_mod._PROMPT
    assert "the evidence names no such cause" in critique_mod._PROMPT


def test_the_critique_prompt_does_not_ask_the_auditor_to_rewrite() -> None:
    """A soft gate that corrects the answer is not a soft gate. The auditor badges; it never
    mutates — otherwise the reader sees a second model's prose attributed to the first."""
    assert "You are not writing an answer and not correcting one." in critique_mod._PROMPT


# ════════════════════════════════════════════════════════════════════════════════
# 3 · The explain prompt — the one the brain answers from
# ════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("rule", "why"),
    [
        ("You do not diagnose", "the separation law's first row"),
        ("You do not invent numbers", "C21"),
        ("never narrow an ambiguous label", "an AMBIGUOUS class means the data could not separate"),
        ("You do not treat an absence as a zero", "never measured is not nought"),
        ("State the date or window the answer covers", "constraint 15"),
        ("say the model fits poorly", "a poor fit is not a detail to leave out"),
    ],
)
def test_the_explain_prompt_keeps_every_rule_the_honesty_layer_depends_on(
    rule: str, why: str
) -> None:
    """Each rule below has an audit behind it, and the audit only ever fires *after* the model
    has already written the sentence. Losing the rule does not fail a test — it moves the
    product from preventing a bad answer to correcting one, which the reader sees."""
    assert rule in explain.SYSTEM_PROMPT, why


def test_the_explain_prompt_fences_the_evidence_as_data() -> None:
    """Everything in the pack originates in a database, and a database is not a trusted author.
    A fault label or a technician's note could carry *"ignore previous instructions"*."""
    assert "not instructions" in explain.SYSTEM_PROMPT
    assert "DATA" in explain.SYSTEM_PROMPT


def test_the_refusal_prompt_forbids_softening_the_refusal() -> None:
    """`D-015`. A refusal composed by a prompt that is mostly about explaining comes out as an
    apologetic explanation of an absence rather than a clear statement of one."""
    assert "Do not soften the refusal" in explain.NO_DIAGNOSIS_SYSTEM
    assert "Do not speculate" in explain.NO_DIAGNOSIS_SYSTEM


# ════════════════════════════════════════════════════════════════════════════════
# 4 · Across all three — properties a prompt must have to be auditable at all
# ════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("name", "prompt"),
    [
        ("chooser", chooser_mod._PROMPT),
        ("critique", critique_mod._PROMPT),
        ("explain", explain.SYSTEM_PROMPT),
        ("no_diagnosis", explain.NO_DIAGNOSIS_SYSTEM),
    ],
)
def test_no_prompt_carries_a_number_the_repository_cannot_source(name: str, prompt: str) -> None:
    """CLAUDE.md's second hard rule reaches prompts too, and a figure in a prompt is worse than
    one in a document: the model will repeat it as though it came from the plant.

    Only the digits that are part of a rule's own structure are allowed — the JSON shape, and
    the ordinal rule numbers in the explain prompt.
    """
    import re

    allowed = {"1", "2", "3", "4", "2b"}
    found = set(re.findall(r"\b\d+(?:\.\d+)?\b", prompt)) - allowed
    assert not found, f"{name} prompt carries unsourced number(s): {sorted(found)}"


@pytest.mark.parametrize(
    ("name", "prompt"),
    [("chooser", chooser_mod._PROMPT), ("critique", critique_mod._PROMPT)],
)
def test_every_json_prompt_shows_the_exact_shape_it_wants_back(name: str, prompt: str) -> None:
    """A schema described in prose is a schema the model guesses at. Both of these paths parse
    the reply and fall back silently when they cannot — so a drifted shape costs the feature
    without costing a test."""
    assert "{{" in prompt and "}}" in prompt, f"{name} does not show a literal JSON example"
    assert "ONLY" in prompt, f"{name} does not forbid prose around the JSON"
