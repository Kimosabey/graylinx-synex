"""The tools themselves — read-only, deterministic, and runnable with the GPU terminated.

Every tool here answers from the domain layer or a service, so the whole set is unit-testable
with MySQL stopped. That is not a convenience: it is what makes the tool loop gateable, since
a tool that needed live infrastructure to *exist* could not be exercised by the gate.

**One tool is registered and permanently refused.** `set_chiller_setpoint` does not work and
never will — `CONTEXT.md` §13 says agents are read-only with respect to hardware control, in
any phase. It is registered rather than omitted because an absent capability proves nothing:
a reader cannot tell "we decided against this" from "nobody thought of it". Registered and
refused, with a test on the refusal, is the difference between a policy and an oversight.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain import cases as case_rules
from app.domain import differential, equipment, faults
from app.services import cases as case_service
from app.tools.registry import REGISTRY, ControlLevel, SideEffect, ToolSpec

# ── parameter models ────────────────────────────────────────────────────────────
# A pydantic model per tool rather than a shared dict. Validation is the gateway's second
# gate, and a shared loose model would make every tool as permissive as the loosest one.


class NoArgs(BaseModel):
    model_config = {"extra": "forbid"}


class FaultLabelArgs(BaseModel):
    model_config = {"extra": "forbid"}

    fault_label: str = Field(description="A fault class label, e.g. CONDENSER_LOW_FLOW")


class EquipmentArgs(BaseModel):
    model_config = {"extra": "forbid"}

    equipment_key: str = Field(description="An equipment key, e.g. chiller_1")


class SetpointArgs(BaseModel):
    model_config = {"extra": "forbid"}

    equipment_key: str
    setpoint_c: float


# ── handlers ────────────────────────────────────────────────────────────────────


async def _list_fault_classes() -> dict[str, Any]:
    """Every label the trained model can emit, with what is settled about each."""
    return {
        "labels": [
            {
                "label": f.label,
                "is_fault": f.is_fault,
                "declares_undecidable": f.declares_undecidable,
                "measured_slots": f.measured_slots,
                "severity": faults.severity_of(f.label).value,
                "severity_is_rated": faults.is_rated(f.label),
            }
            for f in faults.FAULT_CLASSES
        ],
        "undecidable": list(faults.undecidable_labels()),
        "unlabelled_slots": faults.UNLABELLED_SLOTS,
    }


async def _explain_fault_class(fault_label: str) -> dict[str, Any]:
    """What one class is. Returns a stated absence rather than nothing for an unknown label."""
    fault = faults.by_label(fault_label)
    if fault is None:
        return {
            "found": False,
            "reason": (
                f"{fault_label!r} is not a label this plant's model emits. The labels it does "
                f"emit are: {', '.join(faults.all_labels())}."
            ),
        }
    return {
        "found": True,
        "label": fault.label,
        "is_fault": fault.is_fault,
        "declares_undecidable": fault.declares_undecidable,
        "measured_slots": fault.measured_slots,
        "severity": faults.severity_of(fault.label).value,
        "severity_is_rated": faults.is_rated(fault.label),
        "severity_note": "" if faults.is_rated(fault.label) else faults.UNRATED_SEVERITY_TEXT,
        "has_differential": differential.has_differential(fault.label),
        "note": fault.note,
    }


async def _list_equipment() -> dict[str, Any]:
    return {
        "equipment": [
            {"key": e.key, "display_name": getattr(e, "display_name", e.key)}
            for e in equipment.all_equipment()
        ]
    }


async def _checklist_for_fault(fault_label: str) -> dict[str, Any]:
    """`RC2`/`RC3`. Only reviewed items reach a reader; the rest are counted, not shown."""
    checklist = case_service.checklist_for(fault_label)
    return {
        "fault_label": checklist.fault_label,
        "visible": [
            {
                "id": i.id,
                "text": i.text,
                "capability": i.capability.value,
                "blocking": i.blocking,
                "is_sample": i.is_sample,
                "stored_reading": i.stored_reading,
            }
            for i in checklist.visible_items()
        ],
        "unreviewed_count": checklist.unreviewed_count,
        "operator_can_start": case_rules.operator_can_start(checklist),
        "note": (
            "No refrigeration engineer has reviewed the 131-item library. Anything marked "
            "is_sample is illustrative content, not the library."
        ),
    }


async def _differential_availability(fault_label: str) -> dict[str, Any]:
    """`RC12`. Only a class the model itself declares undecidable gets one — constraint 27."""
    fault = faults.by_label(fault_label)
    available = differential.has_differential(fault_label)
    return {
        "fault_label": fault_label,
        "has_differential": available,
        "reason": (
            "this class declares itself undecidable, so narrowing it is honest"
            if available
            else (
                "this class already names a mechanism; narrowing it would invent ambiguity "
                "the model never reported (constraint 27)"
                if fault
                else f"{fault_label!r} is not a label this plant's model emits"
            )
        ),
    }


async def _set_chiller_setpoint(equipment_key: str, setpoint_c: float) -> dict[str, Any]:
    """Never runs. The gateway refuses it before reaching here, and a test asserts that.

    Present as a body rather than `None` so the refusal is proved to come from the gate rather
    than from the handler being missing — those are different guarantees.
    """
    raise AssertionError(
        "set_chiller_setpoint executed. The gateway must refuse it before this line."
    )


# ── registration ────────────────────────────────────────────────────────────────


def register_all(registry=REGISTRY) -> None:
    """Bind every tool. Called once at startup, and by tests against a fresh registry.

    A function rather than import-time side effects: a capability that becomes reachable
    merely because a module was imported is one nobody decided to grant.
    """
    registry.register(
        ToolSpec(
            name="list_fault_classes",
            description=(
                "List every fault class this plant's model can emit, with how many measured "
                "slots carry each, whether the class declares itself undecidable, and whether "
                "its severity has an agreed value."
            ),
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_list_fault_classes,
            skill="look_up",
            tags=("fdd", "reference"),
        )
    )
    registry.register(
        ToolSpec(
            name="explain_fault_class",
            description=(
                "Return what is settled about one fault class: severity and whether it is "
                "rated, whether the class is undecidable, and whether it has a differential."
            ),
            parameters=FaultLabelArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_explain_fault_class,
            skill="explain",
            tags=("fdd",),
        )
    )
    registry.register(
        ToolSpec(
            name="list_equipment",
            description="List the assets this site carries and their keys.",
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_list_equipment,
            skill="look_up",
            tags=("asset",),
        )
    )
    registry.register(
        ToolSpec(
            name="checklist_for_fault",
            description=(
                "The curated checklist for a fault class, filtered to items a refrigeration "
                "engineer has reviewed. Returns the unreviewed count rather than hiding it."
            ),
            parameters=FaultLabelArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_checklist_for_fault,
            skill="resolve",
            tags=("case", "checklist"),
        )
    )
    registry.register(
        ToolSpec(
            name="differential_availability",
            description=(
                "Whether a fault class has a differential, and why. Only a class the model "
                "itself declares undecidable gets one."
            ),
            parameters=FaultLabelArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_differential_availability,
            skill="resolve",
            tags=("case", "differential"),
        )
    )
    registry.register(
        ToolSpec(
            name="set_chiller_setpoint",
            description=(
                "Change a chiller's temperature setpoint. REGISTERED AND PERMANENTLY REFUSED — "
                "no tool issues a control command to plant equipment, in any phase."
            ),
            parameters=SetpointArgs,
            side_effect=SideEffect.CONTROLS_EQUIPMENT,
            control_level=ControlLevel.REFUSED,
            handler=_set_chiller_setpoint,
            skill="",
            tags=("refused",),
        )
    )
