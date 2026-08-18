'use client';

/**
 * **One case — the spine of the product.** `RC1`–`RC18`, on the surface `CONTEXT.md` §10d
 * gives to Reliability and Supervisor.
 *
 * The page is the case lifecycle in the order it actually runs, and the order is the argument:
 *
 * ```
 * detected → the gates → the evidence → the differential → the checks → the work → verified
 * ```
 *
 * The reader meets the **gates before the evidence** and the **evidence before the work**,
 * because that is the direction the claim travels. A deterministic gate decides whether
 * anything may be judged at all; the trained model's residuals are what was measured; the
 * isolation path names the fault class; a formula sets the priority; the Control Plane grants
 * the authority. **The language model appears nowhere in that chain.** It explains, in plain
 * English, what the deterministic half already decided — and this page never says otherwise.
 *
 * **`NO_DIAGNOSIS` is a result, and it is styled as one.** It takes the refusal accent, never
 * the stop colour, and when it happens the most useful thing on the page is the gate that
 * stopped it together with what would change the answer. That block sits directly under the
 * case's own state and above everything it withheld.
 *
 * **Elimination is final.** The differential is the shared `Differential` component precisely
 * so that this surface cannot invent a second opinion about it: a cause eliminated by evidence
 * stays struck through with the question and answer that killed it, and nothing here re-ranks
 * it back into contention.
 *
 * **Every figure comes from the API.** Nothing is hardcoded, nothing is a placeholder, and
 * every section fails into `<Degraded>` naming the endpoint rather than into an empty box that
 * would read as good news.
 */

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import { Differential } from '@/components/Differential';
import { FigureView } from '@/components/FigureView';
import { IconAlert, IconCheck, IconHalt } from '@/components/Icons';
import { ResidualChart } from '@/components/ResidualChart';
import { Degraded, EmptyState, PageHeader, Skeleton, StateChip } from '@/components/Surface';
import { Reveal } from '@/components/motion';
import { useApi } from '@/components/useApi';
import type { FigureFrame } from '@/lib/frames';
import {
  CAPABILITIES,
  STATE_MEANING,
  asAnswerState,
  decodeSegment,
  parseCaseId,
  stampOf,
  type CaseBody,
  type CaseCapability,
  type EvidencePack,
  type PackResidual,
  type SeriesBody,
  type VerificationBody,
  type WorkOrderDraft,
} from '../api';
import styles from '../case.module.css';

/**
 * The pack's residual, in the shape `FigureView` takes.
 *
 * A re-shaping, never a re-rendering: `text` is carried across untouched, because the back end
 * formatted every figure exactly once and a second formatting is how a number starts
 * disagreeing with itself.
 */
function toFigureFrame(residual: PackResidual): FigureFrame {
  return {
    name: residual.name,
    label: residual.figure.label,
    value: residual.figure.value,
    unit: residual.figure.unit,
    basis: residual.figure.basis,
    absence: residual.figure.absence,
    provenance: residual.figure.provenance,
    text: residual.figure.text,
    note: residual.figure.note,
    verdict: residual.verdict,
    model_nrmse: residual.model_nrmse,
    poor_fit: residual.poor_fit,
  };
}

/** `not_answered` → `not answered`. A word swap for reading; it changes no meaning. */
function words(value: string): string {
  return value.replace(/_/g, ' ');
}

export default function CasePage() {
  const params = useParams<{ id: string | string[] }>();
  const raw = Array.isArray(params?.id) ? (params.id[0] ?? '') : (params?.id ?? '');
  const caseId = decodeSegment(raw);
  const parsed = useMemo(() => parseCaseId(caseId), [caseId]);
  // The colon form, never the raw segment. A case reached from the reliability workspace
  // arrives pipe-joined — the same triple under the other of the back end's two encodings —
  // and the episode routes are keyed by the colon form alone.
  const encoded = encodeURIComponent(parsed?.canonical ?? caseId);

  const [viewAs, setViewAs] = useState<CaseCapability>('technician');

  const base = parsed ? `/api/v1/episodes/${encoded}` : null;
  const pack = useApi<EvidencePack>(base && `${base}/pack`);
  const kase = useApi<CaseBody>(base && `${base}/case?viewing_as=${viewAs}`);
  const series = useApi<SeriesBody>(base && `${base}/series`);
  const work = useApi<WorkOrderDraft>(base && `${base}/work-order`);
  // The post-work window is the API's own default, echoed back as `post_work_window_days` and
  // rendered from the response. Choosing a number here and printing it would be printing a
  // figure this surface invented.
  const verification = useApi<VerificationBody>(base && `${base}/verification`);

  const state = pack.data ? asAnswerState(pack.data.answer_state) : null;
  const failedGates = pack.data?.gates.filter((gate) => !gate.passed) ?? [];
  const refused = state === 'NO_DIAGNOSIS';

  const equipmentName = kase.data?.equipment_display ?? parsed?.equipmentKey.replace('_', ' ') ?? '';

  if (!parsed) {
    return (
      <>
        <PageHeader
          title="Case"
          lede="A case is named by the equipment, the fault class and the day — that triple is what makes a rescan reopen the same case instead of a second one. The back end joins it with a colon on an episode and a pipe on a seed key, and both reach this page."
        />
        <EmptyState
          title="That is not a case id"
          because={`“${caseId || 'nothing'}” is not the equipment, fault class and day joined by a colon or a pipe, so no case was looked for. Nothing has been asserted about any machine.`}
        >
          <div className="row" style={{ marginTop: 10 }}>
            <Link className={styles.backLink} href="/case">
              ← Back to the case queue
            </Link>
          </div>
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <p style={{ margin: '0 0 4px' }}>
        <Link className={styles.backLink} href="/case">
          ← All cases
        </Link>
      </p>

      <PageHeader
        title={`${equipmentName} · ${parsed.faultLabel}`}
        lede="One fault on one machine, from the moment it was detected to the evidence that a repair worked. What follows is in the order the case actually runs."
        meta={
          pack.data ? (
            <>
              {parsed.canonical} · day {parsed.day} · window {stampOf(pack.data.window.start)} to{' '}
              {stampOf(pack.data.window.end)} · source {pack.data.window.source}
              {pack.data.window.is_snapshot ? ' (snapshot)' : ''}
            </>
          ) : (
            <>{parsed.canonical} · day {parsed.day}</>
          )
        }
        actions={
          <a className={styles.primary} href="#checks">
            {kase.data && !kase.data.may_advance ? 'See what is blocking this' : 'Go to the checks'}
          </a>
        }
      />

      {/* ── where the case stands ─────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="stands">
        <h2 id="stands">Where this case stands</h2>

        {pack.error && (
          <Degraded
            what="The evidence pack"
            detail={pack.error}
            endpoint={pack.endpoint ?? undefined}
          >
            <p className="muted">
              Without it there is no gate outcome and no answer state, so neither is shown. An
              absent state is not <code className="mono">ANSWERED</code>.
            </p>
          </Degraded>
        )}

        {pack.loading && <Skeleton lines={4} label="Reading the evidence pack" />}

        {pack.data && (
          <>
            <div className={styles.standRow}>
              <span className={styles.standLabel}>Answer state</span>
              {state ? (
                <StateChip state={state} />
              ) : (
                <span className="pri" data-band={pack.data.answer_state}>
                  {pack.data.answer_state}
                </span>
              )}
              <span className={styles.standLabel}>Case</span>
              <span className="pri" data-band={kase.data?.state ?? 'unrated'}>
                {kase.data ? words(kase.data.state) : 'not read'}
              </span>
            </div>

            <p className={styles.standNote}>
              {state
                ? STATE_MEANING[state]
                : 'The back end returned a state that is not one of the six in the answer contract. It is printed above exactly as it arrived rather than rounded to the nearest of the six.'}
            </p>

            <dl className="kv">
              <dt>Severity</dt>
              <dd>{pack.data.severity.text}</dd>
              <dt>Fault class</dt>
              <dd>
                {parsed.faultLabel} —{' '}
                {pack.data.model_declares_undecidable
                  ? 'the trained model declares this class undecidable, so the case investigates rather than assuming a mechanism.'
                  : 'the class names a mechanism, so no differential is offered for it.'}
              </dd>
              {pack.data.other_labels_same_day.length > 0 && (
                <>
                  <dt>Same day</dt>
                  <dd>
                    {pack.data.other_labels_same_day.join(', ')} — one repair may explain several
                    of them.
                  </dd>
                </>
              )}
            </dl>

            {pack.data.has_poor_fit && (
              <p className={`${styles.flag} ${styles.flagWarn}`}>
                At least one residual behind this case comes from a poorly fitted model. The
                alarm may be an artefact of the fit rather than a fault — the badge on each
                figure below carries the words and the nRMSE, so it can be checked before
                anyone is dispatched.
              </p>
            )}

            {kase.data && (
              <p className={styles.flag}>
                <strong>
                  {kase.data.may_advance ? 'This case can advance.' : 'This case cannot advance.'}
                </strong>{' '}
                {kase.data.advance_reason}
              </p>
            )}
          </>
        )}
      </section>

      {/* ── the refusal, above everything it withheld ─────────────────────────── */}

      {refused && (
        <section className="card refusal measure" aria-labelledby="nodiag">
          <h2 id="nodiag">
            <IconHalt className="ico" style={{ verticalAlign: '-2px', marginRight: 6 }} />
            No diagnosis — a result, not a failure
          </h2>
          <p className="answer">
            No fault is named for this case. A deterministic gate stopped it before anything
            could be judged, so nothing below may be read as a statement about the equipment.
            The gate that stopped it is named here, with what would change the answer.
          </p>
          {failedGates.map((gate) => (
            <div className="gate" key={gate.gate}>
              <strong>{gate.gate}</strong>
              <div>{gate.reason}</div>
              <div className="what">What would change this: {gate.remedy}</div>
              {gate.unresolved_question && (
                <div className="what">
                  The threshold for this gate is unagreed — {gate.unresolved_question}. It
                  refuses rather than guessing.
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      {/* ── the gates ─────────────────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="gates">
        <h2 id="gates">Gates — nothing is diagnosed until all of them pass</h2>

        {pack.loading && <Skeleton lines={3} label="Reading the gate outcomes" />}

        {/* The pack's own `<Degraded>` is stated once, above. Repeating it per section would
            report one outage four times and bury which endpoint actually failed. */}
        {pack.error && (
          <p className="muted">
            No gate is listed: the evidence pack could not be read, and the outage is stated at
            the top of this case. An unlisted gate has not passed — it was never evaluated.
          </p>
        )}

        {pack.data &&
          (pack.data.gates.length === 0 ? (
            <EmptyState
              title="No gate was evaluated"
              because="The pack carries no gate results, so nothing was checked. That is not the same as everything passing."
            />
          ) : (
            <>
              <Reveal
                as="ul"
                className={styles.gateList}
                runKey={`${caseId}:${pack.data.gates.length}`}
              >
                {pack.data.gates.map((gate) => (
                  <li className="audit" key={gate.gate} data-passed={gate.passed}>
                    {gate.passed ? <IconCheck className="ico" /> : <IconAlert className="ico" />}
                    <span>
                      <span className={styles.gateName}>{gate.gate}</span> —{' '}
                      {gate.passed ? 'passed' : 'did not pass'}
                      {gate.reason && <span className={styles.gateBody}>{gate.reason}</span>}
                      {gate.remedy && (
                        <span className={styles.gateBody}>
                          What would change this: {gate.remedy}
                        </span>
                      )}
                      {gate.unresolved_question && (
                        <span className={styles.gateBody}>
                          Unagreed threshold — {gate.unresolved_question}.
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </Reveal>
              <p className="muted">
                A gate is plain deterministic software and it runs before anything is named. It
                is what makes a refusal useful rather than a shrug: the check that stopped the
                case is on the record, and so is what would unblock it.
              </p>
            </>
          ))}
      </section>

      {/* ── the evidence ──────────────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="evidence">
        <h2 id="evidence">Evidence — every residual against this asset’s own band</h2>

        {pack.error && (
          <p className="muted">
            No residual is shown: the evidence pack could not be read, and the outage is stated
            at the top of this case. Nothing has been substituted or estimated in its place.
          </p>
        )}

        {pack.loading && <Skeleton lines={6} label="Reading the residuals" />}

        {pack.data &&
          (pack.data.residuals.length === 0 ? (
            <EmptyState
              title="No residual was scored for this episode"
              because="No fitted model produced a value here. A missing residual is a signal nobody judged, never a signal that came back normal."
            />
          ) : (
            <>
              {/* Deliberately not wrapped in `Reveal`: `.figure` already carries its own
                  staggered entrance in `globals.css`, and two entrances on one element is
                  motion competing with itself next to a reading somebody dispatches on. */}
              <div className={styles.figures}>
                {pack.data.residuals.map((residual, index) => (
                  <FigureView key={residual.name} figure={toFigureFrame(residual)} index={index} />
                ))}
              </div>

              <p className="muted">
                A residual is not zero-centred. “High” and “normal” mean high or normal{' '}
                <em>for this asset, against its own healthy distribution</em> — never above a
                shared threshold, and never against zero. Two identical machines have different
                bands, which is why models are fitted per asset and never per fleet.
              </p>

              <details className={styles.disclosure}>
                <summary>
                  Provenance — {pack.data.signal_provenance.length} signal note(s) and{' '}
                  {pack.data.sources.length} source(s)
                </summary>
                <div className={styles.disclosureBody}>
                  <Reveal
                    as="ul"
                    className="reasons"
                    runKey={`${caseId}:${pack.data.signal_provenance.length}`}
                  >
                    {pack.data.signal_provenance.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </Reveal>
                  <p className={`mono ${styles.wrapAnywhere}`}>
                    {pack.data.sources.join(' · ')}
                  </p>
                </div>
              </details>
            </>
          ))}
      </section>

      {/* ── the residual, over the day ─────────────────────────────────────────── */}

      <section className="card" aria-labelledby="series">
        <h2 id="series">The residual over this day</h2>

        {series.error && (
          <Degraded
            what="The residual series"
            detail={series.error}
            endpoint={series.endpoint ?? undefined}
          />
        )}

        {series.loading && <Skeleton lines={5} label="Reading the residual series" />}

        {series.data &&
          (series.data.points.length === 0 ? (
            <EmptyState
              title="No reading was returned for this day"
              because="The snapshot holds no scored slot for this asset on this day, so there is nothing to draw. An empty plot is not a flat one."
            />
          ) : (
            <ResidualChart
              points={series.data.points}
              band={series.data.band}
              bandAbsentReason={series.data.band_absent_reason}
              residual={series.data.residual}
              equipment={equipmentName || series.data.equipment_key.replace('_', ' ')}
              nullCount={series.data.null_count}
            />
          ))}
      </section>

      {/* ── the differential ──────────────────────────────────────────────────────
          Mounted between the evidence and the work, because it is what stands between a
          named-but-ambiguous class and a job raised against whichever cause happened to be
          listed first. Rendered by the shared component so this surface cannot form a second
          opinion about an elimination: eliminated causes stay struck through with the check
          and the answer that killed them, and none is ever re-ranked back in. */}
      <Differential faultLabel={parsed.faultLabel} />

      {/* ── the checks ────────────────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="checks-h" id="checks">
        <h2 id="checks-h">The checks — whose they are, and what settles one</h2>

        {kase.error && (
          <Degraded
            what="The case checklist"
            detail={kase.error}
            endpoint={kase.endpoint ?? undefined}
          />
        )}

        {kase.loading && <Skeleton lines={4} label="Reading the checklist" />}

        {kase.data && (
          <>
            {kase.data.content_is_sample && (
              /* Said before the list and never after it: a caveat under a checklist is read
                 second, and by then the reader has taken the items as the library. */
              <p className={styles.flag}>
                <strong>Sample content.</strong> {kase.data.content_note}
              </p>
            )}

            <div className={styles.capRow} role="group" aria-label="Show the checks for">
              {CAPABILITIES.map((capability) => (
                <button
                  key={capability}
                  className="chip"
                  aria-pressed={viewAs === capability}
                  onClick={() => setViewAs(capability)}
                >
                  as {capability}
                </button>
              ))}
            </div>

            {kase.data.my_items.length === 0 ? (
              <EmptyState
                title={`No check on this case belongs to the ${kase.data.viewing_as} capability`}
                because="A check this reader cannot perform collapses out of their list rather than greying out at them — a greyed-out demand still reads as a demand on whoever is standing there. Every check is still on the case, below."
              />
            ) : (
              <Reveal
                as="ul"
                className="checks"
                runKey={`${viewAs}:${kase.data.my_items.length}`}
                aria-label={`Checks for the ${kase.data.viewing_as}`}
              >
                {kase.data.my_items.map((item) => (
                  <li
                    key={item.id}
                    className={`row-check ${item.finding}`}
                    data-blocking={item.blocking}
                  >
                    <span className="mark" aria-hidden="true">
                      {item.finding === 'measured' ? '✓' : item.finding === 'cannot_check' ? '–' : '○'}
                    </span>
                    <span>
                      {item.text}
                      {item.blocking && <span className="badge warn">blocking</span>}
                      <span className={styles.itemOwner}>
                        {item.capability} · {words(item.finding)}
                      </span>
                      {item.stored_reading && <span className="stored">{item.stored_reading}</span>}
                    </span>
                  </li>
                ))}
              </Reveal>
            )}

            <p className="muted">
              Only a measured reading settles a blocking check. An estimate, a cannot-check and
              a not-applicable all leave it open, and they are three different statements: one
              is a judgement, one is about this person, one is about the machine.
            </p>

            {!kase.data.operator_can_start && (
              <p className={`${styles.flag} ${styles.flagWarn}`}>
                Nothing on this case can be started by an operator. Every fault class is
                supposed to leave one check somebody at the machine can do, so nobody starts
                stuck — this one does not.
              </p>
            )}

            {kase.data.for_others.length > 0 && (
              <details className={styles.disclosure}>
                <summary>
                  {kase.data.for_others.length} check(s) belong to another capability
                </summary>
                <div className={styles.disclosureBody}>
                  <Reveal
                    as="ul"
                    className={styles.othersList}
                    runKey={`${viewAs}:${kase.data.for_others.length}`}
                  >
                    {kase.data.for_others.map((item) => (
                      <li className={styles.othersItem} key={item.id}>
                        <span>{item.text}</span>
                        <span className="mono">{item.capability}</span>
                      </li>
                    ))}
                  </Reveal>
                  <p className="muted">
                    They stay on the case and out of the task list above. A capability is not a
                    rank: a supervisor is not a more capable technician, it is authority and
                    records rather than gauges.
                  </p>
                </div>
              </details>
            )}
          </>
        )}
      </section>

      {/* ── the work raised ───────────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="work">
        <h2 id="work">The work this case would raise</h2>

        {work.error && (
          <Degraded
            what="The work order draft"
            detail={work.error}
            endpoint={work.endpoint ?? undefined}
          />
        )}

        {work.loading && <Skeleton lines={5} label="Drafting the work order" />}

        {work.data && (
          <>
            <p className="answer measure" style={{ marginTop: 0 }}>
              {work.data.title}
              <span className="pri" data-band={work.data.priority.band}>
                {work.data.priority.band}
              </span>
            </p>

            <p className="muted">
              <strong>How this priority was reached:</strong> {work.data.priority.explanation}
            </p>

            {work.data.priority.used.length > 0 && (
              <p className="muted">
                Inputs the formula could use: {work.data.priority.used.join(', ')}. Priority is
                derived from severity, and severity comes from the fault class plus how long the
                pattern persisted — never from how far a residual sits outside its band, because
                non-faults were measured to deviate more than faults.
              </p>
            )}

            {!work.data.priority.is_complete && work.data.priority.missing.length > 0 && (
              <Reveal
                as="ul"
                className="reasons"
                runKey={`${caseId}:${work.data.priority.missing.length}`}
              >
                {work.data.priority.missing.map((missing) => (
                  <li key={missing.input}>
                    <code className="mono">{missing.input}</code> — {missing.why}
                  </li>
                ))}
              </Reveal>
            )}

            {work.data.warnings.map((warning) => (
              <p className={styles.flag} key={warning}>
                {warning}
              </p>
            ))}

            <p className="muted" style={{ marginTop: 14 }}>
              <strong>Cannot close until:</strong>
            </p>
            <Reveal
              as="ul"
              className="reasons"
              runKey={`${caseId}:${work.data.cannot_close_until.length}`}
            >
              {work.data.cannot_close_until.map((condition) => (
                <li key={condition}>{condition}</li>
              ))}
            </Reveal>

            <details className={styles.disclosure}>
              <summary>
                {work.data.evidence.length} piece(s) of evidence travel with this job
              </summary>
              <div className={styles.disclosureBody}>
                <Reveal
                  as="ul"
                  className={styles.evidenceList}
                  runKey={`${caseId}:${work.data.evidence.length}`}
                >
                  {work.data.evidence.map((piece) => (
                    <li className={styles.evidenceItem} key={`${piece.kind}:${piece.text}`}>
                      <span className={styles.evidenceKind}>{piece.kind}</span>
                      {piece.text}
                      <span className={styles.evidenceSource}>{piece.source}</span>
                    </li>
                  ))}
                </Reveal>
                <p className="muted">
                  Nothing is fetched again by whoever opens the job — the justification travels
                  with the work rather than being looked up afterwards.
                </p>
              </div>
            </details>

            {work.data.is_draft && (
              <p className="muted">
                This is a <strong>draft</strong> and nothing is persisted. Graylinx Synex keeps
                its own state in PostgreSQL and that is not wired yet, so no one can be
                dispatched against it and it does not pretend otherwise.
              </p>
            )}
          </>
        )}
      </section>

      {/* ── did it work? ──────────────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="verify">
        <h2 id="verify">Verification — did it work?</h2>

        {verification.error && (
          <Degraded
            what="Verification"
            detail={verification.error}
            endpoint={verification.endpoint ?? undefined}
          />
        )}

        {verification.loading && <Skeleton lines={4} label="Reading the post-work window" />}

        {verification.data && (
          <>
            <p className="answer measure" style={{ marginTop: 0 }}>
              {verification.data.reason}
              <span className="pri" data-band={verification.data.outcome}>
                {verification.data.outcome}
              </span>
            </p>

            <dl className="kv">
              <dt>Residual</dt>
              <dd className="mono">{verification.data.residual_name}</dd>
              <dt>Before</dt>
              <dd>
                {verification.data.before.in_band} of {verification.data.before.total} readings
                inside this asset’s own band
              </dd>
              <dt>After</dt>
              <dd>
                {verification.data.after.in_band} of {verification.data.after.total}, over the{' '}
                {verification.data.post_work_window_days} day(s) following
              </dd>
            </dl>

            {!verification.data.post_work_was_diagnosable && (
              <p className={styles.flag}>
                The gates did not pass over the post-work window, so nothing was being judged
                there. A NULL means not diagnosed — never healthy.
              </p>
            )}

            {verification.data.notes.map((note) => (
              <p className="muted" key={note}>
                {note}
              </p>
            ))}

            <p className="muted">
              {verification.data.closes_the_work_order
                ? 'This closes the work order.'
                : verification.data.outcome === 'FAIL'
                  ? 'This does not close the work order — what was measured has not been fixed.'
                  : 'This does not close the work order. UNKNOWN is a permitted outcome, and an open job is the correct state when the data cannot decide.'}
              {verification.data.blocked_by &&
                ` A PASS is unreachable until ${verification.data.blocked_by} is answered.`}
            </p>

            <p className="muted">
              The outcome comes from post-work residuals against this asset’s own band and a
              deterministic rule — never from the closure note, and never from whoever did the
              work saying it is done.
            </p>
          </>
        )}
      </section>

      <section className="card supporting measure">
        <h2>What this surface does not do</h2>
        <p className="muted">
          Nothing here writes. No check can be answered, no work order raised and no case
          advanced, deferred or closed on this build — Synex’s own case store is not wired yet,
          and a control that looked like it acted would be the most misleading thing on the
          page. What is shown is what the deterministic half of the platform produces today,
          read live from the API with the GPU terminated.
        </p>
      </section>
    </>
  );
}
