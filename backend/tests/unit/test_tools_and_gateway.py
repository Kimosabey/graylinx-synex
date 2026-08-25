"""`C20` the registry · `G4` the gateway · `G5` idempotency.

The gap these close: until now there were **no tools at all**. `max_react_steps` sat in
config with nothing consuming it, and "the Copilot reaches every capability through the
Control Plane" was a sentence rather than a mechanism.

Every test here runs with MySQL stopped and the GPU terminated, which is the point — a tool
that needed live infrastructure to exist could not be exercised by the gate.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.services.control_plane import Persona, compute_scope
from app.tools.gateway import Gateway, Outcome, idempotency_key
from app.tools.plant_tools import NoArgs, register_all
from app.tools.registry import ControlLevel, SideEffect, ToolRegistry, ToolSpec


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    register_all(r)
    return r


@pytest.fixture
def gateway(registry: ToolRegistry) -> Gateway:
    return Gateway(registry)


@pytest.fixture
def engineer():
    return compute_scope(Persona.RELIABILITY_ENGINEER)


# ── the registry ───────────────────────────────────────────────────────────────

def test_every_registered_tool_has_a_handler(registry: ToolRegistry) -> None:
    """A tool in the list that fails when called is worse than one that is absent."""
    assert registry.declared_but_missing() == ()


def test_a_duplicate_name_is_refused_rather_than_replacing(registry: ToolRegistry) -> None:
    """Silent replacement is how two capabilities share a name and the wrong one answers —
    and the symptom is a correct-looking answer from the wrong source."""
    with pytest.raises(ValueError, match="already registered"):
        register_all(registry)


def test_the_listing_never_exposes_the_handler(registry: ToolRegistry) -> None:
    """A caller that can see the function can call it around the gateway."""
    described = registry.by_name("list_fault_classes").describe()
    assert "handler" not in described
    assert described["parameters"]["type"] == "object"


def test_the_tool_order_is_stable(registry: ToolRegistry) -> None:
    """The list a model is shown must not reorder between turns, or the same question routes
    differently on a second asking."""
    assert [t.name for t in registry.all()] == sorted(t.name for t in registry.all())


def test_a_refused_side_effect_must_declare_a_refused_control_level() -> None:
    """Saying it in one place and not the other lets a reader trust the wrong half."""
    r = ToolRegistry()
    with pytest.raises(ValueError, match="permanently refused"):
        r.register(
            ToolSpec(
                name="rogue",
                description="",
                parameters=NoArgs,
                side_effect=SideEffect.CONTROLS_EQUIPMENT,
                control_level=ControlLevel.AUTOMATIC,
            )
        )


# ── G4 gate 1: the tool must exist ─────────────────────────────────────────────

async def test_an_invented_tool_name_is_a_refusal_not_an_exception(gateway, engineer) -> None:
    """Hallucinated capability is the commonest agent failure and it must be boring."""
    result = await gateway.invoke("summon_a_technician", {}, engineer)
    assert result.outcome is Outcome.UNKNOWN_TOOL
    assert result.is_refusal
    assert not result.ok
    assert "there is no tool called" in result.reason
    assert "list_fault_classes" in result.reason, "a refusal must say what does exist"


# ── G4 gate 2: the arguments must validate ─────────────────────────────────────

async def test_bad_arguments_are_refused_with_the_reason_in_words(gateway, engineer) -> None:
    result = await gateway.invoke("explain_fault_class", {"wrong_name": "x"}, engineer)
    assert result.outcome is Outcome.INVALID_ARGUMENTS
    assert result.is_refusal
    assert "fault_label" in result.reason


async def test_extra_arguments_are_refused(gateway, engineer) -> None:
    """`extra="forbid"` on every model. A tool that tolerates unknown arguments is one the
    model can call with anything, including SQL."""
    result = await gateway.invoke(
        "explain_fault_class",
        {"fault_label": "CONDENSER_LOW_FLOW", "sql": "DROP TABLE"},
        engineer,
    )
    assert result.outcome is Outcome.INVALID_ARGUMENTS


# ── G4 gate 3: no tool controls equipment, in any phase ────────────────────────

@pytest.mark.parametrize("persona", list(Persona))
async def test_no_persona_can_control_equipment(gateway, persona: Persona) -> None:
    """`CONTEXT.md` §13, and it is not a scope question — there is no persona for whom this
    succeeds.

    Parametrised over `list(Persona)` rather than a written-out list, so a persona added
    later is covered the moment it exists. A hand-written list would silently stop being
    exhaustive on the day somebody adds the sixth.
    """
    result = await gateway.invoke(
        "set_chiller_setpoint",
        {"equipment_key": "chiller_1", "setpoint_c": 6.5},
        compute_scope(persona),
    )
    assert result.outcome is Outcome.REFUSED
    assert "in every phase and for every persona" in result.reason


async def test_the_refusal_comes_from_the_gate_not_from_a_missing_handler(
    gateway, engineer
) -> None:
    """The handler exists and raises if reached. That proves the gate stopped it, which is a
    different guarantee from the tool simply being unimplemented."""
    spec = gateway._registry.by_name("set_chiller_setpoint")
    assert spec.is_implemented, "the handler must exist for this test to mean anything"
    result = await gateway.invoke(
        "set_chiller_setpoint", {"equipment_key": "chiller_1", "setpoint_c": 6.5}, engineer
    )
    assert result.outcome is Outcome.REFUSED


# ── G4 gate 4: the Control Plane decides, never the model ──────────────────────

async def test_writing_synex_state_needs_the_approve_capability() -> None:
    """Permission is plain software — the separation law's seventh row."""
    r = ToolRegistry()

    async def _handler() -> str:
        return "written"

    r.register(
        ToolSpec(
            name="close_a_case",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.WRITES_SYNEX_STATE,
            control_level=ControlLevel.NEEDS_APPROVAL,
            handler=_handler,
        )
    )
    gw = Gateway(r)

    refused = await gw.invoke("close_a_case", {}, compute_scope(Persona.TECHNICIAN))
    assert refused.outcome is Outcome.REFUSED
    assert "approve_work" in refused.reason
    assert "not the model" in refused.reason

    allowed = await gw.invoke("close_a_case", {}, compute_scope(Persona.SUPERVISOR))
    assert allowed.ok, "a supervisor holds approve_work"


# ── G5 idempotency ─────────────────────────────────────────────────────────────

def test_argument_order_does_not_change_the_key() -> None:
    """A hash over raw text would let a retry through on dictionary ordering alone."""
    assert idempotency_key("t", {"a": 1, "b": 2}) == idempotency_key("t", {"b": 2, "a": 1})


def test_different_arguments_give_different_keys() -> None:
    assert idempotency_key("t", {"a": 1}) != idempotency_key("t", {"a": 2})


async def test_the_same_call_twice_is_replayed_rather_than_repeated(gateway, engineer) -> None:
    """`G5`: a retry can never create a second work order."""
    first = await gateway.invoke("list_fault_classes", {}, engineer)
    second = await gateway.invoke("list_fault_classes", {}, engineer)

    assert first.ok and second.ok
    assert first.replayed is False
    assert second.replayed is True, "the second call must come from the ledger"
    assert first.idempotency_key == second.idempotency_key
    assert second.value == first.value


async def test_a_replayed_result_says_so(gateway, engineer) -> None:
    """A caller that cannot tell a fresh result from a cached one will rely on the difference."""
    await gateway.invoke("list_equipment", {}, engineer)
    again = await gateway.invoke("list_equipment", {}, engineer)
    assert again.as_dict()["replayed"] is True


def test_the_ledger_reports_that_it_is_not_durable(gateway) -> None:
    """In memory, so idempotency survives a turn and not a restart. Stated rather than
    implied — `langgraph-checkpoint-postgres` is the recorded home for durable state."""
    assert gateway.is_durable is False


# ── a tool failure is a turn outcome, not a crash ──────────────────────────────

async def test_a_raising_tool_returns_failed_rather_than_propagating(engineer) -> None:
    """The router's rule that no layer may raise applies one level down too."""
    r = ToolRegistry()

    async def _boom() -> None:
        raise RuntimeError("the database went away")

    r.register(
        ToolSpec(
            name="boom",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_boom,
        )
    )
    result = await Gateway(r).invoke("boom", {}, engineer)
    assert result.outcome is Outcome.FAILED
    assert result.is_refusal is False, "a break is not a refusal — those are different facts"
    assert "the database went away" in result.reason


async def test_a_declared_tool_with_no_handler_says_so(engineer) -> None:
    r = ToolRegistry()
    r.register(
        ToolSpec(
            name="planned",
            description="",
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
        )
    )
    result = await Gateway(r).invoke("planned", {}, engineer)
    assert result.outcome is Outcome.NOT_IMPLEMENTED
    assert r.declared_but_missing() == ("planned",)


# ── the tools answer honestly ──────────────────────────────────────────────────

async def test_an_unknown_fault_label_gets_a_stated_absence(gateway, engineer) -> None:
    """An absence is not a zero and not a dash. Words, always."""
    result = await gateway.invoke("explain_fault_class", {"fault_label": "MADE_UP"}, engineer)
    assert result.ok
    assert result.value["found"] is False
    assert "is not a label this plant's model emits" in result.value["reason"]


async def test_an_unrated_severity_carries_its_reason(gateway, engineer) -> None:
    """`F17`/`Q49`: only one class has a sourced severity; the rest render as words rather
    than defaulting to a number nobody agreed."""
    result = await gateway.invoke(
        "explain_fault_class", {"fault_label": "HIGH_HEAD_AMBIGUOUS"}, engineer
    )
    assert result.value["severity_is_rated"] is False
    assert result.value["severity_note"], "an unrated severity must say why"


async def test_the_checklist_tool_reports_the_unreviewed_count(gateway, engineer) -> None:
    """The SME hour is a counter rather than a blocker, and the count must reach a caller."""
    result = await gateway.invoke(
        "checklist_for_fault", {"fault_label": "CONDENSER_LOW_FLOW"}, engineer
    )
    assert "unreviewed_count" in result.value
    assert "No refrigeration engineer has reviewed" in result.value["note"]


async def test_a_determinate_class_is_refused_a_differential(gateway, engineer) -> None:
    """Constraint 27: narrowing a class that already names a mechanism would invent
    ambiguity the model never reported."""
    result = await gateway.invoke(
        "differential_availability", {"fault_label": "CONDENSER_LOW_FLOW"}, engineer
    )
    assert result.value["has_differential"] is False
    assert "constraint 27" in result.value["reason"]


class _Unused(BaseModel):
    pass


# ── added 2026-08-17 after adversarial review ─────────────────────────────────

def test_a_catalogue_never_offers_a_tool_that_cannot_run(registry: ToolRegistry) -> None:
    """**The defect this closes: the refused tool was in EVERY catalogue.**

    `set_chiller_setpoint` carries `skill=""` to mean unscoped, and `for_skill` read an empty
    skill as *available to every skill* — so a model was offered equipment control on every
    turn, with `G4` the only thing standing behind it. A gate should be the second line of
    defence, not the first.
    """
    for skill in ("", "look_up", "explain", "resolve", "prepare_work", "verify"):
        names = [t.name for t in registry.for_skill(skill)]
        assert "set_chiller_setpoint" not in names, f"refused tool offered to {skill!r}"


def test_an_unnarrowed_catalogue_is_everything_usable_not_one_refused_tool(
    registry: ToolRegistry,
) -> None:
    """`for_skill("")` used to return exactly one tool — the refused one — so any caller that
    omitted a skill got a catalogue it could never act on. Five tests ran that path and passed,
    because each asserted only within the single-element list."""
    unnarrowed = registry.for_skill("")
    assert len(unnarrowed) > 1
    assert all(not t.is_permanently_refused for t in unnarrowed)


def test_a_refused_tool_stays_declared_even_though_it_is_never_offered(
    registry: ToolRegistry,
) -> None:
    """`C20` must still show that the capability was declared and denied. Removing it from the
    registry entirely would make 'we decided against this' indistinguishable from 'nobody
    thought of it' — which is why it was registered rather than omitted in the first place."""
    assert "set_chiller_setpoint" in [t.name for t in registry.all()]
