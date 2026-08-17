"""A library item that cannot name its source is indistinguishable from model output.

**The failure this prevents.** Inherited constraint 1 says the checklist library is curated
content, never model output, and constraint 26 says the language model selects and
contextualises library content but never authors a field instruction. Both are unenforceable
against a bare string. Six months from now, an item reading *"Read the field device
directly"* is either a refrigeration engineer's instruction or something a model produced on
a Tuesday, and nothing in the string says which. So provenance is a field rather than a
convention: `CuratedItem` carries the file, the part, the heading and the fault label it was
transcribed from, and refuses to be constructed without them.

**Two facts about a transcribed item, kept apart on purpose.**

`is_sample` means *invented to demonstrate the mechanism* — that is what it means in
`app/services/cases.py`, and widening it would destroy the only flag that currently
distinguishes demonstration content from the real thing. A curated item is never a sample, so
`is_sample=True` is refused at construction. `sme_reviewed` is the other fact: no
refrigeration engineer has read any of this. It is left as the dataclass default `False` and
asserted by test rather than forbidden here, because the review is going to happen and its
outcome has to be representable.

**Where the text ends and our tagging begins.** The instruction text comes from one document;
the role tag and the blocking flag come from another. They are recorded as two separate
sources because they were two separate human judgements, and a reviewer who disagrees with a
role tag is disagreeing with `17-role-tags-every-check.md`, not with the instruction.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.cases import ChecklistItem


@dataclass(frozen=True)
class CuratedItem(ChecklistItem):
    """One item copied verbatim out of a review document, with where it came from.

    Extends `ChecklistItem` rather than wrapping it so every existing accessor —
    `Checklist.visible_items`, `for_capability`, `blocking_items`, `at_stage` — keeps working
    unchanged. In particular the SME gate in `visible_items` applies to curated items exactly
    as it applies to anything else, which is what makes the unreviewed library safe to hold in
    code at all.
    """

    source_file: str = ""
    """The document the instruction text was transcribed from."""

    source_part: str = ""
    """The part heading within that document, verbatim."""

    source_heading: str = ""
    """The fault-class heading the item sits under, verbatim. For content that belongs to no
    class, this repeats the part heading — see `source_fault_label`."""

    source_fault_label: str | None = None
    """The fault label the source attributes the item to, or `None` for content the source
    explicitly attaches to no class. `None` means **unattributed**, never *"we did not look"*."""

    role_tag_file: str = ""
    """The document the `capability` and `blocking` values came from. A different judgement by
    a different author from the instruction text, so it is recorded separately."""

    source_note: str = ""
    """The italic rationale the source prints under the item, verbatim. The enclosing markdown
    emphasis markers are dropped as formatting; not one word of the text is changed. Empty
    means the source printed no note — not that the note was thought unnecessary."""

    settles_it: bool | None = None
    """Did the source mark this item `[SETTLES IT]` — the check asked first because it is
    believed to discriminate between the candidate causes?

    `None` means the document that carries that marker does not cover this item, which is a
    different fact from the document covering it and leaving it unmarked. Kept separate from
    `blocking` because the two documents define them differently: `[SETTLES IT]` is a belief
    about discriminating power, `BLOCKING` is *the case cannot be root-caused until a human
    answers*. They happen to coincide on every item transcribed so far, and merging them on
    that evidence would erase a distinction the sources drew deliberately."""

    capability_defaulted: bool = False
    """`True` when the source gave no role tag and constraint 24's technician default applied.
    Recorded rather than inferred: a defaulted tag is a gap in the source, and a reviewer has
    to be able to see which tags are the author's and which are ours."""

    def __post_init__(self) -> None:
        missing = [
            name
            for name in ("source_file", "source_part", "source_heading", "role_tag_file")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                f"curated item {self.id!r} cannot name its source ({', '.join(missing)}). "
                f"An item with no provenance is indistinguishable from model output, which "
                f"is what inherited constraint 1 forbids."
            )
        if self.is_sample:
            raise ValueError(
                f"curated item {self.id!r} is flagged is_sample. `is_sample` means invented "
                f"to demonstrate the mechanism; this item was transcribed from "
                f"{self.source_file}. Those are different facts and both are needed."
            )

    @property
    def provenance(self) -> str:
        """One line a reviewer can check against the document in front of them."""
        where = self.source_fault_label or "no fault class"
        return (
            f"{self.source_file} · {self.source_part} · “{self.source_heading}” "
            f"[{where}] · role tag from {self.role_tag_file}"
        )
