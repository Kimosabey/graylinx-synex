"""Part 1 of the review pack — the trained model's seven fault classes, transcribed.

**The failure this module prevents.** The 124-item library exists only as prose in a review
pack, which means the product either ships without it or somebody writes a plausible
replacement. The second is the dangerous one: a generated instruction reads exactly like a
curated one, so an item that would kill a compressor arrives with the same authority as one
that would save it. Inherited constraint 1 makes the library curated content, never model
output; constraint 26 lets the language model select and contextualise it and nothing more.
This module is therefore a **transcription** — 86 human-written items copied verbatim, wording
untouched, and every gap in the source left as a gap.

**Nothing here is reviewed, and every item says so.** `sme_reviewed=False` on all 86, so
`Checklist.visible_items` returns nothing and not one of these instructions reaches a user.
That is the intended state: the SME hour is the last gate before a technician sees any of it,
and until it happens the honest output is a counter rather than a checklist.

**`is_sample=False`, and the distinction is load-bearing.** `app/services/cases.py` carries
short invented items flagged `is_sample=True` so a case screen can demonstrate the mechanism
while the real library is hidden. This is the opposite object. Marking it `is_sample` would
claim it was invented to demonstrate something; marking it `sme_reviewed` would claim a review
that has not happened. Both flags stay off, and the two facts stay separate.

**Order is preserved exactly, because it is the author's judgement.** Constraint 39: the next
question is the one that could move the most live candidates. The source's numbering is what
the author believes about that, so `position` carries the source's own number and the item id
is built from it. Renumbering, sorting or tidying would overwrite an engineering opinion with
an accident.

**`[SETTLES IT]` is carried as a field, never dropped.** It marks the check the pack believes
discriminates between the candidate causes, and `06-differentials-for-review.md` states what
each answer eliminates. Those are the items the pack asks a reviewer to challenge hardest, so
losing the marker would leave them indistinguishable from the routine checks.

**Role tags come from a second file and are recorded against it.** The instruction text was
written in `05`; the capability that may perform it was written in `17`. They are separately
challengeable, so each item names both files. An item the role file does not tag falls to
constraint 24's technician default and sets `capability_defaulted` — the asymmetry is
deliberate, because mis-tagging a technician task as operator work puts an unqualified person
on a pressurised circuit while the reverse merely wastes a callout.

**Severity is transcribed as the source's word, not mapped onto ours.** The pack states
`high`, `critical` and `warning` per class. `app/domain/faults.py` records six of the seven as
`UNRATED` against `Q49`, and `warning` is not a value on that scale at all. Choosing between
the two would be a judgement about severity wearing a transcription's clothes, so
`stated_severity` holds the source's word and the reconciliation is a question for a human.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.cases import (
    DEFAULT_CAPABILITY,
    Capability,
    Checklist,
    ChecklistItem,
    Stage,
)

#: Where the instruction text was copied from, verbatim.
CHECKLIST_SOURCE = "thermynx/docs/for-vishnu/05-checklist-library-for-review.md"

#: Where the capability tag on each item was copied from. A separate document, separately
#: challengeable — one review pass over these tags has ever been run, on one class.
ROLE_TAG_SOURCE = "thermynx/docs/for-vishnu/17-role-tags-every-check.md"

#: Where a `[SETTLES IT]` marker's consequences are written down: which cause each answer
#: eliminates. Named here so the marker points somewhere rather than being decoration.
DIFFERENTIAL_SOURCE = "thermynx/docs/for-vishnu/06-differentials-for-review.md"

#: The marker as the source writes it. Held as a constant so a reader can grep the pack for it.
SETTLES_IT_MARKER = "[SETTLES IT]"

#: The source's own words for a class the trained model cannot resolve. Four of the seven
#: carry it, and they are the four with a differential — constraint 27.
NEEDS_A_HUMAN = "needs a human — the model says it cannot resolve this one"

#: The source's own words for the other three.
FLOWS_STRAIGHT_THROUGH = "flows straight through"


@dataclass(frozen=True)
class CuratedItem:
    """One transcribed instruction, and everything the source says about it.

    Deliberately *not* a `ChecklistItem`: it carries provenance, the `[SETTLES IT]` marker and
    the italic rationale, none of which the domain model has a field for. `to_checklist_item`
    is the one-way door into the domain, and it sets both honesty flags explicitly rather than
    inheriting a default that some later edit could widen.
    """

    id: str
    text: str
    """Verbatim from `source_file`. Never reworded, corrected or expanded."""

    stage: Stage
    position: int
    """The source's own number within its stage. Order is load-bearing — constraint 39."""

    source_heading: str
    """The fault-class heading the item sits under, as the source writes it."""

    capability: Capability = DEFAULT_CAPABILITY
    capability_defaulted: bool = False
    """`True` when `ROLE_TAG_SOURCE` gives no tag and constraint 24's default applied. A
    defaulted tag is a recorded absence, never a guess."""

    blocking: bool = False
    """From the **BLOCKING** column of `ROLE_TAG_SOURCE`: the case cannot be root-caused until
    a human answers this check."""

    settles_it: bool = False
    """From the `[SETTLES IT]` marker in `CHECKLIST_SOURCE`. The pack believes this check
    discriminates between the candidate causes; `DIFFERENTIAL_SOURCE` says what each answer
    eliminates. Unreviewed, like everything else here."""

    rationale: str | None = None
    """The italic line under a check, where the source has one. `None` where it does not —
    an absent rationale is left absent rather than composed."""

    source_file: str = CHECKLIST_SOURCE
    capability_source_file: str = ROLE_TAG_SOURCE

    def to_checklist_item(self) -> ChecklistItem:
        """The domain object, with both honesty flags stated rather than defaulted."""
        return ChecklistItem(
            id=self.id,
            text=self.text,
            capability=self.capability,
            blocking=self.blocking,
            sme_reviewed=False,
            is_sample=False,
            stored_reading=None,
            stage=self.stage,
        )


@dataclass(frozen=True)
class CuratedClass:
    """One fault class as the review pack presents it: the heading, what it says about the
    class, and its items in source order across the three stages."""

    label: str
    heading: str
    """The class's heading in `CHECKLIST_SOURCE`, verbatim."""

    stated_severity: str
    """The source's word — `high`, `critical` or `warning`. Not mapped onto `faults.Severity`;
    see the module docstring for why that mapping is a human's call."""

    routing_note: str
    """`NEEDS_A_HUMAN` or `FLOWS_STRAIGHT_THROUGH`, in the source's words."""

    needs_human: bool
    """Does the source say the model needs a human for this class?"""

    items: tuple[CuratedItem, ...]

    def at_stage(self, stage: Stage) -> tuple[CuratedItem, ...]:
        return tuple(i for i in self.items if i.stage is stage)

    @property
    def settles_it_items(self) -> tuple[CuratedItem, ...]:
        return tuple(i for i in self.items if i.settles_it)

    @property
    def blocking_items(self) -> tuple[CuratedItem, ...]:
        return tuple(i for i in self.items if i.blocking)

    def for_capability(self, capability: Capability) -> tuple[CuratedItem, ...]:
        """Transcribed items this capability may perform.

        Reads the transcription rather than `Checklist.for_capability`, which filters through
        `visible_items` and therefore returns nothing while the library is unreviewed. The
        constraint-37 property — every class leaves the operator something to do — is a fact
        about the *content*, and has to be checkable before the review gate opens.
        """
        return tuple(i for i in self.items if i.capability is capability)

    def checklist(self) -> Checklist:
        """The domain `Checklist`. Every item unreviewed, so `visible_items` is empty."""
        return Checklist(
            fault_label=self.label,
            items=tuple(i.to_checklist_item() for i in self.items),
        )


@dataclass(frozen=True)
class _Row:
    """One line of the source, before it is given an id and a stage.

    `capability=None` means `ROLE_TAG_SOURCE` tags it with nothing — which does not happen
    anywhere in Part 1, and the path exists so that a future part without tags defaults
    rather than invites a guess.
    """

    text: str
    capability: Capability | None
    blocking: bool = False
    settles_it: bool = False
    rationale: str | None = None


def _curated_class(
    *,
    label: str,
    heading: str,
    stated_severity: str,
    routing_note: str,
    checks: tuple[_Row, ...],
    corrective: tuple[_Row, ...],
    preventive: tuple[_Row, ...],
) -> CuratedClass:
    """Stamp a class's rows with stage, source position and provenance.

    Ids are built from the source position — `LABEL:rca:2` is item 2 under *Checks to run* —
    so a reordering shows up as an id change rather than passing silently.
    """
    items: list[CuratedItem] = []
    for stage, rows in (
        (Stage.RCA, checks),
        (Stage.CORRECTIVE, corrective),
        (Stage.PREVENTIVE, preventive),
    ):
        for position, row in enumerate(rows, start=1):
            items.append(
                CuratedItem(
                    id=f"{label}:{stage.value}:{position}",
                    text=row.text,
                    stage=stage,
                    position=position,
                    source_heading=heading,
                    capability=(
                        DEFAULT_CAPABILITY if row.capability is None else row.capability
                    ),
                    capability_defaulted=row.capability is None,
                    blocking=row.blocking,
                    settles_it=row.settles_it,
                    rationale=row.rationale,
                )
            )
    return CuratedClass(
        label=label,
        heading=heading,
        stated_severity=stated_severity,
        routing_note=routing_note,
        needs_human=routing_note == NEEDS_A_HUMAN,
        items=tuple(items),
    )


# ── 1. Starved evaporator — undercharge or restriction ──────────────────────────
# Three of six checks are marked [SETTLES IT], and the pack's own preamble says the marked
# item is "the one we ask first" — singular. The plural marking is transcribed as it stands.

STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION = _curated_class(
    label="STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION",
    heading="Starved evaporator — undercharge or restriction",
    stated_severity="high",
    routing_note=NEEDS_A_HUMAN,
    checks=(
        _Row(
            "Sight glass at full load — bubbles or flashing?",
            Capability.OPERATOR,
            blocking=True,
            settles_it=True,
            rationale="Clear glass with adequate subcooling argues against undercharge.",
        ),
        _Row(
            "Temperature drop across the filter-drier (inlet vs outlet)",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
            rationale=(
                "A measurable cold spot across the drier means a restriction, not low "
                "charge. This is the single test that separates the two causes."
            ),
        ),
        _Row(
            "Measured superheat at the TXV vs setpoint",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
        ),
        _Row("Subcooling at the condenser outlet", Capability.TECHNICIAN),
        _Row(
            "Any refrigerant service or charge adjustment on this circuit recently?",
            Capability.SUPERVISOR,
            rationale=(
                "Recent service points toward charge; a long-untouched circuit points "
                "toward a restriction."
            ),
        ),
        _Row(
            "Evaporator water flow and entering/leaving temperatures vs design",
            Capability.OPERATOR,
        ),
    ),
    corrective=(
        _Row(
            "If restricted: isolate, recover, replace the filter-drier, evacuate and "
            "recharge to spec",
            Capability.TECHNICIAN,
        ),
        _Row(
            "If undercharged: leak-test the circuit, repair, then weigh in charge to "
            "nameplate",
            Capability.TECHNICIAN,
        ),
        _Row("Verify superheat and subcooling after the fix", Capability.TECHNICIAN),
        _Row(
            "Re-check the suction-pressure residual on the next run to confirm the fault "
            "cleared",
            Capability.TECHNICIAN,
        ),
    ),
    preventive=(
        _Row(
            "Set a filter-drier replacement interval for this circuit",
            Capability.SUPERVISOR,
        ),
        _Row("Add filter-drier ΔT to the chiller PM round", Capability.SUPERVISOR),
        _Row(
            "Check the moisture indicator each PM; investigate any ingress source",
            Capability.TECHNICIAN,
        ),
    ),
)


# ── 2. High head — refrigerant side ─────────────────────────────────────────────
# No [SETTLES IT] marker and no blocking item anywhere in this class. Transcribed as it
# stands; what that means for a case that concludes here is Q37, and not this module's call.

REFRIGERANT_SIDE_HIGH_HEAD = _curated_class(
    label="REFRIGERANT_SIDE_HIGH_HEAD",
    heading="High head — refrigerant side",
    stated_severity="high",
    routing_note=FLOWS_STRAIGHT_THROUGH,
    checks=(
        _Row("Sight glass condition at full load", Capability.OPERATOR),
        _Row("Subcooling and superheat vs design", Capability.TECHNICIAN),
        _Row("Charge weight vs nameplate (from the charge log)", Capability.SUPERVISOR),
        _Row(
            "Leak-test the circuit — joints, seals, service ports",
            Capability.TECHNICIAN,
        ),
        _Row(
            "Non-condensables present? Check head pressure vs saturation at condenser "
            "temperature",
            Capability.TECHNICIAN,
            rationale=(
                "Head above saturation for the measured condenser water temperature "
                "suggests air in the circuit."
            ),
        ),
    ),
    corrective=(
        _Row("Recover, weigh and correct the refrigerant charge", Capability.TECHNICIAN),
        _Row("Repair any leak found before recharging", Capability.TECHNICIAN),
        _Row("Purge non-condensables if indicated", Capability.TECHNICIAN),
        _Row(
            "Replace the filter-drier after opening the circuit",
            Capability.TECHNICIAN,
        ),
    ),
    preventive=(
        _Row("Annual leak test on this circuit", Capability.TECHNICIAN),
        _Row(
            "Maintain a charge log — every addition recorded with date and weight",
            Capability.SUPERVISOR,
        ),
        _Row(
            "Record superheat and subcooling on every PM round",
            Capability.TECHNICIAN,
        ),
    ),
)


# ── 3. Compressor inefficiency ──────────────────────────────────────────────────

COMPRESSOR_INEFFICIENCY = _curated_class(
    label="COMPRESSOR_INEFFICIENCY",
    heading="Compressor inefficiency",
    stated_severity="high",
    routing_note=FLOWS_STRAIGHT_THROUGH,
    checks=(
        _Row(
            "Compressor current vs nameplate at the observed load",
            Capability.OPERATOR,
            rationale=(
                "Suction is normal here — high current with normal suction points at the "
                "compressor."
            ),
        ),
        _Row("Oil level and oil pressure differential", Capability.OPERATOR),
        _Row("Oil analysis — acid number, moisture, metals", Capability.TECHNICIAN),
        _Row(
            "Valve plate / unloader condition and operation",
            Capability.TECHNICIAN,
        ),
        _Row("Discharge superheat", Capability.TECHNICIAN),
        _Row("Vibration reading vs baseline", Capability.TECHNICIAN),
    ),
    corrective=(
        _Row(
            "Take an oil sample for analysis; change oil and filter if out of spec",
            Capability.TECHNICIAN,
        ),
        _Row("Inspect valve plates and unloader mechanism", Capability.TECHNICIAN),
        _Row(
            "Vibration survey to confirm mechanical condition",
            Capability.TECHNICIAN,
        ),
        _Row(
            "If wear is confirmed, plan a compressor overhaul with the OEM",
            Capability.VENDOR,
        ),
    ),
    preventive=(
        _Row("Set an oil-analysis interval for this compressor", Capability.SUPERVISOR),
        _Row(
            "Trend current-vs-load monthly to catch drift early",
            Capability.SUPERVISOR,
        ),
        _Row("Add this unit to the vibration route", Capability.SUPERVISOR),
    ),
)


# ── 4. Condenser low flow ───────────────────────────────────────────────────────
# The only class with a sourced severity, and it has no blocking item and no marker.

CONDENSER_LOW_FLOW = _curated_class(
    label="CONDENSER_LOW_FLOW",
    heading="Condenser low flow",
    stated_severity="critical",
    routing_note=FLOWS_STRAIGHT_THROUGH,
    checks=(
        _Row(
            "Condenser water pump running and at expected speed?",
            Capability.OPERATOR,
        ),
        _Row(
            "Valve positions on the condenser circuit — anything throttled or shut?",
            Capability.OPERATOR,
        ),
        _Row("Strainer differential pressure", Capability.OPERATOR),
        _Row("Measured condenser flow vs design", Capability.TECHNICIAN),
        _Row(
            "Air binding in the condenser or high point of the loop?",
            Capability.MAINTENANCE,
        ),
    ),
    corrective=(
        _Row(
            "Restore condenser flow — open valves, clean the strainer, vent trapped air",
            Capability.MAINTENANCE,
        ),
        _Row("Verify pump performance against its curve", Capability.TECHNICIAN),
        _Row(
            "Confirm head pressure and current return to expected after flow is restored",
            Capability.OPERATOR,
        ),
    ),
    preventive=(
        _Row(
            "Verify the condenser flow interlock is functional",
            Capability.TECHNICIAN,
        ),
        _Row("Set a strainer cleaning schedule", Capability.SUPERVISOR),
        _Row("Annual pump performance test", Capability.SUPERVISOR),
    ),
)


# ── 5. Condenser water side — cause unspecified ─────────────────────────────────

CONDENSER_WATER_SIDE_UNSPECIFIED = _curated_class(
    label="CONDENSER_WATER_SIDE_UNSPECIFIED",
    heading="Condenser water side — cause unspecified",
    stated_severity="high",
    routing_note=NEEDS_A_HUMAN,
    checks=(
        _Row(
            "Condenser water flow vs design",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "Condenser approach temperature (leaving water vs condensing temperature)",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
            rationale="A widening approach with adequate flow points to tube fouling.",
        ),
        _Row("Strainer differential pressure", Capability.OPERATOR),
        _Row(
            "Cooling tower condition — fill, basin, distribution, fan operation",
            Capability.OPERATOR,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "Condenser tube fouling — last cleaning date and current fouling factor",
            Capability.SUPERVISOR,
        ),
        _Row("Condenser water pump performance vs curve", Capability.TECHNICIAN),
    ),
    corrective=(
        _Row("Clean strainers and restore design flow", Capability.MAINTENANCE),
        _Row(
            "Brush-clean condenser tubes if fouling is confirmed",
            Capability.MAINTENANCE,
        ),
        _Row(
            "Service the cooling tower — fill, distribution, fan, basin",
            Capability.MAINTENANCE,
        ),
        _Row(
            "Confirm approach temperature returns to design after the fix",
            Capability.OPERATOR,
        ),
    ),
    preventive=(
        _Row(
            "Review the condenser water treatment programme",
            Capability.SUPERVISOR,
        ),
        _Row(
            "Set condenser tube cleaning interval based on the fouling rate observed",
            Capability.SUPERVISOR,
        ),
        _Row(
            "Trend approach temperature as the leading indicator for this failure mode",
            Capability.SUPERVISOR,
        ),
    ),
)


# ── 6. High head pressure — cause not isolated ──────────────────────────────────

HIGH_HEAD_AMBIGUOUS = _curated_class(
    label="HIGH_HEAD_AMBIGUOUS",
    heading="High head pressure — cause not isolated",
    stated_severity="warning",
    routing_note=NEEDS_A_HUMAN,
    checks=(
        _Row(
            "Condenser approach temperature vs design",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "Condenser water flow vs design",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "Cooling tower performance — is it making design cold-water temperature?",
            Capability.OPERATOR,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "Condenser tube fouling — last cleaning, current fouling factor",
            Capability.SUPERVISOR,
        ),
        _Row("Non-condensables in the circuit?", Capability.TECHNICIAN),
        _Row("Refrigerant charge vs nameplate", Capability.SUPERVISOR),
    ),
    corrective=(
        _Row(
            "Address whichever cause the checks isolate — flow, fouling, tower, air, or "
            "charge",
            Capability.TECHNICIAN,
        ),
        _Row(
            "Clean condenser tubes if fouling is indicated",
            Capability.MAINTENANCE,
        ),
        _Row(
            "Verify head pressure returns to expected for the ambient and load",
            Capability.OPERATOR,
        ),
    ),
    preventive=(
        _Row(
            "Trend condenser approach temperature — it separates fouling from flow early",
            Capability.SUPERVISOR,
        ),
        _Row(
            "Confirm the tower water treatment programme is being followed",
            Capability.SUPERVISOR,
        ),
        _Row("Set a condenser cleaning interval", Capability.SUPERVISOR),
    ),
)


# ── 7. Power draw high — unexplained ────────────────────────────────────────────

POWER_HIGH_UNEXPLAINED = _curated_class(
    label="POWER_HIGH_UNEXPLAINED",
    heading="Power draw high — unexplained",
    stated_severity="warning",
    routing_note=NEEDS_A_HUMAN,
    checks=(
        _Row(
            "Phase currents and voltage balance at the starter",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
        ),
        _Row("Power factor vs expected", Capability.OPERATOR),
        _Row(
            "Motor winding resistance and insulation (megger) test",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "Actual load vs the current curve for this machine",
            Capability.OPERATOR,
            blocking=True,
            settles_it=True,
        ),
        _Row(
            "VFD parameters and fault history, if fitted",
            Capability.TECHNICIAN,
        ),
        _Row(
            "Starter and panel thermography — any hot joints?",
            Capability.TECHNICIAN,
        ),
    ),
    corrective=(
        _Row(
            "Correct any voltage or current imbalance found",
            Capability.TECHNICIAN,
        ),
        _Row(
            "Complete a motor electrical test; act on the result",
            Capability.TECHNICIAN,
        ),
        _Row(
            "Review and correct VFD configuration if fitted",
            Capability.TECHNICIAN,
        ),
    ),
    preventive=(
        _Row(
            "Annual thermography on the starter and panel",
            Capability.SUPERVISOR,
        ),
        _Row("Annual motor electrical test", Capability.SUPERVISOR),
        _Row(
            "Monitor power factor and current-vs-load trend",
            Capability.SUPERVISOR,
        ),
    ),
)


#: Part 1, in the source's order. The order of the classes is the pack's, not a ranking.
TRAINED_MODEL_CLASSES: tuple[CuratedClass, ...] = (
    STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION,
    REFRIGERANT_SIDE_HIGH_HEAD,
    COMPRESSOR_INEFFICIENCY,
    CONDENSER_LOW_FLOW,
    CONDENSER_WATER_SIDE_UNSPECIFIED,
    HIGH_HEAD_AMBIGUOUS,
    POWER_HIGH_UNEXPLAINED,
)

_BY_LABEL: dict[str, CuratedClass] = {c.label: c for c in TRAINED_MODEL_CLASSES}


def by_label(label: str) -> CuratedClass | None:
    """The transcribed class, or `None` when Part 1 does not carry that label.

    `None` means **not transcribed here**, never *"this class has no checklist"* — Parts 2
    and 3 of the pack hold the rest, and a caller reporting the absence must say which it
    means.
    """
    return _BY_LABEL.get(label)


def all_items() -> tuple[CuratedItem, ...]:
    """Every transcribed item in Part 1, in source order."""
    return tuple(item for c in TRAINED_MODEL_CLASSES for item in c.items)


def unreviewed_count() -> int:
    """How many of these instructions no refrigeration engineer has read. Currently all of
    them, and the number is reported rather than the content being shown."""
    return sum(1 for i in all_items() if not i.to_checklist_item().sme_reviewed)
