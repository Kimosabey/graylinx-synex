"""`K1` SOP search · `K5` source-visible answers · `S4` safety answers from the SOP.

Marked `requires_box` for the infrastructure it needs, but note **what it does not need**: the
Jarvis GPU. `nomic-embed-text` is 274 MB and runs on the host CPU, so retrieval works with the
box terminated — the same property every other gate here holds.

    docker compose -f infra/docker-compose.yml up -d postgres
    ollama pull nomic-embed-text
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.config import Settings
from app.db.knowledge import DIMENSIONS, DocumentChunk
from app.db.session import create_state_schema, state_session
from app.llm.embeddings import Embedder, EmbeddingUnavailable
from app.retrieval.sop import SopIndex

pytestmark = pytest.mark.requires_box

ISOLATION = (
    "Before opening a refrigerant circuit, isolate the compressor, lock off the starter "
    "and verify zero pressure at both gauges."
)
CLEANING = "Brush-clean condenser tubes when approach temperature exceeds the commissioned value."


@pytest.fixture
async def index():
    settings = Settings()
    await create_state_schema(settings)
    async with state_session(settings) as session:
        await session.execute(delete(DocumentChunk))
        yield SopIndex(session, Embedder(settings.embed_host))


# ── the embedder ───────────────────────────────────────────────────────────────

async def test_the_embedder_runs_without_the_gpu() -> None:
    """274 MB on the host CPU against the roster's ~41 GB on the rented card. This is why
    `K1` and `S4` are not among the six features the box gates."""
    embedder = Embedder(Settings().embed_host)
    assert await embedder.available() is True
    assert len((await embedder.embed("condenser fouling")).vector) == DIMENSIONS


async def test_an_unreachable_embedder_raises_rather_than_returning_zeros() -> None:
    """A zero vector would make every document equidistant from every query, so the search
    would return whatever came first and look like it had worked."""
    embedder = Embedder("http://127.0.0.1:59999")
    assert await embedder.available() is False
    with pytest.raises(EmbeddingUnavailable):
        await embedder.embed("anything")


async def test_the_model_travels_with_the_vector() -> None:
    """A table holding vectors from two embedding models is *silently* broken: every number
    is a valid float and every distance between them is meaningless."""
    embedding = await Embedder(Settings().embed_host).embed("suction pressure")
    assert embedding.model
    assert len(embedding.vector) == DIMENSIONS


# ── K1: search finds the right passage ─────────────────────────────────────────

async def test_search_finds_the_relevant_procedure(index: SopIndex) -> None:
    """Semantic, not keyword: the question shares almost no words with the passage."""
    await index.index(
        document="Chiller Isolation SOP", version="3", locator="§4.2",
        text=ISOLATION, is_approved=True, is_sample=True,
    )
    await index.index(
        document="Condenser Cleaning SOP", version="1", locator="§2",
        text=CLEANING, is_approved=True, is_sample=True,
    )

    result = await index.search("how do I make the compressor safe before opening it")
    assert result.available
    assert result.passages
    assert result.passages[0].document == "Chiller Isolation SOP"


# ── K5: every answer names its document and version ────────────────────────────

async def test_every_passage_carries_a_checkable_citation(index: SopIndex) -> None:
    """`K5`. A version matters: an SOP revised last month and one revised in 2019 are
    different instructions, and a citation without one cannot tell a reader which they have."""
    await index.index(
        document="Chiller Isolation SOP", version="3", locator="§4.2",
        text=ISOLATION, is_approved=True, is_sample=True,
    )
    passage = (await index.search("isolate the compressor")).passages[0]

    assert "Chiller Isolation SOP" in passage.citation
    assert "v3" in passage.citation
    assert "§4.2" in passage.citation


async def test_sample_content_is_labelled_in_its_own_citation(index: SopIndex) -> None:
    """The same escape hatch the case surface uses — visible, and never posing as the library."""
    await index.index(
        document="Draft SOP", text=ISOLATION, is_approved=True, is_sample=True
    )
    assert "(sample content)" in (await index.search("isolate")).passages[0].citation


async def test_the_distance_is_never_part_of_the_rendering(index: SopIndex) -> None:
    """Constraint 2: no numeric confidence score. A cosine distance shown to an operator
    reads as a probability that the answer is right, which it is not."""
    await index.index(document="SOP", text=ISOLATION, is_approved=True, is_sample=True)
    passage = (await index.search("isolate")).passages[0]

    assert passage.distance >= 0.0, "distance exists for ordering"
    assert str(round(passage.distance, 2)) not in passage.render()


# ── approval gates retrieval, exactly as review gates the checklist ────────────

async def test_unapproved_content_is_never_returned(index: SopIndex) -> None:
    """An SOP nobody signed off directs physical work exactly as an unreviewed checklist item
    does — constraint 1."""
    await index.index(document="Unapproved SOP", text=ISOLATION, is_approved=False)

    result = await index.search("isolate the compressor")
    assert result.passages == ()
    assert result.found_nothing


async def test_the_unapproved_count_is_reported_rather_than_hidden(index: SopIndex) -> None:
    """The gap between what exists and what may be shown is a number somebody can act on —
    the same mechanism that turned the SME hour from a blocker into a counter."""
    await index.index(document="Unapproved SOP", text=ISOLATION, is_approved=False)
    result = await index.search("isolate")

    assert result.unapproved_in_corpus == 1
    assert "not approved and were not searched" in result.render()
    assert "not a statement that no procedure exists" in result.render()


# ── an absence is not an empty result set ──────────────────────────────────────

async def test_an_unreachable_embedder_is_a_stated_absence_not_no_results(index) -> None:
    """*Nothing matched* and *we could not search* are different facts — one is about the
    library, the other about the system. An empty list would assert the first while meaning
    the second."""
    settings = Settings()
    async with state_session(settings) as session:
        broken = SopIndex(session, Embedder("http://127.0.0.1:59999"))
        result = await broken.search("anything at all")

    assert result.available is False
    assert result.found_nothing is False, "it did not look, so it found nothing in no sense"
    assert "Search is unavailable" in result.render()
    assert "not a statement about what the library contains" in result.reason


# ── S4: safety is narrower, deliberately ──────────────────────────────────────

async def test_a_safety_answer_never_comes_from_a_manual(index: SopIndex) -> None:
    """`S4`. Widening the search until something comes back is how a manufacturer's manual
    becomes a safety instruction."""
    await index.index(
        document="OEM Manual", text=ISOLATION, kind="manual", is_approved=True, is_sample=True
    )

    result = await index.search_safety("how do I isolate the compressor safely")
    assert result.passages == ()
    assert "never composed from model memory" in result.reason
    assert "ask the EHS owner" in result.reason


async def test_a_safety_answer_from_an_approved_sop_is_returned(index: SopIndex) -> None:
    await index.index(
        document="Chiller Isolation SOP", version="3", locator="§4.2",
        text=ISOLATION, kind="sop", is_approved=True, is_sample=True,
    )
    result = await index.search_safety("how do I isolate the compressor safely")

    assert result.passages
    assert result.passages[0].kind == "sop"
    assert "v3" in result.passages[0].citation


async def test_no_approved_sop_produces_a_refusal_with_its_reason(index: SopIndex) -> None:
    """The honest output. A safety question with no approved procedure behind it has no
    answer, and saying so is the answer."""
    result = await index.search_safety(f"a question about {uuid.uuid4().hex}")
    assert result.available
    assert result.passages == ()
    assert result.reason
