'use client';

/**
 * The separation law, stated on the screen it applies to.
 *
 * **Why a panel and not a footnote.** `CONTEXT.md` §5 is the rule this whole product is built
 * around — the language model explains, and never names a fault, grants a permission, sets a
 * priority or decides a repair worked. Every one of those is enforced in code and none of it is
 * visible to somebody watching an answer stream in. A reader who cannot see the boundary has to
 * take it on trust, and the boundary is the reason to trust the product at all.
 *
 * `mvp/mock.html` carries this as a fixed panel beside the conversation. It was the one element
 * of the designed shell the build had not brought across.
 *
 * **Each line names what does the job instead.** "Never names a fault" alone reads as a missing
 * feature; "the isolation path does" reads as an architecture. The second half is the half that
 * makes it a claim rather than an apology.
 */

import { Reveal } from '@/components/motion';

/** Five, from `mvp/mock.html`. Not a summary of the rules — the rules themselves. */
const NEVER = [
  { it: 'Name a fault', instead: 'the isolation path does' },
  { it: 'Grant a permission', instead: 'the Control Plane does' },
  { it: 'Approve its own request', instead: null },
  { it: 'Set a priority', instead: 'a formula does' },
  { it: 'Decide a repair worked', instead: 'residuals do' },
  { it: 'Command plant equipment', instead: 'in any phase' },
] as const;

export function NeverDoes() {
  return (
    <section className="card supporting neverdoes" aria-labelledby="never">
      <h2 id="never">What it will never do</h2>
      <Reveal as="ul" className="neverdoes-list">
        {NEVER.map((row) => (
          <li key={row.it}>
            <span className="neverdoes-it">{row.it}</span>
            {row.instead && <span className="neverdoes-instead">{row.instead}</span>}
          </li>
        ))}
      </Reveal>
    </section>
  );
}
