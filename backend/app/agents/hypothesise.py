"""When the model cannot decide, name the candidates and the question that would separate them.

**The mode that turns a refusal into the product.** The Resolve design states it in one line —
*"the AI's value is inversely proportional to the model's certainty; a product built only for
Explain is a model viewer"* — and this plant's own fault model agrees: four of its classes admit
in their names that they cannot resolve. `HIGH_HEAD_AMBIGUOUS` is the longest-running class
here and the least informative one.

Until now that produced a refusal. A reader asking about the most common fault on the plant was
told the gates did not pass, which is true and is not an answer: the platform holds five named
candidate causes for that class and five checks that would separate them, and said none of it.

**It answers with a question, and that is the point.** A differential is not a hedge — it is
the shortest route to knowing. Naming five causes and the one reading that eliminates two of
them is more useful to somebody standing at a machine than a confident guess would be, and it
is the only honest thing to offer when the sensors genuinely cannot decide.

**Nothing here diagnoses.** The candidate set and the discriminators are transcribed content;
`differential.py` picks the next question deterministically — the one that could move the most
live candidates, ties broken toward the lowest id so *"why was I asked this first?"* is
answerable from the data. No model chooses a cause, ranks one, or eliminates one.

**No discriminator has been reviewed by a refrigeration engineer, so none is put to anybody.**
`askable` returns nothing and the differential reports `EXHAUSTED` by construction. That is a
worse product and a truthful one — thirty-one causes were once eliminated on the reference
queue by checks nobody had read. So this mode names the causes, names the checks that exist,
and states plainly that they are unreviewed. It is also the clearest possible statement of what
one hour with an SME would unlock.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain import differential as diff
from app.domain.differential import Differential, Outcome


@dataclass(frozen=True)
class Hypothesis:
    """The candidates for one undecidable class, and what would separate them."""

    fault_label: str
    equipment_display: str
    differential: Differential

    @property
    def cause_count(self) -> int:
        return len(self.differential.causes)

    @property
    def has_reviewed_check(self) -> bool:
        return bool(self.differential.askable)

    def render(self) -> str:
        """The hypothesis in words, for somebody who asked what is wrong.

        Ordered the way a reader needs it: what the class means, what could be causing it, what
        would tell them which, and then — never before — what is standing in the way.
        """
        state = diff.start(self.differential)

        causes = "\n".join(f"- {c.text}" for c in self.differential.causes)
        lines = [
            f"The model flagged {self.fault_label} on {self.equipment_display} and this class "
            f"cannot be resolved from the readings alone — that is what its name says. It does "
            f"not mean nothing is known.",
            "",
            f"**{self.cause_count} causes could produce this**",
            causes,
        ]

        question = state.next_question
        if question is not None:
            lines += [
                "",
                "**The check that would narrow it most**",
                f"- {question.text}",
                "",
                f"It is asked first because it can move more of the {self.cause_count} "
                f"candidates than any other available check, not because it is the most "
                f"likely cause.",
            ]
        elif self.differential.questions:
            checks = "\n".join(f"- {q.text}" for q in self.differential.questions)
            lines += [
                "",
                f"**{len(self.differential.questions)} checks exist that would separate these**",
                checks,
                "",
                "None of them has been reviewed by a refrigeration engineer, so none is being "
                "put to anybody. Which test separates two causes is engineering judgement, and "
                "a check nobody has read is a check that could send somebody to open a "
                "pressurised circuit for nothing.",
            ]
        else:
            lines += [
                "",
                "No check has been transcribed for this class yet, so the causes above cannot "
                "be separated from here.",
            ]

        if state.outcome is Outcome.EXHAUSTED and self.differential.questions:
            lines += [
                "",
                "So this stands as a differential rather than a diagnosis. That is a finding, "
                "not a gap in the answer.",
            ]
        return "\n".join(lines)


def for_fault(fault_label: str | None, *, equipment_display: str) -> Hypothesis | None:
    """The hypothesis for this class, or `None` when it does not have one.

    `None` covers two different situations and neither should be dressed as a differential: a
    class that names a mechanism does not need one, and a class that declares itself
    undecidable but has no candidate set authored yet is missing content. Both are reported by
    the caller in their own words rather than collapsed into a hedge here.
    """
    if not fault_label:
        return None
    authored = diff.differential_for(fault_label)
    if authored is None:
        return None
    return Hypothesis(
        fault_label=fault_label,
        equipment_display=equipment_display,
        differential=authored,
    )
