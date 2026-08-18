'use client';

/**
 * The rail's collapse state, and the motion that expresses it.
 *
 * **Why the two halves use different techniques.** GSAP's own performance guidance is to
 * animate transform and opacity and to avoid `width`, because layout properties trigger
 * reflow. But a rail collapse *is* a layout change — that is the entire point of it, and a
 * transform cannot fake giving the content column 172 more pixels. So:
 *
 * - **The width** is a CSS transition on `grid-template-columns`. A real layout change,
 *   done by the browser, which optimises it better than JavaScript ticking a width per frame.
 * - **The labels** are GSAP `autoAlpha` and `x`, staggered. Pure compositor work, and it is
 *   what makes the change read as one movement rather than a jump.
 *
 * **Motion here expresses cause and effect** — you pressed collapse, it narrowed — which is
 * the bar the motion-design principles set. It is not decoration, and there is none of it
 * anywhere a reading is displayed.
 *
 * **`prefers-reduced-motion` is handled by `gsap.matchMedia()`**, not by a hand-rolled check.
 * Under `reduceMotion` the labels change state with `duration: 0`: the rail still collapses,
 * because that is a function rather than an effect, and only the movement is removed. This
 * matters for vestibular disorders, and the 94-rule accessibility pass regresses without it.
 *
 * **The state persists.** Re-collapsing on every navigation is the detail that makes software
 * feel unfinished, and the rail is on every surface.
 */

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { useCallback, useEffect, useRef, useState } from 'react';

const STORAGE_KEY = 'synex.rail.collapsed';

/** The locked motion budget. `mvp/DESIGN-HANDOFF.md` §2 — not a per-component choice. */
const DURATION = 0.17;

/** Exits run shorter than entrances so the interface feels responsive rather than draggy. */
const EXIT_RATIO = 0.7;

/** Per-item offset. Long enough to read as a sequence, short enough not to read as lag. */
const STAGGER = 0.02;

export function useRailCollapse() {
  const railRef = useRef<HTMLElement | null>(null);
  // `null` until the stored value is read, so the first paint does not flash the wrong
  // width — the shell reads this to decide whether to animate at all.
  const [collapsed, setCollapsed] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(STORAGE_KEY) === '1');
    } catch {
      // Private browsing, or storage disabled. A rail that refuses to render because it
      // could not remember a preference would be a worse failure than forgetting one.
      setCollapsed(false);
    }
  }, []);

  const toggle = useCallback(() => {
    setCollapsed((was) => {
      const next = !was;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
      } catch {
        /* forgetting the preference is survivable; failing to collapse is not */
      }
      return next;
    });
  }, []);

  useGSAP(
    () => {
      // Nothing to animate before the stored value is known, and animating from a guessed
      // state is how a rail flashes open on every page load.
      if (collapsed === null) return;

      const mm = gsap.matchMedia();

      mm.add(
        {
          motion: '(prefers-reduced-motion: no-preference)',
          reduceMotion: '(prefers-reduced-motion: reduce)',
          // Below 640px the rail is a bottom bar and cannot collapse, so no handler runs
          // there at all — matchMedia reverts anything it created when it stops matching.
          wide: '(min-width: 640px)',
        },
        (context) => {
          const { reduceMotion, wide } = context.conditions as Record<string, boolean>;
          if (!wide) return;

          const duration = reduceMotion ? 0 : collapsed ? DURATION * EXIT_RATIO : DURATION;

          gsap.to('.navitem .long, .railgroup h2 span, .railgroup h2', {
            // `autoAlpha` sets visibility as well as opacity, so a faded label is also
            // removed from hit-testing rather than sitting invisible over the icon.
            autoAlpha: collapsed ? 0 : 1,
            x: collapsed ? -6 : 0,
            duration,
            stagger: reduceMotion ? 0 : STAGGER,
            ease: collapsed ? 'power2.in' : 'power2.out',
            overwrite: 'auto',
          });
        }
      );

      return () => mm.revert();
    },
    { scope: railRef, dependencies: [collapsed] }
  );

  return { railRef, collapsed: collapsed ?? false, ready: collapsed !== null, toggle };
}
