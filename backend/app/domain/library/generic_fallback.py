"""An uncurated fault label must not arrive at an empty screen — and must not borrow a class.

**The failure this content prevents.** A label the library was never curated for — a new
class from the trained model, or a z-score anomaly on a site with no trained model at all —
would otherwise reach a person with nothing attached to it. Seven items exist for exactly
that case, and `17-role-tags-every-check.md` Part 3 says what they are for:

> Used when a fault label arrives that this library has **not** been curated for — a new class
> from the model, or a z-score anomaly on a site with no trained model. It always routes to a
> human.

**The second failure is the reason this is its own module.** The obvious way to give an
uncurated label some checks is to lend it the nearest class's list. That would attribute a
refrigeration engineer's judgement about *condenser fouling* to a fault nobody has looked at,
and the attribution is invisible once the items are on a screen. So these seven belong to no
class: `source_fault_label` is `None` on every one of them, `fallback_checklist_for` records
the arriving label on the `Checklist` while leaving the items unattributed, and a test asserts
the difference.

**This is the 7 that makes the honest count 124 + 7.** *"131 items across 11 fault classes"*
is the imprecise phrasing, and the imprecision is not cosmetic: it counts seven unattributed
items inside a per-class total, so any per-class arithmetic done against 131 is wrong by
seven. The source is explicit — *"This is the 7 that makes the total 131 rather than 124. It
is not attached to any of the 11 classes above."*

**Transcription, not authorship.** All seven come from `17-role-tags-every-check.md` Part 3,
text and role tag alike — it is the only document that carries them; they are not in
`05-checklist-library-for-review.md`. Nothing is reworded and nothing is added.
`sme_reviewed=False` throughout, so `Checklist.visible_items` shows none of them.

**The source asks whether this feature should exist at all**, and that question is carried
here verbatim as `OPEN_REVIEW_QUESTION` rather than answered.
"""
from __future__ import annotations

from app.domain.cases import Capability, Checklist, Stage
from app.domain.library.curated import TranscribedItem

#: The only document that carries these seven. Text and role tag come from the same place,
#: which is why both source fields name it.
SOURCE = "thermynx/docs/for-vishnu/17-role-tags-every-check.md"

PART = "Part 3 — The generic fallback (7 items)"

#: There is no fault-class heading above these items — the part heading *is* the heading, and
#: that is the point. Recorded so `TranscribedItem.provenance` still names a real place in the
#: document rather than an invented one.
HEADING = PART

#: The source's own review question, verbatim. Not answered here: whether an uncurated fault
#: should offer generic checks or refuse to offer any is a judgement about what a person does
#: at a machine, which is exactly the judgement the review exists to make.
OPEN_REVIEW_QUESTION = (
    "Is a generic fallback the right behaviour at all, or should an uncurated fault refuse "
    "to offer checks?"
)

#: What the source says the fallback always does. Carried because it is the one behavioural
#: promise the fallback makes.
ALWAYS_ROUTES_TO_A_HUMAN = True

#: The count the source states, and the count it corrects. Both are quoted rather than derived
#: so a future edit that changes the item list fails the test rather than the documents.
CURATED_ITEM_COUNT = 124
"""Items across the 11 fault classes, per `05-checklist-library-for-review.md`."""

FALLBACK_ITEM_COUNT = 7
"""Items attached to no class. `124 + 7` is the honest count; `131 across 11 classes` is not."""


def _item(
    stage: Stage,
    n: int,
    text: str,
    capability: Capability,
    *,
    blocking: bool = False,
) -> TranscribedItem:
    """One fallback item.

    `source_fault_label` is left at `None` — the field's absence is the fact being recorded.
    `settles_it` is left at `None` too: the `[SETTLES IT]` marker lives in
    `05-checklist-library-for-review.md`, which does not carry these seven at all, so the
    honest value is *"the document that marks it does not cover this item"* rather than
    `False`.
    """
    return TranscribedItem(
        id=f"fallback-{stage.value}-{n}",
        text=text,
        capability=capability,
        blocking=blocking,
        stage=stage,
        source_file=SOURCE,
        source_part=PART,
        source_heading=HEADING,
        source_fault_label=None,
        role_tag_file=SOURCE,
    )


FALLBACK_ITEMS: tuple[TranscribedItem, ...] = (
    _item(
        Stage.RCA, 1,
        "Confirm the anomaly against the panel / BMS reading",
        Capability.OPERATOR,
        blocking=True,
    ),
    _item(
        Stage.RCA, 2,
        "Inspect the unit for any obvious abnormality — noise, leak, vibration, heat",
        Capability.OPERATOR,
        blocking=True,
    ),
    _item(
        Stage.RCA, 3,
        "Compare current operating parameters against design",
        Capability.OPERATOR,
    ),
    _item(
        Stage.RCA, 4,
        "Check recent operating and service history for this unit",
        Capability.SUPERVISOR,
    ),
    _item(
        Stage.CORRECTIVE, 1,
        "Address the cause identified by inspection",
        Capability.TECHNICIAN,
    ),
    _item(
        Stage.CORRECTIVE, 2,
        "Verify the parameter returns to its expected range",
        Capability.OPERATOR,
    ),
    _item(
        Stage.PREVENTIVE, 1,
        "Add the affected parameter to the PM round",
        Capability.SUPERVISOR,
    ),
)


def fallback_checklist_for(fault_label: str | None) -> Checklist:
    """The seven items, carried under whichever uncurated label arrived.

    The label goes on the `Checklist`; it never goes on the items. A reader looking at the
    case sees which fault brought them here, and a reader looking at an item still sees that
    nobody curated it for this class — which is the distinction that stops borrowed content
    reading as curated content.

    Every item is `sme_reviewed=False`, so `visible_items` is empty and the fallback shows
    nobody anything today. That is the same gate as everywhere else in the library, and the
    same desired state.
    """
    return Checklist(fault_label=fault_label or "unlabelled", items=FALLBACK_ITEMS)


def unreviewed_count() -> int:
    return sum(1 for item in FALLBACK_ITEMS if not item.sme_reviewed)


def honest_total() -> int:
    """`124 + 7`. Stated as a sum because the two halves are counted differently."""
    return CURATED_ITEM_COUNT + FALLBACK_ITEM_COUNT


def count_note() -> str:
    """Why the round number in circulation is the wrong shape, in one sentence."""
    return (
        f"{honest_total()} items in total: {CURATED_ITEM_COUNT} across the 11 fault classes "
        f"plus {FALLBACK_ITEM_COUNT} attached to no class. Reporting it as "
        f"'{honest_total()} across 11 fault classes' folds the unattributed seven into a "
        f"per-class total, so any per-class arithmetic against that figure is wrong by "
        f"{FALLBACK_ITEM_COUNT}."
    )
