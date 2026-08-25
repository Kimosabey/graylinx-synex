"""An unreviewed holding instruction is worse than none — so these nine ship switched off.

**The failure this module prevents, and the cost it accepts.** A holding action is shown while
a case waits for a technician, which makes it an operating instruction given without
supervision: *"keep below 70% load"*, *"stop the machine if any phase climbs further"*. Nobody
is standing there to catch it if it is wrong. Inherited constraint 10 therefore says **no
interim holding action ships unreviewed**, and it names the price openly — a deferred critical
fault then runs with no interim protection at all. That is the accepted cost. The alternative
is telling an operator to hold a pressurised circuit at a load nobody qualified has agreed to.

**Why `sme_reviewed=False` is not enough on its own.** `05-checklist-library-for-review.md`
Part 3 says these are *"drafted and deliberately switched OFF pending this review"*. Two facts
are hiding in that sentence:

| Fact | Field | Who clears it |
|---|---|---|
| No refrigeration engineer has read this instruction | `sme_reviewed` | the review |
| The feature is off as a matter of policy | `switched_on` | a second, deliberate act |

Collapsing them into one flag would mean the review itself switches the feature on — sign off
124 checklist items and nine unsupervised operating instructions go live in the same stroke,
which is precisely the decision constraint 10 says must be taken on purpose. So both gates
must be open, `may_be_shown` requires both, and turning these on is a change somebody has to
write down. The load limits are ours rather than the OEM's, which is the other reason the
second act should not be automatic: the source states plainly *"The load limits are our
numbers, not the OEM's."*

**Switched off means unreachable, not hidden.** `holding_action_for` returns `None`,
`available()` returns an empty tuple, and no accessor in this module will hand back a drafted
action — the only way to read one is `for_review`, whose name says what it is for. A test
asserts that opening one gate is not enough.

**Transcription, not authorship.** All nine rows come verbatim from
`05-checklist-library-for-review.md` Part 3. Not one instruction is reworded, softened,
qualified or completed. The fault names are the ones in that table, and the labels beside them
are the ones the same document prints against those headings in Parts 1 and 2 — a lookup
within one source, not an inference about equipment.

**Two of the eleven classes have no holding action at all.** `INSTRUMENT_FLATLINE` and
`INSTRUMENT_IMPLAUSIBLE_EFFICIENCY` are absent from the table. That absence is recorded rather
than filled: writing an interim instruction for a suspect sensor is exactly the authorship
constraint 26 forbids.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The one document these nine come from, text and fault name alike.
SOURCE = "thermynx/docs/for-vishnu/05-checklist-library-for-review.md"

PART = "Part 3 — Interim holding actions"

#: The source's framing of what a holding action *is*, verbatim. Carried because it is the
#: sentence that makes the review a safety review rather than a wording review.
WHAT_THESE_ARE = (
    "Shown while a case waits for a technician, so they are operating instructions given "
    "without supervision. The load limits are our numbers, not the OEM's."
)

#: The source's own statement of the current switch position, verbatim.
CURRENT_STATE = "drafted and deliberately switched OFF pending this review"


@dataclass(frozen=True)
class HoldingAction:
    """One row of the Part 3 table: a fault, and what we currently tell the operator.

    Not a `ChecklistItem`. A checklist item asks a person to go and find something out; this
    tells a person to change how a running machine is operated, and giving the two the same
    type would let one be rendered by a surface built for the other.
    """

    fault_label: str
    fault_display: str
    """The `Fault` column, verbatim."""

    text: str
    """The `What we currently tell the operator` column, verbatim. Never reworded — a hedge
    added here would be a hedge a refrigeration engineer never wrote."""

    source_file: str = SOURCE
    source_part: str = PART

    sme_reviewed: bool = False
    """No refrigeration engineer has read this instruction. Cleared by the review."""

    switched_on: bool = False
    """The policy gate. `False` for every one of them, and the review does **not** clear it —
    see the module docstring. Constraint 10, and the deferred-fault cost it accepts."""

    @property
    def may_be_shown(self) -> bool:
        """Both gates, because they are two decisions and not one."""
        return self.sme_reviewed and self.switched_on

    @property
    def why_not_shown(self) -> str:
        """What to print instead of the instruction. Words, never silence.

        A case that quietly shows nothing reads as *"there is nothing to do in the meantime"*.
        What is true is that there is something drafted and it is not safe to give yet.
        """
        if self.may_be_shown:
            return ""
        reasons = []
        if not self.sme_reviewed:
            reasons.append("no refrigeration engineer has reviewed it")
        if not self.switched_on:
            reasons.append("the feature is switched off as a matter of policy")
        return (
            f"An interim holding action is drafted for {self.fault_display} and is not being "
            f"shown: {', and '.join(reasons)}. Constraint 10 — an unreviewed holding "
            f"instruction is worse than none, accepting that this fault runs with no interim "
            f"protection until the review happens."
        )


#: The nine rows, in source order. Named `DRAFTED_` because that is what they are: reading
#: this tuple is reading the review pack, not reading what the platform will tell anybody.
DRAFTED_HOLDING_ACTIONS: tuple[HoldingAction, ...] = (
    HoldingAction(
        fault_label="STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
        fault_display="Starved evaporator — undercharge or restriction",
        text=(
            "Keep below 70% load and log discharge pressure hourly until the drier is checked."
        ),
    ),
    HoldingAction(
        fault_label="HIGH_HEAD_AMBIGUOUS",
        fault_display="High head pressure — cause not isolated",
        text="Monitor head pressure each shift; reduce load if it climbs further.",
    ),
    HoldingAction(
        fault_label="REFRIGERANT_SIDE_HIGH_HEAD",
        fault_display="High head — refrigerant side",
        text="Do not top up the charge before the leak check. Log head pressure hourly.",
    ),
    HoldingAction(
        fault_label="COMPRESSOR_INEFFICIENCY",
        fault_display="Compressor inefficiency",
        text="Avoid running below 40% load — surge risk. Listen for noise or vibration.",
    ),
    HoldingAction(
        fault_label="CONDENSER_WATER_SIDE_UNSPECIFIED",
        fault_display="Condenser water side — cause unspecified",
        text="Keep condenser water flow at design; do not throttle. Log approach each shift.",
    ),
    HoldingAction(
        fault_label="POWER_HIGH_UNEXPLAINED",
        fault_display="Power draw high — unexplained",
        text="Log phase currents each shift. Stop the machine if any phase climbs further.",
    ),
    HoldingAction(
        fault_label="CONDENSER_LOW_FLOW",
        fault_display="Condenser low flow",
        text="Reduce load until flow is restored — high head risks a trip.",
    ),
    HoldingAction(
        fault_label="INSTRUMENT_CONTRADICTION",
        fault_display="Contradictory readings — measurement fault",
        text=(
            "Treat all efficiency figures for this unit as invalid until the signal is fixed."
        ),
    ),
    HoldingAction(
        fault_label="MODEL_BLIND",
        fault_display="Fault model cannot diagnose this unit",
        text="Do not rely on fault detection for this unit. Use manual rounds until it recovers.",
    ),
)

#: Classes the transcription covers that the Part 3 table does not. Recorded, never filled.
LABELS_WITH_NO_HOLDING_ACTION: tuple[str, ...] = (
    "INSTRUMENT_FLATLINE",
    "INSTRUMENT_IMPLAUSIBLE_EFFICIENCY",
)

_BY_LABEL: dict[str, HoldingAction] = {a.fault_label: a for a in DRAFTED_HOLDING_ACTIONS}


def available() -> tuple[HoldingAction, ...]:
    """Holding actions that may actually be shown to anybody. Empty, and correctly so."""
    return tuple(a for a in DRAFTED_HOLDING_ACTIONS if a.may_be_shown)


def holding_action_for(fault_label: str) -> HoldingAction | None:
    """The action for a class, **or `None` while it is switched off**.

    `None` here carries two different facts and the caller must not conflate them: either no
    action is drafted for this label at all, or one is drafted and both gates are shut. Ask
    `is_drafted_for` and `why_nothing_is_shown` to tell them apart — a surface that treats
    `None` as *"nothing to say"* reproduces the silence this module exists to avoid.
    """
    action = _BY_LABEL.get(fault_label)
    if action is None or not action.may_be_shown:
        return None
    return action


def is_drafted_for(fault_label: str) -> bool:
    """Does a drafted action exist? A question about the review pack, not about display."""
    return fault_label in _BY_LABEL


def for_review() -> tuple[HoldingAction, ...]:
    """Every drafted action, for the review pack and for nothing else.

    The one accessor that returns switched-off content, and it is named so that a call site
    using it to render a case reads as obviously wrong.
    """
    return DRAFTED_HOLDING_ACTIONS


def why_nothing_is_shown(fault_label: str) -> str:
    """The sentence to print in place of an interim instruction."""
    action = _BY_LABEL.get(fault_label)
    if action is None:
        return (
            f"No interim holding action has been drafted for {fault_label}. It is absent from "
            f"{PART} of the review pack, and writing one here would be authoring a field "
            f"instruction — which inherited constraint 26 forbids."
        )
    return action.why_not_shown


def unreviewed_count() -> int:
    return sum(1 for a in DRAFTED_HOLDING_ACTIONS if not a.sme_reviewed)


def switched_off_count() -> int:
    return sum(1 for a in DRAFTED_HOLDING_ACTIONS if not a.switched_on)
