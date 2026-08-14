/**
 * **The only component permitted to render a number.**
 *
 * Enforced rather than agreed: a test greps the source for `toFixed(` outside this file, and
 * a DOM assertion checks that every numeral in an answer card sits inside a `data-figure`
 * element. The rule exists because a number formatted twice is a number that can disagree
 * with itself — and the back end already rendered every figure exactly once, which is what
 * lets the numeric audit compare exact values rather than pick a tolerance.
 *
 * So this component **never formats**. It prints `figure.text`, which the back end produced.
 *
 * The absent case is the one that matters most. `never measured`, `0` and `—` are three
 * different claims and only one of them is true for condenser flow on this plant, so an
 * absence renders as *the words the back end chose* — muted, italic, and in the body face
 * rather than the mono face, so it reads as a sentence rather than as a missing value.
 */

import type { FigureFrame } from '@/lib/frames';

/** Stagger index, so figures rise in the order they streamed. Capped: past ~8 the delay
 *  stops reading as sequence and starts reading as lag. */
export function FigureView({ figure, index = 0 }: { figure: FigureFrame; index?: number }) {
  const absent = figure.value === null;

  return (
    <div
      className="figure"
      data-figure={figure.name}
      data-absent={absent}
      style={{ animationDelay: `${Math.min(index, 8) * 28}ms` }}
    >
      <span className="name">{figure.name}</span>
      <span>
        {/* figure.text, never figure.value — the back end formatted it once, already. */}
        <span className="value">{figure.text}</span>

        {!absent && figure.verdict !== 'no_band' && (
          <span className="badge verdict">{figure.verdict} for this asset</span>
        )}

        {/* A residual never travels without its fit. Chiller 1's current model runs at
            nRMSE 48.03 and is out of band in 402 of 412 high-head readings, so the alarm
            may be an artefact of the model rather than a fault. Badged, never hidden —
            and the badge carries the words and the number, so colour is not the signal. */}
        {figure.poor_fit && figure.model_nrmse !== null && (
          <span className="badge warn" title="the model behind this residual fits poorly">
            poor fit · nRMSE {figure.model_nrmse}
          </span>
        )}
      </span>
    </div>
  );
}
