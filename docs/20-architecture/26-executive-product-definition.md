# 26. Executive Product Definition

| **THE PRODUCT IN ONE LINE Graylinx is an AI-native maintenance and reliability platform centered on Reports, Work Orders and an Synex Copilot, using existing equipment intelligence to turn evidence into controlled action and verified outcomes.** |
|---|

## 26.1 Priority hierarchy

| **Priority** | **What belongs here** | **Purpose** |
|---|---|---|
| **P0 — Core product** | 📊 Reports; 🔧 Work Orders; 🤖 Synex Copilot | What customers directly use and value. |
| **P0 — Trust foundation** | AI Control Plane; Identity; Scope; Policy; Safety; Approval; Evidence; Audit | What makes the core product safe and enterprise-grade. |
| **P1 — Intelligence foundation** | Existing ML; FDD; RAG; Asset hierarchy; Data quality | Makes the core experiences intelligent and grounded. |
| **P1 — Execution support** | Planning; Scheduling; Inventory; People; Notifications; Integrations | Makes WOs and decisions executable. |
| P2 — Advanced features | Voice, vision, deeper autonomy, advanced optimization | Add only when a measurable business case exists. |

| **KEY PRODUCT PRINCIPLE Do not let 'AI that can plan and use tools AI' become the product. Agentic AI is the execution mechanism underneath the three core customer experiences.** |
|---|

## 26.2 High-level to low-level design

| **Level** | **Question answered** | **Typical artifacts** |
|---|---|---|
| **Level 0 — Business** | Why does Graylinx exist? | Objectives, value proposition, ROI |
| **Level 1 — Product** | What do users experience? | Reports, WOs, Copilot, menus, user roles |
| **Level 2 — Workflow** | How does a job move end-to-end? | Journey maps, workflow/state diagrams |
| **Level 3 — Architecture** | What components make it work? | Layered architecture, service boundaries |
| **Level 4 — Control** | Who/what is allowed to act? | RBAC/ABAC, rule, risk, approval, safety |
| **Level 5 — Engineering** | How exactly is it implemented? | API/tool contracts, schemas, state machines |
| **Level 6 — Verification** | How do we prove it works? | validation, test matrix, service targets, audit evidence |
