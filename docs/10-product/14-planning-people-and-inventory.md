# 14. Planning, People and Inventory

| **Capability** | **Case** | **Workflow** |
|---|---|---|
| **Prioritization** | Many WOs compete for same window | Risk + criticality + SLA + production + parts + skills → ranked queue |
| **Scheduling** | Maintenance window tomorrow | WO duration + asset dependency + production schedule → suggested slot |
| **Assignment** | Need qualified technician | Skills + certification + availability + location → candidates |
| **Parts** | Part not in stock | Required part → stock/ETA → reserve/order/substitute → schedule decision |
| **Vendor/OEM** | Internal team cannot perform work | Qualification + contract + SLA → vendor escalation |
| **Shift handover** | Unfinished critical WO | State + findings + risk → next shift briefing |

## 14.1 Planning example

Three critical WOs compete for one maintenance window. Planning Agent evaluates asset criticality, risk, production impact, technician certification, parts availability and expected duration. It recommends an order; the planner approves; the system schedules and records the decision. The agent cannot override a safety or authorization constraint.

## 14.2 PLANNING, INVENTORY AND ALERT AI

| **Feature** | **Case** | **AI help** |
|---|---|---|
| **Priority ranking** | 30 WOs, 5 technicians | Rank by risk, criticality, SLA, production and dependencies |
| **Schedule suggestion** | Tomorrow has a 4-hour maintenance window | Fit the best WOs into the window |
| **Technician matching** | Need certified HVAC technician | Match skill, certification, location and availability |
| **Parts prediction** | Repeated pump repair | Warn that a common part may be needed |
| **Shortage warning** | Critical WO has no part | Tell planner before scheduling |
| **Alert explanation** | “Why did I get this alert?” | Explain trigger and impact |
| **Alert grouping** | 20 related sensor alerts | Group into one useful event |
| **Escalation** | Critical fault not acknowledged | Route to next responsible person |
