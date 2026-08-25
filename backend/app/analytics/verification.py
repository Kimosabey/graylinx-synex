"""`V1`–`V4` — did the repair work? Post-work residuals, and three honest outcomes.

**The closure note never decides this, and neither does the technician's opinion.**
Separation law, last row: *"Did the repair work? Post-work residuals plus a deterministic
rule — never the closure note or the LLM."* A work order that closes because somebody typed
"done" has proved nothing.

**Three outcomes, and `UNKNOWN` is not a failure of the check.** It is the answer when the
data cannot decide, and on this plant it is the common one. `AC5` requires it.

| Outcome | Meaning |
|---|---|
| `PASS` | Residuals returned inside this asset's own band, and the gates passed |
| `FAIL` | Residuals are still outside the band. The repair did not fix what was measured |
| `UNKNOWN` | The data cannot decide. **The work order does not close** |

**The failure this module exists to prevent is measured, not hypothetical.** On chiller 1 the
`HIGH_HEAD_AMBIGUOUS` label disappears after 2026-04-22 and never returns in the measured
window. It looks exactly like a repair. It is not: after 23 April every slot is
`NO_DIAGNOSIS` or unlabelled — the gates stopped passing, so nothing was being judged at all
— and the current residual over that period is **worse**, averaging 105.75 against 41.72
before, against a healthy band of [−38.677, −12.613].

A verification that read "the fault label is gone" as PASS would have closed a work order on
a machine that had deteriorated. Inherited constraint 7 in one sentence: **a NULL means not
diagnosed, never healthy.**

**`Q15` blocks the PASS threshold, not the mechanism.** Nobody has agreed how far inside its
band a residual must return, or for how long, to count as fixed. Until that number exists,
`PASS` is unreachable and the honest output is `UNKNOWN` — stated, with the question named.

Pure functions. No I/O, no settings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.analytics.bands import BandVerdict, ResidualBand, classify


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    """The data cannot decide. Not a failure of the check — the answer."""


@dataclass(frozen=True)
class Verification:
    outcome: Outcome
    reason: str
    residual_name: str
    before_in_band: int = 0
    before_total: int = 0
    after_in_band: int = 0
    after_total: int = 0
    blocked_by: str | None = None
    """The unanswered question preventing a stronger outcome, if any. `Q15`."""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def closes_the_work_order(self) -> bool:
        """Only a PASS closes. `W9`.

        `UNKNOWN` is explicitly permitted and explicitly does not close — that pairing is
        the whole point, because the tempting shortcut is to treat "no evidence of a
        problem" as "evidence of no problem".
        """
        return self.outcome is Outcome.PASS

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "reason": self.reason,
            "residual_name": self.residual_name,
            "before": {"in_band": self.before_in_band, "total": self.before_total},
            "after": {"in_band": self.after_in_band, "total": self.after_total},
            "closes_the_work_order": self.closes_the_work_order,
            "blocked_by": self.blocked_by,
            "notes": list(self.notes),
        }


def _in_band(values: tuple[float | None, ...], band: ResidualBand) -> tuple[int, int]:
    judged = [v for v in values if v is not None]
    inside = sum(1 for v in judged if classify(v, band) is BandVerdict.NORMAL)
    return inside, len(judged)


def verify(
    *,
    residual_name: str,
    before: tuple[float | None, ...],
    after: tuple[float | None, ...],
    band: ResidualBand | None,
    after_was_diagnosable: bool,
) -> Verification:
    """Compare post-work readings to the asset's own band.

    `after_was_diagnosable` is the parameter that matters. It is `False` when the gates did
    not pass over the post-work window — and when it is `False`, no amount of clean-looking
    data is evidence of a repair, because nothing was being judged.
    """
    if band is None:
        return Verification(
            outcome=Outcome.UNKNOWN,
            reason=(
                "No reference band is fitted for this asset, so a post-work reading cannot "
                "be judged high or normal for it. Nothing can be proved either way."
            ),
            residual_name=residual_name,
        )

    if not after:
        return Verification(
            outcome=Outcome.UNKNOWN,
            reason="There are no readings after the work, so there is nothing to compare.",
            residual_name=residual_name,
        )

    before_in, before_n = _in_band(before, band)
    after_in, after_n = _in_band(after, band)

    if after_n == 0:
        return Verification(
            outcome=Outcome.UNKNOWN,
            reason=(
                "Every post-work reading for this residual is NULL. A NULL means not "
                "measured, never healthy."
            ),
            residual_name=residual_name,
            before_in_band=before_in,
            before_total=before_n,
        )

    # ── the one that matters ────────────────────────────────────────────────
    if not after_was_diagnosable:
        return Verification(
            outcome=Outcome.UNKNOWN,
            reason=(
                "The fault label is absent after the work, but the gates did not pass over "
                "that window — so nothing was being diagnosed. The label disappearing is "
                "not evidence of a repair; a NULL means not diagnosed, never healthy."
            ),
            residual_name=residual_name,
            before_in_band=before_in,
            before_total=before_n,
            after_in_band=after_in,
            after_total=after_n,
            notes=(
                "This is the failure mode this check exists for. On this plant the label "
                "clears while the residual gets worse.",
            ),
        )

    still_out = after_n - after_in
    if still_out > 0:
        return Verification(
            outcome=Outcome.FAIL,
            reason=(
                f"{still_out} of {after_n} post-work readings are still outside this "
                f"asset's own band. What was measured has not been fixed."
            ),
            residual_name=residual_name,
            before_in_band=before_in,
            before_total=before_n,
            after_in_band=after_in,
            after_total=after_n,
        )

    # Everything returned to band and the window was diagnosable — the only route to PASS,
    # and it is closed until Q15 says how far in, and for how long, counts as fixed.
    return Verification(
        outcome=Outcome.UNKNOWN,
        reason=(
            f"All {after_n} post-work readings are back inside this asset's own band, which "
            f"is what a repair looks like. It is not recorded as a PASS because no one has "
            f"agreed how far inside the band a residual must return, or for how long, to "
            f"count as fixed."
        ),
        residual_name=residual_name,
        before_in_band=before_in,
        before_total=before_n,
        after_in_band=after_in,
        after_total=after_n,
        blocked_by="Q15",
        notes=(
            "The mechanism works; the threshold is missing. Until Q15 is answered the "
            "honest outcome is UNKNOWN, and the work order stays open.",
        ),
    )
