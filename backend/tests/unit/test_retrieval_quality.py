"""Retrieval evaluation — and the two ways a metric lies.

The first is a **gate that passes while checking nothing**, which this repository has shipped
twice: the numeric audit that compared by substring containment, and seven layering contracts
that import-linter refused as misconfigured and nobody noticed. So half of this file feeds the
evaluator situations where a score is *not* available and asserts that no number comes out.

The second is a **score that is really about something else**. `synex_document_chunk` holds
zero rows, so today every question would miss and recall@5 would read 0.00 — a statement about
the ingest, printed as a statement about retrieval. The empty-corpus tests are the ones that
matter most, and they run offline with Postgres stopped and the embedder unreachable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.retrieval import quality
from app.retrieval.quality import (
    LabelledQuestion,
    LabelledSet,
    Outcome,
    Verdict,
    evaluate,
)
from app.retrieval.sop import DEFAULT_LIMIT, Passage, SearchResult

ISOLATION_DOC = "Chiller Isolation SOP"
CLEANING_DOC = "Condenser Cleaning SOP"


@dataclass
class _FakeIndex:
    """A stand-in for `SopIndex` that satisfies `ApprovedCorpus` and touches nothing.

    The point is not to fake retrieval well — it is to fix the *ranking* so the arithmetic is
    checkable by hand. A test whose expected recall depends on a live embedder measures the
    embedder.
    """

    documents: frozenset[str] = field(default_factory=frozenset)
    ranking: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unapproved: int = 0
    available: bool = True
    unavailable_reason: str = ""
    limits_seen: list[int] = field(default_factory=list)
    kinds_seen: list[str | None] = field(default_factory=list)

    async def approved_documents(self, kind: str | None = None) -> frozenset[str]:
        return self.documents

    async def unapproved_count(self, kind: str | None = None) -> int:
        return self.unapproved

    async def search(
        self, question: str, *, kind: str | None = None, limit: int = DEFAULT_LIMIT
    ) -> SearchResult:
        self.limits_seen.append(limit)
        self.kinds_seen.append(kind)
        if not self.available:
            return SearchResult(available=False, reason=self.unavailable_reason)
        returned = self.ranking.get(question, ())[:limit]
        return SearchResult(
            passages=tuple(
                Passage(
                    text=f"a passage from {document}",
                    citation=document,
                    document=document,
                    version="1",
                    locator="§1",
                    kind="sop",
                    is_sample=True,
                    distance=0.1 * position,
                )
                for position, document in enumerate(returned, start=1)
            ),
            unapproved_in_corpus=self.unapproved,
        )


def _pair(question: str, expected: str) -> LabelledQuestion:
    return LabelledQuestion(
        question=question,
        expected_document=expected,
        why="fixed ranking, so the arithmetic is checkable by hand",
    )


ISOLATION_PAIR = _pair("how do I make the compressor safe", ISOLATION_DOC)
CLEANING_PAIR = _pair("when should the condenser tubes be brushed", CLEANING_DOC)

SET = LabelledSet(
    questions=(ISOLATION_PAIR, CLEANING_PAIR),
    source="written in this test file, alongside the retriever it measures",
)


def _seeded(**ranking: tuple[str, ...]) -> _FakeIndex:
    return _FakeIndex(
        documents=frozenset({ISOLATION_DOC, CLEANING_DOC}),
        ranking={
            ISOLATION_PAIR.question: ranking.get("isolation", (ISOLATION_DOC,)),
            CLEANING_PAIR.question: ranking.get("cleaning", (CLEANING_DOC,)),
        },
    )


# ── the empty corpus: a statement about the corpus, never a score ──────────────

async def test_an_empty_corpus_reports_no_corpus_rather_than_a_recall_of_zero() -> None:
    """The single most important test here. `synex_document_chunk` holds zero rows today, so
    every question misses and recall@5 reads 0.00 — which blames retrieval for an ingest that
    was never run. Honesty rule 2: an absence is not a zero."""
    report = await evaluate(_FakeIndex(), SET)

    assert report.verdict is Verdict.NO_CORPUS
    assert report.recall_at_k is None
    assert report.mrr_at_k is None
    assert "no corpus" in report.reason
    assert "statement about the corpus and not about retrieval" in report.reason


async def test_the_empty_case_never_renders_a_number_that_looks_like_a_score() -> None:
    """A reader skimming the render must not be able to read a figure out of it. `0.00` in
    that output would be indistinguishable from a measured failure."""
    rendered = (await evaluate(_FakeIndex(), SET)).render()

    assert "0.00" not in rendered
    assert "recall@5 was not measured" in rendered


async def test_an_unapproved_corpus_is_a_different_finding_from_an_empty_one() -> None:
    """*Nobody indexed anything* and *nobody approved anything* send an engineer to two
    different places. Constraint 1 — approval gates retrieval as review gates the checklist —
    working as designed is not a retrieval failure."""
    report = await evaluate(_FakeIndex(unapproved=131), SET)

    assert report.verdict is Verdict.NOTHING_APPROVED
    assert report.verdict is not Verdict.NO_CORPUS
    assert report.recall_at_k is None
    assert "131 passage(s)" in report.reason


async def test_no_labelled_set_is_not_a_low_score() -> None:
    """The set Synex actually holds is empty (`Q91`). A metric over zero questions has no
    value, and printing one would make the absence of an evaluation set invisible."""
    report = await evaluate(_seeded(), quality.NO_LABELLED_SET_YET)

    assert report.verdict is Verdict.NO_LABELLED_SET
    assert report.recall_at_k is None
    assert "Q91" in report.reason


# ── the seeded corpus: the arithmetic, checkable by hand ───────────────────────

async def test_a_seeded_corpus_measures_recall_and_mrr_at_the_stated_k() -> None:
    """Both expected documents come back at rank 1, so recall@5 is 1.00 and MRR@5 is 1.00.
    Hand-checkable on purpose: a metric nobody can verify by inspection is one that can be
    subtly wrong for a year."""
    report = await evaluate(_seeded(), SET)

    assert report.verdict is Verdict.MEASURED
    assert report.recall_at_k == 1.0
    assert report.mrr_at_k == 1.0
    assert len(report.scored) == 2


async def test_a_miss_inside_the_corpus_is_the_only_thing_recall_punishes() -> None:
    """One of two found: recall@5 = 0.50. The missed pair names what came back instead, so a
    person can diagnose it rather than only re-run it."""
    index = _seeded(cleaning=(ISOLATION_DOC,))
    report = await evaluate(index, SET)

    assert report.recall_at_k == 0.5
    missed = next(r for r in report.results if r.outcome is Outcome.MISSED)
    assert missed.documents_returned == (ISOLATION_DOC,)
    assert "did not appear in the top 5" in missed.reason


async def test_mrr_falls_when_the_right_passage_is_buried() -> None:
    """Rank 1 and rank 3 give (1 + 1/3) / 2. Recall@5 cannot see the difference, which is
    exactly why both are reported: a retriever that always ranks the answer fourth is a
    retriever nobody reads."""
    index = _seeded(cleaning=(ISOLATION_DOC, ISOLATION_DOC, CLEANING_DOC))
    report = await evaluate(index, SET)

    assert report.recall_at_k == 1.0
    assert report.mrr_at_k == pytest.approx((1.0 + 1 / 3) / 2)


async def test_a_document_missing_from_the_corpus_is_excluded_not_counted_as_a_miss() -> None:
    """The empty-corpus error, one question at a time. Scoring it as a miss would blame the
    retriever for an ingest that never happened, and the resulting recall would silently be a
    measure of coverage."""
    index = _FakeIndex(
        documents=frozenset({ISOLATION_DOC}),
        ranking={ISOLATION_PAIR.question: (ISOLATION_DOC,), CLEANING_PAIR.question: ()},
    )
    report = await evaluate(index, SET)

    assert report.verdict is Verdict.MEASURED
    assert report.recall_at_k == 1.0, "one scorable pair, found"
    excluded = next(r for r in report.results if not r.is_scored)
    assert excluded.outcome is Outcome.EXPECTED_DOCUMENT_ABSENT
    assert "measures the ingest, not the retriever" in excluded.reason


async def test_a_labelled_set_that_misses_the_corpus_entirely_says_so() -> None:
    """Every expected document absent means the set was written against documents nobody
    ingested. That is a finding about the set, and reporting 0.00 would attach it to the
    retriever instead."""
    index = _FakeIndex(documents=frozenset({"Some Other Manual"}))
    report = await evaluate(index, SET)

    assert report.verdict is Verdict.LABELLED_SET_MISSES_THE_CORPUS
    assert report.recall_at_k is None
    assert "says nothing about retrieval" in report.reason


async def test_an_unreachable_embedder_is_not_a_score_of_zero() -> None:
    """*Nothing matched* and *we could not search* are different facts — one about the library,
    the other about the system. `SearchResult` keeps them apart and the metric must too."""
    index = _FakeIndex(
        documents=frozenset({ISOLATION_DOC, CLEANING_DOC}),
        available=False,
        unavailable_reason="the embedding model could not be reached at 127.0.0.1:59999",
    )
    report = await evaluate(index, SET)

    assert report.verdict is Verdict.SEARCH_UNAVAILABLE
    assert report.recall_at_k is None
    assert all(r.outcome is Outcome.UNAVAILABLE for r in report.results)
    assert "fact about the system rather than about the library" in report.reason


# ── never a bare score ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("k", [1, 3, 5])
async def test_every_figure_carries_the_k_it_was_measured_at(k: int) -> None:
    """recall@1 and recall@5 over the same search are different claims. A number printed
    without its `k` cannot be argued with — and `k` is `DEFAULT_LIMIT`, itself unsourced
    (`Q59`)."""
    report = await evaluate(_seeded(), SET, k=k)

    assert f"recall@{k}" in report.recall_statement
    assert f"MRR@{k}" in report.mrr_statement
    assert report.as_dict()["k"] == k


async def test_the_k_asked_for_is_the_k_the_search_was_run_at() -> None:
    """Measuring recall@1 against a search that returned five passages would report a figure
    for a retriever the product does not run."""
    index = _seeded()
    await evaluate(index, SET, k=2)

    assert index.limits_seen == [2, 2]


async def test_k_defaults_to_what_a_reader_actually_sees() -> None:
    """`DEFAULT_LIMIT` bounds what a search returns, so evaluating at anything else measures a
    configuration nobody uses."""
    report = await evaluate(_seeded(), SET)
    assert report.k == DEFAULT_LIMIT


async def test_recall_at_zero_raises_rather_than_answering_a_different_question() -> None:
    """Clamping would answer recall@1 to a caller who asked for recall@0. Silently answering a
    different question is how a metric starts reassuring people."""
    with pytest.raises(ValueError, match="k must be at least 1"):
        await evaluate(_seeded(), SET, k=0)


# ── this measures; it does not gate ────────────────────────────────────────────

def test_no_recall_target_is_invented() -> None:
    """`Q90`. A threshold chosen here would pass on day one against an empty corpus and keep
    passing — the third gate that checks nothing, authored deliberately."""
    assert quality.TARGET_RECALL_AT_K is None


async def test_the_report_states_that_it_does_not_gate() -> None:
    """A measurement a reader assumes is a gate is worse than no measurement, because it gets
    trusted. So the absence of a target is printed alongside the figure."""
    statement = (await evaluate(_seeded(), SET)).target_statement

    assert "no target is agreed" in statement
    assert "does not gate (Q90)" in statement


async def test_an_unreviewed_labelled_set_is_declared_beside_its_own_figures() -> None:
    """The same defect as the 124 unreviewed checklist items and the 19 unreviewed
    discriminators: a set written by whoever wrote the retriever measures the author."""
    report = await evaluate(_seeded(), SET)

    assert report.labelled_set_reviewed is False
    assert "measure agreement with the expectations of whoever wrote them" in report.render()


async def test_a_reviewed_set_stops_claiming_it_is_unreviewed() -> None:
    """The declaration must be a fact about the set rather than a fixed sentence, or it stops
    being read."""
    reviewed = LabelledSet(
        questions=SET.questions, source="reviewed with the EHS owner", is_reviewed=True
    )
    report = await evaluate(_seeded(), reviewed)

    assert report.review_statement == "the labelled set has been reviewed"


# ── the shape a surface would consume ──────────────────────────────────────────

async def test_the_serialised_report_carries_the_reason_beside_every_absence() -> None:
    """`as_dict` is what a route would return. A `None` with no accompanying sentence is the
    dash wearing a value — constraint 14."""
    payload = (await evaluate(_FakeIndex(), SET)).as_dict()

    assert payload["recall_at_k"] is None
    assert payload["mrr_at_k"] is None
    assert "recall@5 was not measured" in payload["recall"]
    assert payload["verdict"] == "no_corpus"
    assert payload["measured"] is False


async def test_a_safety_pair_is_scored_against_the_search_S4_would_actually_run() -> None:
    """`S4` restricts to `kind="sop"`. Measuring it against an unrestricted search reports a
    recall the safety path would never achieve."""
    index = _seeded()
    safety = LabelledSet(
        questions=(
            LabelledQuestion(
                question=ISOLATION_PAIR.question,
                expected_document=ISOLATION_DOC,
                why="S4 never answers from a manufacturer's manual",
                kind="sop",
            ),
        ),
        source="written in this test file",
    )
    await evaluate(index, safety)

    assert index.kinds_seen == ["sop"]


async def test_unscored_questions_are_counted_apart_from_failures() -> None:
    """A pair that could not be scored is not a pair that failed, and a report that merged the
    two would let a coverage gap read as a retrieval defect."""
    index = _FakeIndex(
        documents=frozenset({ISOLATION_DOC}),
        ranking={ISOLATION_PAIR.question: (ISOLATION_DOC,), CLEANING_PAIR.question: ()},
    )
    report = await evaluate(index, SET)

    assert len(report.scored) == 1
    assert len(report.unscored) == 1
    assert "is not a pair that failed" in report.render()
