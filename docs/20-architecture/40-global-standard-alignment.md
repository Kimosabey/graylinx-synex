# 40. Global-Standard Alignment

The architecture is designed against recognized frameworks and practices. This is an alignment target, not a claim of certification.

| **Framework / practice** | **Graylinx use** |
|---|---|
| **NIST AI RMF 1.0** | GOVERN → MAP → MEASURE → MANAGE; AI risk lifecycle |
| **ISO/IEC 42001:2023** | AI management system, accountability and continual improvement |
| **ISO/IEC 23894:2023** | AI-specific risk identification, treatment and monitoring |
| **NIST CSF 2.0** | Cybersecurity governance, protection, detection, response and recovery |
| **OWASP LLM / application security** | Prompt injection, access control, insecure tool use, supply chain, logging and resource abuse |
| **Zero Trust principles** | Never trust by default; authenticate, authorize and continuously validate |
| **Industrial safety practices** | Safety-critical work requires controlled human authorization and fail-safe behavior |

## 40.1 Governance operating cycle

| **CONTINUOUS GOVERNANCE PLAN → RISK ASSESS → DESIGN → BUILD → TEST / validation → APPROVE → DEPLOY → MONITOR → REVIEW → IMPROVE** |
|---|

## 40.2 Non-negotiable global practices

- Policy is enforced outside the LLM.
- Tool/API boundaries enforce authorization independently.
- Safety cannot be overridden by prompts.
- Unknown/ambiguous is a valid outcome.
- High-risk actions require explicit human control.
- Persistent external changes are auditable.
- Production AI components are versioned and evaluated.
- Tenant boundaries are enforced independently at retrieval and execution.
