# 8. Reports

## 8.1 Report features

| **Feature** | **What it does** | **Example** |
|---|---|---|
| **Executive dashboard** | Enterprise/site health at a glance | “Show top 10 risks this month.” |
| **Asset report** | Health, status, history, criticality | “Give me Chiller-03's last 90 days.” |
| **Reliability report** | FDD, bad actors, repeat faults, degradation | “Which assets have repeated condenser faults?” |
| **Maintenance report** | Backlog, PM, MTTR, SLA, workload | “Show overdue critical WOs by site.” |
| **Energy report** | Consumption, anomalies, savings opportunities | “Which chillers are inefficient?” |
| **Cost report** | Labor, parts, downtime and avoided cost | “What failures cost us most?” |
| **WO report** | Lifecycle and verification performance | “How many WOs were reopened after repair?” |
| **Comparison** | Asset/site/period comparison | “Compare Plant A vs Plant B.” |
| **Drill-down** | KPI → site → system → equipment → sensor/evidence | “Why did availability drop?” |
| **Scheduled report** | Role-aware recurring delivery | Monday reliability summary for managers |
| **AI narrative** | Natural-language explanation over verified metrics | “Summarize the week's maintenance risks.” |
| **Export** | Controlled PDF/CSV/XLSX or approved destinations | Export monthly customer report |

## 8.2 Report workflow — question to evidence

USER QUESTION → RESOLVE PERSONA/SCOPE → IDENTIFY REPORT/KPI → RETRIEVE AUTHORIZED DATA → QUALITY/FRESHNESS CHECK → CALCULATE → RECONCILE → GENERATE VISUAL/NARRATIVE → SHOW EVIDENCE → DRILL-DOWN / EXPORT / ACTION

## 8.3 Report cases

**Case: Executive asks “Are we getting better?”**

Copilot selects executive scope → compares current vs prior period → reports availability, MTTR, downtime, cost and repeat failures → highlights material changes → links to affected sites/assets.

**Case: Manager asks “Why is Plant A worse?”**

Report compares sites → identifies availability/MTTR difference → drills into equipment families → surfaces recurring FDD/WO patterns → offers a ranked action list.

**Case: Customer requests monthly report**

Customer scope is resolved → approved report template runs → metrics are reconciled → narrative is generated from verified values → recipient authorization is checked → report is delivered and audited.

## 8.4 Report scope, controls and governance

Reports are not static exports. They are a role-aware intelligence surface over the enterprise → asset → sensor hierarchy.

| **Report family** | **Examples** | **Primary users** |
|---|---|---|
| **Executive** | Enterprise health, risk, availability, cost, downtime, energy, ROI | CXO / Executive |
| **Operations** | Plant health, production impact, critical assets, alerts | Plant / Operations |
| **Maintenance** | Backlog, PM compliance, MTTR, SLA, technician workload | Maintenance |
| **Reliability** | FDD, bad actors, repeat failures, MTBF, degradation | Reliability |
| **Energy** | Energy performance, anomalies, savings opportunities | Energy |
| **Cost** | Labor, parts, downtime cost, maintenance spend, avoided cost | Finance |
| **WO performance** | Open/closed/overdue, SLA, cycle time, verification | Maintenance / Service |
| **Customer** | Site/asset performance and service outcomes | Customer |
| **AI/ML** | Model/FDD health, drift, evaluation, AI action outcomes | AI/ML / Governance |

### Report controls

- Every report is scoped by customer account → organization → site → asset permissions.
- Metrics must have definitions, source lineage, calculation logic and freshness.
- Exports and scheduled delivery re-check authorization when executed.
- Sensitive data, recipients and external sharing are rule-controlled.
- created by AI narrative must remain distinguishable from verified day-to-day facts.
