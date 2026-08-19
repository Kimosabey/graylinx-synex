'use client';

/**
 * `W1` — every work order that was actually raised.
 *
 * **Raised, not draftable, and the distinction is the whole screen.** A draft exists for every
 * one of the detected episodes: it is computed on demand from the evidence pack, and nothing is
 * written until somebody confirms it. Listing drafts here would put dozens of jobs on a surface
 * meant to show what has been *committed to* — and a planner reading it would schedule against
 * work nobody raised. Drafts stay on the case they came from, which is where the evidence to
 * judge them is.
 *
 * **Newest first, not ranked.** Severity is agreed for one fault class of nine (`Q49`), so
 * ordering by priority would present a ranking the formula cannot actually produce. Recency is
 * a fact about the record; priority ordering would be a claim about the plant.
 *
 * **An incomplete priority says so on the row.** Three of `W4`'s four inputs do not exist in
 * this snapshot, so a band shown without that caveat reads as a finished rank.
 */

import Link from 'next/link';
import { Degraded, EmptyState, PageHeader, Skeleton } from '@/components/Surface';
import { AskCopilot } from '@/components/AskCopilot';
import { Reveal } from '@/components/motion';
import { useApi } from '@/components/useApi';

interface RaisedWorkOrder {
  id: number;
  equipment_key: string;
  kind: string;
  state: string;
  priority: string;
  priority_is_complete: boolean;
  evidence_lines: number;
  created_at: string | null;
  closed_at: string | null;
}

interface WorkOrdersView {
  viewing_as: string;
  raised: RaisedWorkOrder[];
  count: number;
  store_note: string;
  draft_note: string;
  priority_note: string;
}

export default function WorkOrdersPage() {
  const { data, error, loading, endpoint } = useApi<WorkOrdersView>('/api/v1/work-orders');

  return (
    <>
      <PageHeader
        title="Work orders"
        lede="Every job that was actually raised, with the evidence that justified it and what its priority could and could not be computed from."
      />

      {loading && <Skeleton lines={3} label="Loading work orders" />}

      {error && (
        <Degraded
          what="The work order list could not be read"
          detail={error}
          endpoint={endpoint ?? undefined}
        />
      )}

      {data && (
        <>
          {/* The store being unreachable and nothing having been raised are different facts,
              and a list that cannot tell them apart shows a clean plant when the store is down. */}
          {data.store_note && <Degraded what="The store could not be reached" detail={data.store_note} />}

          {data.count === 0 && !data.store_note ? (
            <EmptyState
              title="No work order has been raised"
              because="Every detected episode can produce a draft on demand, and nothing is written until somebody confirms one. Open a case to see the job it would raise."
            >
              <Link href="/case">Open the cases</Link>
            </EmptyState>
          ) : (
            <section className="card">
              <h2>{data.count} raised</h2>

              {/* **The planner's view, and only what can be computed.** A maintenance screen
                  usually leads with MTTR and a repeat-issue rate. Both need closed jobs with
                  timestamps, and every job here is open — so those tiles would either read
                  "—" on a dashboard that looks broken, or be filled with a number nobody
                  measured. Counts by state and by kind need nothing that is missing.

                  Kind is the more useful of the two on this plant and it is unusual enough to
                  be worth showing: an *inspection* job carries the open checks as its task
                  list, an *authorisation* job carries a question for somebody to decide, and a
                  *corrective* job carries the repair. Three different people. */}
              <dl className="wo-summary">
                {Object.entries(
                  data.raised.reduce<Record<string, number>>((acc, wo) => {
                    acc[wo.state] = (acc[wo.state] ?? 0) + 1;
                    return acc;
                  }, {}),
                ).map(([state, n]) => (
                  <div key={state} className="wo-tile" data-state={state}>
                    <dt>{state}</dt>
                    <dd>{n}</dd>
                  </div>
                ))}
                {Object.entries(
                  data.raised.reduce<Record<string, number>>((acc, wo) => {
                    acc[wo.kind] = (acc[wo.kind] ?? 0) + 1;
                    return acc;
                  }, {}),
                ).map(([kind, n]) => (
                  <div key={kind} className="wo-tile" data-kind={kind}>
                    <dt>{kind}</dt>
                    <dd>{n}</dd>
                  </div>
                ))}
              </dl>

              <Reveal as="ul" className="reasons" runKey={data.count}>
                {data.raised.map((wo) => (
                  <li key={wo.id}>
                    <strong>{wo.equipment_key.replace('_', ' ')}</strong> · {wo.kind} · {wo.state}
                    {' · priority '}
                    {wo.priority}
                    {!wo.priority_is_complete && (
                      <span className="muted">
                        {' '}
                        — incomplete, reported with what was used rather than as a finished rank
                      </span>
                    )}
                    <div className="askcopilot-row">
                      <AskCopilot
                        question={`What happened on ${wo.equipment_key.replace('_', ' ')}?`}
                      >
                        Ask about this machine
                      </AskCopilot>
                    </div>
                    <div className="muted">
                      {wo.evidence_lines} evidence line(s) travel with this job
                      {wo.created_at ? ` · raised ${wo.created_at.slice(0, 16).replace('T', ' ')}` : ''}
                      {wo.closed_at ? ` · closed ${wo.closed_at.slice(0, 16).replace('T', ' ')}` : ' · open'}
                    </div>
                  </li>
                ))}
              </Reveal>
            </section>
          )}

          <section className="card supporting">
            <h2>What is not on this screen</h2>
            <p className="muted">{data.draft_note}</p>
            <p className="muted">{data.priority_note}</p>
          </section>
        </>
      )}
    </>
  );
}
