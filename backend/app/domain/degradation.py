"""`CONTEXT.md` §13 — the platform states when it is in degraded mode rather than silently
substituting a weaker capability.

**The failure this prevents, and half of it has already happened here.** Four different things
can be down and they are not interchangeable: MySQL on **:3307** holds the plant snapshot,
PostgreSQL holds Synex's own case queue, the rented box holds the four-model roster at roughly
**41 GB** resident, and `nomic-embed-text` at **274 MB** holds retrieval on the host CPU. Today
`app/agents/answer.py` already falls back to a deterministic answer when the box cannot be
reached, and carries the reason on the turn. But that reason is **one string about one
capability**, `/api/v1/health` reports a single `status` word that is true of MySQL alone, and
nothing anywhere adds the four together. A surface asking *"what is not working right now"*
gets the word `degraded` and no way to tell which of seven capabilities it means — which is a
silent substitution wearing a status field.

**Three states are not enough, so there are four.** The distinction that does the work is
between *nothing stands in for this* and *something weaker is standing in and here it is*:

| | Rule | Why |
|---|---|---|
| 7 | `NULL` means **not diagnosed**, never healthy | An empty queue on a blind window once read
  as a clean plant. `UNKNOWN` is therefore not a quiet `AVAILABLE`, and a capability nobody
  probed is named in the report rather than omitted from it |
| 8 | **`cannot_check` is separate from `not applicable`** | Six "N/A" presses once opened a
  blocking gate with zero evidence behind it. The same separation one layer up: *we could not
  tell* and *it is down* are different facts and neither may absorb the other |
| 14 | A figure is **a value or a stated absence, never both and never neither** | Every state
  below carries its reason in words, and a `SUBSTITUTED` state cannot exist without naming
  what is standing in |

**Nothing here probes anything.** This module is the vocabulary and the registry; observing
the running process is `app/agents/degraded_mode.py`, one layer up, because reaching a socket
is not something `domain` may do — contract 4, `domain` imports nothing. That split is also
what lets every rule below be tested with MySQL stopped and the box terminated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    """The seven things that can be separately absent.

    Named individually rather than rolled into *"the database"* or *"the models"*, because the
    substitutions differ: losing the plant snapshot ends the turn, losing the box costs the
    prose and keeps the answer, and losing the embedder must never cost a safety answer.
    """

    PLANT_TELEMETRY = "plant_telemetry"
    """The chiller readings, residuals and bands — MySQL `graylinx_synex` on :3307, read as
    `synex_plant_ro`."""

    CASE_QUEUE = "case_queue"
    """Synex's own state — the case queue, findings, work orders and the audit rows, on
    PostgreSQL. `CONTEXT.md` §9: Synex writes here and nowhere else."""

    ANSWER_PROSE = "answer_prose"
    """The roster on the rented box, or a transcript recorded from it. What turns a verdict
    into a sentence — and only that."""

    EMBEDDINGS = "embeddings"
    """`nomic-embed-text` on the host, 768 dimensions, always local."""

    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    """`K1` SOP search and `S4` safety answers — pgvector plus the embedder above."""

    AUDIT_TRAIL = "audit_trail"
    """`G6`. Every material action and decision, permanently."""

    TOOL_IDEMPOTENCY = "tool_idempotency"
    """`G5`. The ledger that makes a retry return the first result instead of acting twice."""


class Availability(StrEnum):
    """What is true of one capability. Four, and the last two are not each other."""

    AVAILABLE = "available"
    """The real thing answered. Nothing is standing in."""

    SUBSTITUTED = "substituted"
    """It is absent and something weaker is doing its job. **The substitution is named**, or
    this state cannot be constructed — an unnamed substitution is the silent one §13 forbids."""

    UNAVAILABLE = "unavailable"
    """It is absent and nothing stands in. Whatever needs it refuses, and the refusal says
    which capability was missing."""

    UNKNOWN = "unknown"
    """Nobody established either way. **Not a pass**, inherited constraint 7 — and not the same
    fact as `UNAVAILABLE`, inherited constraint 8. Reporting an unprobed dependency as working
    is how a health endpoint becomes a reassurance."""


class Finding(StrEnum):
    """What one probe came back with. Deliberately three, and deliberately not `bool | None`.

    A tri-state boolean is the shape that produced *"an absence is a zero"* everywhere else in
    this codebase: `False` and `None` look alike at a call site and the second one silently
    becomes the first.
    """

    REACHED = "reached"
    NOT_REACHED = "not_reached"
    NOT_PROBED = "not_probed"


@dataclass(frozen=True)
class CapabilityProfile:
    """What a capability is for, what stands in when it is gone, and what breaks if nothing does.

    Held as data with the source attached, so adding a dependency means writing down its
    substitution rather than discovering later that there was not one.
    """

    capability: Capability
    provides: str
    """What a reader loses, in their words rather than in infrastructure names."""

    depends_on: str
    """The actual thing that has to be up. Named so an operator knows what to restart."""

    substitute: str = ""
    """What stands in, in words. **Empty means nothing does** — and then the capability goes to
    `UNAVAILABLE` rather than `SUBSTITUTED`, because a substitution nobody can name is not one."""

    breaks: str = ""
    """What stops working when nothing stands in. Required wherever `substitute` is empty."""

    @property
    def has_substitute(self) -> bool:
        return bool(self.substitute.strip())


#: The registry. Every entry's substitution is a claim about code that exists — none of them is
#: aspirational, and a test asserts that the two capabilities claiming a durability substitution
#: match what `audit_log.IS_DURABLE` and `Gateway.is_durable` actually report.
PROFILES: dict[Capability, CapabilityProfile] = {
    Capability.PLANT_TELEMETRY: CapabilityProfile(
        capability=Capability.PLANT_TELEMETRY,
        provides="the plant's readings, the residuals computed from them and each asset's band",
        depends_on="MySQL on :3307, read through the `synex_plant_ro` grant",
        # No substitute, deliberately. There is no second copy of what the instruments read,
        # and a figure assembled from anything else would be the fabrication D-009 removed:
        # `cond_flow` was synthetic for 3,354 slots and read as an instrument capability the
        # site does not have.
        breaks=(
            "every figure, residual and band. A turn that needs one refuses and names this "
            "capability rather than answering from memory"
        ),
    ),
    Capability.CASE_QUEUE: CapabilityProfile(
        capability=Capability.CASE_QUEUE,
        provides="the case queue, its findings, the work orders raised from it and the trail",
        depends_on="PostgreSQL, which Synex writes to and which is never the plant snapshot",
        substitute=(
            "the case is recomputed for each request and discarded, so a pause is a value in a "
            "response rather than a state in the world — a technician who stops for the day "
            "leaves nothing behind, and `RC8`'s idempotency has no unique index to lean on"
        ),
    ),
    Capability.ANSWER_PROSE: CapabilityProfile(
        capability=Capability.ANSWER_PROSE,
        provides="the plain-English explanation of a verdict the rules already reached",
        depends_on="the roster on the rented box, or a transcript recorded from it",
        substitute=(
            "the deterministic answer assembled from the evidence pack. It is flat on purpose "
            "— it is not trying to sound like the roster, so a reader can see that the prose "
            "layer is absent rather than wonder why the writing got worse. Nothing about what "
            "may be claimed changes: the gates ran before this point either way"
        ),
    ),
    Capability.EMBEDDINGS: CapabilityProfile(
        capability=Capability.EMBEDDINGS,
        provides="the 768-dimension vectors that make a document searchable",
        depends_on="`nomic-embed-text` on the host, 274 MB, and never a hosted API",
        # No substitute, and the reason is measured rather than stylistic: a zero vector makes
        # every document equidistant from every query, so the search returns whatever came
        # first and looks like it worked.
        breaks=(
            "retrieval refuses rather than returning an arbitrary row. A zero vector would "
            "make every document equidistant from every query"
        ),
    ),
    Capability.KNOWLEDGE_RETRIEVAL: CapabilityProfile(
        capability=Capability.KNOWLEDGE_RETRIEVAL,
        provides="the SOP and manual passages an answer quotes, with where they came from",
        depends_on="pgvector on PostgreSQL, plus the embedder above",
        # No substitute. `S4` is *safety answers from the SOP*, and the only thing that could
        # stand in is the roster's own memory — which is precisely what that feature forbids.
        breaks=(
            "a knowledge answer refuses. `S4` requires the SOP itself, so falling back to what "
            "a model remembers would answer a safety question from the wrong source"
        ),
    ),
    Capability.AUDIT_TRAIL: CapabilityProfile(
        capability=Capability.AUDIT_TRAIL,
        provides="the permanent record of every material action and decision — `G6`",
        depends_on="PostgreSQL, through the case store",
        substitute=(
            "an in-process list of audit rows that does not survive a restart. Every row it "
            "holds is real; none of them is permanent, and `G6` says permanently"
        ),
    ),
    Capability.TOOL_IDEMPOTENCY: CapabilityProfile(
        capability=Capability.TOOL_IDEMPOTENCY,
        provides="the guarantee that a retried call returns the first result instead of acting "
        "twice — `G5`",
        depends_on="a durable ledger; today the tool gateway keeps one in memory",
        substitute=(
            "an in-memory ledger that holds for the life of the process. A retry inside one "
            "turn is caught; a retry after a restart is not, and at the work-order boundary "
            "the unique index on `synex_work_order.idempotency_key` is what catches it instead"
        ),
    ),
}


@dataclass(frozen=True)
class Observation:
    """What one probe found about one capability. The input to `assess`."""

    capability: Capability
    finding: Finding
    detail: str
    """What was actually checked, in words — *"the pool opened"*, *"nothing listens on :3307"*,
    *"reaching this costs an HTTP call and health does not make one"*. Required: an observation
    without a detail cannot explain itself once it reaches a screen."""

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError(
                f"an observation of {self.capability.value} arrived with no detail. Every "
                f"state this produces carries its reason in words, and there is nowhere else "
                f"for those words to come from."
            )


@dataclass(frozen=True)
class CapabilityState:
    """One capability's standing, ready to be rendered. Never a bare boolean."""

    capability: Capability
    availability: Availability
    reason: str
    substitution: str = ""
    """Filled only where something is standing in. Empty everywhere else — and empty here means
    *nothing is standing in*, which the reason states in words rather than leaving to a dash."""

    probe: str = ""
    """What was checked to reach this. Kept beside the verdict so a reader can tell a probe
    that failed from a probe that never ran."""

    def __post_init__(self) -> None:
        if self.availability is Availability.SUBSTITUTED and not self.substitution.strip():
            raise ValueError(
                f"{self.capability.value} was reported as substituted without naming the "
                f"substitution. `CONTEXT.md` §13 is precisely about not doing that."
            )

    @property
    def is_degraded(self) -> bool:
        """Substituted or unavailable. `UNKNOWN` is deliberately excluded — see `is_unknown`."""
        return self.availability in {Availability.SUBSTITUTED, Availability.UNAVAILABLE}

    @property
    def is_unknown(self) -> bool:
        return self.availability is Availability.UNKNOWN

    def render(self) -> str:
        return f"{self.capability.value}: {self.availability.value} — {self.reason}"

    def as_dict(self) -> dict:
        return {
            "capability": self.capability.value,
            "availability": self.availability.value,
            "reason": self.reason,
            "substitution": self.substitution,
            "probe": self.probe,
            "is_degraded": self.is_degraded,
        }


@dataclass(frozen=True)
class DegradationReport:
    """Every capability, every time — including the ones nobody probed.

    **The report is always complete.** A capability with no observation is reported `UNKNOWN`
    rather than left out, because a list that shrinks to what was easy to check is the
    reconciliation failure `R10` exists for, wearing infrastructure clothes.
    """

    states: tuple[CapabilityState, ...]

    @property
    def degraded(self) -> tuple[CapabilityState, ...]:
        return tuple(s for s in self.states if s.is_degraded)

    @property
    def unknown(self) -> tuple[CapabilityState, ...]:
        return tuple(s for s in self.states if s.is_unknown)

    @property
    def available(self) -> tuple[CapabilityState, ...]:
        return tuple(s for s in self.states if s.availability is Availability.AVAILABLE)

    @property
    def is_fully_available(self) -> bool:
        """True only when every capability was probed **and** answered. An unprobed
        dependency leaves this false, which is constraint 7 said as a property."""
        return len(self.available) == len(self.states)

    def state_of(self, capability: Capability) -> CapabilityState:
        for state in self.states:
            if state.capability is capability:
                return state
        raise KeyError(f"{capability.value} is not in this report, which should be impossible")

    def headline(self) -> str:
        """One sentence a surface can print, with the denominator attached.

        *"Degraded"* on its own is the word that hid three of these. The count is never given
        without the total, and the unprobed are counted separately rather than folded in.
        """
        total = len(self.states)
        if not self.degraded and not self.unknown:
            return f"all {total} capabilities answered; nothing is being substituted."

        parts = []
        if self.degraded:
            names = ", ".join(s.capability.value for s in self.degraded)
            parts.append(f"{len(self.degraded)} of {total} capabilities are degraded ({names})")
        if self.unknown:
            names = ", ".join(s.capability.value for s in self.unknown)
            parts.append(
                f"{len(self.unknown)} of {total} were not probed, so their standing is "
                f"unknown rather than good ({names})"
            )
        return "; ".join(parts) + "."

    def render(self) -> str:
        lines = ["Degraded-mode report", self.headline(), ""]
        lines.extend(f"  {state.render()}" for state in self.states)
        substitutions = [s for s in self.states if s.substitution]
        lines.append("")
        if substitutions:
            lines.append("WHAT IS STANDING IN")
            lines.extend(
                f"  {s.capability.value}: {s.substitution}" for s in substitutions
            )
        else:
            lines.append("Nothing is standing in for anything.")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "headline": self.headline(),
            "capabilities_reported": len(self.states),
            "degraded": [s.capability.value for s in self.degraded],
            "unknown": [s.capability.value for s in self.unknown],
            "fully_available": self.is_fully_available,
            "states": [s.as_dict() for s in self.states],
        }


def _state_for(profile: CapabilityProfile, observation: Observation) -> CapabilityState:
    """One observation, resolved against the profile that knows what stands in for it."""
    if observation.finding is Finding.REACHED:
        return CapabilityState(
            capability=profile.capability,
            availability=Availability.AVAILABLE,
            reason=f"{profile.provides} is available. {observation.detail}",
            probe=observation.detail,
        )

    if observation.finding is Finding.NOT_PROBED:
        return CapabilityState(
            capability=profile.capability,
            availability=Availability.UNKNOWN,
            reason=(
                f"nobody established whether {profile.provides} is available. "
                f"{observation.detail}. This is not a report that it is working."
            ),
            probe=observation.detail,
        )

    if profile.has_substitute:
        return CapabilityState(
            capability=profile.capability,
            availability=Availability.SUBSTITUTED,
            reason=(
                f"{profile.provides} is not available — {observation.detail}. Something weaker "
                f"is standing in, and it is named beside this."
            ),
            substitution=profile.substitute,
            probe=observation.detail,
        )

    return CapabilityState(
        capability=profile.capability,
        availability=Availability.UNAVAILABLE,
        reason=(
            f"{profile.provides} is not available — {observation.detail}. Nothing stands in "
            f"for it: {profile.breaks}."
        ),
        probe=observation.detail,
    )


def assess(observations: tuple[Observation, ...]) -> DegradationReport:
    """Fold every observation into one report over **all** seven capabilities.

    A capability nobody observed becomes `UNKNOWN` with that said outright, so the report's
    length never depends on how much the caller bothered to check. Two observations of the same
    capability raise rather than silently picking one — a caller holding two answers about one
    dependency has a bug, and quietly keeping the cheerful one is the exact shape of failure
    this module exists to prevent.
    """
    seen: dict[Capability, Observation] = {}
    for observation in observations:
        if observation.capability in seen:
            raise ValueError(
                f"{observation.capability.value} was observed twice in one assessment. There "
                f"is no rule here for which answer wins, and picking one silently would hide "
                f"a degradation behind a cheerful duplicate."
            )
        seen[observation.capability] = observation

    states: list[CapabilityState] = []
    for capability, profile in PROFILES.items():
        observation = seen.get(capability)
        if observation is None:
            observation = Observation(
                capability=capability,
                finding=Finding.NOT_PROBED,
                detail="nothing in this request checked it",
            )
        states.append(_state_for(profile, observation))
    return DegradationReport(states=tuple(states))
