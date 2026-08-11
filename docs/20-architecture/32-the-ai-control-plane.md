# 32. The AI Control Plane

This is the governed execution layer between users/Copilot and agents/tools/enterprise systems.

| **Control domain** | **What it enforces** |
|---|---|
| **Identity & RBAC/ABAC** | Who the user/agent is and what scope they possess |
| Tenant / asset scope | Which customer, site, equipment and data may be accessed |
| AI action rule | READ / ANALYZE / RECOMMEND / DRAFT / APPROVE / EXECUTE / VERIFY |
| **Risk engine** | LOW / MEDIUM / HIGH / SAFETY-CRITICAL / SYSTEM-CRITICAL |
| **Approval engine** | Who must approve which action and under what conditions |
| **Safety / permit engine** | SOP, permit, qualification, isolation/LOTO and EHS gates |
| **Agent registry** | Agent purpose, features, tools, boundaries and version |
| **Tool gateway** | Schema validation, authorization, credentials, safe retry without creating duplicates, side effects |
| Evidence / where the information came from | Source, timestamp, model/FDD/rule version, confidence and lineage |
| State / coordination | Durable workflow state, retries, timeouts, recovery |
| **Audit** | Immutable action and decision trail |
| **Observability** | Agent/tool/model/RAG/action/verification metrics |
| **Governance** | Model, prompt, FDD, rule and configuration lifecycle |
| **Resilience** | Backup, recovery, degraded mode and offline field behaviour |
