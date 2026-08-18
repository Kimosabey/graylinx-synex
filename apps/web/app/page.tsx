'use client';

/**
 * The Copilot shell — topbar, rail, and one column of work, as `mvp/mock.html` lays it out.
 *
 * **The order on screen is the order of the argument.** Route, then evidence, then the
 * answer, then the audits. The reader sees the figures arrive *before* the prose, which is
 * the point: the evidence is not a summary of the answer, the answer is a reading of the
 * evidence. Reversing them would make the numbers look like illustration.
 *
 * Every interactive surface is a client component and there are no server actions on the
 * chat path — the plan's guidance for treating the App Router as a shell rather than as a
 * framework to fight.
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTurn } from '@/lib/useTurn';
import { TurnView } from '@/components/TurnView';
import { NeverDoes } from '@/components/NeverDoes';
import { StarterChips } from '@/components/StarterChips';
import { PageEnter, Pressable, Reveal } from '@/components/motion';
import { Skeleton } from '@/components/Surface';

interface CaseItem {
  id: string;
  text: string;
  capability: string;
  blocking: boolean;
  is_sample: boolean;
  stored_reading: string | null;
  finding: string;
}

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

interface Episode {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  slot_count: number;
}

export default function Page() {
  const { turns, turn, ask, stop, clear } = useTurn();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selected, setSelected] = useState<Episode | null>(null);
  // Empty. A composer that arrives pre-filled is a script, not a conversation — and the
  // question it held was the one the demonstration wanted asked.
  const [question, setQuestion] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/episodes`, { credentials: 'include' })
      .then((r) => r.json())
      .then((body) => {
        setEpisodes(body.episodes ?? []);
        // **Nothing is pre-selected.** This used to open on a named fault class —
        // `CONDENSER_LOW_FLOW`, chosen because it is the strongest single case in the data —
        // which meant the surface arrived already pointed at the episode that demonstrates
        // best. That is a demonstration arranging itself, and a reader cannot tell it from
        // the product deciding. The Copilot now answers questions that need no episode at
        // all, so an empty context is a real starting state rather than a broken one.
      })
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  // **Four fetches left with the sections they fed.** The series, the work-order draft, the
  // verification outcome and the case view were all loaded the moment an episode was
  // selected — four round trips per selection, for five cards that now live on `/case/[id]`.
  // Removing the render without removing the fetch would have left the network cost and
  // the API load behind with nothing to show for either.

  const send = useCallback(() => {
    if (!question.trim()) return;
    ask({
      question,
      equipment_key: selected?.equipment_key,
      fault_label: selected?.fault_label,
      day: selected?.day,
      // What "this" and "it" resolve against. The back end remembers six turns and resolves
      // the pronoun; it can only do that if the client says what the last turn was about.
      last_equipment: turns.length ? turns[turns.length - 1].equipmentKey : undefined,
    });
    setQuestion('');
  }, [ask, question, selected, turns]);

  const refused = turn.state?.state === 'NO_DIAGNOSIS' || Boolean(turn.refusal);
  const graded = useMemo(() => turn.audits.find((a) => a.findings), [turn.audits]);
  const notes = useMemo(() => turn.audits.filter((a) => !a.findings), [turn.audits]);

  return (
    <PageEnter>


        {/* **The context, not the catalogue.**
         *
         * This was a grid of twelve episode chips — a second, truncated copy of `/workspace`,
         * which now holds all 39 ranked and filterable. Two problems beyond the duplication:
         * it showed 12 of 39 with nothing saying 27 were hidden, and making a person pick from
         * a grid before they could ask anything is a router limitation (it needs equipment plus
         * fault plus day) rendered as furniture.
         *
         * So the Copilot carries **what is loaded**, and `/workspace` owns **choosing**. The
         * picker is still here because a cold visit to `/` needs a way in — but it is a
         * disclosure behind the chip rather than the first thing on the screen, and it names
         * the true total rather than silently cutting the list. */}
        <section className="card sunken context" aria-labelledby="ctx">
          <h2 id="ctx">Asking about</h2>

          {selected ? (
            <p className="context-current">
              <strong>{selected.equipment_key.replace('_', ' ')}</strong>
              {' · '}
              {selected.fault_label}
              {' · '}
              {selected.day}
              <span className="muted"> · {selected.slot_count} slot(s)</span>
            </p>
          ) : (
            <p className="muted">
              Nothing selected — ask about the plant, a machine or a fault class and it will
              answer. Pick an episode only when you want the evidence behind one specific day.
            </p>
          )}

          {loadError && (
            <p className="muted">Could not reach the back end on {API}: {loadError}</p>
          )}

          {episodes.length === 0 && !loadError && <Skeleton lines={1} label="Loading episodes" />}

          {/* The picker never opens itself. It used to whenever nothing was selected,
              which put 39 rows between a cold visitor and the composer — on the assumption
              that selecting was a prerequisite. It is not: the catalogue path answers
              questions that have no episode at all. */}
          {episodes.length > 0 && (
            <details className="context-picker">
              {/* The count is the true total. A disclosure that says "12" while holding 39 is
                  the silent cap this replaces. */}
              <summary>
                {selected ? 'Change episode' : 'Choose an episode'} · {episodes.length} detected
                in the measured window
              </summary>
              <Reveal className="row" runKey={episodes.length}>
                {episodes.map((e) => (
                  <Pressable
                    key={e.id}
                    className="chip"
                    ariaPressed={selected?.id === e.id}
                    onClick={() => setSelected(e)}
                    ariaLabel={`${e.equipment_key.replace('_', ' ')}, ${e.fault_label}, ${e.day}, ${e.slot_count} slot(s)`}
                  >
                    {e.equipment_key.replace('_', ' ')} · {e.fault_label} · {e.day}
                  </Pressable>
                ))}
              </Reveal>
              <p className="muted">
                <Link href="/workspace">Open the reliability workspace</Link> to rank, filter and
                work the full queue.
              </p>
            </details>
          )}
        </section>

        {/* **The case detail left this surface on 2026-08-18.**
         *
         * Everything that used to sit here — the residual chart, the differential, the work
         * order draft, the verification outcome, the case checklist — is now on `/case/[id]`,
         * which exists and is built for it. Holding all of it permanently open under the
         * composer made the Copilot a dashboard that happened to have a text box: a reader
         * scrolled past five cards of an episode they had not asked about to reach the thing
         * they came to type into, and every one of those cards was already a whole surface
         * somewhere else.
         *
         * A conversation shows what was said. The detail is one link away, and the link says
         * which case it opens. */}
        {selected && (
          <p className="muted">
            <Link href={`/case/${encodeURIComponent(selected.id)}`}>
              Open the full case for {selected.equipment_key.replace('_', ' ')} ·{' '}
              {selected.fault_label} · {selected.day}
            </Link>{' '}
            — evidence, the differential, the work order it would raise, and verification.
          </p>
        )}



        {/* The transcript. Turns append rather than replace, so the exchange the back end
            already remembers — six turns, with pronoun resolution — is visible to the reader
            resolving the same pronouns. Newest last, the way a conversation reads. */}
        {turns.map((t) => (
          <TurnView key={t.id} turn={t} />
        ))}

        {/* Starters before the boundary panel: what you CAN ask, then what it will never do.
            The other order reads as a list of refusals with an invitation appended. */}
        {turns.length === 0 && (
          <StarterChips
            faultLabels={Array.from(new Set(episodes.map((e) => e.fault_label)))}
            onPick={(q) => {
              setQuestion(q);
              ask({ question: q });
            }}
          />
        )}

        {turns.length === 0 && <NeverDoes />}

        {turns.length === 0 && (
          <p className="muted">
            Ask about a detected episode. Every answer states its data window, names the
            evidence behind it, and says plainly when the data cannot support a diagnosis.
          </p>
        )}

        {/* The composer is last in the flow and pinned by CSS. A chat where you type
            above the reply is one where every answer arrives off-screen. */}
        <div className="composer">
          <label htmlFor="q" className="sr-only" style={{ position: 'absolute', left: -9999 }}>
            Your question
          </label>
          <input
            id="q"
            value={question}
            onChange={(ev) => setQuestion(ev.target.value)}
            onKeyDown={(ev) => ev.key === 'Enter' && !turn.streaming && send()}
            placeholder="Ask about a machine, a fault, a reading — or what this plant has at all"
            aria-label="Your question"
          />
          <button className="btn" onClick={turn.streaming ? stop : send} disabled={!question.trim()}>
            {turn.streaming ? 'Stop' : 'Ask'}
          </button>
        </div>
    </PageEnter>
  );
}
