'use client';

/**
 * **ValueChange — a figure that changed, moving. Never a figure counting up.**
 *
 * ## Read this before using it
 *
 * The brief asked for a count-up. **A digit-interpolating count-up is not buildable in this
 * product and this component deliberately is not one.** The reason is the whole thesis: a
 * count-up puts numbers on screen that the plant never measured. A residual tweening from 0 to
 * −25.65 displays −4.1, −11.8 and −19.3 on its way, and a technician who glances during those
 * 170ms reads a residual that no instrument ever produced. On this data that is not a
 * hypothetical risk — the residual bands are asset-specific and *not zero-centred*
 * (`CONTEXT.md` §6), so an interpolated value is not merely imprecise, it is inside a
 * different verdict's range for most of the tween.
 *
 * So the rule this component enforces mechanically: **at every frame, the text on screen is
 * the exact string the back end produced.** There is one text node, it holds `value`, and
 * `value` is written by React before any tween starts. What animates is the node's transform
 * and opacity — its *presentation*. There is no interpolation anywhere in this file, no
 * arithmetic, and no second copy of the old value lingering beside the new one.
 *
 * It therefore also satisfies the two rules that constrain every number in this product:
 * `FigureView` remains the only component that renders a figure (pass it that figure's
 * `text`), and nothing here formats — `value` is printed verbatim.
 *
 * ## What it expresses
 *
 * *You changed something, and this figure answered.* Selecting a different episode, switching
 * the capability on a checklist, moving the verification window — the number moves because
 * you moved something. That is cause and effect.
 *
 * **Do not attach it to a figure that changes on its own** — a poll, a stream, a timer. Motion
 * with no cause is decoration, and this product does not put decoration next to a reading.
 *
 * Under reduced motion the value still changes; it simply does not travel.
 *
 * @example
 * <ValueChange value={figure.text} figure={figure.name} className="value" />
 */

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { useRef } from 'react';
import { DUR, EASE, MOTION_QUERIES, ensureMotion, type MotionConditions } from './tokens';

export interface ValueChangeProps {
  /**
   * The display string the back end already rendered. Printed verbatim — this component does
   * not format, round, parse or interpolate it, and it must never be handed a raw number to
   * turn into text.
   */
  value: string;
  className?: string;
  /** Passed through as `data-figure`, so a figure keeps its identity in the DOM. */
  figure?: string;
}

export function ValueChange({ value, className, figure }: ValueChangeProps) {
  const scope = useRef<HTMLSpanElement | null>(null);
  // The previously-animated value. `null` until the first pass, so the initial paint is
  // still — a figure that was always there did not just change, and React Strict Mode's
  // double-invoke lands on the `was === value` branch rather than firing a phantom tween.
  const previous = useRef<string | null>(null);

  useGSAP(
    () => {
      const was = previous.current;
      previous.current = value;
      if (was === null || was === value) return;

      ensureMotion();
      const el = scope.current;
      if (!el) return;

      const mm = gsap.matchMedia();

      mm.add(MOTION_QUERIES, (context) => {
        const { reduce } = context.conditions as MotionConditions;
        // Reduced motion: React has already written the new value. Nothing further to do —
        // and nothing further is *allowed*, because the state change is the part that must
        // survive.
        if (reduce) return;

        // A `from` tween, so the element's resting state is the finished state. The value on
        // screen is the new one for the entire duration; only where it sits changes.
        gsap.from(el, {
          yPercent: -32,
          autoAlpha: 0,
          duration: DUR,
          ease: EASE,
          overwrite: 'auto',
          clearProps: 'transform,visibility,opacity',
        });
      });

      return () => mm.revert();
    },
    { scope, dependencies: [value], revertOnUpdate: true },
  );

  return (
    <span ref={scope} className={className ? `value-swap ${className}` : 'value-swap'} data-figure={figure}>
      {value}
    </span>
  );
}
