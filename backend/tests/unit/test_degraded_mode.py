"""`CONTEXT.md` §13 — the platform states when it is in degraded mode rather than silently
substituting a weaker capability.

These tests exist to keep four things from eroding, each with a failure behind it: a
degradation must be **named**, a substitution must say **what is standing in**, an unprobed
dependency must not read as a working one, and the report must name **every** capability
whether or not the caller bothered to look at it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.agents import degraded_mode as observer
from app.domain.degradation import (
    PROFILES,
    Availability,
    Capability,
    CapabilityState,
    Finding,
    Observation,
    assess,
)

REACHED = Observation(
    capability=Capability.PLANT_TELEMETRY,
    finding=Finding.REACHED,
    detail="the pool opened",
)


# ── the vocabulary refuses to be vague ─────────────────────────────────────────

def test_an_observation_cannot_be_made_without_a_detail() -> None:
    """Every state this produces carries its reason in words, and there is nowhere else for
    those words to come from — so the absence is refused at construction rather than rendered
    as an empty string three layers later."""
    with pytest.raises(ValueError, match="no detail"):
        Observation(
            capability=Capability.EMBEDDINGS, finding=Finding.NOT_REACHED, detail="   "
        )


def test_a_substitution_cannot_be_reported_without_naming_what_stands_in() -> None:
    """This is §13 in one assertion. *"Degraded"* with no named substitute is precisely the
    silent substitution the rule forbids."""
    with pytest.raises(ValueError, match="without naming the substitution"):
        CapabilityState(
            capability=Capability.ANSWER_PROSE,
            availability=Availability.SUBSTITUTED,
            reason="the box did not answer",
        )


def test_every_profile_either_names_a_substitute_or_names_what_breaks() -> None:
    """A capability with neither would produce a state that says a thing is missing and
    nothing about the consequence — which is a dash wearing a sentence."""
    for capability, profile in PROFILES.items():
        assert profile.provides.strip(), f"{capability.value} does not say what it provides"
        assert profile.depends_on.strip(), f"{capability.value} does not say what it needs"
        assert profile.has_substitute or profile.breaks.strip(), (
            f"{capability.value} has no substitute and does not say what breaks without one"
        )


# ── the four availabilities are four different facts ───────────────────────────

def test_a_capability_with_no_substitute_becomes_unavailable_not_substituted() -> None:
    """There is no second copy of what the instruments read. Reporting the plant as
    *substituted* would imply something is standing in for a reading, and the fabricated
    `cond_flow` window is exactly what that looks like when it happens."""
    report = assess(
        (
            Observation(
                capability=Capability.PLANT_TELEMETRY,
                finding=Finding.NOT_REACHED,
                detail="nothing listens on :3307",
            ),
        )
    )
    state = report.state_of(Capability.PLANT_TELEMETRY)
    assert state.availability is Availability.UNAVAILABLE
    assert state.substitution == "", "nothing stands in, and the field says so by being empty"
    assert "Nothing stands in for it" in state.reason
    assert "nothing listens on :3307" in state.reason


def test_a_capability_with_a_substitute_names_it_in_the_report() -> None:
    """The prose layer going away costs the writing, not the answer — and a reader has to be
    able to see which of those happened."""
    report = assess(
        (
            Observation(
                capability=Capability.ANSWER_PROSE,
                finding=Finding.NOT_REACHED,
                detail="the box at 127.0.0.1:11500 did not answer",
            ),
        )
    )
    state = report.state_of(Capability.ANSWER_PROSE)
    assert state.availability is Availability.SUBSTITUTED
    assert "deterministic answer assembled from the evidence pack" in state.substitution
    assert state.is_degraded


def test_an_unprobed_capability_is_unknown_and_is_not_a_pass() -> None:
    """Inherited constraint 7: `NULL` means not diagnosed, never healthy. An empty queue on a
    blind window once read as a clean plant, and a health endpoint that reports what it never
    checked is the same mistake with a different denominator."""
    report = assess(())
    state = report.state_of(Capability.CASE_QUEUE)
    assert state.availability is Availability.UNKNOWN
    assert state.is_unknown
    assert not state.is_degraded, "unknown is not degraded either — it is unknown"
    assert "This is not a report that it is working" in state.reason
    assert report.is_fully_available is False


def test_unknown_and_unavailable_are_never_folded_together() -> None:
    """Inherited constraint 8 — `cannot_check` is separate from `not applicable` — one layer
    up. Six "N/A" presses once opened a blocking gate with zero evidence behind it."""
    report = assess(
        (
            Observation(
                capability=Capability.EMBEDDINGS,
                finding=Finding.NOT_REACHED,
                detail="Ollama on the host refused the connection",
            ),
        )
    )
    assert report.state_of(Capability.EMBEDDINGS).availability is Availability.UNAVAILABLE
    assert report.state_of(Capability.CASE_QUEUE).availability is Availability.UNKNOWN
    assert Capability.EMBEDDINGS in {s.capability for s in report.degraded}
    assert Capability.CASE_QUEUE in {s.capability for s in report.unknown}


# ── the report is always complete ──────────────────────────────────────────────

def test_the_report_names_every_capability_however_little_was_checked() -> None:
    """A list that shrinks to what was easy to check is the reconciliation failure `R10`
    exists for, wearing infrastructure clothes."""
    report = assess((REACHED,))
    assert len(report.states) == len(PROFILES)
    assert {s.capability for s in report.states} == set(Capability)


def test_the_headline_never_gives_a_count_without_its_total() -> None:
    """*"Degraded"* on its own is the word that hid three of these. The denominator is what
    makes the sentence mean anything."""
    report = assess(
        (
            Observation(
                capability=Capability.AUDIT_TRAIL,
                finding=Finding.NOT_REACHED,
                detail="the sink reports itself not durable",
            ),
        )
    )
    headline = report.headline()
    assert f"of {len(PROFILES)}" in headline
    assert "audit_trail" in headline
    assert "were not probed" in headline


def test_two_observations_of_one_capability_raise_rather_than_pick_one() -> None:
    """A caller holding two answers about one dependency has a bug, and silently keeping the
    cheerful one is the exact failure shape this module exists to prevent."""
    with pytest.raises(ValueError, match="observed twice"):
        assess((REACHED, REACHED))


# ── the probes report what the process actually knows ──────────────────────────

def test_the_plant_error_is_carried_through_verbatim() -> None:
    """*"Nothing listens on :3307"* and *"access denied for `synex_plant_ro`"* need different
    people. Collapsing them into "the plant database is down" sends the wrong one."""
    observation = observer.observe_plant(None, "OperationalError: access denied for user")
    assert observation.finding is Finding.NOT_REACHED
    assert "access denied for user" in observation.detail


def test_a_missing_pool_with_no_recorded_error_is_still_reported() -> None:
    """The state nobody expects: the lifespan neither opened the pool nor recorded why. Read
    as *available* it would be invisible; read as a bare failure it would be unactionable."""
    observation = observer.observe_plant(None, None)
    assert observation.finding is Finding.NOT_REACHED
    assert "itself a defect" in observation.detail


def test_stub_mode_with_no_transcript_is_a_certainty_rather_than_an_unknown(
    tmp_path: Path,
) -> None:
    """`SESSION-HANDOFF.md` §3: `backend/tests/fixtures/` holds nothing but `__init__.py`, so
    no transcript has ever been recorded and every completion raises. That is not *we do not
    know whether the box answers* — it is knowing that every answer will be the deterministic
    one, before anybody asks a question."""
    observation = observer.observe_answer_prose(model_mode="stub", transcript_dir=tmp_path)
    assert observation.finding is Finding.NOT_REACHED
    assert "no transcript has been recorded" in observation.detail


def test_stub_mode_is_a_substitution_even_when_it_works(tmp_path: Path) -> None:
    """A replayed transcript is not the roster answering — it is a recording of the roster
    answering a prompt somebody asked once. Reporting that as *available* is the silent
    substitution §13 forbids, however well it works, and the transcript key is a hash of the
    whole prompt so the replay only ever covers what was recorded."""
    (tmp_path / "abc123.json").write_text("{}", encoding="utf-8")
    observation = observer.observe_answer_prose(model_mode="stub", transcript_dir=tmp_path)

    assert observation.finding is Finding.NOT_REACHED
    assert "nothing reaches the roster" in observation.detail
    assert "1 transcript(s)" in observation.detail
    assert "still raises" in observation.substitution


def test_a_probe_may_narrow_a_substitution_and_may_never_invent_one() -> None:
    """The roster has two weaker things behind it — a replay, and the deterministic assembly —
    and a reader told the wrong one looks in the wrong place. But a probe that could supply a
    substitution where the registry says there is none could report the plant snapshot as stood
    in for, which is how a fabricated reading gets a respectable name."""
    narrowed = assess(
        (
            Observation(
                capability=Capability.ANSWER_PROSE,
                finding=Finding.NOT_REACHED,
                detail="the mode is 'stub'",
                substitution="a recorded transcript replays instead",
            ),
        )
    )
    state = narrowed.state_of(Capability.ANSWER_PROSE)
    assert state.availability is Availability.SUBSTITUTED
    assert state.substitution == "a recorded transcript replays instead"

    with pytest.raises(ValueError, match="may never invent one"):
        assess(
            (
                Observation(
                    capability=Capability.PLANT_TELEMETRY,
                    finding=Finding.NOT_REACHED,
                    detail="nothing listens on :3307",
                    substitution="the last figures we happen to remember",
                ),
            )
        )


def test_a_turn_that_already_fell_back_outranks_the_configured_mode(tmp_path: Path) -> None:
    """Evidence beats configuration. A mode claiming the box is reachable does not outrank a
    call that just failed, and the aggregate has to reflect what happened in this request.

    It also carries the *right* substitution: this turn got the deterministic assembly, not a
    replay, so the profile's own wording applies rather than the transcript one.
    """
    (tmp_path / "abc123.json").write_text("{}", encoding="utf-8")
    observation = observer.observe_answer_prose(
        model_mode="stub",
        transcript_dir=tmp_path,
        turn_degraded_reason="the box at 127.0.0.1:11500 did not answer for gemma4",
    )
    assert observation.finding is Finding.NOT_REACHED
    assert "already fell back" in observation.detail
    assert observation.substitution == "", "the profile's substitution applies to a fallback"

    report = assess((observation,))
    assert "deterministic answer assembled from the evidence pack" in report.state_of(
        Capability.ANSWER_PROSE
    ).substitution


def test_live_mode_is_not_probed_rather_than_assumed_reachable() -> None:
    """Establishing it costs a call to the box, and a health endpoint that dials every
    dependency is one that times out — after which nobody reads it at all."""
    observation = observer.observe_answer_prose(model_mode="live")
    assert observation.finding is Finding.NOT_PROBED
    assert "makes no call" in observation.detail


def test_the_durability_flags_are_read_from_the_code_that_publishes_them() -> None:
    """`audit_log.IS_DURABLE` and `Gateway.is_durable` exist so a surface can say so. Until
    this reporter, nothing read either of them, which made both flags comments."""
    from app.services import audit_log
    from app.tools.gateway import GATEWAY

    audit = observer.observe_audit_trail()
    tools = observer.observe_tool_idempotency()

    assert (audit.finding is Finding.REACHED) is audit_log.IS_DURABLE
    assert (tools.finding is Finding.REACHED) is GATEWAY.is_durable


# ── the aggregate, which is the point of the feature ───────────────────────────

def test_four_separate_degradations_are_reported_separately(tmp_path: Path) -> None:
    """The headline finding: MySQL down, the box down, the audit sink not durable and the tool
    ledger in memory are four different facts. A single `status: degraded` word says none of
    them, and a surface cannot act on it."""
    report = observer.assess_platform(
        plant_repo=None,
        plant_error="OperationalError: cannot connect to 127.0.0.1:3307",
        model_mode="stub",
        transcript_dir=tmp_path,
    )

    degraded = {s.capability for s in report.degraded}
    assert Capability.PLANT_TELEMETRY in degraded
    assert Capability.ANSWER_PROSE in degraded
    assert Capability.AUDIT_TRAIL in degraded
    assert Capability.TOOL_IDEMPOTENCY in degraded

    # And the two nobody probed are named as unknown rather than left out or assumed working.
    unknown = {s.capability for s in report.unknown}
    assert Capability.EMBEDDINGS in unknown
    assert Capability.KNOWLEDGE_RETRIEVAL in unknown
    assert Capability.CASE_QUEUE in unknown


def test_a_healthy_plant_does_not_make_the_platform_fully_available(tmp_path: Path) -> None:
    """The reason this reporter earns its place: with MySQL up and transcripts recorded, three
    capabilities are still substituted — the roster is being replayed rather than reached, the
    audit trail is not durable, and `G5`'s ledger is in memory. A status field computed from the
    plant connection alone prints `ok` over all three."""
    (tmp_path / "abc123.json").write_text("{}", encoding="utf-8")
    report = observer.assess_platform(
        plant_repo=object(),
        plant_error=None,
        model_mode="stub",
        transcript_dir=tmp_path,
    )

    assert report.state_of(Capability.PLANT_TELEMETRY).availability is Availability.AVAILABLE
    assert {s.capability for s in report.degraded} == {
        Capability.ANSWER_PROSE,
        Capability.AUDIT_TRAIL,
        Capability.TOOL_IDEMPOTENCY,
    }
    assert report.is_fully_available is False


def test_the_rendered_report_says_what_is_standing_in(tmp_path: Path) -> None:
    """A reader of the artefact must be able to answer *"what is running instead"* without
    opening the code."""
    report = observer.assess_platform(
        plant_repo=object(),
        plant_error=None,
        model_mode="stub",
        transcript_dir=tmp_path,
    )
    text = report.render()
    assert "WHAT IS STANDING IN" in text
    assert "does not survive a restart" in text
    assert "answer_prose" in text


def test_the_serialised_report_carries_the_reason_for_every_capability(
    tmp_path: Path,
) -> None:
    """An absence is not a zero and not a dash — including on the wire, where a surface has
    nothing but this dictionary to render."""
    report = observer.assess_platform(
        plant_repo=None,
        plant_error="nothing listens on :3307",
        model_mode="stub",
        transcript_dir=tmp_path,
    )
    payload = report.as_dict()
    assert payload["capabilities_reported"] == len(PROFILES)
    assert payload["fully_available"] is False
    for state in payload["states"]:
        assert state["reason"].strip(), f"{state['capability']} was serialised without a reason"
