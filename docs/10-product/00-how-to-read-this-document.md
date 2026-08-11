# How to Read This Document

The product sections of this document are written in plain English. The architecture sections use the precise technical term, because engineers, auditors and security reviewers need the exact word. This table maps one to the other. Every term below means the same thing everywhere in the document.

| **Term** | **Plain English meaning** |
|---|---|
| Copilot | The single AI assistant users talk to. It is the front door to the whole platform. |
| Agent | A specialised worker inside the platform that handles one kind of job, such as reliability or planning. Users never address agents directly. |
| Tool | A single controlled action the AI is allowed to perform, such as “get health” or “create work order”. |
| Tool gateway | The layer that checks and executes every tool call, attaches credentials and writes the audit record. |
| Control Plane | The system that decides whether an action is allowed. The AI decides what it wants to do; the Control Plane decides whether it may. |
| Scope | The exact set of customers, sites, equipment and data one person is allowed to see or change. |
| Tenant | One customer account, kept completely separate from every other customer account. |
| Evidence | The real data behind an answer: readings, timestamps, model versions, records and documents. |
| Evidence pack | The bundle of evidence assembled for one answer, kept with the answer so it can be checked later. |
| Grounding | Checking that every statement the AI makes is supported by the evidence it retrieved. |
| Hallucination | An AI statement that sounds right but is not supported by any real data. Grounding exists to catch these. |
| Lineage | Where a number came from and how it was calculated, all the way back to the source record. |
| FDD | Fault Detection and Diagnosis — the existing Graylinx models and rules that find and classify equipment faults. |
| Model residual | The difference between what a sensor actually reads and what the normal-operation model predicted it should read. |
| Operating gate | A check that the equipment is in a valid state (running steady, above minimum load, valid flows) before any fault rule is allowed to fire. |
| Persistence | How long a pattern must hold before it counts as a fault rather than a passing disturbance. |
| NO_DIAGNOSIS | The honest answer the platform gives when the evidence is not good enough to name a cause. |
| RAG | Retrieval-augmented generation — the AI searches approved documents and answers from what it finds, with the sources shown. |
| SOP | Standard operating procedure — the approved way a task must be carried out. |
| Verification | Proving after the work that the problem is actually fixed, using post-work evidence rather than the work order status. |
| Criticality | How important a piece of equipment is to production, safety and cost. |
| Escalation | Sending an issue to the right person or team when a rule requires it. |
| Approval | A named human agreeing to an action before it happens. The AI can prepare an approval request but never grants one. |
| Idempotency | A safety property meaning a repeated request cannot create a duplicate — a retried work order is still one work order. |
| Degraded mode | A reduced but safe way of operating when part of the system is unavailable. The platform says when it is in this mode. |
| Audit trail | The permanent record of who asked, what was decided, what ran and what changed. |
| Break-glass | Temporary emergency access that is explicitly granted, fully recorded and expires automatically. |
| Prompt injection | An attack where text hidden in a document tries to give the AI instructions. Retrieved text is always treated as data, never as instructions. |
| Release gate | A test the platform must pass before a new version reaches customers. |
| Digital twin | The platform’s model of a real asset, including its normal behaviour and its history. |
| Work order (WO) | The record of a maintenance job: what must be done, by whom, when, and what was found. |
| Normal-operation model | A model trained on how the equipment behaves when it is healthy. It predicts what a reading should be, so we can measure how far reality has moved away from it. |
| Operating envelope | The range of loads and temperatures a model was trained on. Outside that range its prediction is not trustworthy. |
| Model drift | A model slowly becoming wrong because the equipment, the controls or the duty have changed since it was trained. |
| Model registry | The controlled list of every model in production — its version, inputs, owner, error band and status. |
| Quarantine | What happens to a model that fails its health check: its output stops being used for diagnosis until it is fixed or retrained. |
| Re-baseline | Retraining a model on a new definition of normal, after the equipment or its controls have legitimately changed. |
| Efficiency proxy | A calculated indicator of how well the chiller is moving heat, derived from the two water-side temperature differences and their flows. |
| SLA | The agreed service level — for example how quickly critical work must be started or completed. |
