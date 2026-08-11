# 15. Alerts and Escalation

| **Alert type** | **Trigger** | **Action** |
|---|---|---|
| **Equipment fault** | FDD continues for the required time fault | Notify reliability/maintenance; offer WO |
| **Critical risk** | Risk crosses threshold | Immediate escalation per rule |
| **SLA breach** | WO approaching/overdue | Notify owner/manager; reprioritize |
| **Data quality** | Sensor/model input invalid | Suppress unsafe diagnosis; open data-quality path |
| **AI anomaly** | Agent/tool behavior abnormal | Observe, contain, disable/rollback if required |
| **Safety** | Safety condition detected | Stop/deny controlled action and route to allowed human |

Escalation workflow: EVENT → CLASSIFY → DEDUPLICATE → SCOPE → PRIORITY → ROUTE → ACKNOWLEDGE → ACT → VERIFY → CLOSE/ESCALATE.
