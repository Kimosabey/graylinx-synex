# 28. Enterprise Architecture — High Level

| **Layer** | **Name** | **Primary responsibility** |
|---|---|---|
| **Layer 0** | Physical / OT | Equipment, sensors, PLC, BMS, SCADA and field environment |
| **Layer 1** | Connectivity / Integration | Gateways, protocols, APIs, CMMS/ERP/BMS integrations |
| **Layer 2** | Data / Digital Twin | Telemetry, asset hierarchy, master data, quality, lineage |
| **Layer 3** | Equipment ML | Existing models, health, anomaly, degradation, residuals |
| **Layer 4** | FDD / Reliability | Operating gates, persistence, volatility, trends, deterministic fault evidence |
| **Layer 5** | Knowledge / RAG | SOPs, manuals, historical WOs, verified cases, customer account-scoped retrieval |
| **Layer 6** | Agentic Intelligence | Copilot, orchestrator, specialized agents, task planning |
| **Layer 7** | AI Control Plane | Identity, scope, risk, rule, safety, approval, tools, evidence, audit |
| **Layer 8** | Execution / Enterprise | WO/CMMS, scheduling, inventory, procurement, notifications, reports |
| **Layer 9** | Verification / Learning | Post-work evidence, outcome, feedback, controlled learning, ROI |
| **Cross-cutting** | Security / Governance | Zero Trust, privacy, resilience, compliance, supply chain and lifecycle governance |

## 28.1 High-level product flow

USER → REPORTS / WOs / COPILOT → CONTROL PLANE → AGENTS → TOOLS → ML/FDD/RAG/DATA → EVIDENCE → POLICY/APPROVAL → EXECUTION → VERIFICATION → AUDIT → OUTCOME
