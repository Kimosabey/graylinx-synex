"""A short expert reading of the evidence, written before the answer is composed.

**Why a separate pass rather than a better prompt.** Composing and assessing are different jobs
and asking one call to do both produces an answer that reads fluently and skips the hard part:
the model writes a tidy paragraph about the residual that is easiest to describe, and the one
with a poor model fit or a contradicting sibling goes unmentioned. Splitting them gives the
assessment its own call with **thinking on**, and hands the composer something to write *from*
rather than something to work out while writing.

`reasoning_policy` has listed `domain_analyst` as a thinking task since it was written and
nothing ever called it — the same shape as `react.py`, `escalate.py` and the whole knowledge
layer before them. A policy nobody exercises is a comment.

**It assesses evidence; it never names a fault.** That boundary is the whole reason this is safe
to add. The analyst may say *which* residual carries the most weight, that a model with a high
nRMSE should not be leaned on, that two signals disagree, or that a gate failing makes the rest
moot. It may not say what is wrong with the machine — the FDD rules named the fault before this
runs, and the prompt says so twice because this is the one pass whose output reads most like a
diagnosis.

**Never blocks and never replaces.** An unreachable box, a timeout or an empty reply yields an
empty assessment and the composer runs exactly as it did before. The pass can only make an
answer better informed; it cannot make the turn fail.
"""
from __future__ import annotations

import asyncio

#: One short paragraph is the whole output. Longer and it competes with the answer for the
#: composer's attention, which is how a note about the evidence becomes the answer itself.
MAX_CHARS: int = 900

#: Bounded because this sits in front of the answer: a reader is already waiting when it runs.
TIMEOUT_S: float = 45.0

_SYSTEM = """You are a reliability engineer reading the evidence behind one detected fault,
before somebody else writes the answer. Your note is for them, not for the reader.

WHAT YOU ARE DOING
Say which parts of this evidence actually carry weight and which do not. That is all.

- Which residual is furthest outside its own band, and whether its model is fitted well enough
  to lean on. A high nRMSE means the model predicts this signal poorly, so a large residual
  from it says less than a small one from a well-fitted model.
- Whether any two signals disagree with each other.
- Whether a failed gate makes the rest of it moot.
- Which signals are absent, and what that closes off.

WHAT YOU MUST NOT DO
- Do not name a cause or a fault. The detection rules already named it before you were called.
  You are reading the evidence, not deciding what it means about the machine.
- Do not recommend an action, a check or a repair.
- Do not rank by seriousness. Severity is agreed for one fault class of nine on this plant.
- Do not state a number that is not in the evidence, and do not round one that is.
- Do not write an answer. Somebody else is writing it from your note.

One paragraph. If the evidence carries nothing worth flagging, say exactly that in one line —
a note padded to look substantial is worse than a short true one."""


async def assess(*, evidence: str, question: str, client) -> str:
    """A short reading of this evidence, or `""` when none could be taken.

    Empty on every failure, and the caller composes without it. This pass is an improvement to
    an answer that already works; making the turn depend on it would trade a better answer for
    a less reliable one.
    """
    if client is None or not evidence.strip():
        return ""

    try:
        completion = await asyncio.wait_for(
            client.complete(
                role="brain",
                # The task name is what turns thinking on — `reasoning_policy` has listed
                # `domain_analyst` since it was written, and this is its first caller.
                task="domain_analyst",
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"EVIDENCE\n{evidence}\n\n"
                            f"The person asked: {question}\n\n"
                            "Write your note on what this evidence does and does not support."
                        ),
                    },
                ],
            ),
            timeout=TIMEOUT_S,
        )
    except Exception:
        return ""

    note = (getattr(completion, "text", "") or "").strip()
    if len(note) < 30:
        return ""
    return note[:MAX_CHARS]


def as_prompt_block(note: str) -> str:
    """The assessment, framed for the composer that reads it next.

    Framed rather than pasted, because an unlabelled paragraph in a prompt reads as more
    evidence — and this is one model's opinion about evidence, which is a different thing. The
    composer is told to use it for emphasis and never as a source of figures.
    """
    if not note:
        return ""
    return (
        "<<<SYNEX_ANALYST_NOTE>>>\n"
        f"{note}\n"
        "<<<SYNEX_ANALYST_NOTE>>>\n\n"
        "That note is one engineer's reading of the evidence below — it says which parts carry "
        "weight. Use it to decide what to lead with and what to caveat. It is not a source: "
        "every figure you state must still come from the evidence itself, and if the note and "
        "the evidence disagree, the evidence is right.\n\n"
    )
