'use client';

/**
 * The motion primitives, in the React Bits spirit and on the GSAP that is already installed.
 *
 * **Why these are local components and not a package.** React Bits is a copy-in library —
 * source you paste into your own tree and own from then on — not a maintained npm dependency.
 * Installing a wrapper around it would add a dependency this repo would have to hold to a
 * recorded reason, for code that would still need rewriting to honour the locked budget, the
 * reduced-motion contract and the rule that nothing decorative may sit beside a reading. So
 * the primitives live here, on `gsap@3.15` and `@gsap/react@2.1` which are already in
 * `package.json`, and nothing new was installed to build them.
 *
 * Four, and no more. Every one of them:
 *
 * - runs inside `useGSAP` with a scoped ref, so it cleans itself up on unmount;
 * - branches on `gsap.matchMedia()` for `prefers-reduced-motion`, never a hand-rolled check;
 * - animates transform and opacity only — no width, height, top or left;
 * - is `'use client'` on the primitive, so a server-rendered page can hold one without
 *   becoming a client component itself;
 * - fails *visible*: every entrance is a `from` tween, so the resting state is the rendered
 *   state and no content is ever hidden waiting for JavaScript that may not arrive.
 *
 * **The rule that governs all four:** motion expresses cause and effect. There is none of it
 * anywhere a reading, a residual, a priority band or a gate outcome is displayed on its own.
 * Those are facts, not moments.
 */

export { Reveal, type RevealProps, type RevealTag } from './Reveal';
export { ValueChange, type ValueChangeProps } from './ValueChange';
export { PageEnter } from './PageEnter';
export { Pressable, type PressableProps } from './Pressable';
export { DUR, DUR_EXIT, DUR_PAGE, EASE, EASE_EXIT, RISE, STAGGER, ensureMotion } from './tokens';
