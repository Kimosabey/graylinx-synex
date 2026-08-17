"""Retrieval evaluation — recall@k and MRR@k, and what they are not allowed to claim.

**The failure this prevents.** Nothing measures whether a search returns the right passage.
`synex_document_chunk` holds **zero rows**, so `K1`, `K5` and `S4` are a mechanism that has
never been run against content — and a retrieval layer nobody measures is one that degrades
silently, because every query still returns five confident, well-cited passages.

This repository has already shipped **two gates that passed while checking nothing**, and both
were found by accident rather than by a gate:

* the numeric audit compared by substring containment, so `-25.6` matched inside `-25.645` and
  the exact truncation the audit existed to catch sailed straight through — and the test
  written to catch that passed against the broken version;
* `importlinter.ini` set `exhaustive` without `containers`, so import-linter refused all seven
  contracts as misconfigured rather than running them, for the whole life of the repository.

An unmeasured retrieval layer is the third of those, waiting.

**A recall of 0.0 over an empty corpus is a statement about the corpus.** Constraint 14 — a
figure is a value or a stated absence, never both and never neither — and honesty rule 2, an
absence is not a zero. So `evaluate` returns a `Verdict` before it returns a number, and five
of the six verdicts mean *no score was measured, and here is why in words*. Reporting `0.0`
against zero indexed documents would blame retrieval for the ingest never having been run.

**Never a bare score.** Every figure this module renders carries the `k` it was measured at,
because recall@1 and recall@5 over the same search are different claims and a number printed
without its `k` cannot be argued with. `DEFAULT_LIMIT` is itself `TBD (Q59)`.

**Nothing here gates.** `TARGET_RECALL_AT_K` is unset (`Q90`): no document states what recall
retrieval must reach. Choosing a threshold here so that the suite could go green would be the
third gate that passes while checking nothing, authored deliberately.

**No model judges relevance.** A pair is scored by whether the expected document appears in
the top k — arithmetic over ranks. A model-scored relevance judgement would produce exactly
the numeric confidence inherited constraint 2 forbids, and would let the language model decide
whether the retrieval it feeds on is working. Answer quality is a separate question with a
separate tool: DeepEval against a local judge, never Ragas, which is banned.

**The labelled set is unreviewed, and that is reported rather than assumed away.** No labelled
set exists (`Q91`), and one written here would measure agreement with our own expectations —
the same defect as the 124 checklist items and 19 discriminators that no refrigeration
engineer has read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from app.retrieval.sop import DEFAULT_LIMIT, SearchResult

#: What recall@k would have to reach before retrieval could be called good enough. **Unset.**
#:
#: TBD (Q90) — nothing in `docs/00-source/` or `CONTEXT.md` states a retrieval target, at any
#: k. `None` means this module reports and never gates: a threshold invented here would pass
#: on day one against an empty corpus and go on passing, which is the precise failure the
#: module docstring names twice. When Q90 is answered this becomes a float and
#: `RetrievalReport.target_statement` starts saying something.
TARGET_RECALL_AT_K: float | None = None


class Verdict(StrEnum):
    """Whether a score was measured at all, and if not, what stopped it.

    Six, and five of them are refusals. Each names a different thing to go and fix, which is
    the whole reason they are not collapsed into one `False`: *nobody indexed anything*,
    *nobody approved anything* and *the questions point at documents we do not hold* send an
    engineer to three different places.
    """

    MEASURED = "measured"

    NO_CORPUS = "no_corpus"
    """`synex_document_chunk` holds nothing at all. Not a score of zero."""

    NOTHING_APPROVED = "nothing_approved"
    """Passages exist and none is approved, so search can reach none of them. Constraint 1 —
    approval gates retrieval exactly as review gates the checklist — working as designed."""

    NO_LABELLED_SET = "no_labelled_set"
    """No question was supplied. A metric over zero questions is not a low score."""

    LABELLED_SET_MISSES_THE_CORPUS = "labelled_set_misses_the_corpus"
    """Every expected document is absent from the corpus. This measures the labelled set."""

    SEARCH_UNAVAILABLE = "search_unavailable"
    """The embedder could not be reached, so nothing was searched — a fact about the system
    rather than about the library, exactly as `SearchResult.available` keeps them apart."""


class Outcome(StrEnum):
    """How one labelled question ended. Four, and only two of them are scored."""

    FOUND = "found"
    MISSED = "missed"
    """The corpus holds the expected document and the search did not return it in the top k.
    The only genuine retrieval failure here, and the only one recall is entitled to punish."""

    EXPECTED_DOCUMENT_ABSENT = "expected_document_absent"
    """The corpus does not hold the expected document at all. **Excluded from the score.**
    Counting it as a miss blames the retriever for an ingest that never happened, which is the
    empty-corpus error one question at a time."""

    UNAVAILABLE = "unavailable"
    """Nothing was searched. Also excluded — it did not fail, it did not run."""


class ApprovedCorpus(Protocol):
    """What evaluation needs of an index, and nothing more.

    Structural rather than concrete so the metrics are unit-testable with Postgres stopped and
    the embedder unreachable — the same property every other gate in this repository holds.
    `app.retrieval.sop.SopIndex` satisfies it.
    """

    async def approved_documents(self, kind: str | None = ...) -> frozenset[str]: ...

    async def unapproved_count(self, kind: str | None = ...) -> int: ...

    async def search(
        self, question: str, *, kind: str | None = ..., limit: int = ...
    ) -> SearchResult: ...


@dataclass(frozen=True)
class LabelledQuestion:
    """One `(question, expected_document)` pair, and why somebody wrote it down.

    `why` is not decoration. A pair whose purpose nobody recorded cannot be reviewed, and an
    unreviewable evaluation set is how a suite starts passing on the wrong thing — see the two
    gates in the module docstring, both of which had tests.
    """

    question: str
    expected_document: str
    why: str = ""
    kind: str | None = None
    """Restricts the search the way `S4` does. A safety pair must be scored against `sop`
    only, or it measures a search the product would never run."""


@dataclass(frozen=True)
class LabelledSet:
    """The pairs, where they came from, and whether anyone qualified has read them."""

    questions: tuple[LabelledQuestion, ...] = field(default_factory=tuple)
    source: str = ""
    """Words. *Written alongside the retriever* and *taken from real operator questions* are
    different evidence, and a set that cannot say which is not evidence."""

    is_reviewed: bool = False
    """**Defaults to `False`**, like `is_approved` and `sme_reviewed`. An unreviewed set
    measures agreement with whoever wrote the retriever."""

    @property
    def review_statement(self) -> str:
        if self.is_reviewed:
            return "the labelled set has been reviewed"
        return (
            "the labelled set is unreviewed, so these figures measure agreement with the "
            "expectations of whoever wrote them, not with what an engineer would look for "
            "(Q91)"
        )


#: The labelled set Synex actually holds. Empty — and that is the finding rather than a gap
#: this module should quietly fill with plausible questions.
#:
#: `Q91` carries who authors it and against which documents. It is the SME hour's analogue for
#: retrieval: a set written by the people who wrote the retriever measures the retriever
#: against its author's assumptions, which is worth less than measuring nothing, because it
#: produces a number.
NO_LABELLED_SET_YET = LabelledSet(
    questions=(),
    source="no labelled set has been authored for Synex — Q91",
    is_reviewed=False,
)


@dataclass(frozen=True)
class QuestionResult:
    """One pair, scored or explicitly not scored."""

    question: LabelledQuestion
    outcome: Outcome
    rank: int | None
    """Where the expected document appeared, 1-based. `None` is *not in the top k*, *absent
    from the corpus* or *never searched* — which is why `outcome` exists and `rank` alone is
    never read."""

    reason: str
    documents_returned: tuple[str, ...] = field(default_factory=tuple)
    """What came back instead. A miss with no record of what was returned cannot be
    diagnosed by a person, only re-run."""

    @property
    def is_scored(self) -> bool:
        return self.outcome in {Outcome.FOUND, Outcome.MISSED}

    @property
    def reciprocal_rank(self) -> float:
        """`1/rank`, or 0.0 for a scored miss. Only ever summed over `is_scored` results."""
        return 1.0 / self.rank if self.rank else 0.0

    def render(self) -> str:
        return f"{self.question.question!r} — {self.reason}"


@dataclass(frozen=True)
class RetrievalReport:
    """The measurement, or the reason there is not one. `k` is on the object, always.

    There is no `score` attribute and no `__float__`. Every route out of this class carries
    the `k` alongside the number, because a recall printed without its `k` is a figure that
    cannot be argued with — and `k` here is `DEFAULT_LIMIT`, which is itself unsourced (Q59).
    """

    k: int
    verdict: Verdict
    reason: str
    results: tuple[QuestionResult, ...] = field(default_factory=tuple)
    corpus_documents: int = 0
    unapproved_in_corpus: int = 0
    labelled_set_source: str = ""
    labelled_set_reviewed: bool = False

    @property
    def was_measured(self) -> bool:
        return self.verdict is Verdict.MEASURED

    @property
    def scored(self) -> tuple[QuestionResult, ...]:
        return tuple(result for result in self.results if result.is_scored)

    @property
    def unscored(self) -> tuple[QuestionResult, ...]:
        return tuple(result for result in self.results if not result.is_scored)

    @property
    def recall_at_k(self) -> float | None:
        """`None` when nothing was measured. Never `0.0` standing in for *we did not look*."""
        if not self.was_measured or not self.scored:
            return None
        found = sum(1 for result in self.scored if result.outcome is Outcome.FOUND)
        return found / len(self.scored)

    @property
    def mrr_at_k(self) -> float | None:
        """Mean reciprocal rank over the scored pairs, cut off at `k`. `None`, not zero."""
        if not self.was_measured or not self.scored:
            return None
        return sum(result.reciprocal_rank for result in self.scored) / len(self.scored)

    @property
    def recall_statement(self) -> str:
        """The metric with its `k`, or the absence with its reason. Never a bare number."""
        value = self.recall_at_k
        if value is None:
            return f"recall@{self.k} was not measured: {self.reason}"
        return (
            f"recall@{self.k} is {value:.2f} over {len(self.scored)} scored question(s) "
            f"against {self.corpus_documents} approved document(s)"
        )

    @property
    def mrr_statement(self) -> str:
        value = self.mrr_at_k
        if value is None:
            return f"MRR@{self.k} was not measured: {self.reason}"
        return f"MRR@{self.k} is {value:.2f} over {len(self.scored)} scored question(s)"

    @property
    def target_statement(self) -> str:
        """What this would have to reach to be good enough. Nothing does, yet — `Q90`."""
        if TARGET_RECALL_AT_K is None:
            return (
                f"no target is agreed for recall@{self.k}, so this measurement reports and "
                f"does not gate (Q90). A threshold chosen here would pass against an empty "
                f"corpus and keep passing"
            )
        value = self.recall_at_k
        if value is None:
            return (
                f"the target for recall@{self.k} is {TARGET_RECALL_AT_K:.2f} and nothing was "
                f"measured against it: {self.reason}"
            )
        met = "meets" if value >= TARGET_RECALL_AT_K else "is below"
        return f"recall@{self.k} of {value:.2f} {met} the agreed {TARGET_RECALL_AT_K:.2f}"

    @property
    def review_statement(self) -> str:
        if self.labelled_set_reviewed:
            return "the labelled set has been reviewed"
        return (
            "the labelled set is unreviewed, so these figures measure agreement with the "
            "expectations of whoever wrote them (Q91)"
        )

    def as_dict(self) -> dict[str, Any]:
        """`k` is a key in its own right and appears beside every figure it qualifies."""
        return {
            "k": self.k,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "measured": self.was_measured,
            "recall_at_k": self.recall_at_k,
            "recall": self.recall_statement,
            "mrr_at_k": self.mrr_at_k,
            "mrr": self.mrr_statement,
            "target": self.target_statement,
            "labelled_set": self.labelled_set_source,
            "labelled_set_review": self.review_statement,
            "scored_questions": len(self.scored),
            "unscored_questions": len(self.unscored),
            "corpus_documents": self.corpus_documents,
            "unapproved_in_corpus": self.unapproved_in_corpus,
        }

    def render(self) -> str:
        lines = [self.recall_statement, self.mrr_statement, self.target_statement]
        lines.append(self.review_statement)
        if self.unscored:
            lines.append(
                f"{len(self.unscored)} question(s) were not scored, and each says why below — "
                f"a pair that could not be scored is not a pair that failed."
            )
        lines.extend(f"  {result.render()}" for result in self.results)
        return "\n".join(lines)


def _corpus_refusal(
    k: int, documents: frozenset[str], unapproved: int, labelled: LabelledSet
) -> RetrievalReport | None:
    """The checks that must happen *before* a number exists. `None` means go ahead.

    Ordered so the reason a reader gets is the first thing they can act on: no questions is a
    different job from no corpus, and no corpus is a different job from nothing approved.
    """
    common = {
        "k": k,
        "corpus_documents": len(documents),
        "unapproved_in_corpus": unapproved,
        "labelled_set_source": labelled.source,
        "labelled_set_reviewed": labelled.is_reviewed,
    }
    if not labelled.questions:
        return RetrievalReport(
            verdict=Verdict.NO_LABELLED_SET,
            reason=(
                f"no labelled question was supplied ({labelled.source or 'no source given'}). "
                f"A metric over zero questions is not a low score, so none is reported"
            ),
            **common,
        )
    if not documents and unapproved == 0:
        return RetrievalReport(
            verdict=Verdict.NO_CORPUS,
            reason=(
                "there is no corpus — synex_document_chunk holds no passages at all, so "
                "nothing could be retrieved by any retriever. A recall of 0.0 here would be a "
                "statement about the corpus and not about retrieval, so no score is reported"
            ),
            **common,
        )
    if not documents:
        return RetrievalReport(
            verdict=Verdict.NOTHING_APPROVED,
            reason=(
                f"the corpus holds {unapproved} passage(s) and none is approved, so search can "
                f"reach none of them. That is approval gating retrieval as designed, not a "
                f"retrieval failure, so no score is reported"
            ),
            **common,
        )
    return None


def _score_one(
    labelled: LabelledQuestion, result: SearchResult, corpus: frozenset[str], k: int
) -> QuestionResult:
    """One pair against one search. Four outcomes, and two of them are not failures."""
    if not result.available:
        return QuestionResult(
            question=labelled,
            outcome=Outcome.UNAVAILABLE,
            rank=None,
            reason=(
                f"nothing was searched, so this pair was not scored — {result.reason}"
            ),
        )

    returned = tuple(passage.document for passage in result.passages)

    if labelled.expected_document not in corpus:
        return QuestionResult(
            question=labelled,
            outcome=Outcome.EXPECTED_DOCUMENT_ABSENT,
            rank=None,
            reason=(
                f"{labelled.expected_document!r} is not in the approved corpus, so this pair "
                f"was excluded rather than counted as a miss — it measures the ingest, not the "
                f"retriever"
            ),
            documents_returned=returned,
        )

    for position, document in enumerate(returned, start=1):
        if document == labelled.expected_document:
            return QuestionResult(
                question=labelled,
                outcome=Outcome.FOUND,
                rank=position,
                reason=(
                    f"{labelled.expected_document!r} came back at rank {position} of "
                    f"{len(returned)} within k={k}"
                ),
                documents_returned=returned,
            )

    instead = ", ".join(dict.fromkeys(returned)) or "nothing at all"
    return QuestionResult(
        question=labelled,
        outcome=Outcome.MISSED,
        rank=None,
        reason=(
            f"{labelled.expected_document!r} is in the corpus and did not appear in the top "
            f"{k}; what came back was: {instead}"
        ),
        documents_returned=returned,
    )


async def evaluate(
    index: ApprovedCorpus,
    labelled: LabelledSet,
    *,
    k: int = DEFAULT_LIMIT,
    kind: str | None = None,
) -> RetrievalReport:
    """Recall@k and MRR@k over a labelled set — or the reason there is no number.

    `k` defaults to `DEFAULT_LIMIT`, which is what a reader actually sees, so the measurement
    is of the product rather than of a retriever configured for the test. It is unsourced
    itself (`Q59`) and therefore travels with every figure this returns.

    Raises on `k < 1` rather than clamping: a caller asking for recall@0 has a bug, and
    silently answering a different question than the one asked is how a metric starts
    reassuring people.

    **A pair's own `kind` narrows the search but not the corpus, deliberately.** An `S4` pair
    expecting a document that exists only as a `manual` scores a **miss**, not an exclusion —
    because `S4` restricting to `sop` is the product refusing to answer a safety question from
    a manufacturer's manual, and a labelled set that recorded that as *not applicable* would
    hide the one behaviour the restriction exists to produce.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, and this was called with {k}")

    documents = await index.approved_documents(kind)
    unapproved = await index.unapproved_count(kind)

    refusal = _corpus_refusal(k, documents, unapproved, labelled)
    if refusal is not None:
        return refusal

    results: list[QuestionResult] = []
    for pair in labelled.questions:
        found = await index.search(pair.question, kind=pair.kind or kind, limit=k)
        results.append(_score_one(pair, found, documents, k))

    common = {
        "k": k,
        "results": tuple(results),
        "corpus_documents": len(documents),
        "unapproved_in_corpus": unapproved,
        "labelled_set_source": labelled.source,
        "labelled_set_reviewed": labelled.is_reviewed,
    }

    if all(result.outcome is Outcome.UNAVAILABLE for result in results):
        return RetrievalReport(
            verdict=Verdict.SEARCH_UNAVAILABLE,
            reason=(
                "no question could be searched, so nothing was measured. This is a fact about "
                "the system rather than about the library, and reporting it as a score would "
                "assert the second while meaning the first"
            ),
            **common,
        )

    if not any(result.is_scored for result in results):
        return RetrievalReport(
            verdict=Verdict.LABELLED_SET_MISSES_THE_CORPUS,
            reason=(
                f"none of the {len(labelled.questions)} expected document(s) is in the approved "
                f"corpus of {len(documents)}, so nothing could be scored. This measures the "
                f"labelled set against the ingest, and says nothing about retrieval"
            ),
            **common,
        )

    return RetrievalReport(
        verdict=Verdict.MEASURED,
        reason=(
            f"measured over {sum(1 for r in results if r.is_scored)} scorable pair(s) at k={k} "
            f"against {len(documents)} approved document(s)"
        ),
        **common,
    )
