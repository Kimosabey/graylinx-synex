"""Synex's own state — the first thing in this product that persists.

**Two stores, and the split is the point.** `graylinx_synex` on MySQL is the plant snapshot,
read through `synex_plant_ro`, which holds `SELECT` and nothing else. Synex writes *here*, to
its own Postgres. That is not tidiness: `graylinx_synex` is routinely dropped and re-cloned —
it happened on 2026-08-17 — and a case queue living inside it would be destroyed by the next
restore. `CONTEXT.md` §9 recorded this design before there was anything to persist; this
module is where it becomes real.

**`RC8`, and why it is a database constraint rather than a code path.** Inherited constraint
21: *detection is not seeding.* Twenty-two detected episodes once sat outside the case queue
because nothing called the seed, and the queue read as empty. The fix is a scheduled seed
(`RC17`) that is safe to run repeatedly — which means the idempotency has to survive two
workers running it at the same moment. A `SELECT`-then-`INSERT` in Python does not; a unique
index does. `seed_key` is that index, and constraint 35 gives it its shape: **one case per
equipment, fault and day**, because a single real fault spans hundreds of consecutive
readings — up to 412 observed — and per-slot cases would bury one afternoon under five
hundred rows.

**`RC9`, and why a case must be able to go stale.** Four open cases once described
transmitters repaired weeks earlier, and twenty had been waiting since April. Two different
things are called stale and they are kept apart here: a case whose **condition cleared**, and
a case **nobody has touched**. The first is evidence about the plant; the second is evidence
about the queue. Collapsing them would let a fixed machine and a forgotten one look identical.

**Nothing here decides anything.** The state machine is `app/domain/cases.py` and stays there —
this module stores what that decided. A transition is validated by `can_transition` before it
reaches a row, and a test asserts the row cannot hold a state the machine forbids.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    """UTC, always, and timezone-aware.

    A naive timestamp is how "opened three hours ago" becomes "opened tomorrow" on a machine
    in another region — and `RC9` ages cases by subtracting these.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """One declarative base. `metadata.create_all` is the migration path until Alembic —
    stated rather than implied, because a reader who assumes migrations exist will write one
    that never runs."""


class CaseRow(Base):
    """One case. The object between a named fault and a closed work order."""

    __tablename__ = "synex_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    seed_key: Mapped[str] = mapped_column(String(160), nullable=False)
    """`RC8`. `equipment|label|day` — constraint 35's identity, enforced by the unique index
    below rather than by a lookup that two workers could both pass."""

    equipment_key: Mapped[str] = mapped_column(String(64), nullable=False)
    fault_label: Mapped[str] = mapped_column(String(64), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    state: Mapped[str] = mapped_column(String(32), nullable=False, default="detected")
    """A `CaseState` value. Stored as text rather than a database enum so adding a state is a
    code change and a migration, not a migration that locks the table."""

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    """`RC9`. Words, always — a stale case with no reason is a row nobody can act on."""

    condition_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """Kept apart from *untouched* deliberately: one is evidence about the plant, the other
    about the queue, and a fixed machine must not look like a forgotten one."""

    slot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """How many readings carried the label. Evidence, not configuration."""

    findings: Mapped[list[FindingRow]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # `RC8` in one line. Two schedulers racing the same episode produce one case, and the
        # loser gets an integrity error rather than a duplicate queue entry.
        UniqueConstraint("seed_key", name="uq_synex_case_seed_key"),
        Index("ix_synex_case_state", "state"),
        Index("ix_synex_case_equipment_day", "equipment_key", "day"),
    )

    @staticmethod
    def make_seed_key(equipment_key: str, fault_label: str, day: date) -> str:
        """Constraint 35's identity, in one place so two call sites cannot disagree."""
        return f"{equipment_key}|{fault_label}|{day.isoformat()}"


class FindingRow(Base):
    """`RC4`/`RC10`. One answer to one checklist item.

    `kind` is load-bearing and not a boolean: *measured*, *estimated*, *cannot_check*,
    *not_applicable* and *not_answered* are five different facts, and only the first settles a
    blocking item. Six "N/A" presses once opened a blocking gate with zero evidence behind it.
    """

    __tablename__ = "synex_finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("synex_case.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="not_answered")
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    case: Mapped[CaseRow] = relationship(back_populates="findings")

    __table_args__ = (
        # One answer per item per case. A second answer is an *update*, not a second row —
        # otherwise a `cannot_check` and a later `measured` both exist and the gate has to
        # guess which is current.
        UniqueConstraint("case_id", "item_id", name="uq_synex_finding_case_item"),
    )


class WorkOrderRow(Base):
    """`W2`/`W3`. A job that arrives carrying its own justification."""

    __tablename__ = "synex_work_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("synex_case.id", ondelete="SET NULL"), nullable=True
    )
    equipment_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="corrective")
    """`RC7`'s three artefacts: *inspection*, *authorisation*, *corrective*. A job whose task
    is a **question** is not the same as one whose task is a measurement."""

    state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="unrated")
    priority_is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    """`W4`. Three of four inputs do not exist (`Q51`), so a priority that silently dropped
    them would be a severity wearing a rank — which a planner would schedule against."""

    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    """`G5`. A retry can never create a second work order — enforced by the index below."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_synex_work_order_idem"),
        Index("ix_synex_work_order_state", "state"),
    )


class AuditRow(Base):
    """`G6`. Every material action and decision, permanently.

    Append-only by discipline and by shape: there is no `updated_at`, and nothing in the
    repository updates a row. An audit trail that can be edited is a log.
    """

    __tablename__ = "synex_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    persona: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    target: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    is_production_identity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    """Recorded per row rather than assumed. Every audit row written today carries `False`,
    so a future reader cannot mistake a demonstration trail for a production one — which is
    exactly the mistake an audit trail exists to make impossible."""

    __table_args__ = (Index("ix_synex_audit_action", "action"),)
