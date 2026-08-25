"""`A1` one equipment story — and the last section, which says what cannot be said about it.

**The failure this prevents.** A one-page asset view that lists health, models, faults and
open work reads as a complete account of the machine. On this plant that page would be a lie
of omission, and every one of its omissions has been measured:

| What the page would not say | Measured |
|---|---|
| Condenser flow has never been metered here | **0 non-zero in 37,430 measured slots**, and
  four of the five models fitted on a chiller take it as an input |
| Condenser approach cannot be computed at all | `dpt` holds a flat **107.0** on chiller 1 and
  **112.9** on chiller 2 — present, carrying nothing. `Q8` |
| The chilled-water flow instrument died while its column kept filling | It stopped reading
  credibly after **2026-04-22**, and the re-clone moved that boundary *earlier* within the day |
| The design names six models and five are fitted | `compressor_power_residual` is not fitted
  anywhere in the measured window |
| The same model is not the same model on the two machines | **nRMSE 48.03** on chiller 1
  against **2.65** on chiller 2 — an eighteenfold gap between two machines of one type |

A page that showed five models, nine labels and a work queue and stopped there would tell a
reader the machine is understood. That is the reassuring lie, and this module exists to make
it unavailable: **`cannot_say` is never empty for a scoreable asset**, a test asserts it, and
`render()` puts it last because last is where a reader stops.

**Every absence here is words.** Inherited constraint 14 — a figure is a value or a stated
absence, never both and never neither — is enforced in `ModelLine.__post_init__` rather than
asked for, the same way `Figure` enforces it. There is no dash anywhere in this module's
output and no zero standing in for a measurement nobody took.

**Nothing is inferred from silence.** Constraint 7: `NULL` means not diagnosed, never healthy,
and a blind two-month window once read as a clean plant. So an asset with no episodes supplied
reports *nothing was read*, and an asset with nothing open reports *nothing is open* beside
the **7,662 unlabelled slots** in the window — quiet is not the same as clean.

**This module lives in `services` and holds no driver.** It assembles what `domain` and
`analytics` already know plus whatever rows the caller read; the computed provenance verdict
arrives as a `SignalNote` rather than as a `SignalAvailability`, so a read surface with no
rows of its own never reaches into `db`.

**Nothing here calls a model.** The register marks `A1` as `SW + LLM`; the language model's
half is narrating this page, never assembling it, and it never decides what belongs in the
last section. `services` is prompt-free and model-free by contract 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.analytics.episodes import Episode
from app.analytics.honesty import DataWindow
from app.domain import equipment as eq
from app.domain import faults, residuals, signals
from app.domain.signals import SignalStatus

# ── constraints held as data ────────────────────────────────────────────────────

#: Which fitted models take condenser flow as an input. `CONTEXT.md` §6 is the source:
#: condenser flow feeds DP, DT, Power and Cond Leaving — four of the six designed models —
#: and without a trustworthy signal the whole efficiency and high-head branch is
#: `NO_DIAGNOSIS` plus a data-quality work order, by design on day one. That is `Q1`, the
#: highest-leverage open question in the programme.
#:
#: TBD (Q73): §6 names its models DP, SP, DT, Power, Comp Amps and Cond Leaving.
#: `gla_equipment_model_metrics` names them `Discharge_Pres`, `Suction_Pres`,
#: `Discharge_Temp`, `Chiller_Current` and `Condenser_Leav_Temp`. **No document states the
#: correspondence.** The reading taken here is `Chiller_Current` = §6's *Power* (chiller amps
#: or power), which leaves §6's *Comp Amps* as the unfitted `compressor_power_residual` — a
#: reading supported by that column's own name, and by Comp Amps being the one model of the
#: six that takes no condenser flow at all. If it is wrong the count falls from four to three
#: and the compressor branch gains a model, so the story states which way it was read rather
#: than printing a bare four.
MODELS_TAKING_COND_FLOW: frozenset[str] = frozenset(
    {"Discharge_Pres", "Discharge_Temp", "Chiller_Current", "Condenser_Leav_Temp"}
)

#: How the correspondence above was read, in the words the story carries. Held beside the set
#: so that the claim and its caveat cannot drift apart.
COND_FLOW_MAPPING_CAVEAT: str = (
    "the source names its models DP, SP, DT, Power, Comp Amps and Cond Leaving and the "
    "metrics table names them differently; Chiller_Current has been read as the Power model "
    "and Comp Amps as the unfitted compressor residual, which no document confirms (Q73)"
)

#: `dpt`'s constant value per asset, measured and recorded in `CONTEXT.md` §10a. Held per
#: asset because the two machines hold *different* constants, which is itself the evidence
#: that neither is a reading: a shared plant condition would not produce two flat numbers
#: five apart.
CONSTANT_DPT_VALUE: dict[str, float] = {"chiller_1": 107.0, "chiller_2": 112.9}

#: The last day the chilled-water flow transmitters read credibly. Both of them, on both
#: machines. Sourced from `app/db/provenance.py`, which computed it rather than asserting it.
#:
#: The 2026-08-17 re-clone moved the boundary *earlier* within this day — from 17:35 to 00:00
#: — because the rest of it was derived rather than read. A verdict that got more honest when
#: a marker arrived is the one worth trusting, so the date is carried at day granularity.
CHILLER_FLOW_LAST_CREDIBLE: date = date(2026, 4, 22)


class Silence(StrEnum):
    """Why something cannot be said about this asset. **Twelve kinds, and none is a gap.**

    They are kept apart rather than collapsed into "unavailable" because the reasons send a
    reader to different places: *the meter does not exist* is a capital question, *the
    instrument died* is a work order, and *the model fits badly* is a modelling问题 nobody
    should take to a machine.
    """

    NO_REFERENCE_BAND = "no_reference_band"
    """No model, no band, no fitted residual — so **nothing may be said at all**. Ten of the
    twelve equipment tables land here, and that is the correct answer rather than a gap."""

    NOTHING_WAS_READ = "nothing_was_read"
    """No episodes were supplied for this asset in this window. Constraint 7: `NULL` means not
    diagnosed, never healthy — an empty queue on a blind window once read as a clean plant."""

    NEVER_MEASURED = "never_measured"
    """The tag is wired and the meter is not. `cond_flow`, 0 non-zero in 37,430 measured
    slots, and four of the five fitted models take it as an input."""

    MODEL_NOT_FITTED = "model_not_fitted"
    """The design names a model that does not exist over this window. `Q1`'s smaller sibling:
    a branch of the isolation path with nothing behind it."""

    CONSTANT_SIGNAL = "constant_signal"
    """The column never changes value. Present, carrying nothing — `dpt`, and why condenser
    approach temperature cannot be computed at all (`Q8`)."""

    INSTRUMENT_STOPPED = "instrument_stopped"
    """Real readings exist, and they collapsed while the column went on filling. The failure a
    non-zero count cannot see."""

    SIGNAL_CONTRADICTED = "signal_contradicted"
    """Other signals on the same circuit make this one impossible. `F16`, and the reason a
    single-signal validity flag missed two months of it."""

    VALUE_WAS_COMPUTED = "value_was_computed"
    """Derived, not read. *Derived may be quoted, simulated may not* — quoted **with its
    label**, and no rendering path attaches one yet."""

    FIT_IS_PARTLY_ERROR = "fit_is_partly_error"
    """The model's own error is large enough that its residual is partly that error rather
    than the machine. Not a suppression: a badge (`Q50`)."""

    NOT_COMPARABLE_ACROSS_ASSETS = "not_comparable_across_assets"
    """The same model, the same label, two machines, and they do not mean the same thing.
    Models are fitted per asset and never per fleet."""

    NOT_SEPARABLE = "not_separable"
    """The class the model emitted declares in its own name that it could not separate the
    causes. Constraint 27: only these get a differential, and none of them gets a mechanism."""

    SEVERITY_NOT_AGREED = "severity_not_agreed"
    """No document states a severity for this class. `Q49`, and six of the seven fault classes
    are in it. Rendered as words, never defaulted to a plausible-looking `MEDIUM`."""


#: Reading order for the last section: **the silence that removes the most from the page leads
#: it.** Held as a tuple rather than sorted by any score, because ranking absences by
#: magnitude would be inherited constraint 3 wearing a different hat — and because a reader
#: who stops after one line should have read the one that changes what the rest of the page
#: means.
SILENCE_ORDER: tuple[Silence, ...] = (
    Silence.NO_REFERENCE_BAND,
    Silence.NOTHING_WAS_READ,
    Silence.NEVER_MEASURED,
    Silence.MODEL_NOT_FITTED,
    Silence.CONSTANT_SIGNAL,
    Silence.INSTRUMENT_STOPPED,
    Silence.SIGNAL_CONTRADICTED,
    Silence.VALUE_WAS_COMPUTED,
    Silence.FIT_IS_PARTLY_ERROR,
    Silence.NOT_COMPARABLE_ACROSS_ASSETS,
    Silence.NOT_SEPARABLE,
    Silence.SEVERITY_NOT_AGREED,
)

#: One `Silence` per provenance that is not `MEASURED`, as a map rather than a chain of
#: comparisons so that a new `SignalStatus` forces a decision here. That shape is what stops a
#: status nobody thought about falling through to *sayable* — which is exactly how `DERIVED`
#: would have arrived, since it did not exist until 2026-08-17.
STATUS_SILENCE: dict[SignalStatus, Silence] = {
    SignalStatus.NEVER_MEASURED: Silence.NEVER_MEASURED,
    SignalStatus.CONSTANT: Silence.CONSTANT_SIGNAL,
    SignalStatus.SUSPECT: Silence.SIGNAL_CONTRADICTED,
    SignalStatus.DERIVED: Silence.VALUE_WAS_COMPUTED,
}

#: What a `SUSPECT` status actually **is** on a given column. One word in `SignalStatus` covers
#: two different failures, and they send a reader to two different places: `chiller_flow`'s
#: transmitter *died* on a date this module already knows, which is a work order somebody
#: raises; `cond_leaving_temp` is *contradicted* by its own circuit, which is `F16` and a
#: mislabelled column. Without this map `Silence.INSTRUMENT_STOPPED` is defined, ordered and
#: unreachable, and a dead instrument renders as a contradiction — the exact collapse the
#: twelve kinds exist to refuse, hidden one layer further down than the enum that names them.
SUSPECT_SILENCE: dict[str, Silence] = {
    "chiller_flow": Silence.INSTRUMENT_STOPPED,
}

#: What each unusable signal costs this page, in the words a reader acts on. Keyed by signal,
#: because the consequence of a dead condenser-flow meter and a frozen `dpt` are different
#: questions for different people — and a generic *"unavailable"* would hide both.
SIGNAL_CONSEQUENCE: dict[str, str] = {
    "dpt": (
        "condenser approach temperature cannot be computed at all, which is both the fouling "
        "threshold and a question inside a differential, so neither can be answered from "
        "telemetry here (Q8)"
    ),
    "chiller_flow": (
        "evaporator ΔT, the efficiency proxy and every figure standing on chilled-water flow "
        "are not computable after that day. Both transmitters read near zero while ΔT and "
        "power stayed normal, which is physically impossible and blinded two months of "
        "efficiency figures before a cross-signal check existed (F16)"
    ),
    "cond_leaving_temp": (
        "condenser ΔT cannot be trusted on this asset. The column reaches −273.2, absolute "
        "zero used as a sensor sentinel, and ΔT reads negative every month on one chiller — a "
        "condenser rejects heat, so the two columns are swapped or mislabelled (F16)"
    ),
    "kw_per_tr": (
        "efficiency is a stated absence rather than a number here. It was computed while flow "
        "was near zero and ranges −6,265 to +30,183, which is not a bad score but a "
        "meaningless one (C21)"
    ),
}

#: Said instead of a consequence for a signal nobody has written one for. It claims nothing
#: about the plant, which is the point: the registry covers 5 of a normalised table's 38
#: columns, and inventing a consequence for the other 33 would be a second fabrication on top
#: of the absence it is describing.
UNWRITTEN_CONSEQUENCE: str = (
    "what this costs the page has not been worked out for this signal, so nothing is claimed "
    "about it either way"
)


# ── the pieces of the page ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class CannotSay:
    """One thing this page will not tell you, and why, and what it costs.

    Three fields rather than one sentence, because a reader needs all three and an interface
    that carries only the first produces *"efficiency: unavailable"* — which is the dash this
    module exists to refuse, spelled out in letters.
    """

    subject: str
    silence: Silence
    because: str
    consequence: str

    def render(self) -> str:
        return f"{self.subject} — {self.because}. {self.consequence}."


@dataclass(frozen=True)
class ModelLine:
    """One model on the roster: fitted with a fit, or absent with a reason.

    **A value xor a stated absence**, enforced in the constructor rather than asked for. The
    sixth model is the reason: `compressor_power_residual` was omitted from a roster once, and
    omission is precisely the failure inherited constraint 14 exists to prevent — a page
    listing five models where the design names six reads as complete.
    """

    model_name: str
    nrmse: float | None = None
    absence: str = ""
    takes_cond_flow: bool = False

    def __post_init__(self) -> None:
        if self.nrmse is None and not self.absence:
            raise ValueError(
                f"model {self.model_name!r} has no fit and no reason for not having one — "
                f"say one thing"
            )
        if self.nrmse is not None and self.absence:
            raise ValueError(
                f"model {self.model_name!r} carries both a fit ({self.nrmse}) and an absence "
                f"reason ({self.absence!r}) — say one thing"
            )

    @property
    def is_fitted(self) -> bool:
        return self.nrmse is not None

    @property
    def is_poor_fit(self) -> bool:
        """`False` for an unfitted model, and that is not a clean bill of health — an absent
        model has no fit to be poor. The page says so on its own line."""
        return self.nrmse is not None and self.nrmse >= residuals.POOR_FIT_NRMSE

    def render(self) -> str:
        if self.nrmse is None:
            return f"{self.model_name}: {self.absence}"
        text = f"{self.model_name}: nRMSE {self.nrmse}"
        if self.is_poor_fit:
            text += " — its residual is partly its own error rather than the machine"
        if self.takes_cond_flow:
            text += "; takes condenser flow as an input, which this site has never measured"
        return text


@dataclass(frozen=True)
class DiagnosisLine:
    """What this asset was labelled with, and how much of it there was.

    Slot counts and episode counts are both carried because they answer different questions.
    *"High head, ambiguous"* over 412 slots on ten days is one machine misbehaving for a
    fortnight; the same label on three slots is an afternoon. An interface that shows only one
    of the two cannot tell them apart.
    """

    fault_label: str
    episode_count: int
    slot_count: int
    first_day: date
    last_day: date
    severity_text: str
    declares_undecidable: bool
    is_fault: bool

    def render(self) -> str:
        span = (
            f"{self.first_day:%Y-%m-%d}"
            if self.first_day == self.last_day
            else f"{self.first_day:%Y-%m-%d} to {self.last_day:%Y-%m-%d}"
        )
        days = "day" if self.episode_count == 1 else "days"
        text = (
            f"{self.fault_label}: {self.slot_count} slots across {self.episode_count} {days}, "
            f"{span} — {self.severity_text}"
        )
        if self.declares_undecidable:
            text += "; the class name says the model could not separate the causes"
        return text


@dataclass(frozen=True)
class OpenItem:
    """One thing outstanding against this asset. Supplied by the caller, never derived here.

    Constraint 22 is why `opened_on` is required: four open cases once described transmitters
    repaired weeks earlier and twenty had been waiting since April, so an item shown without
    its age is an item nobody chases. Whether it has gone **stale** is `RC9`'s verdict and not
    this page's, so the story states the age and leaves the judgement alone.
    """

    reference: str
    kind: str
    """`case`, `work order`, `data-quality work order` — the caller's word, not a taxonomy."""

    fault_label: str
    opened_on: date
    state: str
    blocked_on: str = ""
    """Why it is not moving, in words. Empty means nobody recorded a blocker — which is
    different from *nothing is blocking it*, and the render says so rather than leaving the
    line to trail off."""

    def age_text(self, as_of: date | None) -> str:
        """The age in words, or a stated reason for not having one.

        `as_of` is `None` on a page built without a reference date — a snapshot has no *now*,
        and inventing one would let a reader supply their own from their head, which is the
        failure constraint 15 exists to prevent one level up.
        """
        if as_of is None:
            return "its age is not stated, because this page was built without a reference date"
        days = (as_of - self.opened_on).days
        if days < 0:
            return f"opened {abs(days)} days after the date this page was built against"
        if days == 0:
            return "opened on the day this page was built against"
        return f"open for {days} day{'s' if days != 1 else ''}"

    def render(self, as_of: date | None = None) -> str:
        blocker = (
            f"blocked on {self.blocked_on}"
            if self.blocked_on
            else "no blocker was recorded against it, which is not the same as nothing "
            "blocking it"
        )
        return (
            f"{self.kind} {self.reference} ({self.fault_label}), {self.state} — "
            f"{self.age_text(as_of)}; {blocker}"
        )


@dataclass(frozen=True)
class SignalNote:
    """One signal's provenance as **computed** for this asset, rather than as registered.

    `app/db/provenance.py` derives availability per column from the two marker tables and is
    the authority; `app/domain/signals.py` is the five signals somebody verified by hand. The
    story prefers a computed verdict where it has one, so a plant that commissions a condenser
    flow meter tomorrow stops being told it never had one.

    Carried as three plain fields rather than as `SignalAvailability` so that a read surface
    with no rows of its own never has to reach into `db` for this page.
    """

    column: str
    status: SignalStatus
    rendered: str


@dataclass(frozen=True)
class AssetStory:
    """One asset, one page. Five sections, and the fifth is the one that makes it honest."""

    equipment_key: str
    display_name: str
    kind: str
    scoreable: bool
    window: DataWindow
    """Required, not optional. Inherited constraint 15: every artefact states its data window,
    because anomaly counts were once shown on the database wall clock under a heading
    describing a telemetry window that did not overlap it at all."""

    models: tuple[ModelLine, ...] = ()
    diagnoses: tuple[DiagnosisLine, ...] = ()
    open_items: tuple[OpenItem, ...] = ()
    cannot_say: tuple[CannotSay, ...] = ()
    as_of: date | None = None

    @property
    def fitted_model_count(self) -> int:
        return sum(1 for m in self.models if m.is_fitted)

    @property
    def blocked_model_count(self) -> int:
        """Fitted models whose input this site has never measured. Four of five on a chiller."""
        return sum(1 for m in self.models if m.is_fitted and m.takes_cond_flow)

    @property
    def fault_count(self) -> int:
        """Labels that are faults. `NO_DIAGNOSIS` and `NO_EFFICIENCY_FAULT` are outcomes."""
        return sum(1 for d in self.diagnoses if d.is_fault)

    def silences_of(self, kind: Silence) -> tuple[CannotSay, ...]:
        return tuple(c for c in self.cannot_say if c.silence is kind)

    def render(self) -> str:
        """The page, in reading order, with the last section last.

        The order is the argument. A reader who stops halfway has read the capabilities and
        not the limits, so the limits are not halfway — they are where a reader stops.
        """
        return "\n".join(
            (
                f"{self.display_name} ({self.equipment_key}) — {self.kind}",
                f"Window: {self.window.render()}",
                "",
                self._section("Models", [m.render() for m in self.models], self._no_models()),
                "",
                self._section(
                    "Diagnosed with",
                    [d.render() for d in self.diagnoses],
                    self._nothing_diagnosed(),
                ),
                "",
                self._section(
                    "Open against it",
                    [o.render(self.as_of) for o in self.open_items],
                    "Nothing is open against this asset. The window also carries "
                    f"{faults.UNLABELLED_SLOTS:,} slots the model never labelled at all, so "
                    "an empty queue here is quiet rather than clean.",
                ),
                "",
                self._section(
                    "What cannot be said about it",
                    [c.render() for c in self.cannot_say],
                    "Nothing was withheld — and on this plant that is a defect in this page "
                    "rather than a property of the machine.",
                ),
            )
        )

    def _nothing_diagnosed(self) -> str:
        """*Nobody looked* and *we looked and found nothing* are two different absences.

        `build` keeps them apart — `episodes=None` against `episodes=()` — and records the
        first as `Silence.NOTHING_WAS_READ`. This section printed the *nobody looked* sentence
        for both, so an asset whose history had genuinely been read was told, in words, that it
        had not been. Neither reading means the machine is clean; they differ in what the reader
        should do next, which is the whole reason the two are kept apart upstream.
        """
        if self.silences_of(Silence.NOTHING_WAS_READ):
            return (
                "Nothing was read for this asset in this window. That is not a clean machine — "
                "it is an absence of evidence, and a blind window once read as a clean plant."
            )
        return (
            "The fault history was read and this asset carried no label in this window. That "
            "is a different statement from nobody having looked, and it is still not a clean "
            "machine — a NULL means not diagnosed, never healthy."
        )

    def _no_models(self) -> str:
        return (
            "No model is fitted for this asset, so no residual can be judged high or normal "
            "against its own history. Ten of the twelve equipment tables are in this position, "
            "and it is the correct answer rather than a gap."
        )

    @staticmethod
    def _section(heading: str, lines: list[str], when_empty: str) -> str:
        body = "\n".join(f"  - {line}" for line in lines) if lines else f"  {when_empty}"
        return f"{heading}:\n{body}"

    def as_dict(self) -> dict:
        return {
            "equipment_key": self.equipment_key,
            "display_name": self.display_name,
            "kind": self.kind,
            "scoreable": self.scoreable,
            "window": self.window.as_dict(),
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "models": [
                {
                    "model_name": m.model_name,
                    "nrmse": m.nrmse,
                    "absence": m.absence,
                    "takes_cond_flow": m.takes_cond_flow,
                    "is_poor_fit": m.is_poor_fit,
                    "text": m.render(),
                }
                for m in self.models
            ],
            "diagnoses": [
                {
                    "fault_label": d.fault_label,
                    "episode_count": d.episode_count,
                    "slot_count": d.slot_count,
                    "severity_text": d.severity_text,
                    "declares_undecidable": d.declares_undecidable,
                    "is_fault": d.is_fault,
                    "text": d.render(),
                }
                for d in self.diagnoses
            ],
            "open_items": [
                {
                    "reference": o.reference,
                    "kind": o.kind,
                    "fault_label": o.fault_label,
                    "state": o.state,
                    "opened_on": o.opened_on.isoformat(),
                    "text": o.render(self.as_of),
                }
                for o in self.open_items
            ],
            "cannot_say": [
                {
                    "subject": c.subject,
                    "silence": c.silence.value,
                    "because": c.because,
                    "consequence": c.consequence,
                    "text": c.render(),
                }
                for c in self.cannot_say
            ],
        }


# ── the roster ──────────────────────────────────────────────────────────────────

def model_lines(equipment_key: str) -> tuple[ModelLine, ...]:
    """Every model the design names for this asset — the fitted ones and the one that is not.

    **Six lines on a chiller, and five of them carry a number.** Returning only the five would
    make the roster agree with itself and disagree with the specification, which is the shape
    of omission constraint 14 forbids: a reader counting five models has no way to learn that
    a sixth was designed and never arrived.
    """
    fits = residuals.fits_for(equipment_key)
    if not fits:
        return ()

    lines = [
        ModelLine(
            model_name=f.model_name,
            nrmse=f.nrmse,
            takes_cond_flow=f.model_name in MODELS_TAKING_COND_FLOW,
        )
        for f in fits
    ]
    lines.append(
        ModelLine(
            model_name=residuals.ABSENT_RESIDUAL_COLUMN,
            absence=(
                "no model is fitted for this signal over the measured window. The design names "
                f"{residuals.DESIGNED_MODEL_COUNT} models per chiller and "
                f"{residuals.FITTED_MODEL_COUNT} are fitted"
            ),
        )
    )
    return tuple(lines)


def blocked_models(equipment_key: str) -> tuple[str, ...]:
    """The fitted models on this asset that take a signal this site has never measured."""
    return tuple(
        f.model_name
        for f in residuals.fits_for(equipment_key)
        if f.model_name in MODELS_TAKING_COND_FLOW
    )


@dataclass(frozen=True)
class FitGap:
    """The same model, two assets, two fits — and how far apart they are.

    Computed rather than quoted. `CONTEXT.md` records the 48.03-against-2.65 case in prose;
    deriving it means the sentence changes if the data does, instead of a document and a page
    disagreeing about a machine.
    """

    model_name: str
    worse_key: str
    worse_nrmse: float
    better_key: str
    better_nrmse: float

    @property
    def ratio(self) -> float:
        return self.worse_nrmse / self.better_nrmse

    def render(self) -> str:
        return (
            f"{self.model_name} runs at nRMSE {self.worse_nrmse} on {self.worse_key} against "
            f"{self.better_nrmse} on {self.better_key} — {self.ratio:.0f} times the error on "
            f"the same model between two machines of one type"
        )


def widest_fit_gap() -> FitGap | None:
    """The model whose fit differs most between the two scoreable assets.

    `None` when fewer than two assets carry a fit for any shared model, which is the honest
    answer on a site with one chiller: there is no comparison to refuse to make.
    """
    scoreable = [e.key for e in eq.scoreable_equipment()]
    best: FitGap | None = None
    for name in residuals.FITTED_MODEL_NAMES:
        pairs = [
            (key, fit.nrmse)
            for key in scoreable
            if (fit := residuals.fit_for(key, name)) is not None
        ]
        if len(pairs) < 2:
            continue
        worse = max(pairs, key=lambda p: p[1])
        better = min(pairs, key=lambda p: p[1])
        if better[1] <= 0:
            continue
        gap = FitGap(name, worse[0], worse[1], better[0], better[1])
        if best is None or gap.ratio > best.ratio:
            best = gap
    return best


# ── what was diagnosed ──────────────────────────────────────────────────────────

def diagnosis_lines(equipment_key: str, episodes: tuple[Episode, ...]) -> tuple[DiagnosisLine, ...]:
    """One line per label this asset carried, faults and non-fault outcomes alike.

    `NO_DIAGNOSIS` is included deliberately. It is the modal outcome — 5,309 slots against 674
    faulted — and a page that filtered it out would show a machine with three fault labels and
    no sign that the platform spent most of the window refusing to judge it.

    Sorted by slot count descending, then by label. That is a **display order and not a
    ranking**: constraint 3 forbids severity from magnitude, and constraint 36 forbids the
    longest-running label from leading anything. Nothing downstream may read position as
    importance, which is why no `primary` is returned here — `correlation.choose_primary` is
    where that question is answered, with a reason attached.
    """
    mine = [e for e in episodes if e.equipment_key == equipment_key]
    by_label: dict[str, list[Episode]] = {}
    for episode in mine:
        by_label.setdefault(episode.fault_label, []).append(episode)

    lines: list[DiagnosisLine] = []
    for label, group in by_label.items():
        fault = faults.by_label(label)
        lines.append(
            DiagnosisLine(
                fault_label=label,
                episode_count=len(group),
                slot_count=sum(e.slot_count for e in group),
                first_day=min(e.day for e in group),
                last_day=max(e.day for e in group),
                severity_text=_severity_text(label),
                declares_undecidable=bool(fault and fault.declares_undecidable),
                is_fault=bool(fault and fault.is_fault),
            )
        )
    return tuple(sorted(lines, key=lambda d: (-d.slot_count, d.fault_label)))


def _severity_text(label: str) -> str:
    """Words, always. `Q49`: only `CONDENSER_LOW_FLOW` has a sourced severity, and a class
    silently defaulted to `MEDIUM` is a number invented in the one place `F17` says must be
    authoritative."""
    severity = faults.severity_of(label)
    if severity is faults.Severity.UNRATED:
        return faults.UNRATED_SEVERITY_TEXT
    return f"severity {severity.value}"


# ── the last section ────────────────────────────────────────────────────────────

def _registered_status(column: str) -> SignalStatus | None:
    registered = signals.by_key(column)
    return registered.status if registered else None


def _signal_silence(
    equipment_key: str, column: str, status: SignalStatus, rendered: str
) -> CannotSay | None:
    """One unusable signal, turned into the sentence a reader acts on.

    `MEASURED` returns `None` — there is nothing to say about a signal that works, and
    manufacturing a line for it would bury the four that matter.
    """
    silence = STATUS_SILENCE.get(status)
    if silence is None:
        return None
    if status is SignalStatus.SUSPECT:
        silence = SUSPECT_SILENCE.get(column, silence)

    if column == "cond_flow":
        blocked = blocked_models(equipment_key)
        fitted = len(residuals.fits_for(equipment_key))
        if blocked:
            consequence = (
                f"{len(blocked)} of the {fitted} models fitted on this asset take it as an "
                f"input — {', '.join(blocked)} — so the efficiency and high-head branch is "
                f"NO_DIAGNOSIS plus a data-quality work order rather than an answer (Q1). "
                f"Read the count with its caveat: {COND_FLOW_MAPPING_CAVEAT}"
            )
        else:
            consequence = (
                "no model is fitted on this asset at all, so nothing here depended on it in "
                "the first place"
            )
    elif column == "dpt" and equipment_key in CONSTANT_DPT_VALUE:
        consequence = (
            f"it holds a flat {CONSTANT_DPT_VALUE[equipment_key]} on this machine and a "
            f"different flat value on the other, which is itself the evidence that neither is "
            f"a reading. {SIGNAL_CONSEQUENCE['dpt']}"
        )
    elif column == "chiller_flow":
        consequence = (
            f"it last read credibly on {CHILLER_FLOW_LAST_CREDIBLE:%Y-%m-%d}; "
            f"{SIGNAL_CONSEQUENCE['chiller_flow']}"
        )
    else:
        consequence = SIGNAL_CONSEQUENCE.get(column, UNWRITTEN_CONSEQUENCE)

    return CannotSay(
        subject=column, silence=silence, because=rendered, consequence=consequence
    )


def _signal_silences(
    equipment_key: str, notes: tuple[SignalNote, ...]
) -> tuple[CannotSay, ...]:
    """Every signal that must render as a stated absence on this asset.

    Computed notes win over the registry where they overlap, and registry entries that nothing
    computed still appear. Dropping the registry when a note set arrives would silently narrow
    the page to whatever the caller happened to query, and the caller is not the authority on
    what this plant cannot measure.
    """
    seen: dict[str, tuple[SignalStatus, str]] = {}
    for signal in signals.SIGNALS:
        if not signal.is_usable:
            seen[signal.key] = (signal.status, signal.note)
    for note in notes:
        seen[note.column] = (note.status, note.rendered)

    found: list[CannotSay] = []
    for column, (status, rendered) in sorted(seen.items()):
        entry = _signal_silence(equipment_key, column, status, rendered)
        if entry is not None:
            found.append(entry)
    return tuple(found)


def _model_silences(equipment_key: str) -> tuple[CannotSay, ...]:
    found: list[CannotSay] = []

    for line in model_lines(equipment_key):
        if line.is_fitted and line.is_poor_fit:
            found.append(
                CannotSay(
                    subject=line.model_name,
                    silence=Silence.FIT_IS_PARTLY_ERROR,
                    because=(
                        f"it fits at nRMSE {line.nrmse}, at or beyond the "
                        f"{residuals.POOR_FIT_NRMSE} this product treats as poor (Q50)"
                    ),
                    consequence=(
                        "its residual is partly the model's own error rather than the "
                        "machine, so an alarm raised on it may be an artefact. The badge is "
                        "shown and nothing is suppressed — a hidden fault would be the worse "
                        "error"
                    ),
                )
            )
        elif not line.is_fitted:
            found.append(
                CannotSay(
                    subject=line.model_name,
                    silence=Silence.MODEL_NOT_FITTED,
                    because=line.absence,
                    consequence=(
                        "the compressor-amps branch of the isolation path has no residual "
                        "behind it over this window, so where the trained model emitted a "
                        "compressor label this page can neither re-derive it nor contradict "
                        "it. Constraint 34 says consume that verdict rather than inventing a "
                        "second opinion, and this is what that costs"
                    ),
                )
            )

    # Only on an asset that actually carries that fit. `widest_fit_gap` is a fleet-level fact
    # and takes no equipment key, so appending it unconditionally put *"no figure on this page
    # may be compared with the same figure on the other"* onto a condenser pump's page — an
    # asset with no models, no fits and nothing to compare. That is a claim about a machine
    # invented from another machine's data, which is the failure this whole section exists to
    # refuse.
    gap = widest_fit_gap()
    if gap is not None and residuals.fit_for(equipment_key, gap.model_name) is not None:
        found.append(
            CannotSay(
                subject=f"{gap.model_name} across assets",
                silence=Silence.NOT_COMPARABLE_ACROSS_ASSETS,
                because=gap.render(),
                consequence=(
                    "an identical fault label on the two machines does not mean the same "
                    "thing, and no figure on this page may be compared with the same figure "
                    "on the other. Models are fitted per asset and never per fleet"
                ),
            )
        )
    return tuple(found)


def _diagnosis_silences(diagnoses: tuple[DiagnosisLine, ...]) -> tuple[CannotSay, ...]:
    found: list[CannotSay] = []
    for line in diagnoses:
        if line.declares_undecidable:
            found.append(
                CannotSay(
                    subject=line.fault_label,
                    silence=Silence.NOT_SEPARABLE,
                    because=(
                        "the class the trained model emitted declares in its own name that it "
                        "could not separate the causes"
                    ),
                    consequence=(
                        "no mechanism can be named from telemetry alone. A differential "
                        "narrows the candidates by asking somebody at the machine, and it can "
                        "end exhausted rather than settled — which is a different statement "
                        "from a conclusion (constraints 27 and 32)"
                    ),
                )
            )
        if line.is_fault and not faults.is_rated(line.fault_label):
            found.append(
                CannotSay(
                    subject=f"{line.fault_label} severity",
                    silence=Silence.SEVERITY_NOT_AGREED,
                    because="no document states a severity for this class (Q49)",
                    consequence=(
                        "how bad it is cannot be said, so it is rendered as words rather than "
                        "defaulted to a plausible-looking middle value. Severity comes from "
                        "fault class plus persistence and never from residual magnitude, "
                        "because non-faults were measured to deviate more than faults"
                    ),
                )
            )
    return tuple(found)


def cannot_say_for(
    equipment_key: str,
    *,
    diagnoses: tuple[DiagnosisLine, ...] = (),
    episodes_supplied: bool = True,
    signal_notes: tuple[SignalNote, ...] = (),
) -> tuple[CannotSay, ...]:
    """The last section, assembled — and for a scoreable asset it is never empty.

    Order is `SILENCE_ORDER`: the silence that removes the most from the page leads it, and
    within a kind the order is the order the pieces were found, which is alphabetical by
    signal and roster order by model. Stable, so the page does not rearrange itself between
    two readings of the same window.
    """
    found: list[CannotSay] = []

    if not eq.is_scoreable(equipment_key):
        found.append(
            CannotSay(
                subject=equipment_key,
                silence=Silence.NO_REFERENCE_BAND,
                because=(
                    "no model parameters, no reference band and no scored residual exist for "
                    "this asset"
                ),
                consequence=(
                    "no residual can be judged high or normal against this machine's own "
                    "healthy distribution, so nothing on it may be diagnosed. Judging it "
                    "against zero or against another asset's threshold would rank ordinary "
                    "operation above a real fault"
                ),
            )
        )

    if not episodes_supplied:
        found.append(
            CannotSay(
                subject="fault history",
                silence=Silence.NOTHING_WAS_READ,
                because="no labelled slots were supplied for this asset in this window",
                consequence=(
                    "that is an absence of evidence and not a healthy machine. A NULL means "
                    "not diagnosed, never healthy — a two-month window here was blind rather "
                    "than clean, and an empty queue read as a clean plant"
                ),
            )
        )

    found.extend(_signal_silences(equipment_key, signal_notes))
    found.extend(_model_silences(equipment_key))
    found.extend(_diagnosis_silences(diagnoses))

    rank = {kind: i for i, kind in enumerate(SILENCE_ORDER)}
    return tuple(sorted(found, key=lambda c: rank[c.silence]))


# ── the page ────────────────────────────────────────────────────────────────────

def build(
    equipment_key: str,
    *,
    window: DataWindow,
    episodes: tuple[Episode, ...] | None = None,
    open_items: tuple[OpenItem, ...] = (),
    signal_notes: tuple[SignalNote, ...] = (),
    as_of: date | None = None,
) -> AssetStory:
    """One asset, one page.

    `episodes` is `None` for *nobody read the fault history* and `()` for *the history was read
    and this asset carried nothing*. They are kept apart deliberately: collapsing them would
    let an unqueried asset render exactly like a clean one, which is inherited constraint 7
    reintroduced through a default argument.

    An unregistered key raises. `equipment.is_scoreable` answers `False` for an unknown key on
    purpose, but a *story* about a machine that is not in the registry is a page describing
    something that does not exist, and returning one would be worse than a stack trace.
    """
    equipment = eq.by_key(equipment_key)
    if equipment is None:
        raise ValueError(
            f"{equipment_key!r} is not in the equipment registry, so there is no asset to tell "
            f"a story about — this is a defect in the caller, not an absence in the plant"
        )

    supplied = episodes is not None
    diagnoses = diagnosis_lines(equipment_key, episodes or ())

    return AssetStory(
        equipment_key=equipment.key,
        display_name=equipment.display_name,
        kind=equipment.kind.value,
        scoreable=equipment.scoreable,
        window=window,
        models=model_lines(equipment_key),
        diagnoses=diagnoses,
        open_items=open_items,
        cannot_say=cannot_say_for(
            equipment_key,
            diagnoses=diagnoses,
            episodes_supplied=supplied,
            signal_notes=signal_notes,
        ),
        as_of=as_of,
    )
