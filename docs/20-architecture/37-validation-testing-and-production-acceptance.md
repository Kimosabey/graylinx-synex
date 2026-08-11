# 37. Validation, Testing and Production Acceptance

10/10 architecture requires proof, not only documentation.

| **Test area** | **Example acceptance test** |
|---|---|
| **Authorization** | Unallowed asset request returns DENY with zero data leakage |
| **Tool security** | Unallowed write cannot reach CMMS |
| **Approval** | Critical WO cannot execute without valid approval |
| **Safety** | Safety-critical action cannot bypass safety gate |
| **Prompt injection** | Malicious document cannot change rule/tool authority |
| RAG isolation | Cross-customer account retrieval is blocked |
| **Data quality** | Invalid operating state results in NO_DIAGNOSIS |
| **Idempotency** | Retry after timeout does not duplicate WO |
| **Concurrency** | Conflicting WO updates resolve safely |
| **State machine** | Invalid state transition is rejected |
| **Evidence** | Material suggestion exposes source/version/evidence |
| **Verification** | Failed repair verification reopens/escalates |
| **Audit** | Material action has complete trace |
| **Recovery** | Dependency outage results in defined safe/degraded mode state |
| **Report accuracy** | Reported KPI reconciles with source calculation |

## 37.1 Release gates

| **Gate** | **Required evidence** | **Decision** |
|---|---|---|
| **G0 Design** | Use case, risk, threat model, owners | Proceed / redesign |
| **G1 Data** | Quality, lineage, privacy/security | Proceed / block |
| **G2 AI** | validation, grounding, red-team, evaluation | Approve / reject |
| **G3 Action** | Tool, rule, approval, safety tests | Approve / reject |
| **G4 Production** | service target, audit, rollback, incident plan | Go / no-go |
| **G5 Post-release** | Monitoring, incidents, drift, outcomes | Continue / remediate / rollback |
