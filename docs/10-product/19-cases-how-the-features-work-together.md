# 19. Cases — How the Features Work Together

## Case 1 — Manager Finds Today's Important Problems

User: “What needs attention today?”

Flow: Copilot checks the manager's allowed sites → checks equipment health, FDD events, critical WOs and SLA risks → ranks the important items → explains each item → offers actions.

Result: Manager gets a short prioritized list instead of checking many screens.

## Case 2 — Fault Becomes a Work Order

User: “Create a WO for this Chiller-03 fault.”

Flow: AI understands the selected equipment → collects the fault and supporting data → prepares WO details → checks permission/risk → asks for approval if required → creates the WO.

Result: A useful, evidence-backed WO is created with less manual typing.

## Case 3 — Technician Gets Help

User: “What should I check first?”

Flow: AI reads the current WO and equipment context → finds the approved procedure → shows the first safe checks → records the technician's findings.

Result: The technician gets job-specific help without searching many documents.

## Case 4 — Repair Is Verified

User: “Did the repair fix the problem?”

Flow: After the WO is completed → system checks new equipment readings and FDD state → compares before/after → decides PASS, FAIL or not enough information.

Result: A WO is not called successful just because someone clicked Complete.

## Case 5 — Executive Wants the Business Story

User: “How are we doing this month?”

Flow: AI builds a role-appropriate summary → shows availability, downtime, cost, major risks and critical work → lets the executive ask why any number changed.

Result: Leadership gets the business answer first and can drill into technical detail only when needed.

## Case 6 — Customer Wants a Site Report

User: “Why did my site's performance drop?”

Flow: Customer scope is checked → AI analyzes allowed site data → explains the main drivers → links to relevant equipment and WOs → keeps other customers' data hidden.

Result: Customer receives a clear, scoped explanation.

## Case 7 — Not Enough Evidence

User: “What exactly failed?”

Flow: ML/FDD data is checked → operating conditions are invalid or evidence conflicts → AI does not invent a diagnosis → explains what is missing and suggests the next data/check needed.

Result: The platform is useful without pretending to know something it cannot prove.

## Case 8 — Many Alerts Are Really One Problem

User: “Why am I getting so many alerts?”

Flow: System groups related alerts → finds the common equipment/event → explains the main issue → sends the appropriate alert instead of repeating the same message.

Result: Less alert noise and faster attention to the real issue.

## 19.1 Complete Example — Fault → Fix → Proof → Report

1. Existing ML/FDD detects abnormal equipment behavior.
2. Graylinx checks that the equipment is in a valid operating state and the issue persists.
3. Reliability AI explains the finding using the available proof.
4. User asks the Copilot what to do.
5. AI suggests the next inspection or repair.
6. User asks AI to prepare a WO.
7. Control checks permission, risk and approval.
8. WO is planned and assigned.
9. Technician performs the work and records findings.
10. Graylinx checks the equipment after repair.
11. PASS → close. FAIL → reopen/escalate. UNKNOWN → request more evidence.
12. Verified result becomes part of the report/history and future learning.
