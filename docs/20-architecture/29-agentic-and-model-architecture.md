# 29. Agentic and Model Architecture

Keep the current four-model local configuration as the baseline unless evaluation demonstrates a need for change.

| **Model** | **Role** | **Primary responsibility** |
|---|---|---|
| **gemma4:26b-a4b-it-qat** | Brain | Reasoning + final answer |
| **devstral:latest** | Tool executor | ReAct loop + NL→SQL |
| **phi4** | Text / auditor / router / RAG | Narration, auditing, routing arbitration, RAG and grounding |
| **nomic-embed-text** | Embeddings | Local 768d embeddings |

## 29.1 Agent families

| **Agent** | **Core job** | **Hard boundary** |
|---|---|---|
| **Orchestrator** | Coordinate workflow and state | Cannot bypass rule |
| **Asset** | Asset context and health | Asset scope only |
| **Reliability** | ML/FDD evidence and diagnosis support | Must use evidence |
| **Maintenance** | Maintenance suggestion and WO drafting | Cannot bypass safety |
| **WO** | Controlled WO operations | Tool gateway required |
| Knowledge/RAG | Authorized knowledge retrieval | Tenant/source scoped |
| **Planning** | Schedule/assignment suggestion | Cannot override skills/safety |
| **Inventory** | Parts availability/reservation suggestion | Financial thresholds enforced |
| **Verification** | Repair outcome determination | Evidence required |
| **Reporting** | Role-aware report generation | No scope expansion |

## 29.2 Agent registry

Each production agent must register: owner, purpose, version, prompt/instruction version, allowed tools, allowed data scopes, risk class, evaluation suite, service target, rollback version and status.
