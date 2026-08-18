'use client';

/**
 * Who built this.
 *
 * **At the foot of the content column, not in the rail and not in the bar.** The rail answers
 * *where do I go* and the bar carries the two facts that change what an answer is worth; a
 * credit in either competes with those every second the product is open. The foot of the page
 * is where a reader's eye lands last, which is the correct weight for authorship — present on
 * every surface, never in the way of one.
 *
 * **The motion is a reveal on entry and nothing else.** It uses the same `Reveal` primitive
 * every list on every surface uses, which means it inherits the locked 170ms budget and the
 * `prefers-reduced-motion` branch rather than carrying its own. A credit with a signature
 * animation would be the one element on the page insisting on itself, and the motion rule here
 * is that movement expresses cause and effect — an entrance is the cause being *arrival*.
 */

import { Reveal } from '@/components/motion';

export function BuiltBy() {
  return (
    <Reveal className="builtby">
      <span className="builtby-mark" aria-hidden="true" />
      <span className="builtby-who">
        <span className="builtby-name">Harshan Aiyappa</span>
        <span className="builtby-role">Fullstack AI Engineer</span>
      </span>
      <span className="builtby-what">Graylinx Synex</span>
    </Reveal>
  );
}
