'use client';

/**
 * **Pressable — a card or row that is genuinely clickable, and says so under the finger.**
 *
 * **What it expresses:** *this responded to you*. A lift on hover says the surface is
 * reachable; a 1.5% scale on press says the press landed. Both are answers to something the
 * reader did, which is the bar motion has to clear in this product.
 *
 * **It is a real control, not a div with a click handler.** Give it `href` and it renders a
 * Next `Link`; give it `onClick` and it renders a `<button type="button">`. Either way it is
 * in the tab order, it takes the shared focus ring, and it meets the 44px touch minimum — a
 * technician in gloves is a real user of this product, not a hypothetical one.
 *
 * The press feedback runs on `gsap.quickTo`, which reuses one tween per property instead of
 * creating a new one per pointer event — the difference is visible on a long queue where every
 * row is pressable.
 *
 * Under reduced motion no pointer handlers are attached at all: the control still works, the
 * hover and focus styling in `globals.css` still identifies it, and nothing moves.
 *
 * @example
 * <Pressable href={`/case/${c.id}`} className="card" ariaLabel={`Open case ${c.id}`}>…</Pressable>
 * <Pressable onClick={() => select(e.id)} className="card">…</Pressable>
 */

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import Link from 'next/link';
import { useRef, type ReactNode } from 'react';
import { DUR, EASE, MOTION_QUERIES, ensureMotion, type MotionConditions } from './tokens';

/** Hover lift, in px. Small enough to read as attention, not as the card jumping. */
const LIFT = 2;

/** Press scale. The same 0.985 `globals.css` already uses for chips, buttons and nav items. */
const PRESS = 0.985;

interface PressableBase {
  children: ReactNode;
  /** Appended to `pressable`. Pass `card` to get the card surface as well. */
  className?: string;
  /** Required when the control's visible content is not a sufficient name (icon-only rows). */
  ariaLabel?: string;
  disabled?: boolean;
}

/**
 * A toggle's on/off state, for controls that select rather than navigate — an episode chip, a
 * filter, a view switch. Buttons only: a link goes somewhere, it is not pressed.
 *
 * Added 2026-08-18. Without it a chip built on this primitive lost `aria-pressed` entirely, so
 * the selected episode was styled as selected and announced identically to the eleven that
 * were not — the selection existed on screen and nowhere in the accessibility tree.
 */

type PressableLink = PressableBase & { href: string; onClick?: never };
type PressableButton = PressableBase & {
  onClick: () => void;
  href?: never;
  ariaPressed?: boolean;
};

export type PressableProps = PressableLink | PressableButton;

export function Pressable(props: PressableProps) {
  const { children, className, ariaLabel, disabled } = props;
  const scope = useRef<HTMLElement | null>(null);

  useGSAP(
    () => {
      ensureMotion();
      const el = scope.current;
      if (!el || disabled) return;

      const mm = gsap.matchMedia();

      mm.add(MOTION_QUERIES, (context) => {
        const { reduce } = context.conditions as MotionConditions;
        if (reduce) return;

        const toY = gsap.quickTo(el, 'y', { duration: DUR, ease: EASE });
        const toScale = gsap.quickTo(el, 'scale', { duration: 0.09, ease: EASE });

        const enter = () => toY(-LIFT);
        const rest = () => {
          toY(0);
          toScale(1);
        };
        const down = () => toScale(PRESS);
        const up = () => toScale(1);

        el.addEventListener('pointerenter', enter);
        el.addEventListener('pointerleave', rest);
        el.addEventListener('pointerdown', down);
        el.addEventListener('pointerup', up);
        // A pointer released outside the element never fires `pointerup` on it, and a card
        // left permanently pressed is the bug this line exists to prevent.
        el.addEventListener('pointercancel', rest);
        el.addEventListener('blur', rest);

        return () => {
          el.removeEventListener('pointerenter', enter);
          el.removeEventListener('pointerleave', rest);
          el.removeEventListener('pointerdown', down);
          el.removeEventListener('pointerup', up);
          el.removeEventListener('pointercancel', rest);
          el.removeEventListener('blur', rest);
          gsap.set(el, { clearProps: 'transform' });
        };
      });

      return () => mm.revert();
    },
    { scope, dependencies: [disabled] },
  );

  const shared = {
    className: className ? `pressable ${className}` : 'pressable',
    'aria-label': ariaLabel,
  };

  if (typeof props.href === 'string') {
    return (
      <Link
        {...shared}
        href={props.href}
        ref={(node) => {
          scope.current = node;
        }}
        // A disabled link is not a thing HTML has, so it is announced disabled and taken out
        // of the tab order rather than pretending to be a button.
        aria-disabled={disabled || undefined}
        tabIndex={disabled ? -1 : undefined}
      >
        {children}
      </Link>
    );
  }

  return (
    <button
      {...shared}
      type="button"
      aria-pressed={props.ariaPressed}
      onClick={props.onClick}
      disabled={disabled}
      ref={(node) => {
        scope.current = node;
      }}
    >
      {children}
    </button>
  );
}
