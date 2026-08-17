"""`K1` SOP search · `K5` source-visible answers · `S4` safety answers from the SOP.

**The rule that makes retrieval honest here, and it is not ours.** From the Thermynx playbook
review: *"If a playbook entry is just prose without naming a real database field and a real
threshold, the model cannot connect it to what it is reading from the sensors — it stays
generic."* That is `C21`'s figure discipline arriving from the knowledge side. So a retrieved
passage is evidence with an address, never a paragraph that sounds right.

**`S4` is narrower than `K1`, deliberately.** *Safety answers are never answered from model
memory* — so `search_safety` restricts to `kind="sop"` and to approved content, and returns a
**refusal with a reason** when nothing approved matches. The tempting alternative is to widen
the search until something comes back; that is how a manufacturer's manual, or a plausible
sentence, becomes a safety instruction.

**Nothing here ranks by a score a reader sees.** Inherited constraint 2: no numeric confidence
score. Distance orders the results and is never rendered as a percentage — a cosine distance
presented to an operator reads as a probability that the answer is right, which it is not.

**Exact search, and the reason is stated rather than hidden.** The corpus is small enough that
an approximate index would trade accuracy for a speedup nobody would measure. `Q58` carries
the trigger for adding one.

**Retrieval degrades to a stated absence.** If the embedder is unreachable, this returns
`Unavailable` with the reason in words — never an empty result set, because an empty result
set reads as *"the library has nothing on this"*, which is a different and false claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.knowledge import DocumentChunk
from app.llm.embeddings import Embedder, EmbeddingUnavailable

#: How many passages a search returns. Small on purpose: a reader who is handed twelve
#: passages reads none of them, and the top few are what a citation is built from.
#:
#: TBD (Q59) — no document fixes it. Five because the four decision trees and the seven-item
#: generic fallback mean a single question rarely has more than a handful of relevant entries.
#: It bounds display only; it never suppresses a match from being findable.
DEFAULT_LIMIT: int = 5


@dataclass(frozen=True)
class Passage:
    """One retrieved passage, carrying its own attribution. `K5`."""

    text: str
    citation: str
    document: str
    version: str
    locator: str
    kind: str
    is_sample: bool
    distance: float
    """Ordering only. **Never rendered to a reader** — constraint 2 forbids a numeric
    confidence score, and a distance shown in an interface is read as one."""

    def render(self) -> str:
        return f"{self.text}\n\n— {self.citation}"


@dataclass(frozen=True)
class SearchResult:
    """What a search found, or why it could not look."""

    passages: tuple[Passage, ...] = field(default_factory=tuple)
    available: bool = True
    reason: str = ""
    """Words, always. The difference between *nothing matched* and *we could not search* is
    the difference between a fact about the library and a fact about the system."""

    unapproved_in_corpus: int = 0
    """Exposed rather than hidden, like the unreviewed-checklist count — so the gap between
    what exists and what may be shown is a number somebody can act on."""

    @property
    def found_nothing(self) -> bool:
        return self.available and not self.passages

    def render(self) -> str:
        if not self.available:
            return f"Search is unavailable: {self.reason}"
        if not self.passages:
            return (
                f"No approved procedure matches this. {self.unapproved_in_corpus} passage(s) "
                f"in the library are not approved and were not searched — this is not a "
                f"statement that no procedure exists."
            )
        return "\n\n".join(p.render() for p in self.passages)


class SopIndex:
    """Reads and writes the document store. `K1`'s engine."""

    def __init__(self, session: AsyncSession, embedder: Embedder) -> None:
        self._session = session
        self._embedder = embedder

    async def index(
        self,
        *,
        document: str,
        text: str,
        version: str = "",
        locator: str = "",
        kind: str = "sop",
        is_approved: bool = False,
        is_sample: bool = False,
    ) -> DocumentChunk:
        """Store one passage with its vector.

        `is_approved` defaults to `False` at both this call site and the column, deliberately:
        an SOP that becomes searchable merely by being ingested is one nobody approved.
        """
        embedding = await self._embedder.embed(text)
        chunk = DocumentChunk(
            document=document,
            version=version,
            locator=locator,
            text=text,
            embedding=list(embedding.vector),
            model=embedding.model,
            kind=kind,
            is_approved=is_approved,
            is_sample=is_sample,
        )
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def unapproved_count(self, kind: str | None = None) -> int:
        stmt = select(DocumentChunk).where(DocumentChunk.is_approved.is_(False))
        if kind:
            stmt = stmt.where(DocumentChunk.kind == kind)
        return len((await self._session.scalars(stmt)).all())

    async def search(
        self, question: str, *, kind: str | None = None, limit: int = DEFAULT_LIMIT
    ) -> SearchResult:
        """`K1`. Approved passages only, each carrying its citation."""
        try:
            query = await self._embedder.embed(question)
        except EmbeddingUnavailable as exc:
            return SearchResult(
                available=False,
                reason=(
                    f"{exc} Nothing was searched, so this is not a statement about what the "
                    f"library contains."
                ),
            )

        stmt = (
            select(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(list(query.vector)).label("distance"),
            )
            .where(DocumentChunk.is_approved.is_(True))
            .where(DocumentChunk.model == query.model)
            .order_by("distance")
            .limit(limit)
        )
        if kind:
            stmt = stmt.where(DocumentChunk.kind == kind)

        rows = (await self._session.execute(stmt)).all()
        return SearchResult(
            passages=tuple(
                Passage(
                    text=chunk.text,
                    citation=chunk.cite(),
                    document=chunk.document,
                    version=chunk.version,
                    locator=chunk.locator,
                    kind=chunk.kind,
                    is_sample=chunk.is_sample,
                    distance=float(distance),
                )
                for chunk, distance in rows
            ),
            unapproved_in_corpus=await self.unapproved_count(kind),
        )

    async def search_safety(self, question: str, limit: int = DEFAULT_LIMIT) -> SearchResult:
        """`S4`. **Never answered from model memory, and never from a manual.**

        Restricted to `kind="sop"` rather than merely preferring it. Widening the search until
        something comes back is how a plausible sentence becomes a safety instruction, and the
        honest output when nothing approved matches is a refusal that says so.
        """
        result = await self.search(question, kind="sop", limit=limit)
        if result.available and not result.passages:
            return SearchResult(
                available=True,
                unapproved_in_corpus=result.unapproved_in_corpus,
                reason=(
                    "no approved SOP covers this. A safety answer is never composed from "
                    "model memory or from a manufacturer's manual, so there is no answer to "
                    "give — ask the EHS owner."
                ),
            )
        return result
