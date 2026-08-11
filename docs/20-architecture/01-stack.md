# The stack — what is inherited, what is decided, and what we refuse to add

Read against `CONTEXT.md` §9 (what Synex stands on) and §10 (inherited constraints).
Everything here was read out of the Thermynx repository's own dependency files and
compose file on 2026-08-11, with the reasoning those files record. Where a choice has a
reason attached, the reason is quoted rather than paraphrased — D-003 says these are
inherited, not re-litigated, and a reason is the only thing that makes that safe.

**Everything is OSI open source and free.** One licence needs a note; see §6.

---

## 1. Runtime — already chosen, nothing to decide

| Package | Why it is there |
|---|---|
| `fastapi` · `uvicorn[standard]` | The service |
| `sqlalchemy[asyncio]` · `aiomysql` · `asyncpg` | Two stores, two drivers — MySQL for the plant, Postgres for ours |
| `alembic` | Migrations on our own schema |
| `redis` · **`arq`** | Async task queue. **This is the scheduler `RC17` needs — it already exists** |
| `pgvector` | Vector search inside the Postgres we already run |
| `numpy` · **`statsmodels`** | The six FDD regressions and their residuals |
| **`sqlglot`** | *"NL→SQL AST validation — parse + structurally verify the generated SELECT"* |
| `slowapi` | Rate limiting |
| `prometheus-fastapi-instrumentator` | `/metrics`, always exposed |
| `pypdf` · `python-multipart` | Document intake |
| `slack-sdk` | Notification route |

### `arq` is the whole of `RC17`

Worth stating plainly, because it changes the size of the feature. The Thermynx failure
that produced `RC17` — 22 detected episodes, including the only two `critical`, never
reaching the queue — was **not** a missing scheduler. `arq` was installed. Nothing
pointed it at the seeding call. So `RC17` is a scheduled job and a visible counter, not a
component.

### The generated SQL is verified, not trusted

`sqlglot` earns its own paragraph because it is the strongest single answer to *"you are
letting a language model write SQL against the plant database"*. Four independent layers,
read out of `nl_to_sql.py`:

1. The statement must **parse** as exactly one statement.
2. The AST root must be `exp.Query` — a `SELECT` or a read-only set operation. `Insert`,
   `Update`, `Delete`, `Drop`, `Create` and friends are rejected by **class**, not by
   keyword.
3. A token deny-list rejects `load`, `outfile`, `infile`, `into outfile`,
   `into dumpfile` — so the file-write forms of `SELECT` are blocked as well.
4. Tables are checked against an allow-list, and a narrow column deny-list catches the
   common hallucinations.

This is genuinely good, and §2 of `02-deployment.md` explains why it should nonetheless
not be the only thing standing there.

---

## 2. Agentic — the orchestration spine

| Package | Why |
|---|---|
| `langgraph` 1.2.4 · `langchain-core` 1.4.3 | StateGraph, checkpointer, streaming, tool primitives |
| `langchain-ollama` 1.1.0 | `ChatOllama`, per-task model routing — keeps inference on Ollama |
| **`langgraph-checkpoint-postgres`** | Durable graph state, so human-in-the-loop interrupt and resume **survive a restart** and are shared across workers |
| LlamaIndex (`core`, `llms-ollama`, `embeddings-ollama`, `vector-stores-postgres`) | RAG over the existing pgvector rather than a new store |
| **`docling`** | PDF, table and **scanned** manual ingestion |
| **`flashrank`** | CPU cross-encoder rerank after pgvector top-k — *"never a new LLM hop"* |

`flashrank` deserves the emphasis. Reranking is the obvious place to reach for another
model call; doing it on CPU in milliseconds instead keeps the turn budget intact and the
GPU free for the roster.

---

## 3. Evaluation — decided, with one framework actively rejected

### DeepEval — chosen

`deepeval>=1.0`, Apache-2.0, **with a local Ollama judge**. It lives in the dev
requirements and is deliberately **not shipped in the production image** — *"keeps the
runtime lean"*. Plus `pytest` and `pytest-asyncio` for the golden and unit suites,
`locust` for load, `ruff` for lint.

The pattern worth copying exactly: a stronger cloud judge exists as an option,
`anthropic>=0.69`, lazy-imported, and it is pointed **only at the synthetic golden set**.

> *"Off by default → zero egress, never installed in the runtime image."*

So a hard case can be judged well without any plant data leaving the site. That is the
on-premise constraint honoured rather than worked around.

### Ragas — removed, and must not be re-added

Not "not chosen". Tried, then taken out on 2026-06-10, quoted in full because the reason
is the important part:

> *"ragas — REMOVED: incompatible with the langchain 1.x / langgraph stack. ragas 0.4.3
> hard-imports `langchain_community…ChatVertexAI` (removed in langchain 1.x), and pinning
> langchain-community low enough to restore it breaks langgraph 1.x. The local LLM-judge
> gives grounding/faithfulness framework-free. **This is the ADR-0001 framework-churn
> risk, realized. Do not re-add without a stack bump.**"*

### What no framework gives us

`EV3` (dimensions no overall score may trade away) and `EV4` (the evaluation's own tests,
fed deliberately dishonest inputs) are custom logic. So is the separation law — nothing
off the shelf checks that the fault name came from the rules rather than from the model.
Those stay ours.

---

## 4. Observability — provisioned, and opt-in

`prometheus-fastapi-instrumentator` is a **runtime** dependency, so `/metrics` is always
exposed. The collectors are containers behind a compose profile:

`prometheus` · `alertmanager` · `loki` · `promtail` · `grafana`

All behind `profiles: [obs]`, which means **nothing scrapes the endpoint unless that
profile is started**. That is a memory decision on a 48 GB box, and it is the same
reasoning that keeps Langfuse switched off.

### Langfuse — integrated, then deliberately disabled

> *"NOT used by the product today; DISABLED on purpose. The Langfuse server is commented
> out in docker-compose.yml and `graph_callbacks()` is a no-op while `LANGFUSE_HOST` is
> empty, so the SDK is never imported. Left UNINSTALLED so it isn't pulled into builds.
> Re-enable ONLY IF tracing is wanted later: stand up the v3 server (langfuse-web +
> worker + clickhouse + redis + minio)… Must stay v4 SDK (OTEL) — v2/v3 are incompatible
> with langchain 1.x."*

Five extra containers for tracing. For an on-premise product that is five more things a
customer's IT has to accept, patch and back up. Prometheus and Loki answer the same
question at a fraction of the cost.

### What our counters should measure

Generic HTTP metrics come free with the instrumentator and are not the interesting part.
The counters worth adding are the ones that measure **the product's own claims**:

- grounded-answer rate
- `NO_DIAGNOSIS` count, broken down by **which gate failed**
- refusal reasons
- tool timeout and schema-failure rate

Those are the evidence that the honesty rules fired. `EV1`–`EV4` fail the build; nothing
currently watches the running system, and for a demonstration those numbers *are* the
argument. See Q43.

---

## 5. Frontend — already equipped

`react` 19 · `vite` 8 · `typescript` 6 · **`echarts` 6 + `echarts-for-react`** ·
`tailwindcss` 4 + `shadcn` + `radix-ui` · `framer-motion` · `lucide-react` ·
**`react-markdown` + `remark-gfm`** · `react-router-dom` 7 · `sonner`

Testing: `vitest` · `@testing-library/react` · `jsdom` · `@playwright/test` ·
**`@axe-core/playwright`**

Two of these close gaps we would otherwise have opened:

- **`echarts` means `C24` has its charting library already.** Apache-2.0, and it handles
  the long five-minute-slot series that a lighter library would choke on.
- **`@axe-core/playwright` means the accessibility work is testable in CI** rather than
  by eye, which matters given the design system was built to WCAG 2.2 and audited at 72
  of 72 pairs.

---

## 6. Licences

Everything is MIT, Apache-2.0 or BSD except one, and Thermynx already reasoned about it:

> `psycopg[binary,pool]` — *"LGPL-3.0 — used unmodified via import (no license obligation
> for internal on-prem use); binary = prebuilt wheels"*

Note also that two Postgres drivers are present, `asyncpg` for the application and
`psycopg3` for the LangGraph checkpointer. Same database, different clients — deliberate,
not duplication.

---

## 7. What we refuse to add

Refusals belong in a stack document, because the pressure to add is constant and the
reason is always plausible in the moment.

| Refused | Why |
|---|---|
| `scikit-learn` | The six models are OLS. `statsmodels` and `numpy` already do it, and the fit metrics are four lines of arithmetic. Adding an ML framework to compute an RMSE is how a stack starts drifting |
| Ragas | ADR-0001, proven. See §3 |
| Langfuse | Five containers for tracing two stacks already answer. See §4 |
| Parallel multi-agent | Concurrency breaks attribution — *"which agent said this"* must have exactly one answer. Phase 2 |
| Anything replacing Ollama | The roster must fit one card, and inference stays on infrastructure we control |
| Vision / P&ID OCR | Shipped there once and **parked** — OCR on drawings and P&IDs proved unreliable in practice. We have no vision feature, and that is now evidence-backed rather than accidental |

---

## 8. The only genuine gap: identity

There is **no authentication library in the backend at all** — no `pyjwt`, no `passlib`,
no `authlib`. And in the snapshot, `gl_user`, `gl_role` and `gl_access` all hold **zero
rows**, so identity is not in the plant data either.

Meanwhile `G1` — identity and scope per turn — is `P0` in the cut, and the Control Plane
cannot grant a scope it cannot establish.

Three routes, all free:

| Route | When |
|---|---|
| `pyjwt` (MIT) + `passlib[bcrypt]` (BSD) | Self-contained demonstration, four personas |
| A signed header from the host platform | The D-006-consistent production route: Synex is a layer, identity belongs to Graylinx. Needs a stub issuer to demonstrate |
| `authlib` (BSD) | OIDC against the customer's own identity provider. Phase 2 |

This is the one place a runtime dependency should be added, and it needs a decision
rather than a default. Recorded as **Q41**.
