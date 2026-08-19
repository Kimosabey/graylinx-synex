"""Which episode a question is about, read from the words rather than from a selection.

**The last thing keeping the Copilot bound to a picker.** A question that needs one episode's
evidence — *"raise a work order"*, *"what should I check?"*, *"did the repair work?"* — had no
way to name one, so the interface had to carry a selection and the starter chips had to carry a
fixed episode. Both are the same workaround for the same gap: the product could not understand
*"raise a work order for chiller 1 on 9 April"*.

**It resolves against episodes that exist, never against a parse.** A date and a machine are
extracted from the message and then matched to the detected episodes; nothing is constructed. So
a question naming a day with no detected fault gets told that, rather than an empty evidence
pack that reads as a clean machine.

**Ambiguity is reported, never guessed.** One machine on one day can carry several fault
classes — chiller 1 on 18 April carries four — and picking the first would answer about a fault
nobody named. When more than one matches, this returns them all and the caller asks which,
because a confident answer to the wrong one of four is worse than a question.

**Dates only, and only in forms that cannot be mistaken for something else.** No relative dates:
*"yesterday"* and *"last week"* have no meaning against a snapshot that ends on a fixed date, and
resolving them against the wall clock would match nothing while looking like it worked — the
same failure the SQL guard refuses `NOW()` for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

#: Month names as somebody actually writes them. Long and short, because "9 April" and
#: "9 Apr" are the same request.
_MONTHS: dict[str, int] = {
    m: i
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for m in names
}

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE
)
_MONTH_DAY = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", re.IGNORECASE
)

#: Relative expressions, refused rather than resolved. On a snapshot they mean nothing, and
#: answering them against the wall clock returns an empty result that reads as good news.
_RELATIVE = (
    "yesterday", "today", "tonight", "last week", "this week", "last month", "this month",
    "recently", "right now", "currently", "latest", "most recent",
)


@dataclass(frozen=True)
class EpisodeRef:
    """What the question named, and what it matched.

    `matches` holds every detected episode consistent with the words. Zero means the day
    carries no detected fault — a fact about the plant. More than one means the question was
    ambiguous, which is a fact about the question.
    """

    equipment_key: str | None = None
    day: date | None = None
    matches: tuple[dict, ...] = field(default_factory=tuple)
    relative_term: str = ""

    @property
    def is_resolved(self) -> bool:
        return len(self.matches) == 1

    @property
    def is_ambiguous(self) -> bool:
        return len(self.matches) > 1

    def render_ambiguity(self) -> str:
        """Name every candidate. A reader picking from four is a reader who can pick."""
        labels = ", ".join(sorted({str(m.get("fault_label")) for m in self.matches}))
        return (
            f"{self.equipment_key} carries {len(self.matches)} detected faults on "
            f"{self.day}: {labels}. Say which one and the evidence behind it follows."
        )


#: Questions that cannot be answered without picking **one** episode: a work order is raised
#: from one episode's evidence, a check-list is the check-list for one fault, and "did it work"
#: compares before and after for one repair. Everything else — *"what happened on chiller 1 on
#: 18 April?"* — is answered better by naming all of them than by asking which.
_NEEDS_ONE = (
    "work order", "work-order", "raise a job", "raise a ticket",
    "what should i check", "what do i check", "checklist", "check list",
    "did the repair", "did it work", "did the fix", "was it fixed",
    "isolate", "permit", "lock out", "lockout",
    # **Handing work over is an episode-level act, and leaving it off here broke the whole
    # path.** "I haven't got the gauge for chiller 1 on 9 April" routed to `resolve` correctly
    # and then died before reaching it: chiller 1 carries two faults that day, so resolution
    # was ambiguous, and because escalating was not listed as needing one episode the
    # ambiguity went unreported and the pack stayed empty. The reader got "open a case first" —
    # the exact refusal the handoff was built to replace.
    "escalate", "hand this over", "hand it over", "pass this on", "pass it on",
    "i can't do this", "i cannot do this", "out of my depth",
    "not allowed", "no authority", "not authorised", "the authority",
    "haven't got the", "don't have the", "no gauge", "no meter", "no tool",
    "need a technician", "need a supervisor", "second opinion",
)


def needs_one_episode(message: str) -> bool:
    """Whether this question is unanswerable until one episode is picked.

    **Ambiguity is only worth reporting when it blocks an answer.** A broad question about a
    machine on a day is answered by naming every fault detected; asking which one back would
    withhold an answer the platform already has.
    """
    text = message.lower()
    return any(term in text for term in _NEEDS_ONE)


def day_in(message: str) -> tuple[date | None, str]:
    """The date this message names, and any relative term it used instead.

    Returns `(None, term)` when the message reaches for a relative date — those are refused
    rather than resolved, and the term is returned so the refusal can quote it back.
    """
    text = message.lower()

    for term in _RELATIVE:
        if term in text:
            return None, term

    m = _ISO.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), ""
        except ValueError:
            return None, ""

    for pattern, day_first in ((_DAY_MONTH, True), (_MONTH_DAY, False)):
        m = pattern.search(text)
        if not m:
            continue
        raw_day = m.group(1) if day_first else m.group(2)
        raw_month = m.group(2) if day_first else m.group(1)
        month = _MONTHS.get(raw_month.lower())
        if not month:
            continue
        # The year is not guessed from the wall clock. The measured window spans one year on
        # this snapshot, so it is taken from the episodes the caller matches against.
        return date(1900, month, int(raw_day)), ""

    return None, ""


def resolve(
    message: str, *, equipment_key: str | None, episodes: list[dict]
) -> EpisodeRef:
    """Match a question against episodes that actually exist.

    `episodes` are the detected ones as the API lists them, so every match is a real episode
    with real evidence behind it. Nothing here constructs an episode id.
    """
    day, relative = day_in(message)
    if relative:
        return EpisodeRef(equipment_key=equipment_key, relative_term=relative)
    if day is None:
        return EpisodeRef(equipment_key=equipment_key)

    def same_day(value: str) -> bool:
        try:
            got = date.fromisoformat(value)
        except (TypeError, ValueError):
            return False
        # Year 1900 is the sentinel for "no year was written". The snapshot spans one year, so
        # a day and month identify a day uniquely; if that stops being true this must ask.
        return (
            (got.month, got.day) == (day.month, day.day)
            if day.year == 1900
            else got == day
        )

    matches = tuple(
        e
        for e in episodes
        if same_day(str(e.get("day")))
        and (equipment_key is None or e.get("equipment_key") == equipment_key)
    )

    # **A fault named in the question is the disambiguator.** Chiller 1 on 15 April carries five
    # detected faults, and a request naming one of them is not ambiguous — asking which would be
    # asking a question the reader already answered. Matched on the label as written and on its
    # words, so "condenser low flow" reaches CONDENSER_LOW_FLOW.
    text = message.lower()
    named_fault = tuple(
        e
        for e in matches
        if (label := str(e.get("fault_label", "")).lower())
        and (label in text or label.replace("_", " ") in text)
    )
    if named_fault:
        matches = named_fault
    if matches:
        resolved_day = date.fromisoformat(str(matches[0]["day"]))
    else:
        # A day written without a year cannot be reported back as a date — 1900 is a sentinel,
        # not a fact — so an unmatched partial date reports no day rather than a wrong one.
        resolved_day = None if day.year == 1900 else day
    return EpisodeRef(equipment_key=equipment_key, day=resolved_day, matches=matches)
