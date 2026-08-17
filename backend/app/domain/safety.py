"""`S1` the safety-critical action block · `S6` the stop-the-machine response class.

**The failure, and it is a hole in the taxonomy rather than a bug in any code.** The reference
fault taxonomy has **no safety impact class at all**: every escalation route ends in a work
order. On the reference queue that meant all 43 measured cases — 13 straight through, 26
waiting on a technician, 2 explained by a broken sensor, 2 by a blind model — could produce
exactly one kind of artefact about a running machine, and that artefact is *scheduled work*.
There was no sentence in the system that meant **stop this machine now**. A fault that needs
one does not become survivable because a job card was the only thing available to raise.

**What this module therefore refuses to do.** Filling that hole by deciding which of our seven
fault classes are safety-critical would be the platform weighing the risk itself, which is the
exact behaviour `S1` exists to prevent. It would also be judgement resting on nothing: six of
the seven classes carry no agreed severity at all — `Q49`, and only `CONDENSER_LOW_FLOW`, 3
slots in the whole measured window, has a sourced value — and safety impact is a further
judgement on top of severity rather than a rename of it. A fault can be low severity and
lethal, or critical and perfectly safe to run out to a planned shutdown.

So `SAFETY_CONDITIONS` **is empty**, in exactly the way the 124-item checklist library is
complete and gated behind `sme_reviewed`. The mechanism is whole and testable; the content is
a review that has not happened. The gap is published as a number —
`unreviewed_condition_count()` returns 7 — rather than hidden behind seven plausible rows.

**An unassessed condition is not a safe one.** Inherited constraint 7 in its safety form:
`NULL` means not diagnosed, never healthy — a blind window once read as a clean plant.
`SafetyImpact.NOT_ASSESSED` and `SafetyImpact.NO_SAFETY_IMPACT` are separate values, and only
the second may ever be read as *this one is fine* — and only when an EHS reviewer put it
there. Every route through this module carries its reason in words for that reason.

**Constraint 6 is what makes both halves lookups.** Routing to a human is a static per-label
lookup, never a model judgement. So a safety-critical condition carries its own hazard, its
own instruction and its own addressee, authored alongside the review — and constraint 26
holds at its strongest here, because a stop order is the most consequential field instruction
the product can issue and nothing in this file composes one.

**`S6` raises a human instruction; it never stops a machine.** `CONTEXT.md` §13: agents are
read-only with respect to hardware control, and no tool issues a control command to plant
equipment, in any phase. A `StopInstruction` is therefore addressed to a person, records that
Synex did not act on the plant, and is deliberately **not** a work order — a work order is
scheduled work, and the schedule is precisely what a hazard does not wait for.

**Nothing here calls a model.** `S1` is `SW` and `S6` is `R` in the register.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from app.domain import faults
from app.domain.authority import Action, Risk
from app.domain.cases import Capability

# ── S1, first half: which actions ───────────────────────────────────────────────
# A static table, not a chain of comparisons. `G2` classifies what is about to happen; this
# says where that classification comes from, so risk is read off a declared side effect
# rather than inferred from how the sentence was phrased.


class ActionEffect(StrEnum):
    """What an action actually does. Five, and the last two are why `S1` exists."""

    READS_A_RECORD = "reads_a_record"
    """Looks something up. Nothing changes and nobody is called."""

    WRITES_A_SYNEX_RECORD = "writes_a_synex_record"
    """Changes something inside Synex that a human can undo — a draft, a note, a proposal."""

    DISPATCHES_A_PERSON = "dispatches_a_person"
    """Sends somebody to a machine, or closes a job. A callout cannot be un-made."""

    COMMANDS_PLANT_HARDWARE = "commands_plant_hardware"
    """Touches whether a machine keeps running. **Never available, in any phase.**
    `CONTEXT.md` §13, and the reason this maps to a risk no approval clears rather than to a
    high one somebody senior could sign."""

    CHANGES_THE_RULES = "changes_the_rules"
    """Edits scope, the approval matrix or the policy version. `G8` policy simulation is
    Phase 3, so a rule change happens deliberately and outside the agent."""


#: `S1`'s action half, as data. `COMMANDS_PLANT_HARDWARE` maps to `SAFETY_CRITICAL` because
#: `CONTEXT.md` §13 settles it — that is a quoted constraint, not a risk this module weighed.
EFFECT_RISK: dict[ActionEffect, Risk] = {
    ActionEffect.READS_A_RECORD: Risk.LOW,
    ActionEffect.WRITES_A_SYNEX_RECORD: Risk.MEDIUM,
    ActionEffect.DISPATCHES_A_PERSON: Risk.HIGH,
    ActionEffect.COMMANDS_PLANT_HARDWARE: Risk.SAFETY_CRITICAL,
    ActionEffect.CHANGES_THE_RULES: Risk.SYSTEM_CRITICAL,
}

#: Which effects a human can undo. Held as a set rather than computed from the risk level,
#: because reversibility is a property of the effect and risk is a judgement about it —
#: deriving one from the other would make constraint 29 depend on a table somebody may retune.
REVERSIBLE_EFFECTS: frozenset[ActionEffect] = frozenset(
    {ActionEffect.READS_A_RECORD, ActionEffect.WRITES_A_SYNEX_RECORD}
)


# ── S1, second half: which fault conditions ─────────────────────────────────────


class SafetyImpact(StrEnum):
    """What a reviewed condition was recorded as. Four, and two of them are not a scale.

    The first two are taken from `Risk.SAFETY_CRITICAL`'s own definition — *touches whether a
    machine keeps running, or whether somebody approaches one* — rather than invented here.
    """

    STOP_THE_MACHINE = "stop_the_machine"
    """Answered by stopping the machine now. `S6`'s route, and not a work order."""

    KEEP_PEOPLE_AWAY = "keep_people_away"
    """The machine may run; nobody may approach it until somebody competent says otherwise."""

    NO_SAFETY_IMPACT = "no_safety_impact"
    """**The only value that means *this one is fine*** — and only with `ehs_reviewed` set.
    Kept distinct from `NOT_ASSESSED` because collapsing them turns silence into reassurance."""

    NOT_ASSESSED = "not_assessed"
    """Nobody has judged this condition. The current answer for all seven fault classes.

    Constraint 7 in its safety form: this is *unknown*, never *safe*. An empty queue on a
    blind window once read as a clean plant, and the same misreading here costs more.
    """


#: The impacts that make a condition safety-critical. A frozenset rather than an ordering,
#: because "keep people away" is not a lesser "stop the machine" — they are different
#: hazards with different instructions, and ranking them would rebuild a ladder.
SAFETY_CRITICAL_IMPACTS: frozenset[SafetyImpact] = frozenset(
    {SafetyImpact.STOP_THE_MACHINE, SafetyImpact.KEEP_PEOPLE_AWAY}
)

#: Rendered wherever an unassessed condition would otherwise print. Words, never a blank and
#: never a reassuring default — the sibling of `faults.UNRATED_SEVERITY_TEXT`.
NOT_ASSESSED_TEXT: str = "no safety impact has been assessed for this fault class (Q60)"


@dataclass(frozen=True)
class SafetyCondition:
    """One fault condition and its recorded safety impact — curated content, never derived.

    Constraint 6: routing to a human is a static per-label lookup. So the hazard, the words
    the person is given and the capability they are given to are all authored *with* the
    review and read back verbatim. Nothing composes them at runtime, which is constraint 26
    at its strongest: a stop order is the most consequential field instruction there is.
    """

    fault_label: str
    impact: SafetyImpact
    hazard: str
    """Why this is dangerous, in the reviewer's words. Printed to whoever is standing there."""

    instruction: str
    """What the person is to do, verbatim. Never generated, never paraphrased."""

    addressed_to: Capability
    """Who it goes to. A capability, not a rank — constraint 13. Authored per condition
    rather than looked up from a role table, because who can stop *this* machine is a
    property of the hazard rather than of the org chart."""

    ehs_reviewed: bool = False
    """**Defaults to False.** An unreviewed instruction that moves people around a running
    machine is the risk constraint 1 names, one step further along than a checklist item."""

    source: str = ""
    """Where the judgement came from. An entry with no source is not a reviewed entry."""


#: **Empty, deliberately — and this is the feature rather than a gap in it.**
#:
#: Seven fault classes exist and not one of them has a recorded safety impact. Filling this
#: tuple from our own reading of the fault names would be the platform weighing the risk
#: itself, which is what `S1` refuses; it would also rest on severities that do not exist
#: (`Q49`). The mechanism above is complete, the tests below exercise it against fixtures,
#: and `unreviewed_condition_count()` publishes the shortfall as a number so the review is a
#: counter rather than an invisible assumption. `Q60`.
SAFETY_CONDITIONS: tuple[SafetyCondition, ...] = ()


@dataclass(frozen=True)
class SafetyAssessment:
    """What is recorded about one fault class, and why — always in words."""

    fault_label: str
    impact: SafetyImpact
    reason: str
    ehs_reviewed: bool = False
    condition: SafetyCondition | None = None

    @property
    def is_safety_critical(self) -> bool:
        """True only for a **reviewed** entry recording a safety-critical impact.

        An unreviewed proposal does not block, and an unassessed class does not block, because
        defaulting to strict must not become defaulting to impossible — every class is
        unassessed today, so blocking on absence would stop the product entirely rather than
        make it safer.
        """
        return self.ehs_reviewed and self.impact in SAFETY_CRITICAL_IMPACTS

    @property
    def declares_no_safety_impact(self) -> bool:
        """The only way to read *this one is fine*. `NOT_ASSESSED` can never satisfy it."""
        return self.ehs_reviewed and self.impact is SafetyImpact.NO_SAFETY_IMPACT

    def as_dict(self) -> dict:
        return {
            "fault_label": self.fault_label,
            "impact": self.impact.value,
            "reason": self.reason,
            "ehs_reviewed": self.ehs_reviewed,
            "is_safety_critical": self.is_safety_critical,
            "declares_no_safety_impact": self.declares_no_safety_impact,
        }


def _index(conditions: tuple[SafetyCondition, ...]) -> dict[str, SafetyCondition]:
    """Index by fault label, and **refuse a duplicate rather than letting the last one win.**

    Found in adversarial review, 2026-08-17. This was a plain dict comprehension, so two
    entries for one fault class silently kept the second — which meant an EHS-reviewed *stop
    the machine* instruction could be overwritten by a later unreviewed row and quietly
    downgrade to a work order. Nobody would see it happen: both rows are valid, the lookup
    succeeds, and the answer is wrong in the one direction that costs a person.

    Raising is right here where it would be wrong elsewhere. The registry is authored content
    loaded at import, not user input, so a duplicate is a defect in the file rather than a
    condition to degrade around — and failing at import is the earliest possible place to
    find it.
    """
    index: dict[str, SafetyCondition] = {}
    for condition in conditions:
        existing = index.get(condition.fault_label)
        if existing is not None:
            raise ValueError(
                f"two safety conditions are registered for {condition.fault_label!r}. The "
                f"first is {'EHS-reviewed' if existing.ehs_reviewed else 'unreviewed'} and "
                f"the second is "
                f"{'EHS-reviewed' if condition.ehs_reviewed else 'unreviewed'}; keeping "
                f"either silently could downgrade a reviewed stop instruction to a work "
                f"order. Resolve it in the registry."
            )
        index[condition.fault_label] = condition
    return index


def assess(
    fault_label: str, *, conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS
) -> SafetyAssessment:
    """`S1`. What is recorded about this fault class — a lookup, never a judgement.

    `conditions` is a parameter so the mechanism is testable against fixtures without any
    invented content acquiring `ehs_reviewed=True` inside the module. That is the same
    separation `cases.ChecklistItem.is_sample` makes for the checklist library: sample content
    may be visible, but it must never be able to claim somebody reviewed it.
    """
    condition = _index(conditions).get(fault_label)

    if condition is None:
        known = faults.by_label(fault_label)
        if known is None:
            detail = (
                "this label is not in the taxonomy at all, so nothing is recorded about it "
                "in either direction"
            )
        elif not known.is_fault:
            detail = (
                f"{fault_label} is an outcome rather than a fault, so no condition was named "
                f"to assess — which is emphatically not a finding that the machine is safe"
            )
        else:
            detail = "no EHS review has assigned this fault class a safety impact"
        return SafetyAssessment(
            fault_label=fault_label,
            impact=SafetyImpact.NOT_ASSESSED,
            reason=(
                f"{NOT_ASSESSED_TEXT}: {detail}. Read this as unknown and never as safe — an "
                f"unassessed condition is constraint 7 wearing safety colours."
            ),
        )

    if not condition.ehs_reviewed:
        return SafetyAssessment(
            fault_label=fault_label,
            impact=SafetyImpact.NOT_ASSESSED,
            reason=(
                f"an entry proposing '{condition.impact.value}' exists for {fault_label} and "
                f"no EHS reviewer has read it. Unreviewed content that moves people around a "
                f"running machine does not reach anybody — the gate the checklist library "
                f"sits behind, one step further along."
            ),
            condition=condition,
        )

    return SafetyAssessment(
        fault_label=fault_label,
        impact=condition.impact,
        reason=(
            f"{fault_label} is recorded as '{condition.impact.value}' and an EHS reviewer has "
            f"signed it. Source: {condition.source or 'not stated, which is itself a defect'}."
        ),
        ehs_reviewed=True,
        condition=condition,
    )


def reviewed_labels(
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> tuple[str, ...]:
    """The fault classes an EHS reviewer has actually ruled on. Empty today."""
    reviewed = {c.fault_label for c in conditions if c.ehs_reviewed}
    return tuple(label for label in faults.fault_labels() if label in reviewed)


def unreviewed_labels(
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> tuple[str, ...]:
    """The fault classes with no reviewed safety impact. All seven today."""
    reviewed = set(reviewed_labels(conditions))
    return tuple(label for label in faults.fault_labels() if label not in reviewed)


def reviewed_condition_count(
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> int:
    return len(reviewed_labels(conditions))


def unreviewed_condition_count(
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> int:
    """The shortfall, as a number a screen can print. **7 today, out of 7.**

    Published rather than absorbed, for the reason `Checklist.unreviewed_count` exists: it
    turns the review from a blocker into a counter, and a counter that stops moving is
    visible in a way an assumption is not.
    """
    return len(unreviewed_labels(conditions))


def coverage_note(
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> str:
    """The state of the review, in words, for anything that renders it."""
    total = len(faults.fault_labels())
    reviewed = reviewed_condition_count(conditions)
    if reviewed == total:
        return f"all {total} fault classes carry an EHS-reviewed safety impact."
    return (
        f"{reviewed} of {total} fault classes carry an EHS-reviewed safety impact; "
        f"{total - reviewed} carry none. Those {total - reviewed} are unknown, not safe — "
        f"nothing here has found them harmless. Q60."
    )


def classify_action(
    name: str,
    effect: ActionEffect | None = None,
    *,
    target: str = "",
    fault_label: str = "",
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> Action:
    """`S1`. Build the `G2` action from two static lookups and no judgement at all.

    A reviewed safety-critical condition wins outright rather than being ranked against the
    effect. Comparing the two would need an ordering over `Risk`, and an ordering is the
    ladder `SAFETY_CRITICAL` is deliberately not part of — *a different kind, not the top of
    a scale*. An action taken about a condition somebody has ruled dangerous is refused
    whatever it happens to do.

    An unrecognised effect yields `risk=None` on purpose, so `G2` defaults it to `HIGH` and
    `G3` reports it as `UNCLASSIFIED`. Guessing a level here would hide the omission behind a
    ruling that looked deliberate.
    """
    if fault_label and assess(fault_label, conditions=conditions).is_safety_critical:
        return Action(
            name=name,
            risk=Risk.SAFETY_CRITICAL,
            target=target or fault_label,
            reverses_cleanly=False,
        )
    if effect is None:
        return Action(name=name, risk=None, target=target)
    return Action(
        name=name,
        risk=EFFECT_RISK[effect],
        target=target,
        reverses_cleanly=effect in REVERSIBLE_EFFECTS,
    )


# ── S6: the response class that is not a work order ─────────────────────────────


class ResponseClass(StrEnum):
    """How a fault is answered. Two, and the second is the one the taxonomy never had."""

    WORK_ORDER = "work_order"
    """The ordinary route: a case, and a job if one is justified. Scheduled work."""

    STOP_INSTRUCTION = "stop_instruction"
    """`S6`. Answered now, by a person, at the machine. **Not a work order** — putting a
    hazard on a schedule is the failure this class exists to end."""


#: How long a stop instruction may sit unacknowledged before somebody else is called.
#:
#: TBD (Q61). **No document states one**, so none is set. A plausible-looking figure here
#: would be a number invented in the one place where being wrong means nobody came, and the
#: honest alternative — saying in words that no deadline is agreed — costs nothing and is
#: what `StopInstruction.acknowledgement_state` does. Constraint 21 is the reason the field
#: exists at all: a detector that fires into nowhere is worse than no detector, and an
#: instruction nobody acknowledged is exactly that with a person's safety attached.
ACKNOWLEDGEMENT_DEADLINE: timedelta | None = None


@dataclass(frozen=True)
class StopInstruction:
    """`S6`'s artefact. A sentence for a person — not a job, and not a control command."""

    equipment_key: str
    fault_label: str
    hazard: str
    instruction: str
    addressed_to: Capability

    acknowledged_by: str = ""
    """Empty until somebody takes it. Constraint 21: raised is not received."""

    #: Always `False`. Held as fields rather than as constants so they survive into any
    #: rendering and any serialisation, where a reader can see them stated — the same reason
    #: `GroupProposal.requires_confirmation` is a field. `CONTEXT.md` §13: no tool issues a
    #: control command to plant equipment, in any phase, so the second one can never be True.
    is_work_order: bool = False
    synex_stopped_the_machine: bool = False

    @property
    def awaiting_acknowledgement(self) -> bool:
        return not self.acknowledged_by

    @property
    def acknowledgement_state(self) -> str:
        """The reason in words, never a bare bool and never a dash."""
        if self.acknowledged_by:
            return f"Acknowledged by {self.acknowledged_by}."
        if ACKNOWLEDGEMENT_DEADLINE:
            return (
                f"Nobody has acknowledged this yet, and it is due to be picked up within "
                f"{ACKNOWLEDGEMENT_DEADLINE}."
            )
        return (
            "Nobody has acknowledged this yet, and no deadline for acknowledging one is "
            "agreed (Q61). Until somebody does, it has been raised and not received."
        )

    def render(self) -> str:
        return (
            f"Stop {self.equipment_key} now — {self.hazard} {self.instruction} "
            f"This is for {self.addressed_to.value} to carry out. Synex has not stopped the "
            f"machine and cannot: it raises the instruction and a person acts on it. This is "
            f"not a work order. {self.acknowledgement_state}"
        )

    def as_dict(self) -> dict:
        return {
            "equipment_key": self.equipment_key,
            "fault_label": self.fault_label,
            "hazard": self.hazard,
            "instruction": self.instruction,
            "addressed_to": self.addressed_to.value,
            "acknowledged_by": self.acknowledged_by,
            "awaiting_acknowledgement": self.awaiting_acknowledgement,
            "acknowledgement_state": self.acknowledgement_state,
            "is_work_order": self.is_work_order,
            "synex_stopped_the_machine": self.synex_stopped_the_machine,
        }


@dataclass(frozen=True)
class ResponseDecision:
    """Which response class a fault gets, and the assessment that decided it."""

    fault_label: str
    response: ResponseClass
    reason: str
    assessment: SafetyAssessment
    stop_instruction: StopInstruction | None = None

    @property
    def raises_a_work_order(self) -> bool:
        return self.response is ResponseClass.WORK_ORDER

    @property
    def is_stop_instruction(self) -> bool:
        return self.response is ResponseClass.STOP_INSTRUCTION

    def as_dict(self) -> dict:
        return {
            "fault_label": self.fault_label,
            "response": self.response.value,
            "reason": self.reason,
            "assessment": self.assessment.as_dict(),
            "stop_instruction": (
                self.stop_instruction.as_dict() if self.stop_instruction else None
            ),
        }


def respond_to(
    fault_label: str,
    equipment_key: str,
    *,
    conditions: tuple[SafetyCondition, ...] = SAFETY_CONDITIONS,
) -> ResponseDecision:
    """`S6`. Which response class this fault gets — read off `S1`'s lookup, decided by nobody.

    Today every call returns `WORK_ORDER`, because `SAFETY_CONDITIONS` is empty. That is not
    the reference taxonomy's failure repeated: the difference is that the ordinary route now
    **says why it is ordinary**, and the alternative exists and is reachable the moment a
    reviewed entry is added. A route that cannot be expressed and a route that is empty are
    different states, and only the second one can be filled.
    """
    assessment = assess(fault_label, conditions=conditions)
    condition = assessment.condition

    if assessment.is_safety_critical and condition is not None:
        return ResponseDecision(
            fault_label=fault_label,
            response=ResponseClass.STOP_INSTRUCTION,
            reason=(
                f"{fault_label} is reviewed as '{condition.impact.value}', so it is answered "
                f"now rather than scheduled. A work order is scheduled work, and the schedule "
                f"is what this hazard does not wait for. Synex raises the instruction; a "
                f"person carries it out."
            ),
            assessment=assessment,
            stop_instruction=StopInstruction(
                equipment_key=equipment_key,
                fault_label=fault_label,
                hazard=condition.hazard,
                instruction=condition.instruction,
                addressed_to=condition.addressed_to,
            ),
        )

    if assessment.declares_no_safety_impact:
        why = "an EHS reviewer recorded no safety impact for this class."
    else:
        why = (
            "The route is ordinary because no reviewed entry says otherwise, not because "
            "this condition was found harmless."
        )
    return ResponseDecision(
        fault_label=fault_label,
        response=ResponseClass.WORK_ORDER,
        reason=(
            f"{fault_label} takes the ordinary route on {equipment_key}: a case, and a work "
            f"order if one is justified. {why} {assessment.reason}"
        ),
        assessment=assessment,
    )
