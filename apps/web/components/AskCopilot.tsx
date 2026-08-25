'use client';

/**
 * A link from any surface into the Copilot, carrying the question that surface would ask.
 *
 * **The Copilot is the front door to every capability, and until now every other page was a
 * dead end.** A planner looking at a work order, a technician on a job pack, a supervisor on
 * the queue — each could see a fact and had nowhere to ask about it. The chat sat on its own
 * route and every other surface pointed only at itself.
 *
 * **The question is written by the surface, not typed by the reader.** A page knows what it is
 * showing: the work-orders page knows the machine and the kind, a case knows its episode. So
 * the link carries a whole sentence rather than dropping somebody into an empty composer to
 * reconstruct it — which is the moment most people give up.
 *
 * **It sends once and strips the parameter.** A URL that keeps re-asking on every render is a
 * URL somebody bookmarks and then cannot stop, and a back-button press that silently re-runs a
 * turn costs box time for an answer already on screen.
 */

import Link from 'next/link';

interface Props {
  /** The whole question, as a person would type it. */
  question: string;
  /** What the link says. Defaults to the plainest possible thing it could say. */
  children?: React.ReactNode;
}

export function AskCopilot({ question, children }: Props) {
  return (
    <Link className="askcopilot" href={`/?ask=${encodeURIComponent(question)}`}>
      {children ?? 'Ask the Copilot'}
      {/* The question is shown rather than hidden behind the label: somebody who can see what
          will be asked can tell whether it is the question they actually have. */}
      <span className="askcopilot-q">“{question}”</span>
    </Link>
  );
}
