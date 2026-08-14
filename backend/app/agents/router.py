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
                     "reading")),
)

#: Domain vocabulary. A message with none of this and no named equipment is out of scope,
#: and layer 3.5 refuses it **before** any model call.
_DOMAIN_TERMS = (
    "chiller", "compressor", "condenser", "evaporator", "refrigerant", "residual",
    "fault", "alarm", "temperature", "pressure", "flow", "efficiency", "kw", "plant",
    "cooling tower", "pump", "maintenance", "work order", "case", "diagnos", "head",
    "suction", "discharge", "power", "load", "setpoint", "equipment", "sensor",
)

_REFUSAL_SCOPE = (
    "That is outside what Synex can answer. It covers this plant's chiller telemetry, the "
    "faults detected on it, and the work that follows from them — ask about a machine, a "
    "fault, or a reading and it will have something to work with."
)


def _normalise(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def _extract_equipment(message: str, last_equipment: str | None) -> str | None:
    """Layer 2. Equipment by pattern, against the **live catalog**, carrying the last forward.

    Carrying forward is what makes *"and its ΔT?"* resolve. It is deliberately narrow: only
    the most recently named unit, and only when the new message names none of its own.
    """
    text = _normalise(message)

    for e in eq.all_equipment():
        if e.key.replace("_", " ") in text or e.display_name.lower() in text:
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
    if equipment is None and not any(t in text for t in _DOMAIN_TERMS):
        return RouteDecision(
            skill=Skill.REFUSE,
            layer="3.5 · scope gate",
            reason=(
                "no equipment named and no domain vocabulary; refused before any model call"
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
