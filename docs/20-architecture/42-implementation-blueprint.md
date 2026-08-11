# 42. Implementation Blueprint

## 42.1 Service boundaries

| **Component** | **Owns** | **Must not own** |
|---|---|---|
| **Copilot API** | Conversation/session entry | Direct uncontrolled writes |
| **Control Plane** | Policy, identity/scope decisions, approval, audit | Business-specific diagnostic logic |
| **Orchestrator** | Workflow coordination/state | Policy bypass |
| **Agent services** | Domain reasoning/suggestion | Unrestricted enterprise writes |
| **Tool Gateway** | Validated external actions | Free-form agent access |
| ML/FDD services | Equipment intelligence/evidence | User authorization |
| RAG service | Scoped retrieval | Policy authority |
| **WO service** | WO state and transactions | LLM rule decisions |
| **Reporting service** | Metrics/report artifacts | Scope expansion |
| **Verification service** | Outcome verification | Unverified closure |

## 42.2 Minimum state domains

- Conversation state
- Agent task state
- Approval state
- WO state
- Tool execution state
- Verification state
- Audit/event state

## 42.3 Transaction rule

Every external write must be treated as a transactionally significant event: validate → authorize → execute once → reconcile → audit → verify.
