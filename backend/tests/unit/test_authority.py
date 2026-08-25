"""`G2` risk classification · `G3` the approval engine.

*Is this person allowed?* is decided by plain software. These tests exist to keep it that
way — and to keep the two constraints with incidents behind them from eroding: roles are
capabilities rather than ranks, and an untagged action defaults to the stricter side.
"""
from __future__ import annotations

import pytest

from app.domain.authority import (
    DEFAULT_RISK,
    NEVER_APPROVABLE,
    REQUIRED_CAPABILITY,
    Action,
    Decision,
    Risk,
    classify,
    rule,
)
from app.services.control_plane import Persona, compute_scope

ENGINEER = frozenset({"view_faults", "view_residuals", "open_case"})
SUPERVISOR = frozenset({"view_faults", "approve_work", "close_work"})
TECHNICIAN = frozenset({"view_faults", "record_findings"})


# ── G2: classification ─────────────────────────────────────────────────────────

def test_an_unclassified_action_defaults_to_the_stricter_side() -> None:
    """Constraint 24. Mis-tagging a high-risk action as low puts an unqualified decision into
    production; the reverse wastes an approval. Over-escalating is the cheap error."""
    risk, defaulted = classify(Action(name="do_something"))
    assert risk is DEFAULT_RISK is Risk.HIGH
    assert defaulted is True


def test_an_irreversible_action_is_raised_to_high_even_when_declared_lower() -> None:
    """Constraint 29: elimination is final. A caller that under-declares a one-way door does
    not get the last word on it."""
    risk, defaulted = classify(
        Action(name="eliminate_cause", risk=Risk.LOW, reverses_cleanly=False)
    )
    assert risk is Risk.HIGH
    assert defaulted is False, "raised, not defaulted — those are different facts"


def test_a_reversible_low_action_stays_low() -> None:
    risk, defaulted = classify(Action(name="read_residuals", risk=Risk.LOW))
    assert risk is Risk.LOW
    assert defaulted is False


# ── G3: the two kinds that are never approvable ────────────────────────────────

@pytest.mark.parametrize("risk", sorted(NEVER_APPROVABLE))
def test_no_capability_clears_a_never_approvable_action(risk: Risk) -> None:
    """`S1`: the platform stops and does not weigh the risk itself.

    Tested with **every** capability held, because the failure to prevent is somebody
    sufficiently senior signing off a safety stop.
    """
    everything = frozenset(
        {"view_faults", "view_residuals", "open_case", "record_findings",
         "approve_work", "close_work", "edit_policy"}
    )
    ruling = rule(Action(name="stop_the_machine", risk=risk), everything)
    assert ruling.decision is Decision.REFUSED
    assert ruling.is_refusal
    assert not ruling.may_proceed
    assert "no approval clears it" in ruling.reason


def test_safety_critical_is_a_kind_not_the_top_of_a_scale() -> None:
    """If it were merely 'highest', a sufficiently senior person could sign it off — which is
    the reading `S1` exists to prevent."""
    assert Risk.SAFETY_CRITICAL in NEVER_APPROVABLE
    assert Risk.SAFETY_CRITICAL not in REQUIRED_CAPABILITY


# ── G3: capabilities, not ranks ────────────────────────────────────────────────

def test_approval_asks_for_a_named_capability_never_for_seniority() -> None:
    """Constraint 13. A comparison like `persona >= SUPERVISOR` would rebuild the seniority
    ladder that sent a filter-drier restriction to a supervisor, invisibly."""
    ruling = rule(Action(name="close_work_order", risk=Risk.HIGH), SUPERVISOR)
    assert ruling.may_proceed
    assert ruling.required_capability == "approve_work"


def test_a_technician_is_not_a_lesser_supervisor_and_a_supervisor_not_a_better_technician() -> None:
    """Constraint 25: different capabilities, not a ladder. Each holds something the other
    does not, and the engine must not order them."""
    high = Action(name="approve_a_job", risk=Risk.HIGH)
    assert rule(high, SUPERVISOR).may_proceed
    assert not rule(high, TECHNICIAN).may_proceed

    medium = Action(name="open_a_case", risk=Risk.MEDIUM)
    assert rule(medium, ENGINEER).may_proceed
    assert not rule(medium, SUPERVISOR).may_proceed, (
        "a supervisor does not hold open_case — if this passes, seniority has crept back in"
    )


def test_low_risk_needs_no_approval_at_all() -> None:
    ruling = rule(Action(name="read_a_band", risk=Risk.LOW), frozenset())
    assert ruling.may_proceed
    assert ruling.required_capability == ""


# ── needing authority is not a refusal ─────────────────────────────────────────

def test_needing_approval_is_not_a_refusal() -> None:
    """Collapsing them would tell a caller to give up when somebody down the corridor could
    sign. The answer state is `NEEDS_APPROVAL`, not `BLOCKED`."""
    ruling = rule(Action(name="approve_a_job", risk=Risk.HIGH), TECHNICIAN)
    assert ruling.decision is Decision.NEEDS_APPROVAL
    assert ruling.is_refusal is False
    assert ruling.may_proceed is False
    assert "approve_work" in ruling.reason


def test_an_unclassified_action_reports_itself_distinctly() -> None:
    """Absorbed into `NEEDS_APPROVAL` it would be invisible, and the register would stop
    matching the code without anyone noticing."""
    ruling = rule(Action(name="mystery_action"), TECHNICIAN)
    assert ruling.decision is Decision.UNCLASSIFIED
    assert ruling.was_unclassified is True
    assert "Nobody classified this action" in ruling.reason
    assert ruling.risk is Risk.HIGH


def test_an_unclassified_action_still_passes_for_someone_who_holds_the_capability() -> None:
    """Defaulting to strict must not become defaulting to impossible."""
    ruling = rule(Action(name="mystery_action"), SUPERVISOR)
    assert ruling.may_proceed
    assert ruling.was_unclassified is True


# ── it agrees with the Control Plane ───────────────────────────────────────────

@pytest.mark.parametrize("persona", list(Persona))
def test_every_persona_is_ruled_on_without_error(persona: Persona) -> None:
    """The engine takes plain strings so `domain` imports nothing (contract 4). This checks
    the two halves still line up for every persona that exists."""
    scope = compute_scope(persona)
    held = frozenset(c.value for c in scope.capabilities)
    for risk in (Risk.LOW, Risk.MEDIUM, Risk.HIGH):
        ruling = rule(Action(name="x", risk=risk), held)
        assert ruling.reason, "every ruling carries its reason in words"
        assert isinstance(ruling.may_proceed, bool)


def test_no_persona_may_take_a_safety_critical_action() -> None:
    """The end-to-end version of `S1`, across the real capability sets."""
    for persona in Persona:
        held = frozenset(c.value for c in compute_scope(persona).capabilities)
        ruling = rule(Action(name="stop_machine", risk=Risk.SAFETY_CRITICAL), held)
        assert ruling.decision is Decision.REFUSED
