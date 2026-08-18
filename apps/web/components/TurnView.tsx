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
import { Inspector } from '@/components/Inspector';
import type { TurnState } from '@/lib/useTurn';

export function TurnView({ turn }: { turn: TurnState }) {
  const refused = turn.state?.state === 'NO_DIAGNOSIS' || Boolean(turn.refusal);
  const graded = turn.audits.find((a) => a.findings);
  const notes = turn.audits.filter((a) => !a.findings);
  const uid = (name: string) => `${name}-${turn.id}`;

  return (
    <article className="turn" aria-label={`Question: ${turn.question}`}>
      <p className="turn-question">{turn.question}</p>

      {/* The stream's own stages, while it runs. A turn that shows nothing for several seconds
          reads as a hang; naming the stage says the work is real and which part of it is
          happening. It disappears when the answer arrives — progress is not a result. */}
      {turn.streaming && turn.stages.length > 0 && (
        <p className="turn-stage mono" aria-live="polite">
          {turn.stages[turn.stages.length - 1].stage}…
        </p>
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

      {turn.error && <p className="muted">Stream error: {turn.error}</p>}
    </article>
  );
}
