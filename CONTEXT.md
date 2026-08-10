# CONTEXT.md — What Graylinx Synex is

Everything in this file is settled product truth. If a source document
contradicts it, the source document is out of date — flag it, do not follow it.

---

## 1. Positioning

> **Graylinx Synex — Intelligent Operations, Connected by AI**

**Synex** = Sync + Nexus.

- **Sync** — connects data, people, equipment and workflows
- **Nexus** — the central connection point
- **Synex** — short, modern, AI-native, and not tied to HVAC, FDD or maintenance

The name is deliberately domain-neutral. Nothing in the documentation should
narrow Synex to HVAC. HVAC is the first vertical, not the definition.

## 2. The kingpin

> **Synex Copilot — the intelligent operating layer for Graylinx**

The Copilot is not a feature of the platform. It is how the platform is used.
Every other capability is a skill the Copilot reaches, through the Control
Plane, with evidence and an audit trail.

A user asks in their own words. Synex resolves who they are, what they are
allowed to see, what "this" refers to, what evidence exists, what it means,
what to do next, and — if approved — does it and proves it worked.

```
ASK → UNDERSTAND → FIND DATA → EXPLAIN → RECOMMEND → CREATE/ACT → VERIFY → REPORT → LEARN
```

## 3. The three P0 pillars

| Priority | Pillar | Promise |
|---|---|---|
| P0 | Synex Copilot | One assistant that understands, explains, prepares work and proves the result |
| P0 | Reports | Ask a question, get the answer with the numbers behind it |
| P0 | Work Orders | Work that arrives carrying its own justification and cannot close unproven |

Reports and Work Orders keep their own screens. The Copilot is a third door to
the same capability, not a replacement for the first two.

## 4. The four local models

Do not invent a fifth. Power comes from models + agents + tools + existing
ML/FDD + data + RAG + Control Plane + workflows + verification.

| Model | Size | Env | Role |
|---|---|---|---|
| `gemma4:26b-a4b-it-qat` | ~16 GB | `OLLAMA_MODEL_BRAIN` | Reasoning, final answer |
| `devstral:latest` | ~14 GB | `OLLAMA_MODEL_TOOL` | Tool execution, ReAct loop, read-only NL→SQL |
| `phi4` | 9.1 GB | `OLLAMA_MODEL_TEXT` / `_AUDITOR` / `_RAG` / `_DEFAULT` | Routing, narration, grounding, audit |
| `nomic-embed-text` | 274 MB | — | 768-dim embeddings, always local |

Rules: the brain never calls tools directly; the executor never writes the final
user-facing answer; the auditor must not be the model that wrote the answer;
embeddings never leave the site.

## 5. The separation law

This is the single most important architectural statement in the product.

| Question | Decided by | Never decided by |
|---|---|---|
| Is this reading abnormal? | The ML model, as a residual | Rules or the LLM |
| Is the equipment fit to be judged? | A deterministic gate | ML or the LLM |
| Has the pattern lasted long enough? | A deterministic persistence rule | The LLM |
| Which fault class is this? | The deterministic isolation path | The LLM |
| What does it mean in plain English? | The LLM | — |
| What priority does the work get? | A deterministic formula | The LLM |
| Is this person allowed? | Plain software — the Control Plane | ML or the LLM |
| Did the repair work? | Post-work residuals + a deterministic rule | The closure note or the LLM |

## 6. The FDD engine (first vertical: water-cooled chillers)

Six normal-operation models per chiller. A residual is
`rX(t) = X_actual(t) − X_predicted(t)`.

| Model | Predicts | Inputs | Residual |
|---|---|---|---|
| DP | Discharge pressure | Suction pressure; cooling load; condenser water entry temp; condenser flow; lead/lag | `rDP` |
| SP | Suction pressure | Evaporator leaving; evaporator entry; evaporator flow/DPT; lead/lag | `rSP` |
| DT | Discharge temperature | Suction pressure; discharge pressure; cooling load; condenser water entry temp; condenser flow; lead/lag | `rDT` |
| Power | Chiller amps / power | Evaporator leaving temp; chiller load; condenser water entry temp; condenser flow | `rPwr` |
| Comp Amps | Compressor amps | Suction pressure; discharge pressure; chiller load; lead/lag | `rAmp` |
| Cond Leaving | Condenser water leaving temp | Chiller load; condenser water entry temp; condenser flow; lead/lag | `rCWL` |

Computed: evaporator ΔT, condenser ΔT, and
`efficiency proxy = (condenser ΔT × condenser flow) ÷ (evaporator ΔT × evaporator flow)`.

**Gates — nothing is diagnosed until all pass:** running steady, load above the
model's floor, flows valid, no setpoint change, and the pattern persisted
(20–30 min proposed, unconfirmed — see Q6).

**Isolation path:** `rPwr` high → `rDP` high → `rCWL` high or normal separates
condenser water-side from refrigerant-side high head. Steady drift over weeks =
fouling; spiky/intermittent = low condenser flow. `rDP` normal with `rAmp` high
= compressor inefficiency; `rDP` normal with `rSP` low = starved evaporator.
`rDT` is a **support signal only** and must never be used to separate the
high-head causes.

**Honest ambiguity:** undercharge and restriction/underfeeding stay a combined
label. Overcharge and non-condensables stay a combined label. Do not let any
document imply the platform separates them.

**The dependency that shapes everything:** condenser flow feeds DP, DT, Power
and Cond Leaving — four of the six models. Without a trustworthy condenser flow
signal, the entire efficiency and high-head branch collapses and the correct
output is `NO_DIAGNOSIS` plus a data-quality work order. This is Q1 and it is
the highest-leverage open question in the programme.

## 7. Answer contract

Every Copilot turn ends in exactly one of six states:
`ANSWERED` · `PARTIAL` · `NO_DIAGNOSIS` · `NEEDS_APPROVAL` · `BLOCKED` · `FAILED`.

Confidence uses four words only: **Confirmed**, **Likely**, **Possible**,
**Not enough evidence**.

## 8. What exists today

| Artefact | State | Location |
|---|---|---|
| Product & Architecture Document v4 | 78 pages, 44 chapters, product-first, validated | `docs/00-source/` |
| Feature Review Pack | 9 pages landscape, 85 features, 20 SME questions | `docs/00-source/` |
| WC Chiller FDD specification | Source of section 6 above | `docs/00-source/` |
| Feature register | 85 features, IDs C/R/W/A/F/K/P/I/L/V/U/S/G | `mvp/FEATURE-REGISTER.md` |
| MVP cut | Proposed, not agreed | `mvp/MVP-SCOPE.md` |

## 9. Known constraints

- On-premise by default. Embeddings and inference stay local.
- Agents are read-only with respect to hardware control. No tool issues a
  control command to plant equipment, in any phase.
- Models are fitted per asset, not per fleet. Two identical chillers on one site
  do not share a model.
- The platform must state when it is in degraded mode rather than silently
  substituting a weaker capability.
