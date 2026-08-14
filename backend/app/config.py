"""Settings — and the reasons, which are the point.

`.env.example` states the dividing rule and this file is the other half of it: **if a value
has a REASON it lives here with the reason above it; if it has a SECRET or an ADDRESS it
lives in the environment.** That is why `.env.example` is fifty lines and this is not. A
number without its reason is the thing that gets "tuned" at 2am by someone who does not know
what it was protecting.

`docs/20-architecture/03-from-thermynx.md` §7 says *"copy the table, not just the idea. Each
entry names the failure it prevents."* The ten ceilings below are that table, executable.
The `stops` text is not decoration — it is carried into `ceilings()` and rendered by the
operations endpoint, so the failure a bound prevents is visible to whoever is about to raise
it.

**Three of the ten have no number in the source.** The architecture record says "capped",
"hard cap" and "hard `LIMIT`" without values, and CLAUDE.md §2.2 forbids inventing one. They
are marked `TBD (Q48)` and carry a deliberately conservative provisional value, because the
alternative — leaving them unbounded until the question is answered — is the failure the
ceiling exists to prevent. `RESOURCE_CEILINGS_PROVISIONAL` names exactly which three, and a
test asserts that set does not grow.

**This module is not importable from `analytics` or `domain`.** Contracts 3 and 4 in
`importlinter.ini` forbid it by name: a pure function that reads a feature flag is not a pure
function, and the honesty primitives live in `analytics`.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── the three ceilings the architecture record leaves unnumbered ────────────────
# Q48. Each is a bound whose *existence* is sourced and whose *value* is not, so the value
# is provisional and says so. Named here rather than inline so the set is one thing a test
# can assert about, and so raising one is a visible edit rather than a character change.
RESOURCE_CEILINGS_PROVISIONAL = frozenset(
    {"max_input_chars", "max_context_chars", "max_sql_rows"}
)


class Settings(BaseSettings):
    """Every knob, with the failure it prevents written next to it."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # `model_` is a real prefix in this product — `model_mode`, `model_digest`. Pydantic
        # claims it for its own namespace and warns on every field. We use it deliberately.
        protected_namespaces=(),
    )

    # ── the plant: MySQL, shared with the existing platform, READ-ONLY ──────────
    # Q42, half-closed. The grant in `infra/sql/01-mysql-grants.sql` makes "Synex never
    # writes to the plant" a property of the database; this is the half that is a promise.
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "synex_plant_ro"
    mysql_password: str = ""
    mysql_db: str = "graylinx_synex"

    # ── Synex's own state ───────────────────────────────────────────────────────
    postgres_url: str = "postgresql+asyncpg://synex:dev@127.0.0.1:5443/synex"
    redis_url: str = "redis://127.0.0.1:6381/0"

    # ── inference ───────────────────────────────────────────────────────────────
    ollama_host: str = "http://127.0.0.1:11500"
    ollama_box_label: str = "Jarvis"

    # stub | record | live. The default is `stub` so the honest run is the one that needs
    # nothing: most of M1 is built with the box terminated, and the box is burst once a day.
    synex_model_mode: Literal["stub", "record", "live"] = "stub"

    # ── identity. D-013 ─────────────────────────────────────────────────────────
    auth_mode: str = "dev_jwt"
    jwt_secret: str = ""
    policy_version: str = "2026-08-13.1"

    # ── the window discipline ───────────────────────────────────────────────────
    # D-009. Real readings stop here; everything after is simulated, and the simulation
    # invented `cond_flow` — a signal this plant has never measured. Config-enforced rather
    # than a literal in a query, so a new repository cannot quietly omit the clip.
    synex_measured_window_end: datetime = datetime(2026, 6, 23, 11, 50, 0)

    backend_port: int = 8001
    log_json: bool = True

    # ════════════════════════════════════════════════════════════════════════════
    # The ten resource ceilings
    # `docs/20-architecture/03-from-thermynx.md` §7. One field each, in the order the
    # table gives them.
    # ════════════════════════════════════════════════════════════════════════════

    # 1 — Stops: a pasted wall of text becoming a VRAM spike.
    # TBD (Q48): the record says "capped" without a value.
    max_input_chars: int = Field(default=8_000)

    # 2 — Stops: unbounded growth, and silent partial context.
    # The second half is the one that is easy to get wrong. Truncating is fine; truncating
    # *silently* means the model answers from a fragment and the answer reads complete.
    # `context_truncation_marked` is not a setting — see below.
    # TBD (Q48): the record says "hard cap" without a value.
    max_context_chars: int = Field(default=24_000)

    # 3 — Stops: a tool loop that never terminates.
    max_react_steps: int = 8

    # 4 — Stops: a wedged Ollama stalling a request forever.
    # Q46 may lower this: no document states a target turn time, and 150 s can compose into
    # an answer nobody wants to watch arrive. It is a ceiling, not a target.
    graph_timeout_s: float = 150.0

    # 5 — Stops: one slow tool holding the loop.
    tool_timeout_s: float = 30.0

    # 6 — Stops: a planner fanning out unboundedly.
    max_specialists: int = 4

    # 7 — Stops: a retry loop burning the GPU on a bad answer.
    # One retry. Not zero, because a single re-ask fixes most ungrounded answers; not two,
    # because the second retry has never been the one that worked.
    max_grounding_retries: int = 1

    # 8 — Stops: routing costing more than answering.
    # Layer 4 of the routing ladder. The layers below it are deterministic and cost ~1 ms,
    # so this is the only part of routing that can get expensive.
    router_arbiter_timeout_s: float = 3.0

    # 9 — Stops: a generated query pulling the whole table.
    # Applied as a hard `LIMIT` injected by the validator, never as a trailing clause the
    # model was asked to include.
    # TBD (Q48): the record says "hard LIMIT" without a value.
    max_sql_rows: int = Field(default=500)

    # 10 — Stops: an error-feedback loop, and a repair smuggling a write.
    # "Re-validated" is the load-bearing word: a repaired query goes through the whole
    # validator again from the start. A repair that skipped validation would be a write
    # path opened by an error message.
    max_sql_repairs: int = 1

    @field_validator("synex_measured_window_end")
    @classmethod
    def _window_end_is_not_in_the_simulated_span(cls, v: datetime) -> datetime:
        """Moving this forward is how the simulated window gets demonstrated by accident.

        The value is a fact about the snapshot, not a preference, so a config edit that
        pushes it past the real data fails here rather than in a report six steps later.
        """
        latest_real = datetime(2026, 6, 23, 11, 50, 0)
        if v > latest_real:
            raise ValueError(
                f"measured window end {v.isoformat()} is after the last real reading "
                f"({latest_real.isoformat()}). Everything after it is simulated, and the "
                f"simulation invented cond_flow — see D-009"
            )
        return v

    @field_validator("max_input_chars", "max_context_chars", "max_sql_rows")
    @classmethod
    def _provisional_ceilings_stay_positive(cls, v: int) -> int:
        """A ceiling of zero or less is an unbounded ceiling with extra steps."""
        if v <= 0:
            raise ValueError("a resource ceiling must be a positive bound")
        return v

    # ── derived ─────────────────────────────────────────────────────────────────

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    @property
    def gpu_required(self) -> bool:
        """`stub` and `record` differ in what they write, not in what they need.

        `record` calls the box; `stub` replays a committed transcript. This is the flag that
        decides whether a code path may reach the network at all.
        """
        return self.synex_model_mode in ("record", "live")

    def ceilings(self) -> list[dict[str, object]]:
        """Every bound, its value, the failure it prevents, and whether it is sourced.

        Rendered by the operations endpoint. The `stops` column travels with the number on
        purpose: raising a ceiling should require reading what it was protecting.
        """
        rows: list[tuple[str, object, str]] = [
            ("max_input_chars", self.max_input_chars,
             "a pasted wall of text becoming a VRAM spike"),
            ("max_context_chars", self.max_context_chars,
             "unbounded growth, and silent partial context"),
            ("max_react_steps", self.max_react_steps,
             "a tool loop that never terminates"),
            ("graph_timeout_s", self.graph_timeout_s,
             "a wedged Ollama stalling a request forever"),
            ("tool_timeout_s", self.tool_timeout_s,
             "one slow tool holding the loop"),
            ("max_specialists", self.max_specialists,
             "a planner fanning out unboundedly"),
            ("max_grounding_retries", self.max_grounding_retries,
             "a retry loop burning the GPU on a bad answer"),
            ("router_arbiter_timeout_s", self.router_arbiter_timeout_s,
             "routing costing more than answering"),
            ("max_sql_rows", self.max_sql_rows,
             "a generated query pulling the whole table"),
            ("max_sql_repairs", self.max_sql_repairs,
             "an error-feedback loop, and a repair smuggling a write"),
        ]
        return [
            {
                "bound": name,
                "value": value,
                "stops": stops,
                "provisional": name in RESOURCE_CEILINGS_PROVISIONAL,
                "question": "Q48" if name in RESOURCE_CEILINGS_PROVISIONAL else None,
            }
            for name, value, stops in rows
        ]


# Truncation is marked, always. This is a constant rather than a setting because §7 names it
# one of the two easy ones to get wrong, and a switch labelled "mark truncation" is a switch
# somebody turns off to make an output look tidier. Silent partial context is the failure.
CONTEXT_TRUNCATION_MARKER = "\n\n[… context truncated to fit the assembled cap …]"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """One instance per process.

    Cached so that a ceiling cannot differ between two call sites in the same request —
    which would make "the bound that was applied" unanswerable after the fact.
    """
    return Settings()
