# Thermynx end to end — Reports, Work Orders, Nyx Chat, Nyx Resolve, Anomalies

Read out of the Thermynx repository (`d:\Harshan\graylinx-things\thermynx`) on 2026-08-19,
cross-checked against the live code rather than taken from its planning documents alone —
that repository has run through plan v3 through v6, and several of its own older documents
describe a design that was later changed, fixed, or abandoned without the document being
updated. Where a claim below rests on a document rather than code, that is said explicitly.
Companion to `03-from-thermynx.md` (what Synex adopts) — this document does not make adoption
decisions; it is a record of how Thermynx's own features work today, for reference.

This is a study of another product's mechanism, not a comparison. Naming question N1 (how
Synex and Thermynx relate) is unresolved, and nothing here should be read as positioning one
platform relative to the other.

---

## 1. The model roster and AI architecture, once — every feature below reuses it

All inference is local Ollama, zero-egress by policy. Five roles, resolved by name rather than
hardcoded, the same indirection principle `03-from-thermynx.md` §1a already records:

| Role | Model | Job |
|---|---|---|
| Narration / audit | `phi4` (14B) | Writes narrated answers, runs the self-critique pass, ranks candidates in Resolve |
| Tool execution | `devstral` (24B) | The ReAct tool-calling loop; also NL→SQL generation |
| Reasoning / composition ("the brain") | `gemma4:26b-a4b-it-qat` | Planning, final answer composition, multi-agent synthesis — the only reasoning-tier model, not a toggle between tiers |
| Vision | `llama3.2-vision` | `/vision/*` endpoints |
| Embeddings | `nomic-embed-text` (768-dim) | RAG retrieval, hard-locked local regardless of provider |

An external model (`claude-opus-4-8`) appears only as an optional offline eval judge and as the
judge that picked this roster during a bake-off — never in the live answer path.

**A documented model was already retired.** The repository's own architecture-inventory
document lists `codestral` for SQL generation and `gemma4:12b` for planning; both are retired in
the current code, which unconditionally maps `sql → tool` (devstral) and `planner/composer →
brain` (the 26B model). Some comments inside the code's own config file still list the retired
names — the drift is not only in the documentation, it is in stale comments in the code too.

**Architecture inventory, in one pass:**

- **Orchestration** — three LangGraph engines: a single-agent path, a ReAct tool-calling path,
  and a multi-agent orchestrator that runs several ReAct specialists in parallel and synthesises
  their findings. A router picks among eight dispatch intents.
- **RAG** — mature mechanics (hybrid dense+keyword retrieval, HNSW index, a reranking pass,
  an adaptive relevance floor) sitting over a thin corpus — measured at 19 chunks across 10
  documents at last check, and invoked on a small minority of calls.
- **Tool-calling** — native model function-calling, seven to nine tools depending on how they are
  counted, no MCP anywhere in the codebase.
- **Memory** — a shallow 24-turn raw transcript per thread, no summarisation, no long-term or
  cross-session memory. A durable state store exists for resuming a paused run, which is a
  different thing from conversational memory.
- **Routing** — deterministic and keyword-based first, with a small model as an arbiter only when
  nothing upstream resolves the question.

**The repository's own production-readiness verdict, quoted rather than softened:**

> "5.5 / 10 ... strong bones, but the quality path and the deploy/capacity layers are the gating
> work before this is dependable in production."

And on answer quality specifically: *"Answer quality is not dependable — the KB is unpopulated,
grounding is non-mandatory and over-flags, and the deep-reasoning model isn't running on this
box."* A separate AI-maturity score of 7.0/10 credits the architecture while marking it down for
the same two reasons.

**The single most consequential finding in that investigation** concerns a soft grounding check
on the single-agent answer path: a single claim flagged "suspicious" trips an automatic
regeneration whose instruction is to *"drop or clearly qualify any claim you cannot support"* —
without re-retrieving any evidence — and the hedged result silently replaces the original answer
the operator sees. A specific, well-evidenced answer can be wrongly flagged and overwritten with
a vaguer one, with no visible sign to the reader that a swap happened at all. As of this reading,
the fix for this specific failure mode had not yet landed; two related routing fixes had.

---

## 2. Nyx Chat — the conversational front door

**What a user experiences.** A single composer with no mode picker — the pitch is that it
routes every prompt itself. Sending a message is: classify the message, dispatch to whichever
path the classifier chose, stream the answer, then a separate best-effort call proposes up to
three follow-up questions. The answer streams behind a collapsible inspector showing the chosen
route and why, which model wrote the answer, every tool call and its result, the grounding
verdict, and citations. A welcome screen offers example prompts grouped by how much the question
asks for — data alone, an insight, a recommendation, or all three.

**The routing cascade, deterministic before it is ever a model's decision:**

1. A UI mode chip can force the route outright.
2. Regex preflight refusals — an oversized input, a prompt-leak or jailbreak attempt, a request
   to actuate equipment (nothing in this system can ever write to the plant), an unknown piece of
   equipment.
3. A conversational fast path answers greetings and "what can you do" instantly, no model call.
4. Deterministic extraction of which equipment and what time window the question concerns,
   carrying the last-named equipment forward across turns.
5. An ordered keyword table; naming two pieces of equipment forces the multi-agent path.
6. A scope gate refuses anything with no equipment and no domain vocabulary before any model is
   asked.
7. Only if nothing above resolved it: a small model, strict JSON output, a few seconds' timeout,
   asked to pick among the eight intents. Its answer is reconciled against the deterministic
   facts already extracted rather than trusted outright, and if it returns nothing usable the
   fallback is a tool-bearing path rather than a bare responder — a documented fix for an earlier
   defect where a routing miss silently removed a capability instead of degrading gracefully.

**Four dispatch shapes, each a LangGraph state graph:**

- **Quick answer** — fetch telemetry, assemble an honesty block about dead or never-measured
  signals, retrieve and rerank a handful of knowledge passages, an optional reasoning pass, then
  the narration model writes the answer, followed by an automated audit and a critique pass.
- **Investigate / root cause / optimise / maintenance / brief** — a ReAct loop: the tool-calling
  model chooses among the tools, bounded to eight steps with a stall breaker for repeated
  identical calls, then the reasoning model composes the final answer from what was gathered.
  A deterministic gate node force-calls the work-order proposal tool if a user clearly asked for
  one but the model's own tool loop never reached it — "the code decides *when* to propose; the
  model still writes *what* the diagnosis says."
- **Multi-agent** — a planner decomposes the question into up to four sub-tasks (with an optional
  pause for a human to approve the plan), each sub-task runs the entire investigate loop above in
  an isolated conversation, and a synthesis pass composes the combined answer from the
  specialists' actual findings.
- **Natural-language query** — one model-generated `SELECT`, checked by a hard security
  validator (read-only, single statement, no comments, an allow-listed set of tables and columns,
  a mandatory row limit, no relative-time functions), one bounded and re-validated repair
  attempt if the first query fails.

**Deterministic versus model-driven, precisely.** Every routing decision through step 6 above,
every refusal, the equipment/time extraction, the SQL security validator, the six-part automated
audit (a numeric-claim check, an equipment-mention check, a citation check, a language check, a
never-measured-signal check, a phantom-work-order check — all pattern-based, no model call), and
the decision of *whether* to propose a work order at all, are all deterministic code. What the
model is trusted with: the routing arbiter as a last resort, the reasoning and narration passes,
tool selection and argument construction, task decomposition and synthesis in the multi-agent
path, the critique pass, and the SQL query text itself (which is untrusted output, checked before
it runs). Nothing any tool can call ever writes to the plant.

**Gaps found, as of this reading:** an older internal document describing chat's memory as
broken across most answer types is now stale — memory has since been wired into every dispatch
path; that document should not be read as current. Separately: knowledge retrieval is exercised
by only a small fraction of the evaluation suite's cases, so its measured coverage understates
how much of the system it actually touches; claim-level numeric grounding exists in code but is
switched off by default, so today's audit works at the level of a sentence, not a re-derived
number; automatic regeneration on a failed grounding check is enabled on the quick-answer path
only, not on the multi-step paths; a user cannot declare which of the four question "layers" they
want, so the system infers it every time; and first-token latency on the reasoning-heavy paths
was measured at 13 to 19 seconds, visible in every live demo.

---

## 3. Nyx Resolve — the fault-to-fix case lifecycle

**What a technician or reliability engineer experiences.** A case opens with a fault label, a
severity, an evidence strength, and — for the fault classes the trained detection model itself
calls ambiguous — a curated differential. The reader gets a plain-English explanation, then
either nothing further to do, or one discriminating question at a time, never a full checklist
dropped at once. Each answer is tapped from options with a fixed effect (confirm, eliminate, or
keep undecided), or entered as free text, and is marked measured, estimated, or unsure. As
candidates are eliminated the reader watches the field narrow, with a visible trail of which
check eliminated which cause. A check nobody can actually perform gets an honest "could not
check — pass it on" rather than a disguised skip. A stuck case has three ways out: sideways to a
technician with an inspection job, up to a supervisor for authority, or deferred with a mandatory
follow-up date. Once findings settle a root cause, the reasoning model re-explains with the
technician's own answers folded in, names the specific failed component, attaches the
corresponding corrective and preventive checklist items, and a human commits the work order — the
case cannot close until that work order is itself closed.

**The state machine** is nine states enforced by an explicit adjacency table: `detected →
explained → awaiting_findings → root_caused → actioned → closed`, with `escalated` and
`deferred` branching off `awaiting_findings` and rejoining it, `dismissed` reachable from any
non-terminal state, and `actioned → root_caused` for a reopened case on recurrence. An illegal
transition raises an error rather than being silently allowed, every write is optimistically
locked so two people editing one case cannot clobber each other, and closing a case is refused
server-side — not merely in the interface — unless its linked work order is itself closed or
cancelled.

**The differential/narrowing mechanism — the cleanest deterministic/AI split of anything covered
here.** Only the fault classes the trained detection model itself declares ambiguous get a
differential; each has a hand-authored list of candidate causes and discriminating questions,
where every answer option maps to a fixed elimination effect. Eliminating a candidate is a pure
function of the tapped answer: a confirmation never eliminates a sibling cause (two real causes
can coexist), and "can't tell" changes nothing about any candidate. Which question is asked next
is chosen by how many still-live candidates it could move, tie-broken toward whoever is cheapest
to ask. None of this touches a model.

Layered on top, and strictly limited to *ordering* rather than *deciding*: an optional prior that
asks a model to re-rank candidates by how well this case's own readings fit them, so the most
useful question is asked first. The prompt to the model states outright that it is not
diagnosing and not eliminating anything, and the response is adversarially checked before use:
unrecognised candidates are discarded, every score is clamped away from zero (a zero-weight
candidate would be invisible to the question-selection arithmetic, which is elimination by
another name), and a response that carries no real signal is discarded entirely. The result is
written only to a separate ranking field — it is structurally incapable of marking a candidate
eliminated. Only a technician's tapped answer can do that. If the model or its hardware is
unavailable, a hand-derived deterministic fallback takes over, and if that yields nothing either,
every candidate is weighted equally, exactly as if no ranking existed.

Two failure modes are recorded from building this, and both are worth carrying forward as
warnings rather than curiosities: the larger reasoning model was tried for this same ranking task
first and degenerated into a repetition loop that silently produced nothing usable for every
case, which is why the smaller, stricter-schema model does the ranking instead; and the residual
sign convention was documented backwards in the ranking prompt for a period, during which the
model rationalised a plausible-sounding ranking anyway from the inverted premise — recorded
elsewhere as *"the failure mode to fear."*

**Deterministic, no model call:** case detection and seeding, severity and evidence-strength
labelling, grouping same-day fault labels into one event and choosing which leads, four
instrumentation-integrity checks (a flow contradiction, an implausible efficiency figure, a
flatlined signal, a model that cannot see its own inputs), the entire elimination mechanism above,
the 131-item checklist library, every gating signal that decides whether a case can progress or
is stuck, and the escalation target and suggested assignee (explicitly a skills match against the
fault label, not verified routing).

**AI-driven:** the explain and root-cause narrative stages, which reuse the same reasoning/tool
loop as Nyx Chat; the candidate-ranking prior described above; and one narrowly-scoped extraction
of the failed component's name from the root-cause narrative, which falls back to a fixed
vocabulary match if the model's answer does not comply.

**Gaps found, as of this reading:**

- **The checklist library and every discriminating question are engineering judgement, never
  checked by a refrigeration engineer** — the single largest open risk recorded for this feature,
  because an unreviewed discriminator does not merely risk a wrong answer once; it eliminates the
  correct cause with confidence, and nobody re-examines a settled question. The repository's own
  discovery pass measured only a small fraction of items reviewed, and dozens of candidates
  already eliminated on the live queue by discriminators nobody qualified had checked.
- **Case seeding is not on a schedule.** Nothing in the background job list calls the seeding
  endpoint, so the case queue can silently fall months behind the plant's actual detected faults —
  measured at several months behind at last check, including the plant's only critical-severity
  class never having reached anyone's queue.
- **The "all findings negative" heuristic is a known-flawed word match**, deliberately enforced
  only as a dismissible suggestion in the interface rather than a server-side gate, because a
  false positive there (misreading a genuine positive finding as negative purely from wording)
  would block real progress rather than merely offering a bad suggestion.
- **Eliminating a candidate from telemetry alone, with no human answer**, was designed and then
  deliberately not shipped as an automatic eliminator — it exists only as the ranking prior
  described above — on the explicit reasoning that automatic elimination on an unreviewed
  threshold is more dangerous than the ambiguity it would remove.
- **Learning from closed cases is deliberately not built**, on the same reasoning Synex has
  already inherited as a constraint: a wrong confirmed root cause would become the precedent every
  similar case retrieves afterward.
- **A case-level chat surface and photo attachments are unbuilt or partial** — a three-column
  conversation interface was built and then deleted rather than kept behind a toggle, and photo
  attachments are stored and displayed only, with no vision model involved.

---

## 4. Reports — three report types, all narration over pre-computed numbers

**What a user gets.** Three distinct reports, not the larger multi-domain design an earlier
planning document proposed (that design — evidence identifiers on every figure, per-domain
playbooks for meters, solar, generators, transformers — remains undelivered outside the one
domain actually built): an automatic daily digest with a headline and one recommendation, pushed
on a schedule; an on-demand daily operations report over a rolling window; and an on-demand
weekly or monthly executive report.

**The pipeline is the same shape for all three: a direct database query, deterministic Python
analytics, then a model narrates the result — never computes it.** Energy consumption, cost,
efficiency, remaining-useful-life estimates, and an automated data-quality assessment are all
plain arithmetic against the source tables. Only after that block of numbers is assembled does a
model see it, and its system prompt states outright that it may not invent, estimate, or alter
any number in it. The digest narration is capped at a couple of dozen words; the daily report's
narration is a short, three-heading summary; the executive report's narration spans several
headed sections at a larger scale, from the reasoning model rather than the narration model. Every
one of the three has a fully deterministic fallback narrative that substitutes for the model's
text if the model call fails, or if the model's own text is caught making a health claim over a
period the data cannot support — the same class of rule this document's own honesty discipline
depends on elsewhere.

**No report ever computes a figure through a model.** The knowledge-retrieval and evidence-audit
mechanisms built for the chat feature are not wired into any of the three report builders; reports
use an older, separate grounding layer that measures signal credibility arithmetically.

**Gaps found:** none of the three reports retrieves from the knowledge base to suggest a likely
cause — they narrate numbers, never a diagnosis; the executive report's savings and
maintenance-outlook sections are scoped to chillers only and explicitly skip every other asset
type, which is the large majority of assets on at least one deployed site; and the repository's
own changelog is stale — its last entry describes the original proof-of-concept report, predating
the honesty layer, the fault-aware digest, and the executive-report rewrite entirely, so it should
not be read as a record of current capability.

---

## 5. Work Orders — drafted by AI, created only by a person

**The lifecycle.** A work order carries a title, description, equipment, priority, a kind
(corrective, inspection, or authorisation), a source, optional diagnosis and recommended-action
text, an assignee, and a due date. It moves through an explicit state machine — open, assigned,
in progress, resolved, closed — with cancellation reachable from any open state, and every
transition, assignment, and comment is written to an append-only event log. A user either fills a
manual creation form, or opens an existing order to transition its state, assign a technician, or
add a comment.

**Drafting and creating are deliberately two different acts, and only a person performs the
second.** Inside the chat/agent tool-calling loop, a proposal tool can produce a draft — title,
diagnosis, priority, recommended actions — but the tool itself does not write to the database;
persistence happens only when a person reviewing the draft approves it. The draft is checked
before it can even be proposed: a diagnosis must cite a concrete reading or a named, dated
instrument reference, and a specific rule rejects a draft that blames a mechanical component when
the real explanation is a dead sensor. The interface renders a proposal as a distinct
review-required card; approving it is the action that actually creates the record, attributed as
coming from a chat approval rather than a verified identity. Repeated approvals of the same
proposal are deduplicated server-side by a deterministic identifier, not by trusting the
interface not to double-submit. The Anomalies surface reuses the identical propose-then-approve
pattern for its own "create work order" action, optionally carrying a model's causal explanation
into the diagnosis field.

A second, smaller point of model involvement: a technician-assignment endpoint asks a model to
rank candidate technicians by skill, load, and past success for a given job, falling back to a
deterministic skill-overlap match if the model is unavailable or returns nothing usable — again,
only a suggestion; assignment itself is a person's action.

**Gaps found:** a real defect was found and fixed where one of two chat processing paths — the
one without the proposal tool or its review card — could be reached by a work-order request and
fabricated a fake document instead of refusing, since fixed by a dedicated guard; and more
broadly, the safeguard that checks a draft's diagnosis text has no way to check whether the
underlying event the diagnosis describes actually happened — it validates the citation, not the
premise.

---

## 6. Anomalies — statistics, not diagnosis

**A different concept from a fault case, sharing a database and nothing else.** An anomaly here
is a raw statistical outlier: a metric whose value strays far enough from its own hour-matched
historical baseline. A fault case (Nyx Resolve, above) is a separate, heavier record seeded from
the trained detection model's own labelled fault episodes. A column exists to link one to the
other, but nothing in the current seeding path populates it — the two run side by side rather
than being connected in the software.

**Detection is arithmetic, not a trained model and not a language model.** A baseline mean and
spread is computed per metric from a minimum sample of recent history, and any reading beyond a
fixed multiple of that spread is flagged, with a stricter multiple marking it critical; a
confidence figure is derived purely from how far past that line the reading sits and how much
history backs the baseline. This runs both on a five-minute schedule and on demand. A separate,
switched-off-by-default pathway can also fold the trained detection model's own flagged faults
into the same table under a distinct label — off by default, so day to day this feature is pure
statistics. A tool inside the chat feature can call this same function on request, but it is
calling the identical deterministic arithmetic — the model never performs the detection math
itself.

**Model involvement is confined to explaining an anomaly after the fact.** A dedicated endpoint
sends an anomaly plus its surrounding readings to a model and asks for ranked likely causes,
documented explicitly as a hint for a person to weigh, not a causal conclusion. This is invoked
lazily, per anomaly, only when a reader asks for it.

**What a user sees:** summary counts by severity, and a grid of cards each showing the equipment,
the metric, a deviation score, a confidence percentage, the reading against its baseline, and a
plain-language description, with an on-demand "explain why" action and a "create work order"
action that reuses the propose-then-approve pattern above.

**Gaps found:** severity as currently thresholded carries no real information — essentially every
in-window anomaly was measured as the same top severity level, which the repository's own status
notes already flag as needing a different threshold rather than a single fixed multiple; photo or
attachment interpretation is not built; and no tool anywhere in this feature, or in the wider
system, can write to the plant — an anomaly's "explanation" is always a read-only suggestion.

---

## 7. Where AI is trusted with what, across all five

| Feature | AI writes | AI never decides |
|---|---|---|
| Nyx Chat | Narration, reasoning synthesis, tool selection, the routing arbiter as a last resort, the SQL text (checked before running) | Whether a request is in scope, whether an action is refused, what a retrieved figure says |
| Nyx Resolve | The explain/root-cause narrative, the order candidates are asked about | Whether a candidate cause is eliminated, confirmed, or kept; whether a case can advance or close |
| Reports | The prose narration of pre-computed figures | Any number in the report; whether the narration is allowed to stand if it claims health over an untrustworthy window |
| Work Orders | The draft diagnosis and recommended actions; a ranked suggestion of who to assign | Whether the order is created (a person approves), and its state transitions |
| Anomalies | An after-the-fact explanation of likely cause | Whether a reading counts as an anomaly, and its severity |

The pattern repeats deliberately across all five: a model may narrate, rank, draft, or suggest;
only deterministic code or a person may decide, eliminate, create, or close.

---

## 8. Where this repository's own documentation is stale

Worth stating plainly, because a future reader of the Thermynx repository could otherwise cite
any of these as current:

- The AI-architecture inventory's model roster names two models (`codestral`, `gemma4:12b`) that
  are retired in the current code.
- The Nyx conversation-context document describes conversational memory as broken across most
  answer types; memory has since shipped and is wired into every dispatch path.
- The report-structure review's finding that one chiller was excluded from reporting predates a
  fix that already made the equipment list dynamic — that finding no longer holds.
- The top-level changelog stops at the original proof-of-concept phase and names neither Resolve,
  the honesty layer, nor the executive-report rewrite — it should not be read as a status record.

## 9. Left open — worth reconfirming live, not read as settled from this pass

- Whether the reasoning-tier model is actually resident and engaged on the permanently-deployed
  hardware, versus falling back gracefully when it cannot fit alongside the other two models, was
  not resolvable by reading code alone — the relevant gate is a live hardware check.
- The knowledge-retrieval evaluation coverage, the first-token latency figures, and the case-queue
  staleness figure above are all snapshots at the time of reading, not properties of the design —
  each can move with a single deployment or a single scheduled job being wired up.
