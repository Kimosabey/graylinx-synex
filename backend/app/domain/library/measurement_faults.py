"""A dead sensor and a dead chiller look identical from inside a model watching one signal.

**The failure this content prevents.** The trained model cannot raise any of the four classes
below — it has no label for *"the instrument is lying"*, so a flatlined flow transmitter and a
chiller that has genuinely stopped producing cooling arrive at the model as the same shape.
`05-checklist-library-for-review.md` Part 2 states it directly:

> The trained model cannot raise these — a dead sensor and a dead chiller look identical from
> inside a model watching one signal. **Both are live on the plant right now.**

These four are raised by our own arithmetic instead, and the checks here are what a person
does about them. 38 items across four classes: 17 RCA, 12 corrective, 9 preventive.

**This module is a transcription, not authorship.** Every instruction is copied verbatim from
`05-checklist-library-for-review.md` Part 2. Every role tag and every `BLOCKING` flag is
copied from `17-role-tags-every-check.md` Part 2. Nothing is reworded, reordered, corrected or
filled in, because the review is the gate: a wrong item a refrigeration engineer can see is
far better than a corrected one they cannot. Where the two documents disagree about a class,
**both readings are recorded and neither is resolved** — see `MeasurementFault.routing_05`
and `routing_17`.

**Nothing here reaches a user, and that is the desired state.** Every item carries
`sme_reviewed=False`, so `Checklist.visible_items` returns nothing for all four classes.
`is_sample` is `False` as well, and the difference matters: this is the real library awaiting
review, not content invented to demonstrate the mechanism.

**Severity is transcribed as words, not mapped onto `Severity`.** The source rates three of
these classes **high** and one **warning**, and `warning` is not a value of
`app.domain.faults.Severity`. Translating it to `MEDIUM` or `LOW` would invent a rating in the
one place `F17` says must be authoritative, so the source's own word is carried as a string
and the mismatch is left visible.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.cases import Capability, Checklist, ChecklistItem, Stage
from app.domain.library.curated import TranscribedItem

#: The document the instruction text comes from. Read-only input; the same status as
#: `docs/00-source/`.
TEXT_SOURCE = "thermynx/docs/for-vishnu/05-checklist-library-for-review.md"

#: The document the role tag and the `BLOCKING` flag come from. Its own part heading reads
#: "Part 2 — The 4 measurement faults we detect ourselves"; the part heading recorded on each
#: item is the one in the text source, which is where the instruction itself was read from.
ROLE_TAG_SOURCE = "thermynx/docs/for-vishnu/17-role-tags-every-check.md"

PART = "Part 2 — Measurement faults we detect ourselves"


def _slug(label: str) -> str:
    return label.lower().replace("_", "-")


def _item(
    label: str,
    heading: str,
    stage: Stage,
    n: int,
    text: str,
    *,
    capability: Capability,
    blocking: bool = False,
    settles_it: bool = False,
    note: str = "",
) -> TranscribedItem:
    """One transcribed item. `sme_reviewed` and `is_sample` are left at their defaults.

    Both are `False` and neither is passed here, deliberately. A keyword argument for either
    would be a place a future edit could set one to `True` on a whole class at once; leaving
    them to the dataclass defaults means the only way to mark this content reviewed is to
    change `ChecklistItem` itself, which is a change nobody makes by accident.
    """
    return TranscribedItem(
        id=f"{_slug(label)}-{stage.value}-{n}",
        text=text,
        capability=capability,
        blocking=blocking,
        stage=stage,
        source_file=TEXT_SOURCE,
        source_part=PART,
        source_heading=heading,
        source_fault_label=label,
        role_tag_file=ROLE_TAG_SOURCE,
        source_note=note,
        settles_it=settles_it,
    )


@dataclass(frozen=True)
class MeasurementFault:
    """One of the four classes we raise ourselves, with both documents' framing of it."""

    label: str
    display: str
    """The class heading, verbatim."""

    severity_word: str
    """The severity as the source writes it. `warning` is not a `Severity` value — see the
    module docstring for why it is not translated."""

    routing_05: str
    """How `05-checklist-library-for-review.md` describes the routing, verbatim."""

    routing_17: str
    """How `17-role-tags-every-check.md` describes it, verbatim. For all four classes this
    contradicts `routing_05`, and the contradiction is reported rather than resolved."""

    items: tuple[TranscribedItem, ...]

    def checklist(self) -> Checklist:
        return Checklist(fault_label=self.label, items=self.items)


# ── Contradictory readings — measurement fault ──────────────────────────────────

CONTRADICTION = "INSTRUMENT_CONTRADICTION"
_H_CONTRADICTION = "Contradictory readings — measurement fault"

_CONTRADICTION_ITEMS: tuple[TranscribedItem, ...] = (
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.RCA, 1,
        "Read the suspect transmitter at the field device and compare to the BMS/panel value",
        capability=Capability.TECHNICIAN,
        blocking=True,
        settles_it=True,
        note=(
            "A healthy field reading with a dead BMS value means a tag/comms fault, not a "
            "sensor fault."
        ),
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.RCA, 2,
        "Does the sibling signal on the same circuit agree?",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
        note=(
            "e.g. chilled-water flow vs evaporator flow — if one is live and one is flat, "
            "the flat one is faulty."
        ),
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.RCA, 3,
        "Check the tag's last-good timestamp and comms status in the BMS",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.RCA, 4,
        "Confirm the loop is physically flowing — pump running, valves open, no air lock",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
        note="Rules out a genuine hydraulic problem before blaming the instrument.",
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.RCA, 5,
        "Note every derived metric that used this signal (kW/TR, TR, efficiency reports)",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.CORRECTIVE, 1,
        "Recalibrate or replace the faulty transmitter",
        capability=Capability.TECHNICIAN,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.CORRECTIVE, 2,
        "If it is a tag/comms fault, restore the point mapping in the BMS",
        capability=Capability.TECHNICIAN,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.CORRECTIVE, 3,
        "Re-verify the derived metric (kW/TR) returns to a plausible band after the fix",
        capability=Capability.OPERATOR,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.CORRECTIVE, 4,
        "Mark the affected date range so efficiency and FDD outputs from it are not trusted",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.PREVENTIVE, 1,
        "Add a plausibility check on this signal so a flatline raises a case automatically",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.PREVENTIVE, 2,
        "Cross-check paired flow signals on every PM round",
        capability=Capability.MAINTENANCE,
    ),
    _item(
        CONTRADICTION, _H_CONTRADICTION, Stage.PREVENTIVE, 3,
        "Set a calibration interval for this transmitter",
        capability=Capability.SUPERVISOR,
    ),
)


# ── Signal flatlined — suspect sensor ───────────────────────────────────────────

FLATLINE = "INSTRUMENT_FLATLINE"
_H_FLATLINE = "Signal flatlined — suspect sensor"

_FLATLINE_ITEMS: tuple[TranscribedItem, ...] = (
    _item(
        FLATLINE, _H_FLATLINE, Stage.RCA, 1,
        "Confirm the signal is genuinely static and the plant is not simply steady",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
        note="Compare against sibling signals that DID vary over the same window.",
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.RCA, 2,
        "Read the field device directly",
        capability=Capability.TECHNICIAN,
        blocking=True,
        settles_it=True,
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.RCA, 3,
        "Check sensor wiring, power and the BMS point's comms status",
        capability=Capability.TECHNICIAN,
        blocking=True,
        settles_it=True,
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.RCA, 4,
        "Identify when the signal last varied",
        capability=Capability.OPERATOR,
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.CORRECTIVE, 1,
        "Restore the signal — repair wiring, replace sensor, or fix the BMS point",
        capability=Capability.TECHNICIAN,
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.CORRECTIVE, 2,
        "Confirm the value tracks plant state again after the fix",
        capability=Capability.OPERATOR,
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.PREVENTIVE, 1,
        "Add a stuck-signal (zero-variance) check for this point",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        FLATLINE, _H_FLATLINE, Stage.PREVENTIVE, 2,
        "Include the point in the instrument calibration schedule",
        capability=Capability.SUPERVISOR,
    ),
)


# ── Implausible efficiency — suspect measurement ────────────────────────────────

IMPLAUSIBLE_EFFICIENCY = "INSTRUMENT_IMPLAUSIBLE_EFFICIENCY"
_H_IMPLAUSIBLE = "Implausible efficiency — suspect measurement"

_IMPLAUSIBLE_ITEMS: tuple[TranscribedItem, ...] = (
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.RCA, 1,
        "Check the flow reading used to compute TR — plausible for this machine?",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
        note=(
            "An implausible kW/TR is almost always TR near zero, and TR is flow x delta-T."
        ),
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.RCA, 2,
        "Check the chilled-water delta-T",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.RCA, 3,
        "Check the power reading against the panel",
        capability=Capability.OPERATOR,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.RCA, 4,
        "Is the machine genuinely loaded, or idling while reported as running?",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.CORRECTIVE, 1,
        "Fix whichever input is wrong — flow, delta-T, or power",
        capability=Capability.TECHNICIAN,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.CORRECTIVE, 2,
        "Recompute efficiency for the affected period once the input is corrected",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.CORRECTIVE, 3,
        "Exclude the bad period from efficiency reporting and benchmarks",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.PREVENTIVE, 1,
        "Enforce a validity gate on kW/TR before it reaches reports or the model",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        IMPLAUSIBLE_EFFICIENCY, _H_IMPLAUSIBLE, Stage.PREVENTIVE, 2,
        "Alert when a running unit reports near-zero TR",
        capability=Capability.SUPERVISOR,
    ),
)


# ── Fault model cannot diagnose this unit ───────────────────────────────────────

MODEL_BLIND = "MODEL_BLIND"
_H_MODEL_BLIND = "Fault model cannot diagnose this unit"

_MODEL_BLIND_ITEMS: tuple[TranscribedItem, ...] = (
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.RCA, 1,
        "Are the model's input signals valid over this window?",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
        note=(
            "The usual cause is a corrupt input, not a bad model. Check "
            "flow/temperature/power first."
        ),
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.RCA, 2,
        "When did the diagnosable fraction start falling?",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.RCA, 3,
        "Any open instrumentation case on this unit?",
        capability=Capability.OPERATOR,
        blocking=True,
        settles_it=True,
        note="If yes, fix that first — retraining on corrupt inputs learns the corruption.",
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.RCA, 4,
        "Has the plant's operating envelope moved outside the model's training window?",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.CORRECTIVE, 1,
        "Fix the upstream data quality issue before anything else",
        capability=Capability.TECHNICIAN,
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.CORRECTIVE, 2,
        "Only then request a model refit from the platform team, with the window stated",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.CORRECTIVE, 3,
        "Flag that FDD verdicts for this unit are unreliable until diagnosability recovers",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.PREVENTIVE, 1,
        "Monitor the diagnosable fraction continuously and raise a case when it collapses",
        capability=Capability.SUPERVISOR,
    ),
    _item(
        MODEL_BLIND, _H_MODEL_BLIND, Stage.PREVENTIVE, 2,
        "Re-validate the model after any instrumentation change",
        capability=Capability.SUPERVISOR,
    ),
)


# ── the four classes ────────────────────────────────────────────────────────────

#: What `05-checklist-library-for-review.md` prints beside all four class headings. It is
#: carried verbatim, and it appears to be Part 1 boilerplate: Part 2's own preamble says the
#: trained model *cannot raise these at all*, so it cannot also be declaring them
#: unresolvable. Reported, not corrected — see the task return value.
_ROUTING_05 = "needs a human — the model says it cannot resolve this one"

#: What `17-role-tags-every-check.md` prints beside the same four headings.
_ROUTING_17 = "raised by our arithmetic, not the model"


MEASUREMENT_FAULTS: tuple[MeasurementFault, ...] = (
    MeasurementFault(
        label=CONTRADICTION,
        display=_H_CONTRADICTION,
        severity_word="high",
        routing_05=_ROUTING_05,
        routing_17=_ROUTING_17,
        items=_CONTRADICTION_ITEMS,
    ),
    MeasurementFault(
        label=FLATLINE,
        display=_H_FLATLINE,
        severity_word="high",
        routing_05=_ROUTING_05,
        routing_17=_ROUTING_17,
        items=_FLATLINE_ITEMS,
    ),
    MeasurementFault(
        label=IMPLAUSIBLE_EFFICIENCY,
        display=_H_IMPLAUSIBLE,
        severity_word="high",
        routing_05=_ROUTING_05,
        routing_17=_ROUTING_17,
        items=_IMPLAUSIBLE_ITEMS,
    ),
    MeasurementFault(
        label=MODEL_BLIND,
        display=_H_MODEL_BLIND,
        severity_word="warning",
        routing_05=_ROUTING_05,
        routing_17=_ROUTING_17,
        items=_MODEL_BLIND_ITEMS,
    ),
)

_BY_LABEL: dict[str, MeasurementFault] = {f.label: f for f in MEASUREMENT_FAULTS}


def labels() -> tuple[str, ...]:
    """The four labels this module carries content for.

    None of them appears in `app.domain.faults`, whose taxonomy is the nine values of
    `fault_label` measured in `gla_model_residuals_wc`. That is consistent rather than
    contradictory — the trained model never writes these labels, which is the whole reason
    Part 2 exists — but it does mean `faults.severity_of` returns `UNRATED` for all four and
    `severity_word` here is the only rating available. Reported, not reconciled.
    """
    return tuple(f.label for f in MEASUREMENT_FAULTS)


def by_label(label: str) -> MeasurementFault | None:
    return _BY_LABEL.get(label)


def all_items() -> tuple[TranscribedItem, ...]:
    return tuple(item for fault in MEASUREMENT_FAULTS for item in fault.items)


def items_for(label: str) -> tuple[TranscribedItem, ...]:
    fault = _BY_LABEL.get(label)
    return fault.items if fault else ()


def checklist_for(label: str) -> Checklist | None:
    """The class's checklist, or `None` when this module carries nothing for the label.

    `None` means **not one of our four measurement faults**, never *"this class has no
    checks"*. The returned `Checklist` shows nobody anything today: every item is
    `sme_reviewed=False`, so `visible_items` is empty and `unreviewed_count` reports the gap.
    """
    fault = _BY_LABEL.get(label)
    return fault.checklist() if fault else None


def stage_counts() -> dict[Stage, int]:
    counts = dict.fromkeys(Stage, 0)
    for item in all_items():
        counts[item.stage] += 1
    return counts


def unreviewed_count() -> int:
    """How many of these no refrigeration engineer has read. Today: all of them."""
    return sum(1 for item in all_items() if not item.sme_reviewed)


def operator_items(label: str) -> tuple[ChecklistItem, ...]:
    """Items the source tags `OPERATOR`, read off the raw list rather than the visible one.

    Constraint 37 — every fault class must carry at least one check the operator can do — has
    to be checkable *before* the SME hour, and `Checklist.for_capability` filters through
    `visible_items`, which is correctly empty while nothing is reviewed. So this reads the
    transcription directly. It is a statement about the library, not about what anyone can
    currently see.
    """
    return tuple(i for i in items_for(label) if i.capability is Capability.OPERATOR)
