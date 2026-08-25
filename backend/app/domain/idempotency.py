"""`G5` at the work-order boundary — what makes two requests the same job.

**The failure, with the numbers behind it.** Twelve equipment-days in the measured window carry
a fault, and a naive case per (equipment, day, label) gives **39** — a 3.25× ratio. On
2026-04-15 chiller 1 held **five labels at once**, and one real fault spans hundreds of
consecutive readings, **412 observed**. So a single afternoon on a single machine can be
arrived at from five hundred slots, five labels, several surfaces and any number of retries. A
write path that raises a row per arrival dispatches a technician per arrival.

**What was missing, precisely.** `app/tools/gateway.py` derives an idempotency key for a *tool
call*, from the tool name and its validated arguments, and `synex_work_order.idempotency_key`
carries a unique index waiting for one. Nothing computed the key in between. A store that takes
a key it does not derive enforces uniqueness over whatever the caller happened to pass — which
is the guarantee looking like it holds while resting on everybody's care. This module is the
derivation, and it lives in `domain` so the same key is reachable from a draft, from a confirm
and from a scheduled job without any of them importing each other.

**Four fields identify a job, and the fourth is the one that is easy to get wrong.**

| In the key | Why |
|---|---|
| equipment, fault label, day | Inherited constraint 35 — one case per equipment, fault and
  day, because per-slot identity would bury one afternoon under five hundred rows |
| **kind** | `RC7`'s three artefacts are **not** the same job. An *inspection* work order
  carries the open checks as its task list; an *authorisation* work order carries the
  **question**. A case that escalates twice, for two different blockers, needs two rows — and a
  key without `kind` would refuse the second as a duplicate and never raise it |

**The asymmetry that decides every judgement call here.** Raising a second job for one problem
wastes a visit. Refusing to raise a *real* second job means nobody goes, and nobody finds out,
because a suppressed duplicate leaves no trace anywhere. Inherited constraint 28 says the same
thing about causes: a fouled condenser on a machine that is also low on flow is two real
faults. So where this module is unsure, it splits rather than merges.

**Nothing here decides whether the job may be raised.** That is `G3`, in
`app/domain/authority.py`, and it runs before anything reaches a key.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.domain.escalation import Artefact


class WorkOrderKind(StrEnum):
    """The three things a work order can be. Two of them are `RC7` artefacts."""

    INSPECTION = "inspection"
    """`RC7`, the *no tool* route. The open checks are its task list."""

    AUTHORISATION = "authorisation"
    """`RC7`, the *no authority* and *cannot interpret* routes. The task is the question, not a
    measurement — handing a supervisor a gauge reading is how the wrong person ends up at the
    machine."""

    CORRECTIVE = "corrective"
    """The ordinary repair job raised from a diagnosed fault. Not an escalation artefact, which
    is why it has no `Artefact` member to map from."""


#: `RC7`'s artefacts, mapped to the kind a row stores. `Artefact.NONE` is deliberately absent:
#: the *defer* and *not sure* routes raise no work order at all, and giving them a kind would
#: create a job for a case where the whole point is that nobody was called.
#:
#: A test walks `Artefact` and fails if a new work-order artefact appears without a kind, so the
#: two enums cannot drift apart quietly.
KIND_FOR_ARTEFACT: dict[Artefact, WorkOrderKind] = {
    Artefact.INSPECTION_WORK_ORDER: WorkOrderKind.INSPECTION,
    Artefact.AUTHORISATION_WORK_ORDER: WorkOrderKind.AUTHORISATION,
}


@dataclass(frozen=True)
class KeyInput:
    """One field the key is derived from, and the rule that puts it there."""

    field: str
    because: str


@dataclass(frozen=True)
class ExcludedInput:
    """One field the key is deliberately **not** derived from, and what including it would do.

    Held as data rather than as an absence, because an exclusion nobody wrote down is one that
    gets added back by whoever next needs a key to be more specific — and every addition here
    makes a retry into a new job without anything failing.
    """

    field: str
    would_cause: str


KEY_INPUTS: tuple[KeyInput, ...] = (
    KeyInput(
        field="equipment_key",
        because="constraint 35's identity. Two machines are two jobs, always",
    ),
    KeyInput(
        field="fault_label",
        because=(
            "constraint 35, and constraint 28 behind it — a fouled condenser on a machine that "
            "is also low on flow is two real causes, so two labels are two jobs"
        ),
    ),
    KeyInput(
        field="day",
        because=(
            "constraint 35 again. A fault spanning 412 readings is one job, not 412, and the "
            "day is the granularity the detector itself produces"
        ),
    ),
    KeyInput(
        field="kind",
        because=(
            "`RC7`. An inspection work order and an authorisation work order for the same case "
            "are two real jobs — one asks for a measurement, the other asks a question"
        ),
    ),
)

EXCLUDED_FROM_THE_KEY: tuple[ExcludedInput, ...] = (
    ExcludedInput(
        field="the moment the request was made",
        would_cause=(
            "every retry keys differently, so the guarantee inverts: instead of never creating "
            "a second work order, a double press creates one every time"
        ),
    ),
    ExcludedInput(
        field="the persona who asked",
        would_cause=(
            "the same job raised by a reliability engineer and confirmed by a supervisor "
            "becomes two rows, and a technician arrives to find another already there"
        ),
    ),
    ExcludedInput(
        field="the priority",
        would_cause=(
            "`W4` has three of four inputs missing (`Q51`), so the priority can legitimately "
            "change between two attempts at the same job. Keying on it would turn a corrected "
            "priority into a duplicate dispatch"
        ),
    ),
    ExcludedInput(
        field="the drafted title and the evidence prose",
        would_cause=(
            "the pack is reassembled per request and the language model may word the title "
            "differently, so identity would depend on generated text — which is the one input "
            "here that nothing deterministic controls"
        ),
    ),
    ExcludedInput(
        field="the case row id",
        would_cause=(
            "a case re-seeded after a restore gets a new autoincrement id while being the same "
            "case. `graylinx_synex` is routinely dropped and re-cloned — it happened on "
            "2026-08-17 — so an identity resting on a surrogate key is one a restore breaks"
        ),
    ),
)

#: What a fault label of "" would otherwise become. Refused rather than defaulted: an empty
#: label silently collapses every unlabelled finding on one machine-day into a single job, and
#: a suppressed job leaves no trace anywhere.
#:
#: A caller that genuinely has no label passes this sentinel and accepts the consequence, which
#: is stated rather than hidden: all unlabelled findings on one machine-day are then one job.
#: Whether that is right is TBD (Q90) — it is the only place in this module where merging is
#: the default, and nothing in the register settles it.
UNLABELLED: str = "unlabelled_finding"

#: The digest length, matching `app/tools/gateway.py` so there is one convention rather than
#: two. The column is `String(64)`, which this fits with room to spare — and the reason the key
#: is a digest at all is that a readable `equipment|label|day|kind` would be **truncated** by
#: that column on a long label. A truncated key collides, a collision reads as a duplicate, and
#: a duplicate is never raised. That is the failure direction this module refuses.
KEY_LENGTH: int = 32


@dataclass(frozen=True)
class WorkOrderIdentity:
    """The four facts that make two requests the same job."""

    equipment_key: str
    fault_label: str
    day: date
    kind: WorkOrderKind = WorkOrderKind.CORRECTIVE

    def __post_init__(self) -> None:
        if not self.equipment_key.strip():
            raise ValueError(
                "a work order identity needs an equipment key. Without one every job on the "
                "site with the same label and day would share a key, and the second machine's "
                "job would never be raised."
            )
        if not self.fault_label.strip():
            raise ValueError(
                f"a work order identity needs a fault label. Pass {UNLABELLED!r} deliberately "
                f"if there genuinely is none — that merges every unlabelled finding on this "
                f"machine-day into one job, which is a decision rather than a default."
            )

    @property
    def basis(self) -> tuple[str, ...]:
        """Exactly what is hashed, in a fixed order, so a reader can reproduce the key."""
        return (
            self.kind.value,
            self.equipment_key.strip(),
            self.fault_label.strip(),
            self.day.isoformat(),
        )

    @property
    def key(self) -> str:
        return work_order_key(self)

    def render(self) -> str:
        """The identity in words, for a refusal that has to explain itself to a person.

        A duplicate refusal reading *"idempotency key collision"* tells somebody standing at a
        screen nothing they can act on.
        """
        return (
            f"a {self.kind.value} work order for {self.equipment_key} · {self.fault_label} on "
            f"{self.day:%Y-%m-%d}"
        )


def work_order_key(identity: WorkOrderIdentity) -> str:
    """`G5`. Same four facts, same key, on any machine and in any process.

    A null byte separates the fields so that no pair of values can be rearranged into the same
    string — otherwise an equipment key ending in a fragment of a label would key identically
    to a shorter one, and two different jobs would share a row.
    """
    canonical = "\x00".join(identity.basis)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:KEY_LENGTH]


def kind_for_artefact(artefact: Artefact) -> WorkOrderKind | None:
    """`RC7`'s artefact to the kind a row stores. `None` where no work order is raised at all.

    `None` here means *nobody was called*, which is the defer and not-sure routes working
    correctly — it is not a missing mapping, and a caller that treats it as one would create a
    job for a case that was deliberately parked.
    """
    return KIND_FOR_ARTEFACT.get(artefact)


def same_job(left: WorkOrderIdentity, right: WorkOrderIdentity) -> tuple[bool, str]:
    """Are these the same job, and the reason in words either way.

    Returned as a sentence rather than a bare comparison because this answer ends up in front
    of a person deciding whether the platform was right to refuse their second press.
    """
    if left.key == right.key:
        return True, (
            f"the same job: both are {left.render()}. A second row would send a second person "
            f"to a machine somebody is already at."
        )

    differences = [
        name
        for name, a, b in (
            ("equipment", left.equipment_key, right.equipment_key),
            ("fault label", left.fault_label, right.fault_label),
            ("day", left.day.isoformat(), right.day.isoformat()),
            ("kind", left.kind.value, right.kind.value),
        )
        if a != b
    ]
    return False, (
        f"different jobs — they differ by {', '.join(differences)}. Refusing the second as a "
        f"duplicate would mean nobody goes, and a suppressed job leaves no trace anywhere."
    )
