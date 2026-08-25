"""`K1`/`K5` ingest — the job that gives retrieval a corpus, and leaves it unsearchable.

**The failure this prevents.** `synex_document_chunk` holds **zero rows**. Recall@k over an
empty table is not a low score, it is no measurement, and `app/retrieval/quality.py` and
`app/retrieval/chunking.py` were both built, tested and imported by nothing but their own test
files. That is the same defect this repository has now hit six times in one day: `RC18`'s
stored readings had no caller, the tool registry had none for a day, and `react.py`,
`context.py` and `app/eval/` have none now. A module a request never reaches is a module whose
first real input arrives in production.

So this job is the first caller of both. It walks the transcribed library —
`app/domain/library/` — splits each class on its own structure and writes one row per passage.

**After this job runs, search still returns nothing. That is the correct outcome, and a reader
who does not expect it will think the job failed.** Every chunk is written with
`is_approved=False`, and `SopIndex.search` returns approved chunks only. Nothing in the library
has been reviewed by a refrigeration engineer: 124 curated items across 11 fault classes, a
7-item generic fallback, 19 candidate causes and 19 discriminating questions, and **one review
pass of one class** has ever been run over the role tags — it found an oil analysis, a lab
task, being shown to whoever opened a compressor case. Inherited constraint 1 is that the
library is curated content and constraint 26 is that the language model never authors a field
instruction; the approval column is where both are enforced at retrieval. What changes today is
that the corpus becomes **measurable** — `evaluate()` can report *passages exist and none is
approved* instead of *there is no corpus* — without one unreviewed instruction becoming
retrievable. Those are two different states and `CorpusState` keeps them apart.

**Passages are not items, and the run reports both.** A class of thirteen items becomes four
passages: one for the class heading and its routing, one per stage it uses. A reader shown only
the row count would conclude nine items had been lost, and a reader shown only the item count
would think each item is separately retrievable. `IndexRun` carries `passages_stored` and
`items_indexed` as two numbers because they answer two questions.

**Holding actions are deliberately not indexed.** The nine drafted interim instructions in
`app/domain/library/holding_actions.py` sit behind **two** gates — `sme_reviewed` and
`switched_on` — and `DocumentChunk` has only one. Indexing them would let a single approval
open a policy gate that constraint 10 says a review does not clear, so an instruction that is
switched off as a matter of policy would become retrievable the day somebody approved the
passage. They are withheld, counted and reported by name rather than quietly skipped.

**Indexed as `kind="checklist"`, never as `sop`.** `S4` restricts safety retrieval to `sop`,
so tagging the library as an SOP would let a safety question be answered out of an unreviewed
checklist — which is the manufacturer's-manual failure `app/retrieval/sop.py` refuses, entering
through the ingest. `Q98` carries whether a differential deserves a kind of its own; a
discriminating question is not a checklist item, and both are shaped very differently.

**Re-running refuses rather than duplicating.** `synex_document_chunk` has no unique key on
`(document, locator)` and `app.db.knowledge` exposes no delete, so a second pass over a
populated table would write every passage twice — and a corpus with each passage duplicated
scores well on recall while being obviously broken. This is not `RC8`: reconciliation is
idempotent because the store makes it so, and nothing makes this one idempotent. So a second
run reports `ALREADY_INDEXED` with the count it found and indexes nothing. `Q97` carries the
replace path.

**Nothing here calls a model, and nothing here writes text.** Every line of every passage is
either a heading composed from a field the library already records — the class display, the
stage, the source file — or instruction text copied out of a `TranscribedItem` unchanged.
Arranging transcribed content into a document is not authoring one.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from app.config import Settings
from app.db.session import state_session
from app.domain.cases import Stage
from app.domain.differential import Differential, Effect, Question
from app.domain.library import (
    differentials,
    generic_fallback,
    holding_actions,
    measurement_faults,
    trained_model_classes,
)
from app.domain.library.curated import TranscribedItem
from app.llm.embeddings import Embedder
from app.retrieval.chunking import ChunkedDocument
from app.retrieval.quality import (
    NO_LABELLED_SET_YET,
    CorpusState,
    LabelledSet,
    RetrievalReport,
    corpus_state,
    evaluate,
)
from app.retrieval.sop import SearchResult, SopIndex

#: What every passage this job writes is tagged as. **Never `sop`** — see the module docstring.
INDEXED_KIND: str = "checklist"

#: `K5` wants a document **and a version**, and the review pack states none.
#:
#: TBD (Q96) — `05-checklist-library-for-review.md`, `06-differentials-for-review.md` and
#: `17-role-tags-every-check.md` carry no revision number, no date and no edition. An empty
#: string is the honest value: `DocumentChunk.cite` omits the version rather than printing one,
#: so a citation reads *"Checklist library — Compressor inefficiency · §Corrective actions"*
#: and asserts nothing about which revision it came from. Inventing `v1` here would make every
#: citation in the corpus name a version that does not exist.
LIBRARY_VERSION: str = ""

#: Section labels for the three checklist stages. Composed from the `Stage` enum so a heading
#: cannot drift from the value it names, and they are headings rather than instructions —
#: nothing a technician would act on is written in this file.
_STAGE_HEADINGS: dict[Stage, str] = {
    Stage.RCA: "Root cause analysis",
    Stage.CORRECTIVE: "Corrective actions",
    Stage.PREVENTIVE: "Preventive actions",
}


class RunOutcome(StrEnum):
    """What one pass did. Two, and neither of them is an error."""

    INDEXED = "indexed"
    """The corpus was empty and now holds the library. Still searchable by nobody."""

    ALREADY_INDEXED = "already_indexed"
    """A corpus was already there, so nothing was written. A refusal is not an error, and
    duplicating 131 passages would be the failure this refusal exists to avoid."""


class DocumentStore(Protocol):
    """What the ingest needs of an index, and nothing more.

    Structural rather than concrete for the same reason `ApprovedCorpus` is: the job's whole
    arithmetic — what was withheld, what was chunked, which of the three corpus states came
    out — has to be testable with Postgres stopped and the embedder unreachable.
    `app.retrieval.sop.SopIndex` satisfies it.
    """

    async def index_document(
        self,
        *,
        document: str,
        text: str,
        version: str = ...,
        kind: str = ...,
        is_approved: bool = ...,
        is_sample: bool = ...,
    ) -> tuple[ChunkedDocument, tuple[Any, ...]]: ...

    async def approved_documents(self, kind: str | None = ...) -> frozenset[str]: ...

    async def unapproved_count(self, kind: str | None = ...) -> int: ...

    async def search(
        self, question: str, *, kind: str | None = ..., limit: int = ...
    ) -> SearchResult: ...


@dataclass(frozen=True)
class LibraryDocument:
    """One document assembled out of transcribed content, before it is split.

    Carries its own counts because the passage count cannot be predicted from them: a class of
    thirteen items becomes three passages, one per stage, and a reader who saw only *"3 rows
    stored"* would think ten items had been lost.
    """

    title: str
    text: str
    source: str
    """The review-pack file and part every line of `text` was copied from, verbatim."""

    items: int = 0
    """Transcribed checklist items carried. Zero for a differential, which holds neither."""

    causes: int = 0
    questions: int = 0
    kind: str = INDEXED_KIND


@dataclass(frozen=True)
class WithheldContent:
    """Library content this job deliberately did not index, and why in words.

    A skipped section that says nothing is indistinguishable from a section the job failed to
    read. This is the same rule as `holding_actions.why_nothing_is_shown`, one layer out.
    """

    what: str
    count: int
    reason: str

    def render(self) -> str:
        return f"{self.count} × {self.what} withheld: {self.reason}"


@dataclass(frozen=True)
class DocumentOutcome:
    """What one document became. Reported whether or not anything was wrong with it."""

    document: str
    passages_stored: int
    items: int
    structure_found: bool
    reason: str
    """The splitter's own sentence about this document, carried through unchanged."""

    concerns: tuple[str, ...] = field(default_factory=tuple)
    held_as_text: tuple[str, ...] = field(default_factory=tuple)
    """Dotted numbers that could have opened a passage and were refused. Not concerns — the
    splitter holding `4.2 bar` inside its paragraph is the fix working."""

    def render(self) -> str:
        line = (
            f"{self.document}: {self.passages_stored} passage(s) from {self.items} "
            f"transcribed item(s) — {self.reason}"
        )
        if self.concerns:
            line = f"{line}\n    concerns: " + "; ".join(self.concerns)
        return line


@dataclass(frozen=True)
class IndexRun:
    """What one ingest did, what it refused, and what the corpus measures at afterwards."""

    outcome: RunOutcome
    reason: str
    documents: tuple[DocumentOutcome, ...]
    withheld: tuple[WithheldContent, ...]
    measurement: RetrievalReport
    ran_at: datetime

    @property
    def passages_stored(self) -> int:
        return sum(document.passages_stored for document in self.documents)

    @property
    def items_indexed(self) -> int:
        """Transcribed checklist items that reached a passage. Never the row count."""
        return sum(document.items for document in self.documents)

    @property
    def concerns(self) -> tuple[str, ...]:
        return tuple(concern for document in self.documents for concern in document.concerns)

    @property
    def held_as_text(self) -> tuple[str, ...]:
        return tuple(held for document in self.documents for held in document.held_as_text)

    @property
    def corpus_state(self) -> CorpusState:
        """Read off the measurement rather than recomputed, so the two can never disagree."""
        return self.measurement.corpus_state

    @property
    def searchable_statement(self) -> str:
        """**The sentence a reader needs most.** Without it, an empty search reads as a failed
        ingest, and somebody 'fixes' it by approving the library."""
        if self.corpus_state is CorpusState.APPROVED_AND_SEARCHABLE:
            return (
                f"{self.measurement.corpus_documents} document(s) in the corpus are approved "
                f"and reachable by search. Nothing in this job approves anything, so those "
                f"were approved elsewhere"
            )
        if self.corpus_state is CorpusState.EMPTY:
            return (
                "nothing is in the corpus, so search returns nothing and there is nothing to "
                "measure. That is an ingest that has not run, not an approval gate"
            )
        return (
            f"search still returns nothing, and that is correct: all "
            f"{self.measurement.unapproved_in_corpus} passage(s) are unapproved, because no "
            f"refrigeration engineer has read a line of this library. The corpus is now "
            f"measurable without one unreviewed instruction becoming retrievable"
        )

    def render(self) -> str:
        lines = [
            f"{self.ran_at:%Y-%m-%d %H:%M}: {self.outcome.value} — {self.reason}",
            self.searchable_statement,
            self.measurement.corpus_statement,
            self.measurement.recall_statement,
        ]
        lines.extend(f"  {document.render()}" for document in self.documents)
        lines.extend(f"  {item.render()}" for item in self.withheld)
        if self.held_as_text:
            lines.append(
                f"  {len(self.held_as_text)} dotted number(s) were held inside their own "
                f"paragraph rather than opening a passage; each says which rule held it"
            )
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reason": self.reason,
            "documents": len(self.documents),
            "passages_stored": self.passages_stored,
            "items_indexed": self.items_indexed,
            "withheld": [item.render() for item in self.withheld],
            "concerns": list(self.concerns),
            "dotted_numbers_held_as_text": list(self.held_as_text),
            "corpus_state": self.corpus_state.value,
            "searchable": self.searchable_statement,
            "measurement": self.measurement.as_dict(),
            "ran_at": self.ran_at.isoformat(),
            "rendered": self.render(),
        }


# ── assembling the documents ───────────────────────────────────────────────────────────────
# Every line below is either a heading built from a recorded field or text copied out of a
# transcribed object. Nothing is reworded, completed or explained, because an instruction this
# file authored would be indistinguishable from model output the moment it was retrieved —
# inherited constraints 1 and 26.


def _tags(item: TranscribedItem) -> str:
    """The item's own recorded tags, in words. Never a flag and never a bare dash."""
    parts = [f"capability: {item.capability.value}"]
    parts.append("blocking" if item.blocking else "not blocking")
    if item.settles_it is True:
        parts.append("marked [SETTLES IT] in the source")
    elif item.settles_it is None:
        parts.append("the document that carries the [SETTLES IT] marker does not cover it")
    if item.capability_defaulted:
        parts.append(
            "the source gave no role tag, so constraint 24's technician default applied"
        )
    return " · ".join(parts)


def _stage_section(
    heading: str, subject: str, items: Sequence[TranscribedItem], role_tag_file: str
) -> list[str]:
    """One stage as a passage: a lead-in that states provenance, then the items as steps.

    The lead-in is not decoration. `chunking` records a concern when a numbered list opens with
    no prose before it, because a step severed from the condition it applies under reads as
    complete — constraint 38 at ingest. These items are transcribed *with* their conditions in
    the text, and the lead-in is what says whose instructions they are and that nobody has
    checked them.
    """
    lines = [
        f"## {heading}",
        "",
        (
            f"The {len(items)} item(s) the review pack lists at this stage for {subject}, in "
            f"source order. Each carries the capability tagged in {role_tag_file} and whether "
            f"the pack marks it blocking. No refrigeration engineer has reviewed any of them, "
            f"so none of this is approved and none of it is retrievable."
        ),
        "",
    ]
    for position, item in enumerate(items, start=1):
        lines.append(f"{position}. {item.text} — {_tags(item)}")
        if item.source_note:
            lines.append(f"   Source note: {item.source_note}")
    lines.append("")
    return lines


def _checklist_document(
    *,
    title: str,
    display: str,
    label: str,
    severity_word: str,
    routing_05: str,
    routing_17: str,
    items: Sequence[TranscribedItem],
    source_file: str,
    source_part: str,
    role_tag_file: str,
) -> LibraryDocument:
    """One fault class as one document, one passage per stage.

    Per stage rather than per item, deliberately. An item retrieved alone loses the class it
    belongs to and the stage it sits at, which is the citation-with-no-address failure
    `chunking` exists to prevent; a stage is small enough to read whole and large enough to
    place. The four `Stage` values a class does not use produce no section at all rather than
    an empty one, because an empty section would index as a passage citing nothing.
    """
    routing = routing_17 or (
        f"{role_tag_file} prints no routing for this class, which is a different fact from it "
        f"agreeing with the text source"
    )
    lines = [
        f"# {display}",
        "",
        (
            f"Fault label {label}. Severity as the source writes it: {severity_word}. "
            f"Routing per {source_file}: {routing_05}. Routing per {role_tag_file}: {routing}."
        ),
        "",
        (
            f"Transcribed verbatim from {source_file} · {source_part} · “{display}”. "
            f"{len(items)} item(s), none of them reviewed."
        ),
        "",
    ]
    for stage, heading in _STAGE_HEADINGS.items():
        at_stage = [item for item in items if item.stage is stage]
        if at_stage:
            lines.extend(_stage_section(heading, display, at_stage, role_tag_file))

    return LibraryDocument(
        title=title,
        text="\n".join(lines),
        source=f"{source_file} · {source_part}",
        items=len(items),
    )


def _trained_model_documents() -> tuple[LibraryDocument, ...]:
    """The seven classes the trained model reports — 86 of the 124 curated items."""
    return tuple(
        _checklist_document(
            title=f"Checklist library — {fault_class.display}",
            display=fault_class.display,
            label=fault_class.label,
            severity_word=fault_class.severity_word,
            routing_05=fault_class.routing_05,
            routing_17=fault_class.routing_17,
            items=fault_class.items,
            source_file=trained_model_classes.TEXT_SOURCE,
            source_part=trained_model_classes.PART,
            role_tag_file=trained_model_classes.ROLE_TAG_SOURCE,
        )
        for fault_class in trained_model_classes.TRAINED_MODEL_CLASSES
    )


def _measurement_fault_documents() -> tuple[LibraryDocument, ...]:
    """The four classes our own arithmetic raises — the remaining 38 curated items.

    Their two sources contradict each other on routing, and both statements are carried into
    the passage rather than one being chosen. A resolved contradiction is a judgement, and this
    file is not entitled to make one.
    """
    return tuple(
        _checklist_document(
            title=f"Checklist library — {fault.display}",
            display=fault.display,
            label=fault.label,
            severity_word=fault.severity_word,
            routing_05=fault.routing_05,
            routing_17=fault.routing_17,
            items=fault.items,
            source_file=measurement_faults.TEXT_SOURCE,
            source_part=measurement_faults.PART,
            role_tag_file=measurement_faults.ROLE_TAG_SOURCE,
        )
        for fault in measurement_faults.MEASUREMENT_FAULTS
    )


def _fallback_document() -> LibraryDocument:
    """The 7 items attached to no fault class.

    A document of its own rather than a section of one, because that is what the seven are:
    `124 + 7`, not `131 across 11 classes` — folding them into a per-class total makes every
    per-class figure wrong by seven, which is `generic_fallback.count_note()`'s whole point.
    """
    lines = [
        f"# {generic_fallback.PART}",
        "",
        (
            f"{generic_fallback.count_note()} These items belong to no fault class, so they "
            f"carry no fault label. {generic_fallback.OPEN_REVIEW_QUESTION}"
        ),
        "",
    ]
    for stage, heading in _STAGE_HEADINGS.items():
        at_stage = [item for item in generic_fallback.FALLBACK_ITEMS if item.stage is stage]
        if at_stage:
            lines.extend(
                _stage_section(
                    heading,
                    "content attached to no fault class",
                    at_stage,
                    generic_fallback.SOURCE,
                )
            )

    return LibraryDocument(
        title="Checklist library — generic fallback",
        text="\n".join(lines),
        source=f"{generic_fallback.SOURCE} · {generic_fallback.PART}",
        items=len(generic_fallback.FALLBACK_ITEMS),
    )


def _answer_effects(question: Question, differential: Differential) -> list[str]:
    """One line per answer, naming the causes it moves by their text rather than their id.

    *Can't tell* is printed with its emptiness spelt out. Constraint 30 says it must have no
    effect at all, and a passage that simply omitted it would read as though the question
    forces a guess.
    """
    by_id = {cause.id: cause.text for cause in differential.causes}
    lines = []
    for answer in question.answers:
        if not answer.effects:
            lines.append(f"- {answer.text} — no effect on any cause, deliberately")
            continue
        grouped = []
        for effect in (Effect.CONFIRM, Effect.ELIMINATE, Effect.KEEP):
            named = [
                by_id.get(cause_id, cause_id)
                for cause_id, applied in answer.effects.items()
                if applied is effect
            ]
            if named:
                grouped.append(f"{effect.value}s: {'; '.join(named)}")
        lines.append(f"- {answer.text} — {' · '.join(grouped)}")
    return lines


def _differential_documents() -> tuple[LibraryDocument, ...]:
    """The four differentials — 19 causes and 19 discriminating questions.

    Only the four classes the trained model declares undecidable have one, and that is
    constraint 27: narrowing a class that already names a mechanism would invent ambiguity the
    model never reported. `REFRIGERANT_SIDE_HIGH_HEAD` has none, and nothing here fills it.

    This is the highest-risk content in the programme — elimination is irreversible and nobody
    re-examines a settled question — which makes it the content most worth having a citation
    for, and the content that must stay unapproved longest.
    """
    documents = []
    for label, differential in differentials.LIBRARY.items():
        transcribed = trained_model_classes.by_label(label)
        display = transcribed.display if transcribed else label
        lines = [
            f"# Differential — {display}",
            "",
            (
                f"Fault label {label}. {len(differential.causes)} candidate cause(s) and "
                f"{len(differential.questions)} discriminating question(s), transcribed "
                f"verbatim from {differential.source}. Not one has been reviewed, so "
                f"Differential.askable returns nothing and no elimination can reach a user."
            ),
            "",
            "## Candidate causes",
            "",
            (
                "The causes the source lists for this class, in its order. An elimination is "
                "irreversible, so a cause ruled out here is never revisited."
            ),
            "",
        ]
        lines.extend(f"- {cause.text}" for cause in differential.causes)
        lines.append("")
        for question in differential.questions:
            lines.extend(
                [
                    f"## Question {question.id}",
                    "",
                    question.text,
                    "",
                    (
                        f"Asked of: {question.capability.value}. Source: {question.source}. "
                        f"Unreviewed, so it is never asked."
                    ),
                    "",
                ]
            )
            lines.extend(_answer_effects(question, differential))
            lines.append("")
        documents.append(
            LibraryDocument(
                title=f"Differential — {display}",
                text="\n".join(lines),
                source=differential.source,
                causes=len(differential.causes),
                questions=len(differential.questions),
            )
        )
    return tuple(documents)


def library_documents() -> tuple[LibraryDocument, ...]:
    """Everything this job indexes, in the order the review pack presents it."""
    return (
        *_trained_model_documents(),
        *_measurement_fault_documents(),
        _fallback_document(),
        *_differential_documents(),
    )


def withheld_content() -> tuple[WithheldContent, ...]:
    """Library content that exists, is not indexed, and says why.

    One entry today, and it is a policy decision rather than an oversight — see the module
    docstring. Reported on every run, including when nothing changed, for the same reason
    `reconcile.py` reports `detected_but_not_queued` when it is zero: a job that only speaks up
    when something is wrong is indistinguishable from one that has stopped running.
    """
    return (
        WithheldContent(
            what="drafted interim holding action",
            count=len(holding_actions.DRAFTED_HOLDING_ACTIONS),
            reason=(
                f"each sits behind two gates — sme_reviewed and switched_on — and "
                f"synex_document_chunk has one. Constraint 10: an unreviewed holding "
                f"instruction is worse than none, and the source's own state is "
                f"'{holding_actions.CURRENT_STATE}'. Indexing them would let a single "
                f"approval open a policy gate that the review deliberately does not clear"
            ),
        ),
    )


# ── the run ────────────────────────────────────────────────────────────────────────────────


async def index_and_measure(
    store: DocumentStore,
    *,
    documents: Sequence[LibraryDocument] | None = None,
    labelled: LabelledSet = NO_LABELLED_SET_YET,
    now: datetime | None = None,
) -> IndexRun:
    """Index the library if the corpus is empty, then measure the corpus either way.

    **The measurement runs on both paths deliberately.** A refusal that reported nothing about
    the corpus would leave the operator with a job that says *"already indexed"* and no way to
    tell whether what is in there is the library, half the library, or something else entirely.

    Takes a `DocumentStore` rather than a `Settings` so the arithmetic is testable with
    Postgres stopped and the embedder unreachable — the property every other gate here holds.
    """
    moment = now or datetime.now().astimezone()
    before = await corpus_state(store, INDEXED_KIND)

    if before is not CorpusState.EMPTY:
        return IndexRun(
            outcome=RunOutcome.ALREADY_INDEXED,
            reason=(
                "a corpus is already present, so nothing was written. synex_document_chunk has "
                "no unique key on (document, locator) and app.db.knowledge exposes no delete, "
                "so a second pass would store every passage twice rather than replace it — and "
                "a duplicated corpus scores well on recall while being plainly broken. This is "
                "a refusal, not an error; Q97 carries the replace path"
            ),
            documents=(),
            withheld=withheld_content(),
            measurement=await evaluate(store, labelled, kind=INDEXED_KIND),
            ran_at=moment,
        )

    to_index = library_documents() if documents is None else tuple(documents)
    outcomes: list[DocumentOutcome] = []
    for document in to_index:
        # `is_approved` is never passed. It defaults to False at this call site and at the
        # column, and a keyword here would be the one line a future edit could use to make the
        # whole unreviewed library retrievable.
        chunked, stored = await store.index_document(
            document=document.title,
            text=document.text,
            version=LIBRARY_VERSION,
            kind=document.kind,
        )
        outcomes.append(
            DocumentOutcome(
                document=document.title,
                passages_stored=len(stored),
                items=document.items,
                structure_found=chunked.structure_found,
                reason=chunked.reason,
                concerns=chunked.concerns,
                held_as_text=chunked.dotted_numbers_held_as_text,
            )
        )

    return IndexRun(
        outcome=RunOutcome.INDEXED,
        reason=(
            f"{sum(o.passages_stored for o in outcomes)} passage(s) written from "
            f"{len(outcomes)} document(s), every one of them unapproved"
        ),
        documents=tuple(outcomes),
        withheld=withheld_content(),
        measurement=await evaluate(store, labelled, kind=INDEXED_KIND),
        ran_at=moment,
    )


async def index_library(settings: Settings, now: datetime | None = None) -> IndexRun:
    """One pass against the real store. Writes only to Synex's own Postgres.

    The embedder is `nomic-embed-text` at 274 MB on the host CPU, so this runs with the Jarvis
    box terminated — `CONTEXT.md` §4 has always said embeddings are local, and the session that
    recorded 'RAG needs the GPU' as a blocker had never started the thing.
    """
    async with state_session(settings) as session:
        return await index_and_measure(
            SopIndex(session, Embedder(settings.embed_host)), now=now
        )


# ── the arq worker ─────────────────────────────────────────────────────────────────────────
# `arq` rather than a script for the same reason `reconcile.py` gives: the job must run in the
# same process model as the application, with the same settings and connection handling.
#
# **No cron entry, and that is the difference from `reconcile.py`.** Reconciliation runs every
# fifteen minutes because a re-run is free and the cost of running too rarely is twenty-two
# episodes outside the queue. This one refuses on a populated corpus, so a schedule would
# report ALREADY_INDEXED for ever and teach whoever reads the log to ignore it. The library
# changes when a human edits the transcription, so a human enqueues the job.


async def index_library_job(ctx: dict) -> dict:
    """The arq entry point. Returns the run so it lands in the job result."""
    settings: Settings = ctx.get("settings") or Settings()
    return (await index_library(settings)).as_dict()


async def _startup(ctx: dict) -> None:
    ctx["settings"] = Settings()


class WorkerSettings:
    """`arq` worker configuration. Run with `arq app.jobs.index_library.WorkerSettings`.

    A class rather than an object assembled at import, so importing this module — which the
    tests do — never opens a Redis connection.
    """

    functions = [index_library_job]  # noqa: RUF012 — arq reads these as plain class attributes
    on_startup = _startup

    @staticmethod
    def redis_settings():
        """Built lazily so `arq` is not imported unless a worker is actually started."""
        from arq.connections import RedisSettings  # noqa: PLC0415 — see above

        return RedisSettings.from_dsn(Settings().redis_url)


def main() -> None:
    """`python -m app.jobs.index_library`. The path a person at a terminal takes.

    Prints the run rather than returning a count, because the number a reader needs is not how
    many rows were written — it is the sentence saying that search still returns nothing and
    that this is correct.
    """
    print(asyncio.run(index_library(Settings())).render())


if __name__ == "__main__":
    main()
