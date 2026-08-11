# 10. Equipment and Asset Intelligence

| **Capability** | **Function** | **Example** |
|---|---|---|
| **Hierarchy** | Enterprise → Site → Plant → System → Equipment → Component → Sensor | Navigate from enterprise risk to a valve |
| **Asset profile** | Identity, make/model, criticality, age, status, owner | Open Chiller-03 profile |
| **Health** | Current health + trend + risk | Health deteriorating over 14 days |
| **History** | WOs, faults, readings, interventions | Show last 12 repairs |
| **Dependencies** | Upstream/downstream relationships | Which systems depend on this pump? |
| **Criticality** | Business/safety/production importance | Criticality = high |
| **Similar assets** | Compare peers | Compare Chiller-03 with Chiller-01/02 |
| **Context** | Current operating state and maintenance window | Running at 85% load |

Asset workflow: SELECT ASSET → LOAD AUTHORIZED CONTEXT → HEALTH → HISTORY → DEPENDENCIES → FDD → KNOWLEDGE → RECOMMENDATION → ACTION.
