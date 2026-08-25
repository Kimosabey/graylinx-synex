"""`RC1`, `RC3`, `RC4`, `RC5`, `RC7`, `RC10`, `RC15`, `RC16` — the deterministic core of M2.

Every test here corresponds to a failure that actually happened on the reference plant. The
three that matter most:

- **Six "N/A" presses once opened a blocking gate with zero evidence behind it.** So
  `cannot_check` and `not_applicable` are different kinds, and neither settles a blocking
  item.
- **An untagged answer defaulted to `estimated` and opened a blocking gate.** Constraint 20,
  which is constraint 8's failure arriving by a second route. Only a measured reading settles.
- **A filter-drier restriction was routed to a supervisor** because one incidental records
  question outranked three refrigeration measurements. So assignment is by workload, never
  by seniority.
"""
from __future__ import annotations

import pytest

from app.domain.cases import (
    Capability,
    CaseState,
    Checklist,
    ChecklistItem,
    Finding,
    FindingKind,
    can_transition,
    may_advance,
    operator_can_start,
)
from app.domain.escalation import (
    Artefact,
    Blocker,
    Candidate,
    choose_assignee,
    inspection_tasks,
    route_for,
)


def _item(id_: str, **kw) -> ChecklistItem:
    kw.setdefault("sme_reviewed", True)
    return ChecklistItem(id=id_, text=f"check {id_}", **kw)


# ── RC1: the state machine ─────────────────────────────────────────────────────

def test_a_case_cannot_close_without_passing_through_actioned() -> None:
    """`W9`. The only route to closed runs through work being done and then proved."""
    assert not can_transition(CaseState.DETECTED, CaseState.CLOSED)
    assert not can_transition(CaseState.AWAITING_FINDINGS, CaseState.CLOSED)
    assert not can_transition(CaseState.ROOT_CAUSED, CaseState.CLOSED)
    assert can_transition(CaseState.ACTIONED, CaseState.CLOSED)


def test_closed_is_terminal() -> None:
    assert can_transition(CaseState.CLOSED, CaseState.CLOSED) is False
    assert not any(can_transition(CaseState.CLOSED, s) for s in CaseState)


def test_actioned_can_return_to_awaiting_findings() -> None:
    """`W10`. A failed verification reopens rather than closing, and the previous findings
    are what the next technician starts from."""
    assert can_transition(CaseState.ACTIONED, CaseState.AWAITING_FINDINGS)


def test_every_state_can_go_stale_except_closed() -> None:
    """`RC9`. Four open cases once described transmitters repaired weeks earlier."""
    for state in CaseState:
        if state in (CaseState.CLOSED, CaseState.STALE):
            continue
        assert can_transition(state, CaseState.STALE), state


# ── RC5 and RC10: only a measured reading settles a blocking item ──────────────

def test_an_estimate_does_not_settle_a_blocking_check() -> None:
    """Constraint 20. On the reference plant an untagged answer defaulted to estimated and
    opened a blocking gate."""
    checklist = Checklist("X", (_item("b1", blocking=True),))
    ok, why = may_advance(checklist, {"b1": Finding("b1", FindingKind.ESTIMATED)})
    assert not ok
    assert "estimated" in why


@pytest.mark.parametrize(
    "kind",
    [FindingKind.CANNOT_CHECK, FindingKind.NOT_APPLICABLE, FindingKind.NOT_ANSWERED],
)
def test_no_non_measured_answer_opens_a_blocking_gate(kind: FindingKind) -> None:
    """Constraint 8: six "N/A" presses once opened a blocking gate with zero evidence."""
    checklist = Checklist("X", (_item("b1", blocking=True),))
    ok, _ = may_advance(checklist, {"b1": Finding("b1", kind)})
    assert not ok


def test_a_measured_reading_settles_it() -> None:
    checklist = Checklist("X", (_item("b1", blocking=True),))
    ok, why = may_advance(checklist, {"b1": Finding("b1", FindingKind.MEASURED, "4.2")})
    assert ok
    assert "measured" in why


def test_cannot_check_is_a_different_kind_from_not_applicable() -> None:
    """They mean different things: one is about the person, the other about the machine.
    Collapsing them is how a safety gate gets walked past."""
    assert FindingKind.CANNOT_CHECK is not FindingKind.NOT_APPLICABLE
    assert not Finding("i", FindingKind.CANNOT_CHECK).settles_a_blocking_item
    assert not Finding("i", FindingKind.NOT_APPLICABLE).settles_a_blocking_item


def test_non_blocking_items_never_hold_the_case() -> None:
    checklist = Checklist("X", (_item("n1"), _item("n2")))
    ok, _ = may_advance(checklist, {})
    assert ok


# ── RC3: capabilities, and the check that collapses ───────────────────────────

def test_a_check_the_reader_cannot_perform_is_not_in_their_list() -> None:
    """Constraint 38: it collapses, it does not grey out. A greyed-out "oil analysis — acid,
    moisture, metals" still reads as a demand on whoever is standing there."""
    checklist = Checklist(
        "X",
        (
            _item("op1", capability=Capability.OPERATOR),
            _item("lab1", capability=Capability.VENDOR),
        ),
    )
    for_operator = checklist.for_capability(Capability.OPERATOR)
    assert [i.id for i in for_operator] == ["op1"]
    assert [i.id for i in checklist.blocked_for(Capability.OPERATOR)] == ["lab1"]


def test_an_untagged_item_defaults_to_technician() -> None:
    """Constraint 24, and the asymmetry is deliberate: mis-tagging a technician task as
    operator puts an unqualified person on a pressurised circuit. Over-escalating is the
    cheap error."""
    assert ChecklistItem("i", "text").capability is Capability.TECHNICIAN


def test_every_class_must_leave_the_operator_something_to_do() -> None:
    """Constraint 37: otherwise somebody starts stuck rather than getting stuck partway."""
    with_operator = Checklist("X", (_item("op1", capability=Capability.OPERATOR),))
    without = Checklist("X", (_item("t1", capability=Capability.TECHNICIAN),))
    assert operator_can_start(with_operator)
    assert not operator_can_start(without)


# ── the SME gate: nothing unreviewed reaches a user ───────────────────────────

def test_unreviewed_items_are_counted_but_never_shown() -> None:
    """131 items, none reviewed by a refrigeration engineer. The gate is on the library,
    not on the milestone — which is what lets M2 proceed before the SME hour."""
    checklist = Checklist(
        "X",
        (
            ChecklistItem("a", "reviewed", sme_reviewed=True),
            ChecklistItem("b", "not reviewed"),
            ChecklistItem("c", "not reviewed"),
        ),
    )
    assert [i.id for i in checklist.visible_items()] == ["a"]
    assert checklist.unreviewed_count == 2


def test_review_defaults_to_false() -> None:
    """The safe default. An unreviewed instruction directing physical work on pressurised
    refrigerant equipment is the risk constraint 1 names."""
    assert ChecklistItem("i", "text").sme_reviewed is False


def test_an_unreviewed_blocking_item_cannot_hold_a_case_it_is_invisible_in() -> None:
    """A hidden item must not block. Otherwise the case stalls for a reason nobody can see."""
    checklist = Checklist("X", (ChecklistItem("b", "hidden", blocking=True),))
    ok, _ = may_advance(checklist, {})
    assert ok


# ── RC7 and RC15: three routes, three artefacts ───────────────────────────────

def test_no_tool_raises_an_inspection_work_order_for_a_technician() -> None:
    route = route_for(Blocker.NO_TOOL)
    assert route.goes_to is Capability.TECHNICIAN
    assert route.artefact is Artefact.INSPECTION_WORK_ORDER
    assert route.case_state is CaseState.ESCALATED
    assert not route.task_is_a_question


def test_no_authority_raises_an_authorisation_work_order_whose_task_is_a_question() -> None:
    """Handing a supervisor a measurement task is how the wrong person ends up at a gauge."""
    route = route_for(Blocker.NO_AUTHORITY)
    assert route.goes_to is Capability.SUPERVISOR
    assert route.artefact is Artefact.AUTHORISATION_WORK_ORDER
    assert route.task_is_a_question
    assert route.lands_unassigned


def test_the_wrong_moment_calls_nobody() -> None:
    route = route_for(Blocker.WRONG_MOMENT)
    assert route.goes_to is None
    assert route.artefact is Artefact.NONE
    assert route.case_state is CaseState.DEFERRED


def test_not_sure_changes_nothing_at_all() -> None:
    """Constraint 30: "can't tell" must have no effect, or uncertainty silently eliminates
    something."""
    route = route_for(Blocker.NOT_SURE)
    assert route.case_state is None
    assert route.artefact is Artefact.NONE
    assert route.goes_to is None


def test_the_three_routes_produce_three_different_outcomes() -> None:
    """Constraint 9: they are not interchangeable, and one "escalate" button loses the
    distinction that decides who gets called and what they are handed."""
    outcomes = {
        (r.goes_to, r.artefact, r.case_state)
        for r in (
            route_for(Blocker.NO_TOOL),
            route_for(Blocker.NO_AUTHORITY),
            route_for(Blocker.WRONG_MOMENT),
        )
    }
    assert len(outcomes) == 3


def test_the_inspection_job_carries_the_open_checks_themselves() -> None:
    """Not a summary of them. The technician should not have to work out what was already
    established."""
    items = (_item("a"), _item("b"))
    assert inspection_tasks(items) == ("check a", "check b")


# ── RC16: assignment by workload, never by seniority ──────────────────────────

def test_the_least_loaded_eligible_person_is_chosen() -> None:
    candidates = (
        Candidate("Priya", Capability.TECHNICIAN, open_items=5),
        Candidate("Sam", Capability.TECHNICIAN, open_items=1),
        Candidate("Alex", Capability.SUPERVISOR, open_items=0),
    )
    assert choose_assignee(candidates, Capability.TECHNICIAN).name == "Sam"


def test_blocking_items_count_double() -> None:
    """They are what actually stops other cases moving."""
    candidates = (
        Candidate("Priya", Capability.TECHNICIAN, open_items=3),
        Candidate("Sam", Capability.TECHNICIAN, open_items=2, open_blocking_items=2),
    )
    assert choose_assignee(candidates, Capability.TECHNICIAN).name == "Priya"


def test_ties_break_toward_whoever_can_measure() -> None:
    """Constraint 25."""
    candidates = (
        Candidate("Priya", Capability.TECHNICIAN, open_items=2, can_measure=False),
        Candidate("Sam", Capability.TECHNICIAN, open_items=2, can_measure=True),
    )
    assert choose_assignee(candidates, Capability.TECHNICIAN).name == "Sam"


def test_assignment_is_stable_regardless_of_input_order() -> None:
    """*"Why this person"* must be answerable from the data, not from list order."""
    a = Candidate("Priya", Capability.TECHNICIAN, open_items=2, can_measure=True)
    b = Candidate("Sam", Capability.TECHNICIAN, open_items=2, can_measure=True)
    assert choose_assignee((a, b), Capability.TECHNICIAN).name == "Priya"
    assert choose_assignee((b, a), Capability.TECHNICIAN).name == "Priya"


def test_no_eligible_candidate_returns_none_rather_than_the_nearest_person() -> None:
    """Assigning outside the capability is how an unqualified person reaches a pressurised
    circuit."""
    assert choose_assignee((Candidate("Alex", Capability.SUPERVISOR),), Capability.VENDOR) is None


# ── nothing here may reach a model ────────────────────────────────────────────

def test_the_case_machine_never_calls_a_model() -> None:
    """`RC1` is SW + R. A prompt change must not be able to alter a state transition."""
    import pathlib

    from app.domain import cases, escalation

    for module in (cases, escalation):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        # Code patterns, not prose. Both modules discuss prompts in their docstrings — that
        # is them explaining why they do not use one, and a grep that punished the
        # explanation would train people to stop writing it.
        code = " ".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        for banned in ("app.llm", "ModelClient", "import openai", "langchain"):
            assert banned not in code, f"{module.__name__} reaches {banned}"
