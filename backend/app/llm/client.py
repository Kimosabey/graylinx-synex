"""Reaching the model roster — `stub`, `record` or `live`.

**`stub` is the default, and that is the point.** Most of this build happened with the box
terminated. A transcript recorded once on the rented GPU replays instantly and
deterministically, so the evaluation suite, the API tests and the whole web layer can run on
a laptop and in CI. The box is then burst once a day for the runs that genuinely need it.

| Mode | Reaches the box | Writes a transcript | Used for |
|---|---|---|---|
| `stub` | no | no | the gate, CI, the web layer, most of development |
| `record` | yes | yes | capturing a transcript once, on the box |
| `live` | yes | no | the demonstration, and the acceptance run |

**Code never names a model.** Every call here asks for a *role* and `app.llm.models`
resolves it. This module is one of the two places permitted to import a model client at all
— contract 5 in `importlinter.ini` — and `tests/unit/test_role_table.py` walks the AST of
every module and fails if a model name appears outside the role table.

**The transcript key is the prompt.** A transcript is looked up by a hash of the role, the
task and the exact messages, so changing a prompt invalidates its recording rather than
silently replaying an answer to a question no longer being asked. That failure would be
invisible and would make every evaluation meaningless.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.llm.models import model_for
from app.llm.reasoning_policy import should_think

#: Committed to git deliberately. A transcript is evidence of what a model actually said,
#: and `.gitignore` names it as tracked rather than ignored.
TRANSCRIPT_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "transcripts"


class ModelUnavailable(RuntimeError):
    """The box could not be reached, or no transcript exists for this prompt.

    Raised rather than returning empty text. An empty completion is indistinguishable from a
    model that had nothing to say, and the reasoning policy exists because that exact
    confusion cost real debugging time.
    """


@dataclass(frozen=True)
class Completion:
    text: str
    role: str
    model: str
    task: str
    from_transcript: bool
    thinking_enabled: bool


def transcript_key(role: str, task: str, messages: list[dict[str, str]]) -> str:
    """A stable hash of everything that determines the answer.

    The prompt is *in* the key on purpose. Keying by role and task alone would let an edited
    prompt keep replaying the old recording, and every evaluation run after that edit would
    be measuring a question nobody was asking any more.
    """
    payload = json.dumps(
        {"role": role, "task": task, "messages": messages},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


class ModelClient:
    """One entry point to the roster. Ask for a role, never for a model."""

    def __init__(
        self,
        *,
        mode: str = "stub",
        host: str = "http://127.0.0.1:11500",
        timeout_s: float = 150.0,
        transcript_dir: Path | None = None,
    ) -> None:
        self._mode = mode
        self._host = host.rstrip("/")
        self._timeout_s = timeout_s
        self._dir = transcript_dir or TRANSCRIPT_DIR

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def reaches_the_box(self) -> bool:
        return self._mode in ("record", "live")

    # ── transcripts ─────────────────────────────────────────────────────────────

    def _path_for(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def _load(self, key: str) -> str | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["text"]

    def _save(self, key: str, completion: Completion, messages: list[dict[str, str]]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path_for(key).write_text(
            json.dumps(
                {
                    "key": key,
                    "role": completion.role,
                    "task": completion.task,
                    "model": completion.model,
                    # **Which machine produced this.** Decided 2026-08-17: every transcript is
                    # recorded on the Jarvis box and nowhere else. An internal 20 GB GPU was
                    # available and carries `phi4` and `devstral` identically, so a transcript
                    # from it would have been indistinguishable from a roster one — and
                    # "indistinguishable" is the property that makes a silent corruption
                    # possible. One box, one source, and the host on the row so the rule can
                    # be audited rather than remembered.
                    #
                    # Note the model name is already most of the guarantee: the brain is
                    # `gemma4:26b-a4b-it-qat`, which exists on no other host, so a brain
                    # transcript could not have come from anywhere else. This field closes the
                    # gap for the roles whose model is not unique.
                    "host": self._host,
                    "thinking_enabled": completion.thinking_enabled,
                    "messages": messages,
                    "text": completion.text,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    # ── the call ────────────────────────────────────────────────────────────────

    async def complete(
        self,
        *,
        role: str,
        task: str,
        messages: list[dict[str, str]],
        timeout_s: float | None = None,
    ) -> Completion:
        """One completion, by role.

        In `stub` mode a missing transcript raises rather than falling back to the box. A
        silent fallback would mean CI quietly needing a GPU, which is the one thing the whole
        mode split exists to prevent.
        """
        model = model_for(role)
        thinking = should_think(task, role=role)
        key = transcript_key(role, task, messages)

        if self._mode == "stub":
            text = self._load(key)
            if text is None:
                raise ModelUnavailable(
                    f"no transcript for role={role!r} task={task!r} (key {key}). "
                    f"Record one with SYNEX_MODEL_MODE=record on the box, or the prompt "
                    f"has changed since it was recorded."
                )
            return Completion(text, role, model, task, True, thinking)

        text = await self._call_box(model, messages, thinking, timeout_s or self._timeout_s)
        completion = Completion(text, role, model, task, False, thinking)
        if self._mode == "record":
            self._save(key, completion, messages)
        return completion

    async def _call_box(
        self,
        model: str,
        messages: list[dict[str, str]],
        thinking: bool,
        timeout_s: float,
    ) -> str:
        """Ollama on the rented box. Never a hosted API — that is what keeps inference on
        infrastructure we control, and it is why the roster has to fit one card.

        The `think` flag is only sent when the effective model is the brain; the other two
        reject it. `should_think` already enforces that, and passing it here regardless would
        make a 400 from the wrong model look like a network fault.
        """
        options: dict[str, object] = {"temperature": 0.2}
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if thinking:
            payload["think"] = True

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(f"{self._host}/api/chat", json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise ModelUnavailable(
                f"the box at {self._host} did not answer for {model}: {exc}"
            ) from exc

        text = (body.get("message") or {}).get("content", "")
        if not text.strip():
            # The reasoning-policy failure, made loud. With a tight budget and thinking on,
            # the model spends the whole allowance in the think channel and returns nothing.
            raise ModelUnavailable(
                f"{model} returned empty content"
                + (" with thinking enabled — see the reasoning policy" if thinking else "")
            )
        return text

    async def health(self) -> dict:
        """Is the roster actually there? Used by `/api/v1/health` when the mode needs a box."""
        if not self.reaches_the_box:
            return {"mode": self._mode, "reachable": None, "note": "stub mode reaches nothing"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._host}/api/tags")
                response.raise_for_status()
                installed = [m["name"] for m in response.json().get("models", [])]
            return {"mode": self._mode, "reachable": True, "installed": installed}
        except httpx.HTTPError as exc:
            return {"mode": self._mode, "reachable": False, "error": str(exc)}
