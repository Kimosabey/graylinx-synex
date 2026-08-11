# Deployment — the shape it actually has, and what on-premise still needs

Read out of the Thermynx compose file and dependency notes on 2026-08-11. This existed
nowhere in our documents, and it is the kind of thing that gets rediscovered painfully.

Companion to `01-stack.md`. Graylinx solutions deploy **on-premise**, and every
constraint below follows from that.

---

## 1. Infrastructure in Docker, application on the host

**There is no Dockerfile anywhere in the Thermynx repository.** Every compose service is
a pulled image; none has a `build:` stanza. The backend and frontend run natively —
`uvicorn` and `vite` on the host.

**Always running:**

| Service | Image | Note |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | Postgres **and** pgvector in one image — both stores our architecture needs |
| `redis` | `redis:7-alpine` | Backs `arq`, which is what `RC17` schedules on |
| `redis-commander` | `rediscommander/redis-commander:latest` | A development database UI |

**Behind `profiles: [obs]` — not started by default:**

`prometheus:v2.47.0` · `alertmanager:v0.27.0` · `loki:2.9.0` · `promtail:2.9.0` ·
`grafana:10.0.0`

Named volumes: `postgres_data`, `loki_data`, `grafana_data`, `alertmanager_data`.

**MySQL is not in compose.** It is the existing `MySQL80_1` service on the host, on
**port 3307, not 3306**. That is correct rather than an oversight: the plant snapshot
belongs to the existing platform, and Synex is a layer on it (D-006).

**Ollama is not in compose either.** The roster runs on the rented Jarvis box, reached
over the network. See `CONTEXT.md` §9.

### Two notes on hygiene

`redis-commander` is pinned to `:latest` and is a database UI. Acceptable on a developer's
box; it should not exist in anything shared, and an unpinned tag in an on-premise delivery
is a reproducibility problem in itself.

For our own demonstration the `obs` profile should be **on**. The reason it is off there
is memory on a 48 GB box; we burst a 96 GB box, and the honesty counters in
`01-stack.md` §4 are part of what we are demonstrating.

---

## 2. Database privilege — a promise that should be a guarantee

Measured on 2026-08-11 with `SHOW GRANTS FOR CURRENT_USER()`. The backend connects as
**`root`**, holding on `*.*`:

`SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, SHUTDOWN, PROCESS, FILE, …, SUPER`
— **`WITH GRANT OPTION`**.

All three databases live on that one server, so the reach includes `shiva`, the customer's
snapshot.

Our own documents say *"Synex writes to `graylinx_synex` and nowhere else"* and *"`shiva`
stays read-only"*. Today those sentences describe **intent**. The credentials do not
enforce either one.

The SQL validator described in `01-stack.md` §1 is genuinely thorough — four layers,
including a token deny-list that blocks the `INTO OUTFILE` and `INTO DUMPFILE` forms, so
there is **no live vulnerability here**. The objection is structural rather than a bug
report: a single application-layer guard is the only thing between generated SQL and a
credential that can drop the customer's snapshot, and defence in depth means not relying
on one layer being correct forever.

**The fix is two `GRANT` statements:**

| User | Rights |
|---|---|
| `synex_plant_ro` | `SELECT` on `graylinx_synex.*` — and nothing else, on nothing else |
| `synex_app` | Full rights on the Synex Postgres database; **no MySQL grant at all** |

Then *"Synex never writes to the plant"* is a property of the database rather than a
promise in a document, and a validator bug becomes a failed query instead of a lost
snapshot. It also makes the read-only posture in `00-data-model.md` §5 true by
construction.

This touches a MySQL server Thermynx shares, so it is a decision rather than a
housekeeping task. Recorded as **Q42**.

---

## 3. What on-premise delivery still needs

Neither item blocks the demonstration. Both block handing the product to a customer.

### No application image

The dev requirements say the eval packages are *"NOT shipped in the production image"*,
so an image is **intended** and does not exist. On-premise delivery wants one reproducible
artefact, not an instruction to install a Python version and then `pip install`.

There is a second reason to build it early. D-006 says this MVP exists to be shown, and
then to be deployed. If the demonstration runs from the same artefact a customer would
receive, *"it worked on my machine"* stops being discoverable in front of an audience.

### No offline install path

The requirements plan for this explicitly:

> *"version FLOORS only. Freeze exact `==` pins after `pip install` resolves on the target
> box and build the offline wheel bundle."*

A plant site may have no outbound internet at all. Air-gapped install means:

- pre-built Python wheels for the exact pinned set
- pre-pulled Docker images for every compose service
- **pre-pulled Ollama models** — the Jarvis notes say a fresh box re-pulls the roster in
  about ten minutes, and that assumes bandwidth a plant room may not have

Recorded as **Q43** together with the observability counters, since both are about what
"production" means here.

---

## 4. Summary — what to add for Synex

| | |
|---|---|
| New compose services | **None.** `pgvector/pgvector:pg16` and `redis` cover both stores and the queue |
| Configuration change | Run with the `obs` profile enabled |
| Decisions needed | Identity (Q41) · least-privilege database users (Q42) · application image and offline bundle (Q43) |
| Deliberately unchanged | App on the host, MySQL on 3307, Ollama on the rented box |
