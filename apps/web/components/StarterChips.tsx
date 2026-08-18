'use client';

/**
 * What to ask, on an empty conversation.
 *
 * **Why an empty chat needs these at all.** A composer with a placeholder is a blank page, and
 * a blank page in front of a product nobody has used before gets one question typed into it —
 * usually the wrong one, usually the one the product refuses. The chips are not decoration:
 * they are the fastest way to show that this Copilot answers plant-level questions *without*
 * an episode, which is the thing everyone assumes it cannot do.
 *
 * **Seeded from what is actually there.** The last chip names a real detected fault class from
 * the live episode list rather than a fixed example, so it is never a question about something
 * this plant does not have. If the list has not loaded, that chip is absent rather than
 * guessed — a starter that returns *"no such fault class"* teaches exactly the wrong lesson.
 *
 * **Four, and the count is not arbitrary.** One per kind: the catalogue, a machine, the
 * boundary, and one real fault. More than four and they stop being an invitation and become a
 * menu somebody has to read.
 */

import { Reveal } from '@/components/motion';

export interface StarterChipsProps {
  /** Fault labels seen in the measured window. Empty until the episode list lands. */
  faultLabels: readonly string[];
  onPick: (question: string) => void;
}

/**
 * Grouped by what a reader is actually trying to find out, and every one of them works with
 * **no episode chosen** — which is the point the chips exist to make.
 *
 * Deliberately mixed in outcome. Two of these come back as good news, two as a refusal or a
 * blocked state, and one is out of scope entirely. A starter set where everything succeeds
 * teaches that the product always answers, and the first genuine refusal then reads as a
 * fault rather than as the product working.
 */
const GROUPS: ReadonlyArray<{ heading: string; questions: readonly string[] }> = [
  {
    heading: 'The plant',
    questions: [
      'What equipment do we have?',
      'What fault classes can the model report?',
      'Do the numbers in the report match the plant?',
    ],
  },
  {
    heading: 'A machine',
    questions: ['What happened on chiller 1?', 'How is chiller 2 doing?'],
  },
  {
    heading: 'The work',
    questions: ['Raise a work order', 'Did the repair work?', 'What should I check?'],
  },
  {
    heading: 'The boundary',
    questions: ['Can you change the chilled water setpoint?'],
  },
];

export function StarterChips({ faultLabels, onPick }: StarterChipsProps) {
  // The last group names a fault class this plant actually detected, rather than a fixed
  // example. Absent until the episode list lands — a starter that returns "no such fault
  // class" teaches exactly the wrong lesson.
  const groups = faultLabels.length
    ? [...GROUPS, { heading: 'A fault', questions: [`What does ${faultLabels[0]} mean?`] }]
    : GROUPS;

  return (
    <section className="starters" aria-labelledby="starters">
      <h2 id="starters">Try asking — none of these needs an episode chosen</h2>
      {groups.map((group) => (
        <div className="startergroup" key={group.heading}>
          <h3>{group.heading}</h3>
          <Reveal className="row" runKey={group.questions.length}>
            {group.questions.map((q) => (
              <button key={q} type="button" className="chip starter" onClick={() => onPick(q)}>
                {q}
              </button>
            ))}
          </Reveal>
        </div>
      ))}
    </section>
  );
}
