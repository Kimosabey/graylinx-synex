"""The critique gate — a second model reads the answer the first one wrote.

**Why a second opinion at all, when `postcheck` is already deterministic.** `postcheck`
compares strings: a number in the answer either appears in the evidence or it does not. That
catches fabrication and catches it perfectly, and it is blind to everything else. An answer can
quote every figure correctly and still assert something the evidence contradicts — *"the
residual is high, so the condenser is fouled"* invents a causal claim out of two true ones, and
no string comparison will ever see it. The two checks fail differently, which is the whole
reason to have both.

**The auditor is not the model that wrote the answer.** `CONTEXT.md` §4 requires exactly that,
and until now nothing exercised the requirement: the roster declared an `auditor` role pointing
at `phi4` and no code path called it — one of seven declared roles with no caller. The brain is
`gemma4:26b-a4b-it-qat` and the auditor is `phi4`; different weights on the same box, so a model
cannot mark its own work.

**A soft gate, and that is a decision rather than a weak implementation.** The answer is never
mutated and never hidden. It ships with a badge a reader consciously accepts. A hidden answer
teaches somebody the system is broken; a badged one teaches them what to check. This is the same
argument `D-015` makes about `NO_DIAGNOSIS` — a correct outcome presented as a failure gets read
as a bug.

**Three verdicts, not two.** *Verified*, *unverified* (absent from the evidence) and *suspicious*
(contradicts it) are three different facts, and the middle one is weak: a reasoning model
legitimately reasons past strict telemetry. Collapsing *absent* into *contradicts* over-flags
every answer that draws a sensible inference, and a gate that fires on good answers is a gate
somebody switches off.

**The thresholds are inherited, not invented.** All four come from the Thermynx implementation
at `thermynx/backend/app/config.py` lines 157–173, where they were tuned against a live corpus.
Copying an inherited constraint rather than re-deriving it is what `CONTEXT.md` §10 asks for.
`Q106` records that they have *not* been re-tuned against Synex's own answers, which have a
different shape — shorter, and a far higher proportion of them are refusals.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.llm.client import ModelClient

#: Gate when at least half the audited claims are not verified.
#: Thermynx `CRITIQUE_SUSPICION_THRESHOLD`.
SUSPICION_THRESHOLD: float = 0.5

#: An *absent* claim counts as half a *contradicting* one.
#: Thermynx `CRITIQUE_UNVERIFIED_WEIGHT`.
UNVERIFIED_WEIGHT: float = 0.5

#: Contradictions alone gate at roughly a third.
#: Thermynx `CRITIQUE_CONTRADICTION_THRESHOLD`.
CONTRADICTION_THRESHOLD: float = 0.34

#: Three deterministic failures is enough on its own, whatever the auditor thinks.
#: Thermynx `_AUDIT_FLAG_GATE`.
POSTCHECK_FLAG_GATE: int = 3

#: The longest slice of either side handed to the auditor. Long enough for every recorded
#: answer and its pack; short enough that a pasted wall of text cannot push the instructions
#: out of the auditor's own context.
MAX_SIDE_CHARS: int = 6000

_PROMPT = """You are checking whether an answer about an industrial chiller plant is supported
by the evidence it was given. You are not writing an answer and not correcting one.

EVIDENCE (everything the writer was given):
{evidence}

ANSWER (what the writer said):
{answer}

For each distinct claim in the ANSWER, decide one of:
- "verified"   the evidence supports it
- "unverified" the evidence neither supports nor contradicts it
- "suspicious" the evidence contradicts it

Return ONLY this JSON object and nothing else:
{{"verified": [], "unverified": [], "suspicious": [], "overall": "pass"}}

Rules:
- Judge claims, not wording. A rounded figure is verified when the evidence carries the value.
- A statement that something could NOT be determined is "verified" when the evidence says so.
- "suspicious" is for a claim the evidence DISAGREES with, not one it is silent about.
  In particular, if the evidence says a signal was never measured, is constant, or is suspect,
  then ANY stated value or condition for that signal is "suspicious" — not "unverified".
  Reporting a reading for an instrument that has never produced one contradicts the evidence.
- A causal claim ("X, so Y is faulty") is "suspicious" when the evidence names no such cause,
  because the evidence describes what was measured and not why.
- "overall" is "fail" only if the answer asserts something the evidence contradicts.
- Write nothing outside the JSON."""

_FAIL_VERDICTS = frozenset({"fail", "failed", "reject", "rejected", "no"})


@dataclass(frozen=True)
class Critique:
    """The auditor's reading, and whether it badges the answer.

    `available` is `False` when the auditor could not be reached or returned nothing usable.
    That is deliberately **not** the same as passing: an answer nobody audited is not an audited
    answer, and a surface that cannot tell those apart will show a clean badge for a check that
    never ran. Two absences, kept apart.
    """

    available: bool = False
    verified: tuple[str, ...] = field(default_factory=tuple)
    unverified: tuple[str, ...] = field(default_factory=tuple)
    suspicious: tuple[str, ...] = field(default_factory=tuple)
    overall: str = ""
    needs_review: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)
    model: str = ""
    note: str = ""

    @property
    def total(self) -> int:
        return len(self.verified) + len(self.unverified) + len(self.suspicious)

    def render(self) -> str:
        """One sentence for a reader. Never blank, and never optimistic about a check that
        did not happen."""
        if not self.available:
            return f"This answer was not independently checked — {self.note}."
        if not self.needs_review:
            return (
                f"A second model ({self.model}) read {self.total} claim(s) against the evidence "
                f"and found nothing it contradicts."
            )
        return f"Needs review — {'; '.join(self.reasons)}."

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "needs_review": self.needs_review,
            "verified": len(self.verified),
            "unverified": len(self.unverified),
            "suspicious": list(self.suspicious),
            "overall": self.overall,
            "reasons": list(self.reasons),
            "model": self.model,
            "note": self.note,
        }


def gate(
    *,
    verified: int,
    unverified: int,
    suspicious: int,
    overall: str,
    postcheck_flags: int,
    has_evidence: bool,
) -> tuple[bool, tuple[str, ...]]:
    """The decision, kept apart from the model call so it can be tested without one.

    **Evidence-aware.** A question with no telemetry behind it — *"what does this fault label
    mean?"* — is legitimately all-unverified, and gating that is a false positive that teaches
    people to ignore the badge. Where there was no evidence to check against, only genuine
    contradictions count.

    Returns the decision **and its reasons in words**, because a badge a reader cannot act on is
    just an alarm.
    """
    total = verified + unverified + suspicious
    weight = UNVERIFIED_WEIGHT if has_evidence else 0.0
    ratio = (suspicious + unverified * weight) / total if total else 0.0
    contradiction_ratio = suspicious / total if total else 0.0

    reasons: list[str] = []
    if total and ratio >= SUSPICION_THRESHOLD:
        reasons.append(
            f"{ratio:.0%} of {total} claim(s) are not verified — "
            f"{suspicious} contradicted, {unverified} absent from the evidence"
        )
    if total and contradiction_ratio >= CONTRADICTION_THRESHOLD:
        reasons.append(f"{suspicious} of {total} claim(s) contradict the evidence")
    if overall.strip().lower() in _FAIL_VERDICTS:
        reasons.append("the auditor's overall verdict is a fail")
    if postcheck_flags >= POSTCHECK_FLAG_GATE:
        reasons.append(f"{postcheck_flags} deterministic audit(s) had already failed")
    return bool(reasons), tuple(reasons)


async def critique_answer(  # noqa: PLR0911
    *,
    answer: str,
    evidence: str,
    client: ModelClient | None,
    postcheck_flags: int = 0,
) -> Critique:
    """Ask the auditor to read the answer. **Never raises.**

    **Seven exits, and `PLR0911` is suppressed here for the reason `answer_turn` records for
    the same rule.** Each return is a distinct reason the second opinion is unavailable — empty
    answer, no client, unreachable, no JSON, unparseable JSON, not an object, and the audited
    result. Funnelling them through one exit would mean carrying the reason in a mutable local,
    and the reason is the whole value: *"the auditor could not be reached"* and *"the auditor
    returned prose"* send a reader to different places.

    An auditor that cannot be reached is a stated absence, not an exception: the turn already
    has an answer and a deterministic audit, and losing the second opinion must not lose those
    too.
    """
    if not answer.strip():
        return Critique(note="the answer was empty, so there was nothing to check")
    if client is None:
        return Critique(note="no model client was available to reach the auditor")

    try:
        completion = await client.complete(
            role="auditor",
            task="critique",
            messages=[
                {"role": "system", "content": "You return one JSON object and no other text."},
                {
                    "role": "user",
                    "content": _PROMPT.format(
                        evidence=(evidence[:MAX_SIDE_CHARS] or "(no evidence was supplied)"),
                        answer=answer[:MAX_SIDE_CHARS],
                    ),
                },
            ],
        )
    except Exception as exc:  # an auditor that broke is an absence, not a crash
        return Critique(note=f"the auditor could not be reached ({type(exc).__name__})")

    text = (getattr(completion, "text", "") or "").strip()
    opened, closed = text.find("{"), text.rfind("}")
    if opened < 0 or closed <= opened:
        return Critique(note="the auditor returned no JSON object")
    try:
        parsed = json.loads(text[opened : closed + 1])
    except ValueError:
        return Critique(note="the auditor's JSON could not be parsed")
    if not isinstance(parsed, dict):
        return Critique(note="the auditor returned JSON that was not an object")

    def rows(key: str) -> tuple[str, ...]:
        value = parsed.get(key)
        return tuple(str(v) for v in value) if isinstance(value, list) else ()

    verified, unverified, suspicious = rows("verified"), rows("unverified"), rows("suspicious")
    overall = str(parsed.get("overall") or "")
    needs_review, reasons = gate(
        verified=len(verified),
        unverified=len(unverified),
        suspicious=len(suspicious),
        overall=overall,
        postcheck_flags=postcheck_flags,
        has_evidence=bool(evidence.strip()),
    )
    return Critique(
        available=True,
        verified=verified,
        unverified=unverified,
        suspicious=suspicious,
        overall=overall,
        needs_review=needs_review,
        reasons=reasons,
        model=getattr(completion, "model", "") or "the auditor",
    )
