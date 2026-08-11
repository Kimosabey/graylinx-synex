# The Synex data model — what is in `graylinx_synex`, and what is not

Measured against the live database on 2026-08-11. Every figure here came from a
query, not from a document. Where this contradicts a Thermynx source document, the
contradiction is stated rather than smoothed over.

Related: `CONTEXT.md` §9 (what Synex stands on), §10a (what the reference plant's
data says), decisions D-005 and D-009.

---

## 1. The lineage — three generations, on purpose

| Database | Tables | Size | Role |
|---|--:|--:|---|
| `shiva` | 191 | 3,834 MB | The customer's snapshot as delivered. **Read-only.** |
| `graylinx_v2` | 193 | 3,866 MB | A writable working copy, in active use by Thermynx. |
| `graylinx_synex` | 193 | 3,879 MB | **Ours.** Cloned from the working copy. Synex writes here and nowhere else. |

The reason for a third generation is the reason there was a second: staging demo
scenarios is exactly the kind of work that must not disturb a copy somebody else is
using. It costs about 4 GB of disk.

The size differences are index statistics rather than content.

### The clone is exact — every table, not a sample

Re-verified on 2026-08-11 by counting every row in every table of all three
databases, rather than the largest eight:

| Comparison | Result |
|---|---|
| Tables in `graylinx_v2` but not in `graylinx_synex` | **0** |
| Tables in `graylinx_synex` but not in `graylinx_v2` | **0** |
| Per-table row counts, `graylinx_v2` vs `graylinx_synex` | **identical on all 193** |
| Total rows | **14,271,741 in both** |
| Views, routines, triggers | none in any of the three, so nothing to miss |

So `graylinx_synex` holds everything `graylinx_v2` holds, exactly.

### Against `shiva`, it is a superset — and nothing real was disturbed

| | |
|---|--:|
| Tables in `shiva` but not in `graylinx_synex` | **0** |
| Tables `graylinx_synex` adds | 2 — `snapshot_simulated_slots`, `snapshot_simulation_log` |
| Rows `graylinx_synex` adds | **313,424** |

Every added row is accounted for: 12 equipment tables gained 12,529 slots each
(150,348), `gla_model_residuals_wc` gained 6,946 scored rows, and the two registry
tables hold 156,129 and 1.

The important check is the boundary. **Zero registry entries fall at or before
2026-06-23 11:50**, and the simulation log records `gaps_filled=False`. The
simulation appended; it did not overwrite or backfill a single measured slot. That is
what makes the measured window trustworthy as a demonstration window.

`snapshot_simulation_log` also records the choices made:
`condenser labels=stored-convention · dpt=NULL · tr=flow*dt*0.33 · gaps_filled=False`.
Note what is *not* in that line: it discloses setting `dpt` to NULL and says nothing
about supplying `cond_flow`, which is the one signal the plant has never measured.
A simulation's own log being silent about its most consequential choice is the reason
§4 was measured rather than read.

---

## 2. What this database is — and the thing most likely to be assumed wrongly

**`graylinx_synex` is the plant snapshot. It is not the application database.**

Four tables that a reader would reasonably expect are simply absent:

| Expected | Reality |
|---|---|
| `fault_cases` | **absent** — the case lifecycle is Synex's own state |
| `work_orders` | **absent** — same |
| `equipment` | **absent** — no single asset master; see §3 |
| `anomalies` | **absent** |

This is not a defect in the clone; those tables never existed in the MySQL snapshot.
They confirm the split the architecture already draws: **MySQL holds the plant,
PostgreSQL holds Synex's own state** — threads, cases, work orders, evidence packs,
the audit trail and embeddings. Anything that reasons about a case is reading
PostgreSQL; anything that reasons about the plant is reading MySQL.

---

## 3. How the 193 tables are shaped

Most of the volume is per-equipment time series, with equipment identity encoded in
the **table name** rather than in a column:

| Group | Tables | Approx. rows | Size | What it is |
|---|--:|--:|--:|---|
| `ahu_*` | 48 | 7.4 M | 1,999 MB | Air handling units |
| `em_*` | 14 | 1.9 M | 565 MB | Energy meters |
| `ct_*` | 6 | 1.8 M | 508 MB | Cooling towers |
| `ch_*` | 4 | 1.2 M | 367 MB | Chillers, raw |
| `pv_*`, `coh_*`, `condpu_*`, `hf_*` | 20 | 1.0 M | 292 MB | Solar, coils, condenser pumps, heat flow |
| `chiller_*` | 12 | 160 k | 30 MB | **The normalised chiller tables the FDD engine reads** |
| `gl_*` | 37 | 3.3 k | 1 MB | Platform master data — locations, subsystems, parameters, alarms |
| `gla_*` | 4 | 22 k | 2 MB | Model residuals and their statistics |
| `snapshot_*` | 2 | 156 k | <1 MB | **The simulated-slot registry** |

The largest single table is `ct_0002b70000_om_p` at 672,702 rows and 191 MB.

### The tables the MVP actually depends on

| Table | Rows | Why it matters |
|---|--:|---|
| `chiller_1_normalized` | 44,413 | The first vertical. One row per five-minute slot, 32 numeric signals |
| `chiller_2_normalized` | 44,413 | The second machine |
| `plant_normalized` | 44,413 | Plant-level context, including ambient |
| `gla_model_residuals_wc` | 21,534 | What the six models produced — the FDD engine's own output |
| `gla_residual_stats_wc` | 10 | The platform's own residual thresholds, per signal |
| `gla_equipment_model_params` | 60 | The fitted model coefficients |
| `gla_equipment_model_metrics` | 10 | Fit quality per model |
| `gl_alarm` | 948 | The existing alarm records |
| `gl_subsystem` | 891 | The nearest thing to an asset master |
| `gl_parameter` | 454 | Signal definitions |
| `asset_health_daily` | 1,232 | Daily availability per asset |
| `snapshot_simulated_slots` | 156,129 | Which slots are synthetic |

`gl_*` is mostly empty — 24 of its 37 tables hold zero rows, including
`gl_user`, `gl_role` and `gl_access`. **Identity and permission data is not in this
snapshot**, which is worth knowing before assuming the Control Plane can read roles
from it.

---

## 4. The simulated window — and the one signal that was invented

The registry `snapshot_simulated_slots` has two columns, `equipment varchar(64)` and
`slot_time datetime`, and names **156,129** synthetic pairs: 12,529 slots each for
twelve equipment tables — both chillers, three condenser pumps, three cooling towers,
three primary pumps and `plant_normalized` — plus 5,781 distinct slots on
`gla_model_residuals_wc`, which carries several rows per slot and so contributes 6,946
rows from those 5,781 marks.

| | |
|---|---|
| Real data | 2026-03-04 18:55 → **2026-06-23 11:50** — 31,884 slots per chiller |
| Simulated | 2026-06-23 11:55 → **2026-08-05 23:55** — 12,529 slots per chiller |

Every numeric column on `chiller_1_normalized` was compared across the two windows.
Of 32 columns, **exactly one behaves differently in kind**:

| Signal | Real window | Simulated window | Reading |
|---|--:|--:|---|
| `cond_flow` | **0 non-zero, max 0.0** | 3,354 non-zero, **max 893.7** | **Invented.** The plant has never measured it; the simulation supplies it |
| `dpt` | 8,089 non-zero | **0** | Dropped by the simulation |
| everything else | populated | populated proportionally | continued, not invented |

`chiller_2_normalized` matches: zero real non-zero `cond_flow`, and 3,592 synthetic
values reaching 1,099.6.

### Why this is the most important fact in this document

Condenser flow is the signal `CONTEXT.md` §6 calls the highest-leverage single
measurement — **four of the six models depend on it**, and answering *"flow is at
design"* eliminates three of five causes in the
`CONDENSER_WATER_SIDE_UNSPECIFIED` differential.

So the one signal that decides the most is the one signal our database has
fabricated. A demonstration run on the most recent data — the natural choice, since
it runs to five days ago — would show condenser flow reading healthily, the models
resolving cleanly, and the differential narrowing with confidence, **on a
measurement the reference plant cannot take at all.**

This is not a hypothetical about disclosure. Marking the window *simulated* does not
fix it, because the problem is not that the numbers are synthetic — it is that they
imply an **instrumentation capability the site does not have**. Every other synthetic
signal continues something the plant genuinely measures. This one does not.

The constraint that follows is in D-009.

### A side effect worth reporting upstream

Thermynx's own discovery raised its question A-11 — *"what feeds `chiller_flow` now
that `dpt` is NULL?"*, recorded as verified finding VF4 — the documented derivation
`chiller_flow = 1.0 × dpt + 0.0` no longer holding.

The measurement above offers a simpler explanation than an upstream change: in the
simulated window `dpt` is absent and `chiller_flow` is synthesised directly, so the
derivation is not broken — it is **not being applied, because that window was
generated rather than measured.** Their observation was made on data running through
August, which is inside the simulated span.

This is a candidate explanation, not a confirmed one — it needs someone with access
to the live feed to check. But it is cheap to check and it would retire a platform
question.

---

## 5. What Synex writes, and where

| Written by Synex | Store | Note |
|---|---|---|
| Threads, turns, evidence packs | PostgreSQL | Never MySQL |
| Cases and their findings | PostgreSQL | `RC1`–`RC18` |
| Work orders | PostgreSQL | `W1`–`W4`, `W8`–`W10` |
| Verification results | PostgreSQL | `V1`–`V4`, `V6` |
| Audit trail | PostgreSQL | `G6`, append-only |
| Embeddings | PostgreSQL + pgvector | 768-dim, always local |
| **Nothing** | MySQL | Read-only in practice, even though we own the copy |

Treating the plant snapshot as read-only is a choice rather than a permission: it
means a demonstration can be reset by dropping Synex's own state, and the plant data
never needs restoring.

---

## 6. How to re-run this analysis

The clone script and the analysis both connect using the Thermynx backend's `.env`
credentials. MySQL is on **port 3307**, not 3306 — the service is `MySQL80_1`.

```sql
-- the real/simulated split for any signal
SELECT CASE WHEN s.slot_time IS NULL THEN 'REAL' ELSE 'SIMULATED' END AS origin,
       COUNT(*) AS slots,
       SUM(c.cond_flow <> 0) AS nonzero,
       MAX(c.cond_flow) AS max_val
FROM chiller_1_normalized c
LEFT JOIN snapshot_simulated_slots s
  ON s.equipment = 'chiller_1_normalized' AND s.slot_time = c.slot_time
GROUP BY origin;
```

Any signal can be substituted for `cond_flow`. Before building a demonstration on a
window, run this for every signal that demonstration depends on.
