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
}

export interface TurnState {
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

export function useTurn() {
  const [turn, setTurn] = useState<TurnState>(EMPTY);
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
  }, []);

  useEffect(() => stop, [stop]);

  const ask = useCallback(
    async (body: AskBody) => {
      // The dev double-mount guard. Without it one question opens two streams.
      if (readingRef.current) return;
      readingRef.current = true;

      const controller = new AbortController();
      abortRef.current = controller;
      bufferRef.current = '';
      setTurn({ ...EMPTY, streaming: true });

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
          body: JSON.stringify(body),
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
    [],
  );

  return { turn, ask, stop };
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
