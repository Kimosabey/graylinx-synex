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
 * **Seeded from what is actually there.** The chips name a real detected fault class and a real
 * day from the live episode list rather than fixed examples, so they are never questions about
 * something this plant does not have. If the list has not loaded, those chips are absent rather
 * than guessed — a starter that returns *"no such fault class"* teaches exactly the wrong lesson.
 *
 * **Every chip is a sentence, and nothing is attached to it.** The episode chips used to carry a
 * hidden episode — the question said *"Raise a work order"* and an invisible selection said
 * which one. That made the fixed episode part of the interface: the heading had to announce
 * which episode the chips were bound to, and a reader could not get a different one by asking.
 * The words now name the machine, the day and the fault, and the back end resolves the episode
 * from them, so a chip is a worked example of a question the reader can retype with any machine
 * and any day — which is what a chat is for.
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
  /** Real episodes, so the worked examples name a day and a fault this plant actually has. */
  episodes: readonly StarterEpisode[];
  /** A plain question. There is no other kind — every chip is only its words. */
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
    heading: 'Plant level — the whole site, no machine named',
    questions: [
      'What happened across the plant?',
      'What equipment do we have?',
      'What fault classes can the model report?',
      'Do the numbers in the report match the plant?',
    ],
  },
  {
    heading: 'Machine level — one asset, no day needed',
    questions: ['What happened on chiller 1?', 'How is chiller 2 doing?'],
  },
  // **Not the work questions.** "Raise a work order", "did the repair work" and "what should
  // I check" are each built from one episode's evidence, so offered here — with nothing
  // selected — they come back saying an episode is needed. A starter chip that leads to
  // "open a case first" teaches that the product cannot do the thing it is named after. Those
  // belong on the case, where the evidence to answer them is.
  {
    heading: 'The boundary — what it will refuse',
    questions: ['Can you change the chilled water setpoint?'],
  },
];

/** How a day reads in a question somebody would actually type: `2026-04-09` → `9 April`. */
function inWords(iso: string): string {
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return `${parsed.getDate()} ${parsed.toLocaleString('en-GB', { month: 'long' })}`;
}

export function StarterChips({ faultLabels, episodes, onPick }: StarterChipsProps) {
  // A real episode, used only to write the words. Nothing is attached to the chip — the
  // question carries the machine, the day and the fault, and the back end resolves the
  // episode from them the same way it would from anything the reader typed.
  const worked = episodes[0];
  // The last group names a fault class this plant actually detected, rather than a fixed
  // example. Absent until the episode list lands — a starter that returns "no such fault
  // class" teaches exactly the wrong lesson.
  const machine = worked ? worked.equipment_key.replace('_', ' ') : '';
  const day = worked ? inWords(worked.day) : '';
  const groups = faultLabels.length
    ? [...GROUPS, { heading: 'A fault', questions: [`What does ${faultLabels[0]} mean?`] }]
    : GROUPS;

  return (
    <section className="starters" aria-labelledby="starters">
      {/* **The heading names the levels rather than claiming none needs an episode.** It used
          to say "none of these needs an episode chosen" directly above a group scoped to one
          — a contradiction a reader sees before they read either half. Three of the four
          levels genuinely need nothing; the work questions are built from one episode's
          evidence and carry one, and the group says which. */}
      <h2 id="starters">Try asking — plant, machine, fault class or one episode</h2>
      {worked && (
        <div className="startergroup">
          <h3>Episode level — name the machine and the day, and it finds the episode</h3>
          <Reveal className="row" runKey={3}>
            {[
              `Raise a work order for ${machine} on ${day} for ${worked.fault_label}`,
              `What should I check on ${machine} on ${day}?`,
              `Did the repair work on ${machine} on ${day}?`,
            ].map((q) => (
              <button key={q} type="button" className="chip starter" onClick={() => onPick(q)}>
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
