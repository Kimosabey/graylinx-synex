'use client';

/**
 * The motion budget, in one place.
 *
 * **Why these live in a module rather than in each component.** The budget is locked —
 * `mvp/DESIGN-HANDOFF.md` §2 fixes it at ~170ms on `cubic-bezier(.2,.7,.3,1)` — and a locked
 * value that is retyped per component is a locked value that drifts. `globals.css` holds the
 * same two numbers as `--dur` and `--ease`; this file is their JavaScript half, and the two
 * must be changed together or not at all.
 *
 * **The ease is the CSS curve, not an approximation of it.** GSAP's stock `power2.out` is
 * close to `cubic-bezier(.2,.7,.3,1)` but not equal to it, and a card that settles on one
 * curve beside a chip that settles on another reads as two products. `CustomEase` ships in
 * the public GSAP package, so the exact curve is available without a licence or a plugin
 * install — `M0,0 C0.2,0.7 0.3,1 1,1` is the CSS declaration, transcribed.
 *
 * **Registration is lazy and therefore client-only.** `'use client'` still server-renders a
 * module, so registering plugins at import time would run GSAP setup during SSR for no
 * benefit. `ensureMotion()` is called from inside `useGSAP`, which only ever runs in the
 * browser.
 */

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { CustomEase } from 'gsap/CustomEase';

/** Entrances. `--dur: 170ms` in `globals.css`. */
export const DUR = 0.17;

/**
 * Exits, at 70% of an entrance. Something leaving should not hold the screen as long as
 * something arriving did — `useRailCollapse` already applies this ratio and it is stated
 * once here so the next component does not pick its own.
 */
export const DUR_EXIT = DUR * 0.7;

/**
 * A whole column of content moving. Longer than a single element because the distance is
 * greater; it matches the `settle` keyframe `globals.css` already uses for an arriving
 * answer, so a route change and an answer arriving feel like the same product.
 */
export const DUR_PAGE = 0.22;

/**
 * Per-item offset in a staggered reveal. The brief's range is 20–40ms and `FigureView`
 * already staggers at 28ms, so this is that number rather than a second opinion.
 */
export const STAGGER = 0.028;

/** Travel, in px. The `settle` keyframe's 6px — far enough to read as arrival, near enough
 *  not to read as a slide. */
export const RISE = 6;

/** The registered id of the locked curve. Passed to GSAP as `ease: EASE`. */
export const EASE = 'synex';

/**
 * The exit curve. Deliberately a GSAP stock ease rather than a second custom bezier: the
 * design system locks exactly one curve, and inventing a second would be inventing a design
 * value. `useRailCollapse` already uses `power2.in` for the same purpose.
 */
export const EASE_EXIT = 'power2.in';

let ready = false;

/**
 * Register GSAP's React integration and the locked ease. Idempotent, and safe to call at the
 * top of every `useGSAP` callback — which is where it must be called, because that is the
 * only place guaranteed to be running in a browser.
 */
export function ensureMotion(): void {
  if (ready) return;
  ready = true;
  gsap.registerPlugin(useGSAP, CustomEase);
  // The CSS declaration, transcribed: cubic-bezier(0.2, 0.7, 0.3, 1).
  CustomEase.create(EASE, 'M0,0 C0.2,0.7 0.3,1 1,1');
}

/**
 * The two media queries every primitive branches on.
 *
 * `prefers-reduced-motion` is handled by `gsap.matchMedia()` and never by a hand-rolled
 * `window.matchMedia` check, because matchMedia reverts what it created when the query stops
 * matching — a user who turns the preference on mid-session gets a still interface rather
 * than a half-animated one.
 *
 * **Under `reduce` the state still changes; only the movement is removed.** A reveal that
 * hid its content under reduced motion would not be a gentler interface, it would be an
 * empty one.
 */
export const MOTION_QUERIES = {
  motion: '(prefers-reduced-motion: no-preference)',
  reduce: '(prefers-reduced-motion: reduce)',
} as const;

export type MotionConditions = { motion?: boolean; reduce?: boolean };
