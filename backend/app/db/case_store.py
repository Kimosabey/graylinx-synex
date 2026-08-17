"""`RC8` idempotent seeding · `RC9` case ageing — the queue that survives a restart.

**The failure `RC8` exists for.** Twenty-two detected episodes sat outside the case queue
because nothing called the seed, and the queue read as empty. Inherited constraint 21:
*detection is not seeding.* A detector that fires into nowhere is worse than no detector,
because an empty queue reads as a clean plant.

**Why idempotency is a unique index and not an `if`.** `RC17` makes the seed a scheduled job,
so it runs repeatedly and may run twice at once. A `SELECT`-then-`INSERT` has a window between
the two statements; a unique index does not. The insert is attempted and the integrity error
is the *expected* path, not the exceptional one — which is why it is caught per row rather
than wrapping the batch.

**Why `RC9` keeps two kinds of stale apart.** Four open cases once described transmitters
repaired weeks earlier, and twenty had been waiting since April. Those are different problems:
one says the plant moved on, the other says nobody looked. A single `stale` flag would let a
fixed machine and a forgotten one look identical, and the second is the one that needs a
person.

**No number is invented here.** How long a case may sit before it ages has no source, so it
is a parameter with a stated default and `Q56` against it — never a constant that looks
settled.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.state import AuditRow, CaseRow, FindingRow
from app.domain.cases import CaseState, can_transition

#: How long an untouched case waits before it ages visibly. **No document fixes this**, so it
#: is a default rather than a constant and `Q56` carries the question. Seven days because the
#: observed failure was cases waiting since April — months, not days — so any value in the
#: range of days surfaces it, and ageing only ever *shows* a case, never closes or hides one.
DEFAULT_AGEING_AFTER: timedelta = timedelta(days=7)


@dataclass(frozen=True)
class SeedOutcome:
    """What one seeding pass did. Reported as counts because `RC17` shows detected-but-not-
    queued rather than assuming it is zero."""

    seeded: int
    already_present: int
    considered: int

    @property
    def is_idempotent_replay(self) -> bool:
        return self.seeded == 0 and self.already_present > 0

    def render(self) -> str:
        return (
            f"{self.considered} detected episode(s) considered: {self.seeded} opened a case, "
            f"{self.already_present} already had one. A re-run opens nothing."
        )


@dataclass(frozen=True)
class AgeingOutcome:
    """`RC9`. The two kinds, counted separately — see the module docstring."""

    cleared: int
    untouched: int

    def render(self) -> str:
        parts = []
        if self.cleared:
            parts.append(f"{self.cleared} case(s) marked stale because the condition cleared")
        if self.untouched:
            parts.append(f"{self.untouched} case(s) ageing because nobody has touched them")
        return "; ".join(parts) if parts else "no case changed"


@dataclass(frozen=True)
class DetectedEpisode:
    """The seed input. Deliberately not `analytics.episodes.Episode` — `app.db` sits below
    `app.analytics` in the layering, so the store takes a plain record and the caller maps."""

    equipment_key: str
    fault_label: str
    day: date
    slot_count: int = 0


class CaseStore:
    """Reads and writes Synex's own case queue. The only place that does."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── RC8 ────────────────────────────────────────────────────────────────────

    async def seed(self, episodes: Sequence[DetectedEpisode]) -> SeedOutcome:
        """Open a case per episode, exactly once, however many times this runs."""
        seeded = already = 0

        for episode in episodes:
            key = CaseRow.make_seed_key(
                episode.equipment_key, episode.fault_label, episode.day
            )
            row = CaseRow(
                seed_key=key,
                equipment_key=episode.equipment_key,
                fault_label=episode.fault_label,
                day=episode.day,
                slot_count=episode.slot_count,
                state=CaseState.DETECTED.value,
            )
            # A savepoint per row: an integrity error is the *expected* outcome of a re-run,
            # and without the nested transaction it would poison the whole batch.
            try:
                async with self._session.begin_nested():
                    self._session.add(row)
                seeded += 1
            except IntegrityError:
                already += 1

        await self._session.flush()
        return SeedOutcome(
            seeded=seeded, already_present=already, considered=len(episodes)
        )

    async def open_cases(self) -> Sequence[CaseRow]:
        """Everything not closed and not stale — the queue a person actually works."""
        stmt = select(CaseRow).where(
            CaseRow.state.notin_([CaseState.CLOSED.value, CaseState.STALE.value])
        )
        return (await self._session.scalars(stmt)).all()

    async def by_seed_key(self, key: str) -> CaseRow | None:
        return await self._session.scalar(select(CaseRow).where(CaseRow.seed_key == key))

    async def count(self) -> int:
        return len((await self._session.scalars(select(CaseRow))).all())

    # ── the state machine, enforced at the boundary ────────────────────────────

    async def transition(self, case: CaseRow, target: CaseState) -> tuple[bool, str]:
        """Move a case, or refuse and say why.

        The machine lives in `app/domain/cases.py` and is asked here rather than reimplemented.
        A store that could write any state would make the machine advisory.
        """
        current = CaseState(case.state)
        if not can_transition(current, target):
            return False, (
                f"a case cannot go from {current.value} to {target.value}. "
                f"The only route to closed runs through verification."
            )
        case.state = target.value
        await self._session.flush()
        return True, f"case moved from {current.value} to {target.value}"

    # ── RC9 ────────────────────────────────────────────────────────────────────

    async def age(
        self,
        cleared_seed_keys: Sequence[str] = (),
        now: datetime | None = None,
        ageing_after: timedelta = DEFAULT_AGEING_AFTER,
    ) -> AgeingOutcome:
        """Mark stale what the plant settled, and surface what nobody has touched.

        `cleared_seed_keys` is passed in rather than derived: whether a condition cleared is a
        question about telemetry, and `app.db` must not reach across to the plant to answer it.
        The caller — a scheduled job — reads the detector and hands the answer down.
        """
        moment = now or datetime.now(UTC)
        cleared = untouched = 0

        for case in await self.open_cases():
            if case.seed_key in cleared_seed_keys:
                case.state = CaseState.STALE.value
                case.condition_cleared = True
                case.stale_at = moment
                case.stale_reason = (
                    "the condition that opened this case is no longer detected. That is not "
                    "proof the repair worked — only verification establishes that."
                )
                cleared += 1
                continue

            if moment - _aware(case.updated_at) >= ageing_after:
                # Deliberately **not** a state change. Ageing makes a case visible; it does
                # not close it, and it does not decide anything. Twenty cases waiting since
                # April needed a person, not a status.
                case.condition_cleared = False
                case.stale_at = moment
                case.stale_reason = (
                    f"nobody has touched this case since "
                    f"{_aware(case.updated_at):%Y-%m-%d}. It is still open."
                )
                untouched += 1

        await self._session.flush()
        return AgeingOutcome(cleared=cleared, untouched=untouched)

    # ── G6 ─────────────────────────────────────────────────────────────────────

    async def record_audit(
        self,
        *,
        action: str,
        persona: str = "",
        target: str = "",
        decision: str = "",
        reason: str = "",
        detail: dict | None = None,
    ) -> AuditRow:
        """Append one audit row. Never updates — an audit trail that can be edited is a log."""
        row = AuditRow(
            action=action,
            persona=persona,
            target=target,
            decision=decision,
            reason=reason,
            detail=detail or {},
            is_production_identity=False,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def findings_for(self, case: CaseRow) -> Sequence[FindingRow]:
        """The answers recorded against one case.

        An explicit query rather than `case.findings`, because the relationship lazy-loads and
        a lazy load outside the async context raises `MissingGreenlet` — a failure that shows
        up as a crash in a request handler rather than as a slow query. Offering the method
        means a caller never has to know that.
        """
        stmt = select(FindingRow).where(FindingRow.case_id == case.id).order_by(FindingRow.item_id)
        return (await self._session.scalars(stmt)).all()

    async def record_finding(
        self, case: CaseRow, item_id: str, kind: str, value: str | None = None, note: str = ""
    ) -> FindingRow:
        """One answer per item per case. A second answer updates rather than appends, so the
        gate never has to guess which of two answers is current."""
        existing = await self._session.scalar(
            select(FindingRow).where(
                FindingRow.case_id == case.id, FindingRow.item_id == item_id
            )
        )
        if existing is not None:
            existing.kind = kind
            existing.value = value
            existing.note = note
            await self._session.flush()
            return existing

        row = FindingRow(
            case_id=case.id, item_id=item_id, kind=kind, value=value, note=note
        )
        self._session.add(row)
        await self._session.flush()
        return row


def _aware(moment: datetime) -> datetime:
    """SQLite and some drivers hand back naive datetimes even from a timezone-aware column.

    Treating a naive value as UTC is correct here because `_now` only ever writes UTC — but it
    is done in one place, and named, rather than scattered as `.replace(tzinfo=...)` calls
    that a reader has to trust individually.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
