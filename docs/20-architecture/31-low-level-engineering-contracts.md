# 31. Low-Level Engineering Contracts

The architecture becomes production-grade when every workflow component has a precise contract.

## 31.1 Tool contract

| **Field** | **Required** |
|---|---|
| **Tool identity/version** | Unique immutable version |
| **Owner** | Engineering/service owner |
| **Input schema** | Strict validation |
| **Output schema** | Typed validation |
| **Read/write** | Explicit category |
| **Allowed agents/roles** | Allowlist |
| Tenant/asset scope | Required |
| **Risk** | LOW/MEDIUM/HIGH/etc. |
| **Approval** | Explicit rule |
| **Idempotency** | Required for writes |
| **Timeout/retry** | Bounded |
| **Side effects** | Documented |
| **Audit** | Mandatory for material actions |

## 31.2 Policy decision contract

Every action should resolve to:

| **POLICY RESULT ALLOW \| ALLOW-WITH-APPROVAL \| READ-ONLY \| ESCALATE \| DENY** |
|---|

Decision input: user + role + customer account + scope + intent + action + asset criticality + risk + safety + current state + rule version.

## 31.3 Evidence pack contract

| **Evidence** | **Required information** |
|---|---|
| **Source** | Telemetry/document/WO/system |
| **Timestamp** | Freshness |
| ML/FDD | Model/rule/version |
| **Operating state** | Gate result |
| **Measurements** | Residuals/values/trends |
| **History** | Similar verified cases |
| **Knowledge** | Source/version |
| **Confidence** | Known / likely / ambiguous |
| **Decision** | Why suggestion follows |
