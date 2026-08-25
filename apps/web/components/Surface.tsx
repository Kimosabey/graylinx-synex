'use client';

/**
 * **Surface furniture — the parts every one of the eight surfaces needs.**
 *
 * These exist so six pages do not invent six page headers, six empty states and six different
 * ways of saying the back end is unreachable. The styling lives in `globals.css`; these are
 * the markup, and the markup is the part that goes wrong — a heading at the wrong level, an
 * empty state that reads as good news, a degraded state coloured like a refusal.
 *
 * **Three of them enforce a product rule rather than a style:**
 *
 * - `StateChip` renders one of the six answer states from `CONTEXT.md` §7 and prints the word,
 *   so colour is never the only signal and `NO_DIAGNOSIS` never renders as an error.
 * - `EmptyState` **requires** a `because`. Constraint 7 — `NULL` means *not diagnosed*, never
 *   *healthy*, and an empty queue with no sentence under it reads as a clean plant. That
 *   exact misreading has already happened once, on a two-month window that was blind rather
 *   than clean.
 * - `Degraded` takes the *warning* treatment and never the refusal treatment. A refusal is a
 *   judgement the platform made; a degradation is a capability it has lost. Known constraint
 *   13 requires it to say so rather than quietly substituting something weaker.
 *
 * **Headings.** `Shell` owns the page's single `h1` — the product name, which the naming law
 * governs. A surface's own title is the `h2` inside `PageHeader`, and card headings are `h2`
 * as well, as its peers. Nothing here emits a heading at any other level, so a page cannot
 * skip one by accident.
 */

import type { ReactNode } from 'react';
import type { AnswerState } from '@/lib/frames';

/* ── the page header ───────────────────────────────────────────────────────── */

export interface PageHeaderProps {
  /** The surface's name. Rendered as the page's `h2` — `Shell` holds the `h1`. */
  title: string;
  /** One or two sentences on what this surface is for. Set to a reading measure. */
  lede?: string;
  /**
   * The data window, the persona, the record count — whatever this surface is scoped by.
   * Constraint 15: every artefact states its data window, and this is where a page says it.
   */
  meta?: ReactNode;
  /** Filters, a view switcher, a primary action. */
  actions?: ReactNode;
}

export function PageHeader({ title, lede, meta, actions }: PageHeaderProps) {
  return (
    <header className="pagehead">
      <div className="pagehead-top">
        <h2 className="pagetitle">{title}</h2>
        {actions && <div className="pagehead-actions">{actions}</div>}
      </div>
      {lede && <p className="lede measure">{lede}</p>}
      {meta && <p className="headmeta">{meta}</p>}
    </header>
  );
}

/* ── the six answer states ─────────────────────────────────────────────────── */

/**
 * `CONTEXT.md` §7. Every turn ends in exactly one of six states, and each is rendered with its
 * own word so a reader who cannot see the colour loses nothing.
 *
 * `NO_DIAGNOSIS` wears `--refusal`, never `--stop` and never `--warn`. It is a correct
 * outcome and the most common one on this data — 5,309 slots against 674 faulted.
 */
export function StateChip({ state, className }: { state: AnswerState; className?: string }) {
  return (
    <span className={className ? `state-pill ${className}` : 'state-pill'} data-state={state}>
      {state}
    </span>
  );
}

/* ── an empty result, said honestly ────────────────────────────────────────── */

export interface EmptyStateProps {
  /** What is empty. "No cases in this queue", not "Nothing to see here". */
  title: string;
  /**
   * **Required.** What the emptiness means, in a sentence. An empty queue means *no diagnosed
   * faults*, never *no faults* — constraint 7, and the reason this prop has no default.
   */
  because: string;
  children?: ReactNode;
}

export function EmptyState({ title, because, children }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <p className="empty-title">{title}</p>
      <p className="empty-because">{because}</p>
      {children}
    </div>
  );
}

/* ── degraded mode ─────────────────────────────────────────────────────────── */

export interface DegradedProps {
  /** What could not be reached or computed. "The case queue", "Reconciliation". */
  what: string;
  /** The error as it actually was — a status line, an exception message. Never invented. */
  detail?: string | null;
  /** Where it was asked for, so the reader can check the service themselves. */
  endpoint?: string;
  /** Rendered under the detail. Use it to say what the surface still shows without it. */
  children?: ReactNode;
}

/**
 * The state every surface must be able to reach when the back end is down.
 *
 * Never a spinner that never resolves and never placeholder figures: a page that invents data
 * to fill a layout is the exact dishonesty this product argues against, and a spinner with no
 * end is the same lie told more slowly.
 */
export function Degraded({ what, detail, endpoint, children }: DegradedProps) {
  return (
    <section className="card degraded" role="status">
      <p className="degraded-title">Degraded — {what} is unavailable</p>
      <p className="degraded-detail">
        Nothing on this surface is being substituted or estimated while it is down. What is
        shown below, if anything, is what was already loaded.
      </p>
      {detail && <p className="mono">{detail}</p>}
      {endpoint && <p className="mono">{endpoint}</p>}
      {children}
    </section>
  );
}

/* ── the loading skeleton ──────────────────────────────────────────────────── */

/**
 * A shape, held for as long as the request takes.
 *
 * It reserves the space the content will occupy so an answer arriving does not shove the
 * evidence above it down the page — `mvp/DESIGN-HANDOFF.md` §9a rule 6. It is announced once,
 * politely, rather than each bar being read out.
 */
export function Skeleton({
  lines = 3,
  label = 'Loading',
  className,
}: {
  lines?: number;
  label?: string;
  className?: string;
}) {
  return (
    <div className={className ? `skel ${className}` : 'skel'} role="status">
      {Array.from({ length: lines }, (_unused, i) => (
        <span className="skel-bar" key={i} aria-hidden="true" />
      ))}
      {/* Last, so the bars keep their `nth-child` widths — and so the announcement is one
          string rather than one per bar. */}
      <span className="sr-only">{label}</span>
    </div>
  );
}
