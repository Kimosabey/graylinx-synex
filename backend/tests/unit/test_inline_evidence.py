"""`C24` inline evidence — pairing a claim with the figure that backs it, and naming the ones
with nothing behind them.

The half of `C24` these tests exist for is the second half. Rendering a figure beside the
claim it supports is layout; **reporting the claim that has no supporting line is the
feature**, because an unsupported claim rendered inline looks exactly as authoritative as a
supported one — same typeface, same sentence shape, same position on the page.
"""
from __future__ import annotations

from datetime import date, datetime

from app.agents import postcheck
from app.agents.answer import deterministic_answer
from app.analytics.bands import ResidualBand
from app.analytics.gates import Gate, GateOutcome, GateResult, check_running
from app.db.plant import RESIDUAL_COLUMNS, ResidualRow
from app.services.evidence import build_pack, window_for
from app.services.inline_evidence import (
    ClaimSupport,
    EvidenceKind,
    evidence_lines,
    figures_in,
    pair_claims,
    split_claims,
    unsupported_claims,
)

DAY = date(2026, 4, 15)
MEASURED_END = datetime(2026, 6, 23, 11, 50)

#: Chiller 1's current residual, measured. The median is −25.645, and `-25.6` is a substring
#: of it — which is the exact truncation the pairing must refuse to call supported.
BAND = ResidualBand("chiller_1", "chiller_current_residual", -25.645, -38.677, -12.613)


def _pack(*, blind: bool = False, others: tuple[str, ...] = ()):
    values: dict[str, float | None] = dict.fromkeys(RESIDUAL_COLUMNS, None)
    values["chiller_current_residual"] = -20.0
    rows = (ResidualRow("chiller_1", datetime(2026, 4, 15, 9, 0), "CONDENSER_LOW_FLOW", values),)
    gates = (
        GateOutcome(
            (GateResult(Gate.RUNNING, passed=False, reason="no readings", remedy="check feed"),)
        )
        if blind
        else GateOutcome((check_running({"a": 141.0}),))
    )
    return build_pack(
        rows=rows,
        bands=(BAND,),
        gates=gates,
        window=window_for(DAY, MEASURED_END),
        equipment_key="chiller_1",
        fault_label="CONDENSER_LOW_FLOW",
        day=DAY,
        other_labels_same_day=others,
    )


# ── the tokeniser must not drift from the audit's ─────────────────────────────

def test_the_pairing_tokeniser_agrees_with_the_numeric_audit_token_for_token() -> None:
    """The two are separate copies because contract 2 forbids `services` importing `agents`,
    and a copy is a thing that drifts.

    If they disagreed, a number the honesty audit polices could render as unpairable prose —
    an answer would fail one gate and be presented by the other as having stated no figure
    at all.
    """
    samples = [
        "the residual sat at -25.645 against a band of -38.677 to -12.613",
        "chiller 1 ran at nRMSE 48.03 over 412 readings in 2026",
        "0 non-zero values in 37,430 measured slots",
        "all five residuals, two of twelve gates, 13 slots",
        "−273.2 °C is absolute zero, not a temperature",
    ]
    for text in samples:
        assert list(figures_in(text)) == postcheck._numbers_in(text), text


def test_a_year_and_a_small_count_are_not_figures() -> None:
    """A model may legitimately write "all five residuals" and "in 2026" without having read
    either from the evidence. Treating them as figures would fill the unsupported list with
    grammar and bury the one claim that matters."""
    assert figures_in("in 2026 all 5 residuals over 12 slots") == ()


# ── the substring bug, which is why this compares by value ────────────────────

def test_a_truncated_figure_is_unsupported_rather_than_paired() -> None:
    """`-25.6` is a substring of `-25.645`, so containment would call the truncation
    supported. `postcheck.audit_numbers` shipped with exactly that bug and the test written
    to catch it passed against the broken version.

    A truncated figure in a report about instrumentation is a different claim, not a rounder
    one.
    """
    pack = _pack()
    rendering = pair_claims("The median residual was -25.6 for this asset.", pack)

    assert rendering.unsupported
    assert rendering.unsupported[0].unmatched == ("-25.6",)


def test_the_same_value_written_differently_still_pairs() -> None:
    """`-20.0` and `-20` are the same number and nothing was lost, so exact *value* equality
    is the rule rather than exact text. The opposite choice would report honest arithmetic as
    fabrication, and a false accusation suppresses correct answers silently."""
    rendering = pair_claims("The residual read -20 on the last slot.", _pack())
    assert rendering.every_figure_is_supported


def test_a_typeset_minus_pairs_with_an_ascii_hyphen() -> None:
    """The evidence uses U+2212 because it is typeset prose; a model replies with a hyphen.
    Reading the first as *positive* once made one figure look like two different numbers."""
    rendering = pair_claims("The residual read −20.0 on the last slot.", _pack())
    assert rendering.every_figure_is_supported


# ── the three outcomes, and why none of them collapses into another ───────────

def test_a_claim_with_no_figure_is_its_own_outcome_and_not_a_supported_one() -> None:
    """Inherited constraint 8's shape, one layer up: six `not applicable` presses once opened
    a blocking gate with zero evidence behind it.

    A sentence carrying no number cannot be paired. Counting it as paired would let an answer
    of pure prose report a clean pairing.
    """
    rendering = pair_claims("The condenser appears to be fouled.", _pack())

    assert len(rendering.unpairable) == 1
    assert rendering.unpairable[0].support is ClaimSupport.NO_FIGURE
    assert rendering.paired == ()


def test_the_unpairable_claim_says_it_is_a_separation_law_question_not_a_pairing_one() -> None:
    """The honest limit, stated rather than hidden. *"The root cause is a fouled condenser"*
    carries no number, so this module says nothing about it — the audit that catches it is
    `postcheck.audit_no_diagnosis_by_model`, and neither mechanism pretends to be the other."""
    claim = pair_claims("The root cause is a fouled condenser.", _pack()).unpairable[0]
    assert "separation-law question" in claim.reason


def test_the_headline_gives_three_counts_rather_than_one_ratio() -> None:
    """"8 of 10 supported" hides whether the other two were fabrications or ordinary prose,
    and those need different things done about them."""
    answer = (
        "The residual read -20.0 on the last slot.\n"
        "The median was -25.6 for this asset.\n"
        "The machine looks to be running hard."
    )
    statement = pair_claims(answer, _pack()).support_statement()

    assert "1 claim(s) paired" in statement
    assert "1 claim(s) state a figure the evidence does not contain" in statement
    assert "1 claim(s) state no figure" in statement


# ── the unsupported claim is named, never dropped ─────────────────────────────

def test_an_unsupported_claim_is_marked_in_words_inside_the_rendering() -> None:
    """Never dropped, never greyed out. Constraint 38's rule — a thing the reader cannot act
    on collapses with a reason rather than fading out — applies to a sentence too."""
    rendered = pair_claims("Efficiency reached 1.40 that month.", _pack()).render()

    assert "NO SUPPORTING EVIDENCE" in rendered
    assert "1.40" in rendered
    assert "look exactly as authoritative as a supported one" in rendered


def test_a_supported_claim_names_the_evidence_line_standing_beside_it() -> None:
    """"This figure is in the evidence somewhere" is not a checkable statement. The reader
    must be able to see *which* line, so the kind and the label travel with it."""
    claim = pair_claims("The residual read -20.0 there.", _pack()).paired[0]

    assert claim.supporting
    assert claim.supporting[0].kind is EvidenceKind.RESIDUAL
    assert "chiller_current_residual" in claim.render()


def test_the_short_form_returns_only_the_sentences_a_reader_should_not_trust() -> None:
    """What a thread export and a work-order draft both want: not the layout, the list."""
    answer = "The residual read -20.0. Efficiency reached 1.40."
    assert unsupported_claims(answer, _pack()) == ("Efficiency reached 1.40.",)


# ── an ambiguous pairing is reported, not resolved ────────────────────────────

def test_a_figure_matching_more_than_one_line_is_flagged_rather_than_assigned() -> None:
    """Value alone does not prove the line is *about* the same quantity. Silently picking the
    first would attach a plausible-looking line to the wrong figure — the join by guesswork
    that `_RESIDUAL_TO_MODEL` in `evidence.py` exists to refuse."""
    pack = _pack()
    # The day appears in the episode line and again in the window line, so its fragments match
    # in two places by construction.
    rendering = pair_claims("Read on 2026-04-15.", pack)
    claim = rendering.claims[0]

    assert claim.ambiguous
    assert "not resolved here" in claim.render()


# ── the pack's own lines ──────────────────────────────────────────────────────

def test_the_evidence_lines_carry_the_window_and_the_absent_signals() -> None:
    """Constraint 15 and constraint 14 together. A pairing that could not reach the window
    would report a date as unsupported, and one that could not reach the signal notes would
    have nothing to pair *"condenser flow has never been measured"* against."""
    kinds = {line.kind for line in evidence_lines(_pack())}

    assert EvidenceKind.WINDOW in kinds
    assert EvidenceKind.SIGNAL in kinds
    assert EvidenceKind.SOURCE in kinds


def test_an_evidence_line_is_the_pack_string_and_is_never_re_rendered() -> None:
    """The pack carries display strings rather than floats so a figure can be compared by
    exact value. Reformatting on the way past would reintroduce a tolerance, and every
    tolerance forgives some fabrication."""
    pack = _pack()
    texts = {line.text for line in evidence_lines(pack)}
    for evidence in pack.residual_evidence:
        assert evidence.render() in texts


def test_a_blind_gate_line_reaches_the_pairing() -> None:
    """`NO_DIAGNOSIS` is the modal outcome — 5,309 slots against 674 faulted — so a refusal's
    own text must be pairable, or the commonest answer the platform gives is the one nobody
    can check."""
    labels = {line.label for line in evidence_lines(_pack(blind=True))}
    assert Gate.RUNNING.value in labels


# ── the empty answer ──────────────────────────────────────────────────────────

def test_an_empty_answer_says_so_rather_than_reporting_a_clean_pairing() -> None:
    """Zero unsupported claims out of zero claims is not a clean answer, and an interface
    reading the boolean alone would badge it green."""
    rendering = pair_claims("   ", _pack())

    assert rendering.claims == ()
    assert "no claims to pair" in rendering.support_statement()
    assert "not the same as an answer whose every claim was supported" in (
        rendering.support_statement()
    )


def test_claims_keep_the_order_they_were_written_in() -> None:
    """The reader checks the answer as it was shown to them. A pairing over a reordered
    answer would be checking a text nobody was given."""
    claims = split_claims("First. Second.\nThird line.")
    assert claims == ("First.", "Second.", "Third line.")


# ── the integration that proves the pairing is usable ─────────────────────────

def test_the_deterministic_answer_pairs_completely_against_its_own_pack() -> None:
    """The strongest available check that the pairing is not simply strict.

    `deterministic_answer` is assembled from the pack and invents nothing, so every figure in
    it must pair. If this fails, the pairing is rejecting honest text — which is the failure
    mode that matters most, because a false accusation of fabrication silently withholds
    correct answers and nobody looks at what was withheld.
    """
    pack = _pack(others=("HIGH_HEAD_AMBIGUOUS",))
    rendering = pair_claims(deterministic_answer(pack), pack)

    assert rendering.unsupported == (), "\n".join(
        f"{c.text} -> {c.unmatched}" for c in rendering.unsupported
    )


def test_the_rendering_states_its_data_window() -> None:
    """Constraint 15: the pairing is an artefact of its own, and every artefact states its
    window. Anomaly counts were once shown under a heading describing a telemetry window that
    did not overlap them at all."""
    pack = _pack()
    assert pack.window.render() in pair_claims("Anything at all.", pack).render()
