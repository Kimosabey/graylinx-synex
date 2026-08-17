"""`U8` administrator scope, the approval matrix and the policy version.

Three things this surface has to say out loud, and a governance screen that says none of them
is worse than no governance screen at all — it is an authoritative-looking record of who may
act on a live plant, and every line of it is false in a way the reader cannot see.

**The identity.** `gl_user`, `gl_role` and `gl_access` hold zero rows and there is no
authentication library in the back end (`Q41`). Every identity is a demonstration persona and
`is_production_identity` is hard-wired `False`. An approval matrix printed without that line
would be the most misleading screen in the product.

**The matrix.** Inherited constraints 13 and 25. Ranking capability by seniority once sent a
filter-drier restriction to a supervisor, because one incidental records question outranked
three refrigeration measurements. So a row maps a risk level to a *named capability*, never to
a persona standing above another one. The reference plant's own role tags are the reason this
is not a hypothetical: 124 curated checklist items carry them, exactly one review pass over one
class has ever been run, and it found an oil analysis — acid number, moisture, metals — being
shown to whoever opened a compressor case.

**The dry run that does not exist.** `G8` policy versioning and simulation is Phase 3, so a
change to scope or to the matrix takes effect the first time it is applied. Silence about a dry
run reads as a dry run having happened, which is why the absence is words on the screen rather
than an omission from it.

Two defects were found while writing these tests and fixed in `app/services/policy.py`; the
tests that found them are marked in place.
"""
from __future__ import annotations

import dataclasses

import pytest

from app.domain import authority
from app.domain.authority import Decision, Risk, Ruling
from app.services import control_plane, policy
from app.services.control_plane import IDENTITY_KIND, Capability, Persona, compute_scope
from app.services.policy import (
    NEVER_APPROVABLE_BECAUSE,
    NO_DRY_RUN,
    NOT_AVAILABLE,
    ORDER_NOTE,
    AdministratorView,
    MissingCapability,
    PolicyChange,
    PolicyVersion,
    Requirement,
    administrator_view,
    approval_matrix,
    capability_holders,
    ordering_report,
    persona_capabilities,
    ruling_on,
)

#: Date-and-counter shaped, and deliberately never parsed. `Q74` — no document states the
#: scheme or what advances it, so nothing in the module compares two of them.
VERSION = "2026-08-13.1"

A_CHANGE = PolicyChange(
    what_changes="who may approve a high-risk dispatch",
    reason="the supervisor queue is the only route to a work order and one person holds it.",
    supersedes="approve_work held by Supervisor",
    becomes="approve_work held by Supervisor and Reliability Engineer",
)


def _view() -> AdministratorView:
    return administrator_view(VERSION)


# ── Q41: the identity kind, before anything else on the screen ─────────────────

def test_the_surface_states_that_the_identity_is_not_a_production_one() -> None:
    """Every other line on this screen is only as true as the identity behind it, and the
    identity is a switcher anyone reaching the page can turn. A matrix presented without that
    sentence is a record of who may act on a live plant, and it is not one."""
    view = _view()
    assert view.identity_kind == IDENTITY_KIND == "demonstration_persona"
    assert view.is_production_identity is False
    assert "Q41" in view.identity_note


def test_the_identity_line_comes_before_the_rules_it_qualifies() -> None:
    """A disclaimer under the matrix is read after the matrix has already been believed. The
    order is load-bearing, not tidiness."""
    rendered = _view().render()
    assert rendered.startswith(_view().identity_note)
    assert rendered.index(IDENTITY_KIND) < rendered.index("policy version")


def test_the_identity_note_says_the_kind_cannot_be_changed_by_a_setting() -> None:
    """`Q41` is unanswered and D-013 made this a labelled persona switcher instead. The danger
    with a stand-in is that it stops being one, so the screen names the mechanism rather than
    hedging: zero rows in `gl_user`, `gl_role` and `gl_access`."""
    note = _view().identity_note
    assert "cannot become one from a setting" in note
    assert "gl_user" in note


def test_a_view_claiming_a_production_identity_kind_still_reports_false() -> None:
    """Hard-wired means hard-wired. If `is_production_identity` were derived from the field, a
    caller constructing the view could assert production identity into existence on the one
    screen where getting it wrong is worst."""
    view = dataclasses.replace(_view(), identity_kind="corporate_sso")
    assert view.is_production_identity is False
    assert view.as_dict()["is_production_identity"] is False


def test_the_identity_kind_travels_with_the_serialised_surface() -> None:
    """A web surface that had to rebuild the sentence from a flag would eventually not."""
    payload = _view().as_dict()
    assert payload["identity_kind"] == IDENTITY_KIND
    assert "Q41" in payload["identity_note"]


# ── the approval matrix is data, and it maps risk to a named capability ────────

def test_every_risk_level_has_a_row_and_the_order_is_the_engines_own() -> None:
    """A level missing from the matrix is a level a reader assumes needs no approval. Row order
    follows `Risk`'s declaration so the table cannot fall out of step with the enum."""
    rows = approval_matrix()
    assert tuple(row.risk for row in rows) == tuple(Risk)


def test_a_row_names_a_capability_and_never_a_persona() -> None:
    """Constraint 13, stated as a type check on the data. The requirement a row carries is a
    capability the Control Plane defines — `open_case`, `approve_work` — and never a persona
    value, because `persona >= SUPERVISOR` is how the filter-drier restriction was routed."""
    capabilities = {c.value for c in Capability}
    personas = {p.value for p in Persona}
    for row in approval_matrix():
        if row.requirement is Requirement.NAMED_CAPABILITY:
            assert row.required_capability in capabilities
            assert row.required_capability not in personas


def test_whoever_clears_the_high_row_cannot_clear_the_medium_one() -> None:
    """The sharpest available proof that the matrix is not an ordering of personas. Under a
    seniority ladder, whoever clears `HIGH` clears everything beneath it. Here the Supervisor
    holds `approve_work` and not `open_case`, so the two rows name disjoint sets of people —
    which no ranking can produce."""
    rows = {row.risk: row for row in approval_matrix()}
    medium, high = rows[Risk.MEDIUM], rows[Risk.HIGH]

    assert medium.holders and high.holders
    assert set(medium.holders).isdisjoint(high.holders), (
        "a persona clearing both rows means seniority has crept back into the matrix"
    )
    assert "Supervisor" in high.holders
    assert "Supervisor" not in medium.holders


def test_the_holders_are_derived_from_the_control_plane_not_written_here() -> None:
    """`CLAUDE.md` §2.8: one source of truth per fact. The holders come from `compute_scope`,
    the same call a live turn makes, so a capability granted in the Control Plane appears on
    this screen without an edit and the two cannot disagree about who may approve what."""
    holders = capability_holders()
    for capability, names in holders.items():
        granted = {
            compute_scope(p).identity.display_name
            for p in Persona
            if Capability(capability) in compute_scope(p).capabilities
        }
        assert set(names) == granted

    assert set(holders) == {c.value for c in Capability}, (
        "an ungranted capability must appear with an empty holder list, not vanish"
    )


def test_a_never_approvable_row_says_it_does_not_travel_upwards() -> None:
    """`SAFETY_CRITICAL` is a different kind, not the top of a scale. Left as an empty approval
    cell it would read as *nobody senior enough has been found yet*, which is exactly the
    reading `S1` exists to prevent — the platform stops and does not weigh the risk itself."""
    rows = {row.risk: row for row in approval_matrix()}
    safety = rows[Risk.SAFETY_CRITICAL]

    assert safety.requirement is Requirement.NO_APPROVAL_CLEARS_IT
    assert safety.required_capability == ""
    assert "does not travel up to a more senior approver" in safety.who
    assert "S6" in safety.who


def test_the_two_never_approvable_levels_keep_their_own_reasons() -> None:
    """Unrelated reasons. `SAFETY_CRITICAL` leaves Synex for a human process; `SYSTEM_CRITICAL`
    is refused *inside a turn* while the Administrator authors it outside one. Collapsed to a
    shared 'refused' a reader would assume a senior enough person could sign either off."""
    assert set(NEVER_APPROVABLE_BECAUSE) == set(authority.NEVER_APPROVABLE)
    safety = NEVER_APPROVABLE_BECAUSE[Risk.SAFETY_CRITICAL]
    system = NEVER_APPROVABLE_BECAUSE[Risk.SYSTEM_CRITICAL]

    assert safety != system
    assert "human process" in safety
    assert "inside a turn" in system
    assert "outside the agent" in system


def test_the_row_that_needs_no_approval_says_so_in_words() -> None:
    """An empty `who` cell on a `LOW` row is indistinguishable from a row nobody filled in."""
    row = {r.risk: r for r in approval_matrix()}[Risk.LOW]
    assert row.requirement is Requirement.NO_APPROVAL
    assert "No approval is required" in row.who


def test_every_row_carries_its_reason_in_words() -> None:
    """Constraint 14: a figure is a value or a stated absence, never neither. A dash in an
    approval cell is the shape of absence this whole surface exists to refuse."""
    for row in approval_matrix():
        assert row.who.strip(), f"{row.risk.value} has no words"
        assert row.render().startswith(row.risk.value)
        assert row.as_dict()["who"].strip()


# ── the two absences the matrix must not collapse ──────────────────────────────

def test_a_capability_the_control_plane_never_defined_is_not_reported_as_merely_unheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Found a defect; fixed in `_row_for`.** The approval engine names capabilities as plain
    strings and `domain` imports nothing (contract 4), so nothing structural stops it asking
    for a capability the Control Plane has never defined. The matrix reported that as *no
    persona currently holds it* — sending a reader to grant a name that does not exist, when
    the real finding is that the two tables have drifted apart. Two absences, one row."""
    monkeypatch.setitem(authority.REQUIRED_CAPABILITY, Risk.MEDIUM, "authorise_shutdown")
    row = {r.risk: r for r in approval_matrix()}[Risk.MEDIUM]

    assert row.holders == ()
    assert "does not define at all" in row.who
    assert "granting it to somebody is not the repair" in row.who


def test_an_ungranted_capability_reads_differently_from_an_undefined_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the same pair, and the reason the first test is not enough on its own.
    `close_work` is a real capability; revoke it from everybody and the row must say the
    capability exists and nobody has it — a grant somebody can make, not a name to correct."""
    monkeypatch.setitem(authority.REQUIRED_CAPABILITY, Risk.HIGH, "close_work")
    monkeypatch.setitem(
        control_plane._CAPABILITIES, Persona.SUPERVISOR, frozenset({Capability.VIEW_FAULTS})
    )
    row = {r.risk: r for r in approval_matrix()}[Risk.HIGH]

    assert row.holders == ()
    assert "no persona currently holds" in row.who
    assert "does not define at all" not in row.who


def test_a_decision_the_matrix_has_no_row_shape_for_is_shown_as_a_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Found a defect; fixed in `_row_for`.** `Requirement.UNSTATED` documents itself as
    *reported as a gap rather than absorbed*, and the code absorbed it: an unanswered level
    fell through and rendered as an ordinary named-capability row reading *cleared by
    approve_work, held by Supervisor*. A question nobody has answered must not look like one
    somebody has."""
    monkeypatch.setattr(
        policy,
        "rule",
        lambda action, held: Ruling(
            action=action.name,
            risk=Risk.HIGH,
            decision=Decision.UNCLASSIFIED,
            required_capability="approve_work",
            reason="nobody classified this",
            was_unclassified=True,
        ),
    )
    row = policy._row_for(Risk.HIGH, capability_holders())

    assert row.requirement is Requirement.UNSTATED
    assert row.holders == ()
    assert "unstated" in row.who
    assert "Supervisor" not in row.who


# ── constraint 25: display order, computed rather than asserted ────────────────

def test_the_personas_do_not_form_a_ladder_and_the_arithmetic_says_which_pairs() -> None:
    """The sentence *roles are capabilities, not ranks* was already written in the sibling
    implementation, and the code beneath it ranked by seniority anyway. So the claim is
    computed: a supervisor and a technician each hold something the other does not, so neither
    is above the other, and the same holds for a reliability engineer and a supervisor."""
    report = ordering_report()

    assert report.forms_a_ladder is False
    assert ("Supervisor", "Technician") in report.incomparable_pairs
    assert ("Reliability Engineer", "Supervisor") in report.incomparable_pairs
    assert "do not form a ladder" in report.finding
    assert "Supervisor and Technician" in report.finding


def test_real_containment_is_reported_rather_than_hidden() -> None:
    """An honest report says where a subset genuinely exists. The Analyst holds `view_faults`
    and `view_residuals`; the Reliability Engineer holds those and `open_case`. Suppressing
    that to make the anti-ladder point cleanly would be the same dishonesty in reverse."""
    report = ordering_report()
    assert ("Analyst", "Reliability Engineer") in report.contained_pairs
    assert set(report.contained_pairs).isdisjoint(report.incomparable_pairs)


def test_the_ladder_verdict_flips_when_the_capability_map_becomes_a_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The test that stops `forms_a_ladder` being a constant dressed as a computation. Make the
    capability sets an actual chain and the report must say so — and must call it a finding
    about the capability map, because constraint 25 says the map must not be one."""
    order = [
        Persona.TECHNICIAN,
        Persona.ANALYST,
        Persona.RELIABILITY_ENGINEER,
        Persona.SUPERVISOR,
        Persona.ADMINISTRATOR,
    ]
    growing = [
        Capability.VIEW_FAULTS,
        Capability.VIEW_RESIDUALS,
        Capability.OPEN_CASE,
        Capability.APPROVE_WORK,
        Capability.EDIT_POLICY,
    ]
    chain = {p: frozenset(growing[: i + 1]) for i, p in enumerate(order)}
    monkeypatch.setattr(control_plane, "_CAPABILITIES", chain)

    report = ordering_report()
    assert report.forms_a_ladder is True
    assert report.incomparable_pairs == ()
    assert "constraint 25 says it must not" in report.finding


def test_the_personas_are_listed_alphabetically_and_not_by_how_much_they_hold() -> None:
    """Sorting by the number of capabilities held would rebuild the ladder in one line of code,
    invisibly, and it would look like a helpful default. The Administrator sorts first while
    holding two capabilities against the Reliability Engineer's three."""
    rows = persona_capabilities()
    names = [row.display_name for row in rows]

    assert names == sorted(names)
    assert rows[0].display_name == "Administrator"
    assert len(rows[0].capabilities) < max(len(r.capabilities) for r in rows)


def test_each_personas_capabilities_are_alphabetical_for_the_same_reason() -> None:
    """A capability list ordered by importance is a ranking of the things a person may do, and
    the reader carries that ordering back onto the people."""
    for row in persona_capabilities():
        assert list(row.capabilities) == sorted(row.capabilities)
        assert row.render().startswith(row.display_name)


def test_the_order_note_is_read_out_beside_the_list_rather_than_left_to_a_caption() -> None:
    """A caption is dropped the first time the layout changes. Constraints 13 and 25 are on the
    surface itself, naming the incident, so removing them is a visible act."""
    rendered = _view().render()
    assert ORDER_NOTE in rendered
    assert "filter-drier restriction" in ORDER_NOTE
    assert "display order rather than a ladder" in ORDER_NOTE


def test_a_persona_holding_nothing_says_so_rather_than_showing_an_empty_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty capability list reads as a persona whose entry nobody finished. It is a gap in
    the capability map, and that is a different statement from a restriction somebody chose."""
    monkeypatch.setitem(control_plane._CAPABILITIES, Persona.ANALYST, frozenset())
    analyst = {r.display_name: r for r in persona_capabilities()}["Analyst"]

    assert analyst.capabilities == ()
    assert "holds no capabilities at all" in analyst.render()
    assert "gap in the capability map" in analyst.render()


# ── G8: the dry run that does not exist, said rather than omitted ──────────────

def test_the_surface_says_a_rule_change_cannot_be_tried_first() -> None:
    """`G8` is Phase 3. The absence is on the screen because a governance screen that says
    nothing about testing a rule change is read as having tested it — and the one review pass
    ever run over the reference plant's 124 role tags, covering one class, found an oil
    analysis being shown to whoever opened a compressor case. Unreviewed governance content is
    the measured state here, not a hypothetical."""
    rendered = _view().render()
    assert NO_DRY_RUN in rendered
    assert "Phase 3 and is not built" in NO_DRY_RUN
    assert "There is no dry run" in NO_DRY_RUN


def test_the_missing_dry_run_is_named_as_its_own_capability_with_its_source() -> None:
    """Not folded into a general disclaimer. A reader has to be able to see which feature is
    missing, so `G8` is on the row rather than in a footnote about the product generally."""
    by_source = {m.source: m for m in NOT_AVAILABLE}
    assert by_source["G8"].reason == NO_DRY_RUN
    assert by_source["G8"].name == "Try a rule change before it goes live"


def test_three_absences_are_named_separately_rather_than_as_one_disclaimer() -> None:
    """`G8` is unbuilt, `Q41` is unanswered and `Q76` is unstated. They have different owners
    and different repairs; one vague sentence covering all three tells a reader nothing they
    can act on."""
    sources = [m.source for m in NOT_AVAILABLE]
    assert sorted(sources) == ["G8", "Q41", "Q76"]
    assert len(set(sources)) == len(sources)


def test_no_absence_on_this_surface_is_a_bare_flag() -> None:
    """An absence is not a zero and not a dash. Every field of a missing capability is prose
    somebody can act on, and a boolean here would be read as a step that was skipped rather
    than one that does not exist."""
    for missing in NOT_AVAILABLE:
        for field in dataclasses.fields(MissingCapability):
            value = getattr(missing, field.name)
            assert isinstance(value, str) and value.strip()
        assert "not available" in missing.render()
        assert missing.reason in missing.render()


def test_a_policy_change_records_why_it_was_not_tried_beforehand_in_words() -> None:
    """`tried_first` is a sentence and never a flag. `False` on a governance record reads as a
    dry run somebody chose to skip; the truth is that `G8` does not exist to be skipped."""
    assert A_CHANGE.tried_first == NO_DRY_RUN
    assert not isinstance(A_CHANGE.tried_first, bool)
    assert NO_DRY_RUN in A_CHANGE.render()
    assert A_CHANGE.as_dict()["tried_first"] == NO_DRY_RUN


# ── the policy version ─────────────────────────────────────────────────────────

def test_a_stated_version_is_quoted_back_with_what_it_is_for() -> None:
    """It exists to be stamped on every audit row, so a decision can be traced to the rules in
    force when it was taken."""
    version = PolicyVersion(version=VERSION)
    assert version.is_stated
    assert VERSION in version.render()
    assert "stamped" in version.render()


def test_a_missing_version_is_a_sentence_and_not_a_blank_field() -> None:
    """A blank version cell implies a version too dull to print. Nothing was stamped, and no
    decision taken now can be traced back to a rule set — which is a configuration gap."""
    version = PolicyVersion(version="   ")
    assert not version.is_stated
    assert "cannot be traced back" in version.render()
    assert "not a version of zero" in version.render()

    payload = version.as_dict()
    assert payload["version"] is None
    assert payload["statement"].strip()


def test_two_policy_versions_cannot_be_compared_for_order() -> None:
    """`Q74`: no document states the scheme or what advances it. `2026-08-13.1` is
    date-and-counter shaped, and treating it as ordered would invite *two versions behind* —
    arithmetic on a string nothing in the programme has defined."""
    with pytest.raises(TypeError):
        _ = PolicyVersion(version="2026-08-13.1") < PolicyVersion(version="2026-08-14.1")


def test_the_surface_explains_why_the_version_is_an_opaque_string() -> None:
    """Stated on the artefact rather than left in a comment, because the reader is the one who
    would otherwise assume the number means something."""
    payload = _view().as_dict()["policy"]
    assert "Q74" in payload["version_is_a_string"]
    assert "opaque string" in payload["version_is_a_string"]


# ── a rule change is a versioned event, and refusing it is not an error ────────

def test_a_rule_change_cannot_be_declared_anything_milder_than_system_critical() -> None:
    """`risk` is a property rather than a field precisely so a caller cannot hand the approval
    engine a rule change dressed as a draft edit."""
    assert A_CHANGE.risk is Risk.SYSTEM_CRITICAL
    assert "risk" not in {f.name for f in dataclasses.fields(PolicyChange)}


def test_a_rule_change_does_not_reverse_cleanly() -> None:
    """Withdrawing a rule change does not withdraw its consequences: decisions already taken
    under the superseded version stay taken, and stay stamped with it."""
    assert A_CHANGE.action.reverses_cleanly is False
    assert A_CHANGE.action.risk is Risk.SYSTEM_CRITICAL


def test_the_change_carries_what_it_replaces_as_well_as_what_it_becomes() -> None:
    """A record showing only the new state cannot answer *what did this replace*, which is the
    first question an audit asks. That pair is what makes the change a version, not a mutation."""
    rendered = A_CHANGE.render()
    assert A_CHANGE.supersedes in rendered
    assert A_CHANGE.becomes in rendered
    assert "not an edit to the current one" in rendered


def test_the_module_offers_no_way_to_apply_a_change() -> None:
    """`G2` classifies a rule change `SYSTEM_CRITICAL` and `G3` refuses it. An `apply` on this
    object would be the one method that makes every other honesty line on the screen a
    formality."""
    callables = {
        name
        for name in dir(PolicyChange)
        if not name.startswith("_") and callable(getattr(PolicyChange, name, None))
    }
    assert callables == {"render", "as_dict"}
    assert dataclasses.is_dataclass(PolicyChange)
    assert PolicyChange.__dataclass_params__.frozen, "an intent that can be edited is an edit"


def test_holding_edit_policy_does_not_clear_a_rule_change_inside_a_turn() -> None:
    """The Administrator is the one persona holding `edit_policy`, and it still does not let
    the agent change the rules mid-turn. If this ever passes, the refusal has become a
    capability check and `G8` is being relied on to catch what it cannot — it is Phase 3."""
    scope = compute_scope(Persona.ADMINISTRATOR)
    assert Capability.EDIT_POLICY in scope.capabilities

    ruling = ruling_on(A_CHANGE, scope)
    assert ruling.decision is Decision.REFUSED
    assert ruling.may_proceed is False


@pytest.mark.parametrize("persona", list(Persona))
def test_no_persona_may_change_the_rules_inside_a_turn(persona: Persona) -> None:
    """Tested across every persona rather than one, because the failure to prevent is somebody
    sufficiently privileged getting through — the same shape as a senior person signing off a
    safety stop."""
    assert ruling_on(A_CHANGE, compute_scope(persona)).decision is Decision.REFUSED


def test_the_refusal_is_returned_as_a_ruling_and_never_raised() -> None:
    """Honesty rule 1: a refusal is not an error. `NO_DIAGNOSIS` is the modal outcome on this
    plant — 5,309 slots against 674 faulted — and a governance refusal raised as an exception
    would surface to a user as a broken screen rather than as the rules working."""
    ruling = ruling_on(A_CHANGE, compute_scope(Persona.ADMINISTRATOR))
    assert ruling.is_refusal is True
    assert ruling.was_unclassified is False
    assert ruling.reason.strip()
    assert "no approval clears it" in ruling.reason


def test_the_refusal_is_narrow_and_the_surface_says_which_narrowness() -> None:
    """It says the change cannot be made *inside the agent*. It does not say the Administrator
    may not author policy — that is their job, done deliberately, outside a turn and reviewed.
    A screen stating the wider claim would be telling the Administrator they are locked out of
    their own surface."""
    system = NEVER_APPROVABLE_BECAUSE[Risk.SYSTEM_CRITICAL]
    assert "Refused inside a turn rather than forbidden outright" in system
    assert "the Administrator authors these" in system


def test_a_change_is_attributed_to_the_identity_kind_and_not_to_a_name() -> None:
    """An audit row naming an author it cannot verify is worse than one naming none. `Q75` owns
    what attribution becomes once identity is real."""
    assert IDENTITY_KIND in A_CHANGE.authored_by
    assert "Q41" in A_CHANGE.authored_by
    assert "no person can be named" in A_CHANGE.authored_by
    assert A_CHANGE.authored_by in A_CHANGE.render()


# ── the whole surface holds together ───────────────────────────────────────────

def test_the_surface_carries_every_part_of_itself_into_its_serialised_form() -> None:
    """A web surface that had to reassemble any of these from the parts would eventually
    reassemble one of them wrongly, and the wrong one would be the identity line."""
    payload = _view().as_dict()
    assert set(payload) == {
        "policy",
        "identity_kind",
        "identity_note",
        "is_production_identity",
        "approval_matrix",
        "personas",
        "order_note",
        "ordering",
        "not_available",
    }
    assert len(payload["approval_matrix"]) == len(Risk)
    assert len(payload["personas"]) == len(Persona)
    assert len(payload["not_available"]) == len(NOT_AVAILABLE)
    assert payload["ordering"]["forms_a_ladder"] is False


def test_the_rendered_surface_says_all_three_things_it_has_to_say() -> None:
    """The end-to-end version of this file. A screen carrying the matrix without the identity
    kind, without the ordering finding, or without `G8`'s absence is the misleading one."""
    rendered = _view().render()
    assert IDENTITY_KIND in rendered
    assert "do not form a ladder" in rendered
    assert NO_DRY_RUN in rendered
    assert VERSION in rendered
    assert all(line.strip() for line in rendered.splitlines())
