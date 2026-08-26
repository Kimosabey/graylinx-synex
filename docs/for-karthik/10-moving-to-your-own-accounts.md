# Phase 2 — moving everything onto Karthik's accounts

You start on Harshan's access so you are productive on day one. **Everything then moves onto your
own accounts**, and this is that migration: what moves, in what order, and how to prove each step
before the one that depends on it.

**Do not start this until you have run the product end to end at least once.** Every step below
is verified by the system still working, and you cannot tell a broken migration from a broken
setup if you have never seen it working.

---

## The order, and why it is not arbitrary

Two steps can lock you out if done backwards, and both are marked. Everything else is safe to do
in any order.

| # | What moves | Locks you out if reversed? |
|---|---|---|
| 1 | Repository access | no |
| 2 | **SSH key on the GPU box** | **yes — add before removing** |
| 3 | **The Jarvislabs account** | **yes — it is billed, and terminating loses the box** |
| 4 | Plant MySQL user | no |
| 5 | `backend/.env` | no |
| 6 | Postgres and Redis | nothing to move |

---

## 1 · The repository

Harshan adds your GitHub account as a collaborator on `Kimosabey/graylinx-synex`. Then point
your clone at your own credentials — the URL does not change unless the repository is
transferred outright, which is Harshan's decision rather than yours.

```powershell
git remote -v                    # confirm what you are pointing at
git fetch origin
git log --oneline -1             # you should see the newest commit
git push origin develop          # the real test: can you write?
```

**Verified when you can push.** Read access is not the thing being handed over.

> If the repository is transferred to your account rather than shared, the URL changes and every
> clone needs `git remote set-url origin <new URL>`. GitHub redirects the old URL for a while,
> which is exactly long enough to forget you needed to change it.

---

## 2 · The SSH key on the GPU box — **add before removing**

The box is reached over SSH and the tunnel depends on it. Get this order wrong and the tunnel
stops — **and a stopped tunnel gives no sign at all**: the port stays bound, `/health` keeps
answering, and every model call falls back to the deterministic rendering exactly as designed
for a box that is not there. The only symptom is *"Language model · not used"* on every answer.

**Add yours first:**

```powershell
# on your machine
ssh-keygen -t ed25519 -C "karthik@graylinx"
type $env:USERPROFILE\.ssh\id_ed25519.pub
```

Harshan appends that public key to `~/.ssh/authorized_keys` on the box.

**Prove it is yours that works**, not his still being there:

```powershell
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@<box> "ollama --version"
```

`BatchMode=yes` matters: it refuses to fall back to a password prompt, so a pass here means the
key worked rather than something else did.

**Only then** does Harshan remove his key.

**Verify the whole path afterwards**, not just SSH:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jarvis_tunnel.ps1
(Invoke-RestMethod http://127.0.0.1:8001/api/v1/health).box_reachable
```

Must be `True`. That is a probe through the tunnel rather than a setting.

---

## 3 · The Jarvislabs account — **this one is billed**

The box is a rented Jarvislabs.ai GPU: RTX PRO 6000 Blackwell, 96 GB, India region, roughly
**₹179/hr plus ₹2.84/hr for storage**. It is not free and it is not yours until this step.

This is Harshan's to arrange — a new account under your name, or the existing one transferred.
**Do not create a second box to avoid the conversation.** Two boxes bill twice and the roster
takes ten minutes to pull onto each.

**What you must understand before you own it:**

- **Terminate it when you are done.** It bills by the hour whether or not anything is running.
- **A fresh box wipes `/home`.** The four models re-pull in about ten minutes and the SSH key,
  the Ollama port and everything else come back as defaults — see
  `01-running-synex.md` for what a rebuilt box looks like, including that Ollama comes up on
  **6006** rather than 11434.
- **One box, one roster.** Thermynx uses the same card. If both products want it at once, they
  contend.

**Verified when** you can start and stop the box yourself, and a burst you started answers
`/api/v1/health` with `box_reachable: True`.

---

## 4 · The plant database user

Your own `synex_plant_ro`, with **the same grant**:

```sql
CREATE USER 'synex_plant_ro'@'%' IDENTIFIED BY '<your password>';
GRANT SELECT ON graylinx_synex.* TO 'synex_plant_ro'@'%';
FLUSH PRIVILEGES;
```

**`SELECT` and nothing else, and this is not a formality.** That grant is the second lock behind
`sql_guard` — the first is that the validator refuses anything but a bounded `SELECT`. A defence
that exists once is a defence that fails once. If something does not work and widening the grant
would fix it, you have found a bug rather than a permissions problem.

**Verify both halves — that it reads, and that it cannot write:**

```sql
SELECT COUNT(*) FROM graylinx_synex.chiller_1_normalized;   -- should answer
CREATE TABLE graylinx_synex.zzz_test (id INT);              -- should be REFUSED
```

The second failing is the point. If it succeeds, the grant is too wide.

---

## 5 · `backend/.env` — write it fresh

**Do not copy Harshan's.** A copied `.env` is how one person's credentials end up on two machines
with nobody tracking which. Start from the template:

```powershell
copy backend\.env.example backend\.env
```

Fill in your own MySQL password, `SYNEX_MODEL_MODE=live`, and the box address. It is gitignored —
check that it stays that way:

```powershell
git status --short backend\.env     # must print nothing
```

If it appears there, stop and fix `.gitignore` before committing anything.

---

## 6 · Postgres and Redis — nothing moves

Both are local Docker containers defined in `infra/docker-compose.yml`, with development
credentials in that file. They are yours already. If you rebuild them you lose the state
database, so restore the dump again — `07-data-dumps.md`.

---

## The check that proves the whole migration

Not any single step. Run the product and ask four questions:

| Ask | Proves |
|---|---|
| *What equipment do we have?* | your MySQL user reads the plant |
| — the badge says **Language model · wrote the wording** | your SSH key reaches your box |
| *What does HIGH_HEAD_AMBIGUOUS mean?* — **with a `[citation]`** | Postgres survived |
| `git push origin develop` | your GitHub access writes |

**All four, in one sitting.** Each of the first three can pass while another is silently broken,
and the third is the one people miss — retrieval failing looks exactly like the Copilot choosing
not to cite anything.

---

## If something breaks after Harshan's access is removed

| Symptom | Almost certainly |
|---|---|
| every answer says *"language model · not used"* | your SSH key is not on the box, or the box is terminated |
| `ssh` asks for a password | your key is not in `authorized_keys` — `BatchMode=yes` would have caught this |
| every answer refuses, mentioning the plant | your MySQL user, or the grant |
| answers work but never cite | Postgres, not the migration |
| `git push` rejected | you have read access and not write |

**None of these is data loss.** The dumps are files you hold, the repository is on GitHub, and a
GPU box is disposable by design — a fresh one re-pulls the roster in ten minutes. Nothing here is
worth panicking about; it is worth doing in order.
