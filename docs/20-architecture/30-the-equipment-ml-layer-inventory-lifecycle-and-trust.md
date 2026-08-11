# 30. The Equipment ML Layer — Inventory, Lifecycle and Trust

The equipment ML layer existed before the AI layer and is not replaced by it. It produces the numeric signals that the FDD rules classify, the Copilot explains and the verification step re-measures. This chapter defines it as a governed asset with an inventory, a lifecycle, a health standard and a trust contract.

## Model inventory — water-cooled chiller

Six normal-operation models per chiller. Each predicts one signal from the conditions the machine is actually working under, and each yields one residual.

| **Model** | **Predicts** | **Inputs** | **Residual** |
|---|---|---|---|
| Model DP | Discharge pressure | Suction pressure; chiller cooling load; condenser water entry temperature; condenser flow; compressor lead/lag | rDP |
| Model SP | Suction pressure | Evaporator leaving temperature; evaporator entry temperature; evaporator flow / DPT; compressor lead/lag | rSP |
| Model DT | Discharge temperature | Suction pressure; discharge pressure; chiller cooling load; condenser water entry temperature; condenser flow; compressor lead/lag | rDT |
| Model Power | Chiller amps / power | Evaporator leaving temperature; chiller load; condenser water entry temperature; condenser flow | rPwr |
| Model Compressor Amps | Compressor amps | Suction pressure; discharge pressure; chiller load; compressor lead/lag | rAmp |
| Model Condenser Leaving | Condenser water leaving temperature | Chiller load; condenser water entry temperature; condenser flow; compressor lead/lag | rCWL |

**Residual definition: rX(t) = X_actual(t) − X_predicted(t), where the prediction comes from the normal-operation model for that signal.**

## Sensor and tag requirements

| **Signal** | **Required for** | **Notes** |
|---|---|---|
| Suction pressure, discharge pressure, discharge temperature | Models DP, SP, DT, Compressor Amps | Core refrigerant-side instrumentation |
| Compressor amps | Model Compressor Amps | Compressor current or equivalent |
| Chiller power | Model Power | External energy meter where present; otherwise the chiller kW estimate |
| Evaporator entering and leaving water temperature | Models SP, Power; evaporator ΔT | Also drives the chilled-water ΔT health check |
| Condenser entering and leaving water temperature | Models DP, DT, Power, Condenser Leaving; condenser ΔT | Water-cooled machines |
| Evaporator flow / DPT | Model SP; efficiency proxy | Primary variable installations |
| Condenser flow | Models DP, DT, Power, Condenser Leaving; efficiency proxy | The highest-leverage single measurement in this set |
| Compressor lead/lag state | Models DP, SP, DT, Compressor Amps, Condenser Leaving | Staging context; without it residuals shift at every stage change |
| Wet bulb temperature | Cooling tower assessment | Water-cooled machines |
| Outside air temperature | Air-cooled equivalents | Air-cooled machines |

### Computed parameters

- Evaporator ΔT = evaporator entering − evaporator leaving
- Condenser ΔT = condenser leaving − condenser entering
- Efficiency proxy = (condenser ΔT × condenser flow) ÷ (evaporator ΔT × evaporator flow)

## Input dependency map

This table is the most operationally important one in the chapter. It states, in advance, exactly what the platform loses when a given signal fails — and therefore what the Copilot is obliged to say instead of guessing.

| **If this signal is missing or invalid** | **Models affected** | **What is lost** | **Platform behaviour** |
|---|---|---|---|
| Condenser flow | DP, DT, Power, Condenser Leaving — four of six | The entire efficiency and high-head branch: rPwr, rDP and rCWL all become untrustworthy, so condenser water-side, refrigerant-side high head and compressor inefficiency can no longer be separated. | NO_DIAGNOSIS for those classes; raise a data-quality work order for the condenser flow measurement. |
| Evaporator flow / DPT | SP | rSP becomes untrustworthy, so starved evaporator and expansion-valve hunting cannot be assessed. | NO_DIAGNOSIS for evaporator-side classes. |
| Chiller power | Power | The efficiency symptom that starts the whole isolation path disappears. | No efficiency fault can be raised at all. |
| Compressor lead/lag | DP, SP, DT, Compressor Amps, Condenser Leaving | Residuals shift at every staging change and produce false abnormalities. | Gate fails on staging transitions; persistence window extended. |
| Condenser water entry temperature | DP, DT, Power, Condenser Leaving | Head-pressure behaviour cannot be normalised for the water conditions. | NO_DIAGNOSIS for condenser-side classes. |
| Any temperature or pressure sensor drifting | The models using it | A biased input produces a confident but wrong residual. | Sensor-bias checks run first; a suspected sensor fault is reported as a sensor fault, not an equipment fault. |

| **OPERATING PRINCIPLE** **Rule out instrumentation before dispatching a crew. A residual that is abnormal only because its input is wrong looks identical to a real fault — the sensor-bias checks exist precisely to separate the two, and they run before any dispatch recommendation is offered.** |
|---|

## Training and baseline

| **Aspect** | **Standard** |
|---|---|
| What is trained | Normal behaviour only. Known fault periods and known bad-data periods are excluded from the training window. |
| Baseline source | The commissioning baseline where one exists; otherwise a verified healthy period agreed with the site. |
| Minimum window | Enough continuous running to cover the machine’s real duty, not simply a fixed number of days. |
| Envelope coverage | The training set must span the load range and the water temperature range the machine actually operates in. Coverage is recorded with the model. |
| Per-asset, not per-fleet | Models are fitted per chiller. Two identical machines on the same site do not share a model. |
| Recorded with the model | Training window, excluded periods, envelope, error band, fit statistics and the engineer who approved it. |

## Model health, drift and quarantine

| **Monitored** | **What it tells us** | **Action when it fails** |
|---|---|---|
| Residual mean on known-good periods | The model has developed a systematic bias. | Investigate; candidate for retraining. |
| Residual spread against the recorded error band | The model has become less precise than it was accepted at. | Widen confidence or retrain. |
| Operating-envelope coverage | The machine is now running outside what the model saw in training. | Residuals suppressed outside the envelope. |
| Input availability and validity | A required signal has degraded. | Dependent models marked unusable — see the dependency map. |
| Drift trend | Slow divergence caused by equipment, control or duty change. | Drift alert with lead time; scheduled retraining. |
| Post-repair behaviour | A machine that was repaired may have a legitimately new normal. | Re-baseline after verified major work. |

**A model that fails its health standard is quarantined. Quarantine means its residuals stop being used for diagnosis — they are not merely flagged as weaker. Every fault class that depends on that residual returns NO_DIAGNOSIS until the model is restored, and the Copilot states which model is out of service and why.**

## Model registry and versioning

| **Field** | **Required** |
|---|---|
| Model identity and version | Unique and immutable |
| Asset | The specific chiller, not the equipment class |
| Target signal | The one signal it predicts |
| Input list | Exact tags, with units |
| Training window and exclusions | Dates and reasons |
| Operating envelope | Load and temperature ranges covered |
| Accepted error band | The precision the model was approved at |
| Owner | A named reliability or data engineer |
| Status | Candidate / shadow / production / quarantined / retired |
| Rollback version | The last known-good version |
| Evaluation suite | The tests it must pass to be promoted |

**The model version travels with every residual into the evidence pack, so any diagnosis in the platform can be traced back to the exact model that produced the numbers behind it — including months later, after the model has been retrained.**

## Retraining

| **Trigger** | **Handling** |
|---|---|
| Drift detected | Scheduled retraining with engineer review |
| Equipment modified or overhauled | Re-baseline; the old normal no longer applies |
| Control strategy or setpoint regime changed | Re-baseline |
| Duty or seasonal envelope extended | Extend training coverage rather than replace the model |
| Instrumentation changed or recalibrated | Re-baseline any model using that tag |
| Verified major repair completed | Re-baseline once the machine has run steadily under the new condition |

### Retraining rules

- A model is never retrained on a period containing a known unresolved fault — that teaches the model that the fault is normal.
- A new version runs in shadow alongside the current one before promotion, and must beat it on the evaluation suite.
- Promotion is an approved, recorded change with a named owner and a rollback version.
- Retraining is never triggered automatically by a diagnosis being disputed.

## The trust contract between the layers

| **Layer** | **Supplies** | **Must never supply** |
|---|---|---|
| Equipment ML | Predictions, residuals, validity flags, model version, envelope status | A fault name, a cause, or a recommendation |
| FDD rules | Gates, persistence, fault class, confidence, the rule path taken | A free-text explanation |
| Copilot / LLM | Explanation, comparison, drafts, next-step proposals | A fault class, a number it did not retrieve, or an authorisation |
| Control Plane | Allow, approve, deny, and the audit record | A diagnosis |

## What must stay deterministic

These components carry safety, money and legal consequence. None of them may be probabilistic, and none may be delegated to a model.

| **Component** | **Why it must be deterministic** |
|---|---|
| Operating gates | They decide whether any judgement is permitted at all. |
| Fault isolation path | It must produce the same class from the same residuals, every time, and be auditable line by line. |
| Persistence and volatility rules | They separate a fault from a passing disturbance. |
| Sensor-bias checks | They stop instrumentation faults being reported as equipment faults. |
| Priority calculation | The number drives crews, cost and SLA exposure, and must be explainable to a customer. |
| Work order state machine | Illegal transitions must be impossible, not merely unlikely. |
| Scope, RBAC and tenant isolation | One probabilistic mistake here is a data breach. |
| Approval routing | Who must approve what is a policy question, not a prediction. |
| Idempotency keys | A retry must never create a second work order. |
| SLA clocks and audit writes | They are evidence, and evidence cannot be approximate. |
| Safety interlocks and permits | Safety is never inferred. |

## ML layer service targets

| **Measure** | **Target** |
|---|---|
| Residual availability during valid running periods | 99% or better per asset |
| Models in production meeting their health standard | 100% — anything failing is quarantined, not tolerated |
| Diagnoses issued while a required model was quarantined | Zero |
| Gate correctness on the labelled test set | 100% — gates are rules, not predictions |
| Drift detection lead time before residuals become unusable | Measured and improving |
| Faults later attributed to instrumentation rather than equipment | Falling — tracked as a data-quality metric, not a diagnosis failure |
| Model version present in the evidence pack | 100% |
