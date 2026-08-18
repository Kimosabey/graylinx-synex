'use client';

/**
 * What the platform can actually do right now, stated on every screen.
 *
 * **Why this is in the app bar and not on a status page.** Three facts change what an answer
 * on screen is worth, and all three can change without anything on the surface looking
 * different: whether the plant database is reachable, which measured window the data ends at,
 * and whether a real model is answering. A reader who does not know the model is stubbed will
 * read a stub's sentence as the product's judgement. So the bar carries them, on every
 * surface, rather than a page somebody has to think to visit.
 *
 * **The window used to be a hardcoded string.** `measured to 2026-06-23 11:50` was typed into
 * the topbar. It happened to be correct, which is what made it dangerous: it would have stayed
 * on screen, still looking authoritative, for however long it took someone to notice the
 * database had moved on. Constraint 15 says every artefact states its data window — a window
 * that cannot go stale is not stating anything, it is asserting. It now comes from
 * `/api/v1/health` or it does not appear at all.
 *
 * **Colour is never the only signal.** The dot has a word beside it, because the difference
 * between a stubbed model and a live one is the difference between a demonstration and an
 * answer, and no reader should have to distinguish two hues to know which they are looking at.
 *
 * **Degrading honestly is the whole point.** If health cannot be read, this says the platform's
 * state is unknown — it does not fall back to the last value it saw, and it does not render an
 * optimistic default. An unknown state shown as healthy is the failure this component exists
 * to prevent.
 */

import { useEffect } from 'react';
import { useApi } from '@/components/useApi';

/** How often the bar re-reads the platform's state. Long enough not to be chatter, short
 *  enough that a database that dropped out is not still reported as connected minutes later. */
const POLL_MS = 30_000;

interface Health {
  status: string;
  plant_database: {
    connected: boolean;
    host: string;
    database: string;
    read_only_by_grant: boolean;
    error: string | null;
  };
  model_mode: 'stub' | 'record' | 'live';
  /** Whether the box answered when asked. `null` in stub, where nothing is meant to be. */
  box_reachable: boolean | null;
  box_host: string;
  measured_window_end: string;
  policy_version: string;
  audit_trail: { rows: number; durable: boolean };
  equipment: { total: number; scoreable: number };
}

/** ISO timestamp to the form the window has always been written in. Seconds are dropped
 *  because the window is a clip boundary rather than a reading; the full value stays in the
 *  tooltip so nothing is lost, only quietened. */
function windowLabel(iso: string): string {
  return iso.replace('T', ' ').slice(0, 16);
}

export function SystemHealth() {
  const { data, error, loading, reload, endpoint } = useApi<Health>('/api/v1/health');

  useEffect(() => {
    const timer = setInterval(reload, POLL_MS);
    return () => clearInterval(timer);
  }, [reload]);

  if (loading && !data) {
    return (
      <span className="health" data-state="unknown">
        <span className="health-dot" aria-hidden="true" />
        <span className="health-word">checking</span>
      </span>
    );
  }

  if (error || !data) {
    return (
      <span
        className="health"
        data-state="down"
        title={`${endpoint ?? '/api/v1/health'} — ${error ?? 'no response'}. The platform's state is unknown; nothing on screen should be read as current.`}
      >
        <span className="health-dot" aria-hidden="true" />
        <span className="health-word">state unknown</span>
      </span>
    );
  }

  const db = data.plant_database;
  // A stubbed model is not a degraded platform — it is a platform that is deliberately not
  // answering with a model, and saying "degraded" would report a choice as a fault. But it is
  // never "live" either, and the bar has to be able to say which without a third vocabulary.
  // **Configured live and actually answering are different facts, and the bar reports the
  // second.** A chip reading "live model" while the tunnel to the box is down is the same
  // untruth as the one that read "stub" for a release while nobody looked — a claim about how
  // this process was configured, worn as a claim about what it can do. When the mode is live
  // and the box does not answer, the honest word is that it is unreachable.
  const boxDown = data.model_mode !== 'stub' && data.box_reachable === false;
  const state = !db.connected
    ? 'down'
    : data.model_mode === 'stub'
      ? 'stub'
      : boxDown
        ? 'down'
        : 'live';
  const word = !db.connected
    ? 'plant database down'
    : data.model_mode === 'stub'
      ? 'stub model'
      : boxDown
        ? 'model box unreachable'
        : 'live model';
  // Two labels, one shown per breakpoint — the same pattern the rail uses. A phone bar cannot
  // hold three full chips beside the lockup at 360px, and the half that gives way is the
  // wording rather than the fact. The dot never stands alone in either.
  const shortWord = !db.connected
    ? 'db down'
    : data.model_mode === 'stub'
      ? 'stub'
      : boxDown
        ? 'no box'
        : 'live';

  return (
    <span className="healthgroup">
      <span
        className="health"
        data-state={state}
        title={
          `Plant database: ${db.connected ? `connected to ${db.database} at ${db.host}` : `not connected — ${db.error ?? 'no reason given'}`}` +
          `${db.read_only_by_grant ? ', read-only by grant' : ''}. ` +
          `Model mode: ${data.model_mode}` +
          `${data.box_reachable === null ? '' : data.box_reachable ? `, answering at ${data.box_host}` : `, but ${data.box_host} did not answer`}. ` +
          `Policy ${data.policy_version}. ` +
          `Audit trail ${data.audit_trail.rows} row(s), ${data.audit_trail.durable ? 'durable' : 'not durable'}. ` +
          `${data.equipment.scoreable} of ${data.equipment.total} equipment scoreable.`
        }
      >
        <span className="health-dot" aria-hidden="true" />
        <span className="health-word long">{word}</span>
        <span className="health-word short">{shortWord}</span>
      </span>

      {/* Constraint 15: every artefact states its data window. Now read rather than asserted. */}
      <span
        className="window"
        title={`Constraint 15: every artefact states its data window. Readings after ${data.measured_window_end} are outside the measured clip.`}
      >
        {/* The visible wording is `aria-hidden` and the `.sr-only` copy is the announced one.
            Without that, every width above 640px reads "measured to" twice — the visible span and
            the screen-reader span are the same words, and only one of them should be spoken. */}
        <span className="long" aria-hidden="true">
          measured to{}
        </span>
        <span className="sr-only">measured to </span>
        {windowLabel(data.measured_window_end)}
      </span>
    </span>
  );
}
