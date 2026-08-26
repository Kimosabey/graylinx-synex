# Setup from zero — clone to a working Copilot

One pass, in order, on a machine with nothing installed. Every command was run on 2026-08-25;
where a number appears it was read off the running system.

Roughly 90 minutes, most of it waiting for installs and a 91 MB restore.

**Nine steps. Do not skip 6** — it is the one that fails silently.

---

## 0 · What Harshan sends you, out of band

Three things. Not in the repository, not in the same message.

| | Size | |
|---|---|---|
| `synex-dumps-2026-08-25.zip` | **7.7 MB** | **use this one** — the 14 tables Synex reads, plus the state database |
| `graylinx_synex-full-2026-08-25.zip` | 126 MB | the whole 194-table database, if you ever need a table Synex does not read |
| The `.env` values | a few lines | MySQL credentials and the box address — **sent separately** |

**Start with the small one.** It restores in a couple of minutes and contains everything the
product actually reads. The full dump is 1.96 GB unzipped and takes far longer; keep it, but do
not restore it to get started.

---

## 1 · Prerequisites

| | Version used | Check |
|---|---|---|
| Python | 3.12.3 | `python --version` |
| Node | v22.22.3 | `node --version` |
| Docker Desktop | any current | `docker ps` |
| MySQL Server | 8.0 | needed for `mysql` and `mysqldump` on PATH |
| Git | any current | `git --version` |

A different patch version of Python or Node is fine. A different *major* version is not — 3.11
will fail on syntax used throughout.

---

## 2 · Clone

```powershell
git clone https://github.com/Kimosabey/graylinx-synex.git
cd graylinx-synex\Synex
```

---

## 3 · Install

```powershell
cd backend
pip install -r requirements.txt

cd ..\apps\web
npm install
cd ..\..
```

---

## 4 · Prove the code arrived intact — before any data

```powershell
cd backend
python -m pytest
```

**3,682 passing, about 22 seconds.** This needs no database, no GPU and no tunnel — that is
deliberate, and it means a failure here is a broken install rather than missing data.

If it needs any of those to pass, something is wired wrong. Say so rather than starting services
until it goes green.

---

## 5 · The two databases

### 5a · Containers

```powershell
docker compose -f infra\docker-compose.yml up -d
docker ps --filter "name=synex" --format "{{.Names}} → {{.Ports}}"
```

Expect `synex-postgres` on 5443 and `synex-redis` on 6381.

### 5b · The plant — MySQL on 3307

Unzip first, then:

```powershell
mysql -h 127.0.0.1 -P 3307 -u root -p -e "CREATE DATABASE IF NOT EXISTS graylinx_synex;"
mysql -h 127.0.0.1 -P 3307 -u root -p graylinx_synex < synex-plant-2026-08-25.sql
```

A couple of minutes for 91 MB. Then the read-only user:

```sql
CREATE USER 'synex_plant_ro'@'%' IDENTIFIED BY '<pick one>';
GRANT SELECT ON graylinx_synex.* TO 'synex_plant_ro'@'%';
FLUSH PRIVILEGES;
```

**`SELECT` and nothing else.** That grant is the second lock behind `sql_guard`. Widening it to
make something work removes a defence rather than fixing a bug.

Verify 14 tables:

```powershell
mysql -h 127.0.0.1 -P 3307 -u root -p -e "USE graylinx_synex; SHOW TABLES;"
```

### 5c · The state — Postgres

```powershell
Get-Content synex-state-2026-08-25.sql | docker exec -i synex-postgres psql -U synex -d synex
```

Verify by **counting rows**, not by reading an estimate:

```powershell
docker exec synex-postgres psql -U synex -d synex -tAc `
  "SELECT count(*) FROM synex_document_chunk WHERE is_approved;"
```

**Expect 269.** `pg_stat_user_tables` reports 0 on a fresh restore until autovacuum runs — that
reading has already caused one wrong conclusion that the store was empty.

### 5d · DBeaver, so you can look at it

Not required to run Synex, and you will want it within a day. Two connections.

**MySQL — the plant**

| | |
|---|---|
| Host / Port | `127.0.0.1` / **3307** |
| Database | `graylinx_synex` |
| User | `synex_plant_ro` — **connect as this, not as root** |
| Driver | MySQL 8 |

Use the read-only user in DBeaver deliberately. It is the same grant the application holds, so
a query you write in a GUI cannot do something the product could not — and an accidental
`UPDATE` in a scratch tab fails instead of quietly changing the plant.

Two queries worth running the moment it connects, because they orient you faster than the
schema does:

```sql
-- the measured window, and what sits past it
SELECT MIN(slot_time), MAX(slot_time),
       SUM(slot_time <= '2026-06-23 11:50:00') AS measured,
       SUM(slot_time >  '2026-06-23 11:50:00') AS past_window
FROM chiller_1_normalized;

-- what the trained model actually found, which is the whole product
SELECT fault_label, COUNT(*) AS slots
FROM gla_model_residuals_wc
WHERE fault_label IS NOT NULL
GROUP BY fault_label ORDER BY slots DESC;
```

**PostgreSQL — the state**

| | |
|---|---|
| Host / Port | `127.0.0.1` / **5443** |
| Database | `synex` |
| User / Password | `synex` / `dev` |
| Driver | PostgreSQL |

```sql
-- the library the Copilot cites; expect 269
SELECT count(*) FILTER (WHERE is_approved) AS approved, count(*) AS total
FROM synex_document_chunk;
```

> **Watch the port.** Thermynx is on 3306/5442 and Synex on **3307/5443**. Two connections a
> digit apart is exactly the mistake that produces five confusing minutes — name them
> `SYNEX-mysql` and `SYNEX-postgres` in DBeaver rather than leaving the defaults.

---

## 6 · The tunnel to the GPU box — **the step that fails silently**

```powershell
copy backend\.env.example backend\.env
notepad backend\.env
```

Fill the MySQL block with your `synex_plant_ro` password, set `SYNEX_MODEL_MODE=live`, and put
in the box address Harshan gives you.

Then, **in its own terminal, and leave it running:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jarvis_tunnel.ps1
```

**Read this before you skip it.** When the tunnel dies, nothing looks broken: the local port
stays bound, `/health` keeps answering, and every model call falls back to the deterministic
rendering — exactly what the product is designed to do for a box that is not there. The only
symptom is *"Language model · not used"* on every answer.

It died three times in one working day here. Once it cost a whole evaluation run whose
model-written count fell from 12 of 31 to 5, **without a single test failing**.

The keeper probes *through* the tunnel rather than at it, reopens on failure, and survives your
laptop sleeping. A bare `ssh -L` does none of that.

> The remote port is **6006**, not 11434. Forwarding to 11434 opens the local listener and then
> refuses every connection through it, so `netstat` shows LISTENING while nothing works.

---

## 7 · Start the app

Two more terminals.

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

```powershell
cd apps\web
npm run dev
```

---

## 8 · Confirm it is actually working

```powershell
(Invoke-RestMethod http://127.0.0.1:8001/api/v1/health) |
  Select-Object model_mode, box_reachable
(Invoke-RestMethod http://127.0.0.1:8001/api/v1/health).plant_database
```

Want: `model_mode: live`, `box_reachable: True`, `connected: true`.

`box_reachable` is a **probe**, not a setting. `model_mode` says what this process was told to
do; `box_reachable` says the box answered when asked.

---

## 9 · The four checks that catch a half-finished setup

Open `http://127.0.0.1:3000` and ask, in order:

| Ask | Expect | If it fails |
|---|---|---|
| *What equipment do we have?* | 12 machines, 2 judgeable | the plant dump did not restore |
| — the badge on that answer | **Language model · wrote the wording** | the tunnel is down — step 6 |
| *What does HIGH_HEAD_AMBIGUOUS mean?* | an answer **with a `[citation]`** | the Postgres dump did not restore |
| *What is the capital of France?* | refused, and Paris never appears | something is very wrong; stop and ask |

**The third is the one that matters most.** The first two can pass with an empty document
library, and retrieval failing looks exactly like the Copilot choosing not to cite anything.

---

## When something is wrong

| Symptom | Cause |
|---|---|
| every answer says *"language model · not used"* | the tunnel — step 6 |
| every answer refuses, mentioning the plant | MySQL not restored, or the grant is missing |
| answers work but never cite a source | Postgres not restored |
| `pytest` fails before any data exists | a broken install — do not add data to fix it |
| port 8001 in use, `taskkill` says no such process | an orphaned `--reload` child; see `01-running-synex.md` |

---

## Next

`02-the-copilot-end-to-end.md`, then `03-known-issues-and-landmines.md` before you change
anything in the AI code. `05-one-week-plan.md` has the week, and the scope boundary it opens
with is the important part.
