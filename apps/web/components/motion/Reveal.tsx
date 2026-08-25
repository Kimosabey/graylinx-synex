'use client';

/**
 * **Reveal — the workhorse.** A staggered entrance for a list, a table body or a card grid.
 *
 * **What it expresses:** *these arrived together, in this order*. A queue of cases, a set of
 * checklist rows, a grid of assets — the stagger says they are one collection rather than one
 * thing that happens to be repeated, and the order it plays in is the order the reader should
 * read in. That is cause and effect: the page loaded, and here is what it holds.
 *
 * **Where it must not be used.** Not on a single residual, a priority band or a gate outcome.
 * Those are facts, and a fact that animates on its own is decoration next to a number somebody
 * dispatches a crew on. Reveal is for *collections*; the collection arriving is the event.
 *
 * **It animates the container's direct children.** No selector to pass, nothing to remember to
 * tag. Anything that renders a list of siblings can be wrapped and is done.
 *
 * **It fails visible, not invisible.** The tween is a `gsap.from()`, so the natural rendered
 * state is the end state: if JavaScript never runs, if GSAP fails to load, or if the component
 * hydrates late, the content is simply *there*. Nothing is hidden by CSS waiting to be
 * un-hidden, which is the failure mode that turns a reveal into a blank page.
 *
 * @example
 * <Reveal as="ul" className="checks" runKey={items.length}>
 *   {items.map((i) => <li key={i.id} className="row-check">{i.text}</li>)}
 * </Reveal>
 */

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { createElement, useRef, type ReactNode } from 'react';
import { DUR, EASE, MOTION_QUERIES, RISE, STAGGER, ensureMotion, type MotionConditions } from './tokens';

/** Deliberately narrow. A reveal wraps a container of siblings; it is not a general wrapper. */
export type RevealTag = 'div' | 'ul' | 'ol' | 'section' | 'tbody';

export interface RevealProps {
  children: ReactNode;
  /** Defaults to `div`. Use `ul`/`ol` for lists and `tbody` for table rows. */
  as?: RevealTag;
  className?: string;
  /**
   * Re-run the reveal when this changes — a row count, a selected episode id, a filter
   * string. Leave it out and the reveal plays once, on mount. Set it to something that
   * changes on every render and the list will animate forever, which is why it is explicit.
   */
  runKey?: string | number;
  /** Per-item offset in seconds. Defaults to the budget's 28ms. */
  stagger?: number;
  /** Accessible label, when the container is a landmark or a labelled region. */
  'aria-label'?: string;
  'aria-labelledby'?: string;
  role?: string;
  id?: string;
}

export function Reveal({
  children,
  as = 'div',
  className,
  runKey,
  stagger = STAGGER,
  ...rest
}: RevealProps) {
  const scope = useRef<HTMLElement | null>(null);

  useGSAP(
    () => {
      ensureMotion();
      const root = scope.current;
      if (!root) return;

      const items = Array.from(root.children) as HTMLElement[];
      if (items.length === 0) return;

      const mm = gsap.matchMedia();

      mm.add(MOTION_QUERIES, (context) => {
        const { reduce } = context.conditions as MotionConditions;
        // Reduced motion: the items are already in their final state, because `from` never
        // ran. The collection still arrives — it simply arrives without travelling.
        if (reduce) return;

        gsap.from(items, {
          // `autoAlpha` sets visibility as well as opacity, so an item that has not arrived
          // yet is also out of hit-testing rather than an invisible click target.
          autoAlpha: 0,
          y: RISE,
          duration: DUR,
          ease: EASE,
          stagger,
          overwrite: 'auto',
          // Hand the element back to CSS when the tween ends. Leaving inline transforms on a
          // table row is how a later hover or a stacked-card breakpoint stops working.
          clearProps: 'transform,visibility,opacity',
        });
      });

      return () => mm.revert();
    },
    // `revertOnUpdate` so a re-run reverts the previous tween instead of stacking a second
    // one on the same elements.
    { scope, dependencies: [runKey, stagger], revertOnUpdate: true },
  );

  return createElement(as, { ref: scope, className, ...rest }, children);
}
