# 13. Knowledge and Document Intelligence

| **Knowledge source** | **Use** | **Example** |
|---|---|---|
| SOP | Step-by-step procedure | Condenser inspection SOP |
| **Manual** | Manufacturer technical information | Compressor service manual |
| **Historical WO** | What was done before | Previous vibration repair |
| **Verified case** | Known-good troubleshooting pattern | Similar fault on Chiller-07 |
| **Asset documentation** | Site-specific configuration | BMS point mapping |
| **Policy** | Operational restrictions | Approval rule |
| **Safety document** | Safety requirements | Permit/LOTO procedure |

RAG workflow: QUERY → AUTHORIZE SCOPE → RETRIEVE → RANK → CHECK SOURCE/FRESHNESS → GROUND → ANSWER WITH CITATIONS/EVIDENCE → AUDIT.

- Retrieved content cannot override system rule or safety.
- Conflicting sources should be surfaced rather than silently merged.
- Unverified generated content should not automatically become trusted knowledge.
