# Send-ready — the fault grouping question for Vishnu

Nothing below this line is internal. The whole file can be pasted, printed or rendered to
PDF without editing, which is the point: a file that mixes the message with notes about the
message is a file that eventually gets sent whole.

**Provenance.** Every figure in section 1 was read from **`shiva`**, the customer's snapshot
as delivered. That database holds **no simulation tables at all**, so nothing here can be
synthetic. All dates fall inside the measured window, which ends 2026-06-23.

Companion files: `VISHNU-MESSAGE.md` is the covering note for the whole MVP;
`VISHNU-TEAMS.md` is its chat form. This one is the single ask about grouping.

---

Hi Vishnu,

We've been counting things in the chiller plant data to work out what the MVP actually has to
handle, and we've found something I don't want to build on until you've looked at it.

This is split into **what the data says** and **what we think it means**. The second part is
where I need you — it's our reasoning, and no refrigeration engineer has checked any of it.

---

## 1 · What the data says

*Measured from the plant snapshot. No interpretation in this section.*

### 1.1 Twelve fault days would produce thirty-nine cases

Two chillers, **12 fault days, 674 faulted readings**. Open one case per machine, per day,
per alarm name — the obvious way — and that becomes **39 cases**.

### 1.2 One alarm returned for ten days, and never once at night

Chiller 1, `HIGH_HEAD_AMBIGUOUS`:

| Date | How long | Between |
|---|---|---|
| 9 Apr | 5 min | 15:20 |
| 10 Apr | 2¼ hours | 13:40 – 17:45 |
| 11 Apr | 1¾ hours | 12:20 – 14:20 |
| **15 Apr** | **7 hours** | 12:30 – 20:45 |
| 17 Apr | 2 hours | 13:50 – 20:25 |
| 18 Apr | 2¾ hours | 16:50 – 20:45 |
| 19 Apr | 6¼ hours | 12:30 – 19:30 |
| 20 Apr | 4½ hours | 11:25 – 20:35 |
| 21 Apr | 2¼ hours | 11:10 – 13:20 |
| 22 Apr | 5½ hours | 11:50 – 17:35 |

**412 readings in total, every one between 11:10 and 20:45.** Nothing overnight, and nothing
at all on 12, 13, 14 or 16 April.

### 1.3 Four alarms on one machine on one day — and one signal drives them all

17 April, chiller 1. These are the residuals the engine actually computed:

| Time | Alarm | Discharge P | Suction P | Disch T | **Current** |
|---|---|--:|--:|--:|--:|
| 12:15 – 19:35 | `COMPRESSOR_INEFFICIENCY` | −7.5 | −0.5 | −1.2 | **+26.5** |
| 13:50 – 20:25 | `HIGH_HEAD_AMBIGUOUS` | −3.3 | −0.8 | −2.6 | **+54.5** |
| 14:20 – 15:50 | `REFRIGERANT_SIDE_HIGH_HEAD` | −26.1 | −26.9 | +12.0 | **+51.9** |
| 13:30 – 19:45 | `POWER_HIGH_UNEXPLAINED` | −0.8 | −26.1 | −0.2 | **+59.0** |

This machine's **healthy** current residual is **−25.6**, with a normal range of **−38.7 to
−12.6**. Every figure in that last column sits far outside it.

And it is not just that day. Across all 674 faulted readings:

| Alarm | Readings | Current **out of band** | Discharge P out of band |
|---|--:|--:|--:|
| `HIGH_HEAD_AMBIGUOUS` | 412 | **402** | 82 |
| `REFRIGERANT_SIDE_HIGH_HEAD` | 61 | **53** | 5 |
| `COMPRESSOR_INEFFICIENCY` | 58 | **56** | 0 |
| `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION` | 29 | **29** | 3 |
| `CONDENSER_WATER_SIDE_UNSPECIFIED` | 25 | **25** | 13 |
| `POWER_HIGH_UNEXPLAINED` | 19 | **16** | 1 |
| `CONDENSER_LOW_FLOW` | 3 | **3** | 1 |

**Whatever the alarm is called, the current residual is out of band almost every time.**

### 1.4 That current model is the worst-fitting model on the machine

| Model | Chiller 1 | Chiller 2 |
|---|--:|--:|
| Condenser leaving temp | 2.95 | 1.68 |
| Discharge pressure | 5.38 | 2.90 |
| Suction pressure | 7.93 | 3.77 |
| Discharge temp | 36.41 | 3.41 |
| **Chiller current** | **48.03** | **2.65** |

*(nRMSE — lower is better.)*

Also worth knowing: **the compressor-power residual is empty on every reading.** Five models
are fitted per chiller, not six.

### 1.5 The two machines never faulted on the same day

| Machine | Fault days |
|---|---|
| Chiller 1 | 9, 10, 11, 15, 17, 18, 19, 20, 21, 22 April |
| Chiller 2 | 12, 13 April |
| **Both together** | **Never — not one day** |

Chiller 2's two days fall exactly in chiller 1's gap. On those two days chiller 1's condenser
water temperature reads a maximum of **0.0 °C** — it was off.

### 1.6 Two instrument problems — and the system handled them correctly

- Condenser **leaving-water temperature** reads **−273.2 °C** on 25 April, 14 May, 21 May and
  5 June. That is absolute zero, which is a sensor reporting its own failure.
- Condenser **flow has never recorded a reading at all** — zero non-zero values in **31,884**
  readings. Four of the six models depend on it.

**On the days that sensor misbehaved, the engine refused to diagnose.** 25 April returned *no
diagnosis* **53 times**; 14 May and 21 May produced no label at all. That part is working as
intended.

### 1.7 Two details that changed how we read all of the above

**Alarms run in sequence, not together.** The data holds one alarm per five-minute reading. On
15 April chiller 1 had one 7-hour high-head alarm with four shorter ones inside it — 50
minutes, 15, 10, and **one that lasted a single reading**.

**One class is inconsistent on its key signal.** `HIGH_HEAD_AMBIGUOUS` is supposed to show a
**negative** discharge-pressure residual — that is how it argues the water side is *not*
involved. On chiller 1 it is negative **252** times and **positive 160** times. On chiller 2
it is clean: negative in 17 of 18.

---

## 2 · What we think it means

*Our reasoning. Nobody qualified has checked it. This is the part to break.*

1. **The afternoon-only pattern suggests a load- and heat-driven fault** — the machine copes
   at 2 am and struggles in afternoon heat.

2. **A fouled condenser could explain the 17 April cluster.** Heat cannot leave the
   refrigerant, so head pressure rises, the compressor works harder, efficiency drops and
   refrigerant-side pressures shift. Four alarms, one dirty condenser, one brush.

3. **The machines appear to alternate** — lead and lag — which would explain both why they
   never fault together and why chiller 1 reads 0.0 °C on chiller 2's days.

4. **We are no longer confident about number 2.** Nearly every alarm on chiller 1 is driven by
   the **current** residual, and that model fits worst by a wide margin. It may be that
   chiller 1 is not sicker than chiller 2 at all — its current model may simply read high.

---

## 3 · Why this decides what we build

If every alarm opens its own case and every case raises its own work order, then 17 April
sends someone out **four times** for what may be one brush — or, if point 4 above is right,
for nothing at all.

The technician fixes it on the first visit. Visits two, three and four find nothing and get
closed as *no fault found*. After a few weeks of that the crew stops trusting the system, and
then it no longer matters how good the diagnosis is.

So we have written a rule that groups alarms which look like one problem into **one**
investigation with **one** work order — and it only ever *suggests* the grouping, so a person
can always split it. But that rule is only as good as the reasoning in section 2.

---

## 4 · What I need from you

**Seven questions. The first two matter most.**

**Q1 · Look at the 17 April table. Is that a fouled condenser, or a badly fitting model?**
The current residual is doing all the work, and that model has an nRMSE of 48 against chiller
2's 2.65. If the answer is the model, then model quality matters more than grouping does, and
we should build in a different order.

>

**Q2 · Which alarms must NEVER be grouped?**
This is the one that worries me. If a dirty condenser **and** a genuinely low refrigerant
charge are both present and we group them, the second one is hidden. A wasted visit costs a
morning. A missed undercharge costs a compressor.

>

**Q3 · Does the afternoon-only pattern fit fouling** — or does it point somewhere else: the
tower, ambient conditions, the load profile?

>

**Q4 · Do the two machines alternate by design?** And if so, could a cooling-tower problem
ever show on both chillers here? If it could not, then grouping across machines is the wrong
tool for this plant and we should build something else.

>

**Q5 · Can a real fault hide behind a dead sensor?** When an instrument fails we plan to raise
one job — *fix the instrument* — and hold the other alarms until it is repaired. Is that safe?

>

**Q6 · Is an alarm lasting one five-minute reading worth acting on at all**, or should it
never reach a person?

>

**Q7 · When a fault clears overnight and returns the next afternoon, is that one problem or a
new one?** It decides whether ten days become one case or ten.

>

---

One line each is plenty. Or give me ten minutes on a call and I will write it down.

Everything in section 1 is measured from the plant snapshot as delivered. Section 2 is ours,
and it is the part I would like you to disagree with.

Thanks,
Harshan
