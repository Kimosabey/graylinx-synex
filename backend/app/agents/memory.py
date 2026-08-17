"""`C15` turn memory — what "this" and "the other one" actually refer to.

**What was here before, stated plainly:** a single `last_equipment` string threaded through
the router. That is *carry-forward*, not memory — it remembers one noun and forgets that a
question was ever asked. `SESSION-HANDOFF.md` §8 named it as the gap, and said M1's count
should honestly read 26 of 27 because of it.

**Three things a turn must be able to resolve, and only the first existed:**

| Reference | Needs | Example |
|---|---|---|
| *"why was **this** flagged?"* | the equipment | already worked |
| *"and **that** fault?"* | the label and the day too | did not |
| *"what about **the other one**?"* | the alternative within a known set | did not |

**Bounded, and the bound is the point.** An unbounded transcript grows until it exceeds
`max_context_chars` and then fails on a turn nobody can predict, which is the worst possible
place to discover a ceiling. `MAX_REMEMBERED_TURNS` bounds it by count, and the oldest turn
falls off silently — a conversation that refuses to continue because it remembered too much
would be a stranger failure than forgetting.

**Memory never resolves scope.** It records what was discussed; the Control Plane recomputes
what may be *seen* every turn and never inherits it (`G1`). A remembered equipment key that a
new persona may not view is still refused — a test asserts it, because "we were talking about
chiller 2" is exactly the kind of continuity that quietly becomes an authorisation.

**Nothing here calls a model, and nothing here decides.** Resolution is string matching over
what was already established. The language model may use the resolved context; it never
supplies it — the separation law's seventh row applies to *what "this" means* as much as to
who is allowed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

#: How many turns are remembered. Bounded by count rather than characters because a count is
#: what a reader can reason about — "the last six things you said" is a sentence somebody can
#: check, and a character budget is not.
#:
#: TBD (Q66): no document states a conversation depth. Six because the four case journeys plus
#: an opening and a closing turn is the longest exchange the demonstration script contains, so
#: nothing in the walkthrough falls off the end. It bounds recall only — it can never cause a
#: refusal, and dropping a turn never changes what the current turn is allowed to see.
MAX_REMEMBERED_TURNS: int = 6

#: Words that mean "the thing we were just discussing". Held as data so the set is inspectable
#: and so adding one is a decision rather than a regex somebody widens.
ANAPHORA: frozenset[str] = frozenset(
    {"this", "that", "it", "the same", "the one", "there", "then"}
)

#: Words that mean "the other member of the set we were discussing".
ALTERNATION: frozenset[str] = frozenset({"the other", "the other one", "either", "instead"})


@dataclass(frozen=True)
class ResolvedContext:
    """What "this" currently means. Every field independently absent-able.

    Three separate `None`s rather than one context object that is either present or missing,
    because *"why was this flagged"* with an equipment and no day is a different question
    from one with neither — and answering the second as though it were the first is how a
    reader gets a confident answer about the wrong afternoon.
    """

    equipment_key: str | None = None
    fault_label: str | None = None
    day: date | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.equipment_key or self.fault_label or self.day)

    def render(self) -> str:
        """What a route trace shows, so a reader can see what "this" became.

        A resolution nobody can inspect is indistinguishable from a guess.
        """
        if self.is_empty:
            return "nothing has been established yet in this conversation"
        parts = []
        if self.equipment_key:
            parts.append(self.equipment_key)
        if self.fault_label:
            parts.append(self.fault_label)
        if self.day:
            parts.append(f"{self.day:%Y-%m-%d}")
        return " · ".join(parts)

    def merged_with(self, other: ResolvedContext) -> ResolvedContext:
        """Newer wins per field; absent never overwrites present.

        Field-wise rather than wholesale, because naming a new fault on the same machine must
        not silently clear the machine.
        """
        return ResolvedContext(
            equipment_key=other.equipment_key or self.equipment_key,
            fault_label=other.fault_label or self.fault_label,
            day=other.day or self.day,
        )


@dataclass(frozen=True)
class RememberedTurn:
    """One exchange, reduced to what a later turn might refer back to.

    The answer text is **not** kept. A later turn needs to know what was established, not what
    was said about it — and storing generated prose would let a model's own phrasing become
    the evidence for the next answer, which is the grounding failure one turn removed.
    """

    question: str
    skill: str
    answer_state: str
    context: ResolvedContext
    equipment_offered: tuple[str, ...] = field(default_factory=tuple)
    """The set a later *"the other one"* can select from. Empty when no set was shown."""


@dataclass(frozen=True)
class TurnMemory:
    """`C15`. Bounded, immutable, and it decides nothing."""

    turns: tuple[RememberedTurn, ...] = field(default_factory=tuple)
    context: ResolvedContext = field(default_factory=ResolvedContext)

    @property
    def is_new_conversation(self) -> bool:
        return not self.turns

    @property
    def depth(self) -> int:
        return len(self.turns)

    def remember(
        self,
        *,
        question: str,
        skill: str,
        answer_state: str,
        context: ResolvedContext | None = None,
        equipment_offered: tuple[str, ...] = (),
    ) -> TurnMemory:
        """Record one turn and return a new memory. Never mutates."""
        merged = self.context.merged_with(context or ResolvedContext())
        turn = RememberedTurn(
            question=question,
            skill=skill,
            answer_state=answer_state,
            context=merged,
            equipment_offered=equipment_offered,
        )
        kept = (*self.turns, turn)[-MAX_REMEMBERED_TURNS:]
        return replace(self, turns=kept, context=merged)

    def refers_back(self, message: str) -> bool:
        """Does this question lean on what came before?

        Reported so a route trace can show *why* context was applied. A turn that silently
        inherited an equipment key is one nobody can audit.
        """
        lowered = f" {message.lower().strip()} "
        return any(f" {word} " in lowered for word in ANAPHORA | ALTERNATION)

    def wants_the_alternative(self, message: str) -> bool:
        lowered = f" {message.lower().strip()} "
        return any(f" {phrase} " in lowered for phrase in ALTERNATION)

    def resolve(self, message: str, known_equipment: tuple[str, ...] = ()) -> tuple[
        ResolvedContext, str
    ]:
        """What "this" means for this message, and the reason in words.

        Returns the reason alongside so the route frame can carry it. Three outcomes and they
        are kept distinct: nothing to resolve, resolved from context, and resolved to the
        *other* member of a known set.
        """
        if self.wants_the_alternative(message) and self.context.equipment_key:
            others = [k for k in known_equipment if k != self.context.equipment_key]
            if len(others) == 1:
                return (
                    replace(self.context, equipment_key=others[0], fault_label=None, day=None),
                    (
                        f"'the other one' resolved to {others[0]}, because "
                        f"{self.context.equipment_key} was under discussion and the site has "
                        f"exactly two"
                    ),
                )
            if not others:
                return self.context, (
                    "'the other one' has no referent — only one asset is in scope"
                )
            return self.context, (
                f"'the other one' is ambiguous: {len(others)} assets are in scope besides "
                f"{self.context.equipment_key}, so nothing was assumed"
            )

        if self.refers_back(message):
            if self.context.is_empty:
                return self.context, (
                    "this question refers back, but nothing has been established yet in this "
                    "conversation"
                )
            return self.context, f"resolved from the conversation: {self.context.render()}"

        return ResolvedContext(), "this question names its own subject"

    def forget(self) -> TurnMemory:
        """Start again. Exposed so a persona switch can clear the conversation rather than
        carry one person's context into another's — `G1` recomputes scope every turn, and
        memory must not be the thing that leaks around it."""
        return TurnMemory()
