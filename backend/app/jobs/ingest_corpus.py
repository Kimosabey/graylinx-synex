"""The writer `synex_document_chunk` never had — idempotent, attributed, and approving nothing.

**The defect this closes.** `app/db/knowledge.py` defines the table and the cosine search,
`app/retrieval/chunking.py` splits documents, `app/retrieval/sop.py` searches, and
`app/llm/embeddings.py` embeds. Every piece existed and the corpus held only what
`app/jobs/index_library.py` put there — the checklist library, and nothing else. The written
chapters and the FDD specification, which are the documents `K5` describes when it says *every
important answer names its document and version*, had no producer at all. This repository keeps
finding machinery with no consumer; this was the inversion, a consumer with no producer.

**Idempotency, stated rather than claimed.** `index_library` had to *refuse* a second run,
because `synex_document_chunk` carried no key on which two ingests of the same document could
be compared and a re-run would have written every passage twice. `Q97` asked for the replace
path and this is it: `DocumentChunk.source_digest` holds the SHA-256 of the whole source text,
repeated on every passage of that document, so a second run reads the inventory first and each
document lands in exactly one of three outcomes —

| Outcome | When | What is written |
|---|---|---|
| `INGESTED` | the store holds no passage of this document | its passages |
| `UNCHANGED` | the store holds it and the digests match | **nothing at all** |
| `REPLACED` | the digests differ, or the stored digest is unknown | its old passages are
  deleted and the new ones written, in one transaction |

An unknown digest — a row written before that column existed — is treated as `REPLACED` rather
than `UNCHANGED`, because *"we cannot tell whether this is current"* and *"this is current"* are
different facts and only one of them is safe to act on.

**Approval is not part of ingest, and that is the product decision this file carries.**
`is_approved` defaults `False` at the column and at the call site, and nothing in the ingest
path can set it — `index_arguments` cannot express it and `ingest()` takes no keyword for it. So
a straight run leaves the whole corpus invisible to search, which is correct and looks broken.
The two obvious repairs are both wrong: leaving it there means `K1` and `K5` cannot be
demonstrated at all, and flipping everything to approved would put content directing physical
work in front of a technician on nobody's authority — inherited constraint 1 exists because an
unapproved procedure caused a real incident.

So approval is a **separate, attributed, reversible act** with its own command and its own
audit row: `approve()` records who, when, on what basis, and that the approval is
**provisional — pending SME validation** (`RC2`). The provisional state travels into
`DocumentChunk.cite`, so a passage that reaches an answer says on its face that a persona
approved it and an engineer has not. `revoke()` undoes it and the `ChunkApprovalEvent` survives
the undoing, so the SME hour can find every provisional approval, read what was claimed for it,
and withdraw it. `Q105` carries the question; `D-018` carries the decision.

**Nothing here calls a model.** Chunking is arithmetic over text, embedding is
`nomic-embed-text` on the host CPU, and neither decides what a passage says. The Jarvis box is
not involved and is not needed.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from app.config import Settings
from app.db.knowledge import DocumentRecord
from app.db.session import create_state_schema, state_session
from app.jobs.corpus import Discovery, RefusedSource, SourceDocument, discover
from app.jobs.index_library import (
    INDEXED_KIND as LIBRARY_KIND,
)
from app.jobs.index_library import (
    LIBRARY_VERSION,
    library_documents,
)
from app.llm.embeddings import Embedder
from app.retrieval.chunking import ChunkedDocument
from app.retrieval.quality import (
    NO_LABELLED_SET_YET,
    CorpusState,
    LabelledSet,
    RetrievalReport,
    evaluate,
)
from app.retrieval.sop import SopIndex

# `LIBRARY_KIND` and `LIBRARY_VERSION` are re-used from `app/jobs/index_library.py` rather than
# restated. Two constants that must agree is how a corpus grows a body nothing can find — the
# library is written as `checklist` because `S4` restricts safety retrieval to `sop`, and it
# carries no version because the review pack states none (`Q96`).


class Outcome(StrEnum):
    """What happened to one document. Three, and the third is the one that makes a re-run safe."""

    INGESTED = "ingested"
    """The store held no passage of this document."""

    UNCHANGED = "unchanged"
    """The store holds it and the source text has not changed, so nothing was written. Not a
    skip and not a failure — it is the ingest confirming the corpus is current."""

    REPLACED = "replaced"
    """The source text changed, or the stored digest is unknown. Every passage of the document
    was deleted and rewritten, and **its approval was not carried across**: new text nobody
    approved must not inherit an approval granted for old text."""

    UNREADABLE = "unreadable"
    """The document could not be read. Reported by name, never dropped — a corpus missing a
    document it believes it holds answers confidently out of what is left."""


@dataclass(frozen=True)
class DocumentOutcome:
    """What one document became, with the reason attached whether or not anything happened."""

    document: str
    outcome: Outcome
    kind: str
    version: str
    origin: str
    passages_written: int = 0
    passages_removed: int = 0
    reason: str = ""
    concerns: tuple[str, ...] = field(default_factory=tuple)
    held_as_text: tuple[str, ...] = field(default_factory=tuple)
    structure_found: bool = False

    @property
    def version_is_stated(self) -> bool:
        return bool(self.version.strip())

    def render(self) -> str:
        version = f"v{self.version}" if self.version_is_stated else "version not stated"
        line = (
            f"{self.outcome.value:<10} {self.document} ({version}, {self.kind}) — "
            f"{self.passages_written} passage(s) written"
        )
        if self.passages_removed:
            line = f"{line}, {self.passages_removed} replaced"
        if self.reason:
            line = f"{line} — {self.reason}"
        if self.concerns:
            line = f"{line}\n    concerns: " + "; ".join(self.concerns)
        return line


@dataclass(frozen=True)
class CorpusRun:
    """One ingest pass: what changed, what did not, what was refused, and what search can see."""

    documents: tuple[DocumentOutcome, ...]
    refused: tuple[RefusedSource, ...]
    measurement: RetrievalReport
    ran_at: datetime
    embedding_seconds: float = 0.0
    """Wall clock across the whole write. Measured, never estimated — it is the number that
    decides whether an ingest is something a person waits for or something they schedule."""

    def counted(self, outcome: Outcome) -> int:
        return sum(1 for document in self.documents if document.outcome is outcome)

    @property
    def passages_written(self) -> int:
        return sum(document.passages_written for document in self.documents)

    @property
    def passages_removed(self) -> int:
        return sum(document.passages_removed for document in self.documents)

    @property
    def concerns(self) -> tuple[str, ...]:
        return tuple(
            f"{document.document}: {concern}"
            for document in self.documents
            for concern in document.concerns
        )

    @property
    def held_as_text(self) -> tuple[str, ...]:
        return tuple(
            held for document in self.documents for held in document.held_as_text
        )

    @property
    def documents_without_a_stated_version(self) -> tuple[str, ...]:
        """Which citations will read `version not stated`. **Reported, not hidden.**

        A reader who does not know this is coming reads the phrase as a bug. It is a property
        of the documents: the review pack, the FDD specification and the four architecture
        chapters written directly carry no revision number between them, and `Q96` is where
        that stops being true.
        """
        return tuple(
            document.document
            for document in self.documents
            if not document.version_is_stated and document.outcome is not Outcome.UNREADABLE
        )

    @property
    def corpus_state(self) -> CorpusState:
        return self.measurement.corpus_state

    @property
    def is_idempotent_so_far(self) -> bool:
        """True when this run wrote nothing, which is what a second run over an unchanged
        repository must be. Named as a property so a test asserts the claim rather than a
        count that happens to be zero for some other reason."""
        return self.passages_written == 0 and self.passages_removed == 0

    @property
    def searchable_statement(self) -> str:
        """**The sentence a reader needs most**, for the same reason `index_library` needs one:
        without it an empty search reads as a failed ingest, and the obvious repair is to
        approve content no refrigeration engineer has read."""
        if self.corpus_state is CorpusState.EMPTY:
            return (
                "nothing is in the corpus, so search returns nothing and there is nothing to "
                "measure. That is an ingest that has not run rather than an approval gate"
            )
        if self.corpus_state is CorpusState.NOTHING_APPROVED:
            return (
                f"search still returns nothing, and that is correct: all "
                f"{self.measurement.unapproved_in_corpus} passage(s) are unapproved. Nothing "
                f"in an ingest can approve anything — approval is a separate act with a named "
                f"actor, and it is reversible (see --approve and --revoke)"
            )
        return (
            f"{self.measurement.corpus_documents} document(s) are approved and reachable by "
            f"search. Nothing in this run approved them; check the approval trail for who did "
            f"and whether it is still pending SME validation"
        )

    def render(self) -> str:
        lines = [
            f"{self.ran_at:%Y-%m-%d %H:%M} — {len(self.documents)} document(s): "
            f"{self.counted(Outcome.INGESTED)} ingested, "
            f"{self.counted(Outcome.REPLACED)} replaced, "
            f"{self.counted(Outcome.UNCHANGED)} unchanged, "
            f"{self.counted(Outcome.UNREADABLE)} unreadable",
            f"{self.passages_written} passage(s) written in "
            f"{self.embedding_seconds:.1f}s of embedding",
            self.searchable_statement,
            self.measurement.corpus_statement,
        ]
        lines.extend(f"  {document.render()}" for document in self.documents)
        lines.extend(f"  {refusal.render()}" for refusal in self.refused)
        if self.documents_without_a_stated_version:
            lines.append(
                f"  {len(self.documents_without_a_stated_version)} document(s) state no "
                f"version, so their citations read 'version not stated' rather than omitting "
                f"it (Q96): "
                + ", ".join(self.documents_without_a_stated_version)
            )
        if self.held_as_text:
            lines.append(
                f"  {len(self.held_as_text)} dotted number(s) were held inside their own "
                f"paragraph rather than opening a passage; each says which rule held it"
            )
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ran_at": self.ran_at.isoformat(),
            "documents": len(self.documents),
            "ingested": self.counted(Outcome.INGESTED),
            "replaced": self.counted(Outcome.REPLACED),
            "unchanged": self.counted(Outcome.UNCHANGED),
            "unreadable": self.counted(Outcome.UNREADABLE),
            "passages_written": self.passages_written,
            "passages_removed": self.passages_removed,
            "embedding_seconds": round(self.embedding_seconds, 2),
            "corpus_state": self.corpus_state.value,
            "searchable": self.searchable_statement,
            "documents_without_a_stated_version": list(
                self.documents_without_a_stated_version
            ),
            "refused": [refusal.render() for refusal in self.refused],
            "concerns": list(self.concerns),
            "measurement": self.measurement.as_dict(),
            "rendered": self.render(),
        }


class CorpusStore(Protocol):
    """What the ingest needs of an index, and nothing more.

    Structural rather than concrete, like `index_library.DocumentStore`, so the whole
    arithmetic — which documents changed, what was replaced, which corpus state came out — is
    testable with Postgres stopped and the embedder unreachable. `app.retrieval.sop.SopIndex`
    satisfies it, and a test compares the two signatures rather than trusting that.
    """

    async def inventory(self, kind: str | None = ...) -> tuple[DocumentRecord, ...]: ...

    async def index_document(
        self,
        *,
        document: str,
        text: str,
        version: str = ...,
        kind: str = ...,
        is_approved: bool = ...,
        is_sample: bool = ...,
        source_digest: str | None = ...,
    ) -> tuple[ChunkedDocument, tuple[Any, ...]]: ...

    async def replace_document(
        self,
        *,
        document: str,
        text: str,
        version: str = ...,
        kind: str = ...,
        is_sample: bool = ...,
    ) -> tuple[ChunkedDocument, tuple[Any, ...], int]: ...

    async def approved_documents(self, kind: str | None = ...) -> frozenset[str]: ...

    async def unapproved_count(self, kind: str | None = ...) -> int: ...

    async def search(self, question: str, *, kind: str | None = ..., limit: int = ...): ...


# ── assembling every body of the corpus into one list ─────────────────────────


def library_sources() -> tuple[SourceDocument, ...]:
    """The transcribed checklist library, in the shape this job ingests.

    Reuses `index_library.library_documents()` rather than re-assembling the text, because two
    transcriptions of 131 curated items is exactly the second source of truth §2.8 forbids —
    and the one that would diverge silently, since both would look right in isolation.
    """
    return tuple(
        SourceDocument(
            title=document.title,
            text=document.text,
            kind=LIBRARY_KIND,
            origin=document.source,
            version=LIBRARY_VERSION,
        )
        for document in library_documents()
    )


def all_sources(repo_root: Path) -> Discovery:
    """Every body of the corpus: the written chapters, the FDD specification, the library."""
    found = discover(repo_root)
    return Discovery(
        documents=(*found.documents, *library_sources()),
        refused=found.refused,
        unreadable=found.unreadable,
    )


# ── the run ───────────────────────────────────────────────────────────────────


def _decide(document: SourceDocument, held: DocumentRecord | None) -> tuple[Outcome, str]:
    """One document against what the store already holds. The whole of idempotency."""
    if held is None:
        return Outcome.INGESTED, "the store held no passage of this document"
    if not held.digest_is_known:
        return Outcome.REPLACED, (
            f"the {held.passages} stored passage(s) carry no source digest, so whether they "
            f"match this document cannot be answered — replaced rather than assumed current"
        )
    if held.source_digest == document.digest:
        return Outcome.UNCHANGED, (
            f"the {held.passages} stored passage(s) carry this document's digest, so the "
            f"source has not changed and nothing was rewritten"
        )
    return Outcome.REPLACED, (
        f"the source text changed — the stored digest is {held.source_digest[:12]}… and this "
        f"document is {document.digest[:12]}… — so its {held.passages} passage(s) were "
        f"deleted and rewritten, and its approval was not carried across"
    )


async def ingest(
    store: CorpusStore,
    documents: Sequence[SourceDocument],
    *,
    refused: Sequence[RefusedSource] = (),
    unreadable: Sequence[str] = (),
    labelled: LabelledSet = NO_LABELLED_SET_YET,
    now: datetime | None = None,
    clock=None,
) -> CorpusRun:
    """Write every document that is new or changed, leave every one that is not, then measure.

    **Nothing in this signature can approve anything**, and that is the point rather than an
    omission. There is no `is_approved` keyword to pass, no default to override and no flag a
    future edit could reach for — approving is `SopIndex.approve`, which demands an actor and a
    basis in words and writes an audit row.

    `clock` is injectable so the elapsed figure is measurable in a test rather than asserted
    about a real wall clock; it defaults to the real one.
    """
    import time  # noqa: PLC0415 — local so the module imports with nothing running

    tick = clock or time.monotonic
    moment = now or datetime.now().astimezone()
    held = {record.document: record for record in await store.inventory()}

    outcomes: list[DocumentOutcome] = []
    started = tick()

    for document in documents:
        decision, reason = _decide(document, held.get(document.title))
        if decision is Outcome.UNCHANGED:
            outcomes.append(
                DocumentOutcome(
                    document=document.title,
                    outcome=decision,
                    kind=document.kind,
                    version=document.version,
                    origin=document.origin,
                    reason=reason,
                )
            )
            continue

        removed = 0
        if decision is Outcome.REPLACED:
            chunked, stored, removed = await store.replace_document(
                document=document.title,
                text=document.text,
                version=document.version,
                kind=document.kind,
            )
        else:
            chunked, stored = await store.index_document(
                document=document.title,
                text=document.text,
                version=document.version,
                kind=document.kind,
                source_digest=document.digest,
            )
        outcomes.append(
            DocumentOutcome(
                document=document.title,
                outcome=decision,
                kind=document.kind,
                version=document.version,
                origin=document.origin,
                passages_written=len(stored),
                passages_removed=removed,
                reason=f"{reason}. {chunked.reason}",
                concerns=chunked.concerns,
                held_as_text=chunked.dotted_numbers_held_as_text,
                structure_found=chunked.structure_found,
            )
        )

    elapsed = tick() - started

    outcomes.extend(
        DocumentOutcome(
            document=problem,
            outcome=Outcome.UNREADABLE,
            kind="",
            version="",
            origin=problem,
            reason=(
                "this source was meant to be ingested and could not be read. It is named "
                "rather than dropped, because a corpus missing a document it believes it "
                "holds answers confidently out of what is left"
            ),
        )
        for problem in unreadable
    )

    return CorpusRun(
        documents=tuple(outcomes),
        refused=tuple(refused),
        measurement=await evaluate(store, labelled),
        ran_at=moment,
        embedding_seconds=elapsed,
    )


async def ingest_corpus(
    settings: Settings, repo_root: Path, now: datetime | None = None
) -> CorpusRun:
    """One pass against the real store. Writes only to Synex's own Postgres.

    The embedder is `nomic-embed-text` on the host CPU, so this runs with the Jarvis box
    terminated — `CONTEXT.md` §4 has always said embeddings are local.
    """
    await create_state_schema(settings)
    found = all_sources(repo_root)
    async with state_session(settings) as session:
        index = SopIndex(session, Embedder(settings.embed_host))
        await index.ensure_columns()
        return await ingest(
            index,
            found.documents,
            refused=found.refused,
            unreadable=found.unreadable,
            now=now,
        )


async def ingest_corpus_job(ctx: dict) -> dict:
    """The arq entry point, for the day this is scheduled rather than run by hand.

    Unlike `index_library`, this job **is** safe to schedule: it refuses nothing, writes only
    what changed, and a run over an unchanged repository is a handful of `SELECT`s. Nothing
    schedules it today because the corpus changes when a human edits a document.
    """
    settings: Settings = ctx.get("settings") or Settings()
    root: Path = ctx.get("repo_root") or Path(__file__).resolve().parents[3]
    return (await ingest_corpus(settings, root)).as_dict()


def main() -> None:
    """`python -m app.jobs.ingest_corpus`. `scripts/ingest_corpus.py` is the fuller door."""
    root = Path(__file__).resolve().parents[3]
    print(asyncio.run(ingest_corpus(Settings(), root)).render())


if __name__ == "__main__":
    main()
