'use client';

/**
 * **PageEnter — spatial continuity between the eight surfaces.**
 *
 * **What it expresses:** *you moved, and the rail stayed*. Eight surfaces share one shell, and
 * a hard cut between them makes each navigation look like a fresh page load — which is exactly
 * the impression a product with one persistent rail should not give. The content column lifts
 * in while the bar and the rail hold still, so the shell reads as the frame and the surface
 * reads as what is in it.
 *
 * It is mounted **once, in `Shell`**, around `main.content`, and keyed on the pathname. No
 * surface has to remember to add it and no surface can add it twice.
 *
 * **The duration is 220ms, not 170ms**, matching the `settle` keyframe `globals.css` already
 * uses for an arriving answer. A whole column travels further than one card, and the two
 * moments should feel like the same product.
 *
 * **It fails visible.** A `from` tween, so the resting state is the rendered state: without
 * JavaScript the page is simply there. Under reduced motion the navigation still happens and
 * nothing moves.
 */

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { usePathname } from 'next/navigation';
import { useRef, type ReactNode } from 'react';
import { DUR_PAGE, EASE, MOTION_QUERIES, ensureMotion, type MotionConditions } from './tokens';

export function PageEnter({ children, className }: { children: ReactNode; className?: string }) {
  const pathname = usePathname();
  const scope = useRef<HTMLDivElement | null>(null);

  useGSAP(
    () => {
      ensureMotion();
      const el = scope.current;
      if (!el) return;

      const mm = gsap.matchMedia();

      mm.add(MOTION_QUERIES, (context) => {
        const { reduce } = context.conditions as MotionConditions;
        if (reduce) return;

        gsap.from(el, {
          autoAlpha: 0,
          // Up from below: the direction a thing takes when it is being brought forward,
          // rather than a sideways slide, which would imply the surfaces are ordered.
          // `CONTEXT.md` constraint 25 — the rail's order is display order, not a ladder.
          y: 10,
          duration: DUR_PAGE,
          ease: EASE,
          overwrite: 'auto',
          clearProps: 'transform,visibility,opacity',
        });
      });

      return () => mm.revert();
    },
    { scope, dependencies: [pathname], revertOnUpdate: true },
  );

  return (
    <div ref={scope} className={className}>
      {children}
    </div>
  );
}
