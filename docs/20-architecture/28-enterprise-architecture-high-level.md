# 28. Enterprise Architecture — High Level

| **Layer** | **Name** | **Primary responsibility** |
|---|---|---|
| **L0** | Physical / OT | Equipment, sensors, PLC, BMS, SCADA and field environment |
| **L1** | Connectivity / Integration | Gateways, protocols, APIs, CMMS/ERP/BMS integrations |
| **L2** | Data / Digital Twin | Telemetry, asset hierarchy, master data, quality, lineage |
| **L3** | Equipment ML | Existing models, health, anomaly, degradation, residuals |
| **L4** | FDD / Reliability | Operating gates, persistence, volatility, trends, deterministic fault evidence |
| **L5** | Knowledge / RAG | SOPs, manuals, historical WOs, verified cases, customer account-scoped retrieval |
| **L6** | Agentic Intelligence | Copilot, orchestrator, specialized agents, task planning |
| **L7** | AI Control Plane | Identity, scope, risk, rule, safety, approval, tools, evidence, audit |
| **L8** | Execution / Enterprise | WO/CMMS, scheduling, inventory, procurement, notifications, reports |
| **L9** | Verification / Learning | Post-work evidence, outcome, feedback, controlled learning, ROI |
| **Cross-cutting** | Security / Governance | Zero Trust, privacy, resilience, compliance, supply chain and lifecycle governance |

## 28.1 High-level product flow

USER → REPORTS / WOs / COPILOT → CONTROL PLANE → AGENTS → TOOLS → ML/FDD/RAG/DATA → EVIDENCE → POLICY/APPROVAL → EXECUTION → VERIFICATION → AUDIT → OUTCOME
