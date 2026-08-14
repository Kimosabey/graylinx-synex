"""The per-signal provenance registry — `C26`, and the one signal our own database invented.

Marking a whole *window* simulated is one level too coarse, and this module is why. In our
data every synthetic signal continues something the plant genuinely measures — except
`cond_flow`, which the simulation fabricated outright. The first is a weaker reading. The
second implies **an instrumentation capability the site does not have**, which is a
different and worse claim, and no disclosure banner fixes it.

Measured on `graylinx_synex`, 2026-08-11, over 31,884 real slots on `chiller_1_normalized`:

| Signal | Real window | Simulated window |
|---|--:|--:|
| `cond_flow` | **0 non-zero, max 0.0** | 3,354 non-zero, max 893.7 |
| `dpt` | 8,089 non-zero | **0** |

`chiller_2_normalized` matches, with 3,592 synthetic values reaching 1,099.6.

**Why this is the most consequential module in the domain layer.** Condenser flow feeds four
of the six models. A demonstration run on the most recent data — the natural choice, since it
runs to five days ago — would show condenser flow reading healthily, the models resolving
cleanly and the differential narrowing with confidence, on a measurement the reference plant
cannot take at all. `NEVER_MEASURED` here is what makes that impossible rather than merely
discouraged.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SignalStatus(StrEnum):
    """What this plant can actually tell us about a signal."""

    MEASURED = "measured"
    """A real instrument reports it, and the readings are usable."""

    NEVER_MEASURED = "never_measured"
    """The column exists and no credible value has ever been recorded in it.

    Not "missing", not zero. `cond_flow` is 0 of 31,884 measured readings — the tag is
    wired, the meter is not."""

    CONSTANT = "constant"
    """The column changes value never. Present, and carrying no information.

    `dpt` is a flat 107.0 on chiller 1 and 112.9 on chiller 2, which is why condenser
    approach temperature cannot be computed at all. That is Q8, unanswerable until fixed."""

    SUSPECT = "suspect"
    """Readings exist and are contradicted by other signals.

    Not the same as invalid. Both chilled-water flow transmitters have read near zero since
    May while ΔT and power stayed normal — physically impossible, and a single-signal
    validity flag did not catch it. `F16` is the cross-signal check."""


@dataclass(frozen=True)
class Signal:
    key: str
    display_name: str
    unit: str | None
    status: SignalStatus
    note: str = ""

    @property
    def is_usable(self) -> bool:
        """Only `MEASURED` may be read as a value. Everything else is a stated absence.

        `SUSPECT` is deliberately unusable. Constraint 19: do not take the absolute value
        of a signal before judging credibility — `ABS()` let a flow reading of −2.49 count
        as credible and understated a dead transmitter by 62 days.
        """
        return self.status is SignalStatus.MEASURED


COND_FLOW = Signal(
    key="cond_flow",
    display_name="condenser flow",
    unit="m3/h",
    status=SignalStatus.NEVER_MEASURED,
    note=(
        "0 non-zero in 31,884 measured slots on both chillers. Feeds four of the six models, "
        "so the whole efficiency and high-head branch is NO_DIAGNOSIS by design. The "
        "simulated window fabricates it to a max of 893.7 — D-009."
    ),
)

DPT = Signal(
    key="dpt",
    display_name="differential pressure transmitter",
    unit="kPa",
    status=SignalStatus.CONSTANT,
    note=(
        "A flat 107.0 on chiller 1 and 112.9 on chiller 2. Condenser approach temperature "
        "cannot be computed at all — Q8. Absent entirely from the simulated window."
    ),
)

CHILLER_FLOW = Signal(
    key="chiller_flow",
    display_name="chilled water flow",
    unit="m3/h",
    status=SignalStatus.SUSPECT,
    note=(
        "Identical to dpt to the digit wherever the data is real — same zero counts, maxima "
        "and distinct-value counts — so chiller_flow = 1.0 x dpt + 0.0 holds on measured "
        "data and breaks only where the data was generated. Both transmitters have read "
        "near zero since May while ΔT and power stayed normal, which is impossible. F16."
    ),
)

COND_LEAVING_TEMP = Signal(
    key="cond_leaving_temp",
    display_name="condenser leaving temperature",
    unit="C",
    status=SignalStatus.SUSPECT,
    note=(
        "Reaches −273.2 on both chillers — absolute zero used as a sensor sentinel. It must "
        "be rejected, never averaged into a residual. Condenser ΔT is also negative every "
        "month on one chiller, so the two columns are swapped or mislabelled. F16."
    ),
)

KW_PER_TR = Signal(
    key="kw_per_tr",
    display_name="efficiency",
    unit="kW/TR",
    status=SignalStatus.SUSPECT,
    note=(
        "Ranges −6,265 to +30,183 on chiller 1, because efficiency was computed while flow "
        "was near zero. A figure that large is not a bad score, it is a meaningless one — "
        "so it is a stated absence rather than a number. C21."
    ),
)

SIGNALS: tuple[Signal, ...] = (
    COND_FLOW,
    DPT,
    CHILLER_FLOW,
    COND_LEAVING_TEMP,
    KW_PER_TR,
)

_BY_KEY: dict[str, Signal] = {s.key: s for s in SIGNALS}

#: Absolute zero, used by at least one transmitter here as a failure sentinel rather than a
#: temperature. Any reading at or below this is an instrument reporting its own death.
ABSOLUTE_ZERO_C: float = -273.15


def by_key(key: str) -> Signal | None:
    """Unregistered signals return `None`, and the caller treats that as *no claim made*.

    Deliberately not a default of `MEASURED`: this registry names the signals we have
    measured something *about*. Silence here is not a clean bill of health — inherited
    constraint 7, applied to signals rather than to fault counts.
    """
    return _BY_KEY.get(key)


def status_of(key: str) -> SignalStatus | None:
    signal = _BY_KEY.get(key)
    return signal.status if signal else None


def never_measured_keys() -> tuple[str, ...]:
    return tuple(s.key for s in SIGNALS if s.status is SignalStatus.NEVER_MEASURED)


def unusable_keys() -> tuple[str, ...]:
    """Every signal that must render as a stated absence rather than as a number."""
    return tuple(s.key for s in SIGNALS if not s.is_usable)
