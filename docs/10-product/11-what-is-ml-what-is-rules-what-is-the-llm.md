# 11. What Is ML, What Is Rules, What Is the LLM

Graylinx now contains three very different kinds of intelligence, and they do three very different jobs. If a reader cannot tell them apart, they will assume the language model is diagnosing the equipment. It is not, and it never will. This short chapter draws the line, because almost every question an engineer, an auditor or a customer asks about the platform turns out to be this question.

## What is deciding what

There are four kinds of software in the platform. Only one of them is allowed to be uncertain.

| **Kind** | **What it does** | **How it decides** | **Can it be wrong?** |
|---|---|---|---|
| Plain software | Stores records, moves work orders through their states, checks who is allowed to do what, keeps the audit trail. | Fixed code. The same input always produces the same output. | Only if it has a bug — never by design. |
| Deterministic rules | Operating gates, the fault isolation path, priority calculation, approval routing, verification pass or fail. | Written rules over measured values. Auditable line by line. | Only if the rule itself is wrong — and then it is wrong the same way every time, so it can be found and fixed. |
| Machine learning | Predicts what each signal should read when the equipment is healthy, so we can measure how far reality has moved away from it. | Models trained on the equipment’s own normal behaviour. | Yes — within a known error band, and only inside the operating range it was trained on. This is why gates and drift checks exist. |
| The LLM / agentic layer | Understands the question, plans which tools to call, explains the result in plain English, drafts the work order. | Language reasoning over evidence that other layers produced. | Yes — which is exactly why it is never the thing that names a fault or grants a permission. |

## Who decides what — the full split

| **Question** | **Decided by** | **Never decided by** |
|---|---|---|
| Is this reading abnormal, and by how much? | The ML model, as a residual | Rules or the LLM |
| Is the equipment in a fit state to be judged at all? | A deterministic gate | ML or the LLM |
| Has the pattern lasted long enough to be a fault? | A deterministic persistence rule | The LLM |
| Which fault class is this? | The deterministic FDD isolation path over the residuals | The LLM |
| How confident should we be? | The gate results plus the rule path | The LLM’s tone |
| What does all this mean in plain English? | The LLM | — |
| What should we do about it? | The LLM proposes; deterministic rules rank it; a human decides | The LLM alone |
| What priority number does this work get? | A deterministic formula over criticality, risk, SLA and production impact | The LLM |
| Is this person allowed to do this? | Plain software — the Control Plane | ML or the LLM |
| Did the repair actually work? | Post-work residuals judged by a deterministic verification rule | The technician’s note alone, or the LLM |
| What words does the user finally read? | The LLM, checked against the evidence pack | — |

| **THE RULE THAT KEEPS THIS HONEST** **The language model never invents a diagnosis. The FDD engine produces the rule path; the language model reads that path and explains it. If the rule path ends in NO_DIAGNOSIS, the language model says NO_DIAGNOSIS — it is not permitted to soften it into a guess.** |
|---|

## What the ML actually does, in plain English

Graylinx does not train models to recognise faults. It trains models to predict what healthy equipment should be doing right now, given the conditions it is working under. The gap between prediction and reality is the residual, and the residual is the signal everything else reasons about.

**What the model expected  −  what actually happened  =  the residual**

This is done deliberately. A plant produces enormous amounts of normal running data and very little fault data, and every fault looks slightly different. Modelling normal is therefore both more accurate and more transferable than trying to learn each fault directly — and it means a fault the platform has never seen before still shows up as an abnormal residual.

## What the ML cannot do

Stating this plainly is what makes the rest of the platform credible.

- **It cannot explain itself —** A residual says a reading is abnormal. It does not say why. The rules do that.
- **It cannot work outside its envelope —** outside the load and temperature range a model was trained on, its prediction is not trustworthy and its residual must not be used.
- **It cannot replace a sensor —** if a required input signal is missing or invalid, the models that depend on it stop producing usable output. No amount of AI compensates for an instrument that is not reporting.
- **It cannot separate what the sensors cannot separate —** some causes look identical through the available instruments. Refrigerant undercharge and an expansion-valve restriction cannot be cleanly separated with this sensor set, so the platform labels them together and says so rather than picking one.
- **It can go quietly stale —** if the equipment, the control strategy or the duty changes, a model slowly becomes wrong without announcing it. This is why model health and drift are monitored continuously, and why a failing model is taken out of service rather than left to mislead people.

## Where each kind lives

| **Layer** | **Kind of software** | **Produces** |
|---|---|---|
| Data and digital twin | Plain software | Clean, timestamped, hierarchy-aware signals |
| Equipment ML | Machine learning | Predictions and residuals with validity flags |
| FDD and reliability | Deterministic rules | Gates, persistence, fault class, confidence |
| Knowledge and retrieval | Retrieval plus the LLM | Sourced answers from approved documents |
| Copilot and agents | The LLM | Understanding, explanation, plans, drafts |
| Control Plane | Plain software | Allow, approve, deny — and the audit record |
| Execution and workflow | Plain software | Work orders, states, notifications, schedules |
