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

**Idempotency is a column, not a convention.** `source_digest` holds the SHA-256 of the whole
source text a document was chunked from, repeated on every passage of that document. It is
what lets an ingest tell *this document is already in and unchanged* from *this document
changed and its passages are now wrong* — three outcomes rather than the two a row count can
express. Without it the only safe second run is a refusal, which is what `app/jobs/
index_library.py` had to do and what `Q97` asked about. `replace_document` is the other half:
delete-then-insert inside one session, so a failed re-ingest rolls back to the old passages
rather than leaving the document half-written.

**Approval is an act with an author, and it survives being undone.** `is_approved` is not a
flag somebody sets; it is the record of a person taking responsibility for content that
directs physical work. So four more columns travel with it — who, when, on what basis, and
whether the approval is *provisional*. Provisional means **approved by a persona to unblock
the build, pending SME validation** (`RC2`), and it is carried into `cite()` so a passage that
reaches an answer cannot read as reviewed when it is not. `ChunkApprovalEvent` keeps the
history: revoking clears the row's approval and leaves the event, because *"nobody ever
approved this"* and *"somebody approved this and it was withdrawn"* are different findings and
a later real review needs to be able to find the second one.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.state import Base, _now

#: Locked to `nomic-embed-text`. See `app/llm/embeddings.py` — a change here invalidates
#: every row and is therefore a migration.
DIMENSIONS: int = 768

#: What a citation prints where a version would go, when the document asserts none.
#:
#: **Silence is the wrong answer here and that is the whole point.** Omitting the version makes
#: *"this document carries no revision number"* and *"whoever ingested it forgot"* render
#: identically, and `K5`'s promise is that an answer names its document **and version**. So the
#: absence is printed as words — constraint 14, a figure is a value or a stated absence, never
#: both and never neither. Nothing invents `v1`: the review pack, the chapters and the FDD
#: specification carry no revision number, no date and no edition between them. `Q96`.
VERSION_NOT_STATED: str = "version not stated"

#: What a citation prints when the approval behind a passage is a persona's, not an engineer's.
#:
#: The approval column alone lives on the row; a person reading a retrieved passage sees the
#: citation. If *provisional* existed only as a column, a passage pasted into an email would
#: carry none of it — the same argument `app/jobs/index_library.py` makes for stating the
#: unreviewed state inside the passage text rather than only beside it.
PENDING_SME_VALIDATION: str = "approved pending SME validation"


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

    source_digest: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    """SHA-256 of the whole source text this document was chunked from, repeated on every one
    of its passages. The idempotency key: same digest means the document has not changed and
    re-ingesting it would only rewrite identical rows; a different digest means every passage
    of that document is stale and must be replaced rather than joined. Empty means the row
    predates this column and its document's freshness is **unknown**, which is deliberately
    not the same as *unchanged* — an ingest replaces it rather than assuming."""

    approved_by: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    """Who took responsibility. Empty whenever `is_approved` is false, and never empty when it
    is true — an approval attributable to nobody is the *"the software decided"* answer
    constraint 31 rejects, arriving one layer earlier."""

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    approval_basis: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    """Why, in words. Never a code and never a bare name: *"acted as the EHS persona to unblock
    the demonstration"* and *"reviewed against the OEM manual"* are different claims about how
    much a reader may trust the passage, and a column that held only a boolean would render
    them identically."""

    approval_is_provisional: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    """**Approved by a persona, pending SME validation** — blocker `RC2`. Indexed below so a
    later real review can list every provisional approval and revoke it in one act. This is the
    honest middle state between *unapproved and invisible* and *reviewed by a refrigeration
    engineer*, and collapsing it into either would be a lie in a different direction."""

    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("ix_synex_chunk_kind_approved", "kind", "is_approved"),
        Index("ix_synex_chunk_document", "document"),
        Index("ix_synex_chunk_provisional", "approval_is_provisional"),
    )

    @property
    def version_is_stated(self) -> bool:
        return bool(self.version.strip())

    def cite(self) -> str:
        """`K5`, rendered. Every part that exists is named; nothing is invented to fill a gap.

        **An unstated version is printed, not omitted.** `K5` promises the document *and* the
        version, so a citation that simply left the version out would make *"this document
        carries no revision number"* indistinguishable from *"the ingest dropped it"* — and a
        reader would supply the difference themselves, usually generously. Constraint 14.

        **A provisional approval is printed too**, for the same reason: the column is on the
        row and the citation is what a person sees.
        """
        parts = [self.document, f"v{self.version}" if self.version_is_stated
                 else VERSION_NOT_STATED]
        if self.locator:
            parts.append(self.locator)
        citation = " · ".join(parts)
        qualifiers = []
        if self.is_sample:
            qualifiers.append("sample content")
        if self.approval_is_provisional:
            qualifiers.append(PENDING_SME_VALIDATION)
        return f"{citation} ({'; '.join(qualifiers)})" if qualifiers else citation


class ChunkApprovalEvent(Base):
    """Every approval and every revocation, kept after the fact it recorded is undone.

    **Why revocation must not simply clear the columns.** Harshan is acting the personas to
    unblock the build and will validate with Vishnu later, so the SME hour's first job is to
    find what was approved on a persona's authority and decide about each one. If revoking
    wrote `is_approved = False` and blanked the attribution, a corpus that had been approved,
    used and withdrawn would be byte-identical to one nobody ever touched — and the review
    would have nothing to review. `G6` says the trail is permanent; this is that, for the one
    act in retrieval that lets unreviewed content direct physical work.

    Keyed on the document rather than the passage. `Q94` asks whether approval is granted per
    passage or per document-and-version, and this table takes no position on it: it records
    what the act named, and the act names a document.
    """

    __tablename__ = "synex_chunk_approval_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    document: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    """`approve` · `revoke` · `superseded_by_reingest`. The third is not a person's act: a
    document whose text changed loses its approval automatically, and recording that as a
    revocation would attribute a decision to whoever happened to run the ingest."""

    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    basis: Mapped[str] = mapped_column(String(500), nullable=False)
    is_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    passages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    def render(self) -> str:
        qualifier = " (provisional, pending SME validation)" if self.is_provisional else ""
        return (
            f"{self.at:%Y-%m-%d %H:%M} · {self.action} · {self.document} · "
            f"{self.passages} passage(s) · by {self.actor}{qualifier} — {self.basis}"
        )


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


async def approved_documents(session, kind: str | None = None) -> frozenset[str]:
    """Which documents a search could reach at all.

    Distinct titles rather than a count, because the two questions retrieval evaluation asks
    are *is there a corpus* and *does the corpus hold the document this question expects* —
    and a count answers only the first. Scoring a pair whose expected document was never
    ingested as a miss would blame the retriever for the ingest never having been run.
    """
    stmt = select(DocumentChunk.document).where(DocumentChunk.is_approved.is_(True)).distinct()
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    return frozenset((await session.scalars(stmt)).all())


async def count_unapproved(session, kind: str | None = None) -> int:
    """How much of the library exists but may not be shown. Reported, never hidden."""
    stmt = select(DocumentChunk).where(DocumentChunk.is_approved.is_(False))
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    return len((await session.scalars(stmt)).all())


async def count_approved(session, kind: str | None = None) -> int:
    """How much of the library retrieval can actually reach.

    **Reachable and non-empty are different facts about the vector store**, and the health
    surface needs both: a store that answers while holding nothing returns no passages, which
    reads as a plant with no documentation rather than as a store nobody filled. Counted here
    rather than in the API layer because `app.api` may not import a driver — the contract that
    keeps every query in one place.
    """
    stmt = select(DocumentChunk).where(DocumentChunk.is_approved.is_(True))
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    return len((await session.scalars(stmt)).all())


async def add_chunk(session, chunk: DocumentChunk) -> DocumentChunk:
    session.add(chunk)
    await session.flush()
    return chunk


# ── idempotency: the digest, and the replace it makes safe ─────────────────────


def digest_of(text_content: str) -> str:
    """The idempotency key for one source document.

    SHA-256 of the exact source text, before chunking, so the question *"has this document
    changed?"* is answered by the document rather than by its passages. Taking it after
    chunking would make a change to the splitter look like a change to the document, and an
    ingest would then silently rewrite a corpus nobody edited.
    """
    return hashlib.sha256(text_content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DocumentRecord:
    """What the store holds for one document — enough to decide what an ingest should do."""

    document: str
    kind: str
    version: str
    passages: int
    approved: int
    provisional: int
    source_digest: str

    @property
    def digest_is_known(self) -> bool:
        """Empty means the rows predate the digest column. **Not** the same as unchanged: an
        ingest replaces an unknown-digest document rather than assuming it is current."""
        return bool(self.source_digest)


async def corpus_inventory(session, kind: str | None = None) -> tuple[DocumentRecord, ...]:
    """Every document in the store, with its counts. What `--check` prints and ingest reads.

    Grouped in the database rather than by loading rows, because the embedding column is 768
    floats wide and nothing here needs a single one of them.
    """
    stmt = (
        select(
            DocumentChunk.document,
            func.min(DocumentChunk.kind),
            func.min(DocumentChunk.version),
            func.count(DocumentChunk.id),
            func.count(DocumentChunk.id).filter(DocumentChunk.is_approved.is_(True)),
            func.count(DocumentChunk.id).filter(
                DocumentChunk.approval_is_provisional.is_(True)
            ),
            func.min(DocumentChunk.source_digest),
        )
        .group_by(DocumentChunk.document)
        .order_by(DocumentChunk.document)
    )
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    return tuple(
        DocumentRecord(
            document=document,
            kind=row_kind or "",
            version=version or "",
            passages=passages,
            approved=approved,
            provisional=provisional,
            source_digest=source_digest or "",
        )
        for document, row_kind, version, passages, approved, provisional, source_digest in (
            await session.execute(stmt)
        ).all()
    )


async def delete_document(session, document: str) -> int:
    """Remove every passage of one document. Returns how many went.

    Scoped to one document by name and never offered without one: a delete that could take the
    whole table is one line away from being called with a `None` that reads as *"all"*.
    """
    result = await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document == document)
    )
    return int(result.rowcount or 0)


# ── approval: an act with an author, reversible, and recorded either way ───────


async def set_approval(
    session,
    document: str,
    *,
    approved: bool,
    actor: str,
    basis: str,
    provisional: bool = True,
) -> int:
    """Approve or un-approve every passage of one document. Returns how many rows moved.

    **Approving takes an actor and a basis, and there is no default for either.** An approval
    attributable to nobody, for no stated reason, is what an unreviewed procedure looked like
    the last time one reached a technician — inherited constraint 1 exists because of that
    incident. Un-approving clears the attribution on the row and leaves the event behind it.
    """
    if approved and not (actor.strip() and basis.strip()):
        raise ValueError(
            "an approval needs an actor and a basis in words. A passage approved by nobody, "
            "for no recorded reason, directs physical work with nothing behind it"
        )
    values: dict[str, object] = (
        {
            "is_approved": True,
            "approved_by": actor,
            "approval_basis": basis,
            "approval_is_provisional": provisional,
            "approved_at": _now(),
        }
        if approved
        else {
            "is_approved": False,
            "approved_by": "",
            "approval_basis": "",
            "approval_is_provisional": False,
            "approved_at": None,
        }
    )
    result = await session.execute(
        update(DocumentChunk).where(DocumentChunk.document == document).values(**values)
    )
    return int(result.rowcount or 0)


async def record_approval_event(session, event: ChunkApprovalEvent) -> ChunkApprovalEvent:
    session.add(event)
    await session.flush()
    return event


async def approval_events(session, document: str | None = None) -> tuple[ChunkApprovalEvent, ...]:
    """The trail, newest last. What a real SME review reads before it revokes anything."""
    stmt = select(ChunkApprovalEvent).order_by(ChunkApprovalEvent.at, ChunkApprovalEvent.id)
    if document:
        stmt = stmt.where(ChunkApprovalEvent.document == document)
    return tuple((await session.scalars(stmt)).all())


async def provisionally_approved_documents(session) -> frozenset[str]:
    """Every document a persona approved and no engineer has validated. `RC2`'s worklist."""
    stmt = (
        select(DocumentChunk.document)
        .where(DocumentChunk.approval_is_provisional.is_(True))
        .distinct()
    )
    return frozenset((await session.scalars(stmt)).all())


# ── the additive migration this file's new columns need ───────────────────────


#: Every column added to `synex_document_chunk` after the table first shipped, with the DDL
#: that adds it. `Base.metadata.create_all` creates tables and **never alters one**, which its
#: own docstring says — so a column added here would exist in the model, be absent from a
#: database created last week, and fail on the first query rather than at startup.
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_digest", "VARCHAR(64) NOT NULL DEFAULT ''"),
    ("approved_by", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("approved_at", "TIMESTAMPTZ NULL"),
    ("approval_basis", "VARCHAR(500) NOT NULL DEFAULT ''"),
    ("approval_is_provisional", "BOOLEAN NOT NULL DEFAULT FALSE"),
)


async def ensure_knowledge_columns(session) -> tuple[str, ...]:
    """Add the columns above to an existing table. Returns what it ran, for the record.

    **Additive only, and that is a property rather than an intention** — every statement is an
    `ADD COLUMN IF NOT EXISTS` with a default, so running it against a current database does
    nothing and running it against an old one cannot lose a row. A migration that could drop
    or retype a column has no business being called automatically by an ingest.

    This is the migration path until Alembic, said out loud for the same reason
    `create_state_schema` says it: a reader who assumes migrations exist writes one that never
    runs.
    """
    statements = tuple(
        f"ALTER TABLE synex_document_chunk ADD COLUMN IF NOT EXISTS {name} {ddl}"
        for name, ddl in _ADDED_COLUMNS
    )
    for statement in statements:
        await session.execute(text(statement))
    return statements
