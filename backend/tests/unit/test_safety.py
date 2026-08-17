"""`S1` the safety-critical action block · `S6` the stop-the-machine response class.

These tests exist because of a hole rather than a bug: the reference taxonomy has no safety
impact class, so on all 43 measured cases the strongest artefact the platform could raise
about a running machine was a work order — scheduled work. `S6` is the route that was
missing, and `S1` is the lookup that decides when it is taken.

The other half of what is guarded here is our own honesty. Six of seven fault classes have no
agreed severity (`Q49`), and safety impact is a further judgement on top of that, so the
shipped mapping is **empty and gated**. These tests keep it empty, keep the mechanism working
against fixtures, and keep *unassessed* from ever quietly reading as *safe*.
"""
from __future__ import annotations

import pytest

from app.domain import faults, safety
from app.domain.authority import Decision, Risk, rule
from app.domain.cases import Capability
from app.domain.safety import ActionEffect, ResponseClass, SafetyImpact
from app.services.control_plane import Persona, compute_scope

#: Every capability the Control Plane can hand out, held together. Used wherever the failure
#: to prevent is *somebody sufficiently senior signed it off*.
EVERYTHING = frozenset(
    {"view_faults", "view_residuals", "open_case", "record_findings",
     "approve_work", "close_work", "edit_policy"}
)

#: Fixture content, and it lives here rather than in the module on purpose. Setting
#: `ehs_reviewed=True` on invented content inside `safety.py` would be claiming a review
#: happened — the same reason `cases.ChecklistItem` carries `is_sample` separately from
#: `sme_reviewed`. The label is deliberately not one of the seven.
REVIEWED_STOP = safety.SafetyCondition(
    fault_label="TEST_ONLY_STOP_HAZARD",
    impact=SafetyImpact.STOP_THE_MACHINE,
    hazard="a fixture hazard, invented for this test and describing no real plant.",
    instruction="Stop the machine at the local panel and leave it stopped.",
    addressed_to=Capability.OPERATOR,
    ehs_reviewed=True,
    source="tests/unit/test_safety.py — a fixture, not the library",
)

REVIEWED_HARMLESS = safety.SafetyCondition(
    fault_label="TEST_ONLY_HARMLESS",
    impact=SafetyImpact.NO_SAFETY_IMPACT,
    hazard="none recorded.",
    instruction="Raise a work order in the ordinary way.",
    addressed_to=Capability.TECHNICIAN,
    ehs_reviewed=True,
    source="tests/unit/test_safety.py — a fixture, not the library",
)

UNREVIEWED_STOP = safety.SafetyCondition(
    fault_label="TEST_ONLY_PROPOSED",
    impact=SafetyImpact.STOP_THE_MACHINE,
    hazard="a fixture hazard nobody has read.",
    instruction="Stop the machine at the local panel and leave it stopped.",
    addressed_to=Capability.OPERATOR,
    source="tests/unit/test_safety.py — a fixture, not the library",
)

FIXTURES = (REVIEWED_STOP, REVIEWED_HARMLESS, UNREVIEWED_STOP)


# ── S1: which actions ──────────────────────────────────────────────────────────

def test_a_command_to_plant_hardware_is_safety_critical_in_every_phase() -> None:
    """`CONTEXT.md` §13: no tool issues a control command to plant equipment, in any phase.

    Held as a lookup so it cannot be argued with per call site — the failure would be a
    later phase quietly deciding that *this* command is fine because the fault looked bad.
    """
    action = safety.classify_action("close_the_chiller", ActionEffect.COMMANDS_PLANT_HARDWARE)
    assert action.risk is Risk.SAFETY_CRITICAL
    assert action.reverses_cleanly is False


def test_no_capability_however_complete_clears_a_hardware_command() -> None:
    """The two halves composed. `S1` names it, `G3` refuses it, and it is tested with every
    capability held because the reading to prevent is that somebody senior enough may sign."""
    action = safety.classify_action("close_the_chiller", ActionEffect.COMMANDS_PLANT_HARDWARE)
    ruling = rule(action, EVERYTHING)
    assert ruling.decision is Decision.REFUSED
    assert ruling.is_refusal
    assert "no approval clears it" in ruling.reason


def test_no_persona_may_command_plant_hardware() -> None:
    """The end-to-end version, across the real capability sets rather than a constructed one."""
    action = safety.classify_action("stage_the_compressor", ActionEffect.COMMANDS_PLANT_HARDWARE)
    for persona in Persona:
        held = frozenset(c.value for c in compute_scope(persona).capabilities)
        assert rule(action, held).decision is Decision.REFUSED


def test_an_action_with_no_declared_effect_stays_unclassified_rather_than_guessed() -> None:
    """Constraint 24's asymmetry, and the visibility half of it. Guessing a level would hide
    the omission behind a ruling that looked deliberate, and the register would stop matching
    the code without anybody noticing."""
    action = safety.classify_action("mystery_action")
    assert action.risk is None

    ruling = rule(action, frozenset({"view_faults"}))
    assert ruling.decision is Decision.UNCLASSIFIED
    assert ruling.risk is Risk.HIGH


def test_reading_a_record_needs_no_approval() -> None:
    """Defaulting to strict must not become defaulting to impossible — a platform that asks
    for a signature before a lookup is one people route around."""
    ruling = rule(safety.classify_action("read_a_band", ActionEffect.READS_A_RECORD), frozenset())
    assert ruling.may_proceed
    assert ruling.required_capability == ""


@pytest.mark.parametrize("effect", list(ActionEffect))
def test_every_effect_that_exists_has_a_risk_and_a_reversibility(effect: ActionEffect) -> None:
    """A new effect added without a row would fall through to the unclassified default, which
    is safe but silent. This makes the omission a red test instead."""
    assert effect in safety.EFFECT_RISK
    action = safety.classify_action("x", effect)
    assert action.risk is safety.EFFECT_RISK[effect]
    assert action.reverses_cleanly is (effect in safety.REVERSIBLE_EFFECTS)


def test_dispatching_a_person_does_not_reverse_cleanly() -> None:
    """A callout cannot be un-made. Constraint 29's shape applied to people rather than to
    candidate causes."""
    action = safety.classify_action("send_a_technician", ActionEffect.DISPATCHES_A_PERSON)
    assert action.reverses_cleanly is False


# ── S1: which fault conditions — and the gate that keeps it empty ──────────────

def test_the_shipped_safety_mapping_is_empty() -> None:
    """The point of the feature, not a gap in it. Deciding which of our seven classes are
    safety-critical would be the platform weighing the risk itself — and it would rest on
    severities that do not exist for six of the seven (`Q49`)."""
    assert safety.SAFETY_CONDITIONS == ()


def test_every_fault_class_reports_itself_unassessed() -> None:
    """All seven, individually, so a future edit that assesses one silently shows up here."""
    for label in faults.fault_labels():
        assessment = safety.assess(label)
        assert assessment.impact is SafetyImpact.NOT_ASSESSED
        assert assessment.is_safety_critical is False
        assert assessment.ehs_reviewed is False
        assert assessment.reason, "every assessment carries its reason in words"


def test_an_unassessed_condition_is_never_read_as_a_safe_one() -> None:
    """Constraint 7 in its safety form: `NULL` means not diagnosed, never healthy. A blind
    window once read as a clean plant, and the same misreading here costs more than a
    misleading dashboard."""
    assessment = safety.assess("CONDENSER_LOW_FLOW")
    assert assessment.impact is not SafetyImpact.NO_SAFETY_IMPACT
    assert assessment.declares_no_safety_impact is False
    assert "never as safe" in assessment.reason


def test_the_unreviewed_count_is_published_as_a_number() -> None:
    """The gap is a counter, not an invisible assumption — the same move that turns the SME
    hour from a blocker into a number on `Checklist.unreviewed_count`."""
    assert safety.reviewed_condition_count() == 0
    assert safety.unreviewed_condition_count() == len(faults.fault_labels()) == 7
    assert set(safety.unreviewed_labels()) == set(faults.fault_labels())
    assert "unknown, not safe" in safety.coverage_note()


def test_an_unreviewed_entry_is_gated_exactly_like_an_unreviewed_checklist_item() -> None:
    """A proposal is not a decision. Unreviewed content that moves people around a running
    machine is the risk constraint 1 names, one step further along than a checklist item."""
    assessment = safety.assess(UNREVIEWED_STOP.fault_label, conditions=FIXTURES)
    assert assessment.impact is SafetyImpact.NOT_ASSESSED
    assert assessment.is_safety_critical is False
    assert assessment.condition is UNREVIEWED_STOP, (
        "the proposal is still carried — hiding it would lose the fact that somebody drafted "
        "one, which is what the review is waiting on"
    )
    assert "no EHS reviewer has read it" in assessment.reason


def test_only_a_reviewed_entry_makes_a_condition_safety_critical() -> None:
    """The mechanism works — it is the content that is missing. Proven against a fixture so
    the module never needs invented content marked as reviewed."""
    assessment = safety.assess(REVIEWED_STOP.fault_label, conditions=FIXTURES)
    assert assessment.impact is SafetyImpact.STOP_THE_MACHINE
    assert assessment.is_safety_critical is True
    assert assessment.ehs_reviewed is True


def test_a_reviewed_no_safety_impact_is_the_only_way_to_say_this_one_is_fine() -> None:
    """Two values, kept apart on purpose. Collapsing `NOT_ASSESSED` into `NO_SAFETY_IMPACT`
    turns silence into reassurance, which is the shape of constraint 8's failure."""
    harmless = safety.assess(REVIEWED_HARMLESS.fault_label, conditions=FIXTURES)
    assert harmless.declares_no_safety_impact is True
    assert harmless.is_safety_critical is False

    silent = safety.assess("HIGH_HEAD_AMBIGUOUS", conditions=FIXTURES)
    assert silent.declares_no_safety_impact is False


def test_no_diagnosis_is_not_an_assessment_of_safety() -> None:
    """`NO_DIAGNOSIS` is the modal outcome at 5,309 slots. It means the gates did not pass —
    nothing was named — and letting that read as *no safety concern* would make the platform's
    commonest honest answer into a reassurance nobody wrote."""
    assessment = safety.assess("NO_DIAGNOSIS")
    assert assessment.impact is SafetyImpact.NOT_ASSESSED
    assert assessment.declares_no_safety_impact is False
    assert "not a finding that the machine is safe" in assessment.reason


def test_an_unknown_label_says_nothing_is_recorded_rather_than_nothing_is_wrong() -> None:
    """A label we have never seen is exactly the case where guessing is worst — the same
    reasoning as `faults.severity_of` returning `UNRATED` instead of raising."""
    assessment = safety.assess("SOMETHING_NOBODY_HAS_SEEN")
    assert assessment.impact is SafetyImpact.NOT_ASSESSED
    assert "not in the taxonomy at all" in assessment.reason


def test_a_reviewed_safety_critical_condition_is_refused_for_everyone() -> None:
    """`S1` end to end: once a condition is ruled dangerous, an action taken about it is
    refused whatever it happens to do — a different kind, not the top of a scale, so no
    capability set clears it."""
    action = safety.classify_action(
        "resume_the_machine",
        ActionEffect.WRITES_A_SYNEX_RECORD,
        fault_label=REVIEWED_STOP.fault_label,
        conditions=FIXTURES,
    )
    assert action.risk is Risk.SAFETY_CRITICAL
    assert rule(action, EVERYTHING).decision is Decision.REFUSED


def test_an_unassessed_fault_does_not_block_the_ordinary_work_of_the_platform() -> None:
    """Defaulting to strict must not become defaulting to impossible. Every class is
    unassessed today, so blocking on absence would stop the product rather than make it
    safer — the honest answer is to proceed and say the assessment is missing."""
    action = safety.classify_action(
        "draft_a_work_order", ActionEffect.WRITES_A_SYNEX_RECORD, fault_label="CONDENSER_LOW_FLOW"
    )
    assert action.risk is Risk.MEDIUM
    assert rule(action, frozenset({"open_case"})).may_proceed


# ── S6: a response class that is not a work order ─────────────────────────────

def test_a_stop_instruction_is_not_a_work_order() -> None:
    """The whole reason `S6` exists. Every escalation route in the reference taxonomy ended
    in a work order, and a work order is scheduled work — the schedule is exactly what a
    hazard does not wait for."""
    decision = safety.respond_to(REVIEWED_STOP.fault_label, "chiller_1", conditions=FIXTURES)
    assert decision.response is ResponseClass.STOP_INSTRUCTION
    assert decision.raises_a_work_order is False
    assert decision.stop_instruction is not None
    assert decision.stop_instruction.is_work_order is False
    assert "not a work order" in decision.stop_instruction.render()


def test_synex_never_stops_the_machine_itself() -> None:
    """`CONTEXT.md` §13: agents are read-only with respect to hardware control, in any phase.
    `S6` raises a human instruction; the person stops the machine."""
    decision = safety.respond_to(REVIEWED_STOP.fault_label, "chiller_1", conditions=FIXTURES)
    instruction = decision.stop_instruction
    assert instruction is not None
    assert instruction.synex_stopped_the_machine is False
    assert "Synex has not stopped the machine and cannot" in instruction.render()


def test_the_instruction_is_the_reviewed_words_and_nothing_composed_them() -> None:
    """Constraint 26 at its strongest. The language model selects and contextualises library
    content; it never authors a field instruction — and a stop order is the most consequential
    field instruction the product can issue."""
    decision = safety.respond_to(REVIEWED_STOP.fault_label, "chiller_1", conditions=FIXTURES)
    instruction = decision.stop_instruction
    assert instruction is not None
    assert instruction.instruction == REVIEWED_STOP.instruction
    assert instruction.hazard == REVIEWED_STOP.hazard


def test_the_stop_instruction_is_addressed_by_a_static_per_condition_lookup() -> None:
    """Constraint 6: routing to a human is a static per-label lookup, never a model judgement.
    The addressee is authored with the review, because who can stop *this* machine is a
    property of the hazard rather than of the org chart."""
    decision = safety.respond_to(REVIEWED_STOP.fault_label, "chiller_1", conditions=FIXTURES)
    instruction = decision.stop_instruction
    assert instruction is not None
    assert instruction.addressed_to is REVIEWED_STOP.addressed_to is Capability.OPERATOR


def test_an_unacknowledged_stop_instruction_says_so_in_words() -> None:
    """Constraint 21 with a person's safety attached: twenty-two detected episodes once sat
    outside the case queue because nothing called the seed. Raised is not received, and no
    deadline for acknowledging one is agreed — so it says that rather than picking a figure."""
    decision = safety.respond_to(REVIEWED_STOP.fault_label, "chiller_1", conditions=FIXTURES)
    instruction = decision.stop_instruction
    assert instruction is not None
    assert instruction.awaiting_acknowledgement is True
    assert "no deadline for acknowledging one is agreed (Q61)" in instruction.acknowledgement_state

    taken = safety.StopInstruction(
        equipment_key="chiller_1",
        fault_label=REVIEWED_STOP.fault_label,
        hazard=REVIEWED_STOP.hazard,
        instruction=REVIEWED_STOP.instruction,
        addressed_to=Capability.OPERATOR,
        acknowledged_by="the duty operator",
    )
    assert taken.awaiting_acknowledgement is False
    assert "Acknowledged by the duty operator" in taken.acknowledgement_state


def test_no_fault_class_can_produce_a_stop_instruction_today() -> None:
    """The honest state of the feature: the route exists and the content does not. If this
    ever fails, somebody has assessed a condition — which is good news, and must be a
    deliberate change to `SAFETY_CONDITIONS` rather than a side effect."""
    for label in faults.fault_labels():
        decision = safety.respond_to(label, "chiller_1")
        assert decision.response is ResponseClass.WORK_ORDER
        assert decision.stop_instruction is None


def test_the_ordinary_route_says_why_it_is_ordinary() -> None:
    """The difference between our empty mapping and the reference taxonomy's missing one. A
    route that cannot be expressed and a route that is empty are different states, and only
    the second can be filled — so the work order states which one it is."""
    decision = safety.respond_to("CONDENSER_LOW_FLOW", "chiller_1")
    assert decision.raises_a_work_order
    assert "not because this condition was found harmless" in decision.reason


def test_a_reviewed_harmless_class_says_a_reviewer_cleared_it() -> None:
    """The other side of the same sentence. Once somebody has actually ruled, the work order
    should stop apologising — otherwise the caveat becomes wallpaper nobody reads."""
    decision = safety.respond_to(REVIEWED_HARMLESS.fault_label, "chiller_1", conditions=FIXTURES)
    assert decision.raises_a_work_order
    assert "an EHS reviewer recorded no safety impact" in decision.reason
    assert "found harmless" not in decision.reason


def test_an_unreviewed_proposal_raises_a_work_order_and_not_a_stop() -> None:
    """The gate holds at the response layer too. A drafted stop instruction nobody has read
    must not reach a person, and it must not silently upgrade the route either."""
    decision = safety.respond_to(UNREVIEWED_STOP.fault_label, "chiller_1", conditions=FIXTURES)
    assert decision.response is ResponseClass.WORK_ORDER
    assert decision.stop_instruction is None


def test_every_decision_serialises_with_its_reason_intact() -> None:
    """An absence is not a zero and not a dash. Anything that renders one of these gets the
    words, so a screen cannot accidentally print a blank where a safety verdict belongs."""
    for label in (*faults.fault_labels(), REVIEWED_STOP.fault_label):
        payload = safety.respond_to(label, "chiller_1", conditions=FIXTURES).as_dict()
        assert payload["reason"]
        assert payload["assessment"]["reason"]
        assert payload["response"] in {"work_order", "stop_instruction"}
