# 9. Work Orders

## 9.1 WO features

| **Feature** | **What it does** | **Example** |
|---|---|---|
| **Manual WO** | User creates work from observed issue | Technician reports vibration |
| **AI-drafted WO** | Copilot converts evidence into structured draft | “Create WO for this fault.” |
| **Priority** | Ranks work by risk/criticality/SLA/context | Critical chiller fault = P1 |
| **Approval** | Routes controlled actions to allowed approver | Critical repair needs supervisor |
| **Planning** | Suggests window, technician, duration and dependencies | Schedule during low-load period |
| **Assignment** | Matches skill, certification, location and availability | Assign HVAC-certified technician |
| **Parts** | Checks stock, reservation and shortage | Reserve compressor seal kit |
| **Execution** | Technician follows safe procedure and records work | Inspection → repair → findings |
| **Evidence** | Attach readings, photos, notes, documents | Before/after measurements |
| **Verification** | Checks whether equipment returned to expected behavior | FDD clears after repair |
| **Reopen** | Automatically/manual reopen when repair fails | Fault persists after repair |
| **Escalation** | Routes unresolved/high-risk work | Escalate to OEM/EHS |
| **Closure** | Controlled final state | Verified + accepted + audited |

## 9.2 WO workflow cases

Case A — FDD creates maintenance opportunity

FDD detects continues for the required time abnormality → evidence pack created → Reliability Agent explains → Maintenance Agent proposes action → WO draft → rule checks risk → approval if required → planned → assigned → executed → verified.

**Case B — Technician creates WO from field observation**

Technician says “Chiller-03 has abnormal noise” → Copilot resolves asset → asks/records structured observation → checks history → creates WO → supervisor receives notification if priority threshold is met.

**Case C — Parts unavailable**

WO requires part → Inventory Agent checks stock → part unavailable → procurement suggestion → ETA evaluated against maintenance window → planner reschedules or escalates.

**Case D — Repair did not work**

WO marked complete → verification sees abnormality remains → verification FAIL → WO reopens → previous findings preserved → next diagnosis begins.

## 9.3 Work order non-negotiables

The WO system is Graylinx's controlled execution loop.

| **MASTER WO FLOW DETECT → DIAGNOSE → RECOMMEND → DRAFT → APPROVE → PLAN → ASSIGN → PARTS → EXECUTE → FINDINGS → REPAIR → VERIFY → CLOSE / REOPEN → LEARN** |
|---|

| **State** | **Allowed transition** | **Required control** |
|---|---|---|
| **DRAFT** | → APPROVAL / CANCEL | Permission + payload validation |
| **APPROVAL** | → APPROVED / REJECTED / EXPIRED | Authorized approver |
| **APPROVED** | → PLANNED | Planning rule |
| **PLANNED** | → ASSIGNED | Skill + availability + scope |
| **ASSIGNED** | → IN_PROGRESS | Technician authorization |
| **IN_PROGRESS** | → COMPLETED | Findings + work record |
| **COMPLETED** | → VERIFIED / VERIFICATION_PENDING | Evidence-based verification |
| **VERIFIED** | → CLOSED | Closure rule |
| **VERIFIED** | → REOPENED | Failed/uncertain outcome |
| **ANY CONTROLLED STATE** | → ESCALATED | Safety, SLA, failure or rule event |

### WO non-negotiables

- Completion is not automatically successful repair.
- Critical work requires the defined approval/safety path.
- All writes are idempotent and two people/processes changing the same thing at once-safe.
- AI cannot bypass state transitions.
- Verification failure can reopen the WO.
- Every important state/action is auditable.
