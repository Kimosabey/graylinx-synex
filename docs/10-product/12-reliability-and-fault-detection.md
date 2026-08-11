# 12. Reliability and Fault Detection

| **Capability** | **Function** | **Example** |
|---|---|---|
| **Detection** | Detect abnormal residual/behavior | Power residual outside normal band |
| **Operating gates** | Only evaluate when equipment state is valid | Compressor ON + stable load |
| **Persistence** | Reject transient spikes | Fault persists 10 min |
| **Volatility** | Detect unstable behavior | Pressure oscillation |
| **Trend** | Detect deterioration | Residual worsening over 7 days |
| **Fault ranking** | Rank plausible issues | Condenser performance most likely |
| **NO_DIAGNOSIS** | Explicitly decline when evidence is insufficient | “Insufficient evidence” |
| **Evidence pack** | Make conclusion inspectable | Residuals + gates + history |
| **Bad actor** | Find repeat/poor performers | Repeated fault across 5 cycles |
| **Verification** | Check post-repair state | Residual returns to normal |

## 12.1 Reliability case

Telemetry → ML residuals → operating-state gate → persistence/volatility/trend → FDD decision → evidence pack → Reliability Agent explanation → maintenance suggestion → WO → post-work equipment readings → verification.

## 12.2 RELIABILITY AI

| **Feature** | **Example** | **Value** |
|---|---|---|
| **Fault explanation** | “Why did FDD raise this?” | Makes ML useful to non-ML users |
| **Fault ranking** | “What is most likely?” | Focuses investigation |
| **Similar cases** | “Has this happened before?” | Reuse proven experience |
| **Repeat failure** | “Which assets keep failing?” | Find systemic problems |
| **Trend explanation** | “Is this getting worse?” | Early attention |
| **Bad actor list** | “Who causes most downtime?” | Focus maintenance effort |
| **Confidence/uncertainty** | “How sure are we?” | Avoids false certainty |
| **NO_DIAGNOSIS** | Not enough proof | Prevents unsafe/false conclusions |
