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
from app.domain import differential, equipment, faults, priority, safety, signals
from app.services import cases as case_service
from app.services import reports, work_orders
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


class PriorityArgs(BaseModel):
    model_config = {"extra": "forbid"}

    fault_label: str = Field(description="A fault class label, e.g. CONDENSER_LOW_FLOW")
    slot_count: int = Field(
        default=1, ge=0, description="How many consecutive measured slots carried the label"
    )


class EquipmentTrustArgs(BaseModel):
    model_config = {"extra": "forbid"}

    equipment_key: str = Field(description="An equipment key, e.g. chiller_1")


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


async def _equipment_standing(equipment_key: str) -> dict[str, Any]:
    """What is known about one machine before any episode is chosen.

    **The question this exists for is the one people actually ask first.** *"How is chiller 1
    doing?"* previously returned *"there is no scored evidence for that request"* — a true
    sentence and a useless one, because the router needs equipment **and** fault **and** day to
    assemble an evidence pack, and a bare machine name is none of those. A reader hearing that
    concludes the machine is fine, or that the product is broken; both are wrong.

    So this answers what *can* be said without an episode: whether the machine is scoreable at
    all, and which of its signals a reading could be trusted from. It deliberately states no
    verdict — the FDD rules name faults, not this — and it never implies health from silence.
    A machine with no fitted model is not a healthy machine; it is an unjudged one, and the two
    are the distinction the whole honesty layer exists to keep.
    """
    machine = equipment.by_key(equipment_key)
    if machine is None:
        known = ", ".join(e.key for e in equipment.all_equipment())
        return {
            "equipment_key": equipment_key,
            "known": False,
            "note": f"no equipment called {equipment_key!r}. The plant holds: {known}.",
        }

    scoreable = equipment.is_scoreable(equipment_key)
    unusable = list(signals.unusable_keys())
    never = list(signals.never_measured_keys())

    return {
        "equipment_key": machine.key,
        "display_name": getattr(machine, "display_name", machine.key),
        "known": True,
        "scoreable": scoreable,
        "scoreable_note": (
            "a residual model and a reference band are fitted, so readings here can be judged"
            if scoreable
            else (
                "no model and no reference band are fitted, so nothing on this machine can be "
                "judged against one. That is not a statement that it is healthy — it is a "
                "statement that it is unjudged."
            )
        ),
        "never_measured": never,
        "unusable": unusable,
        "trust_note": (
            f"{len(never)} signal(s) have never recorded a credible value and {len(unusable)} "
            f"are unusable for other reasons; a reading derived from either is not a "
            f"measurement of this plant."
        ),
        "to_go_further": (
            "Name a fault label and a day to assemble the evidence for one episode — the "
            "reliability workspace lists every detected episode for this machine."
        ),
    }


async def _safety_for_fault(fault_label: str) -> dict[str, Any]:
    """`S1`. Whether a fault class carries a safety impact, and whether anyone has reviewed it.

    **Two absences kept apart, because collapsing them is the dangerous move.** *"No safety
    impact was found"* and *"nobody has assessed this"* look identical on a screen and mean
    opposite things to a person about to open a compressor. `declares_no_safety_impact` is a
    reviewed finding; `ehs_reviewed` says whether the review happened at all. The coverage note
    states how much of the library has been read, so an unreviewed class is never presented as
    a cleared one.
    """
    assessment = safety.assess(fault_label)
    return {
        **assessment.as_dict(),
        "coverage": safety.coverage_note(),
        "reviewed_labels": len(safety.reviewed_labels()),
        "unreviewed_labels": len(safety.unreviewed_labels()),
    }


async def _priority_for_fault(fault_label: str, slot_count: int) -> dict[str, Any]:
    """`W4`. The priority a deterministic formula computes — never the model's opinion.

    **It reports what it could not use.** Three of the formula's four inputs do not exist for
    this plant, so a band returned without that caveat would read as a complete calculation.
    `used` names the inputs that were available and `missing` names the ones that were not, so
    a reader can see the priority is partial rather than discovering it later.
    """
    computed = priority.compute(fault_label, slot_count)
    return {
        **computed.as_dict(),
        "note": (
            "This band came from a formula over the inputs named in `used`. The language model "
            "did not choose it and cannot change it."
        ),
    }


async def _fault_timeline(*, plant_repo: Any) -> dict[str, Any]:
    """When faults appeared across the measured window — the shape of the record over time.

    **What a trend question can and cannot be on this data.** *"Is it getting worse?"* is the
    question underneath *"show me the trend"*, and it cannot be answered here: the window is a
    **snapshot**, not a live feed, and it ends on a fixed date. A rising count in the last week
    of a snapshot is not a deteriorating plant — it is the end of the data. So this reports the
    distribution by day and says what it is: a record of when labels were raised, in a window
    that stopped.

    **Counts per day, never a slope.** Fitting a line through fault counts and calling it a
    trend would produce a number with no error bar on nine classes of which one has an agreed
    severity. The distribution is a fact; the direction would be a claim.
    """
    rows = [r for r in await plant_repo.faulted_slots() if r.fault_label]

    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        day = row.slot_time.date().isoformat()
        by_day.setdefault(day, {})
        by_day[day][row.fault_label] = by_day[day].get(row.fault_label, 0) + 1

    days = sorted(by_day)
    return {
        "days_with_a_fault": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "by_day": [
            {
                "day": d,
                "labels": len(by_day[d]),
                "slots": sum(by_day[d].values()),
                "classes": sorted(by_day[d], key=lambda k: -by_day[d][k]),
            }
            for d in days
        ],
        "window_note": (
            "This is a snapshot, not a live feed: the measured window ends on a fixed date and "
            "nothing after it exists. A count that rises toward the last day is the end of the "
            "data, not a deteriorating plant."
        ),
        "trend_note": (
            "Counts per day, never a slope. Fitting a line through fault counts would produce a "
            "direction with no error behind it, on nine classes of which one has an agreed "
            "severity. The distribution is a fact; the trend would be a claim."
        ),
    }


async def _compare_equipment(*, plant_repo: Any) -> dict[str, Any]:
    """The two scoreable machines beside each other — what each carries and how far each is
    judged against **its own** band.

    **The comparison this makes, and the one it refuses.** *"Compare the two chillers"* is a
    question a manager asks first and this product could not answer at all. It can now say what
    each machine carried and how wide each model's own healthy band is — and it will not say
    which is worse. `F15` is the reason: a residual means nothing against zero, only against
    that asset's own band, and the same figure is `HIGH` on chiller 1 and `NORMAL` on chiller 2
    because their bands genuinely differ. Comparing the raw numbers would invert the answer on
    one machine, which is not imprecision but a wrong result.

    So it compares **counts and fit quality**, both of which are properties of the record, and
    states the trap rather than performing the comparison a reader expected. A tool that
    answers the wrong question fluently is worse than one that says which question it answered.
    """
    rows = await plant_repo.faulted_slots()
    bands = await plant_repo.residual_bands()
    scoreable = list(await plant_repo.scored_equipment_keys())

    per: dict[str, dict[str, Any]] = {}
    for key in scoreable:
        machine = equipment.by_key(key)
        mine = [r for r in rows if r.equipment_key == key and r.fault_label]
        labels = {r.fault_label for r in mine}
        days = {r.slot_time.date() for r in mine}
        my_bands = [b for b in bands if b.equipment_key == key]
        per[key] = {
            "display_name": getattr(machine, "display_name", key) if machine else key,
            "fault_classes": len(labels),
            "labels": sorted(labels),
            "days_with_a_fault": len(days),
            "labelled_slots": len(mine),
            "bands_fitted": len(my_bands),
            "band_widths": {b.residual_name: round(b.width, 3) for b in my_bands},
        }

    return {
        "compared": scoreable,
        "machines": per,
        "comparable_note": (
            "These are the only two machines with a fitted model and a reference band, so they "
            "are the only two that can be compared at all. The other ten carry telemetry that "
            "nothing has been fitted against."
        ),
        "not_compared_note": (
            "Which machine is WORSE is not answered here, and the reason is not caution. A "
            "residual means nothing against zero, only against that asset's own healthy band — "
            "and the two bands genuinely differ, so the same figure reads HIGH on one machine "
            "and NORMAL on the other. Comparing the raw numbers would invert the answer on one "
            "of them. Counts and band widths are properties of the record and are safe to set "
            "side by side; severity is not."
        ),
    }


async def _plant_overview(*, plant_repo: Any) -> dict[str, Any]:
    """What the whole plant carries — no machine named, no episode chosen.

    **The question a manager actually opens with.** *"What is the worst equipment today?"*,
    *"what happened across the plant?"* — neither names a machine and neither wants a
    diagnosis. Until now the Copilot had no path for them at all: every skill takes an
    `EvidencePack`, a pack needs equipment **and** fault **and** day, so a plant-wide question
    fell through to *"there is no scored evidence"* on a plant with 39 detected episodes.

    **It refuses to rank, and says so.** *"Worst"* is the word in the question and it is the one
    thing this cannot answer: severity is agreed for one fault class of nine (`Q49`), so a
    ranking would be a claim the formula cannot make. Ordering by how far a residual sits
    outside its band is forbidden outright — inherited constraint 3, because non-faults were
    measured to deviate *more* than faults on this plant. So it reports counts, sorted by days
    affected, and states plainly that days are not severity.

    **Machines with nothing detected are listed too.** A plant summary that showed only the
    faulted machines would read as a clean bill of health for the rest, and ten of the twelve
    have no fitted model at all — unjudged, which is not the same as well.
    """
    rows = await plant_repo.faulted_slots()

    per_machine: dict[str, dict[str, set]] = {}
    for row in rows:
        if not row.fault_label:
            continue
        per_machine.setdefault(row.equipment_key, {}).setdefault(row.fault_label, set()).add(
            row.slot_time.date()
        )

    machines = []
    for e in equipment.all_equipment():
        labels = per_machine.get(e.key, {})
        days = {d for dates in labels.values() for d in dates}
        machines.append(
            {
                "equipment_key": e.key,
                "display_name": getattr(e, "display_name", e.key),
                "scoreable": equipment.is_scoreable(e.key),
                "fault_classes": len(labels),
                "days_affected": len(days),
                "labels": sorted(labels, key=lambda k: -len(labels[k])),
            }
        )
    machines.sort(key=lambda m: (-m["days_affected"], -m["fault_classes"], m["equipment_key"]))

    unjudged = [m["display_name"] for m in machines if not m["scoreable"]]
    return {
        "equipment": len(machines),
        "with_a_detected_fault": sum(1 for m in machines if m["fault_classes"]),
        "scoreable": sum(1 for m in machines if m["scoreable"]),
        "machines": machines,
        "unjudged": unjudged,
        "ranking_note": (
            "Sorted by days affected, which is NOT a ranking by severity. Severity is agreed "
            "for one fault class of nine (Q49), and ordering by how far a residual sits outside "
            "its band is forbidden: non-faults on this plant were measured to deviate more than "
            "faults did."
        ),
        "unjudged_note": (
            f"{len(unjudged)} machine(s) have no fitted model and no reference band, so nothing "
            f"on them can be judged. That is not a statement that they are healthy — it is a "
            f"statement that they are unexamined."
        ),
    }


async def _episodes_for_equipment(equipment_key: str, *, plant_repo: Any) -> dict[str, Any]:
    """Every detected episode on one machine — the answer to a question about a *machine*.

    **The gap this closes, and it was producing a wrong answer rather than a refusal.** Asked
    *"what faults did chiller 2 have?"*, the catalogue path matched on "fault" and returned all
    nine fault classes **the plant model can emit** — a confident answer to a different
    question, with the machine silently dropped. *"What happened on chiller 1?"* did worse and
    said there was no scored evidence, on a machine carrying 32 detected episodes.

    Neither needed an episode chosen first. A question that names a machine and no day is a
    question about the machine, and this answers it from what was actually detected: the labels
    seen, how often, and over which days.

    **Counts, never a verdict.** It says a class appeared and how many days it appeared on. It
    does not rank, does not say which matters, and does not imply that more days is worse —
    severity is agreed for one class of nine (`Q49`), and inherited constraint 3 forbids
    ordering by residual magnitude because non-faults were measured to deviate more than faults.
    """
    machine = equipment.by_key(equipment_key)
    if machine is None:
        known = ", ".join(e.key for e in equipment.all_equipment())
        return {
            "equipment_key": equipment_key,
            "known": False,
            "note": f"no equipment called {equipment_key!r}. The plant holds: {known}.",
        }

    rows = [r for r in await plant_repo.faulted_slots() if r.equipment_key == machine.key]
    by_label: dict[str, set] = {}
    for row in rows:
        if row.fault_label:
            by_label.setdefault(row.fault_label, set()).add(row.slot_time.date())

    days = sorted({r.slot_time.date() for r in rows})
    return {
        "equipment_key": machine.key,
        "display_name": getattr(machine, "display_name", machine.key),
        "known": True,
        "scoreable": equipment.is_scoreable(machine.key),
        "labelled_slots": len(rows),
        "days_with_a_fault": len(days),
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,
        "labels": [
            {"label": label, "days": len(dates), "first": min(dates).isoformat(),
             "last": max(dates).isoformat()}
            for label, dates in sorted(by_label.items(), key=lambda kv: -len(kv[1]))
        ],
        "note": (
            "Counts of what was detected, not a ranking. More days is not worse: severity is "
            "agreed for one class of nine (Q49), and ordering by how far a residual sits "
            "outside its band is forbidden — non-faults were measured to deviate more than "
            "faults."
        ),
    }


async def _reconciliation_report(*, plant_repo: Any) -> dict[str, Any]:
    """`R3`. Every documented figure recomputed from the plant, and whether the two agree.

    **The first tool that reads the plant, and it does not hold the connection.** `app.tools`
    is forbidden from importing `sqlalchemy`, `aiomysql`, `asyncpg` or `pgvector`, and the
    reason recorded beside that contract is not testability: *a tool that could import a
    database driver could reach the plant directly and bypass `synex_plant_ro`*. So the
    repository arrives as an injected resource, built by a layer allowed to hold one and
    read-only by grant. The capability widens; the contract does not loosen.

    **A disagreement is the result, not an error.** A reconciliation that returns only the
    agreements is a reconciliation nobody needs — the whole point is the figure that does not
    match, so the count of disagreements leads and each one is named.
    """
    rows = await reports.reconcile(plant_repo)
    checkable = [r for r in rows if r.checkable]
    disagreed = [r for r in checkable if not r.agrees]
    return {
        "figures": len(rows),
        "checkable": len(checkable),
        "agreed": len(checkable) - len(disagreed),
        "disagreed": len(disagreed),
        "not_checkable": len(rows) - len(checkable),
        "disagreements": [r.as_dict() for r in disagreed],
        "note": (
            "Every figure here was recomputed from the plant snapshot and compared with the "
            "documented value. A figure that cannot be recomputed is reported as not checkable "
            "rather than as agreeing — those are different facts."
        ),
    }


async def _work_order_for_episode(*, pack: Any) -> dict[str, Any]:
    """`W2`–`W4`. The draft this episode would raise, and why — asked for rather than navigated to.

    **The capability already existed; only the asking did not.** `prepare_work` has drafted work
    orders since the skill table was wired, so *"raise a work order"* has always worked as a
    whole turn. What it could not do was be reached *from inside a tool loop* — so an
    investigation could not look at the job an episode would raise as one step among several,
    and a question that mixed the two ("what is wrong and what would it cost us to fix") had to
    pick one.

    **The pack is injected, not fetched.** Same rule as the plant repository: `app.tools` may
    not import a driver, and an `EvidencePack` is assembled from one. It arrives as a named
    resource from the turn that already built it, so the tool renders a draft it was handed and
    can never assemble one behind the Control Plane's back.

    **`is_draft` stays true and nothing is written.** A tool that persisted a work order would
    be a write hiding inside a read-only catalogue.
    """
    draft = work_orders.draft_from_pack(pack)
    priority = draft.priority
    return {
        "is_draft": True,
        "title": draft.title,
        "equipment": draft.equipment_display,
        "fault_label": draft.fault_label,
        "priority_band": priority.band,
        "priority_is_complete": priority.is_complete,
        "priority_used": list(priority.used),
        "priority_missing": [name for name, _ in priority.missing],
        "evidence_lines": len(draft.evidence),
        "cannot_close_until": list(draft.cannot_close_until),
        "warnings": list(draft.warnings),
        "note": (
            "Nothing was written. This is what would be raised, with the evidence that "
            "justifies it — a draft that reads as dispatchable when it is not is worse than "
            "none, because somebody plans against it."
        ),
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
            name="equipment_standing",
            description=(
                "What is known about one machine before any episode is chosen: whether it is "
                "scoreable at all, which of its signals have never been credibly measured, and "
                "which are unusable. Answers a bare question about a machine — 'how is chiller "
                "1 doing' — without implying a verdict the FDD rules did not give. States no "
                "fault and never reads silence as health."
            ),
            parameters=EquipmentTrustArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_equipment_standing,
            skill="look_up",
            tags=("asset", "provenance", "reference"),
        )
    )
    registry.register(
        ToolSpec(
            name="work_order_for_episode",
            description=(
                "The work order this episode would raise: title, priority band and which of "
                "the formula's inputs were available, how many evidence lines travel with it, "
                "what must be true before it can close, and any warning about the models "
                "behind it. Drafts only — nothing is written and nothing is approved."
            ),
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_work_order_for_episode,
            skill="prepare_work",
            needs=("pack",),
            tags=("work", "draft"),
        )
    )
    registry.register(
        ToolSpec(
            name="fault_timeline",
            description=(
                "When faults were detected across the measured window: which days carried "
                "which classes and how many slots each. Answers 'show me the trend', 'when did "
                "this start', 'is it getting worse'. Reports the distribution by day and "
                "explicitly refuses to fit a direction — the window is a snapshot that ends."
            ),
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_fault_timeline,
            skill="investigate",
            needs=("plant_repo",),
            tags=("plant", "history"),
        )
    )
    registry.register(
        ToolSpec(
            name="compare_equipment",
            description=(
                "The scoreable machines side by side: how many fault classes and days each "
                "carries, how many models are fitted, and how wide each healthy band is. "
                "Answers 'compare the two chillers'. Deliberately does not say which is worse — "
                "a residual only means anything against that asset's own band."
            ),
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_compare_equipment,
            skill="investigate",
            needs=("plant_repo",),
            tags=("plant", "compare"),
        )
    )
    registry.register(
        ToolSpec(
            name="plant_overview",
            description=(
                "What the whole plant carries: every machine, how many fault classes and days "
                "each has, and which machines cannot be judged at all. Answers a plant-wide "
                "question with no machine named and no episode chosen — 'what happened across "
                "the plant', 'which equipment is worst'. Reports counts and explicitly refuses "
                "to rank by severity."
            ),
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_plant_overview,
            skill="look_up",
            needs=("plant_repo",),
            tags=("plant", "fdd", "overview"),
        )
    )
    registry.register(
        ToolSpec(
            name="episodes_for_equipment",
            description=(
                "Every fault detected on one machine: which labels, how many days each was "
                "seen, and the first and last day. Answers a question about a machine — 'what "
                "happened on chiller 1', 'what faults did chiller 2 have' — with no episode "
                "chosen. Counts only; it ranks nothing and implies no severity."
            ),
            parameters=EquipmentTrustArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_episodes_for_equipment,
            skill="look_up",
            needs=("plant_repo",),
            tags=("asset", "fdd"),
        )
    )
    registry.register(
        ToolSpec(
            name="reconciliation_report",
            description=(
                "Recompute every documented figure from the plant snapshot and report which "
                "agree, which disagree, and which cannot be checked at all. Answers 'do the "
                "numbers in the report match the plant'. Names each disagreement."
            ),
            parameters=NoArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_reconciliation_report,
            skill="look_up",
            needs=("plant_repo",),
            tags=("reports", "lineage"),
        )
    )
    registry.register(
        ToolSpec(
            name="safety_for_fault",
            description=(
                "Whether a fault class carries a safety impact, whether an EHS reviewer has "
                "assessed it at all, and how much of the library has been reviewed. Keeps 'no "
                "impact found' and 'nobody has looked' apart — they mean opposite things to "
                "someone about to open a machine."
            ),
            parameters=FaultLabelArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_safety_for_fault,
            skill="resolve",
            tags=("safety", "reference"),
        )
    )
    registry.register(
        ToolSpec(
            name="priority_for_fault",
            description=(
                "The priority band a deterministic formula computes for a fault class and a "
                "slot count, with the inputs it used and the inputs it could not get. The "
                "language model never sets priority; this reports what the formula did."
            ),
            parameters=PriorityArgs,
            side_effect=SideEffect.READ_ONLY,
            control_level=ControlLevel.AUTOMATIC,
            handler=_priority_for_fault,
            skill="prepare_work",
            tags=("work", "priority"),
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
