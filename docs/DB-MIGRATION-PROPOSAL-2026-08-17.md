# Re-cloning `graylinx_synex` from `graylinx_v2` — proposal

**Task 3. Nothing here has been executed.** Every figure below was measured against the
running MySQL on `:3307` on 2026-08-17, after THERMYNX confirmed the v2 rebuild was settled.

---

## 1 · What `graylinx_v2` now holds — verified, not taken on trust

| | `graylinx_synex` (current) | `graylinx_v2` (rebuilt) |
|---|--:|--:|
| Tables | 193 | **194** |
| `chiller_1_normalized` | 44,413 rows | 44,332 |
| `chiller_2_normalized` | 44,413 rows | 44,333 |
| Span | 2026-03-04 → 2026-08-05 23:55 | 2026-03-04 → 2026-08-05 17:10 |
| `snapshot_simulated_slots` | **156,129 rows** | **0 rows** |
| `snapshot_derived_slots` | absent | **12,589 rows** |
| Residual rows | 21,534 | 18,869 |

THERMYNX's own figures reconcile: 194 tables, 0 simulated, 12,589 derived.

---

## 2 · What would **not** change — and this is the reassuring part

**Every number the test suite asserts is identical inside the measured window.**

| | current | v2 |
|---|--:|--:|
| `NO_DIAGNOSIS` | 5,309 | 5,309 |
| `NO_EFFICIENCY_FAULT` · `HIGH_HEAD_AMBIGUOUS` | 943 · 430 | 943 · 430 |
| `REFRIGERANT_SIDE_HIGH_HEAD` · `COMPRESSOR_INEFFICIENCY` | 104 · 58 | 104 · 58 |
| `STARVED_EVAP…` · `CONDENSER_WATER_SIDE_UNSPECIFIED` | 32 · 25 | 32 · 25 |
| `POWER_HIGH_UNEXPLAINED` · `CONDENSER_LOW_FLOW` | 22 · 3 | 22 · 3 |
| Unlabelled | 7,662 | 7,662 |
| Episodes / equipment-days | 39 / 12 | 39 / 12 |
| Reference bands | 10 | 10 |
| chiller 1 current band | −25.645 [−38.6771, −12.6129] | identical |
| Current-model nRMSE | 48.03 / 2.65 | identical |

All ten labels, the episode arithmetic, every band and every fit are unchanged. **The demo
script, the golden set and the reconciliation report all survive the clone untouched.**

---

## 3 · What **would** break — two things, and the second is the one to think about

### 3a · The sixth model now exists, outside our window

`compressor_power_residual` is **no longer 100% NULL**.

| | non-null | of total |
|---|--:|--:|
| `graylinx_synex` | 0 | 21,534 |
| `graylinx_v2` | **4,281** | 18,869 (77.3% NULL) |

**But every one of those 4,281 values falls after 2026-06-23 14:35 — entirely outside our
measured clip. Zero inside it.**

So the product's *behaviour* is unchanged: within the window we show, the sixth model is
still absent and still renders as *"no model is fitted for this signal"*. What breaks is the
**global** assertion.

Affected, all in `backend/`:

- `app/domain/residuals.py` — `FITTED_MODEL_COUNT = 5`, `ABSENT_RESIDUAL_COLUMN`
- `tests/unit/test_measured_facts.py::test_the_sixth_model_does_not_exist`
- `tests/integration/test_plant_repository.py::test_the_sixth_model_is_entirely_null`
- `app/db/plant.py` — the `UNFITTED_RESIDUAL_COLUMN` docstring
- `CONTEXT.md` §10a and `docs/20-architecture/00-data-model.md` §4c both state "five models
  are fitted, not six"

The honest restatement is narrower and still true: **five models are fitted over the measured
window; a sixth appears only in the derived tail.** That is a documentation change plus two
test edits, not a design change.

### 3b · Derived rows land *inside* our measured window — and nothing labels them

`snapshot_derived_slots` spans **2026-04-16 21:20 → 2026-08-05 17:10**, and **7,670 of its
12,589 rows fall on or before our measured-window end of 2026-06-23 11:50.**

Those slots are inside everything the product currently shows.

Derived is not simulated, and the distinction is real — THERMYNX's rule is *derived may be
quoted, simulated may not*, and the derivation is calibrated per chiller against pre-failure
data. But **our code has no concept of derived at all.** `app/db/provenance.py` reads only
`snapshot_simulated_slots`, so after the clone those 7,670 slots would read as measured with
nothing saying otherwise.

That is a smaller version of the defect we just fixed, arriving through a different door. It
is not a reason to delay the clone — the data is better after it than before — but it is
work that follows the clone rather than optional polish:

1. `ProvenanceRepository` learns `snapshot_derived_slots` the way it learned the simulated
   one: probe once, cache, absent table means nothing is derived.
2. A third `SignalStatus` — `DERIVED` — usable but labelled, sitting between `MEASURED` and
   `SUSPECT`.
3. `Figure` gains a derived provenance so a derived value renders as *"derived from measured
   load"* rather than as a reading.

**Note the interaction with the plant facts.** `chiller_flow` holds raw DP and was never
converted, so kW/TR is uncalibrated wherever it is computable — Vishnu owes `k` for
`Q = k·√ΔP`. A derived efficiency figure would therefore be *derived from an uncalibrated
signal*, which is two qualifications deep. This product does not currently render kW/TR at
all, and until `k` exists that remains the right call.

---

## 4 · The commands — **do not run these without reading §3**

Run from the repository root. `MYSQL_ADMIN_PASSWORD` avoids putting the password in shell
history; `synex_plant_ro` cannot do any of this by design (Q42).

```bash
set MYSQL_ADMIN_PASSWORD=<root password>
set PATH=%PATH%;C:\Program Files\MySQL\MySQL Server 8.0\bin
cd d:\Harshan\graylinx-things\graylinx-synex\Synex
```

**Step 1 — back up what exists.** A file, not a database copy: it survives a bad clone and
costs nothing to keep.

```bash
mysqldump --host=127.0.0.1 --port=3307 --user=root --password=%MYSQL_ADMIN_PASSWORD% ^
  --single-transaction --quick --routines --events ^
  graylinx_synex > backups\graylinx_synex_2026-08-17.sql
```

Check it is not truncated before going further — a dump that failed halfway still exits 0 in
some shells:

```bash
dir backups\graylinx_synex_2026-08-17.sql
findstr /C:"Dump completed" backups\graylinx_synex_2026-08-17.sql
```

**Step 2 — pre-flight, read-only.** Reports the source's row counts, span, marker state and
real `cond_flow` count. Changes nothing.

```bash
python scripts\reclone_plant_db.py --check --from graylinx_v2 --user root
```

**Step 3 — the clone.** Prompts for confirmation, then drops, clones and **re-grants
`synex_plant_ro`** — a `DROP DATABASE` removes that grant along with the schema, and without
the re-grant the back end cannot connect afterwards.

```bash
python scripts\reclone_plant_db.py --from graylinx_v2 --apply --user root
```

**Step 4 — verify against the gate rather than by eye.**

```bash
cd backend
pytest -m requires_box          # 4 live suites; expect the two sixth-model tests to fail
pytest                          # the offline suite must stay green
```

**Rolling back**, if the clone is wrong:

```bash
mysql --host=127.0.0.1 --port=3307 --user=root --password=%MYSQL_ADMIN_PASSWORD% ^
  -e "DROP DATABASE IF EXISTS graylinx_synex; CREATE DATABASE graylinx_synex;"
mysql --host=127.0.0.1 --port=3307 --user=root --password=%MYSQL_ADMIN_PASSWORD% ^
  graylinx_synex < backups\graylinx_synex_2026-08-17.sql
```

---

## 5 · Recommendation

**Clone.** The measured window is byte-identical, so nothing the product currently shows
changes and nothing in the demonstration script moves. What you gain is a database with no
fabricated `cond_flow`, so the honesty layer's verdict stops depending on a date constant
that happens to abut the marker boundary.

Do it **after** the 18th demonstration rather than before, unless the fabricated rows are
going to be discussed in the room. The clone is safe but it is not free: two tests and two
documents need the sixth-model restatement, and the derived-slot work in §3b should follow
soon after rather than be forgotten.

**Not urgent, and worth saying plainly: the clone does not fix `cond_flow`.** It is zero in
all three databases over real slots. The plant does not meter condenser flow — that is
instrumentation, not a data defect, and no restore changes it.
