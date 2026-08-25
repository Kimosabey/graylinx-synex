"""`EV2`/`EV4` — the gate that **blocks**, over the answers the box actually produced.

**The failure this closes: a scorecard nothing was held to.** `app/eval/scorecard.py` has
scored the eight transcripts recorded on the Jarvis box since the day they were captured, and
until this module existed the only thing that ever called `run()` was the scorecard's own test
file. That is the shape this repository keeps rediscovering — machinery with no consumer. The
consequence was concrete rather than theoretical: the gate finds **one hard failure today**,
`04911191`, whose recorded refusal never states the window it covers, and the test that knows
about it asserts that it *fails*. A second answer failing the same dimension tomorrow would
change nothing anywhere. A gate that reports is not a gate that blocks.

**This is not a mean, and it has no tolerance.** Inherited constraint 17 — some dimensions are
hard and exempt from any overall tolerance, because a report whose own figures disagree cannot
pass on the strength of scoring well elsewhere. So there is no ratio here, no pass rate and no
`n of 8 answers were clean`: **one** unacknowledged hard failure blocks, whatever the other
sixty-three checks said.

**Coverage travels with the verdict, always.** `R10`: a reconciliation once claimed agreement
while excluding what it could not check. Eight answers times eight dimensions is 64 questions,
of which 58 are settled, 6 do not arise and three further dimensions are declared and cannot
run at all. `render()` prints the coverage sentence beside the verdict and `as_dict()` cannot
emit one without the other, because the whole failure was the two being separated.

**Known findings are acknowledged, never tolerated.** A gate that goes red on the day it is
written is a gate somebody switches off, and the one failure on record is a real finding with a
real fix that belongs to the `narrate` prompt rather than to this run. So it is listed —
by case, by dimension, with the reason and the question that closes it — and the register is
held to two rules that keep it from becoming a tolerance:

1. **An acknowledgement excuses exactly one dimension on exactly one answer.** It is not a
   waiver on the dimension, so the same failure on a different answer still blocks.
2. **An acknowledgement that no longer fires blocks too.** Otherwise the register outlives the
   defect, and the next person reads a list of problems that were fixed years ago and stops
   reading the list.

Everything here runs with the GPU terminated and MySQL stopped. It reads recorded transcripts
from disk and pure functions over them, and nothing else.

    python -m app.eval.gate
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.eval import scorecard as sc


@dataclass(frozen=True)
class AcknowledgedFinding:
    """One hard failure that is known, understood, and not yet fixed.

    Every field is required and none of them is decorative. `because` is what the next reader
    needs in order to decide whether the acknowledgement still applies, and `question` is the
    thing that closes it — an acknowledgement with nothing to close is a tolerance with better
    manners.
    """

    case_id: str
    dimension_id: str
    because: str
    question: str

    def matches(self, case_id: str, dimension_id: str) -> bool:
        return self.case_id == case_id and self.dimension_id == dimension_id

    def render(self) -> str:
        return f"{self.case_id} · {self.dimension_id}: {self.because} {self.question}."


#: The hard failures the recorded set carries today, each acknowledged by hand.
#:
#: **One entry, and it is a finding rather than an excuse.** `04911191` is the only recorded
#: refusal — cooling tower 1 on 2026-04-15, where two gates failed and the correct answer was
#: `NO_DIAGNOSIS`. It is scored against the `narrate` prompt, which tells the model to name the
#: failed check and what would change it and never asks it for the window, unlike the
#: `diagnose` prompt. The answer duly omits it, and constraint 15 says an artefact with no
#: window is a lie by omission on a snapshot: the reader supplies *now* from their own head.
#:
#: The fix is a prompt change plus a re-recording on the box, which is a burst nobody has
#: booked, and it is not this gate's to make. `Q90` carries it.
ACKNOWLEDGED: tuple[AcknowledgedFinding, ...] = (
    AcknowledgedFinding(
        case_id="04911191",
        dimension_id="window_is_stated",
        because=(
            "the recorded refusal was written by the `narrate` prompt, which names the failed "
            "check and what would change it and never asks for the data window — so the model "
            "omitted what it was never told to state. Fixing it is a prompt change and a "
            "re-recording on the box, not a re-scoring"
        ),
        question="Q90",
    ),
)


class GateVerdict(StrEnum):
    """Three, and only one of them lets a change through.

    Two would force *"nothing was judged"* to become either a pass or a failure of the
    answers, and it is neither — inherited constraint 8, one more time.
    """

    CLEAR = "clear"
    """Every hard dimension that was asked came back `PASSED`, apart from the acknowledged
    findings, and every acknowledgement still fires."""

    BLOCKED = "blocked"
    """A hard dimension failed on an answer nobody has acknowledged, or an acknowledgement no
    longer fires. Constraint 17 — no tolerance forgives either."""

    UNRUNNABLE = "unrunnable"
    """There was nothing to judge. **Not a pass.** A gate that returns a clean report because
    it found no transcripts is the emptiest kind of green, and it is exactly what a deleted
    fixture directory would produce."""


@dataclass(frozen=True)
class StaleAcknowledgement:
    """An acknowledgement that no longer describes anything, and why that blocks.

    Two shapes, kept apart because they call for different edits: the dimension now passes on
    that answer, and the answer is no longer in the set at all.
    """

    finding: AcknowledgedFinding
    reason: str

    def render(self) -> str:
        return f"{self.finding.case_id} · {self.finding.dimension_id}: {self.reason}"


@dataclass(frozen=True)
class GateReport:
    """What the gate judged, what it is blocking on, and what it could not check.

    **No total and no ratio.** `Scorecard` refuses to expose a score for the reason constraint
    17 gives, and a gate that computed *"7 of 8 answers are clean"* over the top of it would
    reintroduce exactly the number the scorecard declines to produce.
    """

    scorecard: sc.Scorecard
    unacknowledged: tuple[tuple[str, sc.DimensionResult], ...]
    stale: tuple[StaleAcknowledgement, ...]
    acknowledged: tuple[AcknowledgedFinding, ...] = ()
    """Empty by default rather than defaulting to the register, so a hand-built report never
    claims to have consulted a list it was not given. `check()` always passes it explicitly."""

    @property
    def verdict(self) -> GateVerdict:
        """`UNRUNNABLE` first, because a gate with nothing to judge has not cleared anything."""
        if not self.scorecard.cases:
            return GateVerdict.UNRUNNABLE
        if self.unacknowledged or self.stale:
            return GateVerdict.BLOCKED
        return GateVerdict.CLEAR

    @property
    def blocks(self) -> bool:
        """Whether this run should stop a change. Anything but `CLEAR` does."""
        return self.verdict is not GateVerdict.CLEAR

    @property
    def coverage(self) -> sc.Coverage:
        return self.scorecard.coverage

    def render(self) -> str:
        """The artefact. Verdict, coverage, what blocks, then what was acknowledged."""
        lines = [
            "EV2 transcript gate",
            f"source: {self.scorecard.source or 'not recorded'}",
            "",
            f"verdict: {self.verdict.value}",
            f"coverage: {self.coverage.render()}",
            f"scorecard verdict: {self.scorecard.verdict.value}",
            "",
        ]

        if self.verdict is GateVerdict.UNRUNNABLE:
            lines.append(
                "No recorded answer was judged, so nothing has been cleared. This is not a "
                "pass — every transcript that could not be read is named below."
            )
            lines.extend(f"  {u.source}: {u.reason}" for u in self.scorecard.unreadable)
            return "\n".join(lines)

        if self.unacknowledged:
            lines.append(
                f"{len(self.unacknowledged)} hard dimension failure(s) nobody has "
                f"acknowledged. Constraint 17: no tolerance forgives one of these, and the "
                f"other sixty-odd checks passing does not either."
            )
            lines.extend(
                f"  {case_id} · {result.render()}" for case_id, result in self.unacknowledged
            )
        else:
            lines.append("No unacknowledged hard dimension failed on any recorded answer.")

        if self.stale:
            lines.append("")
            lines.append(
                f"{len(self.stale)} acknowledgement(s) no longer describe anything. A register "
                f"that outlives its defects is one nobody reads."
            )
            lines.extend(f"  {s.render()}" for s in self.stale)

        lines.append("")
        lines.append("ACKNOWLEDGED, AND STILL FIRING")
        if self.acknowledged:
            lines.extend(f"  {a.render()}" for a in self.acknowledged)
        else:
            lines.append("  nothing is acknowledged; every hard dimension passes on its own.")

        lines.append("")
        lines.append("WHAT THIS GATE DID NOT MEASURE")
        for absent in self.scorecard.unavailable:
            lines.append(
                f"  {absent.id} ({absent.severity.value}) is declared and never runs: "
                f"{absent.reason}. {absent.question}."
            )
        lines.append(
            f"  the acceptance set is {sc.GOLDEN_CASE_COUNT} golden cases and no transcript "
            f"records which one it belongs to, so this gate cannot say which acceptance cases "
            f"remain unjudged. Q78."
        )
        return "\n".join(lines)

    def as_dict(self) -> dict:
        """Never a verdict without its coverage — the `R10` failure, made structurally
        impossible in the one place a reader would otherwise separate them."""
        return {
            "verdict": self.verdict.value,
            "blocks": self.blocks,
            "coverage": self.scorecard.as_dict()["coverage"],
            "unacknowledged": [
                {
                    "case_id": case_id,
                    "dimension": result.dimension.id,
                    "verdict": result.judgement.verdict.value,
                    "detail": result.judgement.detail,
                }
                for case_id, result in self.unacknowledged
            ],
            "stale_acknowledgements": [
                {
                    "case_id": s.finding.case_id,
                    "dimension": s.finding.dimension_id,
                    "reason": s.reason,
                }
                for s in self.stale
            ],
            "acknowledged": [
                {
                    "case_id": a.case_id,
                    "dimension": a.dimension_id,
                    "because": a.because,
                    "question": a.question,
                }
                for a in self.acknowledged
            ],
        }


def _hard_failures(card: sc.Scorecard) -> tuple[tuple[str, sc.DimensionResult], ...]:
    """Every hard dimension that did not come back `PASSED`, however it did not.

    **Blocking rather than failing**, deliberately. `Scorecard.hard_failures` reports only
    `FAILED`, and constraint 20 — an estimate does not settle a blocking check — says an
    unmeasured hard dimension leaves the answer just as unshippable. A gate that watched only
    the first would go green on the day a dimension quietly stopped being answerable.
    """
    return tuple(
        (case.case_id, result)
        for case in card.cases
        for result in case.blocking
    )


def check(
    card: sc.Scorecard, acknowledged: tuple[AcknowledgedFinding, ...] | None = None
) -> GateReport:
    """Hold a scored run to the acknowledged register. Pure, and it takes no clock.

    **The register is looked up at call time rather than bound as a default**, the same
    discipline `golden.main` records for the golden set: a default evaluated at import cannot
    be replaced by a test, so *"prove this gate blocks with the register emptied"* would
    silently assert nothing. `None` means *use the register*; an empty tuple means *use none*,
    and the two are different requests.
    """
    register = ACKNOWLEDGED if acknowledged is None else acknowledged
    blocking = _hard_failures(card)
    unacknowledged = tuple(
        (case_id, result)
        for case_id, result in blocking
        if not any(a.matches(case_id, result.dimension.id) for a in register)
    )

    scored = {case.case_id for case in card.cases}
    fired = {(case_id, result.dimension.id) for case_id, result in blocking}
    stale = tuple(
        StaleAcknowledgement(
            finding=finding,
            reason=(
                f"answer {finding.case_id} is not in this run at all, so the acknowledgement "
                f"describes nothing. Either the transcript was removed or the case id moved; "
                f"either way the entry is now a waiver on a case that cannot be checked"
                if finding.case_id not in scored
                else f"{finding.dimension_id} no longer fails on {finding.case_id}. The finding "
                f"is fixed and the entry should go with it — {finding.question} can be closed"
            ),
        )
        for finding in register
        if (finding.case_id, finding.dimension_id) not in fired
    )

    return GateReport(
        scorecard=card,
        unacknowledged=unacknowledged,
        stale=stale,
        acknowledged=register,
    )


def run(
    directory: Path | None = None,
    acknowledged: tuple[AcknowledgedFinding, ...] | None = None,
) -> GateReport:
    """Score every recorded transcript and hold the result to the register. No box, no clock."""
    return check(sc.run(directory), acknowledged)


def main() -> int:
    """`python -m app.eval.gate`. Exits non-zero on anything but `CLEAR`.

    `UNRUNNABLE` exits non-zero too, and that is the difference between this and
    `golden.main`: there, `INCOMPLETE` is a question nobody can close from the command line
    (`Q78`), so failing on it would make a gate that can never go green. Here, *"there was
    nothing to judge"* is a state somebody can fix in one command — record a burst — and a
    green run over an empty directory is the exact reassurance this whole module exists
    against.
    """
    report = run()
    print(report.render())
    return 0 if report.verdict is GateVerdict.CLEAR else 1


if __name__ == "__main__":
    sys.exit(main())
