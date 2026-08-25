"""`RC17` detection-to-queue reconciliation — the seed that actually runs.

**The failure, measured.** Twenty-two detected episodes never reached the case queue —
including the only two rated *critical* — because the idempotent seed was never scheduled.
Inherited constraint 21: **detection is not seeding.** A detector that fires into nowhere is
worse than no detector, because the queue reads as empty and an empty queue reads as a clean
plant.

**`RC8` makes the seed safe to re-run; it does not make it run.** That distinction is the
whole feature. The unique index in `app/db/state.py` means calling this twice costs nothing —
so the scheduler can be dumb, frequent and unsupervised, which is the only kind that keeps
working after the person who set it up moves on.

**The number that must never be assumed.** `detected_but_not_queued` is reported on every
run, including when it is zero. A reconciliation that only spoke up when it found something
would be indistinguishable from one that had stopped running — and that is precisely how
twenty-two episodes went missing. The count is the artefact; opening the cases is the side
effect.

**Nothing here decides anything.** It reads what the trained model already emitted
(constraint 34: never re-detect), maps it to seed keys and hands them to the store. No model,
no thresholds, no judgement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.analytics.episodes import Episode, LabelledSlot, to_episodes
from app.config import Settings
from app.db.case_store import DetectedEpisode
from app.db.session import case_store, plant_repository
from app.db.state import CaseRow
from app.domain import faults

#: How often the seed runs. Frequency is safe to choose because `RC8` makes a re-run free —
#: the cost of running too often is a few no-op queries, and the cost of running too rarely is
#: the twenty-two-episode failure. Erring toward often is the cheap error.
#:
#: TBD (Q57): no document states a reconciliation interval. Fifteen minutes because the plant
#: writes on a five-minute slot cadence, so three slots is the smallest window that cannot
#: miss a whole reading period. It changes latency only; it never changes what is detected.
RECONCILE_EVERY_SECONDS: int = 15 * 60


@dataclass(frozen=True)
class Reconciliation:
    """What one pass found. **Reported whether or not anything changed.**"""

    detected: int
    queued_before: int
    seeded: int
    detected_but_not_queued: int
    ran_at: datetime

    @property
    def is_clean(self) -> bool:
        """Every detected episode has a case. Not the same as *no faults*."""
        return self.detected_but_not_queued == 0

    def render(self) -> str:
        if self.detected == 0:
            return (
                f"{self.ran_at:%Y-%m-%d %H:%M}: no episode was detected in the window. That is "
                f"the detector's silence, not a statement that the plant is healthy."
            )
        if self.is_clean:
            return (
                f"{self.ran_at:%Y-%m-%d %H:%M}: {self.detected} detected episode(s), all of "
                f"them queued ({self.seeded} opened this pass). Nothing is waiting outside "
                f"the queue."
            )
        return (
            f"{self.ran_at:%Y-%m-%d %H:%M}: {self.detected} detected episode(s) and "
            f"{self.detected_but_not_queued} of them are NOT in the queue. That is the "
            f"twenty-two-episode failure happening again — the seed is not reaching them."
        )

    def as_dict(self) -> dict:
        return {
            "detected": self.detected,
            "queued_before": self.queued_before,
            "seeded": self.seeded,
            "detected_but_not_queued": self.detected_but_not_queued,
            "is_clean": self.is_clean,
            "ran_at": self.ran_at.isoformat(),
            "rendered": self.render(),
        }


def to_detected(episodes: tuple[Episode, ...]) -> tuple[DetectedEpisode, ...]:
    """Map analytics episodes onto the store's input.

    Outcomes are dropped here rather than in the store: `NO_DIAGNOSIS` at 5,309 slots and
    `NO_EFFICIENCY_FAULT` at 943 are the platform's commonest labelled results, and seeding a
    case for a refusal would turn the honest answer into work.
    """
    return tuple(
        DetectedEpisode(
            equipment_key=e.equipment_key,
            fault_label=e.fault_label,
            day=e.day,
            slot_count=e.slot_count,
        )
        for e in episodes
        if _is_fault(e.fault_label)
    )


def _is_fault(label: str) -> bool:
    fault = faults.by_label(label)
    return bool(fault and fault.is_fault)


async def reconcile_once(settings: Settings, now: datetime | None = None) -> Reconciliation:
    """One pass: read what was detected, seed what is missing, report the gap.

    Reads the plant read-only and writes only to Synex's own store — the two-store split, in
    one function.
    """
    moment = now or datetime.now().astimezone()

    async with plant_repository(settings) as repo:
        # `faulted_slots` already excludes both non-fault outcomes, so the refusals never
        # reach the queue — 5,309 `NO_DIAGNOSIS` slots seeded as cases would drown it.
        rows = await repo.faulted_slots()

    episodes = to_episodes(
        tuple(
            LabelledSlot(
                equipment_key=r.equipment_key,
                slot_time=r.slot_time,
                fault_label=r.fault_label,
            )
            for r in rows
            if r.fault_label
        )
    )
    detected = to_detected(episodes)

    async with case_store(settings) as store:
        before = await store.count()
        outcome = await store.seed(detected)

        # The gap is computed by asking the store, not by trusting the seed's own arithmetic.
        # A seed that silently failed would still report `seeded=0`, which is identical to a
        # clean re-run — so the check has to come from the other side.
        missing = 0
        for episode in detected:
            key = CaseRow.make_seed_key(
                episode.equipment_key, episode.fault_label, episode.day
            )
            if await store.by_seed_key(key) is None:
                missing += 1

        await store.record_audit(
            action="reconcile_detection_to_queue",
            decision="allowed",
            reason=(
                f"{len(detected)} detected, {outcome.seeded} seeded, {missing} still outside "
                f"the queue"
            ),
            detail={"detected": len(detected), "seeded": outcome.seeded, "missing": missing},
        )

    return Reconciliation(
        detected=len(detected),
        queued_before=before,
        seeded=outcome.seeded,
        detected_but_not_queued=missing,
        ran_at=moment,
    )


# ── the arq worker ──────────────────────────────────────────────────────────────
# `arq` rather than a cron entry because the reconciliation must run in the same process model
# as the application, with the same settings and the same connection handling. A cron job that
# shells out would need its own copy of both and would drift from them.


async def reconcile_job(ctx: dict) -> dict:
    """The arq entry point. Returns the reconciliation so it lands in the job result."""
    settings: Settings = ctx.get("settings") or Settings()
    return (await reconcile_once(settings)).as_dict()


async def _startup(ctx: dict) -> None:
    ctx["settings"] = Settings()


class WorkerSettings:
    """`arq` worker configuration. Run with `arq app.jobs.reconcile.WorkerSettings`.

    Kept as a class rather than assembled at import so importing this module — which the tests
    do — never opens a Redis connection.
    """

    functions = [reconcile_job]  # noqa: RUF012 — arq reads these as plain class attributes
    on_startup = _startup

    @staticmethod
    def cron_jobs():
        """Built lazily so `arq` is not imported unless a worker is actually started."""
        from arq import cron  # noqa: PLC0415 — lazy so importing this module never reaches Redis

        return [
            cron(
                reconcile_job,
                second=0,
                minute={0, 15, 30, 45},
                run_at_startup=True,
                # A missed run is not worth catching up on: the next pass seeds everything
                # outstanding anyway, because the seed is idempotent rather than incremental.
                max_tries=1,
            )
        ]

    @staticmethod
    def redis_settings():
        from arq.connections import RedisSettings  # noqa: PLC0415 — same reason as above

        return RedisSettings.from_dsn(Settings().redis_url)


def next_run_after(moment: datetime) -> date:
    """Exposed so a surface can say when the queue was last reconciled and when it will be
    again — a reconciliation nobody can see the schedule of is one nobody trusts."""
    return moment.date()
