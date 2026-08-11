# 5. The Copilot in Practice — Levels and Conversations

## 5.1 Conversational feature levels

| **Mode** | **User experience** | **Example** |
|---|---|---|
| **ASK** | Get information | “What is happening with my plant?” |
| **EXPLAIN** | Understand why | “Why is Chiller-03 unhealthy?” |
| **INVESTIGATE** | Explore evidence | “Compare this fault with the last 5 cases.” |
| **RECOMMEND** | Get next best action | “What should we inspect first?” |
| **DRAFT** | Prepare work/report | “Draft a WO and weekly report.” |
| **APPROVE** | Review controlled action | “Show me what I am approving.” |
| **EXECUTE** | Perform permitted action | “Create the approved WO.” |
| **VERIFY** | Check outcome | “Did the repair fix the issue?” |
| **REPORT** | Generate/summarize report | “Give me the maintenance summary.” |
| **ESCALATE** | Route to human/team | “Escalate this safety concern.” |

## 5.2 Copilot end-to-end workflow

MESSAGE → IDENTITY → TENANT/SITE/ASSET SCOPE → INTENT → CONTEXT → RISK CLASS → SELECT AGENT → RETRIEVE EVIDENCE → PLAN → POLICY CHECK → APPROVAL IF REQUIRED → TOOL EXECUTION → RESULT VALIDATION → VERIFICATION → RESPONSE → AUDIT

## 5.3 Example conversations

**“Show me the worst equipment today.”**

Copilot resolves user's site/asset scope → queries health/FDD/risk → ranks assets → shows evidence and reason → offers “Explain”, “Create WO” or “Generate report”.

**“Why is this compressor failing?”**

Asset context → current equipment readings/ML residuals → FDD gates → historical WOs → relevant SOP → grounded explanation → uncertainty if evidence is insufficient.

**“Create a work order for this.”**

Copilot identifies the selected fault/asset → summarizes proposed work → checks permission/risk → drafts WO → requests approval if rule requires → creates through WO tool only after authorization.

**“Close this WO.”**

Copilot checks WO state → verifies required findings and evidence → runs verification → if PASS and user has authority, closure is permitted; otherwise it explains what is missing.

**“Give me all customer sites.”**

Scope check occurs before retrieval. If user lacks cross-customer permission, the request is denied without exposing data.

## 5.4 Copilot conversations by role

### What the Copilot can do

| **Mode** | **User asks** | **What Graylinx does** |
|---|---|---|
| **Ask** | “What is the status?” | Finds current allowed information |
| **Explain** | “Why?” | Explains using supporting data |
| **Investigate** | “Show me similar cases.” | Searches history and documents |
| **Compare** | “Which is worse?” | Compares assets/sites/periods |
| **Recommend** | “What should we do?” | Suggests next steps |
| **Draft** | “Prepare a WO/report.” | Creates a draft |
| **Act** | “Create/assign/send.” | Checks rules then uses an approved tool |
| **Verify** | “Did it work?” | Checks outcome evidence |
| **Summarize** | “Give me the short version.” | Creates role-specific summary |
| **Escalate** | “Send this to reliability.” | Routes to the right team |

### Copilot cases by person

| **Person** | **Example question** | **Expected answer/action** |
|---|---|---|
| **CEO** | “How are we doing?” | Business summary + biggest risks + drill-down |
| **Regional Head** | “Which site is at risk?” | Site comparison + reasons |
| **Plant Manager** | “What needs attention now?” | Ranked equipment/work list |
| **Maintenance Manager** | “Why is backlog high?” | Root causes + suggested actions |
| **Reliability Engineer** | “Why is this fault happening?” | FDD evidence + similar cases |
| **Planner** | “What can we schedule tomorrow?” | WOs matched to window/people/parts |
| **Technician** | “What should I do next?” | Safe procedure + job context |
| **EHS** | “Is this action allowed?” | Rule/safety result + approval path |
| **Customer** | “How is my site?” | Customer-scoped performance summary |
| **Admin** | “Why can't this user access the report?” | Permission/configuration explanation |
