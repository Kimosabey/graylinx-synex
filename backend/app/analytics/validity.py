"""`F16` cross-signal validity · `F6` sensor bias — telling a broken sensor from a broken machine.

**The central point, and it is not ours.** A per-signal residual model cannot tell a dead
sensor from a dead chiller: from inside the model both look like a value it failed to
predict. Separating them requires reading signals *against each other*, which is arithmetic,
not machine learning. Source: `docs/knowledge_base/HVAC_INSTRUMENT_VALIDITY.md` in the
Thermynx repository, read 2026-08-17 — a read-only reference, like `docs/00-source/`.

**Why this is `F6`'s whole job.** Getting it wrong sends a technician to overhaul a healthy
compressor when the real fault is a transmitter costing a fraction as much. So the verdict
here is not "is this reading odd" but **"is the instrument the fault"** — and when it is, the
case routes to instrumentation rather than to a crew.

**Two failures on our own plant that a single-signal check missed:**

| Observed | Why one signal could not see it |
|---|--:|
| Both chilled-water flow transmitters read near zero since May while ΔT and power stayed
  normal | Each signal alone looked plausible. Only the *combination* is impossible |
| Condenser ΔT negative every month on one chiller, −3.0 to −3.4 | A condenser rejects heat.
  The two columns are swapped or mislabelled, and nothing detected it |

**The distinction that constraint 19 exists for.** A flow, a cooling output and an absolute
pressure have a physical floor of zero, so a negative value is **invalid, not small** — taking
`ABS()` once let a flow reading of −2.49 count as credible and understated a dead transmitter
by 62 days. A model *residual* is the opposite: it is a signed deviation, and −5 is as real a
reading as +5. Applying the floor rule to a residual would discard half of every distribution.

**These are contradictions, not judgements.** If one holds, the reading is wrong; no equipment
condition can produce it. That is why they may fire without an SME review, where a
*discriminator* may not — this module eliminates an instrument, never a cause.

**Pure functions, no I/O, no model.** `analytics` imports no driver and no config.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

# ── sourced bands ───────────────────────────────────────────────────────────────
# Every number below is quoted from HVAC_INSTRUMENT_VALIDITY.md with its physical reasoning
# attached. None is tuned, and none is ours — which is what makes them usable under the rule
# that no number appears without a source.

#: Above this, the denominator has collapsed and the instrument is the likely fault rather
#: than the machine. *"Above roughly 5 kW/TR on a running water-cooled centrifugal machine,
#: suspect the instrument rather than the equipment."*
EFFICIENCY_SUSPECT_ABOVE: float = 5.0

#: Above this it is not a bad reading, it is an impossible one — flow ≈ 0 drives kW/TR to
#: 100–150 against a design of 0.65–0.85, *"wrong by two orders of magnitude, not by a
#: margin."* `app/analytics/gates.py` already refuses beyond 10; kept consistent deliberately.
EFFICIENCY_IMPOSSIBLE_ABOVE: float = 10.0

#: *"Genuinely poor-but-real performance sits around 1.3–2.4 kW/TR."* This is the band that
#: partly answers `Q21`: our healthiest measured month at **1.40** is poor-but-real, not an
#: instrument fault — which the design band of 0.65–0.85 alone would have suggested.
EFFICIENCY_POOR_BUT_REAL: tuple[float, float] = (1.3, 2.4)

#: *"the chilled-water delta-T is normal (roughly 3–7 °C)"*. Used only as the *sibling*
#: condition in the impossible-combination test — never as a fault threshold of its own.
DELTA_T_NORMAL_C: tuple[float, float] = (3.0, 7.0)

#: A flow reading at or below this counts as "effectively zero" for the combination test.
#: The source gives no figure, and one is not invented: zero is used literally, and the
#: constant exists so the choice is visible rather than buried in an `== 0`.
FLOW_EFFECTIVELY_ZERO: float = 0.0

#: Signals with a physical floor of zero. A negative value on one of these is an absent
#: reading, never a small one. Residual columns are deliberately absent — see the docstring.
FLOORED_AT_ZERO: frozenset[str] = frozenset(
    {
        "chiller_flow",
        "cond_flow",
        "evap_flow",
        "tr",
        "trh",
        "kw",
        "kwh",
        "suction_pressure",
        "discharge_pressure",
        "comp1_oil_pressure",
        "comp2_oil_pressure",
    }
)


class Verdict(StrEnum):
    """What the arithmetic concluded about a *reading*, never about a machine."""

    CREDIBLE = "credible"
    """No contradiction found. Not the same as healthy — it means the number may be read."""

    INVALID_NEGATIVE = "invalid_negative"
    """Below a physical floor. **Absent, not small** — constraint 19."""

    IMPOSSIBLE_COMBINATION = "impossible_combination"
    """Signals contradict each other. The machine is plainly doing something the readings
    say it cannot."""

    IMPLAUSIBLE_EFFICIENCY = "implausible_efficiency"
    """The denominator has collapsed. Check flow and ΔT before the compressor."""

    STUCK_TAG = "stuck_tag"
    """Flat while siblings vary. A tag frozen in software looks identical to a failed sensor
    in the historian."""

    NEVER_MEASURED = "never_measured"
    """No credible value has ever been recorded. The measurement does not exist at this site."""


class Route(StrEnum):
    """Where an instrument fault goes. `F6`'s output, and the reason it exists.

    Taken from the playbook's own three-part response, because *"add a plausibility alarm"*
    and *"check the 4–20 mA loop"* land on different people.
    """

    NONE = "none"
    OPERATOR = "operator"
    """Compare the suspect tag against its siblings; confirm the running state independently."""

    INSTRUMENTATION = "instrumentation"
    """Verify the transmitter loop — power, wiring, 4–20 mA at transmitter and panel."""

    SUPERVISOR = "supervisor"
    """Add to a periodic validation route; decide whether to commission a missing measurement."""


@dataclass(frozen=True)
class ValidityFinding:
    """One contradiction, with the words a reader can act on."""

    signal: str
    verdict: Verdict
    reason: str
    route: Route = Route.NONE

    @property
    def is_instrument_fault(self) -> bool:
        """`F6`. When this is true the case must **not** dispatch a crew to the machine."""
        return self.verdict is not Verdict.CREDIBLE

    @property
    def excludes_the_slot(self) -> bool:
        """*"Exclude the slots; do not average them in."* A figure computed over an invalid
        slot is wrong by orders of magnitude, not by a margin."""
        return self.verdict in {
            Verdict.INVALID_NEGATIVE,
            Verdict.IMPOSSIBLE_COMBINATION,
            Verdict.IMPLAUSIBLE_EFFICIENCY,
        }

    def render(self) -> str:
        return f"{self.signal}: {self.reason}"


def check_negative(signal: str, value: float | None) -> ValidityFinding | None:
    """Constraint 19. **Never take the absolute value before judging credibility.**

    Returns `None` for a signal with no physical floor — a residual may be negative and that
    is a reading, not a fault.
    """
    if value is None or signal not in FLOORED_AT_ZERO or value >= 0:
        return None
    return ValidityFinding(
        signal=signal,
        verdict=Verdict.INVALID_NEGATIVE,
        reason=(
            f"reads {value}, and this signal has a physical floor of zero. That is an absent "
            f"reading, not a small one — usually a controller reset, a re-scaled tag or a "
            f"sensor-fault sentinel. It must not be read as {abs(value)} of anything."
        ),
        route=Route.INSTRUMENTATION,
    )


def check_flow_against_delta_t_and_power(
    flow: float | None,
    delta_t: float | None,
    power_kw: float | None,
    signal: str = "chiller_flow",
) -> ValidityFinding | None:
    """The headline impossible combination, and the one that blinded our own plant for months.

    Cooling output is computed from flow × ΔT. A chiller genuinely circulating nothing cannot
    simultaneously produce a temperature difference across the evaporator and draw full power.

    **Power is tested as "drawing power at all", not against a band.** The source gives
    *"e.g. 150–200 kW on a large water-cooled machine"* — an illustration, not a threshold,
    and our two chillers are not that machine. Inventing a band here would be exactly the
    failure the rule against unsourced numbers prevents. `Q55`.
    """
    if flow is None or delta_t is None or power_kw is None:
        return None
    if flow > FLOW_EFFECTIVELY_ZERO or power_kw <= 0:
        return None

    low, high = DELTA_T_NORMAL_C
    if not (low <= abs(delta_t) <= high):
        return None

    return ValidityFinding(
        signal=signal,
        verdict=Verdict.IMPOSSIBLE_COMBINATION,
        reason=(
            f"reads {flow} while the chilled-water ΔT is {delta_t} °C and the machine is "
            f"drawing {power_kw} kW. A chiller circulating nothing cannot produce a "
            f"temperature difference across the evaporator and draw power at the same time, "
            f"so the flow reading is wrong — this is a dead transmitter or a stuck tag, not a "
            f"chiller fault. Do not dispatch a crew to the machine."
        ),
        route=Route.INSTRUMENTATION,
    )


def check_efficiency(kw_per_tr: float | None) -> ValidityFinding | None:
    """Three bands, all sourced. Poor-but-real is not an instrument fault, and saying so is
    what stops a genuinely inefficient machine being dismissed as a bad sensor."""
    if kw_per_tr is None:
        return None

    if kw_per_tr < 0:
        return check_negative("kw_per_tr", kw_per_tr) or ValidityFinding(
            signal="kw_per_tr",
            verdict=Verdict.INVALID_NEGATIVE,
            reason=f"computes to {kw_per_tr}, which is not a physical efficiency.",
            route=Route.INSTRUMENTATION,
        )

    if kw_per_tr > EFFICIENCY_IMPOSSIBLE_ABOVE:
        return ValidityFinding(
            signal="kw_per_tr",
            verdict=Verdict.IMPLAUSIBLE_EFFICIENCY,
            reason=(
                f"computes to {kw_per_tr}, which is not a bad score but an impossible one. "
                f"The denominator has collapsed — check flow and ΔT before the compressor. "
                f"Exclude this slot rather than averaging it in."
            ),
            route=Route.INSTRUMENTATION,
        )

    if kw_per_tr > EFFICIENCY_SUSPECT_ABOVE:
        return ValidityFinding(
            signal="kw_per_tr",
            verdict=Verdict.IMPLAUSIBLE_EFFICIENCY,
            reason=(
                f"computes to {kw_per_tr}. Above roughly {EFFICIENCY_SUSPECT_ABOVE} kW/TR on a "
                f"running water-cooled machine, suspect the instrument rather than the "
                f"equipment — check the flow and ΔT inputs first."
            ),
            route=Route.OPERATOR,
        )
    return None


def is_poor_but_real(kw_per_tr: float | None) -> bool:
    """Genuinely poor performance, not a measurement fault.

    Partly answers `Q21`. Our healthiest measured month was **1.40**, which the design band
    of 0.65–0.85 alone would have made look broken. It is not: it is poor, and real.
    """
    if kw_per_tr is None:
        return False
    low, high = EFFICIENCY_POOR_BUT_REAL
    return low <= kw_per_tr <= high


def check_flatline(
    signal: str, values: Sequence[float | None], sibling_values: Sequence[float | None]
) -> ValidityFinding | None:
    """A tag holding constant **while siblings vary** is stuck.

    The sibling condition is the whole test and is not optional: a genuinely steady plant
    makes *everything* steady, and flagging that would bury real findings under a flood of
    false ones. Our own `dpt` is the case — a flat 107.0 on one chiller and 112.9 on the
    other, which is why condenser approach cannot be computed at all (`Q8`).
    """
    present = [v for v in values if v is not None]
    siblings = [v for v in sibling_values if v is not None]
    if len(present) < 2 or len(siblings) < 2:
        return None

    if len(set(present)) > 1:
        return None
    if len(set(siblings)) <= 1:
        return None

    return ValidityFinding(
        signal=signal,
        verdict=Verdict.STUCK_TAG,
        reason=(
            f"holds a constant {present[0]} across {len(present)} readings while sibling "
            f"signals on the same circuit vary normally. A tag frozen in software looks "
            f"identical to a failed sensor in the historian — check for a stuck or overridden "
            f"value in the BMS before replacing anything."
        ),
        route=Route.OPERATOR,
    )


def assess_slot(
    *,
    chiller_flow: float | None = None,
    chw_delta_t: float | None = None,
    kw: float | None = None,
    kw_per_tr: float | None = None,
    extra_signals: dict[str, float | None] | None = None,
) -> tuple[ValidityFinding, ...]:
    """Every contradiction visible in one slot, in the playbook's own reading order.

    *"Can the inputs be believed?"* comes first, deliberately — interpreting a number before
    checking whether it can be believed is the ordering that produced two months of invalid
    efficiency figures.
    """
    findings: list[ValidityFinding] = []

    combination = check_flow_against_delta_t_and_power(chiller_flow, chw_delta_t, kw)
    if combination is not None:
        findings.append(combination)

    for name, value in {"chiller_flow": chiller_flow, "kw": kw, **(extra_signals or {})}.items():
        negative = check_negative(name, value)
        if negative is not None:
            findings.append(negative)

    efficiency = check_efficiency(kw_per_tr)
    if efficiency is not None:
        findings.append(efficiency)

    return tuple(findings)


def blocks_dispatch(findings: Sequence[ValidityFinding]) -> tuple[bool, str]:
    """`F6`. Should a crew be sent to the machine?

    **No, if any finding says the instrument is the fault.** Rules out instrumentation before
    dispatching, which is the feature's whole purpose — the alternative sends somebody to
    overhaul a healthy compressor.
    """
    instrument_faults = [f for f in findings if f.is_instrument_fault]
    if not instrument_faults:
        return False, "no contradiction was found in the readings this rests on"
    reasons = "; ".join(f.render() for f in instrument_faults)
    return True, (
        f"{len(instrument_faults)} reading(s) contradict each other, so the fault may be the "
        f"measurement rather than the machine: {reasons}"
    )
