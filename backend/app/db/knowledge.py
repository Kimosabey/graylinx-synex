"""The document store behind `K1` SOP search and `K5` source-visible answers.

**`K5` is the reason this table has the shape it does.** *Every important answer names its
document and version.* So a chunk cannot exist without a source: the document title, its
version and the location inside it travel on the row itself rather than being looked up
later. A retrieved passage that cannot say where it came from is exactly the "confident,
unattributable" answer the honesty layer exists to refuse.

**Approved content only.** `K1` says *approved procedures, retrieved with the source shown*.
The same gate the checklist library uses applies here — `is_approved` defaults to `False`,
search returns only approved chunks, and the unapproved count is exposed as a number. An SOP
nobody signed off directs physical work exactly as a checklist item does (constraint 1).

**One model, one table.** `model` is stored per row because a table holding vectors from two
embedding models is *silently* broken: every number is a valid float and every distance
between them is meaningless. The dimension is fixed at 768 for `nomic-embed-text`, and a swap
is a migration rather than a setting.

**Why no index yet, stated rather than hidden.** pgvector's IVFFlat and HNSW indexes need a
populated table to build against and only pay off in the thousands. The corpus is 131
checklist items plus a handful of documents, so an exact scan is both faster and correct —
an approximate index here would trade accuracy for a speedup nobody would measure. `Q58`
carries the trigger.
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.db.state import Base, _now

#: Locked to `nomic-embed-text`. See `app/llm/embeddings.py` — a change here invalidates
#: every row and is therefore a migration.
DIMENSIONS: int = 768


class DocumentChunk(Base):
    """One retrievable passage, and everything needed to attribute it."""

    __tablename__ = "synex_document_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    document: Mapped[str] = mapped_column(String(200), nullable=False)
    """`K5`. The document's title, on the row. A passage that cannot name its source is not
    retrievable content — it is an unattributable claim."""

    version: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    """Also `K5`. *"names its document **and version**"* — an SOP revised last month and one
    revised in 2019 are different instructions, and a citation without a version cannot tell
    a reader which they are looking at."""

    locator: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    """Where inside the document — a section number or heading. What makes a citation
    checkable rather than merely present."""

    text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    """Which embedder produced the vector. Two models in one table is a silent corruption."""

    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="sop")
    """`sop` · `checklist` · `manual`. `S4` retrieves **only** `sop`: safety answers come
    from the procedure, never from model memory and never from a manufacturer's manual."""

    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """**Defaults to False**, like `ChecklistItem.sme_reviewed`. An unapproved SOP directs
    physical work exactly as an unreviewed checklist item does."""

    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """Illustrative content, visible and labelled — the same escape hatch the case surface
    uses, so the mechanism can be demonstrated without invented text posing as a procedure."""

    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("ix_synex_chunk_kind_approved", "kind", "is_approved"),
        Index("ix_synex_chunk_document", "document"),
    )

    def cite(self) -> str:
        """`K5`, rendered. Every part that exists is named; nothing is invented to fill a gap."""
        parts = [self.document]
        if self.version:
            parts.append(f"v{self.version}")
        if self.locator:
            parts.append(self.locator)
        citation = " · ".join(parts)
        return f"{citation} (sample content)" if self.is_sample else citation


# ── the queries, kept here because only `app.db` may hold a driver ─────────────
# Contract 6. `app/retrieval/sop.py` used to build these statements itself, which put
# `sqlalchemy` and `pgvector` imports one layer too high. Caught on 2026-08-17, the first
# time the layering config was ever able to run.


async def nearest_approved(
    session, vector: list[float], model: str, kind: str | None, limit: int
) -> list[tuple[DocumentChunk, float]]:
    """Approved chunks nearest this vector, closest first.

    The `model` filter is not optional: a table holding vectors from two embedders is
    silently broken, because every number is a valid float and every distance between them
    is meaningless.
    """
    stmt = (
        select(DocumentChunk, DocumentChunk.embedding.cosine_distance(vector).label("distance"))
        .where(DocumentChunk.is_approved.is_(True))
        .where(DocumentChunk.model == model)
        .order_by("distance")
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    rows = (await session.execute(stmt)).all()
    return [(chunk, float(distance)) for chunk, distance in rows]


async def count_unapproved(session, kind: str | None = None) -> int:
    """How much of the library exists but may not be shown. Reported, never hidden."""
    stmt = select(DocumentChunk).where(DocumentChunk.is_approved.is_(False))
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    return len((await session.scalars(stmt)).all())


async def add_chunk(session, chunk: DocumentChunk) -> DocumentChunk:
    session.add(chunk)
    await session.flush()
    return chunk
