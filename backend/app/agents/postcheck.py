"""The postcheck audits — the honesty layer, which **overrides the model rather than advising it**.

Inherited constraint 16. A reassuring headline over a blind window is replaced outright and
the record marked corrected. These are deterministic functions over the answer text and the
pack: no model judges another model here, because an auditor that can be talked round is not
an auditor.

**The argument for keeping this in the cut, in one sentence from the sibling:** the honesty
layer shipped with a reassuring lie that **56 unit tests, a clean typecheck and a 100%
evaluation score all missed, and reading one live report caught**. That is `EV4`, and it is
why the meta-tests below feed deliberately dishonest answers to the gate.

**How the numeric audit actually works, and the trap in it.** The pack hands the model
*display strings*, never raw floats, so `-25.645` reaches it as the exact characters it must
reproduce. The obvious check is then substring containment — is the answer's number inside
the pack's text?

**That check is worse than useless, and this file shipped with it.** `-25.6` is a substring
of `-25.645`, so the precise truncation the audit exists to catch sailed through, and the
test written to catch a truncated figure passed against it. Both sides are now tokenised
into numbers and compared by **exact value**: `-20.0` matches a pack rendering of `-20`
because nothing was lost, and `-25.6` does not match `-25.645` because a truncated figure in
a report about instrumentation is a different claim. Exact equality, never a tolerance — a
tolerance has to be chosen, and every choice forgives some fabrication.

Six audits, and the soft critique gate. Five are **hard**: they correct or refuse. The sixth
badges. Constraint 17 — some evaluation dimensions are hard and exempt from any overall
tolerance, because a report whose own figures disagree cannot pass on the strength of
scoring well elsewhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain import equipment as eq
from app.domain import signals
from app.services.evidence import EvidencePack


class AuditSeverity(StrEnum):
    HARD = "hard"
    """Fails the answer. It is corrected or replaced, never merely annotated."""

    SOFT = "soft"
    """Badges the answer. The reader is told; the answer still ships."""


@dataclass(frozen=True)
class AuditFinding:
    audit: str
    passed: bool
    severity: AuditSeverity
    detail: str = ""
    offending: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AuditReport:
    findings: tuple[AuditFinding, ...]

    @property
    def passed(self) -> bool:
        return all(f.passed for f in self.findings)

    @property
    def hard_failures(self) -> tuple[AuditFinding, ...]:
        return tuple(
            f for f in self.findings if not f.passed and f.severity is AuditSeverity.HARD
        )

    @property
    def soft_failures(self) -> tuple[AuditFinding, ...]:
        return tuple(
            f for f in self.findings if not f.passed and f.severity is AuditSeverity.SOFT
        )

    @property
    def must_replace_answer(self) -> bool:
        """A hard failure is not a warning. The answer does not ship as written."""
        return bool(self.hard_failures)


# A number in prose: 141, -25.645, 1,099.6, 48.03. Percentages and years are excluded
# separately below rather than by pattern, because "2026" and "20%" are numbers the model
# may legitimately produce without them appearing in the pack.
_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")

#: Numbers a model may state without the pack containing them. Small integers are counts
#: it can legitimately derive — "all five residuals", "two of twelve" — and a four-digit
#: year is a date, not a measurement.
_ALLOWED_BARE = frozenset(str(n) for n in range(0, 13))


# ── the number normaliser, and why it lives HERE ────────────────────────────────
#
# **This must sit in the layer that withholds answers, not above it.** It was written in
# `app.eval` first, which is above `app.agents` in the spine — so the honesty layer that
# actually suppresses a live answer structurally could not reach it, and the wider fold only
# ever ran in an after-the-fact report nobody triggered. Found in adversarial review the same
# day it was written.
#
# The failure it prevents, from the incident on 2026-08-17: the evidence said `−273.2` with
# U+2212 because it is typeset prose, the model replied `-273.2` with an ASCII hyphen, and the
# tokeniser read one as positive and the other as negative. The audit reported the model had
# invented a figure it had quoted correctly, and a true answer was withheld.
#
# **That is the worse of the two failures, and the asymmetry is the whole point.** A fabricated
# number is caught by any reader who checks it. A false accusation of fabrication silently
# suppresses correct answers, and there is no reader on that path at all.
#
# So the fold is deliberately wide: every dash a human or a model might type, the spaces that
# split a number in typeset prose, and fullwidth digits. Applied to BOTH sides — widening one
# side only would make the gate either forgiving of the model or accusing of it, and the point
# is neither. Two spellings of one figure are one figure.

_WIDER_MINUS = str.maketrans(
    {
        "−": "-",  # MINUS SIGN — what typeset prose uses, and what caused the incident
        "–": "-",  # EN DASH
        "—": "-",  # EM DASH
        "‒": "-",  # FIGURE DASH
        "‑": "-",  # NON-BREAKING HYPHEN — indistinguishable from a hyphen on screen
        "﹣": "-",  # SMALL HYPHEN-MINUS
        "－": "-",  # FULLWIDTH HYPHEN-MINUS
        "­": "",   # SOFT HYPHEN — renders as nothing, and splits a number in two
    }
)

#: Spaces that appear *inside* a rendered number. `1 099.6` with a narrow no-break space is
#: ordinary typography and tokenises as two numbers, so a correctly quoted figure reads as two
#: fabricated ones.
_DIGIT_SPACES = str.maketrans(
    {
        " ": "",  # NO-BREAK SPACE
        " ": "",  # FIGURE SPACE — designed for this job, and it splits the token
        " ": "",  # PUNCTUATION SPACE
        " ": "",  # THIN SPACE
        " ": "",  # NARROW NO-BREAK SPACE — the SI thousands separator
    }
)

#: Fullwidth digits. Rare in prose and trivial to fold, and a number written in them is not a
#: different number.
_FULLWIDTH_DIGITS = str.maketrans({chr(0xFF10 + n): str(n) for n in range(10)})

_SIGN_GAP_RE = re.compile(r"(?<=-)[ \t]+(?=\d)")


def widen(text: str) -> str:
    """Fold every typographic variant of a number down to one spelling.

    Used on **both** sides of the comparison, never on one. Widening only the answer would
    make the gate more forgiving of the model; widening only the evidence would make it more
    accusing. The point is not leniency — it is that two spellings of the same figure are the
    same figure, and a gate that cannot see that withholds correct answers.
    """
    folded = text.translate(_WIDER_MINUS).translate(_DIGIT_SPACES)
    return _SIGN_GAP_RE.sub("", folded.translate(_FULLWIDTH_DIGITS))


def _numbers_in(text: str) -> list[str]:
    out: list[str] = []
    for m in _NUMBER_RE.finditer(widen(text)):
        token = m.group(0).rstrip(".").replace(",", "")
        if not token or token in ("-",):
            continue
        if token in _ALLOWED_BARE:
            continue
        if re.fullmatch(r"(19|20)\d{2}", token):  # a year
            continue
        out.append(token)
    return out


def evidence_text(pack: EvidencePack) -> str:
    """Everything the writer was given, as one string.

    Public because the critique gate needs exactly what the deterministic audits compare
    against — if the two read different evidence, a disagreement between them says nothing
    about the answer.
    """
    return _pack_strings(pack)


def _pack_strings(pack: EvidencePack) -> str:
    """Every display string the model was handed, concatenated for containment testing."""
    data = pack.to_prompt_data()
    parts: list[str] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)
        else:
            parts.append(str(value))

    walk(data)
    return " ".join(parts)


# ── audit 1 · every number came from the pack ───────────────────────────────────

def _as_value(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def audit_numbers(answer: str, pack: EvidencePack) -> AuditFinding:
    """`EV4`'s headline. A number the pack does not contain was invented.

    **Token comparison, not substring containment.** The obvious implementation — is this
    number's text inside the pack's text — is worse than useless: `-25.6` is a substring of
    `-25.645`, so the exact truncation this audit exists to catch would sail through. The
    first version of this function had that bug, and the test written to catch a truncated
    figure passed against it.

    So both sides are tokenised into numbers and compared by **exact value**. `-20.0`
    matches a pack rendering of `-20` because they are the same number and nothing was lost;
    `-25.6` does not match `-25.645`, because a truncated figure in a report about
    instrumentation is a different claim. Exact equality, never a tolerance — a tolerance
    would have to be chosen, and any choice forgives some fabrication.
    """
    grounded = {
        v for v in (_as_value(t) for t in _numbers_in(_pack_strings(pack))) if v is not None
    }
    invented = [
        token
        for token in _numbers_in(answer)
        if (value := _as_value(token)) is None or value not in grounded
    ]
    return AuditFinding(
        audit="numbers_are_grounded",
        passed=not invented,
        severity=AuditSeverity.HARD,
        detail=(
            f"{len(invented)} number(s) appear in the answer and not in the evidence"
            if invented
            else "every number in the answer appears in the evidence"
        ),
        offending=tuple(invented),
    )


# ── audit 2 · the equipment exists ──────────────────────────────────────────────

_EQUIPMENT_MENTION_RE = re.compile(r"\bchiller[\s_-]*(\d+)\b", re.IGNORECASE)


def audit_equipment(answer: str, pack: EvidencePack) -> AuditFinding:
    """A model naming `chiller 3` on a two-chiller site is the most convincing kind of wrong.

    Checked against the site catalog rather than against the pack: a correct answer may
    legitimately mention the *other* chiller for contrast, but neither of them may be a
    machine that does not exist.
    """
    known = {e.key for e in eq.all_equipment()}
    invented = [
        f"chiller {n}" for n in _EQUIPMENT_MENTION_RE.findall(answer)
        if f"chiller_{n}" not in known
    ]
    return AuditFinding(
        audit="equipment_exists",
        passed=not invented,
        severity=AuditSeverity.HARD,
        detail=(
            f"the answer names equipment that does not exist: {', '.join(invented)}"
            if invented
            else "every machine named exists on this site"
        ),
        offending=tuple(invented),
    )


# ── audit 3 · never-measured signals are not quoted as readings ─────────────────

_READING_VERBS = ("is", "was", "reads", "reading", "measured", "at", "of")


def audit_never_measured(answer: str, pack: EvidencePack) -> AuditFinding:
    """The one that matters most on this plant.

    `cond_flow` has never recorded a non-zero value, and it feeds four of the six models. An
    answer quoting condenser flow as a reading is not slightly wrong — it asserts an
    instrumentation capability the site does not have, which is the failure D-009 exists to
    prevent and the one the simulated window makes easy.
    """
    lowered = answer.lower()
    offending: list[str] = []

    # Read from the **pack**, not from the module-level registry. A pack built with derived
    # availability is audited against what was computed for it against this database; one
    # built without still gets the registry's five, so nothing regresses. Reading a global
    # table from inside an audit made the verdict independent of the evidence it audited —
    # which is how a stale registry entry could have vouched for a signal the data had
    # already contradicted.
    never_measured = pack.never_measured_signals or tuple(
        s.display_name
        for s in signals.SIGNALS
        if s.status is signals.SignalStatus.NEVER_MEASURED
    )

    for display_name in never_measured:
        name = display_name.lower()
        if name not in lowered:
            continue
        # Mentioning it is fine — *"condenser flow has never been measured"* is the correct
        # sentence. Quoting a value for it is not.
        window = lowered[lowered.index(name) : lowered.index(name) + 120]
        if any(re.search(rf"\b{v}\b\s*-?\d", window) for v in _READING_VERBS):
            offending.append(display_name)

    return AuditFinding(
        audit="never_measured_not_quoted",
        passed=not offending,
        severity=AuditSeverity.HARD,
        detail=(
            f"quoted as a reading despite never being measured: {', '.join(offending)}"
            if offending
            else "no never-measured signal is quoted as a reading"
        ),
        offending=tuple(offending),
    )


# ── audit 4 · the answer states its window ──────────────────────────────────────

def audit_window(answer: str, pack: EvidencePack) -> AuditFinding:
    """`C22`, constraint 15. On a snapshot, an answer with no window is a lie by omission.

    Anomaly counts were once shown on the database wall clock under a heading describing a
    telemetry window that did not overlap it at all.
    """
    day = pack.day.isoformat()
    stated = day in answer or pack.window.render()[:10] in answer
    return AuditFinding(
        audit="window_is_stated",
        passed=stated,
        severity=AuditSeverity.HARD,
        detail=(
            "the answer states the window it covers"
            if stated
            else f"the answer never states its window; it covers {day}"
        ),
    )


# ── audit 5 · the model did not diagnose ────────────────────────────────────────

#: Phrases that assert a fault the FDD rules did not name. The separation law's fourth row:
#: which fault class this is, is decided by the deterministic isolation path — never here.
_DIAGNOSIS_CLAIMS = (
    "i diagnose", "the fault is", "the root cause is", "this is definitely",
    "the problem is definitely", "i have determined", "i conclude that the fault",
    "it is certainly", "the cause is definitely",
)


#: Phrases that always assert a diagnosis, whatever else is in the sentence. Naming the pack's
#: own label does not excuse them, because there is no reading of "I diagnose" in which the
#: model is relaying somebody else's verdict.
_NEVER_EXCUSED: tuple[str, ...] = ("definitely", "i diagnose", "i have")


def _excused_in_context(lowered: str, phrase: str, label: str) -> bool:
    """Is this diagnosis phrase explaining the pack's label, or asserting a new one?

    Sentence-scoped. A phrase is excused only where it sits **in the same sentence** as the
    label — that is the difference between *"HIGH_HEAD_AMBIGUOUS means the head pressure is
    high"* and *"HIGH_HEAD_AMBIGUOUS was flagged. The root cause is a fouled condenser."*
    """
    if any(never in phrase for never in _NEVER_EXCUSED):
        return False

    # Every sentence carrying the phrase must also carry the label. One that does not is a
    # claim standing on its own, whatever the rest of the answer said.
    sentences = re.split(r"(?<=[.!?])\s+|\n+", lowered)
    return all(label in s for s in sentences if phrase in s)


def audit_no_diagnosis_by_model(answer: str, pack: EvidencePack) -> AuditFinding:
    """The separation law, enforced on the output.

    The model explains the label the FDD rules produced. It must not produce one of its own,
    and it must not upgrade an ambiguous class into a specific mechanism — four of seven
    classes declare themselves undecidable, and narrowing one is inventing a certainty the
    trained model explicitly declined to claim.
    """
    lowered = answer.lower()
    offending = [p for p in _DIAGNOSIS_CLAIMS if p in lowered]

    # Naming the class the pack already carries is explaining, not diagnosing — but the
    # exemption is **scoped to the sentence**, not to the answer.
    #
    # Found by the adversarial suite on 2026-08-17. It used to be answer-wide, so any answer
    # that mentioned the pack's own label *anywhere* had every non-"definitely" diagnosis
    # phrase filtered out. That shipped:
    #
    #   "The rules flagged HIGH_HEAD_AMBIGUOUS. The root cause is a fouled condenser."
    #
    # The first sentence is explaining; the second is the model narrowing an undecidable class
    # into a mechanism the trained model explicitly declined to name — which is precisely the
    # separation law's fourth row, and precisely what this audit exists to catch.
    if pack.fault_label:
        label = pack.fault_label.lower().replace("_", " ")
        offending = [
            phrase
            for phrase in offending
            if not _excused_in_context(lowered, phrase, label)
        ]

    return AuditFinding(
        audit="model_did_not_diagnose",
        passed=not offending,
        severity=AuditSeverity.HARD,
        detail=(
            f"the answer asserts a diagnosis of its own: {', '.join(offending)}"
            if offending
            else "the answer explains the rules' verdict rather than producing one"
        ),
        offending=tuple(offending),
    )


# ── audit 6 · a poor fit is disclosed ───────────────────────────────────────────

def audit_fit_disclosed(answer: str, pack: EvidencePack) -> AuditFinding:
    """Chiller 1's current model runs at nRMSE 48.03 and its residual is out of band in 402
    of 412 high-head readings. An answer quoting that residual confidently, without saying
    the model barely fits, is the reassuring-lie shape exactly.

    **Soft**, not hard. The answer is still useful and the interface badges it — hiding it
    would be worse, and acceptance case 14 shows a badged machine beside a clean one on
    purpose.
    """
    if not pack.has_poor_fit:
        return AuditFinding(
            audit="poor_fit_disclosed",
            passed=True,
            severity=AuditSeverity.SOFT,
            detail="no residual in this pack comes from a poorly fitted model",
        )

    lowered = answer.lower()
    disclosed = any(
        t in lowered
        for t in ("nrmse", "poor fit", "poorly fitted", "fit is poor", "model error",
                  "barely fits", "caution", "artefact", "artifact")
    )
    return AuditFinding(
        audit="poor_fit_disclosed",
        passed=disclosed,
        severity=AuditSeverity.SOFT,
        detail=(
            "the answer discloses that a model fits poorly"
            if disclosed
            else "a residual comes from a model at nRMSE 48.03 and the answer does not say so"
        ),
    )


# ── the gate ────────────────────────────────────────────────────────────────────

#: Phrases that assert a work order now exists. Held as data so the set is inspectable and
#: widening it is a decision rather than a regex somebody stretched.
_CLAIMS_A_WORK_ORDER = (
    "work order has been",
    "work order was",
    "i have raised",
    "i have created",
    "i have drafted",
    "have raised a work order",
    "created a work order",
    "raised a work order",
    "drafted a work order",
    "wo-",
    "please review and confirm this work order",
)


def audit_phantom_work_order(answer: str, pack: EvidencePack) -> AuditFinding:
    """An answer that *claims* to have raised a work order without one existing.

    **From a live failure in the Thermynx implementation, not from imagination.** Asked to raise
    a work order, the model produced a beautifully formatted draft — equipment id, title,
    diagnosis citing real figures, recommended actions — ending *"Please review and confirm this
    work order."* It had called one read-only tool and nothing else. **The work order was prose,
    not a proposal:** no Approve control, because the interface keys off the tool frame, and no
    substantiation guard, because none had run. And it reads exactly like the feature working,
    which is what makes it dangerous rather than merely wrong.

    Synex has the same shape of risk. `prepare_work` returns `NEEDS_APPROVAL` and the surface
    renders an approval affordance from *that state*; an `explain` turn whose prose announces a
    work order produces no such state and no such control, so a reader is told something was
    raised and nothing was.

    **Hard, and this is where Synex parts from the implementation it inherited.** Thermynx
    treats the phantom work order as one flag among six, feeding a soft badge. Here it replaces
    the answer, because of what the false sentence *causes*: a reader told a job was raised does
    not raise one. The fault is real, the evidence is real, and the work never happens — which
    is case 8, operational silence, arriving through the one door the honesty layer watches.
    Constraint 16 is that the honesty layer overrides the model rather than advising it, and a
    reassuring sentence followed by a caveat is still read as reassuring.
    """
    lowered = answer.lower()
    hits = tuple(p for p in _CLAIMS_A_WORK_ORDER if p in lowered)

    # A turn that genuinely drafted one carries the draft on the pack, and `prepare_work`
    # renders it from there. If the pack has one, the claim is substantiated by definition.
    drafted = bool(getattr(pack, "work_order_draft", None))

    if not hits or drafted:
        return AuditFinding(
            audit="no_phantom_work_order",
            passed=True,
            severity=AuditSeverity.SOFT,
            detail="the answer claims no work order it did not raise",
        )
    return AuditFinding(
        audit="no_phantom_work_order",
        passed=False,
        severity=AuditSeverity.HARD,
        detail=(
            "the answer says a work order exists, and this turn raised none. Nothing was "
            "written and there is no approval control behind the sentence — a reader told a "
            "job was raised will not raise it themselves."
        ),
        offending=hits,
    )


AUDITS = (
    audit_numbers,
    audit_equipment,
    audit_never_measured,
    audit_window,
    audit_no_diagnosis_by_model,
    audit_fit_disclosed,
    audit_phantom_work_order,
)


def run_audits(answer: str, pack: EvidencePack) -> AuditReport:
    """Every audit, always. None short-circuits.

    Running all six even after the first failure is deliberate: the record should say
    everything that was wrong with an answer, not the first thing. An answer that invented a
    number *and* quoted condenser flow is a different problem from one that only did the
    first, and truncating the report would hide the second.
    """
    return AuditReport(tuple(a(answer, pack) for a in AUDITS))


def correction_for(report: AuditReport, pack: EvidencePack) -> str:
    """What replaces an answer that failed a hard audit.

    Constraint 16: the honesty layer overrides the model, it does not advise it. So this is
    a replacement, not an appended warning — a reassuring paragraph followed by a caveat is
    still read as reassuring.
    """
    reasons = "; ".join(f.detail for f in report.hard_failures)
    return (
        f"The drafted answer was withheld because it failed an honesty check: {reasons}. "
        f"What the evidence actually supports for {pack.equipment_display} on "
        f"{pack.day.isoformat()}: the detected label is "
        f"{pack.fault_label or 'none on this slot'}, severity {pack.severity_text}, over "
        f"{pack.slot_count} slot(s) in {pack.window.render()}."
    )
