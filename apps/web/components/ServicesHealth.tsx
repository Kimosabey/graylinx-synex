'use client';

/**
 * Every capability the platform depends on, and which of them are actually up.
 *
 * **Three states, not two, and that is the whole reason this exists.** `available`,
 * `degraded` and **`unknown`** are three different facts: a capability nobody probed is not a
 * working one, and a panel that painted it green would be reporting a guess as a measurement.
 * Four of the seven are `unknown` right now — the honest answer, and one a reader can act on.
 *
 * The app bar carries the two facts that change what an *answer* is worth — the plant database
 * and the model mode. This is the fuller picture, and it belongs on the governance surface
 * rather than in the bar: it is read when something is wrong, not on every turn.
 *
 * **Every row carries its reason in the platform's own words.** A red dot with no sentence
 * tells somebody to go and find out; the sentence is what they were going to find.
 */

import { Degraded, Skeleton } from '@/components/Surface';
import { Reveal } from '@/components/motion';
import { useApi } from '@/components/useApi';

interface CapabilityState {
  capability: string;
  availability: 'available' | 'degraded' | 'unknown' | string;
  reason: string;
}

interface DegradedView {
  headline: string;
  capabilities_reported: number;
  degraded: string[];
  unknown: string[];
  fully_available: string[];
  states: CapabilityState[];
}

/** How each state reads to somebody deciding whether to trust what is on screen. */
const MEANING: Record<string, string> = {
  available: 'working',
  degraded: 'not working',
  unknown: 'not probed — this is not the same as working',
};

export function ServicesHealth() {
  const { data, error, loading, endpoint } = useApi<DegradedView>('/api/v1/degraded');

  if (loading) return <Skeleton lines={3} label="Reading capability states" />;

  if (error || !data) {
    return (
      <Degraded
        what="The capability states could not be read"
        detail={error ?? 'no response'}
        endpoint={endpoint ?? undefined}
      />
    );
  }

  return (
    <section className="card" aria-labelledby="services">
      <h2 id="services">Services</h2>
      <p className="muted">{data.headline}</p>

      <Reveal as="ul" className="services" runKey={data.states.length}>
        {data.states.map((s) => (
          <li key={s.capability} data-state={s.availability}>
            <span className="services-name">{s.capability.replace(/_/g, ' ')}</span>
            <span className="services-state">
              {s.availability} — {MEANING[s.availability] ?? 'state not recognised'}
            </span>
            <span className="muted services-reason">{s.reason}</span>
          </li>
        ))}
      </Reveal>
    </section>
  );
}
