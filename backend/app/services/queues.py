"""`U6` the reliability workspace · `U7` the supervisor queue — admitted by capability, not rank.

**The failure `U7` exists for, in the library's own tally.** The 124 curated checklist items
carry role tags: technician 49, supervisor 38, operator 29, maintenance 7, vendor 1. The
supervisor's 38 are almost entirely the *preventive* stage — intervals, schedules, trends.
Prevention is a records-and-authority activity, so the tagging is right in principle, and it
meant 38 tagged items landed on the one role that had no queue to receive them. This module is
that queue.

**The failure `U6` exists for.** Twenty-two detected episodes once sat outside the case queue
because nothing called the seed, and the queue read as empty — inherited constraint 21,
*detection is not seeding*. An empty queue reads as a clean plant, so this surface reports
**detected-but-not-queued** rather than assuming it is zero, and a workspace handed no
detection list at all says that too rather than showing a confident nought.

**The trap, and the incident behind it.** Inherited constraint 25: role order is *display*
order, not a capability ladder. Ranking by seniority once sent a filter-drier restriction to a
supervisor because one incidental records question outranked three refrigeration measurements.
So every section here is admitted by a **named capability** and by nothing else:

| Surface | Section | Admitted by |
|---|---|---|
| `U6` | the fault queue | `view_faults` |
| `U6` | the residuals behind each fault | `view_residuals` |
| `U6` | the case each fault opens | `open_case` |
| `U7` | approvals | `approve_work` |
| `U7` | blocked cases | `approve_work` |
| `U7` | closures verification has not cleared | `close_work` |

Read that table in both directions, because that is the whole point. A supervisor holds
`approve_work` and `close_work` and **not** `view_residuals`, so the residual section is
withheld from them exactly as the approval section is withheld from a reliability engineer.
Neither is senior to the other; each is missing something the other has. A comparison like
`persona >= SUPERVISOR` would rebuild the ladder invisibly, so the admission table is a
`dict[Section, Capability]` and there is no ordering over personas anywhere in this file.

**`RC9`'s two kinds of stale are two fields, not one count.** A case whose condition cleared
and a case nobody has touched are different problems needing different action: the first says
the plant moved on, the second says nobody looked. Four open cases once described transmitters
repaired weeks earlier while twenty had been waiting since April, and a single `stale` flag
would have made a fixed machine and a forgotten one look identical. They are kept as separate
tuples so that collapsing them requires writing new code rather than reading a field.

**This module composes; it re-implements nothing.** The state machine is
`app/domain/cases.py`, the approval engine is `app/domain/authority.py`, the ageing verdict is
`RC9`'s and is written onto the row by `app/db/case_store.py`, and the closure gate is
`app/analytics/verification.py`. What is here is the arrangement.

**It takes rows rather than fetching them, for two reasons.** `CaseStore.open_cases()`
deliberately excludes stale cases, and `U7` needs precisely those — so the caller chooses the
query. And taking rows means the whole surface is unit-testable with PostgreSQL stopped, which
is the state PostgreSQL is currently in.

**Nothing here calls a model.** `U7` is `SW` in the register. `U6` is `SW + LLM`, and the
language model's half is the explanation attached to a row — never the ordering, never the
admission, never whether a closure has cleared.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol

from app.analytics.verification import Outcome, Verification
from app.domain import authority, residuals
from app.domain.cases import CaseState
from app.services.control_plane import Capability


class Surface(StrEnum):
    """The two surfaces `CONTEXT.md` §10d names. Not a scale, and not an order."""

    RELIABILITY_WORKSPACE = "reliability_workspace"
    """`U6`. The fault queue, the residuals behind each one, the case it opens."""

    SUPERVISOR_QUEUE = "supervisor_queue"
    """`U7`. Approvals, blocked cases, and closures verification has not cleared."""


class Section(StrEnum):
    """What a surface is made of. Each is admitted by exactly one capability."""

    FAULT_QUEUE = "fault_queue"
    RESIDUALS_BEHIND = "residuals_behind"
    CASES_OPENED = "cases_opened"
    AWAITING_APPROVAL = "awaiting_approval"
    BLOCKED = "blocked"
    UNCLEARED_CLOSURES = "uncleared_closures"


#: Constraint 25, made structural. A `dict[Section, Capability]` cannot degrade into a ladder;
#: a list of personas, or any comparison between them, can and once did. Every membership
#: question in this module is answered by a lookup here and by nothing else.
ADMITS: dict[Section, Capability] = {
    Section.FAULT_QUEUE: Capability.VIEW_FAULTS,
    Section.RESIDUALS_BEHIND: Capability.VIEW_RESIDUALS,
    Section.CASES_OPENED: Capability.OPEN_CASE,
    Section.AWAITING_APPROVAL: Capability.APPROVE_WORK,
    Section.BLOCKED: Capability.APPROVE_WORK,
    Section.UNCLEARED_CLOSURES: Capability.CLOSE_WORK,
}

#: Which sections belong to which surface. Held apart from `ADMITS` so that moving a section
#: between surfaces cannot silently change who may see it.
SECTIONS_OF: dict[Surface, tuple[Section, ...]] = {
    Surface.RELIABILITY_WORKSPACE: (
        Section.FAULT_QUEUE,
        Section.RESIDUALS_BEHIND,
        Section.CASES_OPENED,
    ),
    Surface.SUPERVISOR_QUEUE: (
        Section.AWAITING_APPROVAL,
        Section.BLOCKED,
        Section.UNCLEARED_CLOSURES,
    ),
}

#: Why both queues sit in the order they do, and what that order deliberately does not claim.
#:
#: TBD (Q71): no document says what should order a working queue. Oldest first, because age is
#: a fact the row already carries rather than a judgement about the plant. The three orderings
#: a reader might expect are all unavailable: residual magnitude is forbidden outright by
#: inherited constraint 3, since non-faults were measured to deviate *more* than faults;
#: severity exists for one fault class of nine (`Q49`); and the `W4` priority is incomplete
#: because three of its four inputs do not exist (`Q51`). Ordering by age changes which row a
#: reader sees first and nothing else — it eliminates nothing, hides nothing, and closes
#: nothing.
QUEUE_ORDER_REASON: str = (
    "Oldest first. This is not a ranking: severity is agreed for one fault class of nine "
    "(Q49), the W4 priority is incomplete because three of its four inputs do not exist "
    "(Q51), and ordering by residual magnitude is forbidden — non-faults were measured to "
    "deviate more than faults (constraint 3). Age is the one term this data actually has."
)

#: `RC9`. The condition clearing is evidence about the plant, not proof of a repair — and a
#: cleared case leaves `CaseStore.open_cases()` because its state becomes `stale`, so without
#: a row of its own it would simply vanish from the working queue.
#:
#: TBD (Q72): nobody has said whether a condition-cleared case needs a named human to confirm
#: it before it leaves the queue. Until they do, it is surfaced as its own row with its own
#: action rather than being closed, dropped, or counted alongside the untouched ones.
CLEARED_NEEDS_A_PERSON: str = (
    "The condition that opened this case is no longer detected. That is not proof the repair "
    "worked — only verification establishes that, and a NULL means not diagnosed, never "
    "healthy. Confirm it or reopen it; do not close it on the absence."
)

#: What to do about each kind of ageing. Two entries, two different actions — which is the
#: whole reason the two kinds are kept apart.
ACTION_FOR: dict[str, str] = {
    "condition_cleared": CLEARED_NEEDS_A_PERSON,
    "untouched": (
        "Nobody has touched this case. It is still open and it needs a person rather than a "
        "status — twenty cases once waited since April, and nothing about the queue said so."
    ),
}


# ── the row this module reads ───────────────────────────────────────────────────

class CaseRecord(Protocol):
    """One persisted case, described structurally rather than imported.

    `app.db.state.CaseRow` satisfies this, and so does any plain object with these fields.
    Structural rather than nominal on purpose: importing the row class would pull a database
    driver into `services`, which contract 6 in `importlinter.ini` forbids — and it would make
    this surface untestable with PostgreSQL stopped, which is how it is testable now.
    """

    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    state: str
    updated_at: datetime
    stale_at: datetime | None
    stale_reason: str
    condition_cleared: bool
    slot_count: int


@dataclass(frozen=True)
class SectionAdmission:
    """Whether one section is shown, and — when it is not — the capability that would show it.

    A withheld section always names a capability. It never says "more senior", because that
    sentence is the constraint 25 failure written down.
    """

    section: Section
    capability: Capability
    admitted: bool
    reason: str


def admission(section: Section, capabilities: frozenset[Capability]) -> SectionAdmission:
    """One lookup, one answer, and the answer carries its reason in words."""
    needed = ADMITS[section]
    if needed in capabilities:
        return SectionAdmission(
            section=section,
            capability=needed,
            admitted=True,
            reason=f"this identity holds {needed.value!r}, which admits {section.value}",
        )
    return SectionAdmission(
        section=section,
        capability=needed,
        admitted=False,
        reason=(
            f"{section.value} needs the {needed.value!r} capability, which this identity does "
            f"not hold. That is a capability and not a rank — nothing here is unlocked by "
            f"seniority, and a supervisor is not a more capable technician."
        ),
    )


@dataclass(frozen=True)
class UnreadableCase:
    """A row whose state is not one the machine knows. Reported, never silently dropped.

    A case that disappears from a queue because a string did not parse is the same failure as
    twenty-two episodes sitting outside the queue: the surface looks calm and is not.
    """

    seed_key: str
    state: str
    reason: str


# ── `U6` the reliability workspace ──────────────────────────────────────────────

@dataclass(frozen=True)
class ResidualBehind:
    """One residual standing behind a queued fault, with its fit or with its absence.

    A residual is never rendered without its fit. The same model is eighteen times worse on
    one machine than the other — chiller 1's current model at nRMSE 48.03 against chiller 2's
    2.65 — so an identical fault label on the two machines does not mean the same thing.
    """

    equipment_key: str
    model_name: str
    nrmse: float | None
    absence: str = ""
    """Words when there is no residual to show. Empty when there is one — the absence, never
    the value, is the thing that has to be spelled out."""

    @property
    def is_absent(self) -> bool:
        return bool(self.absence)

    @property
    def is_poor_fit(self) -> bool:
        return self.nrmse is not None and self.nrmse >= residuals.POOR_FIT_NRMSE

    def render(self) -> str:
        if self.is_absent:
            return f"{self.model_name or 'no model'}: {self.absence}"
        return f"{self.model_name}: nRMSE {self.nrmse}"


def residuals_behind(equipment_key: str) -> tuple[ResidualBehind, ...]:
    """The residuals a reliability engineer is entitled to see behind one fault.

    The unfitted sixth is **held as a stated absence rather than omitted**. Constraint 14: a
    figure is a value or a stated absence, never neither — and omission is the failure that
    constraint exists to prevent, because a list of five models reads as complete.
    """
    fits = residuals.fits_for(equipment_key)
    if not fits:
        return (
            ResidualBehind(
                equipment_key=equipment_key,
                model_name="",
                nrmse=None,
                absence=(
                    "no residual model is fitted for this asset, so there is no residual "
                    "behind this fault. That is an absence, not a zero, and not a clean bill."
                ),
            ),
        )

    rows = [
        ResidualBehind(equipment_key=equipment_key, model_name=f.model_name, nrmse=f.nrmse)
        for f in fits
    ]
    rows.append(
        ResidualBehind(
            equipment_key=equipment_key,
            model_name=residuals.ABSENT_RESIDUAL_COLUMN,
            nrmse=None,
            absence=(
                f"no model is fitted for this signal inside the measured window. The design "
                f"says {residuals.DESIGNED_MODEL_COUNT} models per chiller and "
                f"{residuals.FITTED_MODEL_COUNT} are fitted; the sixth is named here rather "
                f"than left out, because a list of five reads as complete."
            ),
        )
    )
    return tuple(rows)


def fit_note_for(equipment_key: str) -> str:
    """What a whole-asset claim on this machine has to answer for, in words either way."""
    worst = residuals.worst_nrmse_for(equipment_key)
    if worst is None:
        return (
            "No model is fitted for this asset, so there is no fit to qualify this row with. "
            "Nothing about it may be read as measured-and-checked."
        )
    if residuals.has_poor_fit(equipment_key):
        return (
            f"The worst fit on this asset is nRMSE {worst}, over the "
            f"{residuals.POOR_FIT_NRMSE} mark (Q50). Part of this residual is the model's own "
            f"error, so the alarm may be an artefact of the fit rather than a fault — check "
            f"before dispatching anyone."
        )
    return (
        f"The worst fit on this asset is nRMSE {worst}, "
        f"under the {residuals.POOR_FIT_NRMSE} mark."
    )


@dataclass(frozen=True)
class FaultRow:
    """One fault in the engineer's queue, and everything standing behind it."""

    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    state: CaseState
    slot_count: int
    residuals: tuple[ResidualBehind, ...]
    residuals_note: str
    fit_note: str
    case_note: str

    @property
    def has_residuals(self) -> bool:
        return any(not r.is_absent for r in self.residuals)


@dataclass(frozen=True)
class ReliabilityWorkspace:
    """`U6`. The fault queue, the residuals behind each one, and the case each one opens."""

    faults: tuple[FaultRow, ...]
    withheld: tuple[SectionAdmission, ...]
    unreadable: tuple[UnreadableCase, ...]
    detected_not_queued: tuple[str, ...]
    seeding_note: str
    order_reason: str = QUEUE_ORDER_REASON

    @property
    def is_empty_queue(self) -> bool:
        """True when there is nothing to work **and the queue was actually read**.

        A withheld queue is not an empty one. Returning `True` for both would collapse *"we
        looked and there is nothing"* into *"we could not look"* — the same two-absences
        failure the seeding note exists to prevent, one field along. **Never read even a true
        answer as a clean plant**: the seeding note is what says whether the emptiness has
        been checked against the detector.
        """
        return not self.faults and not any(
            a.section is Section.FAULT_QUEUE for a in self.withheld
        )


def reliability_workspace(
    cases: Sequence[CaseRecord],
    capabilities: frozenset[Capability],
    *,
    detected_seed_keys: Sequence[str] | None = None,
) -> ReliabilityWorkspace:
    """`U6`. Arrange what already exists into the shape an engineer works.

    `detected_seed_keys` is what the detector found. Supplying it lets the workspace report
    episodes that never became a case — constraint 21, and the twenty-two that sat outside the
    queue. Supplying nothing is reported as *not checked*, never as zero.
    """
    known, unreadable = _readable(cases)
    admissions = tuple(admission(s, capabilities) for s in
        SECTIONS_OF[Surface.RELIABILITY_WORKSPACE])
    withheld = tuple(a for a in admissions if not a.admitted)
    granted = {a.section for a in admissions if a.admitted}

    if Section.FAULT_QUEUE not in granted:
        return ReliabilityWorkspace(
            faults=(),
            withheld=withheld,
            unreadable=unreadable,
            detected_not_queued=(),
            seeding_note=(
                "The fault queue itself is withheld, so nothing was checked against the "
                "detector. This is not an empty queue."
            ),
        )

    show_residuals = Section.RESIDUALS_BEHIND in granted
    show_cases = Section.CASES_OPENED in granted

    rows = tuple(
        FaultRow(
            seed_key=row.seed_key,
            equipment_key=row.equipment_key,
            fault_label=row.fault_label,
            day=row.day,
            state=state,
            slot_count=row.slot_count,
            residuals=residuals_behind(row.equipment_key) if show_residuals else (),
            residuals_note=(
                "" if show_residuals else admission(Section.RESIDUALS_BEHIND, capabilities).reason
            ),
            fit_note=fit_note_for(row.equipment_key) if show_residuals else "",
            case_note=(
                _case_note(row.seed_key)
                if show_cases
                else admission(Section.CASES_OPENED, capabilities).reason
            ),
        )
        for row, state in sorted(known, key=lambda pair: _order_key(pair[0]))
    )

    missing, note = _seeding_gap(known, detected_seed_keys)
    return ReliabilityWorkspace(
        faults=rows,
        withheld=withheld,
        unreadable=unreadable,
        detected_not_queued=missing,
        seeding_note=note,
    )


def _case_note(seed_key: str) -> str:
    """Constraint 35 and `RC8`, said on the row rather than assumed by the reader."""
    return (
        f"This fault opens case {seed_key} — one case per equipment, fault and day. A rescan "
        f"reopens it rather than opening a second, because a single real fault spans hundreds "
        f"of consecutive readings and per-slot cases would bury one afternoon."
    )


def _seeding_gap(
    known: tuple[tuple[CaseRecord, CaseState], ...], detected: Sequence[str] | None
) -> tuple[tuple[str, ...], str]:
    """Detected-but-not-queued, or a statement that nobody checked. Never a confident zero."""
    if detected is None:
        return (), (
            "No detection list was supplied, so whether every detected episode reached this "
            "queue has not been checked. Detection is not seeding (constraint 21): twenty-two "
            "episodes once sat outside the queue and it read as empty."
        )

    queued = {row.seed_key for row, _ in known}
    missing = tuple(sorted(k for k in detected if k not in queued))
    if not missing:
        return (), (
            f"All {len(detected)} detected episode(s) have a case. Checked against the "
            f"detector rather than assumed."
        )
    return missing, (
        f"{len(missing)} detected episode(s) have no case and are not in this queue. A "
        f"detector that fires into nowhere is worse than no detector, because the queue reads "
        f"as a clean plant (constraint 21)."
    )


# ── `U7` the supervisor queue ───────────────────────────────────────────────────

@dataclass(frozen=True)
class PendingAction:
    """What a case in a given state is waiting on from somebody holding `approve_work`."""

    name: str
    risk: authority.Risk
    asks: str
    task_is_a_question: bool = False
    """`RC15`. On the authorisation route the supervisor is asked to *decide*, not to measure.
    Handing them a measurement task is how the wrong person ends up at a gauge — which is
    constraint 25's incident arriving by the other door."""


#: Which case states are waiting on an approval, and what each one actually asks. States
#: absent from this table are not waiting on a supervisor at all, and inventing an entry for
#: them would manufacture work for the role that already receives the library's preventive 38.
PENDING_ON_AN_APPROVER: dict[CaseState, PendingAction] = {
    CaseState.ESCALATED: PendingAction(
        name="authorise_escalated_case",
        risk=authority.Risk.HIGH,
        asks=(
            "This case was escalated up for authority or for a judgement. The task is the "
            "question, not a measurement, and it landed unassigned — a named supervisor would "
            "imply somebody had accepted it, and nobody has."
        ),
        task_is_a_question=True,
    ),
    CaseState.ROOT_CAUSED: PendingAction(
        name="approve_work_against_established_cause",
        risk=authority.Risk.HIGH,
        asks=(
            "A cause is established with the checks that established it. Raising work against "
            "it dispatches a person, which is why it needs approving rather than doing."
        ),
    ),
}


@dataclass(frozen=True)
class ApprovalRow:
    """One case waiting on an approval, carrying `G3`'s ruling rather than a yes or a no."""

    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    state: CaseState
    asks: str
    ruling: authority.Ruling
    task_is_a_question: bool

    @property
    def may_be_approved_now(self) -> bool:
        return self.ruling.may_proceed


class Blocked(StrEnum):
    """Why a case cannot move. Two kinds, and the second is an absence rather than a pass."""

    UNSETTLED_BLOCKING_CHECK = "unsettled_blocking_check"
    """A blocking item has no measured answer. Twenty-six of forty-three measured cases stop
    exactly here, which makes this the ordinary journey rather than the exception."""

    NOT_EVALUATED = "not_evaluated"
    """Nobody supplied a blocking-check evaluation for this case, so whether it can move is
    unknown. **Not a clear pass** — six "N/A" presses once opened a blocking gate with zero
    evidence behind it."""


@dataclass(frozen=True)
class BlockedRow:
    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    state: CaseState
    kind: Blocked
    reason: str


class ClosureBlock(StrEnum):
    """Why a closure has not cleared. Three kinds, and merging any two loses the point."""

    NOT_VERIFIED = "not_verified"
    """The work is done and nothing has been checked. `W9`: a case cannot close unproven, and
    the closure note never decides it."""

    VERIFIED_UNKNOWN = "verified_unknown"
    """The check ran and could not decide. A permitted outcome, and it does not close."""

    VERIFIED_FAIL = "verified_fail"
    """The check ran and says what was measured is still not fixed."""


@dataclass(frozen=True)
class ClosureRow:
    """One closure verification has not cleared, and which of the three reasons it is.

    Carries no `Ruling`. Closing is gated by evidence rather than by authority — `W9` says a
    case cannot close unproven, and a supervisor holding every capability in the system still
    cannot approve their way past a residual that has not returned to band.
    """

    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    block: ClosureBlock
    reason: str
    outcome: str


class AgeingKind(StrEnum):
    """`RC9`'s two kinds of stale. They are two, permanently."""

    CONDITION_CLEARED = "condition_cleared"
    """Evidence about the plant: the condition that opened this case is gone."""

    UNTOUCHED = "untouched"
    """Evidence about the queue: nobody has looked. Twenty cases once waited since April."""


@dataclass(frozen=True)
class AgeingRow:
    """One aged case, its `RC9` verdict, and the action that verdict calls for."""

    seed_key: str
    equipment_key: str
    fault_label: str
    day: date
    kind: AgeingKind
    reason: str
    action: str


@dataclass(frozen=True)
class SupervisorQueue:
    """`U7`. Approvals, blocked cases, closures verification has not cleared — and `RC9`.

    `condition_cleared` and `untouched` are **separate fields and there is deliberately no
    combined total**. A property summing them would be one edit away from a screen on which a
    fixed machine and a forgotten one look identical, which is the failure `RC9` exists for.
    """

    approvals: tuple[ApprovalRow, ...]
    blocked: tuple[BlockedRow, ...]
    closures: tuple[ClosureRow, ...]
    condition_cleared: tuple[AgeingRow, ...]
    untouched: tuple[AgeingRow, ...]
    withheld: tuple[SectionAdmission, ...]
    unreadable: tuple[UnreadableCase, ...]
    order_reason: str = QUEUE_ORDER_REASON

    @property
    def ageing_was_examined(self) -> bool:
        """Whether anybody read `RC9`'s verdicts at all.

        Derived from the admission rather than stored, so it cannot drift from the reason the
        section is missing. `RC9`'s rows are gathered under the blocked section, so when that
        section is withheld nothing looked at ageing — which is not the same fact as nothing
        having aged.
        """
        return not any(a.section is Section.BLOCKED for a in self.withheld)

    def render_ageing(self) -> str:
        """The two kinds, in two clauses. Never one number, and never a confident nought.

        A withheld section is reported as *not checked*. Saying "no case has aged" to a reader
        who was never allowed to look is the twenty-two episodes again: the surface reads calm
        because nothing was examined, not because nothing is wrong.
        """
        if not self.ageing_was_examined:
            return (
                "not checked: this identity does not hold 'approve_work', so no case's RC9 "
                "verdict was read. This is not a statement that nothing has aged."
            )
        parts = []
        if self.condition_cleared:
            parts.append(
                f"{len(self.condition_cleared)} case(s) where the condition cleared and "
                f"somebody has to say whether that was the repair"
            )
        if self.untouched:
            parts.append(f"{len(self.untouched)} case(s) nobody has touched")
        return "; ".join(parts) if parts else "no case has aged"


def supervisor_queue(
    cases: Sequence[CaseRecord],
    capabilities: frozenset[Capability],
    *,
    blocking_reasons: Mapping[str, str] | None = None,
    verifications: Mapping[str, Verification] | None = None,
) -> SupervisorQueue:
    """`U7`. What is waiting on a named human, arranged by capability rather than by rank.

    `blocking_reasons` maps a seed key to the words `app.domain.cases.may_advance` produced.
    It is passed in rather than recomputed because the checklist and its findings belong to the
    case surface — recomputing here would be a second opinion on `RC5`, and two answers to one
    question is how a gate quietly starts disagreeing with itself. A case with no entry is
    reported as **not evaluated**, which is not the same as clear.

    `verifications` maps a seed key to `V1`'s outcome. Absent means nobody ran the check, and
    that is a different row from a check that ran and could not decide.

    The stale rows come from the row's own `RC9` verdict rather than from a recomputed
    interval: `Q56` owns how long a case may sit, `app/db/case_store.py` applies it, and asking
    the same question twice is how two parts of one product start disagreeing about which
    cases are old.
    """
    known, unreadable = _readable(cases)
    admissions = tuple(admission(s, capabilities) for s in SECTIONS_OF[Surface.SUPERVISOR_QUEUE])
    withheld = tuple(a for a in admissions if not a.admitted)
    granted = {a.section for a in admissions if a.admitted}

    ordered = sorted(known, key=lambda pair: _order_key(pair[0]))
    held = frozenset(c.value for c in capabilities)

    approvals: tuple[ApprovalRow, ...] = ()
    blocked: tuple[BlockedRow, ...] = ()
    cleared: tuple[AgeingRow, ...] = ()
    untouched: tuple[AgeingRow, ...] = ()
    closures: tuple[ClosureRow, ...] = ()

    if Section.AWAITING_APPROVAL in granted:
        approvals = tuple(_approval(row, state, held) for row, state in ordered
                          if state in PENDING_ON_AN_APPROVER)

    if Section.BLOCKED in granted:
        blocked = tuple(
            _blocked(row, state, blocking_reasons or {})
            for row, state in ordered
            if state is CaseState.AWAITING_FINDINGS
        )
        cleared = tuple(_ageing(row, AgeingKind.CONDITION_CLEARED) for row, _ in ordered
                        if row.condition_cleared)
        untouched = tuple(_ageing(row, AgeingKind.UNTOUCHED) for row, _ in ordered
                          if row.stale_at is not None and not row.condition_cleared)

    if Section.UNCLEARED_CLOSURES in granted:
        checked = verifications or {}
        closures = tuple(
            _closure(row, checked)
            for row, state in ordered
            if state is CaseState.ACTIONED and not _has_cleared(row, checked)
        )

    return SupervisorQueue(
        approvals=approvals,
        blocked=blocked,
        closures=closures,
        condition_cleared=cleared,
        untouched=untouched,
        withheld=withheld,
        unreadable=unreadable,
    )


def _approval(row: CaseRecord, state: CaseState, held: frozenset[str]) -> ApprovalRow:
    """One approval, ruled on by `G3` rather than by this module.

    The ruling is carried whole. `NEEDS_APPROVAL` is not a refusal — somebody down the
    corridor can sign — and flattening it to a boolean would tell a reader to give up.
    """
    pending = PENDING_ON_AN_APPROVER[state]
    ruling = authority.rule(
        authority.Action(name=pending.name, risk=pending.risk, target=row.seed_key),
        held,
    )
    return ApprovalRow(
        seed_key=row.seed_key,
        equipment_key=row.equipment_key,
        fault_label=row.fault_label,
        day=row.day,
        state=state,
        asks=pending.asks,
        ruling=ruling,
        task_is_a_question=pending.task_is_a_question,
    )


def _blocked(row: CaseRecord, state: CaseState, reasons: Mapping[str, str]) -> BlockedRow:
    """A blocked case, or a case whose blocking status nobody has evaluated."""
    words = reasons.get(row.seed_key)
    if words is None:
        return BlockedRow(
            seed_key=row.seed_key,
            equipment_key=row.equipment_key,
            fault_label=row.fault_label,
            day=row.day,
            state=state,
            kind=Blocked.NOT_EVALUATED,
            reason=(
                "No blocking-check evaluation was supplied for this case, so whether it can "
                "move is not known. That is an absence, not a clear pass — six 'N/A' presses "
                "once opened a blocking gate with zero evidence behind it."
            ),
        )
    return BlockedRow(
        seed_key=row.seed_key,
        equipment_key=row.equipment_key,
        fault_label=row.fault_label,
        day=row.day,
        state=state,
        kind=Blocked.UNSETTLED_BLOCKING_CHECK,
        reason=words,
    )


def _has_cleared(row: CaseRecord, verifications: Mapping[str, Verification]) -> bool:
    """Whether verification has cleared this closure, which is what keeps it out of `U7`.

    The section is *closures verification has not cleared*. A `PASS` has cleared, so it does
    not belong here — and it must not be folded into `VERIFIED_UNKNOWN`, because *the check
    ran and proved it* and *the check ran and could not decide* are the two answers `V1` is
    built to keep apart. Collapsing them tells a supervisor a proven repair is undecided.
    """
    result = verifications.get(row.seed_key)
    return result is not None and result.outcome is Outcome.PASS


def _closure(row: CaseRecord, verifications: Mapping[str, Verification]) -> ClosureRow:
    """One closure verification has not cleared, and which of the three it is."""
    result = verifications.get(row.seed_key)
    if result is None:
        return ClosureRow(
            seed_key=row.seed_key,
            equipment_key=row.equipment_key,
            fault_label=row.fault_label,
            day=row.day,
            block=ClosureBlock.NOT_VERIFIED,
            reason=(
                "The work is raised and done and nothing has been checked. A case cannot "
                "close unproven: the closure note does not decide this and neither does the "
                "technician's opinion — post-work residuals against this asset's own band do."
            ),
            outcome="no verification has been run against this case",
        )

    if result.outcome is Outcome.PASS:
        # Unreachable through `supervisor_queue`, which filters these out. Raising rather than
        # rendering, because there is no honest row for a cleared closure in a section of
        # uncleared ones — and the previous `else` arm printed "could not decide" over an
        # outcome field that said PASS, which is a lie a reader has no way to catch.
        raise ValueError(
            f"{row.seed_key} verified PASS; a cleared closure is not an uncleared one and has "
            f"no row in this section"
        )
    block = (
        ClosureBlock.VERIFIED_FAIL
        if result.outcome is Outcome.FAIL
        else ClosureBlock.VERIFIED_UNKNOWN
    )
    reason = (
        "The check ran and says what was measured is still not fixed."
        if block is ClosureBlock.VERIFIED_FAIL
        else (
            "The check ran and could not decide. UNKNOWN is a permitted outcome and it does "
            "not close the job — treating no evidence of a problem as evidence of no problem "
            "is the shortcut this gate exists to refuse."
        )
    )
    return ClosureRow(
        seed_key=row.seed_key,
        equipment_key=row.equipment_key,
        fault_label=row.fault_label,
        day=row.day,
        block=block,
        reason=reason,
        outcome=f"{result.outcome.value}: {result.reason}",
    )


def _ageing(row: CaseRecord, kind: AgeingKind) -> AgeingRow:
    """One aged case. The reason is `RC9`'s own words off the row, never a fresh judgement."""
    return AgeingRow(
        seed_key=row.seed_key,
        equipment_key=row.equipment_key,
        fault_label=row.fault_label,
        day=row.day,
        kind=kind,
        reason=row.stale_reason or "this case aged and no reason was recorded against it",
        action=ACTION_FOR[kind.value],
    )


# ── shared ──────────────────────────────────────────────────────────────────────

def _readable(
    cases: Sequence[CaseRecord],
) -> tuple[tuple[tuple[CaseRecord, CaseState], ...], tuple[UnreadableCase, ...]]:
    """Split the rows the state machine recognises from the ones it does not.

    A row with an unknown state is reported rather than raised on and rather than dropped: a
    crash takes the whole queue down for one bad string, and a silent drop is the twenty-two
    episodes again, one layer up.
    """
    known: list[tuple[CaseRecord, CaseState]] = []
    unreadable: list[UnreadableCase] = []
    for row in cases:
        try:
            known.append((row, CaseState(row.state)))
        except ValueError:
            unreadable.append(
                UnreadableCase(
                    seed_key=row.seed_key,
                    state=row.state,
                    reason=(
                        f"{row.state!r} is not a state the case machine knows, so this case "
                        f"was not placed in any section. It is listed here rather than "
                        f"dropped — a case that vanishes because a string did not parse is a "
                        f"queue that looks calm and is not."
                    ),
                )
            )
    return tuple(known), tuple(unreadable)


def _order_key(row: CaseRecord) -> tuple[date, str, str]:
    """Oldest first, then stable. See `QUEUE_ORDER_REASON` for what this order does not claim."""
    return row.day, row.equipment_key, row.fault_label
