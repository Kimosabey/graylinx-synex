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
