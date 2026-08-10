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

## Instrumentation and data

| ID | Question | Blocks | Owner | Status |
|---|---|---|---|---|
| Q1 | Is condenser flow measured at target sites, and is the signal trustworthy? | F1–F8: four of six models, and most fault classes | Vishnu + site survey | Open |
| Q2 | How is evaporator flow derived — measured, from DPT, or assumed constant? | `rSP` validity, efficiency proxy | Vishnu + site survey | Open |
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

## Closed

_None yet._
