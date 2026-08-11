# Executive Summary

Graylinx is an AI-native maintenance and reliability platform for the whole company. Its primary customer experiences are Reports, Work Orders and Synex Copilot. Existing ML and FDD provide equipment intelligence; the AI that can plan and use tools layer turns that intelligence into governed decisions and actions; the Control Plane makes those actions secure, scoped, evidence-based and grounded, approved where required, auditable and verifiable.

**The complete loop:**

SENSE → UNDERSTAND → DIAGNOSE → EXPLAIN → DECIDE → CREATE/EXECUTE WORK → VERIFY → LEARN → REPORT VALUE

High-level architecture defines the platform. Workflows define how users and systems operate it. Low-level contracts define implementation. Validation, service targets, audit and governance prove it works in production.

The target is not maximum autonomy. The target is maximum useful feature under explicit, testable and auditable control.

| **Token** | **HEX** | **Use** | **Guidance** |
|---|---|---|---|
| **Primary — Graylinx Blue** | #2563EB | Primary buttons, links, active navigation, selected states | Use for interactive/product identity, not for alarms. |
| **Primary Dark** | #1D4ED8 | Hover/pressed states, strong headings where needed | Maintain contrast. |
| **Deep Navy** | #0F172A | Top-level text, headers, high-emphasis UI | Main enterprise/technical anchor. |
| **Slate** | #334155 | Secondary text, labels, metadata | Readable supporting information. |
| **Muted Slate** | #64748B | Helper text, timestamps, secondary metadata | Do not use for critical content. |
| **Canvas** | #F8FAFC | Application background | Default light workspace. |
| **Surface** | #FFFFFF | Cards, panels, tables, dialogs | Primary content surface. |
| **Border** | #E2E8F0 | Dividers, card borders, table lines | Keep subtle. |
| **Success** | #16A34A | Healthy, verified, completed, approved | Pair with icon/text. |
| **Warning** | #D97706 | Attention, degraded mode, pending, approaching SLA | Not for hard failure. |
| **Critical / Error** | #DC2626 | Fault, failed, blocked, safety-critical | Use sparingly and consistently. |
| **Info** | #0891B2 | Informational states, guidance, neutral system notices | Use for contextual information. |
| **AI Accent** | #7C3AED | AI/Copilot identity, generated insight markers | Use only to distinguish AI—not as a general status color. |

| **Semantic state** | **Color token** | **Example** | **Always pair with** |
|---|---|---|---|
| **Healthy / Verified** | Success | #16A34A | ✓ icon + text |
| **Attention / Pending** | Warning | #D97706 | ⚠ icon + text |
| **Fault / Failed** | Critical | #DC2626 | ✕ icon + text |
| **Information** | Info | #0891B2 | i icon + text |
| created by AI | AI Accent | #7C3AED | AI badge/icon + label |
| **Neutral / Unknown** | Muted Slate | #64748B | Status text |

| **Component** | **Recommended behavior** | **Example** |
|---|---|---|
| **Global navigation** | Role-aware; show core pillars first | Reports / Work Orders / Copilot / Assets |
| **Synex Copilot** | Persistent but non-intrusive entry point | Ask, explain, investigate, recommend, act |
| **KPI cards** | One metric + status + trend + open more detail | Availability 98.4% ↑ |
| **Asset health card** | Health + risk + evidence + next action | Chiller-03 / High risk / Why? |
| **WO card** | Priority + SLA + assignee + state + verification | Critical / Assigned / Verify |
| **Evidence panel** | Source + timestamp + model/FDD + confidence | Why AI says this |
| **Approval dialog** | Exact action + impact + evidence + approver | Approve WO |
| **Safety gate** | Prominent blocking state when required | Permit required |
| **Report builder** | Role/scope-aware filters + saved views | Plant → Asset → Period |
| **Audit timeline** | Human-readable chronological actions | Who / what / when / why |

| **Level** | **Recommendation** | **Use** |
|---|---|---|
| **Display / Page title** | 28–32 px, semibold/bold | Major page titles |
| **Section heading** | 20–24 px, semibold | Dashboard/report sections |
| **Card heading** | 16–18 px, semibold | Modules and cards |
| **Body** | 14–16 px | Normal application text |
| **Dense table** | 12–14 px | Operational data |
| **Metadata** | 11–12 px | Timestamp/source/secondary data |

| **Persona family** | **Primary UI emphasis** | **Copilot emphasis** |
|---|---|---|
| **Executive** | KPIs, risk, cost, availability, ROI | Explain enterprise performance; drill down |
| **Plant / Operations** | Plant health, production impact, alerts | What needs attention now? |
| **Maintenance** | Backlog, SLA, PM, WOs, people, parts | Prioritize, plan, draft and manage WOs |
| **Technician** | My Work, safety, SOP, findings, parts | Guide the job and verify repair |
| **Reliability** | FDD, bad actors, trends, evidence | Diagnose, compare, investigate |
| **AI/ML / Data** | Model/FDD/RAG quality and evidence | Evaluate and troubleshoot AI |
| **EHS / Compliance** | Safety gates, approvals, audit | Explain rule; never bypass safety |
| **Admin / IT** | Users, roles, integrations, health | Diagnose platform/configuration issues |
| **Customer** | Site performance, WOs, reports | Explain customer assets and service outcomes |

| **Primary #2563EB** | **Navy #0F172A** | **Canvas #F8FAFC** | **Success #16A34A** | **Warning #D97706** | **Critical #DC2626** | **AI #7C3AED** |
|---|---|---|---|---|---|---|
