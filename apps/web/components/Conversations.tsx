'use client';

/**
 * The conversations you have had, and the one you are in.
 *
 * **A chat with no history is a chat you cannot leave.** Until now the transcript lived in one
 * React state variable: reloading the page lost it, and *Clear* lost it deliberately with no
 * way back. So the only safe move was never to clear — which meant every new subject inherited
 * the machine named five questions ago, because the router reads the last equipment mentioned.
 * The product punished the tidy behaviour it needed.
 *
 * **Stored in the browser, deliberately.** A conversation is a working note, not a record: it
 * holds what somebody asked and what came back, and the *answers* are already reproducible from
 * the evidence. Putting it on the server would make an ordinary chat into something the audit
 * trail has an opinion about, and `G6` exists for material actions rather than for questions
 * somebody typed and abandoned.
 *
 * **The title is the first question, not a summary.** A generated title is another place a
 * model can put words on a screen, and one that misreads the conversation is worse than no
 * title — somebody looking for the chiller 2 thread should find the words they typed.
 */

import { useCallback, useEffect, useState } from 'react';

import { IconHalt } from '@/components/Icons';
import { Reveal } from '@/components/motion';
import type { TurnState } from '@/lib/useTurn';

/** Where the browser keeps them. Versioned, so a shape change cannot resurrect a stale one. */
const STORE = 'synex.conversations.v1';

/** How many are kept. Enough to reach back through a shift; few enough to scan. */
const KEEP = 12;

export interface StoredConversation {
  id: string;
  title: string;
  /** Milliseconds since the epoch — stamped by the browser, only ever shown as a time. */
  at: number;
  exchanges: { question: string; answer: string }[];
}

function read(): StoredConversation[] {
  try {
    const raw = window.localStorage.getItem(STORE);
    return raw ? (JSON.parse(raw) as StoredConversation[]) : [];
  } catch {
    // A corrupted store is an empty one. Throwing here would take the whole page down over a
    // working note, which is the wrong trade for something the evidence can reproduce.
    return [];
  }
}

function write(all: StoredConversation[]): void {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(all.slice(0, KEEP)));
  } catch {
    // Quota exceeded, or storage disabled. The conversation still works for this session.
  }
}

interface Props {
  /** The turns on screen now, saved under the current id whenever they change. */
  turns: TurnState[];
  /** Called with the exchanges to restore, and with `[]` to start fresh. */
  onOpen: (exchanges: { question: string; answer: string }[]) => void;
}

export function Conversations({ turns, onOpen }: Props) {
  const [all, setAll] = useState<StoredConversation[]>([]);
  const [current, setCurrent] = useState<string>('');

  useEffect(() => {
    setAll(read());
  }, []);

  // Saved as it goes rather than on some end-of-conversation event: there is no such event,
  // and a tab closed mid-thought is exactly when somebody most wants the thread back.
  useEffect(() => {
    const done = turns.filter((t) => t.question.trim() && t.text.trim() && !t.streaming);
    if (!done.length) return;

    setAll((existing) => {
      const id = current || `c${done[0].id}`;
      if (!current) setCurrent(id);
      const entry: StoredConversation = {
        id,
        title: done[0].question,
        at: Date.now(),
        exchanges: done.map((t) => ({ question: t.question, answer: t.text })),
      };
      const next = [entry, ...existing.filter((c) => c.id !== id)].slice(0, KEEP);
      write(next);
      return next;
    });
  }, [turns, current]);

  const startFresh = useCallback(() => {
    setCurrent('');
    onOpen([]);
  }, [onOpen]);

  const open = useCallback(
    (conversation: StoredConversation) => {
      setCurrent(conversation.id);
      onOpen(conversation.exchanges);
    },
    [onOpen],
  );

  const forget = useCallback((id: string) => {
    setAll((existing) => {
      const next = existing.filter((c) => c.id !== id);
      write(next);
      return next;
    });
  }, []);

  return (
    <section className="conversations" aria-labelledby="conversations">
      <div className="conversations-head">
        <h2 id="conversations">Conversations</h2>
        <button type="button" className="btn ghost small" onClick={startFresh}>
          New
        </button>
      </div>

      {all.length === 0 ? (
        <p className="muted conversations-empty">
          Kept in this browser only. Starting a new one drops the machine carried forward from
          the last question, which is what makes a clean read possible.
        </p>
      ) : (
        <Reveal as="ul" className="conversations-list" runKey={all.length}>
          {all.map((conversation) => (
            <li key={conversation.id} data-current={conversation.id === current}>
              <button
                type="button"
                className="conversations-open"
                onClick={() => open(conversation)}
              >
                <span className="conversations-title">{conversation.title}</span>
                <span className="muted conversations-meta">
                  {conversation.exchanges.length} turn
                  {conversation.exchanges.length === 1 ? '' : 's'} ·{' '}
                  {new Date(conversation.at).toLocaleTimeString('en-GB', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </button>
              <button
                type="button"
                className="conversations-forget"
                onClick={() => forget(conversation.id)}
                aria-label={`Forget "${conversation.title}"`}
                title="Forget this conversation"
              >
                <IconHalt className="ico" />
              </button>
            </li>
          ))}
        </Reveal>
      )}
    </section>
  );
}
