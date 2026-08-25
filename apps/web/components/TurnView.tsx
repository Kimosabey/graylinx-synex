'use client';

/**
 * One exchange in the Copilot transcript — the question, and everything the turn produced.
 *
 * **Why this is a component and not a block inside the page.** Until 2026-08-18 the Copilot
 * rendered exactly one turn and replaced it on every question. `docs/10-product/05-…` §5.3
 * describes the product entirely in chained exchanges — *"Create a work order for **this**"*,
 * *"Close **this** WO"* — and the back end resolves those pronouns against six remembered
 * turns. A surface that shows one turn cannot show what "this" refers to.
 *
 * **Each turn carries its own question.** An answer scrolled back to, with the question it
 * answered no longer on screen, is the reading failure this prevents: the refusals are the
 * most important thing the Copilot says, and *"no diagnosis"* means nothing without the
 * question it declined.
 *
 * **The heading ids are per turn.** Six turns each with `id="an"` is six duplicate ids, which
 * breaks `aria-labelledby` for every one of them — a screen reader follows the first match and
 * announces the wrong section. They are suffixed with the turn id instead.
 */

import { IconHalt } from '@/components/Icons';
import { AnswerText } from '@/components/AnswerText';
import { ConfirmWork } from '@/components/ConfirmWork';
import { Inspector } from '@/components/Inspector';
import type { TurnState } from '@/lib/useTurn';

/** What a reader sensibly asks after each kind of answer. Deterministic, from the route. */
/** How a day reads in a question somebody would type: `2026-04-09` → `9 April`. */
function dayInWords(iso: string | undefined): string {
  if (!iso) return '';
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return '';
  return `${parsed.getDate()} ${parsed.toLocaleString('en-GB', { month: 'long' })}`;
}

function followUpsFor(turn: TurnState): string[] {
  const skill = turn.route?.skill ?? '';
  const machine = turn.equipmentKey?.replace('_', ' ');

  if (skill === 'refuse') return ['What equipment do we have?', 'What happened across the plant?'];

  // **The offers name the episode the answer was about.** They used to read "Raise a work
  // order" and "What should I check?" with nothing attached, which worked only while the
  // interface carried a selection to attach them to. Once the episode was read from the
  // question instead, those bare sentences started coming back asking *which* episode — so
  // the product was offering a question it would then decline to answer. The evidence frame
  // names the machine, the fault and the day, so the offer can say them.
  const day = dayInWords(turn.evidence?.day);
  const fault = turn.evidence?.fault_label;
  if (machine && day) {
    return [
      `Raise a work order for ${machine} on ${day}${fault ? ` for ${fault}` : ''}`,
      `What should I check on ${machine} on ${day}?`,
      `Did the repair work on ${machine} on ${day}?`,
      `How is ${machine} doing?`,
    ];
  }

  // A machine with no episode behind it: the answer covered the asset rather than one day, so
  // the offers stay at that level rather than inventing a date to attach to.
  if (machine) {
    return [
      `How is ${machine} doing?`,
      `What happened on ${machine}?`,
      'What happened across the plant?',
    ];
  }
  return [
    'What happened across the plant?',
    'What happened on chiller 1?',
    'Do the numbers in the report match the plant?',
  ];
}

export function TurnView({
  turn,
  isLast = false,
  onAsk,
}: {
  turn: TurnState;
  isLast?: boolean;
  onAsk?: (question: string) => void;
}) {
  const followUps = followUpsFor(turn);
  const refused = turn.state?.state === 'NO_DIAGNOSIS' || Boolean(turn.refusal);
  const graded = turn.audits.find((a) => a.findings);
  const notes = turn.audits.filter((a) => !a.findings);
  const uid = (name: string) => `${name}-${turn.id}`;

  return (
    <article className="turn" aria-label={`Question: ${turn.question}`}>
      <p className="turn-question">{turn.question}</p>

      {/* **Whether a model wrote this, on the answer rather than inside the Inspector.**
       *
       * It was already emitted on the `state` frame and shown one fold down, and the question
       * "is it actually using the models?" was asked three times in one evening — which is a
       * failure of placement, not of instrumentation. Four of the five skills spend no model
       * at all and that is the design, so the badge has to say which happened plainly enough
       * that nobody has to open a panel to find out.
       *
       * `null` until the state frame lands, so a streaming turn does not claim either. */}
      {/* **Three kinds of machinery, named separately, because they fail differently.**
       *
       * `CONTEXT.md` §5 splits the work three ways and a reader cannot see the split from an
       * answer: the ML layer says whether a reading is abnormal, deterministic rules name the
       * fault and set priority and grant permission, and the language model only ever puts it
       * into English. Collapsing that into "AI answered" is exactly the impression the
       * separation law exists to prevent — and "is it actually using the models?" was asked
       * three times in one evening, which is what an invisible split costs.
       *
       * The ML badge appears whenever a residual is on the turn: a residual *is* a trained
       * model's output, so a figure with a band behind it is the ML layer having spoken. */}
      {turn.state && (
        <p className="turn-kinds">
          {turn.figures.length > 0 && (
            <span className="kind" data-kind="ml" title="A trained model produced these residuals — the reading against this asset's own healthy band.">
              ML · {turn.figures.length} residual(s)
            </span>
          )}
          <span className="kind" data-kind="rules" title="Deterministic software: the fault label, the gates, the priority formula and the Control Plane. None of it is a model.">
            Rules · gates and priority
          </span>
          <span className="kind" data-kind="llm" data-used={turn.state.used_model ? 'yes' : 'no'}>
            {turn.state.used_model
              ? 'Language model · wrote the wording'
              : 'Language model · not used'}
          </span>
        </p>
      )}

      {/* The stream's own stages, while it runs. A turn that shows nothing for several seconds
          reads as a hang; naming the stage says the work is real and which part of it is
          happening. It disappears when the answer arrives — progress is not a result. */}
      {turn.streaming && turn.stages.length > 0 && (
        <p className="turn-stage mono" aria-live="polite">
          {turn.stages[turn.stages.length - 1].stage}…
        </p>
      )}




      {/* **The draft is only a draft until somebody says so, and this is where they say it.**
          Offered on `NEEDS_APPROVAL` and only when the state named an episode — a confirm
          button with nothing behind it would be a control that cannot act. */}
      {turn.state?.state === 'NEEDS_APPROVAL' && turn.state.awaiting_approval_for && (
        <ConfirmWork episodeId={turn.state.awaiting_approval_for} />
      )}

      {/* D-015. A refusal gets its own card, its own rule and its own heading — and the accent,
          never red. A NO_DIAGNOSIS is a correct outcome and the most common one on this data;
          colouring it like an error would make an answer look like a bug. */}
      {/* **A refusal with a structured frame, and a refusal with only text, are different
          shapes of the same state.** `state: NO_DIAGNOSIS` always arrives; the `no_diagnosis`
          frame only does when gates actually failed. Requiring both meant the answer card was
          skipped (because `refused`) *and* the refusal card was skipped (because there was no
          frame) — so the tokens streamed in and rendered nowhere. A turn that produced text and
          displayed none is the worst of the three possible bugs here, because it looks like the
          product hung. */}
      {refused && !turn.refusal && turn.text && (
        <section className="card refusal measure" aria-labelledby={uid('nr')}>
          <h2 id={uid('nr')}>
            <IconHalt className="ico" style={{ verticalAlign: '-2px', marginRight: 6 }} />
            No diagnosis — a result, not a failure
          </h2>
          <AnswerText text={turn.text} />
        </section>
      )}

      {refused && turn.refusal && (
        <section className="card refusal measure" aria-labelledby={uid('nd')}>
          <h2 id={uid('nd')}>
            <IconHalt className="ico" style={{ verticalAlign: '-2px', marginRight: 6 }} />
            No diagnosis — a result, not a failure
          </h2>
          <AnswerText text={turn.refusal.text} />
          {turn.refusal.failed_gates.map((g) => (
            <div className="gate" key={g.gate}>
              <strong>{g.gate}</strong>
              <div>{g.why}</div>
              <div className="what">What would change this: {g.what_would_change_it}</div>
            </div>
          ))}
        </section>
      )}

      {turn.text && !refused && (
        <section className="card measure" aria-labelledby={uid('an')}>
          <h2 id={uid('an')}>Answer</h2>
          <AnswerText text={turn.text} />
        </section>
      )}


      {/* The working, gathered under the answer it belongs to and closed by default. Every
          frame this turn produced is in here — route, evidence, provenance, figures, checks —
          rather than stacked as separate cards down the page, where reading how one answer was
          reached meant scrolling past the machinery of the one before it. */}
      <Inspector
        route={turn.route}
        figures={turn.figures}
        evidence={turn.evidence}
        audits={turn.audits}
        usedModel={Boolean(turn.state?.used_model)}
      />

      {/* **What to ask next, from what this turn actually did.**
       *
       * Derived from the route rather than generated: the skill that answered determines what
       * a reader sensibly asks next, and a suggestion that came from a model would be a
       * fourth place a model could put words on the screen. A plant overview leads to a
       * machine; a machine leads to its signals; an answer about one episode leads to the
       * work it would raise.
       *
       * Only on the last turn — every answer carrying its own follow-ups turns a transcript
       * into a wall of buttons. */}
      {isLast && !turn.streaming && onAsk && followUps.length > 0 && (
        <div className="followups">
          <span className="followups-label">Next</span>
          {followUps.map((q) => (
            <button key={q} type="button" className="chip" onClick={() => onAsk(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      {turn.error && <p className="muted">Stream error: {turn.error}</p>}
    </article>
  );
}
