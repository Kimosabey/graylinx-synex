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

**This is now confirmed on our own data rather than merely plausible.** In the measured
window `dpt` and `chiller_flow` are the same column to the digit — identical zero counts
(23,795 on chiller 1, 26,629 on chiller 2), identical maxima (107.0 and 112.9) and
identical distinct-value counts. So `chiller_flow = 1.0 × dpt + 0.0` **holds wherever
the data is real**, and breaks only where the data was generated. Someone with access to
the live feed should still confirm it there, but the derivation is not the thing that
changed.

Two other things the measured window shows, both of which the honesty features exist for:

| Observed | Why it matters |
|---|---|
| `cond_leaving_temp` reaches **&minus;273.2** on both chillers | Absolute zero as a sensor sentinel. A physically impossible reading that `F16` must reject rather than average into a residual |
| `kw_per_tr` ranges **&minus;6,265 to +30,183** on chiller 1 | Efficiency computed while flow is near zero. `C21` and `F16` exist for exactly this; a report that quotes it as a number is worse than one that refuses |
| ~23,800 of 31,884 slots are zero across every signal at once | The machine is **off**, not broken. Roughly a 25% duty cycle, and the gates must read it as off — a "fault" on a stopped chiller is the commonest false positive available |

---

## 4a. What is demonstrable — the fault inventory in the measured window

The engine's output already exists for the real window, so a demonstration does not have
to stage a single fault. `gla_model_residuals_wc` carries six residual columns and a
label per slot:

| `fault_label` | Slots |
|---|--:|
| `NO_DIAGNOSIS` | **5,309** |
| `NO_EFFICIENCY_FAULT` | 943 |
| `HIGH_HEAD_AMBIGUOUS` | 430 |
| `REFRIGERANT_SIDE_HIGH_HEAD` | 104 |
| `COMPRESSOR_INEFFICIENCY` | 58 |
| `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION` | 32 |
| `CONDENSER_WATER_SIDE_UNSPECIFIED` | 25 |
| `POWER_HIGH_UNEXPLAINED` | 22 |
| `CONDENSER_LOW_FLOW` — the only `critical` class | 3 |
| unlabelled | 7,662 |

**All seven model fault classes are present on measured data.** So is the only `critical`
one.

And note the top row. `NO_DIAGNOSIS` is the most common labelled outcome by a wide
margin — 5,309 slots. The honest refusal is not a contrived demonstration case to be
apologised for; it is what the platform genuinely does most, on real readings. That makes
it the strongest asset in this database rather than a caveat.

## 4b. Coverage — twelve equipment tables, two with any model

The scope argument for "one asset class, done completely" is measurable rather than
rhetorical:

| | Count |
|---|--:|
| Normalized equipment tables holding telemetry | **12** |
| …with fitted model parameters | **2** |
| …with residual reference bands | **2** |
| …with residuals ever scored | **2** |

The two are `chiller_1_normalized` and `chiller_2_normalized`. Three condenser pumps,
three cooling towers, three primary pumps and `plant_normalized` all carry telemetry and
have **no** model, **no** band and **no** scored residual.

`gla_residual_stats_wc` is ten rows — five residuals for each of the two chillers. So a
rule that refuses to score equipment with no reference band is not defensive coding; it is
the difference between two machines and twelve.

## 4c. Model fit — why per-asset bands and one severity are not optional

`gla_equipment_model_metrics`, ten rows, five models per chiller:

| Equipment | Model | nRMSE |
|---|---|--:|
| chiller_1 | Chiller_Current | **48.03** |
| chiller_1 | Discharge_Temp | 36.41 |
| chiller_1 | Suction_Pres | 7.93 |
| chiller_1 | Discharge_Pres | 5.38 |
| chiller_1 | Condenser_Leav_Temp | 2.95 |
| chiller_2 | Suction_Pres | 3.77 |
| chiller_2 | Discharge_Temp | 3.41 |
| chiller_2 | Discharge_Pres | 2.90 |
| chiller_2 | Chiller_Current | **2.65** |
| chiller_2 | Condenser_Leav_Temp | 1.68 |

Three things follow.

**Five models exist per chiller, not six.** There is no compressor-power model, and
`compressor_power_residual` is 100% NULL in the residuals table. The six-model
description in `CONTEXT.md` §6 is the design; five is what is fitted.

**The same model is eighteen times worse on one machine than the other** — chiller_1's
current model at nRMSE 48.03 against chiller_2's 2.65. An identical fault label on the two
machines does not mean the same thing, which is `F10` and `F15` earning their place from
measurement rather than argument.

**Ignore MAPE.** It reads 2,931,599 and 12,202,370 on three of the ten rows, because the
denominator approaches zero. A figure that large is not a bad score, it is a meaningless
one, and `C21` says it must be shown as a stated absence rather than as a number.

Severity, for its own part, is **not stored anywhere** — `gla_model_residuals_wc` has
`equipment`, `slot_time`, six residuals and `fault_label`, and no severity column. So
`F17` (one severity scale) is a code-discipline rule, not a data fix.

## 4d. One problem, many labels — the case-inflation measurement

Counted over the measured window, excluding `NO_DIAGNOSIS` and `NO_EFFICIENCY_FAULT`:

| | |
|---|--:|
| Fault days | **12** |
| Equipment-days carrying a fault | **12** |
| **Naive cases** — one per (equipment, day, label) | **39** |
| Faulted slots | 674 |

**A 3.25× inflation**, and the concentration is worse than the ratio suggests:

| Date | Equipment | Labels held **at once** |
|---|---|--:|
| 2026-04-15 | chiller 1 | **5** — `CONDENSER_LOW_FLOW`, `HIGH_HEAD_AMBIGUOUS`, `POWER_HIGH_UNEXPLAINED`, `REFRIGERANT_SIDE_HIGH_HEAD`, `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION` |
| 2026-04-17 | chiller 1 | **5** |
| 2026-04-18 · 04-19 | chiller 1 | 4 each |
| 2026-04-12 | chiller 2 | 4 |

**Ten of chiller 1's twelve fault days carry more than one label.** A fouled condenser
plausibly explains four of the five on 15 April simultaneously, so the honest case count
for that day is one and the naive count is five — five work orders, five visits, five
checklist runs against one repair.

### What the same data says about the other grouping cases

**Intermittency is real.** `HIGH_HEAD_AMBIGUOUS` on chiller 1 spans 2026-04-09 to
2026-04-22 across ten days and 412 slots — it clears and returns rather than persisting.
So "is this one case reopened or a new case?" is not hypothetical.

**Cross-equipment correlation is not demonstrable here.** There are **zero** slots where
both chillers carried a fault simultaneously. A cooling tower starving both machines is a
genuine production risk and this window cannot show it, which is why `RC19` scopes to a
single equipment and the cross-equipment case stays with the Alerts domain.

Recorded as D-011. `RC19` is the feature; `G5` does **not** cover it — `G5` stops a retry
creating a second work order, not two genuinely distinct cases about one physical problem
each raising one.

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
