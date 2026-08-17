"""Chunking decides what can ever be retrieved, so these are tests about a ceiling.

No retrieval improvement can recover a passage the splitter never made. `synex_document_chunk`
holds zero rows, so nothing here has been checked against a real SOP — these tests fix the
*rules* (`Q93` fixes the markers) and, above all, fix the one that costs a person: a numbered
step never opens a passage, so an instruction is never severed from the condition it applies
under. Everything else in this file is arithmetic.
"""
from __future__ import annotations

from app.llm.embeddings import DIMENSIONS, Embedding
from app.retrieval.chunking import (
    LOCATOR_CHARS,
    MAX_PASSAGE_CHARS,
    Boundary,
    chunk_document,
)
from app.retrieval.sop import SopIndex

ISOLATION = """# Chiller Isolation SOP

This procedure applies only once the machine has been stopped and the starter locked off.

1. Close the discharge service valve.
2. Close the suction service valve.
3. Verify zero pressure at both gauges before opening any joint.

## Condenser cleaning

Brush-clean the tubes when approach temperature exceeds the commissioned value.
"""


class _StubSession:
    """Enough of a session for `add_chunk`. The store is not what these tests are about."""

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None


class _StubEmbedder:
    """A fixed 768-dimension vector. `Embedding.__post_init__` still enforces the dimension,
    so a stub that drifted from the store's shape would fail here rather than in production."""

    async def embed(self, text: str) -> Embedding:
        return Embedding(text=text, vector=(0.0,) * DIMENSIONS, model="stub-embedder")


def _by_locator(text: str, locator: str):
    chunked = chunk_document(text, document="Chiller Isolation SOP", version="3")
    return next(chunk for chunk in chunked.chunks if chunk.locator == locator)


# ── the rule that costs a person if it is wrong ────────────────────────────────

def test_a_numbered_step_never_opens_a_passage() -> None:
    """The whole reason this module exists. *"Close the discharge service valve"* on its own
    reads as complete; with *"only once the machine has been stopped"* above it, it is an
    instruction. Splitting on the step would produce three passages that each look finished.
    """
    chunked = chunk_document(ISOLATION, document="Chiller Isolation SOP", version="3")
    for chunk in chunked.chunks:
        assert not chunk.text.lstrip().startswith("1."), chunk.locator
        assert chunk.split_on is not Boundary.NO_STRUCTURE


def test_a_step_list_stays_whole_and_keeps_the_prose_that_introduces_it() -> None:
    """Three steps and their condition are one passage, not four. A checklist step severed
    from its rationale is worse than no chunk, because the reader cannot tell it is missing."""
    chunk = _by_locator(ISOLATION, "Chiller Isolation SOP")

    assert chunk.step_count == 3
    assert chunk.steps_have_a_lead_in is True
    assert "once the machine has been stopped" in chunk.text
    assert "Verify zero pressure" in chunk.text
    assert chunk.is_clean, chunk.concerns


def test_steps_with_no_prose_before_them_carry_the_concern_in_words() -> None:
    """Inherited constraint 38 at ingest: a check the reader cannot place is still a demand on
    whoever is standing there. The passage is kept — it is evidence of a defect in the
    document — and it says what a reader would get wrong by trusting it."""
    chunk = _by_locator(
        "## Isolation\n1. Close the discharge valve.\n2. Close the suction valve.\n",
        "Isolation",
    )

    assert chunk.steps_have_a_lead_in is False
    assert chunk.concerns, "a severed step list must never be silently clean"
    assert "the condition they apply under" in chunk.concerns[0]
    assert "reads as complete when it is not" in chunk.concerns[0]


# ── structure, not arithmetic ──────────────────────────────────────────────────

def test_a_markdown_heading_opens_a_passage_and_travels_inside_it() -> None:
    """A passage stripped of its heading loses the topic it belongs to, and then embeds as
    prose about nothing in particular."""
    chunk = _by_locator(ISOLATION, "Condenser cleaning")

    assert chunk.split_on is Boundary.MARKDOWN_HEADING
    assert chunk.text.startswith("## Condenser cleaning")
    assert chunk.heading_path == ("Chiller Isolation SOP", "Condenser cleaning")


def test_a_dotted_number_is_a_heading_and_a_flat_number_is_a_step() -> None:
    """The one judgement in the module, and getting it backwards severs every checklist in the
    corpus. `4.2 Condenser isolation` names a section; `4. Close the valve` is an instruction.
    """
    chunked = chunk_document(
        "4.2 Condenser isolation\nIsolate before starting.\n4. Close the valve.\n",
        document="Ops Manual",
    )

    assert chunked.chunk_count == 1
    chunk = chunked.chunks[0]
    assert chunk.split_on is Boundary.NUMBERED_HEADING
    assert chunk.locator == "§4.2 Condenser isolation"
    assert chunk.step_count == 1


def test_a_section_mark_is_recognised_because_that_is_what_K5_cites() -> None:
    """The existing citations in the integration suite read `§4.2`. A splitter that did not
    recognise the form the documents already use would produce locators nobody can match."""
    chunked = chunk_document("§4.2 Isolation\nLock off the starter.\n", document="SOP")

    assert chunked.chunks[0].locator == "§4.2 Isolation"
    assert chunked.chunks[0].split_on is Boundary.NUMBERED_HEADING


def test_an_underlined_heading_opens_a_passage() -> None:
    """Plain-text SOPs underline rather than hash. Missing the form would put a whole document
    into one passage and report `structure_found` as false, which is a false statement."""
    chunked = chunk_document(
        "Isolation\n=========\nLock off the starter.\n\nCleaning\n--------\nBrush the tubes.\n",
        document="SOP",
    )

    assert chunked.chunk_count == 2
    assert {c.split_on for c in chunked.chunks} == {Boundary.UNDERLINED_HEADING}
    assert [c.locator for c in chunked.chunks] == ["Isolation", "Cleaning"]


def test_the_text_before_the_first_heading_is_kept_and_says_where_it_is_from() -> None:
    """A preamble usually holds the scope sentence the rest of the document applies under.
    Discarding it is how a procedure loses the plant it belongs to."""
    chunked = chunk_document(
        "This manual covers water-cooled chillers only.\n\n# Isolation\nLock off.\n",
        document="SOP",
    )

    assert chunked.chunks[0].locator == "before the first heading"
    assert chunked.chunks[0].split_on is Boundary.DOCUMENT_START
    assert "water-cooled chillers only" in chunked.chunks[0].text


# ── the three outcomes are kept distinct ───────────────────────────────────────

def test_an_unstructured_document_is_not_split_and_says_so() -> None:
    """No character limit is sourced anywhere (`Q92`), and a boundary chosen by arithmetic is
    not curation. One passage, and a concern stating that its citation names no place inside
    the document — which is a weaker address than `K5` wants and an honest one."""
    prose = "Refrigerant handling is governed by site policy. " * 60
    chunked = chunk_document(prose, document="Site Policy")

    assert chunked.chunk_count == 1
    assert chunked.structure_found is False
    assert chunked.chunks[0].split_on is Boundary.NO_STRUCTURE
    assert "invents a boundary in unstructured prose" in chunked.reason
    assert any("names no place inside it" in c for c in chunked.chunks[0].concerns)


def test_an_empty_document_produces_no_passage_rather_than_an_empty_one() -> None:
    """An empty chunk would index as a row that matches nothing and still carries a citation —
    a passage asserting a source for no content. Zero passages and a reason instead."""
    chunked = chunk_document("   \n\n\t\n", document="Blank SOP")

    assert chunked.chunks == ()
    assert chunked.is_empty is True
    assert "nothing to split" in chunked.reason
    assert "would index as a chunk that matches nothing" in chunked.reason


def test_nothing_to_split_and_nothing_to_split_on_are_different_reasons() -> None:
    """One says the document is blank, the other says it has no sections. They send an
    ingester to two different places, so they must never share a message."""
    blank = chunk_document("", document="A").reason
    unstructured = chunk_document("One paragraph, no headings at all.", document="B").reason

    assert blank != unstructured
    assert "Q93" in unstructured


# ── the unsourced number annotates and never acts ──────────────────────────────

def test_the_length_threshold_annotates_and_never_splits() -> None:
    """`MAX_PASSAGE_CHARS` is `TBD (Q92)`. A threshold that silently cut a checklist would be
    unreviewed judgement severing an instruction, so being wrong here must cost a note a human
    reads rather than a passage a technician never sees."""
    long_body = "# Isolation\n" + ("Check the gauge reading and record it. " * 120)
    chunked = chunk_document(long_body, document="SOP")

    assert chunked.chunk_count == 1, "the threshold must never cause a split"
    assert chunked.chunks[0].characters > MAX_PASSAGE_CHARS
    assert any("Q92" in concern for concern in chunked.chunks[0].concerns)


def test_a_long_heading_is_shortened_and_the_shortening_is_declared() -> None:
    """`locator` is `String(120)`. A citation silently cut at the column width points somewhere
    the reader cannot verify, which is worse than a citation that admits it was trimmed."""
    heading = "# " + ("Condenser water side isolation and lockout " * 5)
    chunk = chunk_document(heading + "\nLock off.\n", document="SOP").chunks[0]

    assert len(chunk.locator) <= LOCATOR_CHARS
    assert chunk.locator.endswith("…")
    assert any("shortened" in concern for concern in chunk.concerns)


# ── what the ingester is handed ────────────────────────────────────────────────

def test_index_arguments_carry_the_locator_so_a_caller_cannot_forget_it() -> None:
    """`K5` needs document, version **and** the place inside. The locator is the half that
    makes a citation checkable, and the half a hand-written call site drops."""
    chunked = chunk_document(ISOLATION, document="Chiller Isolation SOP", version="3")
    arguments = chunked.index_arguments()

    assert len(arguments) == chunked.chunk_count
    for entry in arguments:
        assert entry["document"] == "Chiller Isolation SOP"
        assert entry["version"] == "3"
        assert entry["locator"]
        assert entry["text"].strip()


def test_index_arguments_cannot_grant_approval() -> None:
    """`is_approved` defaults to False at the call site and at the column. A chunker that could
    set it would let ingest approve an SOP nobody signed off — constraint 1."""
    entry = chunk_document(ISOLATION, document="SOP").index_arguments()[0]
    assert "is_approved" not in entry


async def test_index_document_stores_one_row_per_passage_each_with_its_locator() -> None:
    """The route `index()` alone cannot take. Offline with stubs, because the property worth
    fixing is that the splitter's locator reaches the stored row — not that Postgres works."""
    session = _StubSession()
    index = SopIndex(session, _StubEmbedder())

    chunked, stored = await index.index_document(
        document="Chiller Isolation SOP", text=ISOLATION, version="3", is_sample=True
    )

    assert len(stored) == chunked.chunk_count == 2
    assert [row.locator for row in stored] == [c.locator for c in chunked.chunks]
    assert all(row.is_approved is False for row in stored), "ingest never grants approval"
    assert "§4.2" not in stored[0].cite(), "this document numbers nothing"
    assert "Chiller Isolation SOP · v3" in stored[0].cite()


async def test_index_document_stores_nothing_for_an_empty_document_and_says_why() -> None:
    """A row for a blank document would be a citation with no content behind it — an
    unattributable claim built the other way round."""
    session = _StubSession()
    chunked, stored = await SopIndex(session, _StubEmbedder()).index_document(
        document="Blank SOP", text="\n\n  \n"
    )

    assert stored == ()
    assert session.added == []
    assert "nothing to split" in chunked.reason


def test_every_concern_is_reported_with_the_passage_it_belongs_to() -> None:
    """A concern with no locator cannot be acted on, and a document-level count of concerns is
    the dash wearing a sentence."""
    chunked = chunk_document("## Isolation\n1. Close the valve.\n", document="SOP")

    assert chunked.concerns
    assert chunked.concerns[0].startswith("Isolation: ")
