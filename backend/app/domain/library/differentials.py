"""`RC12`'s content: 19 transcribed discriminators, and not one of them asked yet.

**The failure this file prevents.** A discriminator eliminates a cause irreversibly, and
nobody re-examines a settled question — so a wrong one does not produce a wrong answer once,
it produces a confident wrong answer that is never revisited. The defence is not better
wording; it is *knowing whose wording it is*. Inherited constraint 1: the library is curated
content, never model output. Constraint 26: the language model selects and contextualises
library content; it never authors a field instruction. Every question, cause, answer and
effect below was copied from the review pack character for character, and every one carries
the file and the heading it came from. Nothing was reworded, tightened, corrected or
completed, and no item, cause, answer or effect was added.

**Everything here is unreviewed, and that is operational rather than a caveat.**
`Question.sme_reviewed` is `False` on all 19, so `Differential.askable` returns nothing,
every differential reports `EXHAUSTED`, and no elimination can reach a user. That state must
hold until a refrigeration engineer signs the content off — it is the whole reason the
content is safe to hold in the repository at all.

**Not sample content.** `is_sample` on a checklist item means *invented to demonstrate the
mechanism*; this is the real library awaiting review. An illustrative instruction wastes a
walk to the machine, while an illustrative discriminator would rule a real cause out for
ever, so the two facts are kept apart and only one of them is true here.

**The transcription rules, so a reviewer can check the copy against the original:**

| In the source | Here |
|---|---|
| the quoted question in italics, where the heading has one | `Question.text` |
| the heading alone, where there is no quoted question | `Question.text` |
| the `## Differential n` heading and the `### Qn` heading | `Question.source` |
| the role tag on the question heading | `Question.capability` |
| a bold answer label in the effect table | `Answer.text`, emphasis removed |
| an effect cell: `confirm` / `eliminate` / `keep` | `Answer.effects` |
| an empty effect cell | absent from `effects`, never `KEEP` |
| the *My note* column on a cause | a comment, so it cannot be read as instruction text |
| the author's reasoning and the flagged doubts | comments |

All 19 questions offered *Can't tell* in the source, so **none was added** — constraint 30 is
satisfied by the original rather than by us. Every one maps to no effects at all.

All 19 questions carried a role tag on their heading, so **no tag was defaulted**: constraint
24's technician default did not have to fire anywhere in this file.

**Two known holes, preserved rather than fixed** — `CONTEXT.md` §10b, `Q37`. The
condenser-water-side differential's highest-power question is condenser water flow, and that
tag has never recorded a non-zero value on the reference plant, so the question that would
eliminate three causes at once cannot be answered from telemetry. And
`REFRIGERANT_SIDE_HIGH_HEAD` has no differential here because the source authored none — a
case can conclude there with no evidence. Inventing one to close the gap would be exactly the
unreviewed engineering judgement this file is shaped to avoid.
"""
from __future__ import annotations

from app.domain.cases import Capability
from app.domain.differential import (
    CANNOT_TELL,
    DIFFERENTIALS,
    Answer,
    Cause,
    Differential,
    Effect,
    Question,
)

#: The one file every object here was copied from. Read-only input, with the same standing as
#: `docs/00-source/`: a curated item that cannot name where it came from is indistinguishable
#: from model output.
SOURCE_FILE = "thermynx/docs/for-vishnu/06-differentials-for-review.md"

#: Transcribed once and shared. Constraint 30: *Can't tell* must map to no effects at all,
#: and a single frozen instance makes that impossible to get wrong in one table out of 19.
_CANNOT_TELL = Answer(CANNOT_TELL, "Can't tell", {})


def _cause(section: str, id_: str, text: str) -> Cause:
    return Cause(id=id_, text=text, source=f"{section} · Candidate causes")


def _question(
    *,
    section: str,
    label: str,
    ordinal: str,
    heading: str,
    text: str,
    capability: Capability,
    answers: tuple[Answer, ...],
) -> Question:
    """One transcribed question.

    The id is composed mechanically from the fault label and the source's own question
    number, so `Elimination.render` names a check a reviewer can find in the pack —
    constraint 31 asks for the check and the answer, and an opaque id answers neither.

    `sme_reviewed` is not a parameter. There is no argument any caller could pass that would
    make one of these reviewed, because none of them is.
    """
    return Question(
        id=f"{label}.{ordinal}",
        text=text,
        answers=(*answers, _CANNOT_TELL),
        capability=capability,
        source=f"{section} · {heading}",
    )


# ── Differential 1 · STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION ─────────────────────────────
# The source calls this "the cleanest one in the set, the demo case, and the one I am most
# confident about — which is exactly why being wrong here costs the most." It is the first
# question asked on 6 of the 39 fault episodes.
#
# The signature that led the author here: "Suction pressure is the deepest in the dataset
# (Sp residual −69) while current is barely raised (+7). That reads as starved, not straining
# — the compressor is not working harder, it is being fed less. And telemetry cannot separate
# a restriction from an undercharge, because both starve the evaporator identically."

_D1_LABEL = "STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION"
_D1 = f"{SOURCE_FILE} · Differential 1 · {_D1_LABEL}"

_D1_CAUSES = (
    # "Refrigerant cannot get through fast enough — the charge is fine"
    _cause(_D1, "restriction", "Liquid-line restriction (filter-drier)"),
    # "There is not enough refrigerant in the circuit"
    _cause(_D1, "undercharge", "Refrigerant undercharge"),
    _cause(_D1, "txv", "TXV not feeding correctly"),
    _cause(_D1, "evap_load", "Low evaporator load or flow"),
)

_D1_QUESTIONS = (
    # The author's reasoning: "a blockage makes refrigerant expand and go cold, so a cold spot
    # means a restriction; no cold spot means the charge is low instead."
    #
    # 🔴 Flagged for the reviewer, verbatim: "Can an undercharged circuit also produce a cold
    # spot across the drier? If it can, this test does not separate the two and I am
    # eliminating the wrong cause on the single most-used question in the system." And: "is it
    # safe to measure while the machine is running?"
    _question(
        section=_D1,
        label=_D1_LABEL,
        ordinal="Q1",
        heading="Q1 — Temperature drop across the filter-drier (inlet vs outlet)",
        text="Is there a measurable temperature drop across the filter-drier?",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "cold_spot",
                "Yes — a cold spot across it",
                {"restriction": Effect.CONFIRM, "undercharge": Effect.ELIMINATE},
            ),
            Answer("no_drop", "No drop", {"restriction": Effect.ELIMINATE}),
        ),
    ),
    # The author's reasoning: "clear glass with adequate subcooling argues against undercharge
    # — but a restriction upstream of the glass can still starve the evaporator, so it stays
    # live." Flagged: "is 'clear sight glass' enough to eliminate undercharge on its own, or
    # does it need subcooling alongside it? Right now the option is just 'clear' and it
    # eliminates."
    _question(
        section=_D1,
        label=_D1_LABEL,
        ordinal="Q2",
        heading="Q2 — Sight glass at full load",
        text="At full load, is the sight glass clear or showing bubbles?",
        capability=Capability.OPERATOR,
        answers=(
            Answer(
                "bubbles",
                "Bubbles or flashing",
                {"restriction": Effect.KEEP, "undercharge": Effect.CONFIRM},
            ),
            Answer(
                "clear",
                "Clear",
                {"restriction": Effect.KEEP, "undercharge": Effect.ELIMINATE},
            ),
        ),
    ),
    # The author's note: "'well above setpoint' moves nothing. The selector knows this question
    # is weak and will not ask it first." `Question.reach` is what makes that true here.
    _question(
        section=_D1,
        label=_D1_LABEL,
        ordinal="Q3",
        heading="Q3 — Measured superheat at the TXV vs setpoint",
        text="How does measured superheat compare with the TXV setpoint?",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "well_above_setpoint",
                "Well above setpoint",
                {
                    "restriction": Effect.KEEP,
                    "undercharge": Effect.KEEP,
                    "txv": Effect.KEEP,
                },
            ),
            Answer("at_setpoint", "At setpoint", {"txv": Effect.ELIMINATE}),
        ),
    ),
    # No quoted question in the source; the heading is the question.
    _question(
        section=_D1,
        label=_D1_LABEL,
        ordinal="Q4",
        heading="Q4 — Evaporator water flow and entering/leaving temps vs design",
        text="Evaporator water flow and entering/leaving temps vs design",
        capability=Capability.OPERATOR,
        answers=(
            Answer("below_design", "Flow or load below design", {"evap_load": Effect.CONFIRM}),
            Answer("at_design", "At design", {"evap_load": Effect.ELIMINATE}),
        ),
    ),
)

# Deliberately NOT transcribed as a discriminating question, and the source says why: *"Has
# this circuit been serviced recently?"* — "it shifts suspicion without eliminating anything.
# Encoding it as a discriminator would overstate it. It stays a plain checklist item, which is
# the honest place for weak corroborating context." The reviewer is asked whether it should
# carry weight after all; until they answer, it is absent here rather than guessed at.


# ── Differential 2 · HIGH_HEAD_AMBIGUOUS ─────────────────────────────────────────────────
# The commonest class — it appears on 12 of 12 fault days, usually with the most slots, and it
# is the least informative label in the set.

_D2_LABEL = "HIGH_HEAD_AMBIGUOUS"
_D2 = f"{SOURCE_FILE} · Differential 2 · {_D2_LABEL}"

_D2_CAUSES = (
    # "Heat cannot leave the refrigerant fast enough even with adequate flow"
    _cause(_D2, "fouling", "Condenser tubes fouled"),
    # "Less water through the condenser than design"
    _cause(_D2, "low_flow", "Condenser water flow below design"),
    # "The water arriving is already too warm"
    _cause(_D2, "tower", "Cooling tower not making design cold water"),
    # "Air raises head above what the condensing temperature explains"
    _cause(_D2, "non_cond", "Non-condensables (air) in the circuit"),
    _cause(_D2, "overcharge", "Refrigerant charge above nameplate"),
)

_D2_QUESTIONS = (
    # The author's reasoning: "a wide approach with adequate flow is the classic fouling
    # signature, and it cannot be a tower problem — the tower sets the water temperature, not
    # the approach across the condenser."
    #
    # 🔴 Two doubts flagged on this one question. First: "Is eliminating `tower` from a wide
    # approach correct? It is the strongest claim in this table and it rests entirely on that
    # one physical argument." Second, and it is a hole rather than a doubt: "This question may
    # be unanswerable on this plant. The `dpt` tag is a constant (107.0 on chiller 1, 112.9 on
    # chiller 2), so condenser approach cannot be computed at all." `CONTEXT.md` §10 carries
    # the same finding.
    _question(
        section=_D2,
        label=_D2_LABEL,
        ordinal="Q1",
        heading="Q1 — Condenser approach temperature vs design",
        text="How wide is the condenser approach — leaving water vs condensing temperature?",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "wider_than_design",
                "Wider than design",
                {
                    "fouling": Effect.CONFIRM,
                    "low_flow": Effect.KEEP,
                    "tower": Effect.ELIMINATE,
                },
            ),
            Answer("at_design", "At or near design", {"fouling": Effect.ELIMINATE}),
        ),
    ),
    # ⚠️ From the source: "`cond_flow` has never recorded a non-zero value on either chiller —
    # ever. So this question cannot be answered from data and must be measured by hand every
    # time. Is that tag connected to anything?"
    _question(
        section=_D2,
        label=_D2_LABEL,
        ordinal="Q2",
        heading="Q2 — Condenser water flow vs design",
        text="Condenser water flow vs design",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "below_design",
                "Below design",
                {"fouling": Effect.KEEP, "low_flow": Effect.CONFIRM},
            ),
            Answer("at_design", "At design", {"low_flow": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D2,
        label=_D2_LABEL,
        ordinal="Q3",
        heading="Q3 — Cooling tower performance",
        text="Is the tower making its design cold-water temperature?",
        capability=Capability.OPERATOR,
        answers=(
            Answer(
                "warmer_than_design",
                "No — water is warmer than design",
                {"tower": Effect.CONFIRM},
            ),
            Answer("yes", "Yes", {"tower": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D2,
        label=_D2_LABEL,
        ordinal="Q4",
        heading="Q4 — Non-condensables in the circuit",
        text="Is head pressure above saturation for the measured condenser water temperature?",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer("above_saturation", "Yes — above saturation", {"non_cond": Effect.CONFIRM}),
            Answer("matches", "No — it matches", {"non_cond": Effect.ELIMINATE}),
        ),
    ),
    # Tagged `supervisor` in the source: "I tagged it that way because it is a records
    # question, not a measurement". Flagged: "is a charge log trustworthy enough to eliminate
    # overcharge? And is `supervisor` the right role for it?"
    _question(
        section=_D2,
        label=_D2_LABEL,
        ordinal="Q5",
        heading="Q5 — Refrigerant charge vs nameplate",
        text="Does the charge log show more refrigerant than nameplate?",
        capability=Capability.SUPERVISOR,
        answers=(
            Answer("over_nameplate", "Over nameplate", {"overcharge": Effect.CONFIRM}),
            Answer("at_nameplate", "At nameplate", {"overcharge": Effect.ELIMINATE}),
        ),
    ),
)


# ── Differential 3 · CONDENSER_WATER_SIDE_UNSPECIFIED ────────────────────────────────────
# The causes arrive as one inline list in the source rather than a table, so there is no
# *My note* column to transcribe for any of them.

_D3_LABEL = "CONDENSER_WATER_SIDE_UNSPECIFIED"
_D3 = f"{SOURCE_FILE} · Differential 3 · {_D3_LABEL}"

_D3_CAUSES = (
    _cause(_D3, "fouling", "condenser tubes fouled"),
    _cause(_D3, "low_flow", "condenser water flow below design"),
    _cause(_D3, "strainer", "strainer blocked"),
    _cause(_D3, "tower", "cooling tower underperforming"),
    _cause(_D3, "pump", "condenser pump underperforming"),
)

_D3_QUESTIONS = (
    # The author's reasoning: "adequate flow with a failing condenser points at the surface,
    # not the hydraulics — so a blocked strainer and an underperforming pump both go."
    #
    # 🔴 "This is the most aggressive single answer in the whole system — one answer eliminates
    # three causes. Is it sound? Could a strainer be partly blocked, or a pump be off its
    # curve, while total flow still reads 'at design'?"
    #
    # This is also the hole `CONTEXT.md` §10b records: the highest-power question in this
    # differential is condenser water flow, and `cond_flow` has never recorded a non-zero
    # value on the reference plant — so it cannot be answered from telemetry at all. Recorded,
    # not fixed. `Q37`.
    _question(
        section=_D3,
        label=_D3_LABEL,
        ordinal="Q1",
        heading="Q1 — Condenser water flow vs design",
        text="Condenser water flow vs design",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "below_design",
                "Below design",
                {"fouling": Effect.KEEP, "low_flow": Effect.CONFIRM},
            ),
            Answer(
                "at_design",
                "At design",
                {
                    "fouling": Effect.KEEP,
                    "low_flow": Effect.ELIMINATE,
                    "strainer": Effect.ELIMINATE,
                    "pump": Effect.ELIMINATE,
                },
            ),
        ),
    ),
    _question(
        section=_D3,
        label=_D3_LABEL,
        ordinal="Q2",
        heading="Q2 — Strainer differential pressure",
        text="Strainer differential pressure",
        capability=Capability.OPERATOR,
        answers=(
            Answer(
                "high_restricted",
                "High — restricted",
                {"low_flow": Effect.CONFIRM, "strainer": Effect.CONFIRM},
            ),
            Answer("normal", "Normal", {"strainer": Effect.ELIMINATE}),
        ),
    ),
    # The source notes: "(Same `dpt` problem as differential 2 — the approach may not be
    # computable here.)"
    _question(
        section=_D3,
        label=_D3_LABEL,
        ordinal="Q3",
        heading="Q3 — Condenser approach temperature",
        text="Condenser approach temperature",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "wider_than_design",
                "Wider than design",
                {"fouling": Effect.CONFIRM, "tower": Effect.ELIMINATE},
            ),
            Answer("at_design", "At design", {"fouling": Effect.ELIMINATE}),
        ),
    ),
    # 🔴 Flagged: "'it looks right' is a visual answer eliminating a performance cause. A tower
    # can look perfect and still not make design cold water. Should this eliminate, or only
    # keep?" It eliminates here because that is what the source table says.
    _question(
        section=_D3,
        label=_D3_LABEL,
        ordinal="Q4",
        heading="Q4 — Cooling tower condition (fill, basin, distribution, fan)",
        text="Cooling tower condition (fill, basin, distribution, fan)",
        capability=Capability.OPERATOR,
        answers=(
            Answer("something_wrong", "Something is wrong with it", {"tower": Effect.CONFIRM}),
            Answer("looks_right", "It looks right", {"tower": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D3,
        label=_D3_LABEL,
        ordinal="Q5",
        heading="Q5 — Condenser water pump performance vs curve",
        text="Condenser water pump performance vs curve",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "below_curve",
                "Below curve",
                {"low_flow": Effect.CONFIRM, "pump": Effect.CONFIRM},
            ),
            Answer("on_curve", "On curve", {"pump": Effect.ELIMINATE}),
        ),
    ),
)


# ── Differential 4 · POWER_HIGH_UNEXPLAINED ──────────────────────────────────────────────
# "Electrical, not thermodynamic. The current is up with no coherent thermal story behind it."

_D4_LABEL = "POWER_HIGH_UNEXPLAINED"
_D4 = f"{SOURCE_FILE} · Differential 4 · {_D4_LABEL}"

_D4_CAUSES = (
    _cause(_D4, "imbalance", "voltage or current imbalance"),
    _cause(_D4, "motor", "motor winding/insulation degradation"),
    _cause(_D4, "load", "the machine is genuinely running at higher load"),
    _cause(_D4, "vfd", "VFD misconfiguration or fault"),
    _cause(_D4, "connection", "loose or hot electrical connection"),
)

_D4_QUESTIONS = (
    # Marked **ASKED FIRST** on its heading in the source. Nothing encodes that here, and
    # nothing needs to: `Question.reach` scores it highest because it can move five causes,
    # which is constraint 39 arriving at the author's ordering from the data.
    #
    # The author's reasoning: "if the load explains the current there is no electrical fault to
    # chase, and this is the one question an operator can answer straight off the panel. One
    # free reading can settle the whole class."
    #
    # 🔴 "This is the single most powerful answer in the system — it eliminates four causes at
    # once. Is that defensible? Could a machine be both genuinely more loaded and carrying a
    # loose connection or a phase imbalance? If so this is the most dangerous line in the
    # file." Note what the four eliminations are *not*: they are not a consequence of the
    # `load` confirmation. Constraint 28 holds — each one is written out in the source table,
    # and that is precisely what the reviewer is being asked about.
    _question(
        section=_D4,
        label=_D4_LABEL,
        ordinal="Q1",
        heading="Q1 — Actual load vs the current curve",
        text="Is the machine actually running harder than the current suggests it should?",
        capability=Capability.OPERATOR,
        answers=(
            Answer(
                "load_genuinely_higher",
                "Yes — load is genuinely higher",
                {
                    "imbalance": Effect.ELIMINATE,
                    "motor": Effect.ELIMINATE,
                    "load": Effect.CONFIRM,
                    "vfd": Effect.ELIMINATE,
                    "connection": Effect.ELIMINATE,
                },
            ),
            Answer("load_normal", "No — load is normal", {"load": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D4,
        label=_D4_LABEL,
        ordinal="Q2",
        heading="Q2 — Phase currents and voltage balance at the starter",
        text="Phase currents and voltage balance at the starter",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "unbalanced",
                "Unbalanced",
                {"imbalance": Effect.CONFIRM, "connection": Effect.KEEP},
            ),
            Answer("balanced", "Balanced", {"imbalance": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D4,
        label=_D4_LABEL,
        ordinal="Q3",
        heading="Q3 — Motor winding resistance and insulation (megger)",
        text="Motor winding resistance and insulation (megger)",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer("out_of_spec", "Out of spec", {"motor": Effect.CONFIRM}),
            Answer("within_spec", "Within spec", {"motor": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D4,
        label=_D4_LABEL,
        ordinal="Q4",
        heading="Q4 — VFD parameters and fault history, if fitted",
        text="VFD parameters and fault history, if fitted",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer(
                "faults_or_wrong_parameters",
                "Yes — faults or wrong parameters",
                {"vfd": Effect.CONFIRM},
            ),
            Answer("none_found", "No, or none fitted", {"vfd": Effect.ELIMINATE}),
        ),
    ),
    _question(
        section=_D4,
        label=_D4_LABEL,
        ordinal="Q5",
        heading="Q5 — Starter and panel thermography",
        text="Starter and panel thermography",
        capability=Capability.TECHNICIAN,
        answers=(
            Answer("hot_spots", "Yes — hot spots", {"connection": Effect.CONFIRM}),
            Answer("no", "No", {"connection": Effect.ELIMINATE}),
        ),
    ),
)


#: The four transcribed differentials, by fault label. Constraint 27: only a class the trained
#: model declares undecidable has one, and the source authored exactly four — the classes whose
#: own names say *ambiguous*, *unspecified*, *unexplained*, and *undercharge **or**
#: restriction*. Narrowing a class that already names a mechanism would invent ambiguity the
#: model never reported, so the other classes are absent rather than thin.
#:
#: `REFRIGERANT_SIDE_HIGH_HEAD` is the absence that matters: it declares itself decided, yet it
#: names a region rather than a mechanism and carries no blocking item, so a case can conclude
#: there with no evidence. `Q37` records that. Nothing here fills it.
LIBRARY: dict[str, Differential] = {
    _D1_LABEL: Differential(
        fault_label=_D1_LABEL, causes=_D1_CAUSES, questions=_D1_QUESTIONS, source=_D1
    ),
    _D2_LABEL: Differential(
        fault_label=_D2_LABEL, causes=_D2_CAUSES, questions=_D2_QUESTIONS, source=_D2
    ),
    _D3_LABEL: Differential(
        fault_label=_D3_LABEL, causes=_D3_CAUSES, questions=_D3_QUESTIONS, source=_D3
    ),
    _D4_LABEL: Differential(
        fault_label=_D4_LABEL, causes=_D4_CAUSES, questions=_D4_QUESTIONS, source=_D4
    ),
}


def register() -> dict[str, Differential]:
    """Fill `app.domain.differential.DIFFERENTIALS` in place, and hand it back.

    **Why the content registers itself rather than being read from the other side.** The types
    live in `app.domain.differential` and the content is written in terms of them, so this
    module must import upwards; the registry the rest of the code reads lives in that same
    module. Updating the existing dict in place is the one wiring that survives either import
    order — having `differential.py` reach for `LIBRARY` instead would fail for anyone who
    imports this module first, which the tests do.
    """
    DIFFERENTIALS.update(LIBRARY)
    return DIFFERENTIALS


register()
