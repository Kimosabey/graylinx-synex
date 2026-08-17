"""`RC6` both follow-up checklists · `RC11` a preventive item becomes an owned obligation.

**The failure this exists to prevent.** The curated library is 124 items across 11 fault
classes, split **57 RCA · 37 corrective · 30 preventive**, of which **24 are blocking**. A
case that records a confirmed cause and attaches only the repair fixes the machine and leaves
those 30 preventive items as content nobody ever opens. The condenser is cleaned; nothing
changes the interval that let it foul, and the same case is opened again next quarter. So
`RC6` attaches **both** follow-up stages, and an empty one is attached with its absence in
words rather than left as a blank the reader reads as *nothing needed*.

**Where the preventive stage lands, and why that is a queue problem.** Role tags across the
same 124 items are **technician 49 · supervisor 38 · operator 29 · maintenance 7 · vendor 1**,
and supervisor's 31% is almost entirely the preventive stage — intervals, schedules, trends.
Prevention is a records-and-authority activity, so that is right in principle. It also means
the preventive stage lands on the one role that had **no queue to receive it**, which is why
`U7` exists. `RC11` is the other half of that: a preventive item becomes a recurring
commitment with a **named approver**, because a preventive line with no owner and no date is
not prevention, it is a sentence.

**Constraint 13 and 25 are the reason the approver is named rather than ranked.** A
supervisor is not a more capable technician; it is a different capability — authority and
records, not gauges. Ranking by seniority once sent a filter-drier restriction to a supervisor
because one incidental records question outranked three refrigeration measurements. So this
module asks for a *capability* and picks the person by **workload**, and it deliberately drops
the "ties break toward whoever can measure" rule that `RC16` uses — see `choose_approver`.

**Constraint 1 and 26 hold throughout.** Every item here comes from the curated library; the
language model selects and contextualises library content and never authors a field
instruction. Nothing in this module calls a model, and nothing in it is generated: it moves
curated items between stages and attaches an owner to them. `RC6` is `SW + R`, `RC11` is `SW`.

**Nothing unreviewed reaches anyone.** The follow-ups are drawn through `visible_items`, so
the SME gate that guards the diagnostic checklist guards the corrective and preventive ones by
the same mechanism — and the withheld count is reported rather than dropped.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.cases import Capability, Checklist, ChecklistItem, Stage
from app.domain.escalation import Candidate

# ── the curated library, as measured ───────────────────────────────────────────────────────
# CONTEXT §10a. These are counts of content that exists, not thresholds and not estimates.

#: 57 + 37 + 30 = 124 items across 11 fault classes. The 7-item generic fallback belongs to no
#: class and is deliberately outside this split — "131 across 11 classes" is the imprecise
#: phrasing CONTEXT calls out, and restating it here would propagate it.
LIBRARY_STAGE_SPLIT: dict[Stage, int] = {
    Stage.RCA: 57,
    Stage.CORRECTIVE: 37,
    Stage.PREVENTIVE: 30,
}

#: 24 of the 124 are blocking. **How those 24 fall across the three stages is not recorded
#: anywhere** — TBD (Q63). Nothing here guesses at it: `Checklist.blocking_items` reads the
#: per-item flag, and `library_stage_report` states the split as unknown rather than deriving
#: a plausible one. It matters because a blocking *corrective* item gates a case that already
#: has its cause, which is a different stall from one that gates the diagnosis.
BLOCKING_ITEMS_IN_LIBRARY: int = 24

#: `RC6`'s two stages. RCA is deliberately absent: those are the checks that *produced* the
#: cause, and re-attaching them as follow-up work would ask a technician to re-establish
#: something the case has already settled.
FOLLOW_UP_STAGES: tuple[Stage, ...] = (Stage.CORRECTIVE, Stage.PREVENTIVE)


# ── `RC11`'s two settings, and one of them is a stated absence ──────────────────────────────

#: How often a preventive commitment recurs. **No source fixes this.** Not CONTEXT, not the
#: library, not the reference queue — `RC11` says "recurring" and names no interval.
#:
#: TBD (Q62). The choice made here is `None`, and it is a choice rather than an oversight: a
#: commitment with no interval is still created, still owned and reported as *unscheduled*
#: with the absence in words. A plausible 30 or 90 days would be worse than nothing, because a
#: wrong interval is invisible — it reads as a schedule right up until the thing it was meant
#: to prevent happens. Callers with an agreed interval pass it in.
RECURRENCE_INTERVAL_DAYS: int | None = None

#: The capability an approver must hold. **Not because it is the senior one** — constraints 13
#: and 25: roles are capabilities, not ranks. A preventive obligation is records and authority
#: work, which is what this capability *is*, and the measurement agrees: 38 of the 124 role
#: tags are supervisor and almost all of them sit at this stage.
APPROVER_CAPABILITY: Capability = Capability.SUPERVISOR


@dataclass(frozen=True)
class RootCause:
    """A cause the case has confirmed, and the checks that confirmed it."""

    cause_id: str
    label: str

    confirmed_by: tuple[str, ...] = ()
    """Constraint 31: every verdict records the check and the answer that caused it.
    *"Why did nobody look at the tower?"* needs a better answer than *"the software
    decided"*."""

    siblings_still_live: tuple[str, ...] = ()
    """Constraint 28: **a confirmation never eliminates its siblings.** A fouled condenser on
    a machine that is also low on flow is two real causes, and collapsing to the first
    confirmation is how the second gets missed."""

    @property
    def evidence_note(self) -> str:
        """Always words. An unevidenced confirmation is reported, never silently accepted."""
        if not self.confirmed_by:
            return (
                "this cause was recorded with no check behind it, so nothing here says why it "
                "was confirmed — the follow-ups attach, but the record does not support them"
            )
        return f"confirmed by {len(self.confirmed_by)} check(s): {'; '.join(self.confirmed_by)}"


@dataclass(frozen=True)
class StageAttachment:
    """One follow-up stage, attached to a confirmed cause. Attached even when empty."""

    stage: Stage
    checklist: Checklist
    absence_reason: str = ""
    """Empty **only** when items are actually attached. An absence carries its reason in
    words; an empty list left to speak for itself reads as *nothing to do here*, which is a
    claim about the equipment that no one made."""

    @property
    def items(self) -> tuple[ChecklistItem, ...]:
        """What the reader may see — reviewed items only, through the existing SME gate."""
        return self.checklist.visible_items()

    @property
    def is_empty(self) -> bool:
        return not self.items

    @property
    def withheld_for_review(self) -> int:
        """Items that exist at this stage and have not been read by a refrigeration
        engineer. Counted so the gap is a visible number rather than a silent omission."""
        return self.checklist.unreviewed_count

    @property
    def blocking_items(self) -> tuple[ChecklistItem, ...]:
        return self.checklist.blocking_items()

    def render(self) -> str:
        if self.is_empty:
            return f"{self.stage.value}: {self.absence_reason}"
        blocking = len(self.blocking_items)
        held = (
            f", {self.withheld_for_review} withheld pending review"
            if self.withheld_for_review
            else ""
        )
        return (
            f"{self.stage.value}: {len(self.items)} item(s), {blocking} blocking{held}"
        )


@dataclass(frozen=True)
class FollowUp:
    """`RC6`. What a confirmed cause attaches — both stages, always."""

    cause: RootCause
    attachments: tuple[StageAttachment, ...]

    def for_stage(self, stage: Stage) -> StageAttachment:
        for attachment in self.attachments:
            if attachment.stage is stage:
                return attachment
        raise ValueError(f"{stage.value} is not a follow-up stage")

    @property
    def corrective(self) -> StageAttachment:
        return self.for_stage(Stage.CORRECTIVE)

    @property
    def preventive(self) -> StageAttachment:
        return self.for_stage(Stage.PREVENTIVE)

    @property
    def stages_attached(self) -> tuple[Stage, ...]:
        """Always both. Held as a property rather than assumed, because "we attached the
        repair and there happened to be no preventive item" is the failure `RC6` names."""
        return tuple(a.stage for a in self.attachments)

    @property
    def siblings_note(self) -> str:
        live = self.cause.siblings_still_live
        if not live:
            return "no other candidate cause was left live on this case"
        return (
            f"{len(live)} other cause(s) are still live: {', '.join(live)}. Confirming this "
            f"one attaches its follow-ups and eliminates nothing — a fouled condenser on a "
            f"machine that is also low on flow is two real causes."
        )

    def render(self) -> str:
        lines = [f"{self.cause.label} — {self.cause.evidence_note}."]
        lines.extend(a.render() for a in self.attachments)
        lines.append(self.siblings_note + ".")
        return "\n".join(lines)


def attach_follow_ups(cause: RootCause, library: Checklist) -> FollowUp:
    """`RC6`. Recording a confirmed root cause attaches **both** follow-up checklists.

    Two absences are possible at each stage and they are **not the same absence**, so they
    do not share a sentence:

    * the library carries no item at this stage for this fault class — a gap in the content;
    * items exist and none has been reviewed — a gap in the SME hour, which is a queue that
      will clear.

    Reporting either as "no items" would let a content hole and a review backlog look
    identical on the screen, and only one of them is somebody's next task.
    """
    attachments = []
    for stage in FOLLOW_UP_STAGES:
        narrowed = library.at_stage(stage)
        visible = narrowed.visible_items()
        reason = ""
        if not visible and not narrowed.items:
            reason = (
                f"the curated library carries no {stage.value} item for "
                f"{library.fault_label}. That is a gap in the library, not a statement that "
                f"none is needed."
            )
        elif not visible:
            reason = (
                f"{narrowed.unreviewed_count} {stage.value} item(s) exist for "
                f"{library.fault_label} and none has been read by a refrigeration engineer, "
                f"so none is shown. Nothing is missing from the library; the review is."
            )
        attachments.append(
            StageAttachment(stage=stage, checklist=narrowed, absence_reason=reason)
        )
    return FollowUp(cause=cause, attachments=tuple(attachments))


def library_stage_report() -> str:
    """What the curated library holds per stage, and what is not recorded about it.

    The blocking split is stated as unknown on purpose. Dividing 24 across three stages in
    proportion to their sizes would produce three numbers that look measured and are not.
    """
    parts = ", ".join(f"{count} {stage.value}" for stage, count in LIBRARY_STAGE_SPLIT.items())
    total = sum(LIBRARY_STAGE_SPLIT.values())
    return (
        f"{total} curated items across 11 fault classes: {parts}. "
        f"{BLOCKING_ITEMS_IN_LIBRARY} of them are blocking; how those {BLOCKING_ITEMS_IN_LIBRARY} "
        f"fall across the three stages is not recorded anywhere, and is not estimated here."
    )


# ── `RC11` — the preventive stage becomes an owned, recurring commitment ────────────────────


class CommitmentState(StrEnum):
    """`RC11`. Three states, and only one of them is an obligation."""

    SCHEDULED = "scheduled"
    """Owned by a named person and recurring on an agreed interval. The only state that is
    actually a commitment."""

    UNSCHEDULED = "unscheduled"
    """Owned, but no interval is agreed. `RC11` says "recurring" and no source says how often
    — TBD (Q62). Reported as a distinct state so the missing half is visible rather than
    absorbed into an owner's name."""

    UNOWNED = "unowned"
    """Nobody holds the approving capability, so this is still the line of text `RC11` exists
    to replace. Ranked worst of the three: an obligation with no owner is worse than one with
    no date, because a date without an owner still tells you who to ask and an owner without
    a date does not."""


@dataclass(frozen=True)
class Commitment:
    """One preventive item, with an owner and a recurrence — or with the reason it has
    neither. Never a bare flag, never a blank owner field."""

    item_id: str
    text: str
    state: CommitmentState
    reason: str
    approver: str = ""
    """A person's name. Empty **only** when `state` is `UNOWNED`, and the reason says so."""

    approver_capability: Capability = APPROVER_CAPABILITY
    interval_days: int | None = None
    blocking: bool = False

    @property
    def is_an_obligation(self) -> bool:
        """True only when somebody owns it *and* it recurs. Either half missing leaves it as
        an intention, and calling an intention a commitment is the whole failure."""
        return self.state is CommitmentState.SCHEDULED

    def render(self) -> str:
        return f"{self.text} — {self.reason}"


def choose_approver(candidates: tuple[Candidate, ...]) -> Candidate | None:
    """`RC11`'s named approver. By workload, never by seniority — and never by a model.

    **`RC16`'s "ties break toward whoever can physically measure" is deliberately dropped
    here.** That tie-break exists because the work being handed over is a measurement, and
    the person who can take it should. A preventive commitment is records and authority: an
    interval, a schedule, a trend. Carrying the measuring tie-break across would smuggle a
    gauge criterion into an authority decision, which is constraint 25's failure — treating
    the roles as one ladder — arriving by a quieter door. Ties break on name instead, which
    claims nothing and is reproducible.
    """
    eligible = [c for c in candidates if c.capability is APPROVER_CAPABILITY]
    if not eligible:
        return None
    return min(eligible, key=lambda c: (c.load, c.name))


def commitments_from(
    preventive: Checklist,
    candidates: tuple[Candidate, ...] = (),
    interval_days: int | None = RECURRENCE_INTERVAL_DAYS,
) -> tuple[Commitment, ...]:
    """`RC11`. Turn each visible preventive item into a commitment with a named approver.

    **Only preventive items are considered, whatever is passed in.** A corrective item set to
    recur would repeat a repair on a machine that no longer has the fault, so the stage is
    filtered here rather than trusted from the caller.
    """
    approver = choose_approver(candidates)
    items = [i for i in preventive.visible_items() if i.stage is Stage.PREVENTIVE]

    commitments = []
    for item in items:
        if approver is None:
            state = CommitmentState.UNOWNED
            reason = (
                f"no candidate holds the {APPROVER_CAPABILITY.value} capability, so this "
                f"preventive item has no named approver and remains a line of text nobody "
                f"owns. 38 of the library's 124 role tags sit on this capability and almost "
                f"all of them are preventive — this is the stage that lands on the one role "
                f"with no queue to receive it (`U7`)."
            )
        elif interval_days is None:
            state = CommitmentState.UNSCHEDULED
            reason = (
                f"{approver.name} owns this. No recurrence interval is set: none is recorded "
                f"in any source, and putting a date on a plant obligation nobody agreed to "
                f"would read as a schedule until the thing it prevents happens. TBD (Q62)."
            )
        else:
            state = CommitmentState.SCHEDULED
            reason = (
                f"{approver.name} owns this and it recurs every {interval_days} day(s), on an "
                f"interval that was supplied rather than assumed."
            )
        commitments.append(
            Commitment(
                item_id=item.id,
                text=item.text,
                state=state,
                reason=reason,
                approver=approver.name if approver else "",
                interval_days=interval_days if state is CommitmentState.SCHEDULED else None,
                blocking=item.blocking,
            )
        )
    return tuple(commitments)


def commitments_for(
    follow_up: FollowUp,
    candidates: tuple[Candidate, ...] = (),
    interval_days: int | None = RECURRENCE_INTERVAL_DAYS,
) -> tuple[Commitment, ...]:
    """`RC6` into `RC11`: the commitments the preventive attachment produces."""
    return commitments_from(follow_up.preventive.checklist, candidates, interval_days)


def obligation_gap(
    commitments: tuple[Commitment, ...], unreviewed_preventive: int = 0
) -> tuple[int, int, str]:
    """`(real obligations, items still only text, the gap in words)`.

    The third element is never omitted. A count of zero obligations is the same number
    whether nothing was preventable or nothing was owned, and those are opposite situations.

    **`unreviewed_preventive` exists because an empty result has two causes and they are not
    interchangeable.** Found in adversarial review, 2026-08-17: the empty branch asserted *"no
    preventive item was attached"* outright, and since `sme_reviewed` defaults to `False` and
    nothing in the 124-item library has been read by a refrigeration engineer, that fired for
    **all 30 preventive items** — reporting a content hole where the truth was a review
    backlog. The rest of this module argues at length that the two absences must never look
    identical; this function was the one place that made them identical, and picked the wrong
    one. Pass `Checklist.unreviewed_count` or the preventive subset of it.
    """
    owned = [c for c in commitments if c.is_an_obligation]
    text_only = [c for c in commitments if not c.is_an_obligation]

    if not commitments:
        if unreviewed_preventive:
            return 0, 0, (
                f"{unreviewed_preventive} preventive item(s) exist and none has been read by "
                f"a refrigeration engineer, so none has been turned into a commitment — the "
                f"review is missing, not the content"
            )
        return 0, 0, (
            "no preventive item was attached, so there is nothing to own — this is an "
            "absence of content, not a schedule that came back empty"
        )
    if not text_only:
        return len(owned), 0, (
            f"all {len(owned)} preventive item(s) have a named approver and a recurrence"
        )

    unowned = sum(1 for c in text_only if c.state is CommitmentState.UNOWNED)
    unscheduled = sum(1 for c in text_only if c.state is CommitmentState.UNSCHEDULED)
    return len(owned), len(text_only), (
        f"{len(text_only)} of {len(commitments)} preventive item(s) are not yet an "
        f"obligation: {unowned} have no named approver, {unscheduled} have an owner but no "
        f"agreed interval. Prevention that nobody owns is the failure `RC11` exists to stop, "
        f"so this is reported rather than counted as done."
    )
