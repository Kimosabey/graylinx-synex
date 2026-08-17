"""A generated instruction reads exactly like a curated one, and both send someone to a machine.

**The failure this content prevents.** The 124-item library exists as prose in a review pack,
so the product either ships without it or somebody writes a plausible replacement. The second
is the dangerous one: an item that would cost a compressor arrives with the same authority as
one that would save it, and nothing in the string says which it is. Inherited constraint 1
makes the library curated content, never model output; constraint 26 lets the language model
select and contextualise it and nothing further. This module is therefore a **transcription** —
Part 1 of `05-checklist-library-for-review.md`, the trained model's seven fault classes, 86
items copied verbatim. 40 RCA, 25 corrective, 21 preventive — which is the 124-item library's
57 · 37 · 30 split less Part 2's 17 · 12 · 9.

**Nothing is reworded, reordered, corrected or filled in.** The review is the gate. A wrong
item a refrigeration engineer can see is far better than a corrected one they cannot, because
silently improving the content defeats the only check that stands between it and a technician.

**Nothing here reaches a user, and that is the desired state.** Every item carries
`sme_reviewed=False`, so `Checklist.visible_items` returns nothing for all seven classes.
`is_sample` is `False` too, and the difference is load-bearing: this is the real library
awaiting review, not content invented to demonstrate the mechanism. `app/services/cases.py`
holds that other kind, and `TranscribedItem` refuses `is_sample=True` outright.

**Order is preserved exactly, because it is the author's judgement.** Constraint 39: the next
question is the one that could move the most live candidates. The source's numbering is what
the author believes about that, so it survives into the item id — `high-head-ambiguous-rca-3`
is the third check under *Checks to run*. Sorting or tidying would overwrite an engineering
opinion with an accident.

**`[SETTLES IT]` is carried, never dropped.** It marks the check the pack believes
discriminates between the candidate causes, and `06-differentials-for-review.md` states what
each answer eliminates. The pack asks for those especially to be challenged, so losing the
marker would hide the highest-risk items among the routine ones. It is kept separate from
`blocking` on purpose: the two documents define them differently, and they coincide on every
Part 1 item only as a matter of fact.

**Severity is transcribed as the source's word, not mapped.** The pack states `high`,
`critical` and `warning`. `app/domain/faults.py` records six of the seven as `UNRATED` against
`Q49`, and `warning` is not a value on that scale at all. Choosing between them would be a
judgement about severity wearing a transcription's clothes, so both readings stay visible.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.cases import Capability, Checklist, Stage
from app.domain.library.curated import TranscribedItem

#: The document the instruction text comes from. Read-only input, the same status as
#: `docs/00-source/`.
TEXT_SOURCE = "thermynx/docs/for-vishnu/05-checklist-library-for-review.md"

#: The document the role tag and the `BLOCKING` flag come from. A different judgement by a
#: different author, so a reviewer who disagrees with a tag is disagreeing with this file.
ROLE_TAG_SOURCE = "thermynx/docs/for-vishnu/17-role-tags-every-check.md"

#: Where a `[SETTLES IT]` marker's consequences are written down — which cause each answer
#: eliminates. Named so the marker points somewhere rather than being decoration.
DIFFERENTIAL_SOURCE = "thermynx/docs/for-vishnu/06-differentials-for-review.md"

#: The part heading in the text source, verbatim.
PART = "Part 1 — Faults the trained model reports"

#: The marker as the source writes it.
SETTLES_IT_MARKER = "[SETTLES IT]"

#: `05`'s words for a class the trained model cannot resolve. Four of the seven carry it, and
#: they are the four with a differential — constraint 27.
NEEDS_A_HUMAN = "needs a human — the model says it cannot resolve this one"

#: `05`'s words for the other three.
FLOWS_STRAIGHT_THROUGH = "flows straight through"

#: `17`'s words for the same four classes. Different wording, same claim — recorded rather
#: than merged, because the two sentences were written by an author in two documents and a
#: reviewer may accept one and reject the other.
DECLARES_UNDECIDABLE = "the model declares this class undecidable"

#: `17` says nothing at all about routing for the three determinate classes. An empty string
#: is that silence, and it is not the same fact as `FLOWS_STRAIGHT_THROUGH`.
SAYS_NOTHING = ""


def _slug(label: str) -> str:
    return label.lower().replace("_", "-")


@dataclass(frozen=True)
class _Row:
    """One line of the source, before it is given an id, a stage and its provenance.

    `capability=None` means `17-role-tags-every-check.md` tags it with nothing — which happens
    nowhere in Part 1. The path exists so that an untagged item falls to constraint 24's
    technician default and records that it did, rather than inviting a guess.
    """

    text: str
    capability: Capability | None
    blocking: bool = False
    settles_it: bool = False
    note: str = ""


@dataclass(frozen=True)
class TrainedModelClass:
    """One of the seven classes the trained model reports, as the two documents present it."""

    label: str
    display: str
    """The class heading in the text source, verbatim."""

    severity_word: str
    """The severity as the source writes it. `warning` is not a `Severity` value — see the
    module docstring for why it is not translated."""

    routing_05: str
    """How `05-checklist-library-for-review.md` describes the routing, verbatim."""

    routing_17: str
    """How `17-role-tags-every-check.md` describes it. Empty where that document says nothing,
    which is a different fact from it agreeing."""

    needs_human: bool
    """Does the source say the model needs a human for this class? Read off `routing_05`."""

    items: tuple[TranscribedItem, ...]

    def at_stage(self, stage: Stage) -> tuple[TranscribedItem, ...]:
        return tuple(i for i in self.items if i.stage is stage)

    @property
    def settles_it_items(self) -> tuple[TranscribedItem, ...]:
        return tuple(i for i in self.items if i.settles_it)

    @property
    def blocking_items(self) -> tuple[TranscribedItem, ...]:
        return tuple(i for i in self.items if i.blocking)

    def for_capability(self, capability: Capability) -> tuple[TranscribedItem, ...]:
        """Transcribed items this capability may perform.

        Reads the transcription rather than `Checklist.for_capability`, which filters through
        `visible_items` and therefore returns nothing while the library is unreviewed.
        Constraint 37 — every class leaves the operator something to do — is a fact about the
        *content*, so it has to be checkable before the review gate opens.
        """
        return tuple(i for i in self.items if i.capability is capability)

    def checklist(self) -> Checklist:
        """The domain object. Every item unreviewed, so `visible_items` is empty."""
        return Checklist(fault_label=self.label, items=self.items)


def _fault_class(
    *,
    label: str,
    display: str,
    severity_word: str,
    routing_05: str,
    routing_17: str,
    checks: tuple[_Row, ...],
    corrective: tuple[_Row, ...],
    preventive: tuple[_Row, ...],
) -> TrainedModelClass:
    """Stamp a class's rows with stage, source position and provenance.

    `sme_reviewed` and `is_sample` are never passed. Both are `False` by default on
    `ChecklistItem`, and offering a keyword for either here would be a place a future edit
    could mark a whole class reviewed in one line.
    """
    items: list[TranscribedItem] = []
    for stage, rows in (
        (Stage.RCA, checks),
        (Stage.CORRECTIVE, corrective),
        (Stage.PREVENTIVE, preventive),
    ):
        for n, row in enumerate(rows, start=1):
            items.append(
                TranscribedItem(
                    id=f"{_slug(label)}-{stage.value}-{n}",
                    text=row.text,
                    capability=(
                        Capability.TECHNICIAN if row.capability is None else row.capability
                    ),
                    blocking=row.blocking,
                    stage=stage,
                    source_file=TEXT_SOURCE,
                    source_part=PART,
                    source_heading=display,
                    source_fault_label=label,
                    role_tag_file=ROLE_TAG_SOURCE,
                    source_note=row.note,
                    settles_it=row.settles_it,
                    capability_defaulted=row.capability is None,
                )
            )
    return TrainedModelClass(
        label=label,
        display=display,
        severity_word=severity_word,
        routing_05=routing_05,
        routing_17=routing_17,
        needs_human=routing_05 == NEEDS_A_HUMAN,
        items=tuple(items),
    )


# ── Starved evaporator — undercharge or restriction ─────────────────────────────
# Three of the six checks carry the marker, while the pack's preamble calls the marked item
# "the one we ask first" — singular. Transcribed as it stands; that is a reviewer's question.

STARVED_EVAP = "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION"

STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION = _fault_class(
    label=STARVED_EVAP,
    display="Starved evaporator — undercharge or restriction",
    severity_word="high",
    routing_05=NEEDS_A_HUMAN,
    routing_17=DECLARES_UNDECIDABLE,
    checks=(
        _Row(
            "Sight glass at full load — bubbles or flashing?",
            Capability.OPERATOR,
            blocking=True,
            settles_it=True,
            note="Clear glass with adequate subcooling argues against undercharge.",
        ),
        _Row(
            "Temperature drop across the filter-drier (inlet vs outlet)",
            Capability.TECHNICIAN,
            blocking=True,
            settles_it=True,
            note=(
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
            note=(
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


# ── High head — refrigerant side ────────────────────────────────────────────────
# No marker and no blocking item anywhere in this class, so a case can conclude here with no
# measured answer at all. Transcribed as it stands; that is Q37 and not this module's call.

REFRIGERANT_HIGH_HEAD = "REFRIGERANT_SIDE_HIGH_HEAD"

REFRIGERANT_SIDE_HIGH_HEAD = _fault_class(
    label=REFRIGERANT_HIGH_HEAD,
    display="High head — refrigerant side",
    severity_word="high",
    routing_05=FLOWS_STRAIGHT_THROUGH,
    routing_17=SAYS_NOTHING,
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
            note=(
                "Head above saturation for the measured condenser water temperature "
                "suggests air in the circuit."
            ),
        ),
    ),
    corrective=(
        _Row("Recover, weigh and correct the refrigerant charge", Capability.TECHNICIAN),
        _Row("Repair any leak found before recharging", Capability.TECHNICIAN),
        _Row("Purge non-condensables if indicated", Capability.TECHNICIAN),
        _Row("Replace the filter-drier after opening the circuit", Capability.TECHNICIAN),
    ),
    preventive=(
        _Row("Annual leak test on this circuit", Capability.TECHNICIAN),
        _Row(
            "Maintain a charge log — every addition recorded with date and weight",
            Capability.SUPERVISOR,
        ),
        _Row("Record superheat and subcooling on every PM round", Capability.TECHNICIAN),
    ),
)


# ── Compressor inefficiency ─────────────────────────────────────────────────────

COMPRESSOR = "COMPRESSOR_INEFFICIENCY"

COMPRESSOR_INEFFICIENCY = _fault_class(
    label=COMPRESSOR,
    display="Compressor inefficiency",
    severity_word="high",
    routing_05=FLOWS_STRAIGHT_THROUGH,
    routing_17=SAYS_NOTHING,
    checks=(
        _Row(
            "Compressor current vs nameplate at the observed load",
            Capability.OPERATOR,
            note=(
                "Suction is normal here — high current with normal suction points at the "
                "compressor."
            ),
        ),
        _Row("Oil level and oil pressure differential", Capability.OPERATOR),
        _Row("Oil analysis — acid number, moisture, metals", Capability.TECHNICIAN),
        _Row("Valve plate / unloader condition and operation", Capability.TECHNICIAN),
        _Row("Discharge superheat", Capability.TECHNICIAN),
        _Row("Vibration reading vs baseline", Capability.TECHNICIAN),
    ),
    corrective=(
        _Row(
            "Take an oil sample for analysis; change oil and filter if out of spec",
            Capability.TECHNICIAN,
        ),
        _Row("Inspect valve plates and unloader mechanism", Capability.TECHNICIAN),
        _Row("Vibration survey to confirm mechanical condition", Capability.TECHNICIAN),
        _Row(
            "If wear is confirmed, plan a compressor overhaul with the OEM",
            Capability.VENDOR,
        ),
    ),
    preventive=(
        _Row("Set an oil-analysis interval for this compressor", Capability.SUPERVISOR),
        _Row("Trend current-vs-load monthly to catch drift early", Capability.SUPERVISOR),
        _Row("Add this unit to the vibration route", Capability.SUPERVISOR),
    ),
)


# ── Condenser low flow ──────────────────────────────────────────────────────────
# The only class with a sourced severity, and it carries no blocking item and no marker.

CONDENSER_LOW_FLOW_LABEL = "CONDENSER_LOW_FLOW"

CONDENSER_LOW_FLOW = _fault_class(
    label=CONDENSER_LOW_FLOW_LABEL,
    display="Condenser low flow",
    severity_word="critical",
    routing_05=FLOWS_STRAIGHT_THROUGH,
    routing_17=SAYS_NOTHING,
    checks=(
        _Row("Condenser water pump running and at expected speed?", Capability.OPERATOR),
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
        _Row("Verify the condenser flow interlock is functional", Capability.TECHNICIAN),
        _Row("Set a strainer cleaning schedule", Capability.SUPERVISOR),
        _Row("Annual pump performance test", Capability.SUPERVISOR),
    ),
)


# ── Condenser water side — cause unspecified ────────────────────────────────────

CONDENSER_WATER_SIDE = "CONDENSER_WATER_SIDE_UNSPECIFIED"

CONDENSER_WATER_SIDE_UNSPECIFIED = _fault_class(
    label=CONDENSER_WATER_SIDE,
    display="Condenser water side — cause unspecified",
    severity_word="high",
    routing_05=NEEDS_A_HUMAN,
    routing_17=DECLARES_UNDECIDABLE,
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
            note="A widening approach with adequate flow points to tube fouling.",
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
        _Row("Brush-clean condenser tubes if fouling is confirmed", Capability.MAINTENANCE),
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
        _Row("Review the condenser water treatment programme", Capability.SUPERVISOR),
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


# ── High head pressure — cause not isolated ─────────────────────────────────────

HIGH_HEAD = "HIGH_HEAD_AMBIGUOUS"

HIGH_HEAD_AMBIGUOUS = _fault_class(
    label=HIGH_HEAD,
    display="High head pressure — cause not isolated",
    severity_word="warning",
    routing_05=NEEDS_A_HUMAN,
    routing_17=DECLARES_UNDECIDABLE,
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
        _Row("Clean condenser tubes if fouling is indicated", Capability.MAINTENANCE),
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


# ── Power draw high — unexplained ───────────────────────────────────────────────

POWER_HIGH = "POWER_HIGH_UNEXPLAINED"

POWER_HIGH_UNEXPLAINED = _fault_class(
    label=POWER_HIGH,
    display="Power draw high — unexplained",
    severity_word="warning",
    routing_05=NEEDS_A_HUMAN,
    routing_17=DECLARES_UNDECIDABLE,
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
        _Row("VFD parameters and fault history, if fitted", Capability.TECHNICIAN),
        _Row("Starter and panel thermography — any hot joints?", Capability.TECHNICIAN),
    ),
    corrective=(
        _Row("Correct any voltage or current imbalance found", Capability.TECHNICIAN),
        _Row("Complete a motor electrical test; act on the result", Capability.TECHNICIAN),
        _Row("Review and correct VFD configuration if fitted", Capability.TECHNICIAN),
    ),
    preventive=(
        _Row("Annual thermography on the starter and panel", Capability.SUPERVISOR),
        _Row("Annual motor electrical test", Capability.SUPERVISOR),
        _Row("Monitor power factor and current-vs-load trend", Capability.SUPERVISOR),
    ),
)


#: Part 1, in the source's order. The order of the classes is the pack's, not a ranking.
TRAINED_MODEL_CLASSES: tuple[TrainedModelClass, ...] = (
    STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION,
    REFRIGERANT_SIDE_HIGH_HEAD,
    COMPRESSOR_INEFFICIENCY,
    CONDENSER_LOW_FLOW,
    CONDENSER_WATER_SIDE_UNSPECIFIED,
    HIGH_HEAD_AMBIGUOUS,
    POWER_HIGH_UNEXPLAINED,
)

_BY_LABEL: dict[str, TrainedModelClass] = {c.label: c for c in TRAINED_MODEL_CLASSES}


def by_label(label: str) -> TrainedModelClass | None:
    """The transcribed class, or `None` when Part 1 does not carry that label.

    `None` means **not transcribed here**, never *"this class needs no checks"*. Parts 2 and 3
    of the pack hold the rest, and a caller reporting the absence has to say which it means.
    """
    return _BY_LABEL.get(label)


def all_items() -> tuple[TranscribedItem, ...]:
    """Every transcribed item in Part 1, in source order."""
    return tuple(item for c in TRAINED_MODEL_CLASSES for item in c.items)


def unreviewed_count() -> int:
    """How many of these instructions no refrigeration engineer has read.

    Currently all 86, and the number is what is reported while the content itself stays
    hidden — which turns the SME hour from a blocker into a counter.
    """
    return sum(1 for i in all_items() if not i.sme_reviewed)
