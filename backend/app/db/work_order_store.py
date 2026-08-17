"""`C8`'s second half — the write · `G5` idempotency, which is an index rather than an `if`.

**The failure this exists to prevent, with the numbers behind it.** On the reference queue 39
detected episodes fall across **12 equipment-days** — a 3.25× ratio — and on 2026-04-15
chiller 1 carried **five fault labels at once**. A single real fault spans hundreds of
consecutive readings, **412 observed**, so one afternoon on one machine can be arrived at from
five hundred slots, five labels and any number of retries. A confirm that writes a row per
arrival dispatches a technician per arrival, and the second technician finds the first one
already at the machine.

**Why the idempotency is a unique index and not a `SELECT` then an `INSERT`.** The same
reasoning `RC8` records for the case queue: a read-then-write has a window between the two
statements, and two workers — or one impatient person and a flaky connection — fit inside it.
A unique index has no window. So the insert is attempted and the integrity error is the
**expected** path rather than the exceptional one, caught per row.

**A retry is answered with the first row, unmodified.** Not with a copy of what the second
caller sent, and not with a merge of the two. Whoever retried sees the job that actually
exists, including the evidence it was raised on — because the alternative is a row whose
stored justification is not the one anybody confirmed.

**Nothing persists that nobody confirmed.** `C8` is *"shows the action before saving"*, and a
store whose write path does not require the act would make the showing decorative.
`ConfirmedWorkOrder` refuses to exist without a `confirmed_by`, so there is no way to reach
this table from a draft alone.

**The record is deliberately not `WorkOrderDraft`.** `app.db` sits below `app.services` in the
layering (D-012), so the store takes a plain record and the caller maps — the same shape as
`DetectedEpisode`, and for the same reason.

**Nothing here decides anything.** Whether this identity may raise a job at all is `G3`'s
question, answered in `app/domain/authority.py` before a record is ever built. This module
stores what that decided.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.state import WorkOrderRow


class UnconfirmedWriteError(ValueError):
    """A record was built without the act that is supposed to create it.

    Raised at construction rather than at the insert, so the failure lands on the line that
    forgot the confirmation rather than three layers away inside a transaction.
    """


@dataclass(frozen=True)
class ConfirmedWorkOrder:
    """A draft that somebody explicitly confirmed, flattened for storage.

    Every field here is a fact the confirming person saw or the platform derived before they
    pressed anything. Nothing is computed at insert time, because a value that appears only
    once the row exists is a value nobody approved.
    """

    idempotency_key: str
    """`G5`. Derived from equipment, fault and day — never from the moment of the request, or
    two presses a second apart would be two different jobs."""

    equipment_key: str

    confirmed_by: str
    """Who performed the act. Empty is refused — see `UnconfirmedWriteError`."""

    evidence: dict = field(default_factory=dict)
    """`W3`, and `C8`'s guarantee. Carries the draft exactly as it was rendered under
    `shown_as`, so *what was shown* and *what was saved* can be compared rather than trusted."""

    kind: str = "corrective"
    """`RC7`'s three artefacts: *inspection*, *authorisation*, *corrective*. A job whose task
    is a question is not the same as one whose task is a measurement."""

    state: str = "confirmed"
    """A `WorkOrderState` value. The enum lives in `app.services.work_orders`, one layer above,
    so it arrives as a string — the same compromise `DetectedEpisode` makes."""

    priority: str = "unrated"
    priority_is_complete: bool = False
    """`W4`. Three of the four inputs do not exist in this snapshot (`Q51`), so a priority that
    stored as though it were finished would be a severity wearing a rank."""

    case_id: int | None = None
    """`None` means this job was raised outside a case, which is a different fact from *the
    case is unknown*. Nothing here fills it in by guessing."""

    def __post_init__(self) -> None:
        if not self.confirmed_by.strip():
            raise UnconfirmedWriteError(
                "a work order cannot be stored without the identity that confirmed it. C8 "
                "shows the action before saving it, and a write that does not require the "
                "confirmation makes the showing decorative."
            )
        if not self.idempotency_key.strip():
            raise UnconfirmedWriteError(
                "a work order cannot be stored without an idempotency key. G5 is enforced by "
                "a unique index, and an empty key would let the second retry through."
            )


@dataclass(frozen=True)
class WriteOutcome:
    """What one confirm did, and which of the two things it was.

    `created` is never reported on its own: a caller that sees `False` needs to know it got
    somebody's earlier job back rather than that nothing happened.
    """

    row: WorkOrderRow
    created: bool
    reason: str

    @property
    def is_replay(self) -> bool:
        """The retry path. Not an error, and not a failure — the index did its job."""
        return not self.created


class WorkOrderStore:
    """Reads and writes Synex's own work orders. The only place that does."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def confirm(self, record: ConfirmedWorkOrder) -> WriteOutcome:
        """Store a confirmed draft, exactly once per equipment, fault and day.

        The integrity error is expected rather than exceptional, so it is caught around a
        savepoint: without the nested transaction a retry would poison whatever else the
        caller is writing in the same session — the case transition and the audit row.
        """
        row = WorkOrderRow(
            case_id=record.case_id,
            equipment_key=record.equipment_key,
            kind=record.kind,
            state=record.state,
            priority=record.priority,
            priority_is_complete=record.priority_is_complete,
            evidence=record.evidence,
            idempotency_key=record.idempotency_key,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            existing = await self.by_idempotency_key(record.idempotency_key)
            if existing is None:
                # The index fired but the row it collided with is not findable by that key,
                # so a *different* constraint was violated and this is not the retry path.
                # Re-raised rather than reported as a replay: answering an unknown failure
                # with somebody else's work order is worse than the failure.
                raise
            return WriteOutcome(
                row=existing,
                created=False,
                reason=(
                    f"a work order for this equipment, fault and day already exists — "
                    f"work order {existing.id}, raised {_stamp(existing)}. This retry "
                    f"returned that row unchanged rather than raising a second job, and "
                    f"nothing about it was updated."
                ),
            )

        await self._session.flush()
        return WriteOutcome(
            row=row,
            created=True,
            reason=(
                f"work order {row.id} was raised on the explicit confirmation of "
                f"{record.confirmed_by}. The key is derived from equipment, fault and day, "
                f"so a retry returns this row rather than raising a second."
            ),
        )

    async def by_idempotency_key(self, key: str) -> WorkOrderRow | None:
        return await self._session.scalar(
            select(WorkOrderRow).where(WorkOrderRow.idempotency_key == key)
        )

    async def for_equipment(self, equipment_key: str) -> Sequence[WorkOrderRow]:
        stmt = (
            select(WorkOrderRow)
            .where(WorkOrderRow.equipment_key == equipment_key)
            .order_by(WorkOrderRow.id)
        )
        return (await self._session.scalars(stmt)).all()

    async def count(self) -> int:
        return len((await self._session.scalars(select(WorkOrderRow))).all())


def _stamp(row: WorkOrderRow) -> str:
    """When a row was raised, in words rather than a dash when it is absent.

    A row read back before its default has been applied has no timestamp, and printing an
    empty string there would read as *raised at no time*.
    """
    if row.created_at is None:
        return "at a moment this row does not record"
    return f"{row.created_at:%Y-%m-%d %H:%M}"
