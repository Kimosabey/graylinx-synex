"""`G4` the tool gateway · `G5` idempotency — the one door every tool call goes through.

**Why a gateway rather than calling the function.** A tool call is the point where a
probabilistic system reaches a deterministic one, and four things must be true at that
boundary, none of which the caller can be trusted to check:

| | Gate | The failure it prevents |
|---|---|---|
| 1 | The tool **exists** | A model that invents a tool name gets a refusal, not an exception.
  Hallucinated capability is the commonest agent failure and it must be boring |
| 2 | The arguments **validate** | A tool whose arguments are a free-form dict is one the
  model can call with anything, including SQL |
| 3 | The side effect is **permitted** | `CONTEXT.md` §13 — no tool controls equipment, in
  any phase. Refused here as a named branch with a test, not as an absence |
| 4 | The caller is **in scope** | Permission is plain software. The Control Plane decides,
  never the model — the separation law's seventh row |

**`G5`, and why it is in this file.** An idempotency key is derived from the tool name and
its validated arguments, so a retry of the *same* call returns the first result rather than
acting twice. That is what makes "a retry can never create a second work order" true of the
mechanism rather than of everybody's care.

**No invocation raises.** A tool failure is a turn outcome, not a crash: the router's rule
that no layer may raise applies here too. Everything returns a `ToolResult`, and a refusal
carries the reason in words a reader can act on — an absence is not a zero and not a dash.

**Nothing here calls a model.** Contract 2b in `importlinter.ini` makes that a build failure.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from app.services.control_plane import Capability, Scope
from app.tools.registry import REGISTRY, ControlLevel, SideEffect, ToolRegistry, ToolSpec


class Outcome(StrEnum):
    """How an invocation ended. Four, and three of them are refusals with distinct causes.

    Kept distinct on purpose: *the tool does not exist* and *you may not use it* are different
    facts about the world, and collapsing them tells a caller to fix the wrong thing.
    """

    OK = "ok"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    REFUSED = "refused"
    NOT_IMPLEMENTED = "not_implemented"
    FAILED = "failed"


#: Which capability a side effect demands. Read-only work needs none — every persona may look,
#: and scope narrows *which equipment*, not whether looking is allowed. Writing Synex's own
#: state needs `APPROVE_WORK`, which is `G3`'s hook.
#:
#: Capabilities, not ranks — inherited constraint 13. A supervisor is not a more capable
#: technician; it holds authority and records, which is why the gate asks for a named
#: capability rather than comparing two personas.
_REQUIRED_CAPABILITY: dict[SideEffect, Capability | None] = {
    SideEffect.READ_ONLY: None,
    SideEffect.WRITES_SYNEX_STATE: Capability.APPROVE_WORK,
}


@dataclass(frozen=True)
class ToolResult:
    """The outcome of one invocation. Always returned; never raised."""

    tool: str
    outcome: Outcome
    value: Any = None
    reason: str = ""
    """Words, always. A refusal a reader cannot act on is a dash wearing a sentence."""

    idempotency_key: str = ""
    duration_ms: float = 0.0
    replayed: bool = False
    """`G5`. This result came from the ledger rather than from running the tool again."""

    arguments: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.OK

    @property
    def is_refusal(self) -> bool:
        """A refusal is not an error. `NO_DIAGNOSIS` taught us to keep these apart, and the
        same holds one layer down: `FAILED` means something broke, the rest mean the system
        worked and said no."""
        return self.outcome in {
            Outcome.UNKNOWN_TOOL,
            Outcome.INVALID_ARGUMENTS,
            Outcome.REFUSED,
            Outcome.NOT_IMPLEMENTED,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "outcome": self.outcome.value,
            "ok": self.ok,
            "is_refusal": self.is_refusal,
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
            "duration_ms": round(self.duration_ms, 2),
            "replayed": self.replayed,
        }


def idempotency_key(tool: str, arguments: dict[str, Any]) -> str:
    """`G5`. Same tool, same validated arguments, same key.

    Sorted keys and a canonical separator, because `{"a":1,"b":2}` and `{"b":2,"a":1}` are the
    same call and a hash over raw text would say otherwise — which would let a retry through
    on nothing more than dictionary ordering.
    """
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{tool}\x00{canonical}".encode()).hexdigest()
    return digest[:32]


class Gateway:
    """The door. One per process in service; constructed fresh in tests.

    The ledger is in memory and that is a **stated limitation, not a design**: idempotency
    survives a turn but not a restart. `langgraph-checkpoint-postgres` is the recorded home
    for durable state, and until it lands this class reports the limit rather than implying
    a guarantee it cannot keep.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or REGISTRY
        self._ledger: dict[str, ToolResult] = {}

    @property
    def is_durable(self) -> bool:
        """`False` until the checkpointer exists. Exposed so a surface can say so."""
        return False

    def clear(self) -> None:
        """Test-only, and between turns in service."""
        self._ledger.clear()

    async def invoke(
        self, name: str, arguments: dict[str, Any], scope: Scope
    ) -> ToolResult:
        """Run one tool, or explain in words why not. Never raises."""
        started = time.perf_counter()

        spec = self._registry.by_name(name)
        if spec is None:
            known = ", ".join(t.name for t in self._registry.all()) or "none"
            return ToolResult(
                tool=name,
                outcome=Outcome.UNKNOWN_TOOL,
                reason=(
                    f"there is no tool called {name!r}. The registered tools are: {known}. "
                    f"Nothing was run."
                ),
            )

        refusal = self._refusal_for(spec, scope)
        if refusal is not None:
            return refusal

        try:
            validated = spec.parameters(**arguments)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'argument'}: {e['msg']}"
                for e in exc.errors()
            )
            return ToolResult(
                tool=name,
                outcome=Outcome.INVALID_ARGUMENTS,
                reason=f"{name} was called with arguments it cannot accept — {problems}",
                arguments=arguments,
            )

        args = validated.model_dump()
        key = idempotency_key(name, args)

        if key in self._ledger:
            # `G5`. The same call, already made this turn. Return the first result rather than
            # acting twice — and say that it was replayed, because a caller that cannot tell a
            # fresh result from a cached one will eventually rely on the difference.
            previous = self._ledger[key]
            return ToolResult(
                tool=previous.tool,
                outcome=previous.outcome,
                value=previous.value,
                reason=previous.reason,
                idempotency_key=key,
                duration_ms=(time.perf_counter() - started) * 1000,
                replayed=True,
                arguments=args,
            )

        return await self._run(spec, args, key, started)

    async def _run(
        self, spec: ToolSpec, args: dict[str, Any], key: str, started: float
    ) -> ToolResult:
        """Everything after the four gates have passed. Split out so `invoke` reads as the
        gates it is, rather than as gates plus execution."""
        if spec.handler is None:
            return ToolResult(
                tool=spec.name,
                outcome=Outcome.NOT_IMPLEMENTED,
                reason=(
                    f"{spec.name} is registered but has no handler bound. It is declared so it "
                    f"can be seen and counted, and it does nothing until one is wired."
                ),
                idempotency_key=key,
                arguments=args,
            )

        try:
            value = await spec.handler(**args)
        except Exception as exc:
            # Deliberately broad. A tool failure is a turn outcome, not a crash — the router's
            # rule that no layer may raise applies one level down too, and a driver can throw
            # anything. The type and message are carried into the reason rather than swallowed.
            return ToolResult(
                tool=spec.name,
                outcome=Outcome.FAILED,
                reason=f"{spec.name} raised {type(exc).__name__}: {exc}",
                idempotency_key=key,
                duration_ms=(time.perf_counter() - started) * 1000,
                arguments=args,
            )

        result = ToolResult(
            tool=spec.name,
            outcome=Outcome.OK,
            value=value,
            idempotency_key=key,
            duration_ms=(time.perf_counter() - started) * 1000,
            arguments=args,
        )
        self._ledger[key] = result
        return result

    def _refusal_for(self, spec: ToolSpec, scope: Scope) -> ToolResult | None:
        """Gates 3 and 4. Returns `None` when the call may proceed."""
        if spec.is_permanently_refused:
            return ToolResult(
                tool=spec.name,
                outcome=Outcome.REFUSED,
                reason=(
                    f"{spec.name} declares the side effect {spec.side_effect.value!r}, which is "
                    f"refused in every phase and for every persona. No tool issues a control "
                    f"command to plant equipment, and Synex never writes to the plant snapshot."
                ),
            )

        if spec.control_level is ControlLevel.REFUSED:
            return ToolResult(
                tool=spec.name,
                outcome=Outcome.REFUSED,
                reason=f"{spec.name} is registered at control level 'refused' and never runs.",
            )

        required = _REQUIRED_CAPABILITY.get(spec.side_effect)
        if required is not None and not scope.allows(required):
            return ToolResult(
                tool=spec.name,
                outcome=Outcome.REFUSED,
                reason=(
                    f"{spec.name} changes Synex's own records, which needs the "
                    f"{required.value!r} capability. {scope.identity.display_name} does not "
                    f"hold it. The Control Plane decides this, not the model."
                ),
            )
        return None


GATEWAY = Gateway()
