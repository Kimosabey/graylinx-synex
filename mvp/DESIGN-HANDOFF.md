# Design handoff — Graylinx Synex

**For a designer or a design session starting cold.** Everything needed to design any screen
in this product without reading the codebase, and without accidentally undoing something
load-bearing.

Read §2 before anything else. It is short, and every rule in it exists because breaking it
would make the product dishonest rather than merely ugly.

---

## 1 · What this is

**Graylinx Synex — Intelligent Operations, Connected by AI.**

An AI layer over an existing industrial plant platform. The first vertical is water-cooled
chillers on one facility: about ten units, two of which can actually be diagnosed.

**Synex Copilot is not a feature of the platform. It is how the platform is used.** A user
asks in their own words; Synex resolves who they are, what they may see, what evidence
exists, what it means, what to do next, and — if approved — does it and proves it worked.

```
ASK → UNDERSTAND → FIND DATA → EXPLAIN → RECOMMEND → CREATE/ACT → VERIFY → REPORT → LEARN
```

**Audience.** Reliability engineers, technicians, supervisors, plant managers. People who
will be held responsible for a decision made on what this screen told them. Not consumers,
not executives browsing. They are technical, time-pressured, and correctly sceptical of
software that claims to know things.

**The thing that makes this product different from every other AI dashboard:** it refuses.
On the real data, the most common outcome is *"the checks did not pass, so no diagnosis"* —
5,309 slots against 674 faulted ones. **The refusal is the product.** A design that treats it
as an error state, an empty state, or something to minimise has removed the reason the
product exists.

---

## 2 · Locked — do not redesign these

| | Locked value | Why |
|---|---|---|
| **Brand** | `#0020B0` | Decision D-001. The whole colour system is derived and audited from it |
| **Token sheet** | `mvp/mock.html` `:root` block | The approved design. Copy it; do not re-palette |
| **Contrast** | WCAG 2.2 AA, both themes | 72 of 72 rendered pairs already pass; body text at AAA. Currently 94 automated rules, 0 violations |
| **Default theme** | Light, pinned | A demonstration must not change appearance because the room's laptop is dark |
| **Icons** | SVG, one family, consistent stroke | Never emoji — font-dependent, unthemeable |
| **Numbers** | One component renders them | See §4. Enforced by a test |
| **Motion** | ~170ms, `cubic-bezier(.2,.7,.3,1)`, 1–2 elements per view | The mock's own tokens. `prefers-reduced-motion` honoured |

**No WebGL, no heavy animation libraries.** This product's entire pitch is that it does not
overstate what the data supports. A parallax hero undercuts that in a way no copy can
recover. Motion should be used where it *means* something — evidence arriving before prose —
and nowhere else.

---

## 3 · The four semantic states, and why each must look different

These are not styling preferences. Each one exists because a specific failure happened.

### A refusal is **not** an error

`NO_DIAGNOSIS` means the checks did not pass, so nothing is claimed. It is a **correct
outcome and the most common one.**

- Must **not** be red, must not use a warning or error treatment, must not be an empty state
- Must look **deliberate** — its own card, its own colour, its own heading
- Must name the check that failed **and what would change the answer**
- Currently: accent-bordered card, calm surface, 4px left rule

> A refusal styled like an error reads as a bug. A refusal styled like a shrug reads as
> incompetence. It should read as *judgement*.

### An absence is **not** a zero and **not** a dash

Condenser flow has never recorded a value on this plant — 0 readings in 31,884. That is not
"0 m³/h" and it is not "—".

- Renders as **words**: *"never measured"*, *"no model is fitted for this signal"*
- Muted, italic, in the body face rather than the mono face, so it reads as a sentence
- **Never** a blank cell, which reads as agreement or as nothing-to-report

### A poorly fitted model is **badged, never hidden**

One machine's model runs at nRMSE 48.03 against the other's 2.65. Its alarms may be
artefacts of the fit rather than faults.

- The badge carries **the words and the number**, so colour is never the only signal
- Shown beside the clean machine deliberately — hiding the badly-fitted one is the
  temptation this product exists to resist

### An incomplete calculation says so

The priority formula names four inputs; three do not exist in this data. It shows its band
**and** lists what it could not include.

---

## 4 · Rules a design must not break

1. **Only one component renders a number.** The back end formats every figure exactly once;
   the UI prints that string. A number formatted twice can disagree with itself. Enforced by
   a test that fails on any formatting API elsewhere.
2. **Evidence appears before prose.** The answer is a *reading* of the evidence, not a
   summary the numbers were fitted to. Reversing the order makes the numbers look like
   illustration.
3. **Every artefact states its data window.** This is a static snapshot; a screen that does
   not say what period it covers lets the reader supply "now" from their own head.
4. **Unbuilt surfaces are shown disabled, not hidden.** A product that conceals its unbuilt
   half is exactly what this approach argues against.
5. **Tabular numerals in any column of figures**, so a stack of residuals can be compared
   down the page.
6. **Prose gets a measure** (~70 characters). Tables and evidence stay wide — they are
   scanned, not read.

---

## 5 · Every screen — built and unbuilt

Eight surfaces. Three exist today; five are the design work.

| Surface | Who | Holds | State |
|---|---|---|---|
| **Copilot / Ask** | everyone | The front door. Ask, investigate, draft, verify | ✅ built |
| **Reports** | Manager, Analyst | Reconciliation, drill-down to source | ✅ built |
| **Work orders** | Supervisor, Technician | Jobs carrying their evidence; cannot close unproven | ◑ draft card only |
| **Case** | Reliability + Supervisor | The lifecycle between a named fault and a closed job | ✗ **needs design** |
| **Reliability workspace** | Reliability Engineer | Fault queue, residuals, the case it opens | ✗ **needs design** |
| **Supervisor queue** | Supervisor | Approvals, blocked cases, unproven closures | ✗ **needs design** |
| **Technician job pack** | Technician | The work, its checklists, findings with *cannot check* | ✗ **needs design** |
| **Administrator** | Administrator | Scope, approval matrix, policy version | ✗ **needs design** |

**FDD detection has no screen of its own.** It runs, and what it produces arrives as a case.
A queue of residuals is not something anyone acts on.

### Currently built, for reference

**Copilot** — persona switcher (labelled as a demonstration, not authentication) · 39
detected episodes as selectable chips · a residual chart against that asset's own band ·
composer · route trace · evidence figures · provenance · answer or refusal · six honesty
checks · work-order draft.

**Reports** — reconciliation table: every headline figure recomputed from source beside its
documented value, each row expanding to its source table, row count, plain-English basis and
a bounded sample.

---

## 6 · The flows to design

### Flow 1 · Fault → case → work order → verification *(the spine)*

The loop the whole product exists to close. Currently the first and last steps exist and the
middle does not.

```
detected episode → open a case → checklists → findings → root cause
                 → work order (carrying evidence) → work done
                 → post-work residuals → PASS / FAIL / UNKNOWN → close or reopen
```

**Design attention:**
- A case has **four different journeys** and they pause in different places: straight
  through (13 cases), needs a technician (26), broken sensor (2), model blind (2). Two
  thirds pause. A UI built only for the straight-through journey is a model viewer.
- A work order **cannot close unproven**. `UNKNOWN` is a permitted verification outcome and
  does **not** close the job.
- Reopening preserves the previous technician's findings.

### Flow 2 · The checklist, and *cannot check*

A technician works through checklist items. Three states, and the third is the important one:

| State | Meaning |
|---|---|
| `done` | checked, with a finding |
| `open` | not yet checked |
| **`cannot check`** | **this person cannot perform this check** |

**`cannot check` is not the same as `not applicable`.** Six "N/A" presses once opened a
blocking safety gate with zero evidence behind it. They must be visually and semantically
distinct, and a check the reader cannot perform should **collapse, not grey out** — a
greyed-out *"oil analysis — acid, moisture, metals"* still reads as a demand on whoever is
standing there.

### Flow 3 · Escalation — three routes, three artefacts

Not one "escalate" button. Three different things:

| Blocker | Goes to | Produces |
|---|---|---|
| No tool | a technician, matched by skill | an **inspection** work order |
| No authority, or cannot interpret | a supervisor | an **authorisation** work order — the task is the *question* |
| Wrong moment | nobody — parked with a reason and a date | nothing; nobody was called |
| Not sure | stays with you | nothing; it eliminates nothing |

The system **offers** the handoff rather than waiting to be asked, because a worker often
does not know they are out of their depth.

### Flow 4 · The differential — ruling a cause out

A flat checklist says *do all six of these*. A differential says *three causes fit; this one
test kills two of them.*

- Three effects: `confirm`, `eliminate`, `keep`
- **Elimination is irreversible.** An answer never resurrects a ruled-out cause
- Every discriminating question carries an explicit **"can't tell"** with *no effect at all*
- Two terminal states, and they must look different: **settled**, and **exhausted but not
  settled** — the honest *"we cannot separate these with the checks we have"*
- Every elimination records the check and the answer that caused it

### Flow 5 · Grouping — one problem, several labels

On one day, one machine carried **five fault labels at once**. Twelve equipment-days produce
**39 naive cases** — a 3.25× inflation. One plausible repair could raise five work orders.

The UI needs to show related labels as one problem *in the view* without rewriting the
underlying records. **Group in the display, never in the data.**

---

## 7 · Personas — capabilities, not ranks

Five personas. **A supervisor is not a more capable technician** — it is a different
capability: authority and records, not gauges. Ranking by seniority once routed a
refrigerant fault to a supervisor because one incidental records question outranked three
refrigeration measurements.

| Persona | Can |
|---|---|
| Reliability Engineer | view faults, view residuals, open a case |
| Technician | view faults, record findings |
| Supervisor | view faults, approve work, close work |
| Administrator | view faults, edit policy |
| Analyst | view faults, view residuals |

Neither the technician's nor the supervisor's capability set contains the other's. A design
implying a hierarchy would be wrong.

**Identity is currently a demonstration switcher, not authentication** — and every surface
must say so. There is no auth library and the snapshot's user tables are empty.

---

## 8 · The data, because it shapes every screen

Designing against imagined data will produce screens this plant cannot fill.

| Fact | Consequence for design |
|---|---|
| 12 equipment tables, **2 can be scored** | Ten of twelve refuse. Show them with *why not*, never filter them out |
| **5,309** `NO_DIAGNOSIS` vs **674** faulted | The refusal is the modal screen state |
| **39** episodes over **12** equipment-days | Queues are short; grouping matters more than pagination |
| Condenser flow: **0 readings ever** | Feeds 4 of 6 models. Whole branches refuse by design |
| One model at nRMSE **48.03**, another at **2.65** | Same fault label means different things per machine |
| Severity agreed for **1 of 9** labels | Most priorities render *unrated*, with a reason |
| 5 models fitted, design says **6** | One row always renders as a stated absence |
| Real data ends **2026-06-23 11:50** | Everything after is simulated and must be refused |

---

## 9 · Where a modern, distinctive direction could go

The constraints above are the floor, not the ceiling. Genuine opportunities:

- **The case as a spine, not a form.** Four journeys through one object. A timeline that
  shows where it paused and why would beat a tabbed form.
- **The differential as the signature element.** Candidate causes narrowing as questions are
  answered — a live, shrinking set with eliminated causes visibly struck out and *why*
  attached. Nothing else in this product's market shows reasoning being *closed off*.
- **Evidence as a first-class object.** It already travels with the work order. It could be
  draggable, citable, linkable — "this finding, because of this residual, on this day".
- **The honesty counters as ambient.** Refusals, badged figures and stated absences are
  running totals. A quiet persistent indicator of *how often the platform declined* is a
  differentiator no competitor would dare show.
- **Density.** This is an operations tool for people who scan. Consider a genuinely dense,
  keyboard-first layout rather than a spacious marketing-style dashboard.

**Avoid:** cream-and-serif editorial, near-black with one acid accent, and broadsheet
hairline columns. All three are the current defaults of AI-generated design and none is
right for an instrument that people make dispatch decisions with.

---

## 9a · Responsive — mobile first, and one persona genuinely lives there

**The technician is on a phone, in a plant room, possibly in gloves.** That is not a
hypothetical: the job pack, the checklist and *cannot check* are used standing at a machine.
The reliability engineer and the analyst are on a desktop with two monitors. Both are real,
and the same layout cannot serve both by scaling.

### Breakpoints

| Name | Width | Primary persona | Layout |
|---|---|---|---|
| **Small** | `< 640px` | Technician at the machine | Single column. Rail collapses to a horizontal scroller or a bottom bar. Evidence tables become stacked cards, never a horizontally scrolling grid |
| **Medium** | `640–1023px` | Supervisor on a tablet, approving | Single column, wider measure. Rail as a top strip. Two-up only where both halves are independently useful |
| **Large** | `1024–1439px` | Reliability engineer | Rail + content, as now. This is the design's home |
| **XL** | `≥ 1440px` | Two-monitor desk | Content stops widening at ~1120px. Extra width goes to margin, never to longer lines |

Current implementation folds the rail at `900px`; that is one breakpoint doing the work of
three and should be revisited as part of this design pass.

### Mobile-first rules

1. **Design the small screen first, then add.** The technician's screen is the constrained
   one, and it is the one where a wrong decision has someone standing in a plant room
   unable to proceed.
2. **Touch targets ≥ 44×44pt with ≥ 8px between them.** Gloves. The episode chips currently
   use a `::after` inset to reach 44px without visually inflating the pill — keep that
   pattern.
3. **Body text ≥ 16px on small.** Below that iOS auto-zooms on focus and the layout jumps.
4. **Never a horizontally scrolling page.** Wide content — the evidence table, the
   reconciliation table, the residual chart — scrolls **inside its own container**, and the
   page body never does. Currently verified at 375px with no overflow.
5. **The chart reflows, it does not shrink.** A 720×220 SVG squeezed into 340px is
   unreadable. On small: fewer axis ticks, the band and the extreme point kept, the
   per-point markers dropped. The band separation is the message and it survives.
6. **Reserve space for streamed content.** An answer that streams in must not shift the
   evidence above it. Skeletons or fixed minimum heights, not layout jumps.
7. **Safe areas.** Any fixed top or bottom bar respects the notch and the gesture bar.

### Per-screen responsive intent

| Screen | Small | Medium | Large |
|---|---|---|---|
| **Copilot** | Composer pinned to the bottom; evidence as stacked cards; route trace collapsed behind a disclosure | Composer inline; evidence as a two-column grid | As now — rail, single content column |
| **Reports** | Reconciliation becomes one card per figure: label, both values, agree marker. **Not** a scrolling table | Table with the source column dropped | Full four-column table |
| **Work order** | Priority and warnings first; evidence lines collapsed behind "14 pieces of evidence" | Evidence expanded | As now |
| **Technician job pack** | **This is the mobile screen.** One checklist item at a time, thumb-reachable *done / cannot check*, findings capture with the keyboard type set per field | Two-up: list and current item | List, item and evidence side by side |
| **Case** | Timeline vertical, one journey step per row | Timeline vertical, evidence in a drawer | Timeline horizontal or split with evidence |
| **Supervisor queue** | Cards, one approval per card | Two columns | Table with inline approve |

### What to verify, not assume

- 375px, 768px, 1024px, 1440px — and **landscape phone**, which is where fixed bottom bars
  usually break
- No horizontal page overflow at any width
- Reduced motion and largest system text size without layout breakage
- Both themes at every breakpoint — dark mode contrast is checked separately, never inferred
  from light

---

## 10 · Where things are

| | |
|---|---|
| Front end | Next.js App Router, TypeScript, port **3100** (3000–3003 are occupied) |
| Styles | `apps/web/app/globals.css` — tokens copied from `mvp/mock.html` |
| Components | `apps/web/components/` — `FigureView`, `ResidualChart`, `Shell`, `Icons` |
| The approved mock | `mvp/mock.html` — 7 screens, the design source of truth |
| Feature list | `mvp/FEATURE-REGISTER.md` — 147 features, 94 in the cut |
| Product truth | `CONTEXT.md` — settled; if a design contradicts it, the design is wrong |
| Naming law | `CLAUDE.md` §1 — enforced by a build gate over source and prose |

**Run it:** `cd backend && uvicorn app.main:app --port 8001` and
`cd apps/web && npm run dev`. Then `localhost:3100`.

**Check the work:** `npx @accesslint/cli scan http://localhost:3100` must report 0
violations across 94 rules, in both themes, before anything ships.
