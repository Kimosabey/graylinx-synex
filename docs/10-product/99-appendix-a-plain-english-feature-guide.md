# Appendix A — Plain-English Feature Guide

This section explains the main Graylinx features in simple English. For every feature, the goal is: what it does, who uses it, a real example, and what happens next.

## A. Reports — “Tell me what is happening.”

Who uses it: Executives, Plant Managers, Maintenance Managers, Reliability Engineers, Customers and other allowed users.

- See the health of the company, plant, site, system or equipment.
- See open, overdue and critical work orders.
- See failures, repeat problems, downtime, energy use and maintenance cost.
- Ask the Copilot to explain a report in simple words.
- Move from a company-level number down to a site, equipment and sensor.
Example: A Plant Manager asks, “Which equipment needs attention today?”

What happens: Graylinx checks the manager’s allowed sites → checks equipment health and faults → ranks the important equipment → shows why each one needs attention → offers the next action.

Result: The manager does not need to search five dashboards manually.

## B. Work Orders — “Get the work done.”

Who uses it: Maintenance Managers, Supervisors, Planners, Technicians, Service Teams and allowed customers.

- Create a work order manually or ask the Copilot to prepare one.
- Set priority.
- Get approval when needed.
- Plan the time, technician and parts.
- Record what the technician found and fixed.
- Check whether the repair actually solved the problem.
Example: “Create a work order for Chiller-03 because the condenser performance is abnormal.”

What happens: Graylinx checks the equipment and supporting data → prepares the WO → checks the user’s permission and risk → asks for approval if required → creates the WO → assigns/plans it → tracks the work → checks the equipment after repair.

Important: A technician marking a WO complete does not automatically mean the problem is fixed.

## C. Synex Copilot — “Ask Graylinx.”

The Copilot is the simple front door. Behind it, the AI can use reports, equipment data, FDD, documents, work orders and approved tools.

| **User says** | **Graylinx does** | **Example result** |
|---|---|---|
| “What is wrong with Chiller-03?” | Checks asset data, current readings, FDD and past work. | “The main issue is likely condenser performance. Here is the supporting data.” |
| “Why is it unhealthy?” | Explains the important readings and trends. | Simple explanation + proof. |
| “What should we do?” | Suggests the next inspection or maintenance step. | Recommended action with supporting data. |
| “Create a WO.” | Checks permission and risk, then drafts/creates through the controlled WO service. | WO draft or approval request. |
| “Show my overdue WOs.” | Uses the user’s allowed sites/assets and filters the data. | Clean overdue list. |
| “Did the repair work?” | Checks post-repair equipment readings and FDD. | PASS, FAIL or not enough information. |
| “Send this report to the customer.” | Checks whether the user can share it and whether the receiver is allowed. | Send, or safely refuse. |

## D. Asset View — “Show me everything about this equipment.”

Example: Open Chiller-03.

- See where it belongs: customer → site → plant → system → equipment → component.
- See current health and risk.
- See past failures and work orders.
- See important readings and trends.
- See related equipment.
- Ask the Copilot questions about the asset.
Example question: “Has this chiller had this problem before?”

Result: Graylinx searches the allowed history and shows similar past cases.

## E. FDD — “Find and explain problems.”

Graylinx already has ML models. The AI layer uses those results; it does not replace the equipment intelligence.

- ML checks whether readings are different from normal.
- FDD checks that the equipment is really in a valid operating state.
- The system checks whether the problem lasts long enough to matter.
- It checks whether the problem is getting worse or unstable.
- If there is not enough proof, it can say: “I do not have enough information to diagnose this.”
Example: A pressure reading changes for 20 seconds and then returns to normal.

Result: Graylinx should not immediately create a critical fault. It waits for the defined checks and avoids a false alarm.

## F. Knowledge / Documents — “Tell me how to fix it.”

The Copilot can search allowed manuals, SOPs, previous work orders, verified cases and site documents.

Example: Technician asks, “What is the inspection procedure for this fault?”

Result: Graylinx finds the correct procedure, shows the source, and gives the technician the relevant steps.

- Documents are supporting information, not permission to perform an unsafe action.
- A document cannot override safety rules or system rules.
- The user should be able to see where important information came from.

## G. Maintenance Planning — “What should we do first?”

Example: There are 20 open WOs and only two technicians available.

Graylinx considers equipment importance, fault risk, production impact, SLA, technician skill, parts and available maintenance time.

Result: It gives the planner a ranked list. The planner remains in control of the final decision when required.

## H. Inventory and Parts — “Do we have what we need?”

Example: A WO needs a compressor part.

- Check whether the part is in stock.
- Check whether another WO is already using it.
- Check expected delivery.
- Suggest reservation or purchase when allowed.
- Tell the planner if the part will delay the job.
Result: Maintenance does not discover the missing part only after the technician arrives.

## I. Alerts — “Tell the right person at the right time.”

Examples:

- Critical equipment fault → maintenance/reliability alert.
- WO close to SLA breach → manager alert.
- Safety issue → controlled safety escalation.
- Bad sensor data → do not give a confident diagnosis; send a data-quality alert.
The system should avoid sending the same alert repeatedly. It should group related events and show the reason for the alert.

## J. Verification — “Did it really work?”

Example: A technician repairs Chiller-03 and marks the WO complete.

Graylinx checks the equipment again. If the readings return to the expected range and the fault clears, the result can be PASS. If the fault remains, the WO can be reopened or escalated.

This closes the loop: Detect → Work → Repair → Check → Prove.

## K. Safety — “AI must know when to stop.”

Example: A user asks the Copilot to perform a safety-critical change.

The Copilot does not simply follow the instruction. The Control Plane checks the action, risk, permission, required permit and human approval. If the action is not allowed, it is blocked and recorded.

Simple rule: AI can help people understand and prepare work. It must not bypass safety controls.

## L. Customer Assistance — “Give each customer only their own view.”

Example: Customer A asks for all equipment reports.

Graylinx checks Customer A’s account and allowed sites before retrieving anything. Customer A cannot use the Copilot to see Customer B’s data.

The same rule applies to reports, documents, work orders, equipment and AI actions.

## M. Executive Assistance — “Give me the answer, not 20 screens.”

Example: CEO asks, “How are we doing this month?”

The Copilot gives a short business summary, then offers drill-down into availability, downtime, maintenance cost, major risks and problem assets.

The executive can then ask: “Why did downtime increase?” and continue the investigation through the same conversation.

## N. Technician Assistance — “Help me do today's work.”

Example: Technician opens the WO for Chiller-03.

- See the fault in simple language.
- See safety requirements.
- See the correct procedure.
- See important past repair history.
- See required parts.
- Record findings through the Copilot.
- Ask questions while working.
- Finish the WO and start verification.
The technician should not need to understand which AI agent is running in the background.

## O. Complete Example — From Fault to Business Result

1. ML/FDD notices abnormal condenser behavior.
2. The system confirms the equipment is running in a valid state and the problem persists.
3. Reliability AI explains the finding using supporting data.
4. Maintenance AI suggests an inspection.
5. The manager asks the Copilot to create a WO.
6. The Control Plane checks permission and risk.
7. The WO is approved, planned and assigned.
8. The technician follows the procedure and records findings.
9. The repair is completed.
10. Graylinx checks the equipment after the repair.
11. If the fault clears, the WO is verified and closed.
12. The result appears in reports and becomes part of the maintenance history.

## P. Simple Rule for Every Feature

Every feature in Graylinx should make one of these four questions easier to answer:

**1. What is happening?
2. Why is it happening?
3. What should we do?
4. Did it work?**
