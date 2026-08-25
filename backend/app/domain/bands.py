"""A reference band — one asset's healthy distribution for one residual.

**Why this dataclass is in `domain` and the function that uses it is in `analytics`.**
A band is a *plant fact*: it was fitted from that machine's own history and stored in
`gla_residual_stats_wc`. The repository in `app.db` has to construct one, and `app.analytics`
has to judge against one — and `db` sits *below* `analytics` in the layering law (D-012), so
`db` cannot import from `analytics`. `domain` is the leaf both can reach.

So the split is: the **data** lives here, the **verdict** lives in `app.analytics.bands`.
That is also the honest description of what they are — one is a measurement, the other is a
rule applied to it.

Read from `gla_residual_stats_wc`, which holds exactly ten rows: five residuals for each of
the two chillers, and nothing for the other ten equipment tables.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResidualBand:
    """One asset's healthy spread for one residual.

    The bounds are the **healthy** spread, not a fault threshold: crossing one means
    *unusual for this machine*, which is an input to the isolation path rather than a
    verdict. Severity never comes from how far outside a reading sits — inherited
    constraint 3, because non-faults were measured to deviate more than faults.

    `equipment_key` is the **domain** key (`chiller_1`), never the table name
    (`chiller_1_normalized`). The repository translates on the way in, so database naming
    does not leak upward.
    """

    equipment_key: str
    residual_name: str
    median: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError(
                f"band for {self.equipment_key}/{self.residual_name} has lower "
                f"{self.lower} above upper {self.upper}"
            )

    @property
    def width(self) -> float:
        return self.upper - self.lower
