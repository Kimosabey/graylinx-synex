# 34. Data, RAG and Report Governance

## 34.1 Data product contract

| **Field** | **Requirement** |
|---|---|
| **Owner** | Named data owner |
| **Schema** | Versioned contract |
| **Classification** | Public/Internal/Operational/Sensitive/Critical as applicable |
| **Freshness** | Defined SLA |
| **Quality** | Defined validity/completeness rules |
| **Lineage** | Source → transformation → output |
| **Retention** | Defined rule |
| Tenant scope | Enforced |
| **Consumer** | Known services/agents/reports |

## 34.2 RAG rules

- Retrieved content is data, not authority.
- System rules and tool rules cannot be overridden by retrieved documents.
- Retrieval is customer account/site/asset scoped.
- Source/version/freshness are preserved.
- Conflicting sources produce an explicit uncertainty state.
- Unverified created by AI content is not automatically promoted to trusted knowledge.

## 34.3 Report lineage

REPORT → KPI → CALCULATION → SOURCE DATA → SOURCE RECORDS → TIMESTAMP / VERSION

| **EXECUTIVE TRUST RULE Every important number should be explainable: where it came from, how it was calculated, how fresh it is and what scope was used.** |
|---|
