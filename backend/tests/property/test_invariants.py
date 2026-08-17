"""Properties over the whole input space — because every defect so far was the *neighbour*
of the case somebody chose to test.

Three real failures, all the same shape:

* `-25.6` is a substring of `-25.645`, so the numeric audit's containment check was toothless
  — and the unit test written to catch a truncated figure **passed against the broken
  version** for the whole of M1. One example, chosen by the person who wrote the bug.
* The evidence pack rendered chiller 1's failed condenser probe as `−273.2` with U+2212 and
  the model replied `-273.2`. The tokeniser read the first as *positive* 273.2, so the same
  figure appeared on the two sides as two different numbers and the honesty layer withheld a
  correct answer while reporting a fabrication. Found on the first real box run.
* Six "N/A" presses once opened a blocking gate with zero evidence, which is inherited
  constraint 8. `cannot_check` and `not_applicable` were the two answers nobody enumerated.

An example test asks *does it work here*. These ask *is there any input where it does not*,
and they enumerate rather than sample wherever the space is finite:

| Invariant | Constraint | Space |
|---|---|---|
| A `Figure` is a value **or** a stated absence, never both and never neither | 14 | all
  3 x 9 x 4 = 108 constructor combinations |
| No combination of findings opens a blocking gate unless every blocking item is `MEASURED` |
  8, 20 | all 6^3 and 6^4 answer vectors — 1,512 in total |
| No capability set clears a `NEVER_APPROVABLE` risk | `S1`, 13 | the full powerset of the
  Control Plane's seven capabilities, twice |
| Normalising a Unicode minus does not change which numbers are found | — | every glyph in
  `postcheck._WIDER_MINUS`, over the measured figures and the generated ones |

**Hypothesis is deliberately not used, and not installed.** `pip show hypothesis` reports
nothing, and adding a dependency to write a test is a poor trade when three of the four spaces
above are small enough to enumerate exhaustively — an exhaustive table is a *stronger* claim
than a sampled one, and it never shrinks a counter-example into a different bug. The fourth
space is unbounded, so it is generated with `random` under a **fixed seed**.

**Why the seed is fixed.** A generator seeded from the clock turns one latent defect into a
suite that fails on Tuesday and passes on Wednesday, and a gate that fails intermittently is a
gate people switch off — which is the failure mode `importlinter.ini` and `pytest.ini` are both
written around. Fixed, this file's verdict is a property of the code rather than of the day it
ran; a counter-example found here reproduces on every machine forever.
"""
from __future__ import annotations

import random
from itertools import chain, combinations, product

import pytest

from app.agents.postcheck import _NUMBER_RE, _WIDER_MINUS, _numbers_in
from app.analytics.honesty import Absence, Basis, Figure, Provenance
from app.domain.authority import NEVER_APPROVABLE, Action, Decision, Risk, rule
from app.domain.cases import (
    Capability,
    Checklist,
    ChecklistItem,
    Finding,
    FindingKind,
    may_advance,
)
from app.services.control_plane import Capability as ControlPlaneCapability

# ── harness parameters ──────────────────────────────────────────────────────────
#
# Neither of these is a measurement and neither describes the plant. They size a generator,
# and they are named rather than inlined so that a reader can see at a glance that no fact
# about the equipment is hiding in a literal.

#: The seed. Any constant would do; this is the date the suite was written. See the module
#: docstring for why it is fixed rather than drawn from the clock.
GENERATOR_SEED = 20260817

#: How many numbers the Unicode-minus property generates. Enough that a glyph the tokeniser
#: mishandles cannot hide behind a lucky draw, small enough that the file stays instant.
GENERATED_NUMBER_COUNT = 400


# ════════════════════════════════════════════════════════════════════════════════
# 1 · A Figure says one thing — constraint 14
# ════════════════════════════════════════════════════════════════════════════════
#
# The whole argument for the type is that "print a blank and move on" should be
# *unrepresentable* rather than discouraged, because an instruction is followed most of the
# time. That claim is only as strong as the constructor's refusals, so every combination is
# put through it rather than the two that were obviously wrong.

#: `0.0` is in here on purpose. It is the value most often mistaken for an absence, and
#: `cond_flow` — 0 non-zero readings in 37,430 measured slots — is exactly the signal where
#: rendering the absence as `0` would assert an instrument this site does not have.
_VALUES: tuple[float | None, ...] = (None, 0.0, -25.645)

_ABSENCES: tuple[str | None, ...] = (
    None,
    "",                              # falsy: says nothing, and must count as no reason
    Absence.NEVER_MEASURED,
    Absence.INSTRUMENT_INVALID,
    Absence.NOT_COMPUTABLE,
    Absence.NOT_DIAGNOSABLE,
    Absence.NO_DATA,
    Absence.NOT_MODELLED,
    "because_the_query_returned_nothing",   # unregistered: a reason nobody can render
)

_PROVENANCES: tuple[str, ...] = (
    Provenance.MEASURED,
    Provenance.SIMULATED,
    Provenance.NOT_INSTRUMENTED,
    "estimated_by_a_person",                # unregistered
)

_VALID_ABSENCES = frozenset(
    {
        Absence.NEVER_MEASURED,
        Absence.INSTRUMENT_INVALID,
        Absence.NOT_COMPUTABLE,
        Absence.NOT_DIAGNOSABLE,
        Absence.NO_DATA,
        Absence.NOT_MODELLED,
    }
)


def _figure_is_constructible(value: float | None, absence: str | None, provenance: str) -> bool:
    """The invariant restated independently of the code under test.

    Deliberately not a call into `__post_init__`. A predicate that asked the constructor
    whether the constructor was right would pass against any constructor at all.
    """
    stated_absence = bool(absence)
    if value is None and not stated_absence:
        return False           # neither: a blank
    if value is not None and stated_absence:
        return False           # both: two claims
    if stated_absence and absence not in _VALID_ABSENCES:
        return False           # a reason with no words to render
    return provenance in {Provenance.MEASURED, Provenance.SIMULATED, Provenance.NOT_INSTRUMENTED}


_FIGURE_SPACE = tuple(product(_VALUES, _ABSENCES, _PROVENANCES))


@pytest.mark.parametrize("value,absence,provenance", _FIGURE_SPACE)
def test_a_figure_is_a_value_or_a_stated_absence_and_never_both_or_neither(
    value: float | None, absence: str | None, provenance: str
) -> None:
    """Constraint 14, over all 108 constructor combinations rather than the obvious two.

    The type is the argument: an instruction not to print a blank is followed most of the
    time, and a constructor that refuses is followed always. This asserts the refusal covers
    the whole space — including the combinations nobody would write on purpose, which are
    the ones a serialiser or a `dataclasses.replace` reaches by accident.
    """
    should_construct = _figure_is_constructible(value, absence, provenance)

    if should_construct:
        figure = Figure(
            "condenser flow", value=value, absence=absence, provenance=provenance
        )
        assert figure.is_absent is (value is None)
        assert figure.render_value(), "a figure always renders something"
        return

    with pytest.raises(ValueError) as raised:
        Figure("condenser flow", value=value, absence=absence, provenance=provenance)
    assert str(raised.value).strip(), "a refusal carries its reason in words, never a bare raise"


def test_zero_is_a_value_and_never_reads_as_an_absence() -> None:
    """The single most consequential case in the space above, asserted on its own so that a
    parametrisation change can never quietly drop it.

    `cond_flow` records 0 non-zero values in 37,430 measured slots. A figure of `0.0` and a
    figure absent for `NEVER_MEASURED` are opposite claims — one says the meter read nothing,
    the other says there is no meter — and collapsing them asserts instrumentation this site
    does not have.
    """
    zero = Figure.measured("condenser flow", 0.0, "m3/h")
    never = Figure.never_measured("condenser flow", unit="m3/h")

    assert zero.is_absent is False
    assert never.is_absent is True
    assert never.render_value() == "never measured"
    assert "0" not in never.render_value() and "—" not in never.render_value()
    assert never.as_dict()["value"] is None


@pytest.mark.parametrize("absence", sorted(_VALID_ABSENCES))
def test_every_absence_reason_renders_words_rather_than_a_dash(absence: str) -> None:
    """A dash in a table reads as *nothing notable*, which is the opposite of what an absence
    means. Enumerated so a new reason cannot be added without words to go with it."""
    rendered = Figure.absent("condenser approach", absence).render_value()
    assert rendered.strip()
    assert rendered not in {"—", "-", "0", "n/a", "N/A"}
    assert any(c.isalpha() for c in rendered), "an absence renders words, never punctuation"


def test_no_constructor_can_produce_a_figure_that_is_both() -> None:
    """The classmethods are the supported route in, so the invariant is checked there too —
    a helper that bypassed `__post_init__` would make the whole space above irrelevant."""
    for figure in (
        Figure.measured("x", 1.5),
        Figure.derived("x", 1.5),
        Figure.judged("x", 1.5),
        Figure.simulated("x", 1.5),
        Figure.absent("x", Absence.NO_DATA),
        Figure.never_measured("x"),
    ):
        assert (figure.value is None) != (figure.absence is None), figure.label
        assert (figure.basis == Basis.ABSENT) is figure.is_absent


# ════════════════════════════════════════════════════════════════════════════════
# 2 · Only a measured reading opens a blocking gate — constraints 8 and 20
# ════════════════════════════════════════════════════════════════════════════════

#: A sixth answer the enum does not carry: **nobody recorded anything for this item at all**.
#: It has to be in the space because `may_advance` reads `findings.get(...)` and a missing key
#: is a different route to the gate than any recorded answer — and it is the route a partially
#: completed checklist actually takes.
_NO_FINDING_RECORDED = "no finding recorded"

_ANSWER_SPACE: tuple[object, ...] = (*FindingKind, _NO_FINDING_RECORDED)


def _checklist(blocking: int, advisory: int = 0) -> Checklist:
    """A checklist whose items are visible, so the SME gate is not what is being measured.

    `sme_reviewed=True` on every item deliberately: `visible_items` filters before
    `blocking_items` does, and a suite that left them unreviewed would assert the blocking
    rule against an empty list and pass for the wrong reason.
    """
    items = [
        ChecklistItem(
            id=f"blocking-{i}",
            text=f"measure the discharge pressure at test point {i}",
            capability=Capability.TECHNICIAN,
            blocking=True,
            sme_reviewed=True,
            is_sample=True,
        )
        for i in range(blocking)
    ] + [
        ChecklistItem(
            id=f"advisory-{i}",
            text=f"note the ambient conditions at point {i}",
            capability=Capability.OPERATOR,
            blocking=False,
            sme_reviewed=True,
            is_sample=True,
        )
        for i in range(advisory)
    ]
    return Checklist(fault_label="HIGH_HEAD_AMBIGUOUS", items=tuple(items))


def _findings(item_ids: tuple[str, ...], answers: tuple[object, ...]) -> dict[str, Finding]:
    return {
        item_id: Finding(item_id=item_id, kind=answer)
        for item_id, answer in zip(item_ids, answers, strict=True)
        if answer is not _NO_FINDING_RECORDED
    }


_THREE_BLOCKING = tuple(product(_ANSWER_SPACE, repeat=3))


@pytest.mark.parametrize("answers", _THREE_BLOCKING)
def test_no_combination_of_findings_opens_a_blocking_gate_without_a_measured_reading(
    answers: tuple[object, ...],
) -> None:
    """Constraints 8 and 20, over all 216 answer vectors across three blocking items.

    Both incidents behind those constraints were combinations nobody enumerated: six "N/A"
    presses opened a gate with zero evidence, and an untagged answer that defaulted to
    `estimated` opened one by a second route. Each was a single wrong branch inside a space
    this size, and each shipped.
    """
    checklist = _checklist(blocking=3)
    ids = tuple(item.id for item in checklist.blocking_items())
    opened, why = may_advance(checklist, _findings(ids, answers))

    every_answer_measured = all(a is FindingKind.MEASURED for a in answers)
    assert opened is every_answer_measured, (
        f"answers {[getattr(a, 'value', a) for a in answers]} produced opened={opened}; "
        f"only an all-measured vector may open a blocking gate"
    )
    assert why.strip(), "the verdict carries its reason in words, open or shut"

    if not opened:
        assert "no measured answer" in why
        unsettled = sum(1 for a in answers if a is not FindingKind.MEASURED)
        assert f"{unsettled} blocking item(s)" in why


@pytest.mark.parametrize(
    "kind", [k for k in FindingKind if k is not FindingKind.MEASURED]
)
def test_a_single_unmeasured_answer_shuts_the_gate_however_many_others_are_measured(
    kind: FindingKind,
) -> None:
    """The failure this prevents is a *majority* rule creeping in — three measured readings
    out of four reading as good enough. Constraint 8 has no quorum in it: one unsettled
    blocking item is the whole verdict."""
    checklist = _checklist(blocking=4)
    ids = tuple(item.id for item in checklist.blocking_items())
    answers = (FindingKind.MEASURED, FindingKind.MEASURED, FindingKind.MEASURED, kind)

    opened, why = may_advance(checklist, _findings(ids, answers))
    assert opened is False
    assert kind.value in why, "the reason names the answer that held it, not just a count"


_TWO_BLOCKING_TWO_ADVISORY = tuple(product(_ANSWER_SPACE, repeat=4))


@pytest.mark.parametrize("answers", _TWO_BLOCKING_TWO_ADVISORY)
def test_an_advisory_answer_can_neither_open_nor_shut_a_blocking_gate(
    answers: tuple[object, ...],
) -> None:
    """All 1,296 vectors across two blocking and two advisory items.

    Two opposite defects live here and only an enumeration catches both: an advisory
    *cannot-check* dragging a satisfied gate shut, and an advisory *measured* reading being
    counted towards a blocking item it has nothing to do with. The second is the dangerous
    one — it opens a gate on evidence about a different question.
    """
    checklist = _checklist(blocking=2, advisory=2)
    blocking_ids = tuple(i.id for i in checklist.blocking_items())
    advisory_ids = tuple(i.id for i in checklist.visible_items() if not i.blocking)

    findings = _findings(blocking_ids + advisory_ids, answers)
    opened, _ = may_advance(checklist, findings)

    blocking_answers = answers[: len(blocking_ids)]
    assert opened is all(a is FindingKind.MEASURED for a in blocking_answers), (
        "the advisory answers changed the blocking verdict"
    )


def test_a_checklist_with_no_visible_blocking_item_advances_and_that_is_the_sme_gate() -> None:
    """**The current behaviour, documented rather than asserted as desirable — `Q81`.**

    `blocking_items` reads `visible_items`, so a class whose blocking items are all
    unreviewed presents no blocking item at all and `may_advance` returns `True` with the
    words *"every blocking item has a measured answer"*. Today nothing reaches that path:
    `app/services/cases.py` builds cases from sample items that carry `sme_reviewed=True`,
    and the 124-item curated library is never shown to anyone.

    It is written down because the wording would be false the moment the library is reviewed
    in part — 24 of the 124 items are blocking, and a half-reviewed class would advance on a
    sentence claiming measurements that were never taken. `Q81` asks whether the reason
    should name the review backlog instead.
    """
    unreviewed = Checklist(
        fault_label="HIGH_HEAD_AMBIGUOUS",
        items=(
            ChecklistItem(
                id="lib-blocking-1",
                text="measure the oil pressure differential",
                blocking=True,
                sme_reviewed=False,
            ),
        ),
    )
    opened, why = may_advance(unreviewed, {})
    assert opened is True
    assert why.strip(), "even the permissive verdict states its reason"


# ════════════════════════════════════════════════════════════════════════════════
# 3 · No capability set clears a never-approvable risk — S1, constraint 13
# ════════════════════════════════════════════════════════════════════════════════

#: The Control Plane's real vocabulary, read from the enum rather than restated. A hand-typed
#: list would stop matching the moment a capability is added, and the powerset below would
#: then be proving something about a set nobody holds.
_CAPABILITY_VOCABULARY: tuple[str, ...] = tuple(
    sorted(c.value for c in ControlPlaneCapability)
)


def _powerset(items: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    return tuple(
        frozenset(subset)
        for subset in chain.from_iterable(
            combinations(items, n) for n in range(len(items) + 1)
        )
    )


_ALL_CAPABILITY_SETS = _powerset(_CAPABILITY_VOCABULARY)


@pytest.mark.parametrize("risk", sorted(NEVER_APPROVABLE))
@pytest.mark.parametrize(
    "held", _ALL_CAPABILITY_SETS, ids=[f"n{len(s)}-{'+'.join(sorted(s)) or 'none'}"
                                       for s in _ALL_CAPABILITY_SETS]
)
def test_no_capability_set_in_the_powerset_clears_a_never_approvable_risk(
    risk: Risk, held: frozenset[str]
) -> None:
    """`S1`, over every one of the 128 subsets rather than over the two personas somebody
    thought of.

    `SAFETY_CRITICAL` is a *kind*, not the top of a scale — if it were merely the highest
    level, a sufficiently equipped identity would clear it, which is the reading `S1` exists
    to prevent. The powerset includes the set holding everything, which is the shape of that
    misreading.
    """
    ruling = rule(Action(name="stop_the_machine", risk=risk), held)

    assert ruling.decision is Decision.REFUSED
    assert ruling.may_proceed is False
    assert ruling.is_refusal is True
    assert "no approval clears it" in ruling.reason
    assert ruling.required_capability == "", (
        "naming a capability on a refusal would read as 'find someone who holds this'"
    )


def test_the_powerset_is_not_vacuous_because_an_approvable_risk_is_cleared_by_some_of_it() -> None:
    """A suite that enumerated an empty or wrongly-built space would pass every assertion
    above while proving nothing. This is the control: the same powerset must contain sets that
    *do* clear a `HIGH` action, and sets that do not."""
    high = Action(name="approve_a_job", risk=Risk.HIGH)
    outcomes = {rule(high, held).may_proceed for held in _ALL_CAPABILITY_SETS}
    assert outcomes == {True, False}, "the powerset does not discriminate; it is not a space"


@pytest.mark.parametrize("held", _ALL_CAPABILITY_SETS[:16])
def test_every_ruling_over_the_powerset_states_its_reason(held: frozenset[str]) -> None:
    """A refusal is not an error and an absence is not a dash. Whatever the engine concludes,
    the words come with it — `Ruling.reason` empty would leave an interface with a verdict and
    nothing to render beside it."""
    for risk in Risk:
        ruling = rule(Action(name="an_action", risk=risk), held)
        assert ruling.reason.strip(), f"{risk.value} with {sorted(held)} produced no reason"
        assert ruling.decision in set(Decision)


# ════════════════════════════════════════════════════════════════════════════════
# 4 · Normalising a Unicode minus does not change which numbers are found
# ════════════════════════════════════════════════════════════════════════════════
#
# The defect this guards was found on the first real box run and is worse than the one the
# audit exists for: a fabricated number is caught by a reader who checks, but a *false*
# accusation of fabrication silently suppresses a correct answer and nobody looks at what was
# withheld.

#: Every glyph the normaliser folds **to a minus**. Derived from the table rather than
#: restated, so a new dash added there is covered here without an edit and a removed one fails
#: this file. Restating it would also rot: the table was renamed and widened from four entries
#: to eight the same day this suite was written, and a hand-typed list would have gone stale
#: while still passing.
_MINUS_GLYPHS: tuple[str, ...] = tuple(
    chr(codepoint) for codepoint, folded in _WIDER_MINUS.items() if folded == "-"
)

#: The entries that fold to **nothing** — a soft hyphen renders as no glyph at all and splits
#: a number in two. They are excluded above because there is no sign for them to preserve, and
#: they get their own property below rather than being dropped from the file.
_VANISHING_GLYPHS: tuple[str, ...] = tuple(
    chr(codepoint) for codepoint, folded in _WIDER_MINUS.items() if folded == ""
)

#: The figures this actually happened to, from `CONTEXT.md` §10a and the honesty layer.
_MEASURED_FIGURES: tuple[str, ...] = (
    "-273.2",     # cond_leaving_temp, the sensor reporting its own failure
    "-25.645",    # chiller 1's healthy residual median
    "-6265",      # the floor of kw_per_tr on chiller 1
    "-3.4",       # the condenser delta-T that is negative every month
    "-38.677",    # the lower edge of chiller 1's reference band
)


def _generated_negatives() -> tuple[str, ...]:
    """Negative numbers under the fixed seed. See the module docstring for why it is fixed."""
    rng = random.Random(GENERATOR_SEED)
    out: list[str] = []
    while len(out) < GENERATED_NUMBER_COUNT:
        magnitude = rng.uniform(0.001, 50_000.0)
        places = rng.choice((0, 1, 2, 3))
        token = f"-{magnitude:.{places}f}"
        # `-0`, `-0.0` and friends are excluded: the tokeniser is being asked whether the
        # *sign* survived translation, and a magnitude of zero has no sign to lose.
        if float(token) != 0.0:
            out.append(token)
    return tuple(out)


_NEGATIVE_TOKENS: tuple[str, ...] = _MEASURED_FIGURES + _generated_negatives()


def _numbers_without_translation(text: str) -> list[str]:
    """The tokeniser as it behaved *before* `_WIDER_MINUS` existed.

    Present so the property below cannot pass vacuously. If this shim and the real function
    agreed on every input, the assertions would be proving nothing at all.
    """
    return [m.group(0).rstrip(".").replace(",", "") for m in _NUMBER_RE.finditer(text)]


@pytest.mark.parametrize("glyph", _MINUS_GLYPHS)
def test_the_minus_glyph_a_figure_is_written_with_does_not_change_which_numbers_are_found(
    glyph: str,
) -> None:
    """The measured incident, generalised: the pack said `−273.2` and the answer said
    `-273.2`, and the tokeniser called them different numbers.

    Asserted over every negative figure in the generated set rather than over the one that
    was reported. The repository's typography is deliberate — `ruff.toml` keeps
    `RUF001`/`RUF002` off because the documents use U+2212 and a docstring quoting a measured
    fact should quote it exactly — so the pack side of every comparison genuinely carries
    these characters.
    """
    for ascii_token in _NEGATIVE_TOKENS:
        typeset = glyph + ascii_token[1:]
        sentence = "the residual median for this asset is {} kW over the window"

        found_ascii = _numbers_in(sentence.format(ascii_token))
        found_typeset = _numbers_in(sentence.format(typeset))

        assert found_ascii == found_typeset, (
            f"{typeset!r} tokenised as {found_typeset} and {ascii_token!r} as {found_ascii}; "
            f"the same figure must not read as two different numbers"
        )
        assert found_ascii == [ascii_token], "the sign is part of the number, not decoration"


@pytest.mark.parametrize("glyph", _MINUS_GLYPHS)
def test_the_untranslated_tokeniser_really_does_get_this_wrong(glyph: str) -> None:
    """The control. Without the translation table a typeset figure loses its sign and reads as
    a positive number of the same magnitude — which is how the honesty layer came to report a
    fabrication against an answer that had quoted the evidence correctly."""
    typeset = glyph + "273.2"
    assert _numbers_without_translation(typeset) == ["273.2"]
    assert _numbers_in(typeset) == ["-273.2"]


def test_a_typeset_range_survives_translation_intact() -> None:
    """`kw_per_tr` on chiller 1 is quoted as a range — −6,265 to +30,183 — and it is written
    with a typeset minus, a thousands separator and a leading plus in the same phrase. All
    three formatting habits meet in one string, which is where a tokeniser breaks."""
    typeset = "kw_per_tr ranges from −6,265 to +30,183 on this machine"
    ascii_text = "kw_per_tr ranges from -6,265 to +30,183 on this machine"
    assert _numbers_in(typeset) == _numbers_in(ascii_text) == ["-6265", "30183"]


@pytest.mark.parametrize("glyph", _VANISHING_GLYPHS)
def test_a_glyph_that_renders_as_nothing_does_not_split_one_number_into_two(
    glyph: str,
) -> None:
    """A soft hyphen is invisible on screen and inside a token. Left in, `-25.645` tokenises
    as two numbers, so a figure quoted exactly reads as two the pack never contained — the
    false-accusation failure again, arriving through a character nobody can see.

    These glyphs are folded away rather than to a minus, which is why they are not in the sign
    property above. Asserting them here rather than skipping them keeps the whole table
    covered: an entry nobody tests is an entry that can be deleted without a failure.
    """
    for token in _MEASURED_FIGURES:
        split = token[:3] + glyph + token[3:]
        assert _numbers_in(split) == [token], (
            f"an invisible glyph inside {token!r} produced {_numbers_in(split)}"
        )


@pytest.mark.parametrize("glyph", _MINUS_GLYPHS)
def test_translation_never_invents_a_number_that_was_not_there(glyph: str) -> None:
    """The reverse direction, which matters as much: a glyph used as *punctuation* — an em
    dash between clauses — must not attach itself to the number after it and turn a positive
    figure negative. That would make the audit accuse the model of a number nobody wrote."""
    found = _numbers_in(f"the band holds {glyph} and the median is 48.03 nRMSE")
    assert found == ["48.03"], f"{glyph!r} used as punctuation changed the reading to {found}"
