"""Handing the work to somebody else, from the chat, with the handoff named before it happens.

**`RC7`'s three routes had no caller.** The route table, the artefacts, the deterministic
assignee and the case states have been built and tested since `RC15`; nothing in the request
path reached any of it. So the one thing a technician standing at a machine most needs to
say — *"I can't do this"* — had no answer, and the person who says it is exactly the person
least able to go and find the right surface.

**The blocker is read from the words, and it is the whole decision.** *"I don't have the
gauge"*, *"I'm not allowed to open that"* and *"the plant is running, not now"* are three
different sentences that send the work to three different places, and collapsing them into one
"escalate" loses the distinction that decides who gets called. Inherited constraint 9.

**Nothing here decides who.** `route_for` maps blocker to capability, `choose_assignee` picks
by workload with blocking items weighted double. Both are deterministic, so *"why this
person"* is answerable from the data rather than by replaying a prompt — and both keep working
with the box off.

**Nothing is raised until somebody says so.** The skill returns `NEEDS_APPROVAL` with the
route, the artefact and the assignee named. Escalating is cheap to do and expensive to undo:
an inspection work order that nobody meant to raise sends a technician across a plant.

**When the words do not settle it, it asks.** `NOT_SURE` is a real blocker with a real
route — it stays where it is and moves nothing — but *"which of these is it"* is a better
answer than picking the most likely of three and calling somebody.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.escalation import Artefact, Blocker, Route, route_for

#: What each blocker sounds like when somebody says it out loud. Ordered most specific first,
#: because "I don't have the authority to run it" contains both a tool phrase and an authority
#: phrase, and the authority is the one that decides where it goes.
_SAYS: tuple[tuple[Blocker, tuple[str, ...]], ...] = (
    (
        Blocker.NO_AUTHORITY,
        (
            "not allowed", "no authority", "the authority", "not authorised",
            "not authorized", "need approval", "need permission", "above my", "not my call",
            "not permitted", "need a supervisor", "needs a supervisor", "sign this off",
            "sign it off", "cleared first", "clear it first",
        ),
    ),
    (
        Blocker.CANNOT_INTERPRET,
        (
            "can't tell what", "cannot tell what", "don't understand the reading",
            "do not understand the reading", "need a judgement", "need a judgment",
            "second opinion", "not sure what this means", "someone to interpret",
            "need someone to look at",
        ),
    ),
    (
        Blocker.WRONG_MOMENT,
        (
            "not now", "wrong time", "still running", "can't shut", "cannot shut",
            "next shutdown", "during the outage", "when it's off", "when it is off",
            "park this", "park it", "defer", "come back to this", "later in the week",
        ),
    ),
    (
        Blocker.NO_TOOL,
        (
            "don't have the", "do not have the", "no gauge", "no meter", "no tool",
            "haven't got the", "have not got the", "need a technician", "needs a technician",
            "can't measure", "cannot measure", "no access to", "can't reach",
        ),
    ),
)

#: Phrases that ask for a handoff without saying which kind. These reach the skill; the blocker
#: is then unresolved, and unresolved is asked about rather than guessed.
ASKS_TO_ESCALATE: tuple[str, ...] = (
    "escalate", "hand this over", "hand it over", "pass this on", "pass it on",
    "i can't do this", "i cannot do this", "can't do this", "cannot do this",
    "someone else", "who else can", "raise this with", "send this to",
    "out of my depth", "beyond me", "not my job",
)


def asks_to_escalate(message: str) -> bool:
    """Whether this message is asking for a handoff at all."""
    text = message.lower()
    return any(phrase in text for phrase in ASKS_TO_ESCALATE) or blocker_in(message) is not None


def blocker_in(message: str) -> Blocker | None:
    """Which of the four stated blockers this message describes, or `None` if it says.

    `None` is not `NOT_SURE`. *"Escalate this"* names no blocker and must be asked about;
    `NOT_SURE` is somebody explicitly saying they cannot tell, which is a route of its own that
    deliberately moves nothing.
    """
    text = message.lower()
    for blocker, phrases in _SAYS:
        if any(phrase in text for phrase in phrases):
            return blocker
    return None


@dataclass(frozen=True)
class Handoff:
    """What would happen if this escalation were confirmed. Nothing has happened yet."""

    blocker: Blocker
    route: Route
    equipment_key: str = ""
    fault_label: str = ""
    day: str = ""

    @property
    def episode_id(self) -> str:
        """The episode the artefact would be raised against, in the id form the API takes."""
        return f"{self.equipment_key}:{self.fault_label}:{self.day}"

    @property
    def raises_an_artefact(self) -> bool:
        return self.route.artefact is not Artefact.NONE

    def render(self) -> str:
        """The handoff in words, before it happens.

        Names the destination as a **capability** rather than a person, because that is what
        the route decides; who specifically it lands on is `choose_assignee`'s answer and comes
        from workload, which this layer does not hold.
        """
        if self.route.case_state is None:
            return (
                "Nothing moves. You said you cannot tell, and 'cannot tell' is required to "
                "have no effect at all — otherwise uncertainty quietly rules something out. "
                "The case stays with you, unchanged.\n\n"
                f"{self.route.note}"
            )

        if not self.raises_an_artefact:
            return (
                "This would be parked rather than handed to anybody. Nobody is called, which "
                "is the point of this route — a deferral with a reason and a date is not a "
                "quiet way of dropping the work.\n\n"
                f"The case would move to {self.route.case_state.value}. {self.route.note}"
            )

        goes_to = self.route.goes_to.value if self.route.goes_to else "nobody"
        artefact = self.route.artefact.value.replace("_", " ")
        task = (
            "The task on it is the question itself, not a measurement — handing a decision to "
            "somebody as a reading to take is how the wrong person ends up at a gauge."
            if self.route.task_is_a_question
            else "The open checks become its task list, so whoever picks it up re-derives "
            "nothing."
        )
        unassigned = (
            " It lands unassigned and says so: naming somebody would imply they had accepted "
            "it, and nobody has."
            if self.route.lands_unassigned
            else ""
        )
        return (
            f"This goes to a {goes_to}, as an {artefact}. {task}{unassigned}\n\n"
            f"The case would move to {self.route.case_state.value}. Nothing is raised and "
            f"nobody is called until you confirm it."
        )


def plan(message: str, *, equipment_key: str, fault_label: str, day: str) -> Handoff | None:
    """What handing this over would do — or `None` when the words do not say which handoff.

    Returning `None` rather than defaulting is the whole discipline here: the four routes send
    the work to different people, and a default would quietly pick one of them for somebody who
    only said *"escalate"*.
    """
    blocker = blocker_in(message)
    if blocker is None:
        return None
    return Handoff(
        blocker=blocker,
        route=route_for(blocker),
        equipment_key=equipment_key,
        fault_label=fault_label,
        day=day,
    )


def ask_which() -> str:
    """The question to ask when somebody asked for a handoff without saying why.

    Four options in the reader's own words rather than the enum's. A technician does not think
    *"my blocker is NO_TOOL"*; they think *"I haven't got the gauge"*.
    """
    return (
        "Which of these is it? They go to different people, so it is worth one more line:\n\n"
        "- **I haven't got the tool or the access** — this goes to a technician as an "
        "inspection job, with your open checks as its task list.\n"
        "- **I'm not allowed to do it** — this goes to a supervisor as an authorisation "
        "request, and lands unassigned.\n"
        "- **I can't tell what the reading means** — this also goes to a supervisor, and the "
        "task is the question rather than a measurement.\n"
        "- **Not now — the plant is running** — this is parked with a reason and a date. "
        "Nobody is called.\n\n"
        "Say which and the handoff is drafted, with who it goes to and what it carries."
    )
