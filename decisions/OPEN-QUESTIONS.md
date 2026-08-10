# Open questions

Anything unresolved lives here. `TBD (Qn)` in a document must point at a row in
this file. When a question closes, record a decision in `DECISIONS.md` and move
the row to the Closed section — do not delete it.

## Naming

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| N1 | How do Synex and Thermynx relate — replacement, layer above, or separate products? | All positioning copy | Harshan | Open |
| N2 | Is "Graylinx Synex" or "Synex by Graylinx" the commercial form? | Cover, marketing | Harshan | Open |

## Product scope

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| S1 | Is the proposed MVP cut agreed? | `mvp/BACKLOG.md`, all build sequencing | Harshan | Open |
| S2 | Is the cooling tower in scope for phase one? | F13 | Vishnu + Harshan | Open |
| S3 | Which actions require SME sign-off rather than supervisor approval? | Approval matrix, G3 | Vishnu | Open |
| S4 | Relative weighting of criticality, SLA and production impact in the priority formula | W4 | Operations | Open |
| Q17 | Which build stage delivers `A1`, `U3`, `S1` and `S4`? Four MVP features are named by no stage, two of them safety features | Sequencing, and the stage-9 estimate | Harshan | Open |
| Q18 | Three different things are called roles — user personas, capability roles and agent skills. Which system governs which decision? | `C11`, `C20`, `RC3`, `U1`–`U8` | Harshan + Vishnu | Open |
| Q21 | What is a defensible efficiency baseline for these machines? Design band 0.65–0.85; the healthiest measured month on the reference plant is 1.40 | `E1`, and any cost or ROI figure | Vishnu | Open |
| Q22 | Which faults are answered by stopping the machine rather than by raising a work order? | `S6`, the escalation matrix | Vishnu + EHS | Open |
| Q23 | Does an estimated answer settle a blocking check, or only a measured one? | `RC5`, `RC10` | Vishnu | Open — proposed: measured only |
| Q24 | What triggers case seeding in live operation? | `RC8`; a detector that fires into nowhere leaves the queue reading empty | Harshan + platform | Open |
| Q25 | Should a case age, and into what? Auto-escalation on a timer dispatches people on a clock rather than on evidence | `RC9` | Harshan + Vishnu | Open |
| Q26 | What should marking a window untrusted actually do to reports, efficiency figures and the models? | `C23`, `C22` | Harshan + platform | Open |
| Q27 | Who owns model refits, on what trigger, and is there a schedule? | `F10`, `F11`, `F12` | Platform + Vishnu | Open |
| Q19 | Three inherited gaps are adopted as unsolved: no interim holding action for a deferred critical fault, no retraction mechanism (so learning from closed cases stays out), and duplicated checklist work under event grouping. Which, if any, does this programme take on? | `F9`, `V7`, and the deferred-fault risk | Harshan + Vishnu | Open |

## Instrumentation and data

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| Q1 | Is condenser flow measured at target sites, and is the signal trustworthy? | F1–F8: four of six models, and most fault classes | Vishnu + site survey | Open |
| Q2 | How is evaporator flow derived? **The documented derivation is known broken on the reference plant** — the differential-pressure input reads NULL while flow reports healthy values. What feeds it now? | `rSP` validity, efficiency proxy | Vishnu + site survey | Open — chain broken |
| Q14 | Is compressor lead/lag state reliably available from the BMS? | Five of six models | Site survey | Open |

## FDD thresholds — Vishnu

| ID | Question | Proposed starting point | Status |
|---|---|---|---|
| Q3 | Minimum load for a valid diagnosis | Confirm per machine type | Open |
| Q4 | Settling time after a start or stage change before residuals are trusted | TBD | Open |
| Q5 | Settling time after a leaving-water setpoint change | TBD | Open |
| Q6 | Persistence window — one value or per fault class? | 20–30 minutes as a common default | Open |
| Q7 | Healthy chilled-water ΔT band per machine | Design ΔT from the machine data sheet | Open |
| Q8 | Condenser approach temperature thresholds for fouling | Per OEM data sheet | Open |
| Q9 | Time constants separating low condenser flow from fouling | Low flow spiky/intermittent; fouling steady drift over weeks | Open |
| Q10 | Split overcharge from non-condensables, or keep combined? | Keep combined until instrumentation supports a split | Open |
| Q11 | Confirm undercharge and restriction stay combined | Keep combined, label the ambiguity honestly | Open |
| Q12 | Volatility threshold defining expansion valve hunting | Set from observed data | Open |
| Q13 | Sensor drift thresholds per sensor type before declaring sensor bias | Per sensor class | Open |
| Q20 | Are any fault classes missing from the fingerprint matrix? | Open — SME to add | Open |

## Verification and lifecycle

| ID | Question | Proposed starting point | Status |
|---|---|---|---|
| Q15 | What proves a condenser cleaning worked? | `rPwr`, `rDP`, `rCWL` back inside band, held several days across a representative load range | Open |
| Q16 | Re-baseline policy after an overhaul — who authorises, how long must the machine run first? | SME authorises; minimum steady running period to be agreed | Open |

## To reconcile

The Thermynx FDD initiative holds **57 open questions** at
`docs/plan-v4.9.1/fdd/04-sme/questions.md`, none of them answered. That agenda has
been **read** and the findings that change this programme are folded in — see
`CONTEXT.md` §10a and questions Q21–Q27. What has **not** been done is a
question-by-question reconciliation.

Their §1 is nine safety-critical questions about whether the system may *eliminate*
a candidate cause on unreviewed judgement, and it deserves the SME hour on its own
merits. Two of them bear directly on our `F7`: whether a wide approach eliminates
the cooling tower on the commonest fault class, and whether measured separations of
about 4 °C are strong enough to eliminate on or must stay priors. Our answer today
is the conservative one — keep the combined labels — and their reasoning supports it.

**Owner:** Harshan. **Blocks:** nothing today. **Do before the SME session**, not
after: their §3 overlaps our Q3–Q13, and asking Vishnu the same threshold twice
wastes the one review that matters.

## Closed

_None yet._
