"""The gates — nothing is diagnosed until all of them pass.

`CONTEXT.md` §6: *"Gates — nothing is diagnosed until all pass: running steady, load above
the model's floor, flows valid, no setpoint change, and the pattern persisted."* A gate that
fails is not an error. It produces `NO_DIAGNOSIS`, naming the check that stopped it and what
would change the answer — which is what makes a refusal useful rather than a shrug.

**Four of these need no SME number, and they are the ones the demonstration actually shows.**
Each was measured on our own data:

**Off, not broken** — ~23,800 of 31,884 slots read zero across every signal at once, about
a 25% duty cycle. Stops the commonest false positive available: a "fault" on a stopped
chiller.

**Missing band** — 10 of 12 equipment tables have no reference band. Stops a residual being
scored against zero, or against another asset's spread.

**Simulated slot** — 156,129 slots are synthetic and the simulation invented `cond_flow`.
Stops a demonstration implying an instrumentation capability the site does not have.

**Physically possible** — `cond_leaving_temp` reaches −273.2 and `kw_per_tr` spans −6,265 to
+30,183. Stops a sensor's own death being averaged into a residual.

**The threshold gates carry `TBD(Qn)` and default to refusing.** Persistence is 20–30 min
*proposed and unconfirmed* (`Q6`), and the model's load floor is unstated (`Q3`). Refusing is
the safe default because the alternative — passing a gate whose threshold nobody agreed — is
how a diagnosis gets made on data the model cannot judge.

Pure functions. No settings, no I/O; the measured-window boundary is **passed in** rather
than read from config, because contract 3 forbids `app.analytics` from importing
`app.config` and a pure function that reads a flag is not pure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.analytics.bands import ResidualBand


class Gate(StrEnum):
    """Which check stopped the diagnosis. Carried into the `no_diagnosis` frame."""

    RUNNING = "running"
    BAND_AVAILABLE = "band_available"
    MEASURED_WINDOW = "measured_window"
    PHYSICALLY_PLAUSIBLE = "physically_plausible"
    LOAD_FLOOR = "load_floor"
    PERSISTENCE = "persistence"


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict, and — when it failed — what would change the answer.

    `remedy` is not decoration. A refusal that does not say what would unblock it is
    indistinguishable from a broken feature, and on this data refusal is the modal outcome.
    """

    gate: Gate
    passed: bool
    reason: str = ""
    remedy: str = ""
    unresolved_question: str | None = None
    """Set when the gate could not be evaluated because its threshold is unagreed. Such a
    gate reports `passed=False` — refusing — and names the question."""


@dataclass(frozen=True)
class GateOutcome:
    """Every gate's result, and whether a diagnosis may proceed at all."""

    results: tuple[GateResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> tuple[GateResult, ...]:
        return tuple(r for r in self.results if not r.passed)

    @property
    def first_failure(self) -> GateResult | None:
        """The gate to name in the refusal. First in evaluation order, not "worst".

        Ordering by severity would imply a ranking nobody agreed; the order the checks run
        in is defensible and explainable, which matters more in a refusal than in an answer.
        """
        failures = self.failures
        return failures[0] if failures else None


# ── gate 1: off, not broken ─────────────────────────────────────────────────────

def check_running(signal_values: dict[str, float | None]) -> GateResult:
    """A chiller reading zero across every signal at once is **off**, not faulty.

    Roughly 23,800 of 31,884 slots on chiller 1 are exactly this — about a 25% duty cycle.
    Reading them as faults is the commonest false positive available, and it would drown a
    real fault in a queue of stopped-machine alarms.

    An empty reading set also fails: no signals is not evidence of running.
    """
    if not signal_values:
        return GateResult(
            Gate.RUNNING,
            passed=False,
            reason="no signal readings for this slot",
            remedy="check that telemetry is arriving for this equipment",
        )

    present = [v for v in signal_values.values() if v is not None]
    if not present:
        return GateResult(
            Gate.RUNNING,
            passed=False,
            reason="every signal is NULL for this slot",
            remedy="check that telemetry is arriving for this equipment",
        )
    if all(v == 0 for v in present):
        return GateResult(
            Gate.RUNNING,
            passed=False,
            reason="every signal reads exactly zero — the machine is off, not faulty",
            remedy="ask about a slot when the machine was running",
        )
    return GateResult(Gate.RUNNING, passed=True)


# ── gate 2: is there a band to judge against? ───────────────────────────────────

def check_band_available(band: ResidualBand | None, equipment_display: str) -> GateResult:
    """Ten of twelve assets land here, and that is the correct answer rather than a gap."""
    if band is None:
        return GateResult(
            Gate.BAND_AVAILABLE,
            passed=False,
            reason=(
                f"no fitted reference band exists for {equipment_display}, so a residual "
                f"cannot be judged high or normal for this asset"
            ),
            remedy=(
                "fit a normal-operation model for this asset, or ask about chiller 1 or "
                "chiller 2, which are the two that have one"
            ),
        )
    return GateResult(Gate.BAND_AVAILABLE, passed=True)


# ── gate 3: measured, or generated? ─────────────────────────────────────────────

def check_measured_window(
    slot_time: datetime,
    measured_window_end: datetime,
    *,
    include_simulated: bool = False,
) -> GateResult:
    """D-009. The natural demonstration window is the most recent data, and it is synthetic.

    Marking it *simulated* is not sufficient: the problem is not that the numbers are
    generated, it is that `cond_flow` implies an instrumentation capability the site does
    not have. Every other synthetic signal continues something the plant genuinely measures.

    `include_simulated` must be passed explicitly, and it is never a default.
    """
    if slot_time > measured_window_end and not include_simulated:
        return GateResult(
            Gate.MEASURED_WINDOW,
            passed=False,
            reason=(
                f"{slot_time:%Y-%m-%d %H:%M} is after the last real reading "
                f"({measured_window_end:%Y-%m-%d %H:%M}); this window is simulated, and the "
                f"simulation invented condenser flow — a signal this plant has never measured"
            ),
            remedy="ask about a slot on or before the end of the measured window",
        )
    return GateResult(Gate.MEASURED_WINDOW, passed=True)


# ── gate 4: is the reading physically possible? ─────────────────────────────────

#: Below this, a temperature reading is a sensor reporting its own failure.
ABSOLUTE_ZERO_C: float = -273.15


def check_physically_plausible(
    *,
    cond_leaving_temp: float | None = None,
    cond_entering_temp: float | None = None,
    kw_per_tr: float | None = None,
) -> GateResult:
    """Three impossibilities, all measured on this plant, all missed by single-signal checks.

    Constraint 19 is why none of these takes an absolute value first: `ABS()` let a flow
    reading of −2.49 count as credible and understated a dead transmitter by 62 days. The
    sign is the evidence.
    """
    if cond_leaving_temp is not None and cond_leaving_temp <= ABSOLUTE_ZERO_C:
        return GateResult(
            Gate.PHYSICALLY_PLAUSIBLE,
            passed=False,
            reason=(
                f"condenser leaving temperature reads {cond_leaving_temp} C, at or below "
                f"absolute zero — the sensor is reporting its own failure, not a temperature"
            ),
            remedy="replace or recalibrate the condenser leaving temperature transmitter",
        )

    # A condenser rejects heat, so leaving water must be warmer than entering. Negative
    # every month on one chiller, at −3.0 to −3.4 — the two columns are swapped or
    # mislabelled, and nothing detected it. `F16`.
    if cond_leaving_temp is not None and cond_entering_temp is not None:
        delta = cond_leaving_temp - cond_entering_temp
        if delta < 0:
            return GateResult(
                Gate.PHYSICALLY_PLAUSIBLE,
                passed=False,
                reason=(
                    f"condenser ΔT is {delta:.2f} C — a condenser rejects heat, so leaving "
                    f"water cannot be colder than entering. The two columns are swapped or "
                    f"mislabelled"
                ),
                remedy="correct the condenser water column mapping before trusting any residual",
            )

    # Efficiency computed while flow was near zero: −6,265 to +30,183 on chiller 1. A figure
    # that large is not a bad score, it is a meaningless one.
    if kw_per_tr is not None and not (0 < kw_per_tr < 10):
        return GateResult(
            Gate.PHYSICALLY_PLAUSIBLE,
            passed=False,
            reason=(
                f"efficiency computes to {kw_per_tr:.1f} kW/TR, which is not a bad score but "
                f"a meaningless one — it was computed while flow was near zero"
            ),
            remedy="restore a credible flow measurement before efficiency means anything",
        )

    return GateResult(Gate.PHYSICALLY_PLAUSIBLE, passed=True)


# ── the threshold gates: unagreed, and therefore refusing ───────────────────────

def check_load_floor(load: float | None) -> GateResult:
    """`Q3`. No document states the minimum load for a valid diagnosis.

    Refusing is the safe default: passing a gate whose threshold nobody agreed is how a
    diagnosis gets made on data the model cannot judge. The remedy names the question, so
    the refusal is actionable rather than merely negative.
    """
    return GateResult(
        Gate.LOAD_FLOOR,
        passed=False,
        reason=(
            "the minimum load for a valid diagnosis has not been agreed, so it cannot be "
            "confirmed that this reading is above the model's floor"
        ),
        remedy="confirm the minimum load per machine type with the SME (Q3)",
        unresolved_question="Q3",
    )


def check_persistence(consecutive_slots: int) -> GateResult:
    """`Q6`. 20–30 minutes is *proposed and unconfirmed*, so the window is not ours to apply.

    The slot count is carried in the reason regardless, because it is a measured fact and
    useful to whoever answers the question.
    """
    return GateResult(
        Gate.PERSISTENCE,
        passed=False,
        reason=(
            f"the pattern held for {consecutive_slots} consecutive slot(s), but the "
            f"persistence window is proposed at 20-30 minutes and not confirmed"
        ),
        remedy="confirm the persistence window with the SME (Q6)",
        unresolved_question="Q6",
    )


#: The gates that can be evaluated today, in evaluation order. The threshold gates are
#: deliberately excluded: applying an unagreed threshold is worse than not applying it, and
#: including them here would make every diagnosis refuse for a reason nobody can act on.
#:
#: They are still *reachable* — `check_load_floor` and `check_persistence` exist and refuse —
#: so wiring them in is a one-line change the day Q3 and Q6 are answered.
EVALUABLE_GATES: tuple[Gate, ...] = (
    Gate.RUNNING,
    Gate.BAND_AVAILABLE,
    Gate.MEASURED_WINDOW,
    Gate.PHYSICALLY_PLAUSIBLE,
)

UNAGREED_GATES: tuple[Gate, ...] = (Gate.LOAD_FLOOR, Gate.PERSISTENCE)
