# 27. Personas and Role Architecture

Use many business user roles, but implement shared user role families and configurable permissions—not 30+ independent products.

| **Family** | **Personas** |
|---|---|
| **Business** | CXO/Executive; Asset Owner; Regional Head; Finance/Cost Manager |
| **Operations** | Plant Manager; Operations Manager; Production/Business Operations Manager |
| **Maintenance / Service** | Maintenance Manager; Reliability Manager; Supervisor; Planner; Technician; Service Manager; Contractor; OEM Engineer |
| **Engineering / Intelligence** | Reliability Engineer; Controls/BMS Engineer; Energy Manager; Data/IoT Engineer; AI/ML Engineer; Data/Reliability Analyst; AI Governance/Product Owner |
| **Supply Chain** | Inventory/Stores Manager; Procurement/Buyer; Vendor/AMC Manager |
| **Safety / Governance** | EHS/Safety; Auditor/Compliance; Configuration/Change Manager |
| **Platform** | System Administrator; Integration/IT Administrator |
| **Customer** | Customer Administrator; Customer Manager; Customer Viewer |

## 27.1 Authorization model

PERSON → ROLE → TENANT → ORGANIZATION/SITE → ASSET SCOPE → DATA SCOPE → ACTION SCOPE → APPROVAL AUTHORITY

| **ROLE ≠ PERMISSION A Reliability Engineer may have access to Plant-01 but not Plant-03. A Technician may edit assigned WOs but not close critical work. Authorization must be evaluated at the API/tool boundary, not only in the UI.** |
|---|
