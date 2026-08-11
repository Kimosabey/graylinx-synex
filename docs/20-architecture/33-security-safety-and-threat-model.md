# 33. Security, Safety and Threat Model

| **Threat** | **Example** | **Primary control** |
|---|---|---|
| **Prompt injection** | Document tells agent to ignore rule | Instruction/data separation + tool rule |
| **Broken access control** | Cross-site/customer query | RBAC/ABAC + tool-side scope |
| **Excessive agency** | Agent closes critical WO | Risk + approval + state rule |
| **Credential abuse** | Agent receives raw CMMS password | Credential broker + short-lived scoped identity |
| **Data leakage** | Sensitive data in report/export | Classification + row/column/scope security |
| **Tool abuse** | Malformed dangerous parameters | Schema validation + allowlists |
| **Data/model poisoning** | Bad equipment readings/knowledge drives decision | Quality + where the information came from + quarantine |
| **Resource exhaustion** | Runaway agent loop | Rate/step/time/token budgets |
| **Audit failure** | Write without trace | Mandatory audit gate |
| **Concurrency race** | Two users update same WO | Versioning + optimistic locking + state checks |

## 33.1 Safety action matrix

| **Action class** | **AI suggestion** | **AI execution** | **Human control** |
|---|---|---|---|
| **Routine low-risk** | Yes | Policy may allow | Defined role |
| **Maintenance with moderate risk** | Yes | Approval/rule | Supervisor/manager as configured |
| **Critical asset intervention** | Yes with evidence | Approval required | Authorized approver |
| **Safety-critical / LOTO** | Controlled only | No autonomous authorization | EHS/allowed human |
| **Control/configuration change** | Highly restricted | Privileged change process | Explicit allowed human |

## 33.2 Break-glass

Emergency elevation must be temporary, explicitly allowed, scoped, fully audited and automatically expire. It must not become a permanent administrator bypass.
