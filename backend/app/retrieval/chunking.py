"""How a document becomes passages — chunking decides what can ever be retrieved.

**The failure this prevents, and it is live in this repository.** `SopIndex.index()` takes
whole text and embeds it as a single 768-dimension vector. The source Product & Architecture
Document is **78 pages and 44 chapters**; the checklist library is **124 curated items across
11 fault classes** plus a 7-item generic fallback, **24 of them blocking**. Ingested whole, 44
chapters become one vector and one citation reading *"Product & Architecture Document v4"* —
which satisfies `K5`'s document-and-version half and destroys the half that matters, the
`locator` that makes a citation **checkable**. A reader handed a chapter-less citation cannot
find the sentence, so the passage stops being evidence with an address and becomes a paragraph
that sounds right. That is exactly what `app/retrieval/sop.py` says retrieval must never be.

The opposite error costs more. A blocking item severed from the condition it applies under
reads as a demand on whoever is standing there — the same defect inherited constraint 38
describes for a greyed-out check, arriving by a different door. So:

| | Rule | Why |
|---|---|---|
| 1 | Split on **structure**, never on a character count | A character count cuts mid-sentence
  and mid-list. Constraint 1: the library is curated content, and a boundary chosen by
  arithmetic is not curation |
| 38 | A numbered step **never starts a chunk** | A step list travels with the prose that
  introduces it. *"Close the discharge valve"* without *"once the machine is isolated"* is
  worse than no chunk, because it reads as complete |
| 1 | A document with **no structure is not split at all** | It becomes one passage, and says
  so. Inventing a boundary in unstructured prose is inventing curation |
| 14 | A concern is **words**, never a flag | A figure is a value or a stated absence. A chunk
  that quietly carries a defect is the dash wearing a sentence |

**No character limit is sourced anywhere.** `MAX_PASSAGE_CHARS` is `TBD (Q92)` and it
**annotates only** — nothing here splits, drops or truncates a passage because of it. A
threshold that silently cut a checklist would be the unreviewed-judgement failure that
`app/domain/differential.py` exists to prevent, one layer down in the ingest.

**Nothing here has ever run against a real SOP.** `synex_document_chunk` holds zero rows, so
the structure markers below are inferred from the shape of the checklist library rather than
read off a document the site actually uses. `Q93` carries that, and it is the reason every
boundary this module finds is reported by name in `Chunk.split_on` — a chunking decision
nobody can inspect is indistinguishable from a guess.

**Chunking multiplies the approval, and nobody has decided how.** `is_approved` is a column on
the *passage*, so a document that becomes eleven passages becomes eleven approvals — and a
re-ingest after an edit resets all of them to `False`, which is the safe direction and a
tedious one. `Q94` carries whether approval is granted per passage or per document-and-version.
Nothing here guesses: `index_arguments` cannot set `is_approved` at all.

**A stated limitation.** The ancestor headings are *not* prepended to the passage text before
it is embedded, although that measurably helps retrieval, because the stored text is what a
reader checks the citation against and a store that embeds one string and shows another cannot
be checked. The ancestors travel in `heading_path` and the section reaches the citation through
`locator`. Fixing this properly means a second column, not a quiet substitution.

**Nothing here calls a model.** Chunking is arithmetic over text; a model choosing the
boundaries would be the language model deciding what a technician is allowed to see.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

#: How long a passage may be before it is *annotated* as long. **It never causes a split.**
#:
#: TBD (Q92) — no document, and no source under `docs/00-source/`, states a passage size. The
#: value here is an annotation threshold and nothing else: `chunk_document` never splits,
#: truncates or drops on it, so being wrong costs a note a human reads rather than a checklist
#: cut in half. Until Q92 is answered, structure is the only thing that decides a boundary.
MAX_PASSAGE_CHARS: int = 2_000

#: The width of `synex_document_chunk.locator`. Sourced from the column itself —
#: `String(120)` in `app/db/knowledge.py` — rather than chosen here, so the two cannot drift.
#: A locator longer than this is shortened **and says it was**, because a citation silently
#: cut at the column width points somewhere the reader cannot verify.
LOCATOR_CHARS: int = 120


class Boundary(StrEnum):
    """What made this passage start. Reported so a boundary can be argued with.

    Five, and `NO_STRUCTURE` is deliberately not a sixth kind of heading: it is the statement
    that the splitter found nothing to split on, which is a fact about the document rather
    than a decision about it.
    """

    DOCUMENT_START = "document_start"
    """The text before the first heading. It is kept rather than discarded — a preamble
    usually holds the scope sentence the rest of the document applies under."""

    MARKDOWN_HEADING = "markdown_heading"
    NUMBERED_HEADING = "numbered_heading"
    """`§4.2` or `4.2 Condenser isolation`. Dotted, because a flat `4.` is a step."""

    UNDERLINED_HEADING = "underlined_heading"
    NO_STRUCTURE = "no_structure"
    """Nothing in this document marks a section, so it was not split. See `Q93`."""


# ── what a heading looks like, held as data ────────────────────────────────────────────────
# Inferred from the checklist library's shape, not from an ingested SOP — no SOP has ever been
# ingested (`synex_document_chunk` holds zero rows). `Q93` carries the confirmation.
#
# The one judgement worth stating: **a dotted number is a heading and a flat number is a
# step.** `4.2 Condenser isolation` names a section; `4. Close the discharge valve` is an
# instruction. Getting this backwards would sever every checklist in the corpus, which is why
# it is a rule with a reason here rather than a regex somebody widens later.

_ATX_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>\S.*?)\s*#*$")
_SECTION_MARK = re.compile(r"^§\s*(?P<number>\d+(?:\.\d+)*)\.?\s*(?P<title>.*)$")
_DOTTED_HEADING = re.compile(r"^(?P<number>\d+(?:\.\d+)+)\.?\s+(?P<title>\S.*)$")
_UNDERLINE_MAJOR = re.compile(r"={3,}")
_UNDERLINE_MINOR = re.compile(r"-{3,}")

#: A numbered step, and the whole point of the module: this pattern never opens a chunk.
_STEP = re.compile(r"^\s*(?:step\s+)?(?P<number>\d{1,2})\s*[.)]\s+(?P<text>\S.*)$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*[-*•]\s+\S")


@dataclass(frozen=True)
class _Heading:
    """One recognised heading. Internal — the public record is `Chunk.split_on`."""

    level: int
    number: str
    title: str
    boundary: Boundary
    lines_consumed: int


@dataclass(frozen=True)
class Chunk:
    """One passage, and everything a citation and a reviewer need to check it.

    The text is **verbatim**, including its own heading line. A passage that had its heading
    stripped loses the topic it belongs to, and a passage rewritten to read better can no
    longer be checked against the document it claims to come from.
    """

    text: str
    locator: str
    """What `K5` cites, and what makes the citation checkable. Bounded by `LOCATOR_CHARS`."""

    heading_path: tuple[str, ...]
    """Ancestors, outermost first. Empty for a preamble or an unstructured document."""

    split_on: Boundary
    step_count: int
    holds_steps: bool
    steps_have_a_lead_in: bool
    """Is there prose before the first step? Constraint 38's rule at ingest: a step list with
    no lead-in states no condition, so whatever it applies under is in a different passage or
    absent from the document entirely."""

    concerns: tuple[str, ...] = field(default_factory=tuple)
    """Words, always — never a flag and never a count on its own. Each one names what a
    reader would get wrong if they trusted this passage as it stands."""

    @property
    def characters(self) -> int:
        return len(self.text)

    @property
    def is_clean(self) -> bool:
        return not self.concerns

    def index_arguments(self, *, document: str, version: str = "") -> dict[str, str]:
        """Exactly what `SopIndex.index()` needs, so a caller cannot forget the locator.

        `is_approved` is deliberately absent: it defaults to `False` at the call site and at
        the column, and a chunker that could set it would let ingest grant approval.
        """
        return {
            "document": document,
            "version": version,
            "locator": self.locator,
            "text": self.text,
        }

    def render(self) -> str:
        steps = (
            f"{self.step_count} numbered step(s)" if self.holds_steps else "no numbered steps"
        )
        concerns = "; ".join(self.concerns) if self.concerns else "no concerns recorded"
        return (
            f"{self.locator} — split on {self.split_on.value}, {self.characters} characters, "
            f"{steps}. {concerns}."
        )


@dataclass(frozen=True)
class ChunkedDocument:
    """What one document became, and why it became that.

    Carries the reason even when it succeeded. A splitter that reports only its failures makes
    the ordinary case unauditable, and the ordinary case is where the damage is silent.
    """

    document: str
    version: str
    chunks: tuple[Chunk, ...]
    structure_found: bool
    reason: str
    """Words. *Nothing to split* and *nothing to split on* are different facts about a
    document, and both are different from *this document is empty*."""

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    @property
    def concerns(self) -> tuple[str, ...]:
        """Every concern from every passage, each carrying the locator it belongs to."""
        return tuple(
            f"{chunk.locator}: {concern}" for chunk in self.chunks for concern in chunk.concerns
        )

    def index_arguments(self) -> tuple[dict[str, str], ...]:
        return tuple(
            chunk.index_arguments(document=self.document, version=self.version)
            for chunk in self.chunks
        )

    def render(self) -> str:
        if self.is_empty:
            return f"{self.document}: {self.reason}"
        lines = [f"{self.document}: {self.reason}"]
        lines.extend(f"  {chunk.render()}" for chunk in self.chunks)
        return "\n".join(lines)


def _heading_at(lines: list[str], i: int) -> _Heading | None:
    """Is line `i` a heading, and of what kind? `None` means it is body text.

    Checked in order, and the order is the rule: a markdown hash beats a section mark beats a
    dotted number, and a **flat** number reaches none of them because it is a step.
    """
    stripped = lines[i].strip()
    if not stripped:
        return None

    match = _ATX_HEADING.match(stripped)
    if match:
        return _Heading(
            level=len(match.group("hashes")),
            number="",
            title=match.group("title").strip(),
            boundary=Boundary.MARKDOWN_HEADING,
            lines_consumed=1,
        )

    for pattern in (_SECTION_MARK, _DOTTED_HEADING):
        match = pattern.match(stripped)
        if match:
            number = match.group("number")
            return _Heading(
                level=number.count(".") + 1,
                number=number,
                title=match.group("title").strip(),
                boundary=Boundary.NUMBERED_HEADING,
                lines_consumed=1,
            )

    # An underlined heading is the only form that needs the *next* line, and a step or a
    # bullet is excluded first: `- - -` under a bullet is a rule, not a title.
    if _STEP.match(stripped) or _BULLET.match(stripped):
        return None
    following = lines[i + 1].strip() if i + 1 < len(lines) else ""
    level = 0
    if _UNDERLINE_MAJOR.fullmatch(following):
        level = 1
    elif _UNDERLINE_MINOR.fullmatch(following):
        level = 2
    if level:
        return _Heading(level, "", stripped, Boundary.UNDERLINED_HEADING, 2)
    return None


def _locator_for(heading: _Heading | None, path: tuple[str, ...]) -> tuple[str, str]:
    """The citation's address, and the reason if it had to be shortened.

    Built from this section's own number and title rather than the whole path, so it stays
    short by construction instead of being cut at the column width.
    """
    if heading is None:
        return "before the first heading", ""
    parts = []
    if heading.number:
        parts.append(f"§{heading.number}")
    if heading.title:
        parts.append(heading.title)
    if not parts:
        parts = [path[-1]] if path else ["untitled section"]
    locator = " ".join(parts)
    if len(locator) <= LOCATOR_CHARS:
        return locator, ""
    return locator[: LOCATOR_CHARS - 1] + "…", (
        f"the heading is {len(locator)} characters and the citation column holds "
        f"{LOCATOR_CHARS}, so the locator is shortened — a reader checking this citation is "
        f"looking for a longer heading than the one printed"
    )


def _step_shape(body_lines: list[str]) -> tuple[int, bool]:
    """`(how many numbered steps, is there prose before the first one)`.

    The second value is the constraint-38 check at ingest. Prose here means a line that is
    neither blank, nor a step, nor a bullet, nor the heading itself.
    """
    step_count = 0
    lead_in = False
    seen_prose = False
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _STEP.match(stripped):
            if step_count == 0:
                lead_in = seen_prose
            step_count += 1
            continue
        if not _BULLET.match(stripped):
            seen_prose = True
    return step_count, lead_in


def _build_chunk(
    raw_lines: list[str], heading: _Heading | None, path: tuple[str, ...]
) -> Chunk | None:
    """One passage from the lines collected under one heading, or `None` if it is all blank."""
    text = "\n".join(raw_lines).strip("\n")
    if not text.strip():
        return None

    locator, locator_concern = _locator_for(heading, path)
    body = raw_lines[heading.lines_consumed :] if heading else raw_lines
    step_count, lead_in = _step_shape(body)

    concerns: list[str] = []
    if locator_concern:
        concerns.append(locator_concern)
    if step_count and not lead_in:
        concerns.append(
            f"{step_count} numbered step(s) begin with no prose before them, so the condition "
            f"they apply under is in another passage or absent from the document — a step read "
            f"without its condition reads as complete when it is not"
        )
    if len(text) > MAX_PASSAGE_CHARS:
        concerns.append(
            f"this passage is {len(text)} characters against an annotation threshold of "
            f"{MAX_PASSAGE_CHARS} (unsourced — Q92); nothing was split, and a citation to it "
            f"points at a span a reader has to search"
        )

    return Chunk(
        text=text,
        locator=locator,
        heading_path=path,
        split_on=heading.boundary if heading else Boundary.DOCUMENT_START,
        step_count=step_count,
        holds_steps=step_count > 0,
        steps_have_a_lead_in=lead_in,
        concerns=tuple(concerns),
    )


def chunk_document(text: str, *, document: str, version: str = "") -> ChunkedDocument:
    """Split one document into retrievable passages on its own structure.

    Three outcomes, kept distinct because each tells the ingester to do something different:

    * **structure found** — one passage per heading, every step list whole and with whatever
      prose introduces it
    * **no structure** — one passage for the whole document, reported as such. Nothing is cut
      by arithmetic, because a boundary chosen by arithmetic is not curation
    * **nothing to split** — the document is empty or blank. Zero passages, and a reason;
      never one empty passage, which would index as a chunk that matches nothing and cites
      a document
    """
    lines = text.splitlines()
    chunks: list[Chunk] = []
    stack: list[_Heading] = []

    current_heading: _Heading | None = None
    current_path: tuple[str, ...] = ()
    buffer: list[str] = []

    index = 0
    while index < len(lines):
        heading = _heading_at(lines, index)
        if heading is None:
            buffer.append(lines[index])
            index += 1
            continue

        built = _build_chunk(buffer, current_heading, current_path)
        if built is not None:
            chunks.append(built)

        stack = [existing for existing in stack if existing.level < heading.level]
        stack.append(heading)
        current_heading = heading
        current_path = tuple(entry.title or f"§{entry.number}" for entry in stack)
        buffer = lines[index : index + heading.lines_consumed]
        index += heading.lines_consumed

    built = _build_chunk(buffer, current_heading, current_path)
    if built is not None:
        chunks.append(built)

    structure_found = any(chunk.split_on is not Boundary.DOCUMENT_START for chunk in chunks)

    if not chunks:
        reason = (
            "there is nothing to split — the document is empty or entirely blank. No passage "
            "was produced, because an empty passage would index as a chunk that matches "
            "nothing and still carries a citation"
        )
    elif structure_found:
        reason = (
            f"split into {len(chunks)} passage(s) on the document's own structure — headings "
            f"and section numbers. No passage was cut at a character count, and no numbered "
            f"step opened one"
        )
    else:
        reason = (
            "this document marks no sections, so it was not split: nothing here invents a "
            "boundary in unstructured prose. Its citation points at the whole document, which "
            "is a weaker address than K5 wants and an honest one. See Q93"
        )
        chunks = [
            Chunk(
                text=chunks[0].text,
                locator=chunks[0].locator,
                heading_path=(),
                split_on=Boundary.NO_STRUCTURE,
                step_count=chunks[0].step_count,
                holds_steps=chunks[0].holds_steps,
                steps_have_a_lead_in=chunks[0].steps_have_a_lead_in,
                concerns=(
                    *chunks[0].concerns,
                    "this document has no headings and no section numbers, so the whole of it "
                    "is one passage and its citation names no place inside it",
                ),
            )
        ]

    return ChunkedDocument(
        document=document,
        version=version,
        chunks=tuple(chunks),
        structure_found=structure_found,
        reason=reason,
    )
