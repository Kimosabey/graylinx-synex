"""The context budget — what fits in a prompt, and what is said about what did not.

**The failure this prevents: an answer built on two thirds of the evidence, presented as
though it were built on all of it.** `max_context_chars` is 24,000 and `max_input_chars` is
8,000 — both provisional against `Q48` — and for the whole life of this repository nothing
read either of them. They appeared in `config.py`, in a test asserting they exist, and nowhere
else. Measured on the seven `diagnose` turns recorded on the Jarvis box on 2026-08-17, the
message pair the brain received runs **5,712 to 5,929 characters** against that 24,000
ceiling, of which the fenced evidence block is **3,080 to 3,300**. A single-shot turn sits
well inside the ceiling; a turn that composes several episodes, a task trail and retrieved
passages does not, and it would overflow on an unpredictable turn — the worst possible place
to discover a limit.

**Dropping is allowed. Dropping silently is the failure.** Constraint 16 replaces a reassuring
headline outright rather than annotating it, and a prompt quietly shortened by a third is the
same shape one layer earlier. So every drop is reported twice — to the caller, and inside the
payload the model reads, so the answer itself can say what it rests on. Four things are never
dropped, in this order:

| | Never dropped | Because |
|---|---|---|
| 1 | the gate outcome | `NO_DIAGNOSIS` is the modal outcome — 5,309 slots against 674
  faulted — and a turn that lost the failed gate would answer as though the equipment had
  been fit to judge |
| 2 | any never-measured or suspect signal note | `cond_flow` has never recorded a non-zero
  value in 37,430 measured slots and feeds four of the six models |
| 3 | the data window | constraint 15 — anomaly counts were once shown under a heading
  describing a telemetry window that did not overlap them at all |
| 4 | the fault label | the trained model's own output, including the four class names that
  say `AMBIGUOUS` or `UNSPECIFIED` |

That order is not arbitrary. On the pack measured on 2026-08-17, signal provenance alone is
1,552 of 2,936 characters — 53% of the whole, the most expensive thing in the pack and the
least droppable. A residual dropped to fit costs a reader one line; *"this signal was never
measured"* dropped to fit costs them the reason the branch cannot be judged at all.

**Presence is checked, not assumed.** Ordering the payload first protects it only if it is
there. A caller that hands over sections with no gate outcome in them got a context with no
gate outcome and no complaint, which is the never-measured defect arriving by its own door —
an absence that reads as *nothing to say*. `AbsentPayload` names each missing tier, in words,
and the note goes into the text the model reads as well as back to the caller.

**Why this sits in `app.prompts` and not in `app.agents`.** It was written in
`app/agents/context.py` beside `C10` task memory, and `app.prompts` sits **below** `app.agents`
in the spine — so the one module that assembles a prompt structurally could not import the
thing that fits one. A budgeter the prompt builder cannot reach is a budgeter nothing is
fitted by, which is how it spent its first day with no consumer at all. `importlinter.ini`'s
own preamble records the alternative and refuses it: the fix for a contract that blocks a real
dependency is to move the shared thing to a layer both sides may see, not to add an exception.
`app/agents/context.py` re-exports every name here, so `C10` and the budget still read as one
idea from the agent layer.

**Nothing here calls a model, and nothing here decides.** Ordering is a fixed table, the
ceilings come from configuration, and no number is rendered — every value arrives as a display
string because the pack carries display strings rather than floats, and re-rendering one would
reintroduce a tolerance. The language model never grants itself more room: the budget is plain
software, like the Control Plane one row above it in the separation law.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.config import CONTEXT_TRUNCATION_MARKER, get_settings

SECTION_SEPARATOR = "\n"


class ContextTier(StrEnum):
    """What a piece of context *is*, which is what decides whether it may be given up.

    Held as a closed set rather than a number so the ordering is inspectable: a priority
    integer somebody nudges is how *"this signal was never measured"* ends up below a residual.
    """

    GATE_OUTCOME = "gate_outcome"
    SIGNAL_NOTE = "signal_note"
    DATA_WINDOW = "data_window"
    FAULT_LABEL = "fault_label"
    EVIDENCE = "evidence"
    SUPPORTING = "supporting"
    HISTORY = "history"


#: The honesty payload, **in the order the ceiling protects it**. Never dropped, whatever the
#: budget. Each entry is a measured failure: a lost gate outcome answers as though the machine
#: was fit to judge; a lost signal note lets `cond_flow` read as a reading rather than as an
#: instrument the plant does not have; a lost window is constraint 15's mismatched heading; a
#: lost label invents certainty the trained model never claimed.
HONESTY_PAYLOAD: tuple[ContextTier, ...] = (
    ContextTier.GATE_OUTCOME,
    ContextTier.SIGNAL_NOTE,
    ContextTier.DATA_WINDOW,
    ContextTier.FAULT_LABEL,
)

#: What is given up first when the budget bites. History before supporting detail, supporting
#: detail before evidence — a residual is the last thing surrendered, and it is surrendered
#: rather than the note that says a signal was never measured at all.
DROP_ORDER: tuple[ContextTier, ...] = (
    ContextTier.HISTORY,
    ContextTier.SUPPORTING,
    ContextTier.EVIDENCE,
)

#: What a reader loses when one of the four never-dropped tiers is **not there to protect**.
#: Held as data beside the tier rather than written into a message, so the reason a payload
#: matters and the check that it arrived cannot drift apart.
PAYLOAD_ABSENCE_COST: dict[ContextTier, str] = {
    ContextTier.GATE_OUTCOME: (
        "no gate outcome reached this prompt, so nothing says whether the equipment was fit "
        "to be judged at all. A refusal is the modal outcome on this plant — 5,309 slots "
        "against 674 faulted — and an answer written without it reads as though every check "
        "had passed"
    ),
    ContextTier.SIGNAL_NOTE: (
        "no signal provenance reached this prompt, so nothing says which signals this plant "
        "has never measured. Condenser flow has 0 non-zero values in 37,430 measured slots "
        "and feeds four of the six models; with no note, a missing reading reads as a zero"
    ),
    ContextTier.DATA_WINDOW: (
        "no data window reached this prompt. Constraint 15 — on a snapshot the reader "
        "supplies *now* from their own head and every tense in the answer inherits it"
    ),
    ContextTier.FAULT_LABEL: (
        "no fault label reached this prompt, so there is no verdict for the model to explain "
        "and nothing stopping it producing one. Four of seven classes declare themselves "
        "undecidable, and an answer with no label to anchor it is free to narrow anyway"
    ),
}


@dataclass(frozen=True)
class ContextSection:
    """One labelled piece of what the model will read, and what kind of thing it is."""

    key: str
    tier: ContextTier
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def is_honesty_payload(self) -> bool:
        return self.tier in HONESTY_PAYLOAD


@dataclass(frozen=True)
class DroppedSection:
    """Something that did not fit, and why — in words, never a count on its own."""

    key: str
    tier: ContextTier
    chars: int
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError(
                f"section {self.key!r} was dropped with no reason. A silent drop is the whole "
                f"failure this module exists to prevent"
            )

    def render(self) -> str:
        return f"{self.key} ({self.chars} characters) — {self.reason}"


@dataclass(frozen=True)
class AbsentPayload:
    """One of the four never-dropped tiers that was never handed over in the first place.

    **Not a drop and not a zero.** A drop is something this module gave up and can name; an
    absence is something the caller never supplied, and the two need different fixes — one is
    a budget too small, the other is a pack assembled wrong. Collapsing them would send
    somebody to raise a ceiling that was never the problem.
    """

    tier: ContextTier
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError(
                f"the {self.tier.value} payload was reported absent with no reason. An absence "
                f"a reader cannot act on is a dash wearing a sentence"
            )

    def render(self) -> str:
        return f"{self.tier.value} — {self.reason}"


def absent_payload_in(tiers: Sequence[ContextTier]) -> tuple[AbsentPayload, ...]:
    """Which of the four never-dropped tiers is missing from what the caller supplied.

    Checked rather than assumed, because ordering the payload first protects it only if it is
    there. A context assembled from sections carrying no gate outcome came back complete and
    silent before this existed.
    """
    present = set(tiers)
    return tuple(
        AbsentPayload(tier=tier, reason=PAYLOAD_ABSENCE_COST[tier])
        for tier in HONESTY_PAYLOAD
        if tier not in present
    )


def absence_note(absent: Sequence[AbsentPayload]) -> str:
    """The note the **model** reads when part of the honesty payload never arrived.

    It is told rather than left to infer, for the same reason the drop note exists: the answer
    is written by something that otherwise believes it saw everything it needed.
    """
    if not absent:
        return ""
    lines = "; ".join(a.render() for a in absent)
    return (
        f"{len(absent)} part(s) of the honesty payload were never supplied to this prompt and "
        f"are absent rather than empty: {lines}. Say what is missing rather than answering "
        f"around it."
    )


@dataclass(frozen=True)
class AssembledContext:
    """What fitted, what did not, what never arrived, and whether the turn may be sent at all."""

    text: str
    budget: int
    included: tuple[ContextSection, ...] = field(default_factory=tuple)
    dropped: tuple[DroppedSection, ...] = field(default_factory=tuple)
    absent_payload: tuple[AbsentPayload, ...] = field(default_factory=tuple)
    must_refuse: bool = False
    refusal_reason: str = ""

    @property
    def used_chars(self) -> int:
        return len(self.text)

    @property
    def is_complete(self) -> bool:
        """Nothing was dropped, nothing was missing, and the ceiling was not hit."""
        return not self.dropped and not self.absent_payload and not self.must_refuse

    @property
    def dropped_chars(self) -> int:
        return sum(d.chars for d in self.dropped)

    def render_drop_report(self) -> str:
        """What a route trace shows. An absence of drops is stated, not left blank."""
        missing = (
            " " + absence_note(self.absent_payload) if self.absent_payload else ""
        )
        if self.must_refuse:
            return f"{self.refusal_reason}{missing}"
        if not self.dropped:
            return (
                f"nothing was dropped — {self.used_chars} of {self.budget} characters used, "
                f"and every section fitted.{missing}"
            )
        return (
            f"{len(self.dropped)} section(s) totalling {self.dropped_chars} characters did not "
            f"fit the {self.budget}-character ceiling: "
            + "; ".join(d.render() for d in self.dropped)
            + missing
        )

    def as_dict(self) -> dict:
        return {
            "budget": self.budget,
            "used_chars": self.used_chars,
            "is_complete": self.is_complete,
            "must_refuse": self.must_refuse,
            "refusal_reason": self.refusal_reason,
            "included": [s.key for s in self.included],
            "dropped": [
                {"key": d.key, "tier": d.tier.value, "chars": d.chars, "reason": d.reason}
                for d in self.dropped
            ],
            "absent_payload": [
                {"tier": a.tier.value, "reason": a.reason} for a in self.absent_payload
            ],
        }


def _joined(sections: Sequence[ContextSection]) -> str:
    return SECTION_SEPARATOR.join(s.text for s in sections)


def _body(head: str, sections: Sequence[ContextSection]) -> str:
    """The assembled text, with the missing-payload note ahead of everything it is about."""
    joined = _joined(sections)
    if not head:
        return joined
    return f"{head}{SECTION_SEPARATOR}{joined}" if joined else head


def _payload_first(sections: Sequence[ContextSection]) -> tuple[ContextSection, ...]:
    """The honesty payload in the order `HONESTY_PAYLOAD` fixes, original order within a tier."""
    return tuple(
        sorted(
            (s for s in sections if s.is_honesty_payload),
            key=lambda s: HONESTY_PAYLOAD.index(s.tier),
        )
    )


def _drop_rank(tier: ContextTier) -> int:
    """Where a tier sits in the surrender order — lower goes first.

    A tier in neither table is treated as the **last** droppable thing to give up. That is the
    safe direction for an unclassified piece of context, and it never becomes a quiet default:
    a test asserts every tier is in exactly one of the two tables, so an unclassified one is a
    failing build rather than a section that turns out to be protected by accident.
    """
    return DROP_ORDER.index(tier) if tier in DROP_ORDER else len(DROP_ORDER)


def _keep_order(sections: Sequence[ContextSection]) -> tuple[ContextSection, ...]:
    """Everything droppable, most-worth-keeping first — the reverse of the drop order."""
    return tuple(
        sorted(
            (s for s in sections if not s.is_honesty_payload),
            key=lambda s: -_drop_rank(s.tier),
        )
    )


def _drop_note(dropped: Sequence[DroppedSection], budget: int) -> str:
    """The note the **model** reads, so the answer can say what it was built on.

    Reporting the drop only to the caller would be half the fix: the caller can log it, but the
    sentence a reader sees is written by something that still believes it saw everything.

    **Keys only, and one shared reason.** The per-section reasons go to the caller, where they
    are read once; repeating them here costs about two hundred characters each, which on a
    tight budget makes the note the thing that pushed the evidence out. A note that grows
    faster than what it reports would have to be dropped, and then nothing says anything.
    """
    keys = ", ".join(d.key for d in dropped)
    return (
        f"{CONTEXT_TRUNCATION_MARKER}\n"
        f"{len(dropped)} section(s) did not fit the {budget}-character context ceiling and are "
        f"absent entirely rather than shortened: {keys}. This answer rests on what remains — "
        f"say so if it matters. The gate outcome, the signal provenance notes, the data window "
        f"and the fault label are never dropped, so those are complete above."
    )


def _dropped_for(section: ContextSection, budget: int, exhausted_at: str) -> DroppedSection:
    return DroppedSection(
        key=section.key,
        tier=section.tier,
        chars=section.chars,
        reason=(
            f"{section.tier.value} content, dropped to fit the {budget}-character context "
            f"ceiling. The budget was exhausted at {exhausted_at!r}, and everything with an "
            f"equal or weaker claim to the space went with it. None of it was shortened or "
            f"paraphrased — it is absent"
        ),
    )


def assemble(
    sections: Sequence[ContextSection], *, budget: int | None = None
) -> AssembledContext:
    """Fit the evidence into the ceiling and report what did not fit. Never raises.

    **Stop-on-first-miss, not a best packing.** Candidates are walked most-worth-keeping
    first, and once one does not fit, it and everything with a weaker claim to the space go
    with it — even where a smaller later section would have squeezed in. That is a deliberate
    loss of a few hundred characters in exchange for a result somebody can check: *"residuals 1
    to 4 are here, 5 and 6 are not"* is a sentence a reader can verify against the pack, and
    the output of a knapsack is not.

    **The payload is checked for presence before it is protected.** Ordering it first does
    nothing if it was never handed over, and a context assembled without a gate outcome came
    back complete and silent before that check existed.
    """
    limit = budget if budget is not None else get_settings().max_context_chars
    absent = absent_payload_in([s.tier for s in sections])
    head = absence_note(absent)
    payload = _payload_first(sections)
    payload_text = _body(head, payload)

    if len(payload_text) > limit:
        return AssembledContext(
            text=payload_text,
            budget=limit,
            included=payload,
            dropped=(),
            absent_payload=absent,
            must_refuse=True,
            refusal_reason=(
                f"the honesty payload alone is {len(payload_text)} characters against a "
                f"ceiling of {limit}. It is returned whole and unsent rather than trimmed: the "
                f"gate outcome, the signal notes, the data window and the fault label are the "
                f"four things that must never be dropped, so there is nothing left to give up. "
                f"Ask a narrower question, or raise the ceiling deliberately — "
                f"TBD (Q84) records which of those is correct."
            ),
        )

    kept = list(payload)
    dropped: list[DroppedSection] = []
    exhausted_at = ""
    for section in _keep_order(sections):
        if not exhausted_at and len(_body(head, [*kept, section])) <= limit:
            kept.append(section)
            continue
        exhausted_at = exhausted_at or section.key
        dropped.append(_dropped_for(section, limit, exhausted_at))

    return _with_room_for_the_note(head, kept, dropped, absent, limit)


def _with_room_for_the_note(
    head: str,
    kept: list[ContextSection],
    dropped: list[DroppedSection],
    absent: tuple[AbsentPayload, ...],
    limit: int,
) -> AssembledContext:
    """Make the note that reports the drops fit too, giving up more sections if it must.

    The note is part of the context, so a budget that leaves no room for it would produce the
    silent truncation the note exists to prevent — the failure re-entering through the door
    marked exit. Sections are surrendered from the least-kept end until it fits, and each one
    surrendered is itself reported.
    """
    while dropped:
        note = _drop_note(_in_drop_order(dropped), limit)
        body = _body(head, kept)
        if len(body) + len(SECTION_SEPARATOR) + len(note) <= limit:
            return AssembledContext(
                text=f"{body}{SECTION_SEPARATOR}{note}",
                budget=limit,
                included=tuple(kept),
                dropped=_in_drop_order(dropped),
                absent_payload=absent,
            )

        surrendered = next((s for s in reversed(kept) if not s.is_honesty_payload), None)
        if surrendered is None:
            return AssembledContext(
                text=f"{_body(head, kept)}{SECTION_SEPARATOR}{note}",
                budget=limit,
                included=tuple(kept),
                dropped=_in_drop_order(dropped),
                absent_payload=absent,
                must_refuse=True,
                refusal_reason=(
                    f"the honesty payload fits the {limit}-character ceiling but the note "
                    f"reporting {len(dropped)} dropped section(s) does not fit beside it. "
                    f"Sending the payload without the note would hide the drop, which is the "
                    f"failure this assembler exists to prevent — TBD (Q84)."
                ),
            )
        kept.remove(surrendered)
        dropped.append(
            _dropped_for(surrendered, limit, "the note that reports the dropped sections")
        )

    return AssembledContext(
        text=_body(head, kept),
        budget=limit,
        included=tuple(kept),
        absent_payload=absent,
    )


def _in_drop_order(dropped: Sequence[DroppedSection]) -> tuple[DroppedSection, ...]:
    """Report the drops in the order they were surrendered, not in the order they were walked.

    The selection walks the candidates most-worth-keeping first, so the raw list reads
    evidence-then-history — the reverse of what happened. A reader checking *"what did this
    give up first"* against `DROP_ORDER` would find the two disagreeing, and the table is the
    thing that is supposed to be inspectable.
    """
    return tuple(sorted(dropped, key=lambda d: _drop_rank(d.tier)))


def fit_question(question: str, *, limit: int | None = None) -> tuple[str, str]:
    """`max_input_chars`, applied where the text arrives. Returns the text and the reason.

    A pasted wall of text is what the ceiling stops, and clipping it is fine — clipping it
    without saying so is not, because the model then answers a question it only half received
    and the answer reads as though it addressed the whole thing.

    At a ceiling shorter than the marker itself the marker is all that comes back, deliberately:
    a clipped question carrying no marker is the one output this function must never produce.
    """
    cap = limit if limit is not None else get_settings().max_input_chars
    if len(question) <= cap:
        return question, f"the question fitted the {cap}-character input ceiling whole"

    room = max(cap - len(CONTEXT_TRUNCATION_MARKER), 0)
    kept = question[:room]
    lost = len(question) - room
    return f"{kept}{CONTEXT_TRUNCATION_MARKER}", (
        f"the question was {len(question)} characters against an input ceiling of {cap}; the "
        f"last {lost} were not sent, and the text carries a marker saying so"
    )


# ── from the pack the model actually receives ──────────────────────────────────

#: Everything in `to_prompt_data()` that is real but surrenderable, in the order it is given
#: up. `sources` last because a lineage line is the least useful thing to a reader who has
#: already lost the residual it describes.
_SUPPORTING_KEYS: tuple[str, ...] = (
    "other_labels_same_day",
    "severity",
    "slots_in_episode",
    "sources",
)

#: Stated rather than omitted. A pack with no window is itself a defect — constraint 15 — and
#: the model is never left to supply "now" from its own head.
_NO_WINDOW = (
    "not stated by the evidence pack, which is itself a defect: every artefact states its "
    "data window, and this answer covers an unstated span"
)


def sections_from_prompt_data(prompt_data: dict) -> tuple[ContextSection, ...]:
    """Tier what `EvidencePack.to_prompt_data()` produces. Nothing is reformatted.

    Every value arrives as a display string because the pack carries display strings rather
    than floats, and this module keeps that true: it labels and orders, and never renders a
    number. Re-rendering would reintroduce a tolerance, and every tolerance forgives some
    fabrication.

    **`model_fit_warning` is tiered as a signal note rather than as evidence.** Chiller 1's
    current model runs at nRMSE 48.03 against chiller 2's 2.65, so a residual quoted without
    its fit warning is the *suspect* case the never-dropped rule names — the same defect as a
    never-measured signal reading as a measurement, arriving by a different door.
    """
    out: list[ContextSection] = []

    for i, line in enumerate(prompt_data.get("gates") or (), 1):
        out.append(ContextSection(f"gate.{i}", ContextTier.GATE_OUTCOME, f"gate — {line}"))
    may_diagnose = prompt_data.get("may_diagnose") or "not stated"
    out.append(
        ContextSection(
            "may_diagnose",
            ContextTier.GATE_OUTCOME,
            f"may a fault be named from this evidence: {may_diagnose}",
        )
    )

    for i, line in enumerate(prompt_data.get("signal_provenance") or (), 1):
        out.append(ContextSection(f"signal.{i}", ContextTier.SIGNAL_NOTE, f"signal — {line}"))
    if prompt_data.get("model_fit_warning"):
        out.append(
            ContextSection(
                "model_fit_warning", ContextTier.SIGNAL_NOTE, prompt_data["model_fit_warning"]
            )
        )

    out.append(
        ContextSection(
            "data_window",
            ContextTier.DATA_WINDOW,
            f"data window — {prompt_data.get('data_window') or _NO_WINDOW}",
        )
    )
    out.append(
        ContextSection(
            "fault_label",
            ContextTier.FAULT_LABEL,
            f"fault label — {prompt_data.get('fault_label', 'no label on this slot')}; the "
            f"trained model declares it undecidable: "
            f"{prompt_data.get('model_declares_undecidable', 'not stated')}",
        )
    )

    out.append(
        ContextSection(
            "equipment",
            ContextTier.EVIDENCE,
            f"equipment — {prompt_data.get('equipment', 'not stated')} on "
            f"{prompt_data.get('day', 'a day the pack did not state')}",
        )
    )
    for i, line in enumerate(prompt_data.get("residuals") or (), 1):
        out.append(ContextSection(f"residual.{i}", ContextTier.EVIDENCE, f"residual — {line}"))

    for key in _SUPPORTING_KEYS:
        value = prompt_data.get(key)
        if not value:
            continue
        rendered = "; ".join(str(v) for v in value) if isinstance(value, list) else str(value)
        out.append(ContextSection(key, ContextTier.SUPPORTING, f"{key} — {rendered}"))

    return tuple(out)


# ── fitting the pack the prompt actually carries ───────────────────────────────

#: The keys the prompt payload is measured and trimmed by, **in the order they are given up**.
#:
#: Two tables would drift, so this one is checked against `DROP_ORDER` by a test rather than
#: maintained beside it: history first, then the four supporting keys `sections_from_prompt_data`
#: already classes as supporting, then the residuals — trimmed one at a time from the end,
#: because *"residuals 1 to 4 are here, 5 and 6 are not"* is a sentence a reader can verify
#: against the pack.
SURRENDER_ORDER: tuple[tuple[str, ContextTier], ...] = (
    ("task_trail", ContextTier.HISTORY),
    *((key, ContextTier.SUPPORTING) for key in _SUPPORTING_KEYS),
    ("residuals", ContextTier.EVIDENCE),
)

#: Keys that are never given up, and what each one costs a reader. The first four rows are the
#: honesty payload; the last two are here because dropping them breaks a gate rather than
#: losing a detail — an answer that cannot name its machine fails `equipment_exists`, and one
#: whose day is gone leaves `window_is_stated` unable to be checked at all.
PROTECTED_KEYS: dict[str, str] = {
    "gates": "the gate outcome",
    "may_diagnose": "the gate outcome",
    "signal_provenance": "the never-measured and suspect signal notes",
    "model_fit_warning": "the poor-fit note, which is a suspect-signal note by another door",
    "data_window": "the data window",
    "day": "the day the window is checked against",
    "fault_label": "the fault label the rules produced",
    "model_declares_undecidable": "whether the trained model called this class undecidable",
    "equipment": "the machine the answer is about",
}

#: Where the note about what was dropped is written into the payload the model reads. A key
#: rather than a prose suffix, because the payload is fenced JSON and prose appended after the
#: closing brace is outside the block the system prompt calls DATA.
DROP_NOTE_KEY = "context_dropped"

#: Where the note about what never arrived is written. Separate from the key above, because a
#: drop and an absence need different fixes — a ceiling too small, and a pack assembled wrong.
ABSENCE_NOTE_KEY = "context_absent"


def render_prompt_data(prompt_data: dict) -> str:
    """The payload exactly as `build_messages` has always written it.

    Held here rather than in the prompt builder so the thing that measures the payload and the
    thing that emits it cannot disagree by a keyword argument. A gate that measures 3,283
    characters and sends 3,410 is a ceiling that does not hold.
    """
    return json.dumps(prompt_data, indent=2, ensure_ascii=False)


@dataclass(frozen=True)
class FittedEvidence:
    """A prompt payload cut to the ceiling, and everything given up or missing on the way.

    **`is_unchanged` is the load-bearing property.** A transcript is keyed on the exact bytes
    the model received, so a budgeter that reformatted a payload which already fitted would
    invalidate every recording on disk — eight of them, captured on the Jarvis box on
    2026-08-17 — and the offline replay that lets the rest of this repository run with the box
    terminated would go with them. Under budget, this returns the caller's own dict and the
    same string `json.dumps` has always produced.
    """

    prompt_data: dict
    rendered: str
    budget: int
    dropped: tuple[DroppedSection, ...] = field(default_factory=tuple)
    absent_payload: tuple[AbsentPayload, ...] = field(default_factory=tuple)
    must_refuse: bool = False
    refusal_reason: str = ""

    @property
    def used_chars(self) -> int:
        return len(self.rendered)

    @property
    def is_unchanged(self) -> bool:
        """Nothing was dropped and nothing was noted, so the payload is byte-for-byte what an
        unbudgeted build would have produced."""
        return not self.dropped and not self.absent_payload

    @property
    def is_complete(self) -> bool:
        return self.is_unchanged and not self.must_refuse

    def render_drop_report(self) -> str:
        """What the route trace and the caller read. An absence of drops is stated, not blank."""
        missing = " " + absence_note(self.absent_payload) if self.absent_payload else ""
        if self.must_refuse:
            return f"{self.refusal_reason}{missing}"
        if not self.dropped:
            return (
                f"nothing was dropped — the evidence payload is {self.used_chars} of "
                f"{self.budget} characters.{missing}"
            )
        return (
            f"{len(self.dropped)} entr(ies) totalling {sum(d.chars for d in self.dropped)} "
            f"characters did not fit the {self.budget}-character ceiling: "
            + "; ".join(d.render() for d in self.dropped)
            + missing
        )

    def as_dict(self) -> dict:
        return {
            "budget": self.budget,
            "used_chars": self.used_chars,
            "is_unchanged": self.is_unchanged,
            "must_refuse": self.must_refuse,
            "refusal_reason": self.refusal_reason,
            "dropped": [
                {"key": d.key, "tier": d.tier.value, "chars": d.chars, "reason": d.reason}
                for d in self.dropped
            ],
            "absent_payload": [
                {"tier": a.tier.value, "reason": a.reason} for a in self.absent_payload
            ],
        }


def _payload_tiers_present(prompt_data: dict) -> tuple[ContextTier, ...]:
    """Which of the four never-dropped tiers this payload actually carries.

    Read off the same keys `sections_from_prompt_data` reads, so the presence check and the
    tiering cannot disagree about what a gate outcome is. An empty list is an absence: a pack
    carrying `"signal_provenance": []` told the model nothing about provenance, and treating
    that as *present* is the reassuring branch.
    """
    present: list[ContextTier] = []
    if prompt_data.get("gates") or prompt_data.get("may_diagnose"):
        present.append(ContextTier.GATE_OUTCOME)
    if prompt_data.get("signal_provenance") or prompt_data.get("model_fit_warning"):
        present.append(ContextTier.SIGNAL_NOTE)
    if prompt_data.get("data_window"):
        present.append(ContextTier.DATA_WINDOW)
    if prompt_data.get("fault_label"):
        present.append(ContextTier.FAULT_LABEL)
    return tuple(present)


def _entry_chars(prompt_data: dict, key: str) -> int:
    """How much room one entry costs, measured on the rendered payload rather than guessed."""
    without = {k: v for k, v in prompt_data.items() if k != key}
    return len(render_prompt_data(prompt_data)) - len(render_prompt_data(without))


def _dropped_entry(
    key: str, tier: ContextTier, chars: int, budget: int, detail: str
) -> DroppedSection:
    return DroppedSection(
        key=key,
        tier=tier,
        chars=chars,
        reason=(
            f"{tier.value} content, dropped to fit the {budget}-character evidence ceiling. "
            f"{detail} None of it was shortened or paraphrased — it is absent from the payload "
            f"the model read"
        ),
    )


def fit_prompt_data(prompt_data: dict, *, budget: int | None = None) -> FittedEvidence:
    """Cut the prompt payload to `budget` characters, cheapest claim on the space first.

    **A no-op when it already fits, and that is a requirement rather than an optimisation.**
    The seven `diagnose` payloads recorded on the box measure 3,080 to 3,300 characters against
    a 24,000 ceiling, so nothing is dropped today and the payload returned is the caller's own
    dict rendered exactly as before. A budgeter that normalised a payload which already fitted
    would rekey every transcript on disk.

    **Whole entries, never a slice of one.** Residuals are surrendered one at a time from the
    end and everything else goes entire, because half a rendered display string is a figure
    with no band behind it — and a truncated number is the one thing this repository will not
    print. The honesty payload, the machine and the day are in `PROTECTED_KEYS` and are never
    candidates: when they alone do not fit, this refuses and says so rather than trimming them.
    """
    limit = budget if budget is not None else get_settings().max_context_chars
    absent = absent_payload_in(_payload_tiers_present(prompt_data))

    working = dict(prompt_data)
    if absent:
        working[ABSENCE_NOTE_KEY] = absence_note(absent)

    # Kept before the surrender loop touches anything, because the refusal path below returns
    # it. `_surrender` rebinds `working[key]` rather than mutating the caller's lists, so a
    # shallow copy is genuinely the payload as it arrived.
    whole = dict(working)

    if len(render_prompt_data(working)) <= limit:
        return FittedEvidence(
            prompt_data=working,
            rendered=render_prompt_data(working),
            budget=limit,
            absent_payload=absent,
        )

    def overflows() -> bool:
        return len(render_prompt_data(_with_note(working, dropped, limit))) > limit

    dropped: list[DroppedSection] = []
    for key, tier in SURRENDER_ORDER:
        if key in PROTECTED_KEYS or not working.get(key):
            continue
        while working.get(key) and overflows():
            dropped.append(_surrender(working, key, tier, limit))
        if not overflows():
            break

    rendered_final = _with_note(working, dropped, limit)
    text = render_prompt_data(rendered_final)
    if len(text) <= limit:
        return FittedEvidence(
            prompt_data=rendered_final,
            rendered=text,
            budget=limit,
            dropped=tuple(dropped),
            absent_payload=absent,
        )

    # Nothing here is sendable, so the payload returned is the one that arrived — not the
    # stripped remainder. Two reasons, and the first is that this promised it:
    #
    # 1. Returning the remainder would make the refusal *also* a truncation. A caller that
    #    logged `rendered`, or raised the ceiling and sent it, would be handling a pack with
    #    entries missing and nothing on the object saying which — the exact failure the
    #    surrender note exists to prevent, arriving by the one path that skips the note.
    # 2. `dropped` still carries the attempted surrender, in order, because that is the
    #    arithmetic behind the refusal: *these went, and it still did not fit.* So the record
    #    of the attempt survives without the payload wearing its result.
    #
    # Caught on 2026-08-18 by a test asserting the sentence below against the object.
    return FittedEvidence(
        prompt_data=whole,
        rendered=render_prompt_data(whole),
        budget=limit,
        dropped=tuple(dropped),
        absent_payload=absent,
        must_refuse=True,
        refusal_reason=(
            f"what is left after surrendering every droppable entry is {len(text)} characters "
            f"against a ceiling of {limit}, and everything remaining is protected: "
            f"{', '.join(sorted(set(PROTECTED_KEYS.values())))}. The payload is returned whole "
            f"and marked unsendable rather than trimmed — TBD (Q84) records whether such a turn "
            f"should refuse or raise the ceiling deliberately."
        ),
    )


def _surrender(working: dict, key: str, tier: ContextTier, limit: int) -> DroppedSection:
    """Give up one entry — or one residual — and return the record of it, in words."""
    value = working[key]
    if isinstance(value, list) and len(value) > 1:
        chars = len(str(value[-1]))
        working[key] = value[:-1]
        return _dropped_entry(
            f"{key}[{len(value)}]",
            tier,
            chars,
            limit,
            f"It was the last of {len(value)} and went first, so what remains is the opening "
            f"run rather than an arbitrary subset.",
        )
    chars = _entry_chars(working, key)
    working.pop(key)
    return _dropped_entry(
        key, tier, chars, limit, "The whole entry went; nothing of it was kept."
    )


def _with_note(working: dict, dropped: Sequence[DroppedSection], limit: int) -> dict:
    """The payload with the drop note in it, because the note is part of what must fit.

    Otherwise the failure re-enters through the door marked exit: a payload that overflows by
    exactly the length of the note explaining that it did not overflow.
    """
    if not dropped:
        return working
    return {**working, DROP_NOTE_KEY: _drop_note(_in_drop_order(dropped), limit)}
