# Running Synex on your machine

Verified on 2026-08-25 by starting every one of these from cold. Where a number appears here it
was read off the running system, not remembered.

> **Do this before reading anything else.** Reading about a system you cannot see running is far
> harder than reading about one you can click through, and Synex has enough moving parts that
> the diagrams only click once the thing is on screen.

---

## What has to be running, and what breaks if it is not

Five things. Only two of them are yours to start each morning.

| Piece | Where | Started by | If it is missing |
|---|---|---|---|
| **Plant MySQL** | `127.0.0.1:3307`, database `graylinx_synex` | already running | Nothing works. Every answer is a refusal about the plant being unreachable. |
| **Postgres + pgvector** | `127.0.0.1:5443` (`synex-postgres`) | Docker, already up | Cases, work orders and the document library are gone. Answers still work, thinner. |
| **Redis** | `127.0.0.1:6381` (`synex-redis`) | Docker, already up | Idempotency falls back to memory. The platform says so rather than hiding it. |
| **The Jarvis tunnel** | `127.0.0.1:11500` → the GPU box | **you** | **The dangerous one — see below.** |
| **The backend** | `127.0.0.1:8001` | **you** | The web app shows a degraded banner on every page. |
| **The frontend** | `127.0.0.1:3000` | **you** | No UI. The API still answers `curl`. |

**Starting the containers on a fresh clone.** They are not running until you start them:

```powershell
docker compose -f infra\docker-compose.yml up -d
docker ps --filter "name=synex" --format "{{.Names}} → {{.Ports}}"
```

**And the one file a clone does not give you.** `backend/.env` is gitignored because it carries
the plant credentials. `backend/.env.example` is tracked and is the template — copy it and get
the real values from Harshan:

```powershell
cd backend
copy .env.example .env
```

Everything else a clone needs is tracked: `requirements.txt`, `package-lock.json`,
`importlinter.ini`, `pytest.ini`, the compose file and the tunnel keeper.

---

## The tunnel, and why it gets its own section

The models run on a rented GPU box ("Jarvis"). An SSH tunnel forwards `127.0.0.1:11500` on your
machine to Ollama on the box.

**When that tunnel dies, nothing looks broken.** The local port stays bound for a while, the
health endpoint keeps answering, and every model call falls back to the deterministic rendering
— which is exactly what the product is designed to do for a box that is not there. What you see
is *"Language model · not used"* on every answer and no error anywhere.

It died three times in one working day. Once it cost a whole evaluation run whose model-written
count fell from 12 of 31 to 5, **without a single test failing**.

So do not run a bare `ssh -L`. Run the keeper, in its own terminal, and leave it:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jarvis_tunnel.ps1
```

It probes *through* the tunnel rather than at it, reopens on failure, and does not spin when the
box is genuinely off. It survives your laptop sleeping, which a bare tunnel does not.

**The remote port is 6006, not 11434.** A rebuilt box comes up with `OLLAMA_HOST=0.0.0.0:6006`.
Forwarding to 11434 opens the local listener and then refuses every connection through it — so
`netstat` shows LISTENING while nothing works. The keeper already has the right port; this is
only here so the failure is recognisable if you ever tunnel by hand.

---

## Starting it

Three terminals. Keep them separate — the backend dying takes any running evaluation with it,
and you want to see which one stopped.

**Terminal 1 — the tunnel keeper** (above).

**Terminal 2 — the backend:**

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Add `--reload` while you are editing, but know what it costs: the reloader runs a parent and a
child, and killing the parent can leave the child holding port 8001. That child answers requests
and is invisible to `Get-Process`, so `taskkill` reports "process not found" while the port is
plainly in use. If that happens, find the real one:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'multiprocessing-fork' } |
  Select-Object ProcessId, CommandLine
```

**Terminal 3 — the web app:**

```powershell
cd apps\web
npm run dev
```

---

## Confirming it is actually live

```powershell
(Invoke-RestMethod http://127.0.0.1:8001/api/v1/health) |
  Select-Object model_mode, box_reachable, box_host
```

You want:

```
model_mode     : live
box_reachable  : True
box_host       : http://127.0.0.1:11500
```

`box_reachable` is a **probe**, not a setting. `model_mode: live` only says what this process
was told to do; `box_reachable: True` says the box answered when asked. Both matter, and the app
bar reads *"model box unreachable"* rather than *"live model"* when they disagree.

Then open `http://127.0.0.1:3000` and ask the Copilot *"what equipment do we have?"*. The answer
should carry a badge reading **Language model · wrote the wording**. If it says *not used*, the
tunnel is down — check terminal 1.

---

## Running the tests

The offline suite needs **nothing** — no database, no GPU, no tunnel. That is deliberate:

```powershell
cd backend
python -m pytest
```

3,682 tests, about 22 seconds. `tests/conftest.py` pins `SYNEX_MODEL_MODE=stub` so a bare
`pytest` never reaches for the box. The application default is `live` — turning the models off
is something you do, not something you inherit.

The other three gates, all of which must pass before a change is done:

```powershell
python -m ruff check app tests          # style
lint-imports --config importlinter.ini  # 7 architectural contracts
cd .. ; python scripts\verify.py        # naming law, banned phrases, feature IDs
```

The import contracts are worth knowing before you write anything: `app.tools` may not import a
database driver, `app.api` may not either, `app.domain` imports nothing, and only `app.llm` may
import a model client. They will catch you, and the message tells you which line broke which
rule.

---

## The live evaluation, which does need everything

```powershell
python scripts\eval_copilot.py --one-persona     # 40 hand-written cases
python scripts\eval_generated.py --record        # 147 cases generated from the plant
```

Two things to know before you run these:

1. **Do not restart the backend while one is running.** It dies with an `httpx.ReadError` that
   looks like a product failure and is not. This happened twice in one day, both times self-
   inflicted.
2. **`--record` appends failures to `eval-flywheel.txt`.** That file is a work list: each line is
   a question the product got wrong, waiting for somebody to write a real case with a real
   expectation. It is how the suite stops only containing questions its author thought of.

---

## Versions

| | Verified 2026-08-25 |
|---|---|
| Python | 3.12.3 |
| Node | v22.22.3 |
| Backend source | 122 files under `backend/app` |
| Web source | 54 files under `apps/web` |
| Offline tests | 3,682 passing |

---

Next: **[02-the-copilot-end-to-end.md](02-the-copilot-end-to-end.md)** — what actually happens
between somebody typing a question and an answer appearing.
