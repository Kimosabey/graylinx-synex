'use client';

/**
 * **One way to read the back end, so six surfaces fail the same way.**
 *
 * The API may not be running. Every surface has to render honestly when it is not, and the
 * failure mode this hook exists to prevent is not a crash — it is the three quieter ones:
 *
 * 1. a spinner that never resolves, which says *wait* forever and never says *it is down*;
 * 2. a fallback object, which silently substitutes invented figures for measured ones;
 * 3. a swallowed error, which renders an empty page that reads as a clean plant.
 *
 * So there are exactly three terminal shapes and no fourth: `loading`, `error`, or `data`. On
 * failure `data` stays `null` and `error` carries what actually went wrong, verbatim — a
 * status line or the fetch's own message, never a friendlier rewrite of it. Pair it with
 * `<Degraded>` from `components/Surface`.
 *
 * Nothing here formats a number. `FigureView` is still the only component that renders one.
 */

import { useCallback, useEffect, useState } from 'react';

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

export interface ApiResult<T> {
  data: T | null;
  /** The failure as it happened. `null` while loading and on success. */
  error: string | null;
  loading: boolean;
  /** The full URL that was asked, so a degraded state can name it. */
  endpoint: string | null;
  /** Ask again — for a retry control, or after something changed server-side. */
  reload: () => void;
}

/**
 * @param path an API path beginning with `/`, or `null` to hold off until it is known.
 *             Build it with `encodeURIComponent` for anything user- or data-derived.
 */
export function useApi<T>(path: string | null, init?: RequestInit): ApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    let live = true;

    setLoading(true);
    setError(null);

    fetch(`${API_BASE}${path}`, {
      credentials: 'include',
      signal: controller.signal,
      ...init,
    })
      .then(async (response) => {
        if (!live) return;
        if (!response.ok) {
          // The status line as the server gave it. A 503 is a different fact from a 404 and
          // the reader is the one who has to act on the difference.
          throw new Error(`${response.status} ${response.statusText}`.trim());
        }
        const body = (await response.json()) as T;
        if (!live) return;
        setData(body);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!live || controller.signal.aborted) return;
        setData(null);
        setError(cause instanceof Error ? cause.message : String(cause));
        setLoading(false);
      });

    return () => {
      live = false;
      controller.abort();
    };
    // `init` is deliberately not a dependency: an object literal at a call site is a new
    // reference every render, and depending on it would re-fetch forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, attempt]);

  return { data, error, loading, endpoint: path === null ? null : `${API_BASE}${path}`, reload };
}
