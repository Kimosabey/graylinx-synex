'use client';

/**
 * The conversation runtime — hand-rolled SSE over `fetch` + `getReader()`.
 *
 * **Not `EventSource`.** That API cannot POST, and the turn needs a body: the question, the
 * episode, the persona cookie. So the stream is read manually, which also means the parser
 * lives here where it can be tested rather than inside a browser primitive.
 *
 * Three details, each of which is a bug if omitted:
 *
 * 1. **A `useRef` guard around the reader.** React 18+ in development mounts effects twice,
 *    and without the guard a single question opens two streams and every token arrives
 *    doubled. It looks like a backend bug and is not.
 * 2. **A 40 ms token buffer.** Calling `setState` per token re-renders on every few
 *    characters and the answer visibly stutters. Batching to one frame's worth of work
 *    keeps it smooth without making it feel delayed.
 * 3. **`AbortController` on stop and unmount.** A stream left open after navigation keeps a
 *    connection and keeps appending to state nobody is rendering.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AuditFrame,
  EvidenceFrame,
  FigureFrame,
  NoDiagnosisFrame,
  RouteFrame,
  StageFrame,
  StateFrame,
} from './frames';

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';
const TOKEN_FLUSH_MS = 40;

export interface AskBody {
  question: string;
  equipment_key?: string;
  fault_label?: string;
  day?: string;
  mode?: string;
  last_equipment?: string;
  /**
   * What was already said. Filled in by the hook from its own transcript rather than by the
   * caller — every surface that asks a question wants the conversation carried, and making
   * each one remember to pass it is how one of them ends up not doing so.
   */
  history?: { question: string; answer: string }[];
}

export interface TurnState {
  /** The question that produced this turn. Rendered above the answer in the transcript, so a
   *  reader scrolling back can see what was asked without inferring it from the reply. */
  question: string;
  /** Stable across re-renders, so React keys never collide when two turns ask the same thing. */
  id: number;
  /** What this turn was asked *about*. Recorded on the turn rather than read back out of the
   *  evidence, because a refused turn has no evidence and is exactly the turn a follow-up
   *  question most often refers to — "why not?" needs the machine the refusal was about. */
  equipmentKey?: string;
  streaming: boolean;
  stages: StageFrame[];
  route: RouteFrame | null;
  figures: FigureFrame[];
  evidence: EvidenceFrame | null;
  text: string;
  refusal: NoDiagnosisFrame | null;
  audits: AuditFrame[];
  state: StateFrame | null;
  error: string | null;
}

const EMPTY: TurnState = {
  question: '',
  id: 0,
  streaming: false,
  stages: [],
  route: null,
  figures: [],
  evidence: null,
  text: '',
  refusal: null,
  audits: [],
  state: null,
  error: null,
};

/**
 * **Why a transcript and not a single turn.** `docs/10-product/05-…-levels-and-conversations.md`
 * §5.3 is written entirely in chained exchanges — *"Create a work order for **this**"*, *"Close
 * **this** WO"* — and the back end already resolves those pronouns against
 * `MAX_REMEMBERED_TURNS = 6`. Until 2026-08-18 this hook held one turn and replaced it on every
 * question, so the memory existed and nothing on screen could reach it: a reader could not see
 * what "this" referred to, and neither could they check the answer against the question that
 * produced it. The eighth instance of machinery with no consumer in this repository.
 *
 * The live turn is the **last element** rather than a separate field. One array means there is
 * no second place for a turn to live and no moment where a finished turn has been removed from
 * one and not yet added to the other.
 */
export function useTurn() {
  const [turns, setTurns] = useState<TurnState[]>([]);
  // **A ref beside the state, because `ask` reads the transcript from inside a closure.** The
  // handler that calls it closed over an earlier render, so reading `turns` there would send
  // the conversation as it stood one question ago — which is worse than sending none, since
  // the model would resolve "that one" against the wrong turn.
  const turnsRef = useRef<TurnState[]>([]);
  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);
  const nextId = useRef(1);
  // Every frame folds into the turn being streamed, which is always the last one.
  const setTurn = useCallback(
    (update: TurnState | ((previous: TurnState) => TurnState)) =>
      setTurns((all) => {
        if (!all.length) return all;
        const last = all[all.length - 1];
        const next = typeof update === 'function' ? update(last) : update;
        return [...all.slice(0, -1), next];
      }),
    [],
  );

  const abortRef = useRef<AbortController | null>(null);
  const readingRef = useRef(false);
  const bufferRef = useRef('');
  const flushRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    readingRef.current = false;
    if (flushRef.current) {
      clearInterval(flushRef.current);
      flushRef.current = null;
    }
    setTurn((t) => ({ ...t, streaming: false }));
  }, [setTurn]);

  useEffect(() => stop, [stop]);

  const ask = useCallback(
    async (body: AskBody) => {
      // The dev double-mount guard. Without it one question opens two streams.
      if (readingRef.current) return;
      readingRef.current = true;

      const controller = new AbortController();
      abortRef.current = controller;
      bufferRef.current = '';
      setTurns((all) => [
        ...all,
        {
          ...EMPTY,
          question: body.question,
          equipmentKey: body.equipment_key,
          id: nextId.current++,
          streaming: true,
        },
      ]);

      flushRef.current = setInterval(() => {
        if (!bufferRef.current) return;
        const chunk = bufferRef.current;
        bufferRef.current = '';
        setTurn((t) => ({ ...t, text: t.text + chunk }));
      }, TOKEN_FLUSH_MS);

      try {
        const response = await fetch(`${API}/api/v1/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // **The conversation travels with the question.** Without it the back end saw every
          // turn as the first turn, so "and chiller 2?" or "why is that?" arrived with nothing
          // to attach to. Read from the ref rather than the state variable because `ask` is
          // called from an event handler that closed over an older render.
          body: JSON.stringify({
            ...body,
            history: turnsRef.current
              .filter((t) => t.question.trim() && t.text.trim())
              .slice(-6)
              .map((t) => ({ question: t.question, answer: t.text })),
          }),
          credentials: 'include',
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`the back end answered ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let carry = '';

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          carry += decoder.decode(value, { stream: true });

          // SSE separates events with a blank line. A partial event stays in `carry` until
          // its terminator arrives — splitting on newline alone would parse half a frame.
          const events = carry.split('\n\n');
          carry = events.pop() ?? '';
          for (const raw of events) apply(raw, setTurn, bufferRef);
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setTurn((t) => ({ ...t, error: (err as Error).message }));
        }
      } finally {
        if (flushRef.current) {
          clearInterval(flushRef.current);
          flushRef.current = null;
        }
        if (bufferRef.current) {
          const rest = bufferRef.current;
          bufferRef.current = '';
          setTurn((t) => ({ ...t, text: t.text + rest }));
        }
        readingRef.current = false;
        setTurn((t) => ({ ...t, streaming: false }));
      }
    },
    [setTurn],
  );

  const turn = turns.length ? turns[turns.length - 1] : EMPTY;

  /** Start over. The back end holds no session, so forgetting here is the whole act. */
  const clear = useCallback(() => {
    stop();
    setTurns([]);
  }, [stop]);

  return { turns, turn, ask, stop, clear };
}

/** Parse one `event:`/`data:` pair and fold it into state. */
function apply(
  raw: string,
  setTurn: React.Dispatch<React.SetStateAction<TurnState>>,
  bufferRef: React.MutableRefObject<string>,
) {
  let event = '';
  let data = '';
  for (const line of raw.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7).trim();
    else if (line.startsWith('data: ')) data += line.slice(6);
  }
  if (!event || !data) return;

  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return; // a malformed frame is dropped, never thrown — one bad frame is not a dead turn
  }

  switch (event) {
    case 'stage':
      setTurn((t) => ({ ...t, stages: [...t.stages, payload as StageFrame] }));
      break;
    case 'route':
      setTurn((t) => ({ ...t, route: payload as RouteFrame }));
      break;
    case 'figure':
      setTurn((t) => ({ ...t, figures: [...t.figures, payload as FigureFrame] }));
      break;
    case 'evidence':
      setTurn((t) => ({ ...t, evidence: payload as EvidenceFrame }));
      break;
    case 'token':
      bufferRef.current += (payload as { text: string }).text;
      break;
    case 'no_diagnosis':
      setTurn((t) => ({ ...t, refusal: payload as NoDiagnosisFrame }));
      break;
    case 'audit':
      setTurn((t) => ({ ...t, audits: [...t.audits, payload as AuditFrame] }));
      break;
    case 'state':
      setTurn((t) => ({ ...t, state: payload as StateFrame }));
      break;
    case 'error':
      setTurn((t) => ({ ...t, error: (payload as { detail?: string }).detail ?? 'stream error' }));
      break;
    case 'done':
      break;
    default:
      // An unknown frame is ignored rather than thrown on. The contract gate is what stops
      // one appearing; this is the belt to its braces.
      break;
  }
}
