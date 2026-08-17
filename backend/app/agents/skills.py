"""The skill dispatch — `C3`'s other half, and the end of the fall-through.

**The gap this closes, stated plainly.** `SESSION-HANDOFF.md` §8 has said since M1 that *five
of seven skills route correctly then fall into the same explain path*. The routing ladder was
never the problem: it resolves `look_up`, `prepare_work`, `resolve` and `verify` correctly and
carries the skill into the route frame, so the Inspector showed a skill the turn then ignored.
A router whose decision changes nothing is a router that only looks like one.

**What each skill actually needs already exists.** Every service below was built and tested
milestones ago and reachable from nothing:

| Skill | Reaches | Built in |
|---|---|---|
| `look_up` | the pack's figures, exact, no prose | `C17` · `C21` |
| `explain` | the model, over the pack | `C5` |
| `investigate` | the pack plus the same day's other labels and the differential | `C4` · `C6` |
| `prepare_work` | `work_orders.draft_from_pack` | `W2`–`W4` |
| `resolve` | `cases.case_from_pack` | `RC1`–`RC5` |
| `verify` | `analytics.verification` | `V1`–`V4` |

**Four of the six need no model at all**, and that is the point rather than a limitation. A
look-up that asked a model to read a number back would be the one place `C21`'s figure
discipline could not hold — only `FigureView` renders a number, and it never formats. So
`look_up` returns the pack's display strings untouched and `used_model` is `False`, which the
route trace shows.

**Nothing here decides anything.** Each branch composes services that already own their rules:
`may_advance` still owns the blocking gate, the priority formula still owns priority, the
gates still decide whether anything may be diagnosed at all. This module chooses *which
question is being answered*, which is exactly what the separation law leaves to routing.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain import differential as diff
from app.domain.answer import AnswerState
from app.domain.cases import Capability
from app.services.cases import case_from_pack
from app.services.evidence import EvidencePack
from app.services.work_orders import draft_from_pack


@dataclass(frozen=True)
class SkillOutcome:
    """What a deterministic skill produced. `None` text means *fall through to explain*."""

    state: AnswerState
    text: str
    used_model: bool = False
    payload: dict | None = None

    @property
    def is_terminal(self) -> bool:
        return bool(self.text)


def _evidence_line(evidence) -> str:
    """One residual, rendered as the pack rendered it.

    **Nothing is reformatted here.** `ResidualEvidence.render()` already produces the string
    the pack carries, and the pack carries display strings rather than floats precisely so the
    numeric audit can compare exact values. Re-rendering would reintroduce a tolerance, and
    every tolerance forgives some fabrication.
    """
    return evidence.render()


def look_up(pack: EvidencePack) -> SkillOutcome:
    """`C17`. The exact numbers, and **no model is spent**.

    A look-up that routed through a model would put a language model between a reader and a
    figure, which is the one place `C21`'s discipline cannot survive: the model would have to
    reproduce the string, and reproducing a number is where a number gets rounded.
    """
    evidence = pack.residual_evidence
    lines = [_evidence_line(e) for e in evidence]
    absences = sum(1 for e in evidence if e.figure.value is None)

    body = "\n".join(lines) if lines else "This episode carries no residual evidence."
    note = (
        f"\n\n{absences} of {len(evidence)} figures are a stated absence rather than a "
        f"value. An absence is not a zero."
        if absences
        else ""
    )
    return SkillOutcome(
        state=AnswerState.ANSWERED,
        text=(
            f"{pack.equipment_display} on {pack.window.render()}, read straight from the "
            f"evidence:\n\n{body}{note}"
        ),
        used_model=False,
        payload={"figures": [e.figure.as_dict() for e in pack.residual_evidence]},
    )


def investigate(pack: EvidencePack) -> SkillOutcome:
    """`C4`/`C6`. What else was true that day, and whether the class can be narrowed at all.

    Falls through to `explain` for the prose — the enquiry is deterministic, the explanation
    is not. What it adds is the two facts a single-label answer hides: the other labels on the
    same machine that day, and whether this class even *qualifies* for a differential.
    """
    others = pack.other_labels_same_day
    label = pack.fault_label or ""
    qualifies = diff.has_differential(label)
    authored = diff.differential_for(label) is not None

    lines = [
        f"Investigating {label or 'an unlabelled slot'} on {pack.equipment_display}, "
        f"{pack.window.render()}."
    ]
    if others:
        lines.append(
            f"The same machine carried {len(others)} other label(s) that day: "
            f"{', '.join(others)}. One repair may explain several — a reader who does not "
            f"know that raises several jobs."
        )
    else:
        lines.append("No other label was recorded on this machine that day.")

    if not qualifies:
        lines.append(
            "This class names a mechanism, so it does not get a differential — narrowing it "
            "would invent ambiguity the trained model never reported."
        )
    elif not authored:
        lines.append(
            "This class declares itself undecidable and qualifies for a differential, but no "
            "candidate set has been authored for it yet. That is missing content, not an "
            "absence of ambiguity."
        )
    else:
        lines.append(
            "This class declares itself undecidable and has a differential — the candidates "
            "can be narrowed by asking, once the discriminators have been reviewed."
        )

    return SkillOutcome(
        state=AnswerState.PARTIAL if not pack.may_diagnose else AnswerState.ANSWERED,
        text="\n\n".join(lines),
        used_model=False,
        payload={
            "other_labels_same_day": list(others),
            "qualifies_for_differential": qualifies,
            "differential_authored": authored,
        },
    )


def prepare_work(pack: EvidencePack) -> SkillOutcome:
    """`W2`–`W4`. A draft carrying its own justification, and it says it is a draft.

    `NEEDS_APPROVAL` rather than `ANSWERED`: nothing is persisted and nobody has approved it.
    A work order that reads as dispatchable when it is not is worse than none, because
    somebody plans against it.
    """
    draft = draft_from_pack(pack)
    priority = draft.priority

    # `missing` is (name, reason) pairs rather than bare names, deliberately: `W4`'s formula
    # spans criticality, SLA and production impact, and three of the four inputs do not exist
    # in this snapshot (`Q51`). Naming the input without the reason would read as an omission
    # somebody could fill in, when it is an absence in the plant's records.
    absent = ", ".join(name for name, _ in priority.missing)
    incomplete = (
        f" The priority is incomplete — {absent} do not exist in this snapshot, so it is "
        f"reported with what was used rather than as a finished rank."
        if not priority.is_complete
        else ""
    )
    return SkillOutcome(
        state=AnswerState.NEEDS_APPROVAL,
        text=(
            f"{draft.title}\n\nPriority {priority.band}. {len(draft.evidence)} evidence "
            f"line(s) travel with this job, each naming its source.{incomplete}\n\n"
            f"This is a draft. Nothing is persisted and nobody has approved it."
        ),
        used_model=False,
        payload=draft.as_dict(),
    )


def resolve(pack: EvidencePack) -> SkillOutcome:
    """`RC1`–`RC5`. Open the case and report whether it may advance — usually it may not.

    Two thirds of measured cases pause: 26 of 43 stop at the checks. So the common outcome
    here is `BLOCKED` with the reason, and that is the feature rather than a shortfall.
    """
    case = case_from_pack(pack)
    return SkillOutcome(
        state=AnswerState.ANSWERED if case.may_advance else AnswerState.BLOCKED,
        text=(
            f"Case {case.id} is {case.state.value}. {case.advance_reason}\n\n"
            f"The checklist content is sample content and every surface says so — the curated "
            f"library is unreviewed, so no real item is shown to anyone yet."
        ),
        used_model=False,
        payload=case.as_dict(Capability.TECHNICIAN),
    )


def verify(pack: EvidencePack) -> SkillOutcome:
    """`V1`–`V4`. Refuses rather than guessing, and the refusal is the honest answer.

    Verification compares post-work residuals against this asset's own band. A turn asking to
    verify from an episode alone has no *after* window, and inventing one would be the failure
    `V1` exists to prevent: a label disappearing looked like a successful repair while the
    residual got worse, because the gates had stopped passing and nothing was being judged.
    """
    return SkillOutcome(
        state=AnswerState.BLOCKED,
        text=(
            "Verification needs a post-work window to compare against, and this request "
            "carries only the episode. A label that has stopped appearing is not evidence "
            "that a repair worked — on this plant a class disappeared after 2026-04-22 and "
            "never returned while the residual got worse over the following week, because the "
            "gates had stopped passing and nothing was being judged at all.\n\n"
            "Close the work order through the verification surface, which reads the after "
            "window."
        ),
        used_model=False,
    )


#: The dispatch. Held as a table rather than a chain of `if`s so a skill that is routed but
#: not dispatched is a missing key somebody can see, rather than a silent fall-through — which
#: is precisely how five skills went a milestone without one.
DETERMINISTIC_SKILLS = {
    "look_up": look_up,
    "investigate": investigate,
    "prepare_work": prepare_work,
    "resolve": resolve,
    "verify": verify,
}


def dispatch(skill: str, pack: EvidencePack) -> SkillOutcome | None:
    """Run the skill's own path, or `None` when it is `explain` and belongs to the model.

    Never raises. A skill that fails is a turn outcome, not a crash — the router's rule, one
    layer along.
    """
    handler = DETERMINISTIC_SKILLS.get(skill)
    if handler is None:
        return None
    try:
        return handler(pack)
    except Exception as exc:
        return SkillOutcome(
            state=AnswerState.FAILED,
            text=(
                f"The {skill} skill could not complete: {type(exc).__name__}: {exc}. "
                f"Nothing was assumed in its place."
            ),
            used_model=False,
        )
