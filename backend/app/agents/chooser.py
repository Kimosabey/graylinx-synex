"""The model-backed chooser — `devstral` decides which tool to reach for next.

**What this replaces, and what it does not.** `PlannedChooser` picks from the catalogue by
rule: it looks at what the catalogue offers and what has already been tried, and takes the next
untried thing. That is genuinely useful — it runs with the box terminated, it never invents a
tool, and it is what the whole loop was tested against. It is also blind to the *question*. A
plan that walks the catalogue in order asks the same three tools whether somebody wanted to
know about safety or about efficiency.

So this is the second half of a deliberate split, the same shape `ModelClient` already uses:
the deterministic chooser is the CI side and the floor, and the model-backed one is what runs
when a box is there. `Chooser` was made an injected callable precisely so this could arrive
without touching `ReactLoop`.

**The model is treated as untrusted, and the loop already assumed that.** `LoopState` cannot
see the gateway, the scope or the registry objects — a chooser that could read `spec.handler`
could call around the gate, and one that could read the scope would be a step away from
deciding permission with it. So the worst a bad choice can do is name a tool that does not
exist or pass arguments that do not validate, and both come back through `G4` as worded
refusals the loop can act on. **Nothing here needs to trust the model.**

**It falls back rather than failing.** An unreachable box, a timeout, unparseable JSON, a tool
name that is not in the catalogue — every one of them returns the deterministic chooser's
decision instead, with the reason recorded on `purpose`. A loop that stopped because the
chooser was unavailable would turn a model outage into a product outage, and the deterministic
path is right there.

**`devstral` and not the brain.** The role table gives `tool` to `devstral`; the brain writes
the final answer and must not also be choosing the evidence it will write from. Same argument
as the auditor, one layer earlier.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.agents.react import LoopState, Move, ToolChoice
from app.llm.client import ModelClient

#: How much of each observation the chooser is shown. A tool result can be long, and the
#: chooser needs to know *what came back*, not to re-read all of it — the brain gets the full
#: pack later. Keeps a wide catalogue and a long history inside a small model's context.
OBSERVATION_PREVIEW_CHARS: int = 400

_PROMPT = """You are choosing the next step in an investigation of an industrial chiller plant.

THE QUESTION
{question}

TOOLS YOU MAY CALL
{tools}

WHAT HAS HAPPENED SO FAR
{history}

You have {remaining} step(s) left.

Choose ONE of:
- call a tool that would move the investigation forward
- finish, if the steps so far already answer the question

Return ONLY this JSON object and nothing else:
{{"move": "call", "tool": "<name>", "arguments": {{}}, "purpose": "<what this establishes>"}}
or
{{"move": "finish", "purpose": "<why nothing more is needed>"}}

Rules:
- Only ever name a tool from the list above. Never invent one.
- "purpose" is what the step is meant to ESTABLISH, in words — never a bare tool name.
- Do not repeat a call that already appears in the history; it will return the same thing.
- Prefer finishing over calling a tool that cannot change the answer.
- Write nothing outside the JSON."""


@dataclass(frozen=True)
class ModelChooser:
    """Ask `devstral` for the next move, and fall back to a rule when it cannot answer.

    `fallback` is required rather than optional. A chooser with no floor is one that turns
    every model hiccup into a stopped investigation, and the deterministic chooser it wraps is
    the same object the loop would otherwise have used.
    """

    client: ModelClient
    fallback: object
    """Any deterministic `Chooser` — in practice `PlannedChooser`. Called on every path this
    one cannot complete, so a failure costs a worse choice rather than no choice."""

    async def __call__(self, state: LoopState) -> ToolChoice:  # noqa: PLR0911
        names = {t.get("name") for t in state.available_tools}
        try:
            completion = await self.client.complete(
                role="tool",
                task="choose",
                messages=[
                    {"role": "system", "content": "You return one JSON object and no other text."},
                    {"role": "user", "content": self._render(state)},
                ],
            )
        except Exception as exc:  # an unreachable chooser is a fallback, not a crash
            return await self._fall_back(
                state, f"the chooser was unreachable ({type(exc).__name__})"
            )

        text = (getattr(completion, "text", "") or "").strip()
        opened, closed = text.find("{"), text.rfind("}")
        if opened < 0 or closed <= opened:
            return await self._fall_back(state, "the chooser returned no JSON")
        try:
            parsed = json.loads(text[opened : closed + 1])
        except ValueError:
            return await self._fall_back(state, "the chooser's JSON could not be parsed")
        if not isinstance(parsed, dict):
            return await self._fall_back(state, "the chooser returned JSON that was not an object")

        purpose = str(parsed.get("purpose") or "").strip()
        if str(parsed.get("move") or "").lower() == "finish":
            return ToolChoice(
                move=Move.FINISH,
                purpose=purpose or "the chooser decided enough was already known",
            )

        tool = str(parsed.get("tool") or "").strip()
        if tool not in names:
            # Not an error — the catalogue is the authority and the loop is designed to be
            # told wrong. Falling back is cheaper than a round trip that `G4` would refuse.
            return await self._fall_back(
                state, f"the chooser named {tool!r}, which is not in the catalogue"
            )

        arguments = parsed.get("arguments")
        return ToolChoice(
            move=Move.CALL_TOOL,
            tool=tool,
            arguments=arguments if isinstance(arguments, dict) else {},
            purpose=purpose or f"establish what {tool} returns",
        )

    async def _fall_back(self, state: LoopState, why: str) -> ToolChoice:
        """The deterministic decision, carrying why the model's was not used.

        The reason travels on `purpose` because that is what the ceiling report reads back —
        an investigation that ran on the fallback should say so where somebody will see it.
        """
        choice = await self.fallback(state)  # type: ignore[operator]
        note = (
            f"{choice.purpose} (chose by rule: {why})"
            if choice.purpose
            else f"chose by rule: {why}"
        )
        return ToolChoice(
            move=choice.move,
            tool=choice.tool,
            arguments=choice.arguments,
            purpose=note,
            answer=choice.answer,
        )

    def _render(self, state: LoopState) -> str:
        tools = "\n".join(
            f"- {t.get('name')}: {t.get('description', '')}" for t in state.available_tools
        ) or "(no tools are available)"

        # `Step.render()` is written for exactly this reader — it words a refusal reason
        # rather than showing an empty observation, which is the distinction a chooser
        # must see to avoid retrying a call that was refused rather than unanswered.
        history = (
            "\n".join(
                step.render()[:OBSERVATION_PREVIEW_CHARS] for step in state.steps
            )
            or "Nothing yet — this is the first step."
        )
        return _PROMPT.format(
            question=state.question,
            tools=tools,
            history=history,
            remaining=state.steps_remaining,
        )
