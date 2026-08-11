# 38. Observability, Service Targets and Operations

| **Domain** | **Measure** |
|---|---|
| **Copilot** | Latency, task success, escalation, grounded answer rate |
| **Agents** | Workflow success, failed trajectories, retries, step count |
| **Tools** | Latency, timeout, schema failure, side-effect success |
| RAG | Retrieval quality, stale-source rate, grounding failures |
| FDD | Diagnosis validity, false positives, NO_DIAGNOSIS correctness |
| **WOs** | SLA, cycle time, backlog, verification pass/reopen |
| **Reports** | Generation success, KPI reconciliation against source |
| **Security** | Unallowed-action block rate, incident MTTR |
| **Control plane** | Policy decision latency, approval latency, audit completeness |
| **Business** | Downtime avoided, MTTR, cost, energy, PM compliance |

## 38.1 Resilience

- Define RTO/RPO for control plane, state, audit and integrations.
- Back up and test restoration.
- Provide read-only/degraded mode behavior when critical dependencies are unavailable.
- Reconcile state before retrying uncertain external writes.
- Support controlled offline field capture where required.
- Have incident containment, rollback and credential/rule revocation procedures.
