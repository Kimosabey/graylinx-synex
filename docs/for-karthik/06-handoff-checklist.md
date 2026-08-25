# Access and handoff checklist

What Karthik needs, who grants it, and how to prove each one works. Tick the verification, not
the request — "access requested" is not access.

---

## Accounts and access — two phases, deliberately

**Phase 1, from day one: clone and work.** Karthik gets an account from Harshan and starts on
Harshan's access. Nothing is migrated yet. The point of this phase is that he is productive on
day one rather than blocked on provisioning.

**Phase 2, later: everything moves to his own accounts.** Repository, GPU box, databases,
cloud — all of it transfers to Karthik's own credentials once he is running. Plan for this from
the start, because two things break at the moment of transfer and both are quiet.

| What | Phase 1 | Verified by | What Phase 2 needs |
|---|---|---|---|
| Repository — `graylinx-synex` | Harshan's account | `git clone`, `git log` shows recent commits | his own account added as a collaborator, then `git remote set-url` |
| Repository — `thermynx` | Harshan's account | needed for the reference docs Synex cites | same |
| SSH key on the Jarvis box | Harshan's key | `ssh -o BatchMode=yes root@<box> "ollama --version"` answers with no password | **his own key added to `authorized_keys` before Harshan's is removed** |
| Plant MySQL | Harshan's credentials | `/api/v1/health` → `plant_database.connected: true` | his own `synex_plant_ro` grant — **read-only, and it stays read-only** |
| Postgres + Redis | local Docker | `docker ps --filter "name=synex"` | nothing; they are local containers |
| `backend/.env` | **not in git** — Harshan sends it | `SYNEX_MODEL_MODE=live` and the MySQL block present | rewritten with his own credentials, never copied |

### The two quiet failures at transfer

**The SSH key.** Add Karthik's key and confirm *he* can reach the box before Harshan's is
removed. If the order slips, the tunnel stops — and when the tunnel stops nothing looks broken:
the port stays bound, `/health` keeps answering, and every model call falls back exactly as
designed for a box that is not there. The only visible symptom is *"Language model · not used"*
on every answer. See `03-known-issues-and-landmines.md`.

**The database grant.** `synex_plant_ro` holds two grants and cannot write. When the credentials
change, the new user needs **the same** grant — not a broader one because it was quicker. The
read-only grant is the second lock behind the SQL guard, and a defence that exists once is a
defence that fails once.

**`.env` is gitignored deliberately.** It carries plant credentials. Do not commit it, do not
paste it into a chat, and at transfer **write a fresh one** rather than copying Harshan's — a
copied `.env` is how one person's credentials end up on two machines with nobody tracking it.

---

## Machine setup

| Step | Verified by |
|---|---|
| Python 3.12.3 | `python --version` |
| Node v22.22.3 | `node --version` |
| `pip install -r backend/requirements.txt` | `python -m pytest` — 3,682 pass |
| `npm install` in `apps/web` | `npm run dev` serves on :3000 |
| Docker running | `docker ps --filter "name=synex"` shows two healthy containers |
| Tunnel keeper starts | `/api/v1/health` shows `box_reachable: True` |

**The real test of a working machine** is `python -m pytest` passing with no database, no
tunnel and no GPU. If that needs any of them, something is wired wrong — say so rather than
starting the services to make it pass.

---

## Knowledge handover — the conversations, not the documents

Each of these is a sitting with Harshan. The documents support them; they do not replace them.

| Topic | Why it needs a person |
|---|---|
| **The separation law** | `CONTEXT.md` §5 states it. *Why* it is absolute, and what happened the two times it was nearly relaxed, is verbal. |
| **Which open questions are genuinely blocking** | `decisions/OPEN-QUESTIONS.md` has 86. Five block work. The file does not rank them. |
| **N1 — Synex and Thermynx** | The documents contradict each other. Get the current answer directly. |
| **The Vishnu relationship** | What he has agreed, what he has not, and what has been asked twice. `mvp/ASK-VISHNU.md` is the current ask. |
| **The demo narrative** | Which questions to ask in which order, and which currently answer badly. |

---

## What is running where

| Piece | Address | Owner |
|---|---|---|
| Plant MySQL | `127.0.0.1:3307` / `graylinx_synex` | shared with Thermynx — **read-only by grant** (`synex_plant_ro`) |
| Postgres + pgvector | `127.0.0.1:5443` (`synex-postgres`) | Synex only |
| Redis | `127.0.0.1:6381` (`synex-redis`) | Synex only |
| Jarvis GPU box | tunnel `127.0.0.1:11500` → box `:6006` | rented, shared |
| Backend | `127.0.0.1:8001` | local |
| Web | `127.0.0.1:3000` | local |

**The plant database is shared with Thermynx and Synex's grant cannot write.** That is the second
lock, not the only one — the SQL guard is the first. Do not widen the grant to make something
work; the refusal is the design.

---

## State on handover — 2026-08-25

| | |
|---|---|
| Offline tests | 3,682 passing |
| Import contracts | 7 kept, 0 broken |
| `scripts/verify.py` | PASSED |
| Hand-written live sweep | 31/31 clean, three axes at zero failures |
| Generated live sweep | **84 of 147 clean — never completed** (see below) |
| Model roster | four models, all four with real consumers |

**The one number not to over-report.** The 147-case generated sweep has never finished. Two runs
died to infrastructure — one to a self-inflicted backend restart, one to the backend process
dropping. The highest clean count is 84. Report it as an unfinished measurement, because that is
what it is.

---

## Known gaps, stated plainly

**Blocked on Vishnu, and larger than everything else combined**

The 19 discriminators are authored and unreviewed, so `askable` returns nothing and every
differential reports `EXHAUSTED` by construction. Hypothesise mode works and currently says *"no
check has been reviewed"* every time. One hour of a refrigeration engineer's time turns that into
the product's signature. `mvp/ASK-VISHNU.md` has been sent.

Also his: Q3's load-floor denominator (30% *of what*), and whether the flow signal is usable at
all or a dead transmitter and a constant.

**Ours**

- Interview mode — the fourth answer mode — is not built.
- Retrieval relevance is not measured.
- Multi-turn behaviour is not measured against a live model.
- The flywheel records failures and nothing reads them back.
- Checklist content is sample content and every surface says so. The curated library is the
  bigger SME job and has not been asked for yet.

---

## Before Harshan is unavailable

- [ ] Karthik has started every service himself, from cold, without help
- [ ] Karthik has run all four offline gates
- [ ] Karthik has run one live sweep and read the output
- [ ] Karthik has shipped one change end to end — flywheel entry → failing case → fix → gates
- [ ] The five blocking open questions have been named out loud
- [ ] `HANDOFF.md` is current — it is the first thing the next session reads
- [ ] Any assumption Karthik is carrying is written down, not remembered
- [ ] **Phase 2 is scheduled** — the account transfer has a date, not an intention. The SSH key
      goes on the box before Harshan's comes off, and the new database user gets the same
      read-only grant rather than a wider one.

---

## The two rules worth repeating on the way out

**The language model never diagnoses.** ML says abnormal, rules name the fault, a formula sets
priority, the Control Plane grants permission. The model explains. If a change would move any of
those four into the model, it is not allowed.

**Never invent a number.** Every figure is a real value or an explicitly stated absence. Never
neither, never both. If a number is needed and unavailable: `TBD (see Qn)`, and add the question
to `decisions/OPEN-QUESTIONS.md`.
