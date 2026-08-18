'use client';

/**
 * `U7` — the supervisor queue. Actions that cannot happen until something authorizes them.
 *
 * **Constraint 9 is the load-bearing rule on this screen, and it is a rule about absence.**
 * An approval request is never addressed to a person. A case escalated *up* for authority
 * lands unassigned, and the record behind this surface deliberately carries no field that
 * could hold a name. So there is no assignee, no approver, no owner and no "waiting on"
 * line anywhere below — not blank ones, not placeholder ones. Adding a slot for a person
 * would undo the thing the back end went out of its way to make impossible.
 *
 * **Constraint 25 is the trap.** This is not the reliability workspace with more rows. Every
 * section is admitted by a named capability — `approve_work`, `close_work` — and by nothing
 * else. A section this identity may not see is reported as *withheld with the capability
 * that would show it*, never dropped, and it is styled so it can never be mistaken for an
 * empty one: `EmptyState` says *we looked and there is nothing*, the withheld panel says
 * *nobody looked*, and those are opposite claims.
 *
 * **The separation law.** Synex FDD named the fault. The Control Plane ruled on the
 * authority and every card quotes that ruling verbatim. A formula sets priority — and this
 * queue is ordered by age alone, which the back end explains in its own words at the foot of
 * the page. The language model neither wrote, ranked nor chose anything here.
 *
 * **Nothing on this page is invented.** Every figure, every reason and every state word comes
 * off the response. Authorizing performs a real request and reports the real answer: if the
 * Control Plane does not accept the write, the card says so and no approval is shown as
 * having happened.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { IconAlert, IconCheck, IconHalt, IconShield } from '@/components/Icons';
import { Pressable, Reveal, ValueChange } from '@/components/motion';
import { Degraded, EmptyState, PageHeader, Skeleton, StateChip } from '@/components/Surface';
import { API_BASE, useApi } from '@/components/useApi';
import styles from './supervisor.module.css';

/* ── the response, as `app/services/queues.py` renders it ──────────────────── */

/** `G3`'s output, carried whole. `decision` is a string because a fifth value on the wire
 *  must render as itself rather than fall through to a default that softens it. */
interface Ruling {
  action: string;
  risk: string;
  decision: string;
  required_capability: string;
  reason: string;
  was_unclassified: boolean;
}

interface ApprovalRow {
  seed_key: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  state: string;
  asks: string;
  ruling: Ruling;
  task_is_a_question: boolean;
}

interface BlockedRow {
  seed_key: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  state: string;
  kind: string;
  reason: string;
}

interface ClosureRow {
  seed_key: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  block: string;
  reason: string;
  outcome: string;
}

interface AgeingRow {
  seed_key: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  kind: string;
  reason: string;
  action: string;
}

interface Withheld {
  section: string;
  capability: string;
  admitted: boolean;
  reason: string;
}

interface UnreadableCase {
  seed_key: string;
  state: string;
  reason: string;
}

interface SupervisorQueue {
  approvals: ApprovalRow[];
  blocked: BlockedRow[];
  closures: ClosureRow[];
  /** `RC9`'s two kinds, and there is deliberately no combined total anywhere. */
  condition_cleared: AgeingRow[];
  untouched: AgeingRow[];
  withheld: Withheld[];
  unreadable: UnreadableCase[];
  order_reason: string;
  ageing: string;
  viewing_as: string;
  store_note: string;
}

const ENDPOINT = '/api/v1/supervisor';

/** Where an authorization is written. Built from the seed key, encoded, never interpolated raw. */
const authorizePath = (seedKey: string) =>
  `/api/v1/supervisor/approvals/${encodeURIComponent(seedKey)}`;

/**
 * Sections that report their own withholding in the place the reader looks for them.
 *
 * Anything outside this set is caught by the summary at the foot of the page, so a section
 * the back end adds later cannot be dropped silently — which is the failure the response's
 * `withheld` list exists to prevent in the first place.
 */
const REPORTED_IN_PLACE = new Set(['awaiting_approval', 'blocked', 'uncleared_closures']);

/** The left-edge tone for a supporting row. Colour is never the only signal — every row that
 *  takes one of these also prints its kind as a word. */
const TONE: Record<string, string> = {
  not_evaluated: 'warn',
  unsettled_blocking_check: 'neutral',
  not_verified: 'neutral',
  verified_unknown: 'warn',
  verified_fail: 'stop',
  condition_cleared: 'ok',
  untouched: 'warn',
};

/* ── one approval ──────────────────────────────────────────────────────────── */

interface Sent {
  ok: boolean;
  detail: string;
  path: string;
}

/**
 * One case waiting on an authorization.
 *
 * The confirm step is a second, distinct surface rather than a browser dialog, and the
 * control that confirms is not the control that opened it. Authorizing dispatches a person,
 * so the consequence is restated in the back end's own words — `asks`, and the risk the
 * Control Plane assigned — immediately above the button that commits it.
 */
function Approval({ row, onDone }: { row: ApprovalRow; onDone: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<Sent | null>(null);
  const [returnFocus, setReturnFocus] = useState(false);
  const triggerRef = useRef<HTMLDivElement | null>(null);
  const confirmRef = useRef<HTMLDivElement | null>(null);
  const outcomeRef = useRef<HTMLDivElement | null>(null);

  const { ruling } = row;
  const mayProceed = ruling.decision === 'allowed';

  /* Focus follows the step, in all three directions. Each of these panels replaces the
     control that opened it, so without this the focus ring lands on `body` and a keyboard
     user has to tab back through the whole queue to reach the thing that just appeared. */

  // Opening the confirm step: onto the control that commits.
  useEffect(() => {
    if (!confirming) return;
    confirmRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
  }, [confirming]);

  // Cancelling: back onto the control that opened it, which has just remounted.
  useEffect(() => {
    if (!returnFocus) return;
    triggerRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    setReturnFocus(false);
  }, [returnFocus]);

  // The answer landing: onto the panel carrying it, so what happened is read out first.
  useEffect(() => {
    if (!sent) return;
    outcomeRef.current?.focus();
  }, [sent]);

  const authorize = useCallback(async () => {
    const path = authorizePath(row.seed_key);
    setSending(true);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: ruling.action,
          required_capability: ruling.required_capability,
        }),
      });
      // The status line as the server gave it, never a friendlier rewrite.
      setSent({
        ok: response.ok,
        detail: `${response.status} ${response.statusText}`.trim(),
        path,
      });
    } catch (cause: unknown) {
      setSent({ ok: false, detail: cause instanceof Error ? cause.message : String(cause), path });
    } finally {
      setSending(false);
      setConfirming(false);
    }
  }, [row.seed_key, ruling.action, ruling.required_capability]);

  const titleId = `ask-${row.seed_key}`;

  return (
    <li className={styles.item} data-decision={ruling.decision}>
      <div className={styles.head}>
        <div>
          {/* The fault the FDD rules named — the thing the authorization is about. */}
          <h3 className={styles.title} id={titleId}>
            {row.fault_label}
          </h3>
          <p className={styles.meta}>
            <span>{row.equipment_key}</span>
            <span>{row.day}</span>
            <span>{row.state}</span>
            <span>{row.seed_key}</span>
          </p>
        </div>

        {/* `NEEDS_APPROVAL` is one of the six answer states, so it takes the shared chip.
            The other rulings are not answer states and are printed as their own word. */}
        {ruling.decision === 'needs_approval' ? (
          <StateChip state="NEEDS_APPROVAL" />
        ) : (
          <span className={styles.decision} data-decision={ruling.decision}>
            {ruling.decision}
          </span>
        )}
      </div>

      <p className={styles.asks}>{row.asks}</p>

      <div className="row">
        {row.task_is_a_question && (
          <span className="badge verdict">a decision, not a measurement</span>
        )}
        {ruling.was_unclassified && (
          <span className="badge warn">unclassified action · treated as high risk</span>
        )}
      </div>

      {/* Constraint 9 lives here. A capability, and no place for a name. */}
      <div className={styles.capability}>
        <span className={styles.capLabel}>Capability required</span>
        <span className={styles.capName}>{ruling.required_capability || 'none stated'}</span>
        <p className={styles.capNote}>
          Addressed to the capability, not to a person. Whoever holds it may answer this; the
          case names nobody and has not been accepted by anybody.
        </p>
      </div>

      <div className={styles.evidence}>
        <span className={styles.evidenceLabel}>Evidence on the record</span>
        <dl className="kv">
          <dt>Equipment</dt>
          <dd className="mono">{row.equipment_key}</dd>
          <dt>Fault named</dt>
          <dd className="mono">{row.fault_label}</dd>
          <dt>Detected</dt>
          <dd className="mono">{row.day}</dd>
          <dt>Case state</dt>
          <dd className="mono">{row.state}</dd>
          <dt>Action</dt>
          <dd className="mono">{ruling.action}</dd>
          <dt>Risk</dt>
          <dd className="mono">{ruling.risk}</dd>
        </dl>
      </div>

      {/* The Control Plane's own words. Quoted, never paraphrased. */}
      <p className={styles.ruling}>{ruling.reason}</p>

      {!confirming && !sent && (
        <div className={styles.actions} ref={triggerRef}>
          {mayProceed ? (
            <Pressable
              className={styles.act}
              onClick={() => setConfirming(true)}
              ariaLabel={`Review and authorize ${ruling.action} on ${row.equipment_key}`}
            >
              <IconShield className="ico" />
              Review and authorize
            </Pressable>
          ) : (
            <p className={styles.cannot}>
              This cannot be authorized from here. The Control Plane returned{' '}
              <strong>{ruling.decision}</strong>, and its reason is quoted above.
            </p>
          )}
        </div>
      )}

      {confirming && (
        <div
          className={styles.confirm}
          ref={confirmRef}
          role="group"
          aria-labelledby={`confirm-${row.seed_key}`}
        >
          <p className={styles.confirmTitle} id={`confirm-${row.seed_key}`}>
            Confirm this authorization
          </p>
          <p className={styles.confirmBody}>
            This commits an action in the world rather than changing a note. Read what it
            does before you confirm it.
          </p>
          <ul className={styles.confirmList}>
            <li>
              Action <span className="mono">{ruling.action}</span> against case{' '}
              <span className="mono">{row.seed_key}</span> on{' '}
              <span className="mono">{row.equipment_key}</span>.
            </li>
            <li>
              Risk <span className="mono">{ruling.risk}</span>, admitted by{' '}
              <span className="mono">{ruling.required_capability || 'none stated'}</span>.
            </li>
            <li>{row.asks}</li>
          </ul>
          <div className={styles.actions}>
            <Pressable
              className={styles.act}
              onClick={authorize}
              disabled={sending}
              ariaLabel={`Confirm ${ruling.action} on ${row.equipment_key}`}
            >
              <IconCheck className="ico" />
              {sending ? 'Sending…' : 'Confirm — authorize'}
            </Pressable>
            <button
              type="button"
              className={styles.cancel}
              onClick={() => {
                setConfirming(false);
                setReturnFocus(true);
              }}
              disabled={sending}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {sent && (
        <div
          className={styles.outcome}
          data-ok={sent.ok}
          role="status"
          ref={outcomeRef}
          tabIndex={-1}
        >
          <p className={styles.outcomeTitle}>
            {sent.ok ? 'Recorded by the Control Plane' : 'Not recorded — nothing was written'}
          </p>
          <p className={styles.outcomeBody}>
            {sent.ok
              ? 'The Control Plane accepted the authorization. Reload the queue to read this case in its new state — nothing on this screen has been redrawn from an assumption.'
              : 'The request was made and did not land, so this case has not moved and no work has been raised. An authorization is shown here only when the Control Plane accepts it; this surface never records one locally and never renders an approval that did not happen.'}
          </p>
          <p className={styles.wire}>
            POST {API_BASE}
            {sent.path} → {sent.detail}
          </p>
          <div className={styles.actions}>
            <button type="button" className={styles.cancel} onClick={onDone}>
              Reload the queue
            </button>
            {/* A failed write leaves the case exactly where it was, so the same act is still
                available. Offered only on failure — a second press after a success would ask
                the Control Plane to authorize something twice. */}
            {!sent.ok && (
              <button
                type="button"
                className={styles.cancel}
                onClick={() => {
                  setSent(null);
                  setReturnFocus(true);
                }}
              >
                Try again
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

/* ── a section nobody was admitted to ──────────────────────────────────────── */

/**
 * A withheld section. Never an empty state, and the difference is the whole point: an empty
 * queue was read and held nothing; a withheld one was never read at all.
 */
function WithheldPanel({ entry }: { entry: Withheld }) {
  return (
    <div className={styles.withheld}>
      <IconShield className={styles.withheldIcon} />
      <div>
        <p className={styles.withheldTitle}>
          Not shown — this identity does not hold{' '}
          <span className="mono">{entry.capability}</span>
        </p>
        <p className={styles.withheldWhy}>{entry.reason}</p>
        <p className={styles.withheldWhy}>
          This section was not read. That is not a report that it is empty.
        </p>
      </div>
    </div>
  );
}

/* ── the surface ───────────────────────────────────────────────────────────── */

export default function SupervisorPage() {
  const { data, error, loading, endpoint, reload } = useApi<SupervisorQueue>(ENDPOINT);

  const withheldFor = (section: string) => data?.withheld.find((w) => w.section === section);

  const approvalsWithheld = withheldFor('awaiting_approval');
  const blockedWithheld = withheldFor('blocked');
  const closuresWithheld = withheldFor('uncleared_closures');

  // Everything the response withheld that no section above already reports for itself.
  const unreportedWithheld = data
    ? data.withheld.filter((entry) => !REPORTED_IN_PLACE.has(entry.section))
    : [];

  return (
    <>
      <PageHeader
        title="Supervisor queue"
        lede="Actions that cannot happen until something authorizes them — each one with the evidence on its record, the capability it requires, and the Control Plane's ruling in the Control Plane's own words."
        meta={
          data ? (
            <>
              Viewing as <span className="mono">{data.viewing_as}</span> · oldest first, which
              is not a ranking
            </>
          ) : (
            'Reading the approval queue'
          )
        }
        actions={
          <button type="button" className="btn ghost" onClick={reload} disabled={loading}>
            Reload
          </button>
        }
      />

      {/* `!data` matters: a reload keeps the previous response on screen while the next one
          is in flight, and rendering the skeleton as well would show the queue twice. */}
      {loading && !data && (
        <section className="card" aria-busy="true">
          <Skeleton lines={4} label="Reading the approval queue" />
        </section>
      )}

      {error && (
        <Degraded
          what="The approval queue"
          detail={error}
          endpoint={endpoint ?? undefined}
        >
          <p className="muted">
            No approval, no blocked case and no uncleared closure can be listed while this
            endpoint is unreachable, and none is being guessed at. Bring the Graylinx Synex
            back end up on the address above and press Reload; nothing on this surface will
            appear until it answers.
          </p>
        </Degraded>
      )}

      {data && (
        <>
          {/* The case store can be down while the API is up. Empty is not the same as none,
              and the response says which — so this renders whenever it has words. */}
          {data.store_note && <Degraded what="The case store" detail={data.store_note} />}

          {/* ── approvals ─────────────────────────────────────────────────── */}

          <section className="card" aria-labelledby="approvals">
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle} id="approvals">
                Awaiting authorization
              </h2>
              {!approvalsWithheld && (
                <span className={styles.count}>
                  <ValueChange value={String(data.approvals.length)} /> on this queue
                </span>
              )}
            </div>

            <p className={styles.sectionNote}>
              No request here is addressed to a person. A case escalated up for authority
              lands unassigned, and Graylinx Synex holds no field that could name an
              approver — the request is addressed to a capability, and whoever holds that
              capability may answer it.
            </p>

            {approvalsWithheld ? (
              <WithheldPanel entry={approvalsWithheld} />
            ) : data.approvals.length === 0 ? (
              <EmptyState
                title="Nothing is waiting on an authorization"
                because="The queue was read and no open case has reached a state that asks for authority. That is not a report of a clear plant: a case arrives here only after a fault is named and the case moves on, and an empty queue has never been evidence that nothing is wrong."
              />
            ) : (
              <Reveal as="ul" className={styles.queue} runKey={data.approvals.length}>
                {data.approvals.map((row) => (
                  <Approval key={row.seed_key} row={row} onDone={reload} />
                ))}
              </Reveal>
            )}
          </section>

          {/* ── blocked ───────────────────────────────────────────────────── */}

          <section className="card" aria-labelledby="blocked">
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle} id="blocked">
                Blocked — cases that cannot move
              </h2>
              {!blockedWithheld && (
                <span className={styles.count}>{data.blocked.length} on this queue</span>
              )}
            </div>

            <p className={styles.sectionNote}>
              A case with no blocking-check evaluation is reported as <em>not evaluated</em>,
              which is an absence rather than a pass. The two are never merged.
            </p>

            {blockedWithheld ? (
              <WithheldPanel entry={blockedWithheld} />
            ) : data.blocked.length === 0 ? (
              <EmptyState
                title="No case is blocked"
                because="The queue was read and no open case is waiting on a blocking check. A case whose blocking status nobody had evaluated would appear here as not evaluated rather than be counted as clear, so this emptiness means the cases were read — not that the checks were skipped."
              />
            ) : (
              <Reveal as="ul" className={styles.rows} runKey={data.blocked.length}>
                {data.blocked.map((row) => (
                  <li
                    key={row.seed_key}
                    className={styles.row}
                    data-tone={TONE[row.kind] ?? 'neutral'}
                  >
                    <h3 className={styles.rowTitle}>
                      {row.fault_label} · <span className="mono">{row.equipment_key}</span>
                    </h3>
                    <p className={styles.meta}>
                      <span>{row.day}</span>
                      <span>{row.state}</span>
                      <span>{row.seed_key}</span>
                    </p>
                    <p className={styles.rowWhy}>{row.reason}</p>
                    <span className={styles.kind}>{row.kind}</span>
                  </li>
                ))}
              </Reveal>
            )}
          </section>

          {/* ── closures ──────────────────────────────────────────────────── */}

          <section className="card" aria-labelledby="closures">
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle} id="closures">
                Closures verification has not cleared
              </h2>
              {!closuresWithheld && (
                <span className={styles.count}>{data.closures.length} on this queue</span>
              )}
            </div>

            <p className={styles.sectionNote}>
              Closing is gated by evidence rather than by authority. Holding every capability
              in the system does not clear one of these — post-work residuals against the
              asset&rsquo;s own band do.
            </p>

            {closuresWithheld ? (
              <WithheldPanel entry={closuresWithheld} />
            ) : data.closures.length === 0 ? (
              <EmptyState
                title="No closure is waiting on verification"
                because="The queue was read and every case whose work is done has cleared its check. A closure that had never been checked would be listed here rather than counted as closed, because a case cannot close unproven."
              />
            ) : (
              <Reveal as="ul" className={styles.rows} runKey={data.closures.length}>
                {data.closures.map((row) => (
                  <li
                    key={row.seed_key}
                    className={styles.row}
                    data-tone={TONE[row.block] ?? 'neutral'}
                  >
                    <h3 className={styles.rowTitle}>
                      {row.fault_label} · <span className="mono">{row.equipment_key}</span>
                    </h3>
                    <p className={styles.meta}>
                      <span>{row.day}</span>
                      <span>{row.seed_key}</span>
                    </p>
                    <p className={styles.rowWhy}>{row.reason}</p>
                    <p className="mono">{row.outcome}</p>
                    <span className={styles.kind}>{row.block}</span>
                  </li>
                ))}
              </Reveal>
            )}
          </section>

          {/* ── ageing ────────────────────────────────────────────────────── */}

          <section className="card" aria-labelledby="ageing">
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle} id="ageing">
                Cases that have aged
              </h2>
            </div>

            {blockedWithheld ? (
              /* `RC9`'s verdicts are gathered with the blocked section, so when that is
                 withheld nothing here was examined. The body is the response's own sentence,
                 which says in as many words that this is not a claim that nothing has aged —
                 rather than the generic admission reason, which would repeat the section
                 above it verbatim. */
              <div className={styles.withheld}>
                <IconShield className={styles.withheldIcon} />
                <div>
                  <p className={styles.withheldTitle}>
                    Not read — needs <span className="mono">{blockedWithheld.capability}</span>
                  </p>
                  <p className={styles.withheldWhy}>{data.ageing}</p>
                </div>
              </div>
            ) : data.condition_cleared.length === 0 && data.untouched.length === 0 ? (
              <EmptyState
                title="No case has aged"
                because="The verdicts were read and none of the open cases is stale by either measure. This is the queue reporting what it read, not an assumption about the ones it could not see."
              />
            ) : (
              <>
                <p className={styles.sectionNote}>{data.ageing}</p>

                {/* Two lists, and deliberately no combined total. A machine that fixed itself
                    and a case nobody opened must never be one number. */}
                <h3 className={`${styles.subhead} ${styles.subheadFirst}`}>
                  The condition cleared — {data.condition_cleared.length}
                </h3>
                {data.condition_cleared.length === 0 ? (
                  <p className={styles.sectionNote}>
                    No open case had its condition clear. Counted separately from the one
                    below, and never added to it.
                  </p>
                ) : (
                  <Reveal
                    as="ul"
                    className={styles.rows}
                    runKey={data.condition_cleared.length}
                  >
                    {data.condition_cleared.map((row) => (
                      <li
                        key={row.seed_key}
                        className={styles.row}
                        data-tone={TONE[row.kind] ?? 'neutral'}
                      >
                        <h4 className={styles.rowTitle}>
                          {row.fault_label} · <span className="mono">{row.equipment_key}</span>
                        </h4>
                        <p className={styles.meta}>
                          <span>{row.day}</span>
                          <span>{row.seed_key}</span>
                        </p>
                        <p className={styles.rowWhy}>{row.reason}</p>
                        <p className={styles.rowAction}>{row.action}</p>
                      </li>
                    ))}
                  </Reveal>
                )}

                <h3 className={styles.subhead}>Nobody has touched it — {data.untouched.length}</h3>
                {data.untouched.length === 0 ? (
                  <p className={styles.sectionNote}>
                    Every open case has been touched. Counted separately from the one above,
                    and never added to it.
                  </p>
                ) : (
                  <Reveal as="ul" className={styles.rows} runKey={data.untouched.length}>
                    {data.untouched.map((row) => (
                      <li
                        key={row.seed_key}
                        className={styles.row}
                        data-tone={TONE[row.kind] ?? 'neutral'}
                      >
                        <h4 className={styles.rowTitle}>
                          {row.fault_label} · <span className="mono">{row.equipment_key}</span>
                        </h4>
                        <p className={styles.meta}>
                          <span>{row.day}</span>
                          <span>{row.seed_key}</span>
                        </p>
                        <p className={styles.rowWhy}>{row.reason}</p>
                        <p className={styles.rowAction}>{row.action}</p>
                      </li>
                    ))}
                  </Reveal>
                )}
              </>
            )}
          </section>

          {/* ── sections this identity was not admitted to ────────────────── */}

          {/* The catch-all, and it is normally absent: the three sections this surface knows
              about each report their own withholding above. This exists so a section the back
              end adds later is still reported rather than dropped. */}
          {unreportedWithheld.length > 0 && (
            <section className="card" aria-labelledby="withheld">
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle} id="withheld">
                  Further sections not shown — {unreportedWithheld.length}
                </h2>
              </div>
              <p className={styles.sectionNote}>
                Reported rather than omitted, and each one names the capability that would
                show it. Nothing here is unlocked by seniority: a supervisor is not a more
                capable technician, and the queue holds no ladder to climb.
              </p>
              <Reveal as="ul" className={styles.rows} runKey={unreportedWithheld.length}>
                {unreportedWithheld.map((entry) => (
                  <li key={entry.section}>
                    <div className={styles.withheld}>
                      <IconHalt className={styles.withheldIcon} />
                      <div>
                        <p className={styles.withheldTitle}>
                          <span className="mono">{entry.section}</span> — needs{' '}
                          <span className="mono">{entry.capability}</span>
                        </p>
                        <p className={styles.withheldWhy}>{entry.reason}</p>
                      </div>
                    </div>
                  </li>
                ))}
              </Reveal>
            </section>
          )}

          {/* ── cases the machine could not place ─────────────────────────── */}

          {data.unreadable.length > 0 && (
            <section className="card" aria-labelledby="unreadable">
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle} id="unreadable">
                  Cases not placed in any section — {data.unreadable.length}
                </h2>
              </div>
              <p className={styles.sectionNote}>
                Listed rather than dropped. A case that vanishes because a string did not
                parse leaves a queue that looks calm and is not.
              </p>
              <Reveal as="ul" className={styles.rows} runKey={data.unreadable.length}>
                {data.unreadable.map((row) => (
                  <li key={row.seed_key} className={styles.row} data-tone="warn">
                    <h3 className={styles.rowTitle}>
                      <span className="mono">{row.seed_key}</span>
                    </h3>
                    <p className={styles.rowWhy}>{row.reason}</p>
                    <span className={styles.kind}>{row.state}</span>
                  </li>
                ))}
              </Reveal>
            </section>
          )}

          {/* ── how the queue was assembled ───────────────────────────────── */}

          <section className="card supporting measure" aria-labelledby="how">
            <h2 className={styles.sectionTitle} id="how">
              How this queue is ordered, and who decided what
            </h2>
            <p className="muted">{data.order_reason}</p>
            <p className="muted">
              <IconAlert className={styles.inlineIcon} /> Synex FDD named the fault on every card. The
              Control Plane ruled on the authority, and each card quotes that ruling rather
              than summarising it. A deterministic formula sets priority; the order here is
              age alone. The language model wrote none of this, ranked none of it, and
              decided nothing about what belongs on this screen.
            </p>
          </section>
        </>
      )}
    </>
  );
}
