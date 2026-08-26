# The data Karthik needs, and how to hand it over

A clone gives him the code and none of the data. Without these he can run the offline suite —
3,682 tests, no database needed — and nothing else. Every live answer needs the plant.

Sizes below were measured on 2026-08-25, not estimated.

---

## What has to be handed over

| # | What | Size | Without it |
|---|---|---|---|
| 1 | **Plant MySQL** — 13 tables | **107 MB** | nothing works; every answer refuses |
| 2 | **Postgres state** — cases, jobs, the document library | **11 MB** | no cases, no work orders, and retrieval cites nothing |
| 3 | **`backend/.env`** | a few lines | the backend cannot reach either database |

Redis holds nothing durable — it is a cache and an idempotency ledger, and it rebuilds itself.
Do not dump it.

---

## 1 · The plant database — 13 tables of 194

**Dump the subset, not the schema.** `graylinx_synex` is 3.9 GB across 194 tables; Synex reads
thirteen of them totalling 107 MB. Handing over the whole thing moves 36× the data for no gain,
and every extra table is one nobody has checked the provenance of.

| Table | Rows | |
|---|---|---|
| `chiller_1_normalized`, `chiller_2_normalized` | ~43,700 each | the two machines that can be judged |
| `plant_normalized` | 43,619 | plant-level readings |
| `cooling_tower_1..3_normalized` | ~44,100 each | telemetry only, no fitted model |
| `condenser_pump_1..3_normalized` | ~44,150 each | as above |
| `primary_pump_1..3_normalized` | ~43,500 each | as above |
| **`gla_model_residuals_wc`** | **19,593** | **the trained model's own verdicts — the most important table here** |

`gla_model_residuals_wc` is Shiva's model output. Synex reads per-slot verdicts from it and
**never re-detects**. It is 2.5 MB and it is the one table the product cannot work without.

**Dump:**

```powershell
mysqldump -h 127.0.0.1 -P 3307 -u <user> -p `
  --single-transaction --no-tablespaces `
  graylinx_synex `
  chiller_1_normalized chiller_2_normalized plant_normalized `
  cooling_tower_1_normalized cooling_tower_2_normalized cooling_tower_3_normalized `
  condenser_pump_1_normalized condenser_pump_2_normalized condenser_pump_3_normalized `
  primary_pump_1_normalized primary_pump_2_normalized primary_pump_3_normalized `
  gla_model_residuals_wc `
  > synex-plant-2026-08-25.sql
```

**Restore, on his machine:**

```powershell
mysql -h 127.0.0.1 -P 3307 -u root -p -e "CREATE DATABASE IF NOT EXISTS graylinx_synex;"
mysql -h 127.0.0.1 -P 3307 -u root -p graylinx_synex < synex-plant-2026-08-25.sql
```

**Then the read-only grant, and it stays read-only:**

```sql
CREATE USER 'synex_plant_ro'@'%' IDENTIFIED BY '<his password>';
GRANT SELECT ON graylinx_synex.* TO 'synex_plant_ro'@'%';
```

`SELECT` and nothing else. That grant is the second lock behind `sql_guard`, and widening it to
make something work removes a defence rather than fixing a bug.

**Verify:**

```powershell
(Invoke-RestMethod http://127.0.0.1:8001/api/v1/health).plant_database
```

`connected: true`, and then ask the Copilot *"what equipment do we have?"* — twelve machines,
two of which can be judged.

---

## 2 · The Postgres state database — 11 MB

Cases, work orders, the audit trail, the graph checkpoints, and **the document library with its
vectors**.

| Table | Rows | |
|---|---|---|
| `synex_document_chunk` | **317**, of which **269 approved** | the library the Copilot cites |
| `synex_chunk_approval_event` | 110 | who approved what, and when |
| `synex_work_order` | 2 | raised during testing |
| `synex_audit` | 1 | append-only |
| `synex_case`, `synex_finding` | 0 | none opened yet |

**The vectors are the reason to dump this rather than re-ingest.** Re-ingesting needs the
embedder running and takes time, and the 110 approval events are a record of human decisions
that re-ingestion would not reproduce. Hand over the dump.

```powershell
docker exec synex-postgres pg_dump -U synex -d synex --no-owner > synex-state-2026-08-25.sql
```

**Restore:**

```powershell
docker compose -f infra\docker-compose.yml up -d
Get-Content synex-state-2026-08-25.sql | docker exec -i synex-postgres psql -U synex -d synex
```

**Verify — count directly, do not trust the estimate:**

```powershell
docker exec synex-postgres psql -U synex -d synex -tAc `
  "SELECT count(*) FROM synex_document_chunk WHERE is_approved;"
```

Expect **269**. `pg_stat_user_tables` will report 0 on a fresh restore because its estimate lags
until autovacuum runs — that reading has already caused one wrong conclusion that the vector
store was empty. Count the rows.

Then ask the Copilot *"what does HIGH_HEAD_AMBIGUOUS mean?"*. The answer should carry a citation
in square brackets. If it does not, retrieval has nothing to retrieve.

---

## 3 · `backend/.env`

Not in git, deliberately — it carries the plant credentials. `backend/.env.example` is tracked
and is the template.

**Send the values out of band, and have him write a fresh file.** Do not send your `.env`: a
copied one is how one person's credentials end up on two machines with nobody tracking it.

What he needs filled: the MySQL block, `SYNEX_MODEL_MODE=live`, and the Ollama host.

---

## Handing it over

Two files and a short list of values:

```
synex-plant-2026-08-25.sql     107 MB
synex-state-2026-08-25.sql      11 MB
.env values                     out of band, not in the same channel
```

**Name the dumps with the date they were taken.** The plant database is a snapshot with a fixed
end — currently 2026-06-23 — and a dump with no date in its name becomes a file nobody can place
against the window an answer claims to cover.

**Do not put either file in the repository.** They are data, not code, and the plant dump is 107
MB of a customer's telemetry.

---

## Verified afterwards

He has it working when all four are true:

- [ ] `python -m pytest` — 3,682 pass (this needs neither dump, and proves the code arrived intact)
- [ ] `/api/v1/health` → `plant_database.connected: true` and `box_reachable: true`
- [ ] `SELECT count(*) FROM synex_document_chunk WHERE is_approved` → **269**
- [ ] *"what does HIGH_HEAD_AMBIGUOUS mean?"* answers **with a citation**

The fourth is the one that catches a half-finished restore: the first three can pass while the
document library is empty, and retrieval failing looks like the Copilot simply choosing not to
cite anything.
