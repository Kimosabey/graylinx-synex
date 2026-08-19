"""The mode that turns a refusal into the product, and the line it must not cross."""
from __future__ import annotations

from app.agents import hypothesise
from app.domain import differential as diff


def test_an_undecidable_class_gets_a_hypothesis() -> None:
    """The four classes that admit in their names they cannot resolve are the point."""
    for label in diff.DIFFERENTIALS:
        got = hypothesise.for_fault(label, equipment_display="Chiller 1")
        assert got is not None, f"{label} declares itself undecidable and has no hypothesis"
        assert got.cause_count > 1


def test_a_class_that_names_a_mechanism_gets_none() -> None:
    """**`None` is not a hedge, and the caller reports it in its own words.**

    A class naming a mechanism does not need a differential, and a class that declares itself
    undecidable with no candidate set authored is missing content. Two different facts.
    """
    assert hypothesise.for_fault("CONDENSER_LOW_FLOW", equipment_display="Chiller 1") is None
    assert hypothesise.for_fault(None, equipment_display="Chiller 1") is None
    assert hypothesise.for_fault("", equipment_display="Chiller 1") is None


def test_the_causes_are_named_and_the_machine_with_them() -> None:
    got = hypothesise.for_fault("HIGH_HEAD_AMBIGUOUS", equipment_display="Chiller 1")
    assert got is not None
    rendered = got.render()
    assert "Chiller 1" in rendered
    assert "HIGH_HEAD_AMBIGUOUS" in rendered
    assert "Condenser tubes fouled" in rendered
    assert f"{got.cause_count} causes could produce this" in rendered


def test_it_says_the_class_cannot_be_resolved_from_readings() -> None:
    """The sentence that stops a differential reading as a failure.

    "That is what its name says" is the whole framing: the model was honest, the platform is
    carrying that honesty forward, and neither is broken.
    """
    got = hypothesise.for_fault("HIGH_HEAD_AMBIGUOUS", equipment_display="Chiller 1")
    assert got is not None
    rendered = got.render()
    assert "cannot be resolved from the readings alone" in rendered
    assert "It does not mean nothing is known" in rendered


def test_no_check_is_put_to_anybody_until_one_is_reviewed() -> None:
    """**The state today, and it is a worse product on purpose.**

    Thirty-one causes were once eliminated on the reference queue by discriminators nobody had
    read. An elimination is a door that closes, so `askable` returns only SME-reviewed
    questions — and none is. The checks are still named, because naming what exists is what
    makes the ask to an engineer concrete.
    """
    got = hypothesise.for_fault("HIGH_HEAD_AMBIGUOUS", equipment_display="Chiller 1")
    assert got is not None
    assert got.has_reviewed_check is False

    rendered = got.render()
    assert "checks exist that would separate these" in rendered
    assert "has been reviewed by a refrigeration engineer" in rendered
    assert "pressurised circuit" in rendered


def test_it_never_names_one_cause_as_the_answer() -> None:
    """**The line this mode must not cross.**

    A differential that leant toward a cause would be a diagnosis wearing a hedge — and the
    rules, not the prose, decide what a fault is.
    """
    got = hypothesise.for_fault("HIGH_HEAD_AMBIGUOUS", equipment_display="Chiller 1")
    assert got is not None
    rendered = got.render().lower()
    for forbidden in ("most likely", "probably", "the cause is", "we believe", "suggests that"):
        assert forbidden not in rendered


def test_it_states_that_this_is_a_finding_rather_than_a_gap() -> None:
    """Exhausted is a result. A reader told only that it stopped hears a failure."""
    got = hypothesise.for_fault("HIGH_HEAD_AMBIGUOUS", equipment_display="Chiller 1")
    assert got is not None
    assert "a finding, not a gap in the answer" in got.render()
