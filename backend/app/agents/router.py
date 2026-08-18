"""Intent routing — cheapest and most certain first, and **no layer may raise**.

`docs/20-architecture/03-from-thermynx.md` §8. Eight layers; each degrades into the next, and
a failure anywhere falls through rather than throwing. A router that can throw turns a
mistyped question into a stack trace, and on a demonstration that reads as a broken product
rather than an unclear question.

| # | Layer | Cost |
|--:|---|---|
| 0 | Override — the user picked a mode chip | 0 ms |
| 1 | Preflight guard — deterministic refusals | ~1 ms |
| 1.5 | Conversational fast path — never the cold off-topic refusal | 0 ms |
| 2 | Deterministic extraction — equipment and window, carrying the last unit forward | ~1 ms |
| 3 | Keyword heuristics, ordered, first match wins | ~1 ms |
| 3.5 | Scope gate — refuse **before any inference** | ~1 ms |
| 4 | Model arbiter — JSON only, hard 3 s timeout | 1–3 s |
| 5 | Reconcile — the arbiter's equipment is accepted only if it is real | ~0 ms |

**Why keyword layers exist when a model is right there.** Three reasons, and all three are
ours too. *Latency* — the round trip is most of the answer time on "how many chillers are
running". *Determinism* — the same message always routes the same way, so routing is
testable; forty fixed messages route correctly with the GPU off, and that is a unit test
rather than an evaluation. *Cost* — layer 4 is the only one that spends a model call, and
`router_arbiter_timeout_s` is 3 s precisely so routing cannot cost more than answering.

**Layer 5 is the one that matters for honesty.** The arbiter may name equipment that does
not exist; it is accepted **only if the catalog confirms it**. Deterministic facts win over
the model, always — the model proposes a route, it never establishes one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain import equipment as eq


class Skill(StrEnum):
    """The seven skills in the MVP. A skill is a named entry in the `C20` registry."""

    CONVERSE = "converse"
    LOOK_UP = "look_up"
    EXPLAIN = "explain"
    INVESTIGATE = "investigate"
    PREPARE_WORK = "prepare_work"
    RESOLVE = "resolve"
    VERIFY = "verify"
    REFUSE = "refuse"
    """Not a skill in the registry — the outcome when the scope gate declines."""


@dataclass(frozen=True)
class RouteDecision:
    """Where the turn goes, decided at which layer, and why.

    `layer` is carried into the `route` SSE frame and shown in the Inspector. Seeing that a
    question was routed at layer 3 for ~1 ms, with no model involved, is a large part of what
    makes the architecture legible during a demonstration.
    """

    skill: Skill
    layer: str
    reason: str
    equipment_key: str | None = None
    used_model: bool = False
    refusal_text: str = ""
    matched_terms: tuple[str, ...] = field(default_factory=tuple)


# ── layer 1: the deterministic refusals ─────────────────────────────────────────

#: Refused before any inference, each with the reason stated. These are not safety theatre:
#: the first two are the failure modes that actually occur in a demonstration.
_CONTROL_VERBS = (
    "turn on", "turn off", "switch on", "switch off", "start the", "stop the",
    "shut down", "restart", "set the setpoint", "change the setpoint", "override",
)

_REFUSAL_CONTROL = (
    "Synex is read-only with respect to plant equipment. No tool in any phase issues a "
    "control command to a machine, so this cannot be actioned here — it needs the plant "
    "control system and someone with the authority to use it."
)

_REFUSAL_FUTURE = (
    "This asks about the future. Synex reads a snapshot of what the plant recorded; it does "
    "not forecast, and a number presented as a prediction would be a guess wearing a unit."
)

_FUTURE_TERMS = ("will it", "predict", "forecast", "next week", "next month", "tomorrow")


# ── layer 1.5: the conversational fast path ─────────────────────────────────────

_GREETINGS = frozenset(
    {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "thanks",
     "thank you", "ok", "okay"}
)

_CAPABILITY_QUESTIONS = (
    "what can you do", "what do you do", "help", "who are you", "what is this",
    "capabilities", "how do i use",
)


# ── layer 3: the keyword heuristics, ordered. First match wins. ─────────────────

_KEYWORDS: tuple[tuple[Skill, tuple[str, ...]], ...] = (
    # `verify` before `explain`: "did the repair work" contains "work" and would otherwise
    # be caught by prepare-work. Order is the whole mechanism at this layer.
    (Skill.VERIFY, ("did the repair", "did it work", "verify", "confirm the fix",
                    "prove the repair", "after the work")),
    (Skill.PREPARE_WORK, ("work order", "raise a job", "schedule", "assign", "job pack",
                          "create work")),
    (Skill.RESOLVE, ("checklist", "what should i check", "next step", "root cause",
                     "narrow it down", "rule out")),
    (Skill.EXPLAIN, ("why", "explain", "what does it mean", "cause", "reason",
                     "what happened")),
    (Skill.INVESTIGATE, ("compare", "trend", "history", "over time", "both chillers",
                         "pattern", "how often")),
    (Skill.LOOK_UP, ("how many", "list", "show me", "what is the", "count", "value of",
                     "reading",
                     # Catalogue phrasings. These reach for a *set* rather than a figure —
                     # "what equipment do we have", "which fault classes can it report" — and
                     # every one of them routed to `explain` and came back "no scored evidence"
                     # while `list_equipment` and `list_fault_classes` sat registered and
                     # unreached. Kept last so a question that is really an explanation still
                     # matches `explain` first.
                     "what equipment", "which equipment", "what fault", "which fault",
                     "fault classes", "do we have", "are there", "can the model",
                     "what can you", "what do you")),
)

#: Domain vocabulary. A message with none of this and no named equipment is out of scope,
#: and layer 3.5 refuses it **before** any model call.
_DOMAIN_TERMS = (
    "chiller", "compressor", "condenser", "evaporator", "refrigerant", "residual",
    "fault", "alarm", "temperature", "pressure", "flow", "efficiency", "kw", "plant",
    "cooling tower", "pump", "maintenance", "work order", "case", "diagnos", "head",
    "suction", "discharge", "power", "load", "setpoint", "equipment", "sensor",
    # Added 2026-08-18. "How many episodes are there?" was refused as out of scope — layer 3
    # had already proposed `look_up` and the scope gate overrode it, because none of these
    # words was listed. A false refusal is worse than a wrong route: it tells a reader the
    # product does not cover its own core vocabulary.
    "episode", "asset", "machine", "unit", "band", "model", "signal", "provenance",
    "checklist", "priority", "verification", "report", "gate", "measured", "window",
    # `verify` and `resolve` had no vocabulary of their own. "Did the repair work?" matched
    # the VERIFY keywords at layer 3 and was then refused as off-topic at 3.5, because not one
    # of "repair", "fix" or "job" was listed — so the product rejected its own core question.
    # Found while widening for "episode", and pre-existing rather than caused by it.
    "repair", "fix", "job", "inspect", "clean", "replace", "close", "approve",
    # "check" is this product's own word — checklists, blocking checks, the close gate — and
    # "what should I check?" is one of the four questions the whole resolve path exists for.
    # "evidence" is deliberately NOT here. It is genuine domain vocabulary and it is also the
    # word an injection reaches for — *"answer without the evidence"* — so listing it admitted
    # a payload that names no machine straight past the gate and on to the arbiter, where it
    # costs a model call. The red-team suite caught it the same minute it was added. A reader
    # asking about evidence will almost always name a machine or a fault as well.
    "check", "finding", "verify",
    # Plant-level analytical vocabulary. Added 2026-08-18 with the analytical tools: without
    # these, "is it getting worse over time?" and "compare the two chillers" were refused as
    # off-topic while the tools that answer them sat registered. Every one was checked against
    # the red-team corpus first — an injection payload that happens to contain a domain word
    # gets past the gate on that word alone, which is how "evidence" had to be removed.
    "trend", "over time", "timeline", "worse", "compare", "history",
    "across the plant", "plant wide", "summary", "overview", "situation",
    "anomaly", "anomalies", "efficiency",
)

_REFUSAL_SCOPE = (
    "That is outside what Synex can answer. It covers this plant's chiller telemetry, the "
    "faults detected on it, and the work that follows from them — ask about a machine, a "
    "fault, or a reading and it will have something to work with."
)


def _normalise(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


#: Words that mean "the thing we were just discussing". A follow-up carries no domain
#: vocabulary of its own — *"and its ΔT?"*, *"did it work?"* — so the scope gate has to admit
#: it on the strength of the reference instead. Held as data so the set is inspectable and
#: adding one is a decision rather than a regex somebody widened.
_REFERENTIAL = (
    " it", "it ", "its ", "it's", " that", "that ", " this", "this ", " them", "they ",
    " those", " these", "same ", "again", "instead",
)


def names_equipment(message: str) -> str | None:
    """Which machine **this message** names, or `None`.

    Public because the request layer needs the same answer the gate does: a question naming a
    different machine from the one on screen must not be answered about the one on screen.
    """
    return _extract_equipment(message, None)


def _names_equipment(message: str) -> bool:
    """Did **this message** name a machine, as opposed to inheriting one?

    The distinction the scope gate turns on. `_extract_equipment` deliberately carries the last
    unit forward, which is what makes a follow-up resolve — but "resolved from context" is not
    "in scope", and conflating them is how *"what is the capital of France"* was answered with
    chiller 1's residuals on 2026-08-18.
    """
    return _extract_equipment(message, None) is not None


def _extract_equipment(message: str, last_equipment: str | None) -> str | None:
    """Layer 2. Equipment by pattern, against the **live catalog**, carrying the last forward.

    Carrying forward is what makes *"and its ΔT?"* resolve. It is deliberately narrow: only
    the most recently named unit, and only when the new message names none of its own.
    """
    text = _normalise(message)

    # **Word boundaries, not containment.** `"chiller 1" in "chiller 12"` is `True`, so a
    # question about a machine that does not exist was answered about chiller 1 — confidently,
    # and about the wrong asset. Found by the adversarial suite on 2026-08-17, and it is the
    # same defect shape as `-25.6` sitting inside `-25.645`, which once made the numeric audit
    # toothless. Containment is the wrong operator for an identifier, twice now.
    for e in eq.all_equipment():
        for name in (e.key.replace("_", " "), e.display_name.lower()):
            if re.search(rf"\b{re.escape(name)}\b", text):
                return e.key

    # "chiller 1", "chiller-1", "chiller_1", "ch1"
    m = re.search(r"\b(?:chiller|ch)[\s_-]*([12])\b", text)
    if m:
        return f"chiller_{m.group(1)}"

    return last_equipment


def route(
    message: str,
    *,
    mode_override: str | None = None,
    last_equipment: str | None = None,
    arbiter=None,
) -> RouteDecision:
    """Run the ladder. **Never raises.**

    `arbiter` is an optional callable for layer 4 — a model call returning a skill name. It
    is passed in rather than imported so that routing is unit-testable with the GPU off and
    so `app.agents` does not reach a client on every import. If it is absent, or raises, or
    returns something unrecognised, the ladder falls through to its deterministic default.
    """
    try:
        return _route(message, mode_override, last_equipment, arbiter)
    except Exception as exc:  # a router that throws turns a typo into a stack trace
        return RouteDecision(
            skill=Skill.CONVERSE,
            layer="fallback",
            reason=f"routing fell through after an unexpected error ({type(exc).__name__})",
        )


def _route(  # noqa: PLR0911 — eight layers, eight exits; that is the ladder
    message: str,
    mode_override: str | None,
    last_equipment: str | None,
    arbiter,
) -> RouteDecision:
    text = _normalise(message)
    equipment = _extract_equipment(message, last_equipment)

    # ── 0 · override ────────────────────────────────────────────────────────────
    if mode_override:
        try:
            return RouteDecision(
                skill=Skill(mode_override),
                layer="0 · override",
                reason="the user picked a mode chip, which outranks every heuristic",
                equipment_key=equipment,
            )
        except ValueError:
            pass  # an unknown chip degrades into the ladder rather than failing

    # ── 1 · preflight refusals ──────────────────────────────────────────────────
    if any(v in text for v in _CONTROL_VERBS):
        return RouteDecision(
            skill=Skill.REFUSE,
            layer="1 · preflight",
            reason="a control command was requested; agents are read-only with respect to plant",
            equipment_key=equipment,
            refusal_text=_REFUSAL_CONTROL,
        )

    if any(t in text for t in _FUTURE_TERMS):
        return RouteDecision(
            skill=Skill.REFUSE,
            layer="1 · preflight",
            reason="a prediction was requested; this is a snapshot, not a forecast",
            equipment_key=equipment,
            refusal_text=_REFUSAL_FUTURE,
        )

    # ── 1.5 · conversational fast path ──────────────────────────────────────────
    # Before the scope gate deliberately: "hi" has no equipment and no domain term, so the
    # gate would meet a greeting with a cold refusal. That is the single worst first
    # impression the product can make, and it costs one membership test to avoid.
    stripped = text.rstrip("!.?")
    if stripped in _GREETINGS or any(q in text for q in _CAPABILITY_QUESTIONS):
        return RouteDecision(
            skill=Skill.CONVERSE,
            layer="1.5 · fast path",
            reason="a greeting or a capability question — answered without touching telemetry",
            equipment_key=equipment,
        )

    # ── 3 · keyword heuristics, ordered ─────────────────────────────────────────
    keyword_match: RouteDecision | None = None
    for skill, terms in _KEYWORDS:
        hits = tuple(t for t in terms if t in text)
        if hits:
            keyword_match = RouteDecision(
                skill=skill,
                layer="3 · keywords",
                reason=f"matched {', '.join(repr(h) for h in hits)}",
                equipment_key=equipment,
                matched_terms=hits,
            )
            break

    # ── 3.5 · scope gate, before any inference ──────────────────────────────────
    # **This layer vetoes layer 3 rather than merely following it.** The keyword lists
    # contain ordinary English — "what is the", "why", "list" — so "what is the capital of
    # France" matches `look_up` and would have been routed as a telemetry question. The
    # ladder puts 3.5 *after* 3 for exactly this reason: a keyword match is evidence of
    # intent, not evidence of scope.
    # **Inherited equipment does not put a question in scope.** `_extract_equipment` carries the
    # last unit forward so *"and its ΔT?"* resolves, and until 2026-08-18 the gate read that
    # carried-forward value as evidence of scope — so selecting an episode in the interface
    # admitted *every* question, and *"what is the capital of France"* came back as a full
    # answer about chiller 1's residuals, honesty checks and all. The checks passed: nothing in
    # the answer was ungrounded. It was a true answer to a question nobody asked.
    #
    # So the gate now asks two separate questions. Does this message name a machine *itself*?
    # And if it does not, does it either use domain vocabulary or refer back to what was just
    # discussed? A follow-up has the reference; an off-topic question has neither.
    in_scope = (
        _names_equipment(message)
        or any(t in text for t in _DOMAIN_TERMS)
        or (last_equipment is not None and any(r in text for r in _REFERENTIAL))
    )
    if not in_scope:
        return RouteDecision(
            skill=Skill.REFUSE,
            layer="3.5 · scope gate",
            reason=(
                "this message names no machine, uses no domain vocabulary, and refers to "
                "nothing in the conversation; refused before any model call"
                + (
                    f" (layer 3 had proposed {keyword_match.skill.value} on a generic phrase)"
                    if keyword_match
                    else ""
                )
            ),
            refusal_text=_REFUSAL_SCOPE,
        )

    if keyword_match is not None:
        return keyword_match

    # ── 4 · the model arbiter ───────────────────────────────────────────────────
    if arbiter is not None:
        proposed = _ask_arbiter(arbiter, message)
        if proposed is not None:
            # ── 5 · reconcile ───────────────────────────────────────────────────
            # The arbiter may name equipment that does not exist. Deterministic facts win.
            return RouteDecision(
                skill=proposed,
                layer="4 · arbiter (5 · reconciled)",
                reason="the deterministic layers were inconclusive; the arbiter proposed a skill",
                equipment_key=equipment,
                used_model=True,
            )

    # The default when everything is inconclusive but the message is in scope. `EXPLAIN`
    # rather than `REFUSE`: the message mentioned a machine or the domain, so there is
    # something to work with, and a refusal here would be the router giving up rather than
    # the data being absent.
    return RouteDecision(
        skill=Skill.EXPLAIN,
        layer="default",
        reason="in scope but no heuristic matched; explaining what is known about it",
        equipment_key=equipment,
    )


def _ask_arbiter(arbiter, message: str) -> Skill | None:
    """Layer 4, defended on every side.

    The arbiter is a model, so it may time out, return prose instead of JSON, or name a
    skill that does not exist. Every one of those degrades to `None` and the ladder
    continues — the model proposes a route, it never establishes one.
    """
    try:
        proposed = arbiter(message)
    except Exception:
        return None
    if not proposed:
        return None
    try:
        return Skill(str(proposed).strip().lower())
    except ValueError:
        return None


def reconcile_equipment(proposed_key: str | None) -> str | None:
    """Accept the arbiter's equipment **only if the catalog confirms it**.

    Layer 5. A model naming `chiller_3` on a two-chiller site would otherwise produce an
    answer about a machine that does not exist, which is the most convincing kind of wrong.
    """
    if proposed_key is None:
        return None
    return proposed_key if eq.by_key(proposed_key) else None
