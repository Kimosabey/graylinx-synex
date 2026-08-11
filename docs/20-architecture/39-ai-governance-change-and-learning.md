# 39. AI Governance, Change and Learning

| **Artifact** | **Versioned?** | **Evaluation?** | **Audit?** |
|---|---|---|---|
| **Model** | Yes | Yes | Yes |
| **Agent** | Yes | Yes | Yes |
| **Prompt/instruction** | Yes | Yes | Yes |
| **Tool contract** | Yes | Yes | Yes |
| FDD rule | Yes | Yes | Yes |
| **Policy** | Yes | Simulation + test | Yes |
| **Approval matrix** | Yes | Scenario tests | Yes |
| SOP/RAG source | Yes | Retrieval/grounding tests | Yes |
| **Workflow/state machine** | Yes | Transition tests | Yes |

## 39.1 Human override

When a human rejects or changes an AI suggestion, capture the reason, evidence and eventual outcome. Human override is a governed learning signal—not an automatic training label.

## 39.2 Policy simulation

Before deploying a rule change, replay representative historical requests in dry-run mode and compare ALLOW / APPROVAL / DENY outcomes with the current rule.
