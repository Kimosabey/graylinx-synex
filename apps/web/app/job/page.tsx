'use client';

/**
 * **The technician job pack — `U3`, `RC3`, `RC4`, `W2`–`W4`, `W9`.**
 *
 * The hardest screen in the product, because of where it is read rather than what it holds: a
 * phone, one-handed, in a plant room, possibly gloved, possibly in poor light. `CONTEXT.md`
 * §10d puts the work, its checklists and the explicit *cannot check* in this person’s hands
 * while they are standing at the machine — so the layout is small-screen first and the desk
 * gets what is left over. Nothing is a dense table, nothing depends on hover, every target
 * clears 44px, and the next action is never more than one screen away.
 *
 * **Safety and any holding action lead.** They are the first card, before the machine’s
 * findings and before the evidence, and they are not one item among others. On this episode
 * both of the instructions a hazard would carry are *absent*, and the absence is stated in
 * words rather than left as blank space: `CONTEXT.md` inherited constraint 10 is that no
 * interim holding action ships unreviewed, and constraint 7 in its safety form is that an
 * unassessed condition is not a safe one. A blank space would read as a clearance.
 *
 * **Two endpoints, and each fails on its own.**
 *
 * | What | Endpoint |
 * |---|---|
 * | The job, its priority, its evidence, what closes it | `/api/v1/episodes/{id}/work-order` |
 * | The checks that belong to *this capability* | `/api/v1/episodes/{id}/case?viewing_as=technician` |
 * | The jobs there are to pick from | `/api/v1/episodes` |
 *
 * They are read separately so one being down degrades one section rather than the page. Every
 * figure, every sentence and every source line on this screen came off one of those three
 * responses; nothing on it is composed here.
 *
 * **The separation law, made visible rather than asserted.** The fault label came from the
 * deterministic isolation path, the priority band from a formula over fault class and
 * persistence, and the close gate from post-work residuals against this asset’s own band. The
 * language model named none of them, and the copy on this screen never implies it did.
 *
 * **What this surface deliberately cannot do.** It records nothing. There is no route on the
 * API that accepts a finding, so the record control holds an answer on this screen and says
 * so — a control that looked like it had saved something would be worse than no control.
 */

import { useEffect, useMemo, useState } from 'react';
import { IconAlert, IconClipboard } from '@/components/Icons';
import { Degraded, EmptyState, PageHeader, Skeleton } from '@/components/Surface';
import { Reveal } from '@/components/motion';
import { useApi } from '@/components/useApi';
import styles from './job.module.css';

/* ── the shapes the back end actually returns ─────────────────────────────────
 *
 * Mirrored from `backend/app/services/work_orders.py` (`WorkOrderDraft.as_dict`) and
 * `backend/app/services/cases.py` (`Case.as_dict`), read from the live responses rather than
 * guessed. Every field below appears in one of them.
 */

interface EpisodeRow {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  slot_count: number;
  first_slot: string;
  last_slot: string;
}

interface EpisodeList {
  window: { end: string; includes_simulated: boolean; note: string };
  episode_count: number;
  equipment_days: number;
  episodes: EpisodeRow[];
}

interface MissingInput {
  input: string;
  why: string;
}

interface Priority {
  band: string;
  fault_label: string;
  severity: string;
  slot_count: number;
  sustained: boolean;
  used: string[];
  missing: MissingInput[];
  is_complete: boolean;
  explanation: string;
}

interface EvidenceLine {
  kind: string;
  text: string;
  source: string;
}

interface WorkOrder {
  is_draft: boolean;
  equipment_key: string;
  equipment_display: string;
  fault_label: string;
  day: string;
  title: string;
  priority: Priority;
  evidence: EvidenceLine[];
  cannot_close_until: string[];
  warnings: string[];
}

interface MyItem {
  id: string;
  text: string;
  capability: string;
  blocking: boolean;
  is_sample: boolean;
  stored_reading: string;
  finding: string;
}

interface OtherItem {
  id: string;
  text: string;
  capability: string;
}

interface CaseView {
  id: string;
  equipment_display: string;
  fault_label: string;
  state: string;
  content_is_sample: boolean;
  content_note: string;
  unreviewed_in_library: number;
  may_advance: boolean;
  advance_reason: string;
  operator_can_start: boolean;
  viewing_as: string;
  my_items: MyItem[];
  for_others: OtherItem[];
}

/* ── the five answers a check can take ────────────────────────────────────────
 *
 * `RC4` and `RC10`, and the distinctions are load-bearing rather than cosmetic. Two of them
 * are named in `CONTEXT.md` as inherited constraints in their own right:
 *
 * - constraint 8 — `cannot_check` is separate from `not applicable`. Six “N/A” presses once
 *   opened a blocking gate with zero evidence behind it. One is a statement about the person,
 *   the other a statement about the machine, and collapsing them is how a safety gate gets
 *   walked past.
 * - constraint 20 — an estimate does not settle a blocking check. On the reference plant an
 *   untagged answer defaulted to `estimated` and opened a blocking gate.
 *
 * `measured` and `not_answered` come back on every item the case returns, so all five are
 * this API’s own vocabulary and none of them is invented here. Only the first settles.
 */
const FINDING_KINDS = [
  {
    value: 'measured',
    label: 'Measured',
    settles: true,
    note: 'A reading taken now. The only answer that settles a blocking check.',
  },
  {
    value: 'estimated',
    label: 'Estimated',
    settles: false,
    note: 'A judgement rather than a reading. It leaves a blocking check open.',
  },
  {
    value: 'cannot_check',
    label: 'Cannot check',
    settles: false,
    note: 'You cannot perform this check. Not the same as not applicable, and it leaves the check open.',
  },
  {
    value: 'not_applicable',
    label: 'Not applicable',
    settles: false,
    note: 'This check does not apply to this machine. A statement about the equipment, not about you.',
  },
  {
    value: 'not_answered',
    label: 'Not answered',
    settles: false,
    note: 'Nobody has looked yet.',
  },
] as const;

const SETTLES = 'measured';

/** The path builder. The id carries colons, so it is encoded rather than interpolated raw. */
const path = (id: string, tail: string) => `/api/v1/episodes/${encodeURIComponent(id)}/${tail}`;

export default function JobPage() {
  const episodes = useApi<EpisodeList>('/api/v1/episodes');
  const [picked, setPicked] = useState<string | null>(null);

  /**
   * **Never an empty screen.** A technician who opens the pack without a job selected gets a
   * real one — the longest-running episode in the measured window, because the longest run is
   * the one with the most readings behind it and therefore the most to work from. The choice
   * is stated on the screen with its reason, not made silently.
   */
  const fallback = useMemo(() => {
    const rows = episodes.data?.episodes ?? [];
    if (rows.length === 0) return null;
    return rows.reduce((longest, row) => (row.slot_count > longest.slot_count ? row : longest));
  }, [episodes.data]);

  const episodeId = picked ?? fallback?.id ?? null;
  const selected = useMemo(
    () => episodes.data?.episodes.find((row) => row.id === episodeId) ?? null,
    [episodes.data, episodeId],
  );

  const job = useApi<WorkOrder>(episodeId ? path(episodeId, 'work-order') : null);
  const checks = useApi<CaseView>(
    episodeId ? `${path(episodeId, 'case')}?viewing_as=technician` : null,
  );

  /**
   * What has been answered on *this screen*, keyed by item id. Cleared whenever the job
   * changes: carrying an answer from one machine onto another is the one bug a findings
   * control must never have.
   */
  const [answers, setAnswers] = useState<Record<string, string>>({});
  useEffect(() => setAnswers({}), [episodeId]);

  const wo = job.data;
  const caseView = checks.data;

  const answerFor = (item: MyItem) => answers[item.id] ?? item.finding;

  /** The blocking check that is still open — the one thing this person is here to do. */
  const nextBlocking = caseView?.my_items.find(
    (item) => item.blocking && answerFor(item) !== SETTLES,
  );

  /** Evidence, grouped by the kind the back end tagged it with. No kind is renamed here. */
  const evidenceByKind = useMemo(() => {
    const groups = new Map<string, EvidenceLine[]>();
    for (const line of wo?.evidence ?? []) {
      const bucket = groups.get(line.kind);
      if (bucket) bucket.push(line);
      else groups.set(line.kind, [line]);
    }
    return [...groups.entries()];
  }, [wo]);

  return (
    <>
      <PageHeader
        title={wo ? wo.equipment_display : 'Technician job pack'}
        lede={
          'The job pack, as Graylinx Synex would hand it to the technician standing at the ' +
          'machine: what was found, what to check, and what has to be true before it can be ' +
          'closed. It is a draft — nothing here has been dispatched, and nothing on this ' +
          'screen is saved.'
        }
        meta={
          <>
            {wo && (
              <>
                <span className={styles.faultLabel}>{wo.fault_label}</span> · {wo.day} ·{' '}
              </>
            )}
            {episodes.data
              ? `measured window ends ${episodes.data.window.end.replace('T', ' ')} · ${
                  episodes.data.window.note
                }`
              : 'reading the measured window…'}
          </>
        }
      />

      {/* ── 1 · safety and any holding action — first, and not one item among others ──── */}

      <section className={`card ${styles.lead}`} aria-labelledby="job-safety">
        <div className={styles.leadHead}>
          <IconAlert className={styles.leadIco} />
          <h2 id="job-safety">
            Before you touch {wo ? wo.equipment_display : 'this machine'}
          </h2>
        </div>

        {job.loading && <Skeleton lines={3} label="Reading what travels with this job" />}

        {job.error && (
          <Degraded
            what="The job draft"
            detail={job.error}
            endpoint={job.endpoint ?? undefined}
          >
            <p className={styles.because}>
              Nothing is shown in its place. Treat this screen as carrying no instruction at
              all until the back end answers — start it and reload.
            </p>
          </Degraded>
        )}

        {wo && (
          <>
            {wo.warnings.length > 0 ? (
              <Reveal as="ul" className={styles.warnings} runKey={wo.warnings.length}>
                {wo.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </Reveal>
            ) : (
              <p className={styles.because}>
                The job draft carries no warning about the evidence behind it.
              </p>
            )}

            {/* The two instructions a hazard would carry, stated as absences rather than
                omitted. `S6` raises a human instruction and never stops a machine, and
                constraint 10 keeps every drafted holding action switched off until a
                refrigeration engineer has read it. Blank space here would read as a
                clearance, which is the one thing it must not read as. */}
            <ul className={styles.absences}>
              <li>No holding action travels with this job.</li>
              <li>No stop instruction travels with this job.</li>
            </ul>
            <p className={styles.because}>
              Neither is a clearance. Nothing was attached to this job, which is not the same
              as something having been assessed and found unnecessary — no interim holding
              action ships unreviewed, and an unassessed condition is not a safe one.
            </p>
          </>
        )}

        {nextBlocking && (
          <a className={styles.primary} href={`#check-${nextBlocking.id}`}>
            <IconClipboard className={styles.foldIco} />
            Take the reading that is blocking this job
          </a>
        )}
      </section>

      {/* ── 2 · what was found, and who decided the priority ─────────────────────────── */}

      <section className="card" aria-labelledby="job-found">
        <h2 id="job-found">What was found</h2>

        {job.loading && <Skeleton lines={4} label="Reading the job draft" />}

        {wo && (
          <>
            <div className={styles.ident}>
              <span className={styles.faultLabel}>{wo.fault_label}</span>
              <span className="pri" data-band={wo.priority.band}>
                {wo.priority.band}
              </span>
              {wo.is_draft && <span className={styles.draftTag}>draft · not dispatched</span>}
            </div>

            <p className={styles.explain}>{wo.priority.explanation}</p>

            {wo.priority.missing.length > 0 && (
              <Reveal
                as="ul"
                className={styles.missing}
                runKey={`${wo.fault_label}-${wo.priority.missing.length}`}
                aria-label="Priority inputs that are missing"
              >
                {wo.priority.missing.map((gap) => (
                  <li key={gap.input}>
                    <span className={styles.input}>{gap.input}</span>
                    {gap.why}
                  </li>
                ))}
              </Reveal>
            )}

            <p className={styles.law}>
              The isolation path named the fault. A formula over fault class and persistence
              set the band — never how far a residual sits outside its band, because non-faults
              were measured to deviate more than faults do. Neither is a language-model
              judgement, and neither is anyone’s opinion of the machine.
            </p>
          </>
        )}
      </section>

      {/* ── 3 · the checks that are yours ────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="job-checks">
        <h2 id="job-checks">What to check</h2>

        {checks.loading && <Skeleton lines={4} label="Reading the checks for this capability" />}

        {checks.error && (
          <Degraded
            what="The checklist for this capability"
            detail={checks.error}
            endpoint={checks.endpoint ?? undefined}
          >
            <p className={styles.because}>
              No checks are shown and none are being guessed. The job above still stands; the
              list of what to do about it does not exist on this screen until the case store
              answers.
            </p>
          </Degraded>
        )}

        {caseView && caseView.my_items.length === 0 && (
          <EmptyState
            title={`No checks are tagged to ${caseView.viewing_as} on this job`}
            because={caseView.content_note}
          />
        )}

        {caseView && caseView.my_items.length > 0 && (
          <>
            {caseView.content_is_sample && (
              <p className={styles.because}>{caseView.content_note}</p>
            )}

            <Reveal
              as="ul"
              className={styles.checks}
              runKey={`${caseView.id}-${caseView.my_items.length}`}
              aria-label={`Checks for ${caseView.viewing_as}`}
            >
              {caseView.my_items.map((item) => {
                const chosen = answerFor(item);
                const kind = FINDING_KINDS.find((k) => k.value === chosen);
                return (
                  <li
                    key={item.id}
                    id={`check-${item.id}`}
                    className={styles.check}
                    data-blocking={item.blocking}
                  >
                    <div className={styles.checkTop}>
                      {item.blocking && (
                        <span className={styles.tag} data-blocking="true">
                          blocking
                        </span>
                      )}
                      <span className={styles.tag}>{item.capability}</span>
                      {item.is_sample && (
                        <span className={styles.tag} data-sample="true">
                          sample content
                        </span>
                      )}
                    </div>

                    <p className={styles.checkText}>{item.text}</p>
                    <span className={styles.storedReading}>{item.stored_reading}</span>

                    <span className={styles.recordLabel} id={`record-${item.id}`}>
                      Record what you found
                    </span>
                    <div
                      className={styles.record}
                      role="group"
                      aria-labelledby={`record-${item.id}`}
                    >
                      {FINDING_KINDS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          aria-pressed={chosen === option.value}
                          data-settles={option.settles}
                          onClick={() =>
                            setAnswers((previous) => ({
                              ...previous,
                              [item.id]: option.value,
                            }))
                          }
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>

                    {kind && (
                      <p className={styles.chosen}>
                        <strong>{kind.value}</strong> — {kind.note}
                      </p>
                    )}
                  </li>
                );
              })}
            </Reveal>

            <p className={styles.because}>
              Answers are held on this screen and go no further. There is no route on the API
              that accepts a finding, so nothing you press here is stored against the case, and
              the gate below is the case store’s own reading rather than a response to it.
            </p>

            <p className={styles.gateLine} data-may-advance={caseView.may_advance}>
              <span className={styles.gateWord}>
                Case state · {caseView.state} · {caseView.may_advance ? 'can advance' : 'cannot advance'}
              </span>{' '}
              {caseView.advance_reason}
            </p>
          </>
        )}
      </section>

      {/* ── 4 · the checks that are not yours — collapsed, never greyed out ──────────── */}

      {caseView && caseView.for_others.length > 0 && (
        <details className={styles.fold}>
          <summary>
            <IconAlert className={styles.foldIco} />
            {caseView.for_others.length} checks on this case belong to another capability
          </summary>
          <div className={styles.foldBody}>
            <p className={styles.because}>
              Folded away rather than greyed out. A greyed row still reads as a demand on
              whoever is standing there, and an operator must never be blocked by a check they
              cannot perform. These are here so you know they exist and who has them.
            </p>
            {/* Constraint 37 — every fault class must carry at least one check the operator
                can do, so somebody is never stuck at the start. The flag is read off the case
                rather than inferred from the list below. */}
            <span className={styles.gateWord}>
              operator can start · {String(caseView.operator_can_start)}
            </span>
            <Reveal
              as="ul"
              className={styles.plain}
              runKey={`${caseView.id}-others-${caseView.for_others.length}`}
            >
              {caseView.for_others.map((item) => (
                <li key={item.id}>
                  <span className={styles.capability}>{item.capability}</span>
                  {item.text}
                </li>
              ))}
            </Reveal>
          </div>
        </details>
      )}

      {/* ── 5 · what has to be true before it closes ─────────────────────────────────── */}

      {wo && wo.cannot_close_until.length > 0 && (
        <section className="card" aria-labelledby="job-close">
          <h2 id="job-close">What has to be true before this can close</h2>
          <Reveal
            as="ul"
            className={styles.closers}
            runKey={`${wo.fault_label}-${wo.cannot_close_until.length}`}
          >
            {wo.cannot_close_until.map((condition) => (
              <li key={condition}>{condition}</li>
            ))}
          </Reveal>
          <p className={styles.law}>
            A closure note is not one of them. Whether the repair worked is decided by
            post-work residuals against this asset’s own band and a deterministic rule over
            them — not by what anyone writes in the box, and not by the language model.
          </p>
        </section>
      )}

      {/* ── 6 · the evidence the job carries with it ─────────────────────────────────── */}

      {wo && wo.evidence.length > 0 && (
        <details className={styles.fold}>
          <summary>
            <IconClipboard className={styles.foldIco} />
            The {wo.evidence.length} lines of evidence this job carries
          </summary>
          <div className={styles.foldBody}>
            <p className={styles.because}>
              Work that arrives carrying its own justification. Every line came with the job
              rather than being looked up afterwards, and every one names where it came from.
            </p>
            {evidenceByKind.map(([kind, lines]) => (
              <section key={kind} aria-labelledby={`evidence-${kind}`}>
                <h3 className={styles.kindHead} id={`evidence-${kind}`}>
                  {kind} · {lines.length}
                </h3>
                <Reveal as="ul" className={styles.evidence} runKey={`${kind}-${lines.length}`}>
                  {lines.map((line) => (
                    <li key={line.text}>
                      {line.text}
                      <span className={styles.source}>{line.source}</span>
                    </li>
                  ))}
                </Reveal>
              </section>
            ))}
          </div>
        </details>
      )}

      {/* ── 7 · which job this is, and how to open another ───────────────────────────── */}

      <details className={styles.fold}>
        <summary>
          <IconClipboard className={styles.foldIco} />
          {picked ? 'This job, and the others on this plant' : 'Why this job opened, and the others'}
        </summary>
        <div className={styles.foldBody}>
          {episodes.loading && <Skeleton lines={3} label="Reading the jobs on this plant" />}

          {episodes.error && (
            <Degraded
              what="The list of jobs"
              detail={episodes.error}
              endpoint={episodes.endpoint ?? undefined}
            />
          )}

          {episodes.data && episodes.data.episodes.length === 0 && (
            <EmptyState
              title="No episodes in the measured window"
              because={`Nothing was detected between the start of the snapshot and ${episodes.data.window.end}. ${episodes.data.window.note}. An empty list means nothing was diagnosed here, never that the plant is clean.`}
            />
          )}

          {episodes.data && episodes.data.episodes.length > 0 && (
            <>
              {!picked && selected && (
                <p className={styles.chosenNote}>
                  No job was selected, so this pack opened{' '}
                  <span className={styles.faultLabel}>{selected.id}</span> — the
                  longest-running episode in the measured window at {selected.slot_count} slots,
                  which is the one with the most readings behind it to work from.
                </p>
              )}
              <p className={styles.because}>
                {episodes.data.episode_count} episodes across {episodes.data.equipment_days}{' '}
                equipment-days. {episodes.data.window.note}.
              </p>

              <Reveal
                as="ul"
                className={styles.jobs}
                runKey={episodes.data.episodes.length}
                aria-label="Jobs on this plant"
              >
                {episodes.data.episodes.map((row) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      className={styles.jobBtn}
                      aria-current={row.id === episodeId}
                      onClick={() => setPicked(row.id)}
                    >
                      <span className={styles.jobName}>{row.fault_label}</span>
                      <span className={styles.jobMeta}>
                        {row.equipment_key} · {row.day} · {row.slot_count} slots ·{' '}
                        {row.first_slot.replace('T', ' ')} to {row.last_slot.replace('T', ' ')}
                      </span>
                    </button>
                  </li>
                ))}
              </Reveal>
            </>
          )}
        </div>
      </details>
    </>
  );
}
