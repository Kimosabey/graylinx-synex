"""`RC12`–`RC14` on the wire — candidates narrowing, and eliminations that carry their reason.

**The most dangerous content in the programme, exposed with that fact attached.** Thirty-one
causes have already been eliminated on the reference queue, every one by a discriminator no
refrigeration engineer has reviewed. Elimination is irreversible and nobody re-examines a
settled question, so a wrong discriminator does not produce a wrong answer once — it produces
a **confident wrong answer that is never revisited**.

That shapes this route rather than merely being noted by it:

| | What the wire carries | Why |
|---|---|---|
| 31 | Every elimination ships **the question, the answer and the cause** | *"Why did nobody
  look at the tower?"* deserves better than *"the software decided"* |
| 30 | *Can't tell* is present on every question with **empty effects** | Otherwise uncertainty
  silently eliminates something |
| 32 | `settled` and `exhausted` are **different states**, never one flag | Running out of
  questions establishes *"we cannot separate these"*, which is not a conclusion |
| 27 | Only a class the model declares undecidable has one at all | Narrowing a class that
  already names a mechanism invents ambiguity the model never reported |

**Stateless, and that is deliberate.** Each request carries the answers given so far and the
state is replayed from them. A server-side session would make an irreversible elimination
depend on a cookie, and *"the software decided and then forgot why"* is the one failure this
feature cannot have. Replay also means the elimination audit is reconstructed from the same
inputs every time rather than trusted from storage.

**Today every differential reports `EXHAUSTED` before a single question is asked**, because
`Differential.askable` returns only SME-reviewed questions and none is reviewed. The route
says so in words instead of returning an empty list — an empty candidate set reads as
*"nothing to investigate"*, which is the opposite of the truth.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain import differential as diff
from app.domain import faults

router = APIRouter(prefix="/api/v1", tags=["differential"])


class Answer(BaseModel):
    """One answer already given. Replayed in order to rebuild the state."""

    question_id: str
    answer_key: str


class DifferentialRequest(BaseModel):
    fault_label: str
    answers: list[Answer] = Field(default_factory=list)


def _cause_payload(state: diff.DifferentialState) -> list[dict]:
    """Every cause the differential started with — **live and eliminated alike**.

    Returning only the survivors would make the screen a list that mysteriously shrinks.
    Constraint 31 wants the opposite: an eliminated cause stays visible, struck through, with
    the check and the answer that killed it attached to it.
    """
    by_id = {e.cause_id: e for e in state.eliminations}
    payload = []
    for cause in state.differential.causes:
        elimination = by_id.get(cause.id)
        payload.append(
            {
                "id": cause.id,
                "text": cause.text,
                "live": cause.id in state.live,
                "confirmed": cause.id in state.confirmed,
                "eliminated": elimination is not None,
                # `RC13`. Never a bare `eliminated: true` — the audit travels with it or the
                # elimination is the software deciding on its own authority.
                "eliminated_because": elimination.render() if elimination else "",
                "eliminated_by_question": elimination.question_id if elimination else "",
                "eliminated_by_answer": elimination.answer_text if elimination else "",
            }
        )
    return payload


def _question_payload(question: diff.Question | None) -> dict | None:
    if question is None:
        return None
    return {
        "id": question.id,
        "text": question.text,
        "sme_reviewed": question.sme_reviewed,
        "answers": [
            {
                "key": answer.key,
                "text": answer.text,
                # Constraint 30: *can't tell* must have **no effect at all**. Shipping the
                # effect count lets the interface prove that to the reader rather than
                # asserting it — a "no effect" label nobody can check is a promise.
                "effect_count": len(answer.effects),
                "changes_nothing": not answer.effects,
            }
            for answer in question.answers
        ],
    }


@router.post("/differential")
async def differential_state(body: DifferentialRequest) -> dict:
    """Replay the answers given and return where the differential stands.

    Refuses rather than inventing when the class has no differential — constraint 27 — and
    the refusal names which classes do, because *"this class does not get one"* is a fact
    about the trained model rather than a gap in our content.
    """
    fault = faults.by_label(body.fault_label)
    if fault is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{body.fault_label!r} is not a label this plant's model emits. It emits: "
                f"{', '.join(faults.all_labels())}."
            ),
        )

    if not diff.has_differential(body.fault_label):
        return {
            "fault_label": body.fault_label,
            "has_differential": False,
            "reason": (
                f"{body.fault_label} already names a mechanism, so it does not get a "
                f"differential. Narrowing it would invent ambiguity the trained model never "
                f"reported. Only the classes that declare themselves undecidable have one: "
                f"{', '.join(faults.undecidable_labels())}."
            ),
            "causes": [],
            "next_question": None,
        }

    registered = diff.differential_for(body.fault_label)
    if registered is None:
        return {
            "fault_label": body.fault_label,
            "has_differential": True,
            "content_available": False,
            "reason": (
                f"{body.fault_label} declares itself undecidable and therefore qualifies for "
                f"a differential, but no candidate set has been authored for it yet. The "
                f"reference queue holds 4 differentials, 19 candidate causes and 19 "
                f"discriminating questions, and not one has been reviewed by a refrigeration "
                f"engineer. This is missing content, not a class without ambiguity."
            ),
            "causes": [],
            "next_question": None,
        }

    state = diff.start(registered)
    for answer in body.answers:
        state = diff.apply(state, answer.question_id, answer.answer_key)

    return {
        "fault_label": body.fault_label,
        "has_differential": True,
        "content_available": True,
        "causes": _cause_payload(state),
        "live_count": len(state.live),
        "eliminated_count": len(state.eliminations),
        # `RC14`. Two terminal states, never collapsed into `done`. Exhausted-but-not-settled
        # is a finding — *"we cannot separate these with the checks we have"* — and reporting
        # it as settled would put a conclusion on whichever cause happened to be left.
        "outcome": state.outcome.value,
        "settled": state.outcome is diff.Outcome.SETTLED,
        "exhausted_not_settled": state.outcome is diff.Outcome.EXHAUSTED,
        "outcome_text": state.render_outcome(),
        "next_question": _question_payload(state.next_question),
        "questions_remaining": len(state.remaining_questions),
        "reviewed_questions_available": len(registered.askable),
        "unreviewed_note": (
            "No discriminator in this library has been reviewed by a refrigeration engineer. "
            "Until that review happens none is put to anyone, because an unreviewed "
            "discriminator eliminates irreversibly and nobody re-examines a settled question."
            if not registered.askable
            else ""
        ),
        "eliminations": [e.render() for e in state.eliminations],
    }
