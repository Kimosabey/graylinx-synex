"""`C24` inline evidence — the figure beside the claim it supports, and the claim that has
nothing beside it at all.

**The failure this prevents.** An answer is prose with numbers in it, and the evidence sits in
a separate block underneath. A reader checking the answer has to carry a figure across the gap
in their head, and nobody does that for every sentence. So a claim whose figure came from
nowhere reads exactly like one whose figure came from `gla_model_residuals_wc` — same
typeface, same confidence, same sentence shape. That is the whole of `C24`: the second half of
this module is not a nicety attached to the rendering, it *is* the feature.

**Measured, so the gap is not hypothetical.** On the pack this plant produces, five of the six
residual figures are a *stated absence* rather than a value — `compressor_power_residual` has
no fitted model at all and most columns are NULL — so an answer with six confident numbers in
it has at most one it can pair. And the numbers themselves are unforgiving: chiller 1's
current residual renders as `−25.645`, of which `-25.6` is a substring. Substring containment
would call the truncation supported; `postcheck.audit_numbers` shipped with exactly that bug
and the test written to catch it passed against the broken version. This module therefore
tokenises both sides and compares by **exact value**, never by containment and never with a
tolerance — every tolerance forgives some fabrication.

**Three outcomes per claim, and collapsing any two of them is the dishonesty.**

| Outcome | Means | Why it is its own state |
|---|---|---|
| `PAIRED` | every figure in the claim is in a named evidence line | checkable in place |
| `UNSUPPORTED` | the claim carries a figure no evidence line holds | **the feature** — the
  sentence that looks authoritative and is not |
| `NO_FIGURE` | the claim states no figure at all | it is prose. Not thereby supported, and
  not thereby wrong |

`NO_FIGURE` is the same discipline as inherited constraint 8 — `cannot_check` is separate from
`not applicable`, because six "N/A" presses once opened a blocking gate with zero evidence
behind it. Counting an unpairable sentence as supported would open the same gate here.

**What this module honestly cannot do, stated rather than hidden.** Pairing is over *figures*.
A sentence such as *"the root cause is a fouled condenser"* carries no number, so it lands in
`NO_FIGURE` and this module says nothing about it. The audit that catches that sentence is
`postcheck.audit_no_diagnosis_by_model`, which enforces the separation law on the output — the
language model never names a fault. Two mechanisms, deliberately separate, and neither
pretends to be the other.

**Nothing here calls a model** — contract 2 in `importlinter.ini` makes that a build failure
rather than a sentence, and the pairing is a rules module in the sense the register means.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.analytics.honesty import DataWindow
from app.services.evidence import EvidencePack

# ── the tokeniser ───────────────────────────────────────────────────────────────
# Deliberately a copy of the one in `app.agents.postcheck`, and the duplication is forced
# rather than careless: contract 2 forbids `app.services` importing `app.agents`, and moving
# the tokeniser down to `analytics` would give the repository a third home for the same three
# lines. `test_inline_evidence.py` asserts the two agree token for token, so a drift is a
# failing test rather than a slow divergence between what the audit rejects and what the
# rendering pairs.

#: A number in prose: 141, -25.645, 1,099.6, 48.03.
_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")

#: Every character that means "minus" in text a person or a model might write. The evidence
#: uses U+2212 MINUS SIGN because it is typeset prose; a model replies with an ASCII hyphen.
#: Reading `−273.2` as *positive* 273.2 once made the same figure look like two different
#: numbers and produced a false accusation of fabrication — which suppresses correct answers
#: silently, and nobody ever looks at what was withheld.
_MINUS_SIGNS = str.maketrans({"−": "-", "–": "-", "—": "-", "‒": "-"})

#: Integers at or below this are counts a turn may legitimately derive — "all five residuals",
#: "two of twelve" — rather than figures it must have read from the evidence. **Inherited from
#: `postcheck._ALLOWED_BARE`, not chosen here**: the pairing and the numeric audit must agree
#: on what counts as a figure, or a number the audit polices would render as unpairable prose.
SMALL_COUNT_CEILING: int = 12

#: The ceiling expanded into the exact token set, because `int(token) <= 12` and
#: `token in {"0", ..., "12"}` disagree on `"007"` — and the drift test compares this
#: tokeniser against the audit's token for token, so "nearly the same rule" is a failure.
_SMALL_COUNTS: frozenset[str] = frozenset(str(n) for n in range(0, SMALL_COUNT_CEILING + 1))

_YEAR_RE = re.compile(r"(19|20)\d{2}")

#: Sentence and line boundaries. Line breaks count because the deterministic answer is built
#: as lines and a bulleted residual is one claim, not a fragment of the sentence above it.
_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def figures_in(text: str) -> tuple[str, ...]:
    """Every token in `text` that is a figure rather than a count or a year.

    Public so the drift test can compare it against the audit's tokeniser. Returns the tokens
    as written, not as floats, because the pairing reports what the claim actually said.
    """
    out: list[str] = []
    for match in _NUMBER_RE.finditer(text.translate(_MINUS_SIGNS)):
        token = match.group(0).rstrip(".").replace(",", "")
        if not token or token == "-":
            continue
        if token in _SMALL_COUNTS:
            continue
        if _YEAR_RE.fullmatch(token):
            continue
        out.append(token)
    return tuple(out)


def _as_value(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


# ── what a claim may be paired against ──────────────────────────────────────────

class EvidenceKind(StrEnum):
    """Which part of the pack a line came from.

    Named rather than anonymous so an inline pairing can say *which* evidence stands beside a
    claim. "This figure is in the evidence somewhere" is not a checkable statement.
    """

    RESIDUAL = "residual"
    GATE = "gate"
    SIGNAL = "signal"
    SOURCE = "source"
    WINDOW = "window"
    EPISODE = "episode"


@dataclass(frozen=True)
class EvidenceLine:
    """One line of the pack, and the figures it carries.

    `text` is the string the pack itself rendered, never re-rendered here. The pack carries
    display strings rather than floats precisely so exact comparison is possible, and
    reformatting on the way past would reintroduce the tolerance that discipline exists to
    remove.
    """

    kind: EvidenceKind
    label: str
    text: str

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(
            v for v in (_as_value(t) for t in figures_in(self.text)) if v is not None
        )

    def carries(self, value: float) -> bool:
        return value in self.values

    def render(self) -> str:
        return f"[{self.kind.value}: {self.label}] {self.text}"


def evidence_lines(pack: EvidencePack) -> tuple[EvidenceLine, ...]:
    """Every line of the pack a claim may be paired against, in the pack's own order.

    Drawn from the same material `to_prompt_data()` hands the model, so the pairing is over
    exactly what the answer was written from — an evidence line the model never saw could
    "support" a figure it in fact invented, which would make this module a way of laundering
    a fabrication rather than catching one.
    """
    lines: list[EvidenceLine] = [
        EvidenceLine(
            kind=EvidenceKind.EPISODE,
            label="episode",
            text=(
                f"{pack.equipment_display} on {pack.day.isoformat()}: {pack.slot_count} "
                f"slot(s), label {pack.fault_label or 'none on this slot'}, severity "
                f"{pack.severity_text}"
            ),
        ),
        EvidenceLine(
            kind=EvidenceKind.WINDOW,
            label="data window",
            text=pack.window.render(),
        ),
    ]
    lines += [
        EvidenceLine(EvidenceKind.RESIDUAL, e.residual_name, e.render())
        for e in pack.residual_evidence
    ]
    lines += [
        EvidenceLine(
            kind=EvidenceKind.GATE,
            label=g.gate.value,
            text=(
                f"{g.gate.value}: {'passed' if g.passed else 'FAILED'}"
                + (f" — {g.reason}" if g.reason else "")
                + (f" To change this: {g.remedy}" if g.remedy else "")
            ),
        )
        for g in pack.gates.results
    ]
    lines += [EvidenceLine(EvidenceKind.SIGNAL, s.key, s.render()) for s in pack.signal_notes]
    lines += [EvidenceLine(EvidenceKind.SOURCE, s.table, s.render()) for s in pack.sources]
    return tuple(lines)


# ── the three outcomes ──────────────────────────────────────────────────────────

class ClaimSupport(StrEnum):
    """How a claim stands against the evidence. Three states, never two."""

    PAIRED = "paired"
    """Every figure in the claim appears, by exact value, in a named evidence line."""

    UNSUPPORTED = "unsupported"
    """A figure in the claim appears in no evidence line. **This is what `C24` exists for.**"""

    NO_FIGURE = "no_figure"
    """The claim states no figure, so there is nothing to pair.

    Not supported, not unsupported, and reported as its own count. Collapsing it into
    `PAIRED` would be constraint 8's failure in a new place: a claim nobody could check
    counted as a claim somebody had."""


#: The reason each outcome carries, in words. Held as a table rather than built in a branch so
#: that every outcome has a sentence and adding a fourth cannot silently ship without one.
SUPPORT_TEXT: dict[ClaimSupport, str] = {
    ClaimSupport.PAIRED: "every figure in this claim appears in the evidence line beside it",
    ClaimSupport.UNSUPPORTED: (
        "this claim states a figure that appears nowhere in the evidence pack — rendered "
        "inline it would look exactly as authoritative as a supported one"
    ),
    ClaimSupport.NO_FIGURE: (
        "this claim states no figure, so nothing here can pair it; whether it asserts more "
        "than the evidence supports is a separation-law question, not a pairing one"
    ),
}


@dataclass(frozen=True)
class PairedClaim:
    """One sentence of an answer, and what stands beside it."""

    index: int
    text: str
    support: ClaimSupport
    figures: tuple[str, ...] = ()
    supporting: tuple[EvidenceLine, ...] = ()
    unmatched: tuple[str, ...] = ()
    ambiguous: tuple[str, ...] = ()
    """Figures that matched more than one evidence line by value alone.

    Reported rather than resolved. `412` is a row count in one line and a reading count in
    another, and silently picking the first would attach a plausible-looking line to the wrong
    figure — the same failure `_RESIDUAL_TO_MODEL` in `evidence.py` refuses to make by
    guessing a join between two vocabularies."""

    @property
    def reason(self) -> str:
        return SUPPORT_TEXT[self.support]

    def render(self) -> str:
        """The inline form: the claim, then the evidence that stands beside it.

        An unsupported claim is marked in **words**. It is never dropped, never greyed and
        never left to stand on its own — constraint 38's rule, that a thing the reader cannot
        act on collapses with a reason rather than fading out, applies to a sentence as much
        as to a checklist item.
        """
        out = [self.text]
        for line in self.supporting:
            out.append(f"    ↳ {line.render()}")
        if self.support is ClaimSupport.UNSUPPORTED:
            out.append(
                f"    ↳ NO SUPPORTING EVIDENCE for {', '.join(self.unmatched)} — "
                f"{self.reason}"
            )
        if self.support is ClaimSupport.NO_FIGURE:
            out.append(f"    ↳ no figure to pair — {self.reason}")
        for token in self.ambiguous:
            out.append(
                f"    ↳ {token} matches more than one evidence line by value; which one it "
                f"refers to is not resolved here"
            )
        return "\n".join(out)

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "support": self.support.value,
            "reason": self.reason,
            "figures": list(self.figures),
            "supporting": [
                {"kind": line.kind.value, "label": line.label, "text": line.text}
                for line in self.supporting
            ],
            "unmatched": list(self.unmatched),
            "ambiguous": list(self.ambiguous),
        }


@dataclass(frozen=True)
class InlineRendering:
    """An answer, claim by claim, with the evidence pinned to each one.

    Carries the window because it is an artefact in its own right and constraint 15 says every
    artefact states one. Anomaly counts were once shown under a heading describing a telemetry
    window that did not overlap them at all.
    """

    claims: tuple[PairedClaim, ...]
    window: DataWindow
    lines_available: int

    @property
    def paired(self) -> tuple[PairedClaim, ...]:
        return tuple(c for c in self.claims if c.support is ClaimSupport.PAIRED)

    @property
    def unsupported(self) -> tuple[PairedClaim, ...]:
        """The claims `C24` exists to surface. Never empty by construction."""
        return tuple(c for c in self.claims if c.support is ClaimSupport.UNSUPPORTED)

    @property
    def unpairable(self) -> tuple[PairedClaim, ...]:
        return tuple(c for c in self.claims if c.support is ClaimSupport.NO_FIGURE)

    @property
    def every_figure_is_supported(self) -> bool:
        return not self.unsupported

    def support_statement(self) -> str:
        """The headline, in words, and it never reports a clean pairing as a clean answer.

        Three counts rather than one ratio. "8 of 10 supported" hides whether the other two
        were fabrications or ordinary prose, and those are not the same problem.
        """
        if not self.claims:
            return (
                "this answer contains no claims to pair — it is empty, which is not the same "
                "as an answer whose every claim was supported"
            )
        parts = [
            f"{len(self.paired)} claim(s) paired to an evidence line",
            f"{len(self.unsupported)} claim(s) state a figure the evidence does not contain",
            f"{len(self.unpairable)} claim(s) state no figure and cannot be paired at all",
        ]
        return "; ".join(parts) + f" — {len(self.claims)} claim(s) in total"

    def render(self) -> str:
        """The whole answer in inline form, in the order it was written."""
        header = [
            f"Evidence rendered inline. Data window: {self.window.render()}.",
            f"{self.lines_available} evidence line(s) were available to pair against.",
            self.support_statement() + ".",
            "",
        ]
        return "\n".join(header + [c.render() for c in self.claims])

    def as_dict(self) -> dict:
        return {
            "window": self.window.as_dict(),
            "lines_available": self.lines_available,
            "support_statement": self.support_statement(),
            "every_figure_is_supported": self.every_figure_is_supported,
            "counts": {
                "paired": len(self.paired),
                "unsupported": len(self.unsupported),
                "no_figure": len(self.unpairable),
                "total": len(self.claims),
            },
            "claims": [c.as_dict() for c in self.claims],
        }


# ── the pairing ─────────────────────────────────────────────────────────────────

def split_claims(answer: str) -> tuple[str, ...]:
    """The answer as claims, in order, with the blanks dropped and nothing else.

    A claim is a sentence or a line. Nothing is merged and nothing is reordered: the reader
    checks the answer as it was written, and a pairing over a rewritten answer would be
    checking a text nobody was shown.
    """
    return tuple(part.strip() for part in _CLAIM_SPLIT.split(answer) if part.strip())


def pair_claims(answer: str, pack: EvidencePack) -> InlineRendering:
    """`C24`. Pair every claim with its evidence, and name every claim that has none.

    The unsupported set is the return value that matters. A rendering that only decorated the
    supported claims would leave the fabricated one looking untouched-and-therefore-fine,
    which is precisely how an inline layout makes an answer *more* convincing than a separate
    evidence block rather than less.
    """
    lines = evidence_lines(pack)
    # Tokenised once. `EvidenceLine.values` re-reads its own text on every call, which is fine
    # for a caller checking one figure and wasteful across a whole answer.
    indexed = [(line, line.values) for line in lines]
    claims: list[PairedClaim] = []

    for index, text in enumerate(split_claims(answer)):
        figures = figures_in(text)
        if not figures:
            claims.append(
                PairedClaim(index=index, text=text, support=ClaimSupport.NO_FIGURE)
            )
            continue

        supporting: list[EvidenceLine] = []
        unmatched: list[str] = []
        ambiguous: list[str] = []

        for token in figures:
            value = _as_value(token)
            matches = (
                [] if value is None else [line for line, vals in indexed if value in vals]
            )
            if not matches:
                unmatched.append(token)
                continue
            if len(matches) > 1:
                ambiguous.append(token)
            for line in matches:
                if line not in supporting:
                    supporting.append(line)

        claims.append(
            PairedClaim(
                index=index,
                text=text,
                support=ClaimSupport.UNSUPPORTED if unmatched else ClaimSupport.PAIRED,
                figures=figures,
                supporting=tuple(supporting),
                unmatched=tuple(unmatched),
                ambiguous=tuple(ambiguous),
            )
        )

    return InlineRendering(
        claims=tuple(claims), window=pack.window, lines_available=len(lines)
    )


def unsupported_claims(answer: str, pack: EvidencePack) -> tuple[str, ...]:
    """Just the sentences with nothing behind them, for a caller that wants the short form.

    Kept as its own function because that is what a thread export and a work-order draft both
    need: not the rendering, the list of sentences a reader should not trust.
    """
    return tuple(c.text for c in pair_claims(answer, pack).unsupported)
