"""The streaming frame contract — declared once, consumed by both halves of the product.

This is data, not an emitter. The graph that produces frames arrives in M1.4 and the web
client that reads them in M1.5; the *contract* between them is written now, because the
failure it prevents is a frontend rendering a frame the backend stopped sending, and that
failure is cheapest to make impossible before either side exists.

**Ten frames, not nine.** The approved plan lists nine — `route`, `stage`, `token`,
`figure`, `evidence`, `audit`, `state`, `done`, `error`. `D-015` then added `no_diagnosis`
as a frame of its own, and it is the more recent decision, so ten is correct. The reason is
worth keeping next to the list: the inherited implementation emits a refusal as a `token`
frame, which leaves the interface unable to style a refusal differently from an answer.
`CLAUDE.md` §2.6 says `NO_DIAGNOSIS` must never be softened, and rendering a refusal in the
same typeface as a confident answer **softens it by presentation**. On this data the refusal
is also the modal outcome — 5,309 slots against 674 faulted ones. A state that common needs
to look deliberate.

`scripts/verify_sse_contract.py` reads this module as the single source of truth and fails
the build if either side names a frame that is not here.
"""
from __future__ import annotations

from typing import Final

# ── the frames ──────────────────────────────────────────────────────────────────

FRAMES: Final[tuple[str, ...]] = (
    "route",          # which skill took the turn, and at which ladder layer it was decided
    "stage",          # progress through the turn lifecycle — what the Inspector renders
    "token",          # answer text, streamed
    "figure",         # one Figure, already rendered to a display string. Never a raw float
    "evidence",       # a source row, table and count behind a figure
    "audit",          # a postcheck result — the six deterministic audits and the soft critique
    "no_diagnosis",   # D-015. The gate that failed, why, and what would change the answer
    "state",          # the answer-contract state. Exactly one per turn
    "done",           # the turn is over. Always last
    "error",          # transport or graph failure, distinct from a refusal
)

# ── the answer contract ─────────────────────────────────────────────────────────

# CONTEXT.md §7. Every turn ends in exactly one of these six.
ANSWER_STATES: Final[tuple[str, ...]] = (
    "ANSWERED",
    "PARTIAL",
    "NO_DIAGNOSIS",
    "NEEDS_APPROVAL",
    "BLOCKED",
    "FAILED",
)

# Exactly one `state` frame per turn, and it is the frame that carries one of the six above.
# "Exactly one" is the rule that stops a turn narrowing from ANSWERED to PARTIAL halfway
# through and leaving the interface showing whichever arrived last.
TERMINAL_STATE_FRAME: Final[str] = "state"

# `done` closes the stream and carries no meaning of its own. A turn that ends without it is
# a dropped connection, which the client must be able to tell apart from a completed turn.
STREAM_CLOSING_FRAME: Final[str] = "done"

# The only frame permitted to carry a number for display. M1.5 enforces the other half in
# the web layer: `FigureView` is the sole component allowed to render one.
NUMERIC_FRAME: Final[str] = "figure"

# A refusal is not an error and an error is not a refusal. Conflating them is how a
# NO_DIAGNOSIS starts looking like a bug — or worse, how a bug starts looking like an
# honest refusal.
REFUSAL_FRAME: Final[str] = "no_diagnosis"


def is_frame(name: str) -> bool:
    return name in FRAMES


def is_answer_state(name: str) -> bool:
    return name in ANSWER_STATES
