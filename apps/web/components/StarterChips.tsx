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

export interface StarterEpisode {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
}

export interface StarterChipsProps {
  /** Fault labels seen in the measured window. Empty until the episode list lands. */
  faultLabels: readonly string[];
  /** Real episodes, so a work chip can carry one rather than asking without evidence. */
  episodes: readonly StarterEpisode[];
  /** A plain question, with no episode. */
  onPick: (question: string) => void;
  /**
   * A question that needs one episode's evidence. The chip carries the episode, so the
   * question arrives with what it needs — rather than coming back saying it needs a case
   * opened first, which teaches that the product cannot do the thing it is named after.
   */
  onPickWithEpisode: (question: string, episode: StarterEpisode) => void;
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
      'What happened across the plant?',
      'What equipment do we have?',
      'What fault classes can the model report?',
      'Do the numbers in the report match the plant?',
    ],
  },
  {
    heading: 'A machine',
    questions: ['What happened on chiller 1?', 'How is chiller 2 doing?'],
  },
  // **Not the work questions.** "Raise a work order", "did the repair work" and "what should
  // I check" are each built from one episode's evidence, so offered here — with nothing
  // selected — they come back saying an episode is needed. A starter chip that leads to
  // "open a case first" teaches that the product cannot do the thing it is named after. Those
  // belong on the case, where the evidence to answer them is.
  {
    heading: 'The boundary',
    questions: ['Can you change the chilled water setpoint?'],
  },
];

export function StarterChips({
  faultLabels,
  episodes,
  onPick,
  onPickWithEpisode,
}: StarterChipsProps) {
  // The work questions each need one episode's evidence, so they carry one. Picked from what
  // the plant actually detected rather than fixed, and absent until the list lands.
  const worked = episodes[0];
  // The last group names a fault class this plant actually detected, rather than a fixed
  // example. Absent until the episode list lands — a starter that returns "no such fault
  // class" teaches exactly the wrong lesson.
  const groups = faultLabels.length
    ? [...GROUPS, { heading: 'A fault', questions: [`What does ${faultLabels[0]} mean?`] }]
    : GROUPS;

  return (
    <section className="starters" aria-labelledby="starters">
      <h2 id="starters">Try asking — none of these needs an episode chosen</h2>
      {worked && (
        <div className="startergroup">
          <h3>The work — on {worked.equipment_key.replace('_', ' ')} · {worked.day}</h3>
          <Reveal className="row" runKey={3}>
            {['Raise a work order', 'What should I check?', 'Did the repair work?'].map((q) => (
              <button
                key={q}
                type="button"
                className="chip starter"
                onClick={() => onPickWithEpisode(q, worked)}
              >
                {q}
              </button>
            ))}
          </Reveal>
        </div>
      )}

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
