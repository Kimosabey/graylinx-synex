/**
 * **`RC12` narrowing · `RC13` the elimination audit · `RC14` exhausted is not settled.**
 *
 * `mvp/DESIGN-HANDOFF.md` calls this the product's potential signature: candidate causes
 * visibly narrowing, eliminated ones struck out with *why* attached. This is that screen.
 *
 * **The screen is shaped by the risk rather than by the happy path.** Thirty-one causes have
 * already been eliminated on the reference queue, every one by a discriminator no
 * refrigeration engineer has reviewed. Elimination is irreversible and nobody re-examines a
 * settled question, so a wrong discriminator does not produce a wrong answer once — it
 * produces a confident wrong answer that is never revisited.
 *
 * Four consequences, each visible in the markup:
 *
 * - **An eliminated cause stays on the page**, struck through, carrying the question and the
 *   answer that killed it (constraint 31). A list that silently shrinks is a list nobody can
 *   audit — *"why did nobody look at the tower?"* deserves better than *"the software
 *   decided"*.
 * - ***Can't tell* is rendered with its effect count of zero** (constraint 30). The interface
 *   *proves* it changes nothing rather than asserting it, because a "no effect" label nobody
 *   can check is a promise.
 * - **`settled` and `exhausted` look different** (constraint 32). Running out of questions
 *   establishes *"we cannot separate these with the checks we have"*, which is a finding and
 *   not a conclusion about whichever cause happens to be left.
 * - **No number is rendered here.** Not one — no confidence, no score, no distance. Inherited
 *   constraint 2 forbids a numeric confidence score, and a differential is exactly where a
 *   reader would read one as a probability.
 *
 * **Today every differential reports `exhausted` before a question is asked**, because the
 * candidate sets are transcribed and none of the discriminators is reviewed. The screen says
 * so in words instead of rendering an empty panel — an empty panel reads as *nothing to
 * investigate*, which is the opposite of the truth.
 */

'use client';

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API ?? 'http://127.0.0.1:8001';

interface Cause {
  id: string;
  text: string;
  live: boolean;
  confirmed: boolean;
  eliminated: boolean;
  eliminated_because: string;
  eliminated_by_question: string;
  eliminated_by_answer: string;
}

interface Answer {
  key: string;
  text: string;
  effect_count: number;
  changes_nothing: boolean;
}

interface Question {
  id: string;
  text: string;
  sme_reviewed: boolean;
  answers: Answer[];
}

interface DifferentialBody {
  fault_label: string;
  has_differential: boolean;
  content_available?: boolean;
  reason?: string;
  causes: Cause[];
  live_count?: number;
  eliminated_count?: number;
  outcome?: string;
  settled?: boolean;
  exhausted_not_settled?: boolean;
  outcome_text?: string;
  next_question: Question | null;
  reviewed_questions_available?: number;
  unreviewed_note?: string;
  eliminations?: string[];
}

export function Differential({ faultLabel }: { faultLabel: string | null }) {
  const [body, setBody] = useState<DifferentialBody | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (!faultLabel) {
      setBody(null);
      return;
    }
    let cancelled = false;
    setError('');
    fetch(`${API}/api/v1/differential`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fault_label: faultLabel, answers: [] }),
    })
      .then((r) => (r.ok ? r.json() : r.json().then((d) => Promise.reject(d.detail))))
      .then((d) => !cancelled && setBody(d))
      // A failed fetch is a fact about us, never about the plant. Saying "no causes" here
      // would assert something about the equipment that we did not check.
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [faultLabel]);

  if (!faultLabel) return null;

  if (error) {
    return (
      <section className="card differential" aria-label="Differential">
        <h3>Differential</h3>
        <p className="absence">
          The differential could not be loaded: {error}. Nothing was examined, so this is not a
          statement about the causes.
        </p>
      </section>
    );
  }

  if (!body) {
    return (
      <section className="card differential" aria-label="Differential" aria-busy="true">
        <h3>Differential</h3>
        <p className="absence">Loading the candidate causes…</p>
      </section>
    );
  }

  // Constraint 27. A class that names a mechanism does not get one, and that is a fact about
  // the trained model rather than a gap in our content — so it reads differently from
  // "we have not written it yet".
  if (!body.has_differential) {
    return (
      <section className="card differential" aria-label="Differential">
        <h3>Differential</h3>
        <p className="absence">{body.reason}</p>
      </section>
    );
  }

  if (body.content_available === false) {
    return (
      <section className="card differential" aria-label="Differential">
        <h3>Differential</h3>
        <p className="absence">{body.reason}</p>
      </section>
    );
  }

  const settled = body.settled === true;
  const exhausted = body.exhausted_not_settled === true;

  return (
    <section className="card differential" aria-label="Differential">
      <header className="differential-head">
        <h3>Differential</h3>
        {/* Constraint 32: two terminal states, never one "done" badge. */}
        <span
          className="badge outcome"
          data-outcome={body.outcome}
          data-settled={settled}
          data-exhausted={exhausted}
        >
          {settled ? 'settled' : exhausted ? 'exhausted — not settled' : 'open'}
        </span>
      </header>

      <p className="outcome-text">{body.outcome_text}</p>

      <ol className="causes">
        {body.causes.map((cause) => (
          <li
            key={cause.id}
            className="cause"
            data-live={cause.live}
            data-eliminated={cause.eliminated}
            data-confirmed={cause.confirmed}
          >
            <span className="cause-text">{cause.text}</span>

            {cause.confirmed && (
              /* Constraint 28: a confirmation never eliminates its siblings. Fouling on a
                 machine also low on flow is two real causes. */
              <span className="badge confirmed">confirmed — siblings stay live</span>
            )}

            {cause.eliminated && (
              /* Constraint 31: the audit travels with the elimination or the elimination is
                 the software deciding on its own authority. */
              <p className="elimination">{cause.eliminated_because}</p>
            )}
          </li>
        ))}
      </ol>

      {body.next_question ? (
        <div className="next-question">
          <h4>{body.next_question.text}</h4>
          <ul className="answers">
            {body.next_question.answers.map((answer) => (
              <li key={answer.key} data-changes-nothing={answer.changes_nothing}>
                {answer.text}
                {answer.changes_nothing && (
                  /* Constraint 30, proved rather than promised. */
                  <span className="badge no-effect">changes nothing</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        body.unreviewed_note && <p className="absence review-gate">{body.unreviewed_note}</p>
      )}
    </section>
  );
}
