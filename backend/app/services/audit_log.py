"""The audit trail sink. `G6`, and it is M1 rather than later on purpose.

An audit trail added after the fact records only what somebody remembered to log. Written
from the first route, it records every turn — including the ones nobody expected, which are
the only ones an audit trail is actually for.

**This is an in-memory sink, and that is a stated limitation rather than a hidden one.**
Synex's own state belongs in PostgreSQL, and the durable implementation lands with the rest
of the Postgres work. Keeping the interface here now means the routes are already writing
one row per request, so making it durable is a change of sink and not a change of every call
site. `is_durable` is `False` so that nothing can mistake this for the permanent record.
"""
from __future__ import annotations

from app.services.control_plane import AuditRow

_ROWS: list[AuditRow] = []

#: The trail does not survive a restart yet. Named so a health endpoint can say so rather
#: than implying a permanence that does not exist — the same discipline as `Figure`.
IS_DURABLE: bool = False


def record(row: AuditRow) -> None:
    _ROWS.append(row)


def rows() -> tuple[AuditRow, ...]:
    return tuple(_ROWS)


def count() -> int:
    return len(_ROWS)


def clear() -> None:
    """Test-only. Never called by application code — the trail is append-only in service."""
    _ROWS.clear()
