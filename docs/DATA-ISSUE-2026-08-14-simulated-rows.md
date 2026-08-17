# ⚠ `graylinx_synex` contains simulated rows, and the honesty layer cannot see them

**Date:** 2026-08-14 · **From:** THERMYNX team · **Applies to:** `graylinx_synex` on MySQL `:3307`
(`backend/app/config.py:63`, `backend/.env:5`)

---

## The short version

`graylinx_synex` is a copy of our `graylinx_v2`. We found that **its newest six weeks are simulated,
not measured** — we had not realised it either. Anything Synex shows for **23-Jun-2026 → 05-Aug-2026**
is built on generated rows.

Worse: **your honesty layer cannot tell.** The marker table exists in your database, but no code reads
it, so `NEVER_MEASURED` and `audit_never_measured` pass on signals that were never actually measured.

---

## What is in your database

| period | what it is |
|---|---|
| 2026-03-04 → 2026-06-23 11:50 | real measured data |
| 2026-06-23 11:55 → 2026-08-05 23:55 | **simulated — 12,529 rows per table, 13 tables** |

Affected: both chillers, three cooling towers, three condenser pumps, three primary pumps,
`plant_normalized`, `gla_model_residuals_wc`.

```sql
SELECT COUNT(*) FROM graylinx_synex.snapshot_simulated_slots;   -- ~156,129
SELECT equipment, COUNT(*), MIN(slot_time), MAX(slot_time)
FROM graylinx_synex.snapshot_simulated_slots GROUP BY equipment;
```

The marker is keyed `(equipment, slot_time)` — it identifies synthetic rows exactly.

---

## Why it matters to your code specifically

You have the same honesty machinery we do:

| your file | what it does |
|---|---|
| `backend/app/analytics/honesty.py:83` | `NEVER_MEASURED` — "no credible value ever recorded" |
| `backend/app/agents/postcheck.py:209` | `audit_never_measured` — blocks quoting a never-measured signal |

Both decide availability **by arithmetic on the column values**. A simulated row carries a plausible
value, so it reads as a measurement. We searched your backend: **no file references
`snapshot_simulated_slots`.**

The concrete consequence, which we hit on our side:

- **`cond_flow` is not measured at this plant at all.** Karthik confirmed on 2026-08-14: the models use
  a constant of 100 and never read the tables. But your `cond_flow` column has non-zero values —
  every one simulated — so `audit_never_measured` sees a healthy signal and passes. Condenser approach
  computed from it is not a measurement.
- **Efficiency.** On our side **46% of the slots behind the headline kW/TR figure were simulated**
  (3,194 of 6,906).

---

## Two more plant facts, true in your data as well

1. **The chilled-water flow transmitter died 2026-04-22 (chiller_1) / 2026-04-16 (chiller_2).** Real
   usable efficiency data ends there. The healthy-looking flow values after that (up to 112) are the
   simulated ones.
2. **`chiller_flow` holds the raw DP reading, not converted flow** — Karthik confirmed the DP→flow
   conversion was never applied, in any copy, for any period. So kW/TR is uncalibrated wherever it is
   computable. Vishnu owes the constant `k` for `Q = k·√ΔP`.

Also, from the same investigation: **`cond_entering_temp` and `cond_leaving_temp` are swapped at
source** — plant-wide the "entering" column reads hotter (33.75) than "leaving" (32.20), which is
backwards. Condenser ΔT is negative until that is fixed upstream.

---

## What we would suggest, in order

**1. Teach the honesty layer to read the marker.** This is the important one and it is small — a
signal's availability check must exclude simulated slots, so a filled column stops reading as a live
instrument.

**2. Then choose what to do about the data:**

- **Exclude simulated rows** — smallest change; your data becomes real but ends 23-Jun.
- **Replace them with real rows** — a newer Shiva dump (`shiva_014_08_2026.zip`, 14-Aug) has **real**
  readings for 18-Jun → 05-Aug, exactly the simulated window. We loaded it as `graylinx_v3` on the same
  MySQL instance — **you can query it directly**, no need to repeat the restore.
- **Do nothing, knowingly** — only if nobody outside the team is looking at June–August figures.

**3. Optionally, fill the post-April gap by derivation.** We derive `tr` from `percent_cooling_load`
(which kept working) using a ratio calibrated per chiller on its own pre-failure data — 1.7174 and
1.7148, two units agreeing to 0.15%. Result lands within 4% of real behaviour, energy-weighted. Script:
`thermynx/backend/scripts/fill_dead_signal_gaps.py`. Every derived row is recorded in
`snapshot_derived_slots` and labelled — **derived** may be quoted, **simulated** may not.

---

## Expect this after fixing — it looks like a regression and is not

- **Recent efficiency figures disappear** rather than change. There is no valid flow reading after
  22-Apr, so kW/TR cannot be computed honestly without the derivation in step 3.
- **Flow charts go flat from April**, because the instrument did.
- Numbers that looked reasonable become "not available".

That is the true state of the plant. The healthy-looking version was generated.

---

Happy to share queries, the derivation script, or walk through any of it. Full analysis:
`thermynx/docs/plan-v4.9.2/db-migration/`.
