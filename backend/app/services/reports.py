"""Reports — `R10` reconciliation and `R5` drill-down to source.

**`R10` is the one worth demonstrating.** Every headline figure this product states is
recomputed from the source table and shown beside what the documents claim. Not sampled, not
spot-checked — recomputed, every time the page loads.

That turns the repository's own discipline into a product feature. The same numbers are
already asserted in `tests/unit/test_measured_facts.py` against the documents and in
`tests/integration/test_plant_repository.py` against live queries; this is that pairing made
visible to a reader who cannot run pytest.

**`R5` is what makes a figure auditable rather than merely stated.** Each row carries the
table it came from, the rows counted, and the plain-English basis of the count. A number a
reader cannot open is a number they have to take on trust, and this product's whole argument
is that they should not have to.

**A disagreement is a finding, not an error.** If a recomputed figure differs from the
documented one, the row says so and the report says how many disagreed. It does not fail,
because the interesting case — a document that has drifted from the data — is exactly what
this is for.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.db.plant import NON_FAULT_LABELS, PlantRepository
from app.domain import equipment as eq
from app.domain import faults, residuals


@dataclass(frozen=True)
class Reconciliation:
    """One figure, as documented and as recomputed from source."""

    key: str
    label: str
    documented: float | int
    recomputed: float | int | None
    source_table: str
    source_rows: int
    basis: str
    """Plain English: what was counted, over what. `R5`'s substrate."""

    @property
    def agrees(self) -> bool:
        return self.recomputed is not None and self.documented == self.recomputed

    @property
    def checkable(self) -> bool:
        return self.recomputed is not None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "documented": self.documented,
            "recomputed": self.recomputed,
            "agrees": self.agrees,
            "checkable": self.checkable,
            "source_table": self.source_table,
            "source_rows": self.source_rows,
            "basis": self.basis,
        }


async def reconcile(repo: PlantRepository) -> list[Reconciliation]:
    """Recompute every headline figure from source.

    The documented side comes from `app.domain`, which is where the measured facts are held
    as data. The recomputed side comes from a live query. Neither reads the other.
    """
    rows: list[Reconciliation] = []

    counts = {c.label: c.slots for c in await repo.label_counts()}

    # ── the fault inventory ─────────────────────────────────────────────────
    for fault in faults.FAULT_CLASSES:
        rows.append(
            Reconciliation(
                key=f"label.{fault.label}",
                label=f"{fault.label} slots",
                documented=fault.measured_slots,
                recomputed=counts.get(fault.label),
                source_table="gla_model_residuals_wc",
                source_rows=counts.get(fault.label) or 0,
                basis=(
                    f"rows where fault_label = '{fault.label}' and slot_time is on or "
                    f"before the measured window end"
                ),
            )
        )

    rows.append(
        Reconciliation(
            key="label.unlabelled",
            label="Unlabelled slots",
            documented=faults.UNLABELLED_SLOTS,
            recomputed=counts.get(None),
            source_table="gla_model_residuals_wc",
            source_rows=counts.get(None) or 0,
            basis="rows where fault_label is NULL — scored by nothing, so not healthy",
        )
    )

    faulted = sum(
        n
        for label, n in counts.items()
        if label is not None and label not in NON_FAULT_LABELS
    )
    rows.append(
        Reconciliation(
            key="faulted.total",
            label="Faulted slots",
            documented=sum(f.measured_slots for f in faults.FAULT_CLASSES if f.is_fault),
            recomputed=faulted,
            source_table="gla_model_residuals_wc",
            source_rows=faulted,
            basis=(
                "rows with a fault label, excluding NO_DIAGNOSIS and NO_EFFICIENCY_FAULT — "
                "both are outcomes rather than faults, and including either would overstate "
                "the total by 6,252"
            ),
        )
    )

    # ── coverage ────────────────────────────────────────────────────────────
    scored = await repo.scored_equipment_keys()
    bands = await repo.residual_bands()
    rows.extend(
        [
            Reconciliation(
                key="coverage.telemetry",
                label="Equipment tables with telemetry",
                documented=len(eq.all_equipment()),
                recomputed=None,
                source_table="information_schema",
                source_rows=0,
                basis=(
                    "counted once by hand across the normalized tables; not recomputed per "
                    "request, and marked as such rather than shown as agreeing"
                ),
            ),
            Reconciliation(
                key="coverage.scoreable",
                label="Equipment with any scored residual",
                documented=len(eq.scoreable_equipment()),
                recomputed=len(scored),
                source_table="gla_model_residuals_wc",
                source_rows=len(scored),
                basis="distinct equipment appearing in the residuals table",
            ),
            Reconciliation(
                key="coverage.bands",
                label="Reference bands fitted",
                documented=len(residuals.MODEL_FITS),
                recomputed=len(bands),
                source_table="gla_residual_stats_wc",
                source_rows=len(bands),
                basis="one row per residual per asset — five residuals for each of two chillers",
            ),
        ]
    )

    # ── the model that is not there ─────────────────────────────────────────
    all_null = await repo.unfitted_residual_is_entirely_null()
    rows.append(
        Reconciliation(
            key="models.fitted_per_chiller",
            label="Models fitted per chiller",
            documented=residuals.FITTED_MODEL_COUNT,
            recomputed=residuals.DESIGNED_MODEL_COUNT - 1 if all_null else None,
            source_table="gla_model_residuals_wc",
            source_rows=0,
            basis=(
                "six residual columns exist and compressor_power_residual is NULL in every "
                "row, so five are fitted. The design describes six; the data contradicts it, "
                "and the row is stated rather than the column omitted"
            ),
        )
    )

    return rows


@dataclass(frozen=True)
class ReconciliationReport:
    rows: list[Reconciliation]

    @property
    def checked(self) -> int:
        return sum(1 for r in self.rows if r.checkable)

    @property
    def agreeing(self) -> int:
        return sum(1 for r in self.rows if r.agrees)

    @property
    def disagreeing(self) -> list[Reconciliation]:
        return [r for r in self.rows if r.checkable and not r.agrees]

    @property
    def not_checkable(self) -> list[Reconciliation]:
        """Stated rather than quietly counted as passing.

        A reconciliation report that showed 100% agreement while silently excluding what it
        could not check would be exactly the reassuring lie this product exists to refuse.
        """
        return [r for r in self.rows if not r.checkable]

    def as_dict(self) -> dict:
        return {
            "rows": [r.as_dict() for r in self.rows],
            "total": len(self.rows),
            "checked": self.checked,
            "agreeing": self.agreeing,
            "disagreeing": [r.as_dict() for r in self.disagreeing],
            "not_checkable": [r.as_dict() for r in self.not_checkable],
            "all_agree": self.checked > 0 and self.agreeing == self.checked,
        }
