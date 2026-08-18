"""`C20` the skill and tool registry — what the agent may reach, declared rather than coded.

**The gap this closes.** Until now there were no tools at all. `max_react_steps` sat in
`config.py` with nothing consuming it, five of seven skills routed correctly and then fell
through to the same explain path, and "the Copilot reaches every capability through the
Control Plane" was a sentence rather than a mechanism.

**A tool is data, not a function.** Every tool is a `ToolSpec` with a declared side effect, a
control level and a parameter model. That is what lets `G4` refuse one without knowing what it
does, what lets `C20` list them, and what stops a new capability arriving without anyone
deciding it was allowed. A tool that registered itself by being importable would be a
capability nobody approved.

**Three rules the build enforces rather than states.** Contract 2b in `importlinter.ini`:

| | Rule | Why |
|---|---|---|
| — | A tool **never calls a model** | The executor must not write the final answer, and a
  tool that could reach `app.llm` would let it |
| — | A tool **holds no database driver** | It goes through `app.services`, so the plant stays
  behind `synex_plant_ro` and reads are read-only by grant rather than by promise |
| 13 | **No tool controls equipment, in any phase** | `CONTEXT.md` §13. The cheapest way to keep
  that true is to give tools no way to talk to hardware at all — so the side effect that would
  do it is declarable, and permanently refused |

**Nothing here calls a model, and nothing here decides authority.** The registry says what
exists and what it costs; `gateway.py` decides whether this caller may have it, and the
Control Plane decides who this caller is. Separation law: permission is plain software.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class SideEffect(StrEnum):
    """What invoking this tool changes. Ordered by how much trust it needs."""

    READ_ONLY = "read_only"
    """Reads and returns. The only kind that exists today, and the only kind the MVP needs
    for six of its seven skills."""

    WRITES_SYNEX_STATE = "writes_synex_state"
    """Creates or updates Synex's own records — a case, a work order, an audit row. Never
    touches the plant snapshot. Requires an approval under `G3`."""

    WRITES_PLANT = "writes_plant"
    """**Permanently refused.** `graylinx_synex` is read through `synex_plant_ro`, which holds
    `SELECT` and nothing else (Q42). A tool declaring this could not succeed even if it were
    allowed, and declaring it is how a reviewer sees the intent."""

    CONTROLS_EQUIPMENT = "controls_equipment"
    """**Permanently refused, in any phase.** `CONTEXT.md` §13: agents are read-only with
    respect to hardware control. This value exists so the refusal is a named branch with a
    test on it, rather than an absence somebody later fills in."""


#: Side effects no caller may ever have, whatever their persona, approval or scope. Held as a
#: set rather than an `if` so the refusal is a lookup, and so a new one is added deliberately.
FORBIDDEN_SIDE_EFFECTS: frozenset[SideEffect] = frozenset(
    {SideEffect.WRITES_PLANT, SideEffect.CONTROLS_EQUIPMENT}
)


class ControlLevel(StrEnum):
    """How much oversight an invocation needs. `G2` risk classification consumes this."""

    AUTOMATIC = "automatic"
    """Runs without asking. Read-only lookups against the plant snapshot."""

    NEEDS_APPROVAL = "needs_approval"
    """A human with the right authority must approve first. `G3`, and the answer state is
    `NEEDS_APPROVAL` rather than `ANSWERED`."""

    REFUSED = "refused"
    """Never runs. Paired with a forbidden side effect."""


@dataclass(frozen=True)
class ToolSpec:
    """One capability the agent may reach, and everything settled about it."""

    name: str
    description: str
    """Written for the model, not for a developer. This is what a router reads."""

    parameters: type[BaseModel]
    """A pydantic model. Validation is the gateway's first gate, and a tool whose arguments
    are a free-form dict is one the model can call with anything."""

    side_effect: SideEffect
    control_level: ControlLevel

    handler: Callable[..., Awaitable[Any]] | None = None
    """Bound at wiring time. `None` means declared but not implemented — which is honest and
    visible, rather than a tool that exists in a list and fails when called."""

    skill: str = ""
    """Which of the seven skills reaches for this. Empty means any."""

    tags: tuple[str, ...] = field(default_factory=tuple)

    needs: tuple[str, ...] = field(default_factory=tuple)
    """Named resources the gateway must hand this tool at call time — today only
    ``"plant_repo"``.

    **Why injection rather than letting the tool fetch.** The `tools_are_deterministic`
    contract forbids `app.tools` from importing `sqlalchemy`, `aiomysql`, `asyncpg` or
    `pgvector`, and the reason recorded beside it is not testability: *a tool that could import
    a database driver could reach the plant directly and bypass `synex_plant_ro`*. CONTEXT §13
    says no tool issues a control command to plant equipment in any phase, and giving tools no
    way to talk to hardware is the cheapest way to keep that true.

    Injection keeps both halves. The tool never constructs a connection and still cannot import
    a driver; it is handed a repository built by a layer that is allowed to hold one, and that
    repository is read-only by grant. So the capability widens without the contract loosening.

    A tool that declares a need the gateway was not given does not fail obscurely: it reports
    `MISSING_RESOURCE` in words, which is a different fact from the tool being unimplemented
    and from it being refused."""

    @property
    def is_implemented(self) -> bool:
        return self.handler is not None

    @property
    def is_permanently_refused(self) -> bool:
        return self.side_effect in FORBIDDEN_SIDE_EFFECTS

    def describe(self) -> dict[str, Any]:
        """What `C20` lists and what a router is shown. No handler, deliberately — a caller
        that can see the function can call it around the gateway."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.model_json_schema(),
            "side_effect": self.side_effect.value,
            "control_level": self.control_level.value,
            "skill": self.skill,
            "implemented": self.is_implemented,
            "permanently_refused": self.is_permanently_refused,
        }


class ToolRegistry:
    """The one place a tool becomes reachable.

    An instance rather than a module global so a test can build an empty one. The default
    instance is `REGISTRY`, and `app.agents` reads that.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        """Add a tool. Refuses a duplicate name rather than replacing it.

        Silent replacement is how two capabilities end up sharing a name and the wrong one
        answers — and the symptom is a correct-looking answer from the wrong source.
        """
        if spec.name in self._tools:
            raise ValueError(f"tool {spec.name!r} is already registered")
        if spec.is_permanently_refused and spec.control_level is not ControlLevel.REFUSED:
            raise ValueError(
                f"tool {spec.name!r} declares side effect {spec.side_effect.value!r}, which is "
                f"permanently refused, but its control level is {spec.control_level.value!r}. "
                f"A refused capability must say so in both places or a reader will trust one."
            )
        self._tools[spec.name] = spec
        return spec

    def by_name(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def all(self) -> tuple[ToolSpec, ...]:
        """Every registered tool, name-ordered so the list a model sees is stable."""
        return tuple(self._tools[k] for k in sorted(self._tools))

    def for_skill(self, skill: str) -> tuple[ToolSpec, ...]:
        """The tool scope of one skill — **a catalogue, and a catalogue never offers a tool
        that cannot run.**

        Two defects found in adversarial review on 2026-08-17, and both were mine:

        1. `set_chiller_setpoint` carries `skill=""` to mean *unscoped*, and this method read
           an empty skill as *available to every skill*. So the permanently-refused
           equipment-control tool appeared in **every** catalogue. Offering a model a tool it
           may never use is not merely wasteful — it is an invitation to try, and the only
           thing standing behind it was `G4`. A gate should be the second line, not the first.
        2. `for_skill("")` therefore returned that one tool and nothing else, so any caller
           that omitted a skill handed the chooser a one-item catalogue it could never act on.
           Five tests ran that path and passed, because each asserted only within the list.

        So: permanently-refused tools are excluded here always, and an empty skill means *the
        caller has not narrowed* — it returns everything usable rather than everything
        unscoped. The refused tool stays in `all()`, because `C20` must still be able to show
        that the capability was declared and denied.
        """
        usable = (t for t in self.all() if not t.is_permanently_refused)
        if not skill:
            return tuple(usable)
        return tuple(t for t in usable if not t.skill or t.skill == skill)

    def implemented(self) -> tuple[ToolSpec, ...]:
        return tuple(t for t in self.all() if t.is_implemented)

    def declared_but_missing(self) -> tuple[str, ...]:
        """Tools with no handler. Reported as a number rather than discovered on a call —
        the same reasoning as the unreviewed-checklist count."""
        return tuple(t.name for t in self.all() if not t.is_implemented)


REGISTRY = ToolRegistry()
