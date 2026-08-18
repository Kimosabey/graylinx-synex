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

from app.db.knowledge import (
    ChunkApprovalEvent,
    DocumentChunk,
    DocumentRecord,
    add_chunk,
    approval_events,
    corpus_inventory,
    count_unapproved,
    delete_document,
    digest_of,
    ensure_knowledge_columns,
    nearest_approved,
    provisionally_approved_documents,
    record_approval_event,
    set_approval,
)
from app.db.knowledge import approved_documents as _approved_documents
from app.llm.embeddings import Embedder, EmbeddingInputTooLong, EmbeddingUnavailable
from app.retrieval.chunking import ChunkedDocument, chunk_document

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

    version_is_stated: bool = False
    """Whether the source document asserts a revision at all. Carried as its own fact rather
    than inferred from an empty string, so a consumer cannot read *"no version"* as *"version
    lost in transit"* — `K5` promises the document **and** the version, and the honest answer
    for a document that states none has to be sayable."""

    approval_is_provisional: bool = False
    """Approved by a persona pending SME validation (`RC2`), rather than by a refrigeration
    engineer. On the passage as well as inside `citation` because a surface may need to style
    it, and a fact only available by substring-matching a rendered string is one that gets
    matched wrongly — this repository has already been caught twice by containment."""

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


@dataclass(frozen=True)
class UnembeddablePassage:
    """A passage the store holds no vector for, and the reason in words.

    Named rather than counted, because "317 of 318" tells a reader something is missing and
    not which question it will fail to answer. This is the same treatment the nine withheld
    holding actions get — the corpus states its own gaps.
    """

    document: str
    locator: str
    chars: int
    reason: str

    def render(self) -> str:
        where = self.locator or "(no locator — before the first heading)"
        return f"{self.document} :: {where} — {self.chars} characters, not embedded. {self.reason}"


class SopIndex:
    """Reads and writes the document store. `K1`'s engine."""

    def __init__(self, session, embedder: Embedder) -> None:
        self._session = session
        self._embedder = embedder
        #: Passages this index refused to embed, in the order it met them. Public and mutable
        #: so an ingest run can report them; a private counter would make the gap a number
        #: nobody could name.
        self.unembeddable: list[UnembeddablePassage] = []

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
        source_digest: str = "",
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
            source_digest=source_digest,
        )
        return await add_chunk(self._session, chunk)

    async def index_document(
        self,
        *,
        document: str,
        text: str,
        version: str = "",
        kind: str = "sop",
        is_approved: bool = False,
        is_sample: bool = False,
        source_digest: str | None = None,
    ) -> tuple[ChunkedDocument, tuple[DocumentChunk, ...]]:
        """Split a document on its own structure, then store one row per passage.

        The route `index()` alone cannot take: a whole document is one vector and one citation
        that names no place inside it, which satisfies `K5`'s document-and-version half while
        destroying the `locator` that makes a citation checkable.

        Returns the chunking **alongside** the rows, because a caller needs to see what the
        splitter did and what it was worried about — an empty document stores nothing, an
        unstructured one stores a single passage that cites no section, and neither of those
        is visible from a row count.
        """
        chunked = chunk_document(text, document=document, version=version)
        digest = digest_of(text) if source_digest is None else source_digest

        # A passage the model refuses for its length is skipped and named — never allowed to
        # abandon the run. `replace_document` deletes before it writes, so an exception here
        # used to leave the store emptier than it found it: on 2026-08-18 one 13,284-character
        # preamble in the FDD specification took all 318 passages of the corpus with it, and
        # the reported reason said the embedder was unreachable while it was answering
        # normally. One unembeddable passage is a gap in one document; a raised exception here
        # is a deleted corpus, and those must not share a failure path.
        stored = []
        for chunk in chunked.chunks:
            arguments = chunk.index_arguments(document=document, version=version)
            try:
                stored.append(
                    await self.index(
                        **arguments,
                        kind=kind,
                        is_approved=is_approved,
                        is_sample=is_sample,
                        source_digest=digest,
                    )
                )
            except EmbeddingInputTooLong as refused:
                self.unembeddable.append(
                    UnembeddablePassage(
                        document=document,
                        locator=str(arguments.get("locator", "")),
                        chars=len(str(arguments.get("text", ""))),
                        reason=str(refused),
                    )
                )
        return chunked, tuple(stored)

    # ── the replace path, which is what makes an ingest re-runnable ────────────

    async def inventory(self, kind: str | None = None) -> tuple[DocumentRecord, ...]:
        """What the store already holds, per document. Read before anything is written."""
        return await corpus_inventory(self._session, kind)

    async def replace_document(
        self,
        *,
        document: str,
        text: str,
        version: str = "",
        kind: str = "sop",
        is_sample: bool = False,
    ) -> tuple[ChunkedDocument, tuple[DocumentChunk, ...], int]:
        """Delete this document's passages, then write the new ones. Returns what it removed.

        **Delete-then-insert rather than upsert, and the reason is the locator.** A document
        that gains a heading re-chunks into a different set of passages with different
        locators, so there is no key to update *against* — matching on `(document, locator)`
        would leave every passage whose heading changed behind as an orphan that still cites
        the document and no longer appears in it. The whole document is the unit.

        **Approval does not survive.** New rows are written unapproved, always, so a document
        whose text changed loses its approval rather than carrying it onto text nobody
        approved. That is the safe direction and a tedious one; `Q94` carries whether approval
        should be granted per passage or per document-and-version, and until it is answered the
        expensive error is the one that leaves an old approval attached to new instructions.

        Both halves run in the caller's session, so a failure rolls back to the old passages
        rather than leaving the document deleted and unwritten.
        """
        removed = await delete_document(self._session, document)
        chunked, stored = await self.index_document(
            document=document, text=text, version=version, kind=kind, is_sample=is_sample
        )
        return chunked, stored, removed

    # ── approval: a separate, attributed, reversible act ──────────────────────

    async def approve(
        self, document: str, *, actor: str, basis: str, provisional: bool = True
    ) -> ChunkApprovalEvent:
        """Make one document searchable, on somebody's authority, and record whose.

        `provisional` defaults to **True** and every caller in this repository leaves it there.
        A non-provisional approval is what the SME hour produces — a refrigeration engineer
        reading the content — and nothing reachable from a command line can produce that. The
        keyword exists so the state the review creates is expressible, not so a script can set
        it.
        """
        moved = await set_approval(
            self._session,
            document,
            approved=True,
            actor=actor,
            basis=basis,
            provisional=provisional,
        )
        return await record_approval_event(
            self._session,
            ChunkApprovalEvent(
                document=document,
                action="approve",
                actor=actor,
                basis=basis,
                is_provisional=provisional,
                passages=moved,
            ),
        )

    async def revoke(self, document: str, *, actor: str, reason: str) -> ChunkApprovalEvent:
        """Withdraw an approval. The row loses it; the trail keeps it.

        This is the act a real SME review performs on content a persona approved, so it takes
        an actor and a reason exactly as approving does — *"the software un-approved it"* is
        the same unanswerable sentence as *"the software decided"*.
        """
        moved = await set_approval(
            self._session, document, approved=False, actor=actor, basis=reason
        )
        return await record_approval_event(
            self._session,
            ChunkApprovalEvent(
                document=document,
                action="revoke",
                actor=actor,
                basis=reason,
                is_provisional=False,
                passages=moved,
            ),
        )

    async def provisional_documents(self) -> frozenset[str]:
        """Every document approved by a persona and validated by nobody. `RC2`'s worklist."""
        return await provisionally_approved_documents(self._session)

    async def approval_trail(self, document: str | None = None) -> tuple[ChunkApprovalEvent, ...]:
        return await approval_events(self._session, document)

    async def ensure_columns(self) -> tuple[str, ...]:
        """Additive migration for the columns this module added after the table shipped."""
        return await ensure_knowledge_columns(self._session)

    async def unapproved_count(self, kind: str | None = None) -> int:
        return await count_unapproved(self._session, kind)

    async def approved_documents(self, kind: str | None = None) -> frozenset[str]:
        """Which documents a search could reach. What `app/retrieval/quality.py` asks before
        it computes anything, so an empty corpus reports as an empty corpus rather than as a
        recall of zero."""
        return await _approved_documents(self._session, kind)

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

        rows = await nearest_approved(
            self._session, list(query.vector), query.model, kind, limit
        )
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
                    version_is_stated=chunk.version_is_stated,
                    approval_is_provisional=chunk.approval_is_provisional,
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
