"""The library ingest — and the three things it must never quietly get right.

`synex_document_chunk` held **zero rows**, so `app/retrieval/quality.py` and
`app/retrieval/chunking.py` were both built, tested and imported by nothing but their own test
files. This job is their first caller, which makes these tests the first place the two are
exercised against the content they were written for: 124 curated items across 11 fault classes,
a 7-item generic fallback, 19 candidate causes and 19 discriminating questions.

Three properties carry the whole file, and each is a defect this repository has already shipped
once:

* **nothing becomes retrievable.** Every passage is written unapproved, so search returns
  nothing after a successful ingest. A reader who expects otherwise will "fix" it by approving
  124 instructions no refrigeration engineer has read;
* **a second run refuses rather than duplicating**, because nothing makes this job idempotent
  and a doubled corpus scores well on recall while being plainly broken;
* **empty, unapproved and searchable are three states**, and the job reports which one the
  corpus is in on every path — including the refusal.

All of it runs with Postgres stopped, the embedder unreachable and the Jarvis box terminated.
"""
from __future__ import annotations

import inspect

import pytest

from app.domain.library import (
    differentials,
    generic_fallback,
    holding_actions,
    measurement_faults,
    trained_model_classes,
)
from app.jobs.index_library import (
    INDEXED_KIND,
    LIBRARY_VERSION,
    DocumentStore,
    IndexRun,
    LibraryDocument,
    RunOutcome,
    index_and_measure,
    library_documents,
    withheld_content,
)
from app.retrieval.chunking import chunk_document
from app.retrieval.quality import (
    CorpusState,
    LabelledQuestion,
    LabelledSet,
    Verdict,
)
from app.retrieval.sop import DEFAULT_LIMIT, Passage, SearchResult


class _FakeStore:
    """A store that chunks for real and stores in a list.

    The splitter is deliberately *not* stubbed: half the point of this job is that the library
    survives `chunk_document`, and a fake that returned one passage per document would pass
    while a checklist was being severed. Only the driver and the embedder are absent.
    """

    def __init__(self, approved: frozenset[str] = frozenset()) -> None:
        self.rows: list[tuple[str, str, bool, str]] = []
        self.approved = approved
        self.searches: list[tuple[str, str | None, int]] = []

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
    ):
        chunked = chunk_document(text, document=document, version=version)
        for chunk in chunked.chunks:
            self.rows.append((document, chunk.locator, is_approved, kind))
        return chunked, tuple(chunked.chunks)

    async def approved_documents(self, kind: str | None = None) -> frozenset[str]:
        return self.approved

    async def unapproved_count(self, kind: str | None = None) -> int:
        return sum(1 for _, _, is_approved, _ in self.rows if not is_approved)

    async def search(
        self, question: str, *, kind: str | None = None, limit: int = DEFAULT_LIMIT
    ) -> SearchResult:
        self.searches.append((question, kind, limit))
        return SearchResult(
            passages=tuple(
                Passage(
                    text="a passage",
                    citation=document,
                    document=document,
                    version="",
                    locator="§1",
                    kind=INDEXED_KIND,
                    is_sample=False,
                    distance=0.1,
                )
                for document in sorted(self.approved)
            )
        )


def _as_store(store: DocumentStore) -> DocumentStore:
    """Annotated so a type checker fails if `_FakeStore` stops satisfying the protocol."""
    return store


# ── the state the corpus is left in, which is the whole feature ────────────────

async def test_the_corpus_becomes_measurable_without_becoming_retrievable() -> None:
    """The single most important test here. Before this job, `evaluate` over
    `synex_document_chunk` could only say *there is no corpus*; after it, the corpus exists and
    still reaches nobody. Constraint 1: nothing in the library has been reviewed by a
    refrigeration engineer, and the approval column is where that is enforced at retrieval."""
    store = _FakeStore()
    run = await index_and_measure(store)

    assert run.outcome is RunOutcome.INDEXED
    assert run.passages_stored > 0
    assert run.corpus_state is CorpusState.NOTHING_APPROVED
    assert all(is_approved is False for _, _, is_approved, _ in store.rows)


async def test_every_passage_is_written_unapproved() -> None:
    """An SOP that becomes searchable merely by being ingested is one nobody approved. The
    job never passes `is_approved`, so the default holds at the call site and at the column."""
    store = _FakeStore()
    await index_and_measure(store)

    assert store.rows, "the ingest must actually write something"
    assert not any(is_approved for _, _, is_approved, _ in store.rows)


async def test_the_run_says_in_words_that_an_empty_search_is_the_correct_outcome() -> None:
    """Without this sentence the job looks like it failed, and the obvious repair is to
    approve 124 unreviewed instructions. The reason has to travel with the result."""
    run = await index_and_measure(_FakeStore())

    assert "search still returns nothing, and that is correct" in run.searchable_statement
    assert "no refrigeration engineer has read a line of this library" in run.searchable_statement


async def test_the_library_is_never_indexed_as_an_sop() -> None:
    """`S4` restricts safety retrieval to `kind="sop"`. Tagging the library as an SOP would let
    a safety question be answered out of an unreviewed checklist — the manufacturer's-manual
    failure, entering through the ingest instead of through the search."""
    store = _FakeStore()
    await index_and_measure(store)

    kinds = {kind for _, _, _, kind in store.rows}
    assert kinds == {INDEXED_KIND}
    assert "sop" not in kinds


def test_no_version_is_invented_for_content_whose_source_states_none() -> None:
    """`K5` wants a document **and** a version, and the review pack carries neither a revision
    number nor a date. `v1` here would make every citation in the corpus name a version that
    does not exist. `Q96`."""
    assert LIBRARY_VERSION == ""


# ── the three corpus states, each asserted, none collapsed ─────────────────────

async def test_an_empty_corpus_reports_empty_even_with_no_labelled_set() -> None:
    """The masking case, and the reason `CorpusState` exists at all. With no labelled set the
    *verdict* is `NO_LABELLED_SET` — so if emptiness were carried only by the verdict, an
    un-run ingest would be invisible behind a missing evaluation set."""
    run = await index_and_measure(_FakeStore(), documents=())

    assert run.corpus_state is CorpusState.EMPTY
    assert run.measurement.verdict is Verdict.NO_LABELLED_SET
    assert "the corpus is empty" in run.measurement.corpus_statement
    assert run.measurement.recall_at_k is None


async def test_an_unapproved_corpus_is_a_different_finding_from_an_empty_one() -> None:
    """*Nobody indexed anything* and *nobody approved anything* send an engineer to two
    different places: one to run this job, the other to book the SME hour. Collapsing them is
    the defect this repository has hit five times in a day."""
    empty = await index_and_measure(_FakeStore(), documents=())
    full = await index_and_measure(_FakeStore())

    assert empty.corpus_state is not full.corpus_state
    assert full.corpus_state is CorpusState.NOTHING_APPROVED
    assert "not one is approved" in full.measurement.corpus_statement
    assert "working as designed rather than failing" in full.measurement.corpus_statement


async def test_a_populated_and_approved_corpus_is_measured_rather_than_refused() -> None:
    """The state the SME hour produces. Recall is a real figure here and must be reported as
    one — the honesty rules are not an excuse for never printing a number."""
    approved = "Checklist library — Compressor inefficiency"
    store = _FakeStore(approved=frozenset({approved}))
    labelled = LabelledSet(
        questions=(
            LabelledQuestion(
                question="what do I check on a compressor running inefficiently",
                expected_document=approved,
                why="fixed ranking, so the arithmetic is checkable by hand",
            ),
        ),
        source="written in this test file, alongside the ingest it measures",
    )
    run = await index_and_measure(store, labelled=labelled)

    assert run.corpus_state is CorpusState.APPROVED_AND_SEARCHABLE
    assert run.measurement.verdict is Verdict.MEASURED
    assert run.measurement.recall_at_k == 1.0
    assert "1 approved document(s)" in run.measurement.corpus_statement


async def test_the_measurement_is_scoped_to_the_kind_the_job_writes() -> None:
    """Measuring an unrestricted search would score the library against a corpus that may also
    hold manuals and SOPs, and report a recall for a retriever the product would not run."""
    approved = "Checklist library — Condenser low flow"
    store = _FakeStore(approved=frozenset({approved}))
    labelled = LabelledSet(
        questions=(
            LabelledQuestion(
                question="what do I check when condenser flow is low",
                expected_document=approved,
                why="the kind the search runs at is the property under test",
            ),
        ),
        source="written in this test file",
    )
    await index_and_measure(store, labelled=labelled)

    assert [kind for _, kind, _ in store.searches] == [INDEXED_KIND]


# ── a second run refuses, and a refusal is not an error ────────────────────────

async def test_a_second_run_refuses_rather_than_duplicating_the_corpus() -> None:
    """Nothing makes this job idempotent: `synex_document_chunk` has no unique key on
    (document, locator) and `app.db.knowledge` exposes no delete. A doubled corpus scores well
    on recall while being plainly broken, which is the worst shape a defect can take."""
    store = _FakeStore()
    first = await index_and_measure(store)
    rows_after_first = len(store.rows)

    second = await index_and_measure(store)

    assert second.outcome is RunOutcome.ALREADY_INDEXED
    assert len(store.rows) == rows_after_first, "a re-run must write nothing at all"
    assert second.passages_stored == 0
    assert first.passages_stored == rows_after_first


async def test_the_refusal_carries_its_reason_and_the_question_that_would_lift_it() -> None:
    """A refusal with no reason is indistinguishable from a crash, and a reader who cannot see
    why cannot decide whether to clear the table by hand."""
    store = _FakeStore()
    await index_and_measure(store)
    refused = await index_and_measure(store)

    assert "a refusal, not an error" in refused.reason
    assert "would store every passage twice" in refused.reason
    assert "Q97" in refused.reason


async def test_the_refusal_still_measures_the_corpus_it_found() -> None:
    """*Already indexed* with no measurement leaves an operator unable to tell whether what is
    in there is the library, half of it, or something else. The measurement runs on both
    paths."""
    store = _FakeStore()
    await index_and_measure(store)
    refused = await index_and_measure(store)

    assert refused.corpus_state is CorpusState.NOTHING_APPROVED
    assert refused.measurement.unapproved_in_corpus == len(store.rows)


# ── what is deliberately not indexed ───────────────────────────────────────────

def test_the_nine_holding_actions_are_withheld_with_their_reason() -> None:
    """They sit behind two gates — `sme_reviewed` and `switched_on` — and `DocumentChunk` has
    one. Indexing them would let a single approval open a policy gate that constraint 10 says
    the review deliberately does not clear."""
    withheld = withheld_content()

    assert len(withheld) == 1
    assert withheld[0].count == len(holding_actions.DRAFTED_HOLDING_ACTIONS) == 9
    assert "two gates" in withheld[0].reason
    assert "Constraint 10" in withheld[0].reason


async def test_no_holding_action_text_reaches_a_passage() -> None:
    """The reason is only worth having if the content genuinely stays out. Asserted against the
    text rather than against the count, because a future edit could add a document without
    touching `withheld_content`."""
    corpus = "\n".join(document.text for document in library_documents())

    for action in holding_actions.DRAFTED_HOLDING_ACTIONS:
        assert action.text not in corpus, action.fault_label


async def test_the_withheld_count_is_reported_on_every_run_including_a_refusal() -> None:
    """A job that only speaks up when something changed is indistinguishable from one that has
    stopped running — which is exactly how twenty-two episodes went missing from the queue."""
    store = _FakeStore()
    indexed = await index_and_measure(store)
    refused = await index_and_measure(store)

    assert indexed.withheld == refused.withheld != ()


# ── the corpus is the library, and the counts say which library ────────────────

def test_every_curated_item_reaches_a_document() -> None:
    """124 curated items plus the 7-item fallback. A silently dropped class would leave the
    corpus measurable and wrong, which is worse than leaving it empty."""
    documents = library_documents()

    assert sum(document.items for document in documents) == (
        generic_fallback.CURATED_ITEM_COUNT + generic_fallback.FALLBACK_ITEM_COUNT
    ) == 131


async def test_the_item_count_is_reported_apart_from_the_passage_count() -> None:
    """A class of thirteen items becomes four passages. A reader shown only the row count would
    conclude nine items had been lost, and a reader shown only the item count would think each
    one is separately retrievable."""
    store = _FakeStore()
    run = await index_and_measure(store)

    assert run.items_indexed == 131
    assert run.passages_stored == len(store.rows)
    assert run.passages_stored < run.items_indexed


def test_all_nineteen_causes_and_all_nineteen_questions_are_carried() -> None:
    """`RC12`'s content is the highest-risk material in the programme — thirty-one causes have
    already been eliminated by discriminators nobody has reviewed. Losing one in the ingest
    would remove it from the review pack a reviewer reads."""
    documents = library_documents()

    assert sum(document.causes for document in documents) == 19
    assert sum(document.questions for document in documents) == 19
    assert sum(1 for document in documents if document.questions) == len(differentials.LIBRARY)


def test_a_document_exists_for_every_transcribed_fault_class() -> None:
    """Eleven classes: seven the trained model reports and four our own arithmetic raises.
    Constraint 37 — every class must leave the operator something to do — is unenforceable if
    a class never reaches the corpus at all."""
    titles = {document.title for document in library_documents()}

    for fault_class in trained_model_classes.TRAINED_MODEL_CLASSES:
        assert f"Checklist library — {fault_class.display}" in titles
    for fault in measurement_faults.MEASUREMENT_FAULTS:
        assert f"Checklist library — {fault.display}" in titles


def test_the_fallback_is_its_own_document_rather_than_a_section_of_a_class() -> None:
    """`124 + 7`, never `131 across 11 classes`. Folding the seven into a per-class total makes
    every per-class figure wrong by seven."""
    fallback = next(
        document for document in library_documents() if "generic fallback" in document.title
    )

    assert fallback.items == generic_fallback.FALLBACK_ITEM_COUNT == 7
    assert "belong to no fault class" in fallback.text


# ── provenance survives the ingest, or the passage is model output ─────────────

def test_every_passage_can_name_the_file_it_was_transcribed_from() -> None:
    """A retrieved instruction that cannot name its source is indistinguishable from something
    a model produced on a Tuesday. Constraint 1, checked at the layer that makes text
    retrievable rather than only at the layer that holds it."""
    for document in library_documents():
        assert document.source
        assert "thermynx/docs/for-vishnu/" in document.source


def test_the_unreviewed_state_is_stated_inside_the_text_and_not_only_in_a_column() -> None:
    """`is_approved` lives on the row; a person reading a passage sees the text. If review
    status existed only as a column, a passage pasted into an email would carry none of it."""
    for document in library_documents():
        assert "reviewed" in document.text


def test_no_instruction_is_written_by_this_job() -> None:
    """Every item in every passage must appear character for character in the transcription.
    Constraint 26: the language model selects and contextualises library content and never
    authors a field instruction — and neither does the ingest."""
    corpus = "\n".join(document.text for document in library_documents())

    for item in (*trained_model_classes.all_items(), *measurement_faults.all_items()):
        assert item.text in corpus, item.id


def test_every_item_carries_its_capability_into_the_passage() -> None:
    """Constraint 23: an operator must never be blocked by a check they cannot perform. A
    passage that lost the role tag makes an oil analysis look like something anyone can do."""
    first = trained_model_classes.TRAINED_MODEL_CLASSES[0]
    document = next(
        d for d in library_documents() if d.title == f"Checklist library — {first.display}"
    )

    assert "capability: operator" in document.text
    assert "capability: technician" in document.text


def test_a_blocking_item_says_so_in_words_rather_than_by_omission() -> None:
    """*Not blocking* is printed as well as *blocking*. An absent tag would be the dash wearing
    a value — constraint 14 — and blocking is the flag that shuts a gate, so a passage that
    said nothing about it would read as though the check were optional."""
    corpus = "\n".join(document.text for document in library_documents())

    assert "· blocking" in corpus
    assert "· not blocking" in corpus


def test_cannot_tell_is_carried_with_its_emptiness_spelt_out() -> None:
    """Constraint 30: *can't tell* must have no effect at all. A passage that simply omitted it
    would read as though the question forces a guess."""
    differential_documents = [d for d in library_documents() if d.questions]

    for document in differential_documents:
        assert "Can't tell — no effect on any cause, deliberately" in document.text


# ── the splitter, exercised against the content it was written for ─────────────

async def test_no_checklist_step_is_severed_from_its_lead_in() -> None:
    """The failure `chunking` exists to prevent, checked against the real 131 items rather than
    against a fixture. A step read without the condition it applies under reads as complete."""
    run = await index_and_measure(_FakeStore())

    severed = [c for c in run.concerns if "the condition they apply under" in c]
    assert severed == [], severed


async def test_every_document_is_split_on_its_own_structure() -> None:
    """An unstructured document becomes one passage citing no place inside itself. That is
    honest for a document nobody wrote headings into, and wrong for one this job assembled."""
    run = await index_and_measure(_FakeStore())

    assert all(document.structure_found for document in run.documents)
    assert all(document.passages_stored > 1 for document in run.documents)


async def test_a_dotted_measurement_in_a_document_never_opens_a_passage() -> None:
    """The chunking blocker the review found. `4.2 bar` was read as section 4.2 and split the
    passage there — which severs a checklist step from its rationale through the heading
    detector rather than the step detector. The library holds no dotted numbers today, so it is
    asserted here against the shape a real SOP will bring."""
    document = LibraryDocument(
        title="Pressure notes",
        text=(
            "# Head pressure\n\n"
            "4.2 bar is the commissioned reading for this machine.\n\n"
            "1. Record the reading before cleaning the condenser.\n"
        ),
        source="written in this test file",
    )
    store = _FakeStore()
    run = await index_and_measure(store, documents=(document,))

    assert run.documents[0].passages_stored == 1, "the measurement must not open a passage"
    assert any("is a unit" in held for held in run.held_as_text)
    assert run.documents[0].concerns == ()


async def test_a_held_dotted_number_is_recorded_rather_than_treated_as_a_concern() -> None:
    """Holding `4.2 bar` inside its own paragraph is the splitter working. Reporting it as a
    concern would train a reader to ignore the list that names real defects."""
    document = LibraryDocument(
        title="Pressure notes",
        text="# Head pressure\n\n4.2 bar is the commissioned reading.\n",
        source="written in this test file",
    )
    run = await index_and_measure(_FakeStore(), documents=(document,))

    assert run.held_as_text
    assert run.concerns == ()


# ── the shape a scheduler and an operator consume ──────────────────────────────

async def test_the_serialised_run_carries_the_reason_beside_every_absence() -> None:
    """`as_dict` is what lands in the arq job result. A count with no accompanying sentence is
    the dash wearing a value."""
    payload = (await index_and_measure(_FakeStore())).as_dict()

    assert payload["outcome"] == "indexed"
    assert payload["corpus_state"] == "nothing_approved"
    assert "search still returns nothing" in payload["searchable"]
    assert payload["measurement"]["recall_at_k"] is None
    assert payload["items_indexed"] == 131
    assert payload["withheld"]


async def test_the_rendered_run_never_prints_a_number_that_looks_like_a_score() -> None:
    """`0.00` in this output would be indistinguishable from a measured retrieval failure, and
    the corpus is the thing that has no score today."""
    rendered = (await index_and_measure(_FakeStore())).render()

    assert "0.00" not in rendered
    assert "recall@5 was not measured" in rendered


def test_the_fake_store_and_the_real_index_share_one_shape() -> None:
    """A fake that had drifted from `SopIndex` would let every test above pass against a store
    the job could never actually use — an offline suite measuring itself. Signatures rather
    than names, because a renamed keyword is exactly the drift a `hasattr` check misses."""
    from app.retrieval.sop import SopIndex

    assert _as_store(_FakeStore()) is not None
    for method in ("index_document", "approved_documents", "unapproved_count", "search"):
        real = inspect.signature(getattr(SopIndex, method))
        fake = inspect.signature(getattr(_FakeStore, method))
        assert set(real.parameters) == set(fake.parameters), method


async def test_an_index_run_reads_its_corpus_state_off_the_measurement() -> None:
    """Two derivations of the same fact is how *empty* and *nothing approved* start disagreeing
    across a codebase. There is one, and the run borrows it."""
    run: IndexRun = await index_and_measure(_FakeStore())

    assert run.corpus_state is run.measurement.corpus_state


@pytest.mark.parametrize("documents", [(), None])
async def test_the_run_reports_a_state_whether_or_not_it_wrote_anything(documents) -> None:
    """A job that reports only when it changed something is one nobody can tell has stopped."""
    run = await index_and_measure(_FakeStore(), documents=documents)

    assert run.searchable_statement
    assert run.measurement.corpus_statement
    assert run.withheld
