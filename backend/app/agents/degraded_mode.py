"""What is actually degraded right now — the probes behind `app/domain/degradation.py`.

**The gap this closes, stated exactly.** `app/agents/answer.py` sets `Turn.degraded_reason`
when the roster cannot be reached, and `/api/v1/health` sets `status` to `degraded` when MySQL
is not connected. Those are two capabilities out of seven, reported in two places, in two
shapes, neither of which mentions the other. Nothing aggregates them, so a surface cannot
answer *"which capabilities am I running without"* — and `CONTEXT.md` §13 is exactly the
requirement that it can.

**No probe here opens a socket.** A health endpoint that dials four hosts is a health endpoint
that times out, and the first thing anybody does with a timing-out health endpoint is stop
reading it. So this module reports what the process **already knows** — the pool it opened at
startup, the mode it is configured in, the transcripts on disk, the two durability flags the
code itself publishes — and reports everything else as `NOT_PROBED` with the reason. An
unprobed dependency is `UNKNOWN`, never a quiet pass: inherited constraint 7, `NULL` means not
diagnosed rather than healthy.

**The transcript count is a real probe, not a proxy.** In `stub` mode a missing transcript
raises on every call, and `SESSION-HANDOFF.md` §3 records that `backend/tests/fixtures/` holds
nothing but `__init__.py` — **no transcript has ever been recorded**. So an empty directory in
`stub` mode is not "the box is unreachable, we do not know": it is the certainty that every
answer this process gives will be the deterministic one. Counting the files says so before
anybody asks a question.

**Nothing here calls a model.** Reading a directory listing is not inference, and this module
must keep working precisely when the roster does not.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.degradation import (
    Capability,
    DegradationReport,
    Finding,
    Observation,
    assess,
)
from app.llm.client import TRANSCRIPT_DIR
from app.services import audit_log
from app.tools.gateway import GATEWAY, Gateway

#: Modes in which a completion is fetched from the box rather than replayed from disk. Kept as
#: data rather than as `mode != "stub"`, so adding a fourth mode is a decision here rather than
#: a silent reclassification.
MODES_THAT_REACH_THE_BOX: frozenset[str] = frozenset({"record", "live"})


def observe_plant(repo: object | None, error: str | None) -> Observation:
    """MySQL, from the pool the lifespan either opened or failed to open.

    The error string is carried through verbatim. *"Nothing listens on :3307"* and *"access
    denied for `synex_plant_ro`"* need different people, and collapsing them into *"the plant
    database is down"* sends the wrong one.
    """
    if repo is not None:
        return Observation(
            capability=Capability.PLANT_TELEMETRY,
            finding=Finding.REACHED,
            detail="the connection pool opened at startup and is held on the application state",
        )
    return Observation(
        capability=Capability.PLANT_TELEMETRY,
        finding=Finding.NOT_REACHED,
        detail=(
            error
            or "the pool was never opened and no error was recorded, which is itself a defect"
        ),
    )


def observe_answer_prose(
    *,
    model_mode: str,
    transcript_dir: Path | None = None,
    turn_degraded_reason: str = "",
) -> Observation:
    """The roster, or the recording of it — and the turn's own verdict outranks both.

    Order matters. If a turn has already fallen back then the question is settled by evidence
    rather than by inference, whatever the mode says, so `turn_degraded_reason` is read first.
    A configuration that claims the box is reachable does not outrank a call that just failed.
    """
    if turn_degraded_reason.strip():
        return Observation(
            capability=Capability.ANSWER_PROSE,
            finding=Finding.NOT_REACHED,
            detail=f"this turn already fell back: {turn_degraded_reason.strip()}",
        )

    if model_mode in MODES_THAT_REACH_THE_BOX:
        return Observation(
            capability=Capability.ANSWER_PROSE,
            finding=Finding.NOT_PROBED,
            detail=(
                f"the mode is {model_mode!r}, so a completion goes to the box. Establishing "
                f"whether it answers costs a call to it, and this report makes none"
            ),
        )

    recorded = _transcripts_on_disk(transcript_dir)
    if recorded == 0:
        return Observation(
            capability=Capability.ANSWER_PROSE,
            finding=Finding.NOT_REACHED,
            detail=(
                "the mode is 'stub' and no transcript has been recorded, so every completion "
                "raises and every answer in this process is the deterministic one"
            ),
        )
    return Observation(
        capability=Capability.ANSWER_PROSE,
        finding=Finding.REACHED,
        detail=(
            f"the mode is 'stub' and {recorded} transcript(s) are on disk. A prompt that was "
            f"recorded replays; one that was not still raises, because the key is a hash of "
            f"the prompt"
        ),
    )


def observe_audit_trail() -> Observation:
    """`G6`, read off the flag the sink itself publishes rather than off a belief.

    `audit_log.IS_DURABLE` exists so a health endpoint can say this. Until now nothing did,
    which made the flag a comment.
    """
    if audit_log.IS_DURABLE:
        return Observation(
            capability=Capability.AUDIT_TRAIL,
            finding=Finding.REACHED,
            detail="the sink reports itself durable",
        )
    return Observation(
        capability=Capability.AUDIT_TRAIL,
        finding=Finding.NOT_REACHED,
        detail=(
            f"the sink reports itself not durable and currently holds {audit_log.count()} "
            f"row(s) in this process"
        ),
    )


def observe_tool_idempotency(gateway: Gateway | None = None) -> Observation:
    """`G5` at the tool boundary, read off `Gateway.is_durable`.

    Worth naming separately from the case queue even though both end at PostgreSQL: the
    gateway's ledger is in memory *by construction* rather than because something is down, so
    it stays substituted on a completely healthy platform. A report that only listed outages
    would never mention it, and it is a real limit on what `G5` currently promises.
    """
    door = gateway or GATEWAY
    if door.is_durable:
        return Observation(
            capability=Capability.TOOL_IDEMPOTENCY,
            finding=Finding.REACHED,
            detail="the gateway reports a durable ledger",
        )
    return Observation(
        capability=Capability.TOOL_IDEMPOTENCY,
        finding=Finding.NOT_REACHED,
        detail=(
            "the gateway's ledger is in memory, so it holds within a turn and is empty again "
            "after a restart"
        ),
    )


def observe_case_queue(*, session_opened: bool | None = None) -> Observation:
    """PostgreSQL. `None` means nobody looked, and that is the honest default today.

    The application's lifespan opens the plant pool and nothing else, so at the time a health
    request is served there is no state session to ask. Reporting that as *available* because
    the container is probably running would be the assumption `SESSION-HANDOFF.md` §3 names:
    two of three recorded blockers were things already provisioned that nobody had started.
    """
    if session_opened is None:
        return Observation(
            capability=Capability.CASE_QUEUE,
            finding=Finding.NOT_PROBED,
            detail=(
                "the lifespan opens the plant pool and no state session, so nothing in this "
                "process has tried PostgreSQL since it started"
            ),
        )
    if session_opened:
        return Observation(
            capability=Capability.CASE_QUEUE,
            finding=Finding.REACHED,
            detail="a state session was opened by the caller and answered",
        )
    return Observation(
        capability=Capability.CASE_QUEUE,
        finding=Finding.NOT_REACHED,
        detail="a state session was attempted by the caller and did not open",
    )


def observe_embeddings() -> Observation:
    """The embedder on the host. Never probed from here — see the module docstring."""
    return Observation(
        capability=Capability.EMBEDDINGS,
        finding=Finding.NOT_PROBED,
        detail=(
            "reaching the embedder costs an HTTP call to Ollama on the host, and this report "
            "makes none. `K1` and `S4` establish it when they need it, and refuse if it is "
            "absent"
        ),
    )


def observe_knowledge_retrieval() -> Observation:
    """Retrieval sits on two other capabilities, so it is not probed independently."""
    return Observation(
        capability=Capability.KNOWLEDGE_RETRIEVAL,
        finding=Finding.NOT_PROBED,
        detail=(
            "it stands on pgvector and the embedder, neither of which this report probes. "
            "Deriving it from the two would state a conclusion nobody measured"
        ),
    )


def assess_platform(
    *,
    plant_repo: object | None,
    plant_error: str | None,
    model_mode: str,
    transcript_dir: Path | None = None,
    turn_degraded_reason: str = "",
    case_queue_session_opened: bool | None = None,
    gateway: Gateway | None = None,
) -> DegradationReport:
    """The whole report, from what the process already knows.

    `turn_degraded_reason` is the hook that makes this a *request*-level report rather than a
    process-level one: the Copilot turn already discovers whether the roster answered, and
    handing that in means the aggregate reflects what just happened rather than what was
    configured.
    """
    return assess(
        (
            observe_plant(plant_repo, plant_error),
            observe_case_queue(session_opened=case_queue_session_opened),
            observe_answer_prose(
                model_mode=model_mode,
                transcript_dir=transcript_dir,
                turn_degraded_reason=turn_degraded_reason,
            ),
            observe_embeddings(),
            observe_knowledge_retrieval(),
            observe_audit_trail(),
            observe_tool_idempotency(gateway),
        )
    )


def _transcripts_on_disk(directory: Path | None = None) -> int:
    """How many recordings exist. A missing directory is zero, not an error.

    The directory is created on the first `record` run, so its absence is the ordinary state of
    a machine that has never had the box — which is most of them.
    """
    root = directory or TRANSCRIPT_DIR
    if not root.is_dir():
        return 0
    return len(list(root.glob("*.json")))
