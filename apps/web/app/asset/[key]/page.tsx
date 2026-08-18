'use client';

/**
 * `A1` — the asset story. One machine over the measured window.
 *
 * **Signal provenance leads the page, and that is the whole argument.** A residual chart, a
 * model roster and a fault history all read as an account of a machine. On this plant that
 * account would be a lie of omission unless the reader is told, before anything else, which
 * signals are actually instrumented. `NEVER_MEASURED` is the one that matters most: it is
 * **not zero**, it means no working instrument exists for that signal here, and a reader who
 * takes it for a zero reads every chart below it wrong.
 *
 * So the order is: what can be measured, then what was recorded, then the residual behind it,
 * then whether the repair held, then the models, and last the things this page will not say.
 * Last is where a reader stops, which is why the back end puts `cannot_say` there too.
 *
 * **Nothing on this page was chosen, ranked or approved by the language model.** The FDD
 * rules name the fault, a deterministic rule decides the verification outcome, and the
 * Control Plane decides what this persona may see. This surface renders those decisions and
 * makes none of its own.
 *
 * **Every figure comes from the API.** No count, band, nRMSE or date is computed here, and
 * the two counts that are derived — how many episodes belong to this asset, how many models
 * carry a fit — are counts of rows the API returned, stated as such.
 */

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import { Degraded, EmptyState, PageHeader, Skeleton, StateChip } from '@/components/Surface';
import { Reveal } from '@/components/motion';
import { ResidualChart, type SeriesBand, type SeriesPoint } from '@/components/ResidualChart';
import { useApi } from '@/components/useApi';
import styles from './asset.module.css';

/* ── the wire, mirrored ─────────────────────────────────────────────────────── */

interface DataWindow {
  start: string;
  end: string;
  is_snapshot: boolean;
  source: string;
}

interface ModelLine {
  model_name: string;
  nrmse: number | null;
  absence: string;
  takes_cond_flow: boolean;
  is_poor_fit: boolean;
  text: string;
}

interface DiagnosisLine {
  fault_label: string;
  episode_count: number;
  slot_count: number;
  severity_text: string;
  declares_undecidable: boolean;
  is_fault: boolean;
  text: string;
}

interface OpenItem {
  reference: string;
  kind: string;
  fault_label: string;
  state: string;
  opened_on: string;
  text: string;
}

interface CannotSay {
  subject: string;
  silence: string;
  because: string;
  consequence: string;
  text: string;
}

interface AssetStory {
  equipment_key: string;
  display_name: string;
  kind: string;
  scoreable: boolean;
  window: DataWindow;
  as_of: string | null;
  models: ModelLine[];
  diagnoses: DiagnosisLine[];
  open_items: OpenItem[];
  cannot_say: CannotSay[];
  rendered: string;
}

interface EpisodeRow {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  slot_count: number;
  first_slot: string;
  last_slot: string;
}

interface EpisodeIndex {
  window: { end: string; includes_simulated: boolean; note: string };
  episode_count: number;
  equipment_days: number;
  episodes: EpisodeRow[];
}

interface SeriesResponse {
  episode_id: string;
  equipment_key: string;
  fault_label: string;
  residual: string;
  day: string;
  points: SeriesPoint[];
  null_count: number;
  band: SeriesBand | null;
  band_absent_reason: string | null;
}

interface Verification {
  episode_id: string;
  post_work_window_days: number;
  post_work_was_diagnosable: boolean;
  outcome: 'PASS' | 'FAIL' | 'UNKNOWN';
  reason: string;
  residual_name: string;
  before: { in_band: number; total: number };
  after: { in_band: number; total: number };
  closes_the_work_order: boolean;
  blocked_by: string | null;
  notes: string[];
}

interface EquipmentIndex {
  equipment: {
    key: string;
    display_name: string;
    kind: string;
    scoreable: boolean;
    why_not: string | null;
  }[];
  scoreable_count: number;
  total_count: number;
}

/* ── provenance vocabulary ──────────────────────────────────────────────────── */

type SignalStatus = 'MEASURED' | 'NEVER_MEASURED' | 'CONSTANT' | 'SUSPECT' | 'DERIVED';

/**
 * `STATUS_SILENCE` and `SUSPECT_SILENCE` in `app/services/asset_story.py`, read backwards.
 *
 * The back end names a *silence* — why something cannot be said — and each of these five is
 * a signal's provenance wearing that name. Mapping back is faithful rather than invented:
 * every entry here is one line of the map the service already holds, and a silence that is
 * not about a signal is deliberately absent so it falls through to the last section instead
 * of being drawn as a provenance tile.
 */
const SILENCE_TO_STATUS: Record<string, SignalStatus> = {
  never_measured: 'NEVER_MEASURED',
  constant_signal: 'CONSTANT',
  signal_contradicted: 'SUSPECT',
  instrument_stopped: 'SUSPECT',
  value_was_computed: 'DERIVED',
};

/**
 * What each word means, from `app/domain/signals.py`. Words only — there is not a figure in
 * this table, because every figure on this page comes off the wire.
 */
const STATUS_MEANING: ReadonlyArray<readonly [SignalStatus, string]> = [
  ['MEASURED', 'A real instrument reports it, and the readings are usable.'],
  [
    'NEVER_MEASURED',
    'The column exists and no credible value has ever been recorded in it. Not missing, and not zero — the tag is wired and the meter is not.',
  ],
  ['CONSTANT', 'The column never changes value. Present, and carrying no information.'],
  ['SUSPECT', 'Readings exist and are contradicted by other signals on the same circuit.'],
  ['DERIVED', 'No instrument reports it; the value was computed from one that does.'],
];

/** `instrument_stopped` is `SUSPECT` with a sharper cause, and the two send a reader to
 *  different places — a dead transmitter is a work order, a contradiction is a mislabelled
 *  column. The tile keeps the distinction rather than collapsing it. */
const SILENCE_QUALIFIER: Record<string, string> = {
  instrument_stopped: 'the instrument stopped',
  signal_contradicted: 'contradicted by its own circuit',
};

/* ── the surface ────────────────────────────────────────────────────────────── */

export default function AssetPage() {
  const params = useParams();
  const raw = params?.key;
  const equipmentKey = Array.isArray(raw) ? (raw[0] ?? '') : (raw ?? '');
  const encoded = encodeURIComponent(equipmentKey);

  const story = useApi<AssetStory>(equipmentKey ? `/api/v1/asset/${encoded}` : null);
  const index = useApi<EpisodeIndex>('/api/v1/episodes');
  const fleet = useApi<EquipmentIndex>('/api/v1/equipment');

  const [picked, setPicked] = useState<string | null>(null);

  /** The episodes the index returned for this asset, in the order it returned them. */
  const mine = useMemo(
    () => (index.data?.episodes ?? []).filter((e) => e.equipment_key === equipmentKey),
    [index.data, equipmentKey],
  );

  // The most recent episode in the window, unless the reader picked another. A picked id
  // that belongs to a different asset simply will not match, so navigating between assets
  // needs no reset.
  const selected = useMemo(
    () => mine.find((e) => e.id === picked) ?? mine[mine.length - 1] ?? null,
    [mine, picked],
  );

  const series = useApi<SeriesResponse>(
    selected ? `/api/v1/episodes/${encodeURIComponent(selected.id)}/series` : null,
  );
  // `after_days` is left off deliberately: the window is the service's to choose, and the
  // response states which one it used. Naming a number here would be inventing one.
  const verification = useApi<Verification>(
    selected ? `/api/v1/episodes/${encodeURIComponent(selected.id)}/verification` : null,
  );

  const said = story.data;

  /* The last section, split. Signal provenance is drawn at the top of the page with its own
     treatment, so drawing it again below would read as two findings rather than one. The
     split is named where the remainder is rendered — it is a partition, not an omission. */
  const provenance = useMemo(
    () =>
      (said?.cannot_say ?? [])
        .filter((c) => c.silence in SILENCE_TO_STATUS)
        .map((c) => ({ ...c, status: SILENCE_TO_STATUS[c.silence] as SignalStatus })),
    [said],
  );
  const neverMeasured = provenance.filter((c) => c.status === 'NEVER_MEASURED');
  const otherSignals = provenance.filter((c) => c.status !== 'NEVER_MEASURED');
  const remainingSilences = (said?.cannot_say ?? []).filter(
    (c) => !(c.silence in SILENCE_TO_STATUS),
  );

  const fitted = (said?.models ?? []).filter((m) => m.nrmse !== null);
  const scoreableAssets = (fleet.data?.equipment ?? []).filter((e) => e.scoreable);
  const otherAssets = (fleet.data?.equipment ?? []).filter((e) => e.key !== equipmentKey);

  return (
    <>
      <PageHeader
        title={said ? said.display_name : equipmentKey}
        lede="One machine over the measured window: which of its signals are actually instrumented, what was recorded against it, the residual behind that record, and what Graylinx Synex will not claim about it."
        meta={
          said ? (
            <>
              {said.kind} · {said.window.start.replace('T', ' ')} to{' '}
              {said.window.end.replace('T', ' ')} · {said.window.source}
              {said.window.is_snapshot ? ' · snapshot' : ''} ·{' '}
              {said.as_of
                ? `as of ${said.as_of}`
                : 'built without a reference date, so no age is stated'}
            </>
          ) : (
            <>{story.endpoint ?? 'no equipment key in the route'}</>
          )
        }
        actions={
          scoreableAssets.length > 0 ? (
            <div className={styles.switch}>
              {scoreableAssets.map((e) => (
                <Link
                  key={e.key}
                  href={`/asset/${encodeURIComponent(e.key)}`}
                  className={
                    e.key === equipmentKey ? `chip ${styles.chipCurrent}` : 'chip'
                  }
                  aria-current={e.key === equipmentKey ? 'page' : undefined}
                >
                  {e.display_name}
                </Link>
              ))}
            </div>
          ) : undefined
        }
      />

      {/* The API is down, or this key is not one the site carries. Either way the reader is
          told which, told where it was asked, and offered the request again — never a
          spinner and never a substituted figure. */}
      {story.error && (
        <Degraded
          what="The asset story"
          detail={story.error}
          endpoint={story.endpoint ?? undefined}
        >
          <p className="muted">
            {story.error.startsWith('404')
              ? 'Either this equipment key is not one the site carries, or the running service predates the asset surface. Check the key against the list at the foot of this page, then confirm the API build serves this route.'
              : 'Start the API, or point NEXT_PUBLIC_API_BASE at the host that is serving it. Everything below comes from other routes and is shown only if it actually loaded.'}
          </p>
          <button type="button" className={`btn ${styles.retry}`} onClick={story.reload}>
            Ask again
          </button>
        </Degraded>
      )}

      {/* ── 1. signal provenance ───────────────────────────────────────────── */}

      <section className="card" aria-labelledby="prov">
        <h2 id="prov">Signal provenance — what this plant can actually measure</h2>
        <p className={styles.note}>
          Read this before any chart on the page. A residual is only as good as the signals
          behind it, and on this asset the service states each one it cannot vouch for, in
          its own words.
        </p>

        {story.loading && <Skeleton lines={4} label="Loading signal provenance" />}

        {said && neverMeasured.length === 0 && otherSignals.length === 0 && (
          <EmptyState
            title="No unusable signal was reported for this asset"
            because="The registry names the signals somebody has measured something about, and it reported none against this asset. That is silence, not a clean bill of health — an unlisted signal has had no claim made about it either way."
          />
        )}

        {/* The lead. Full width, above the grid, because on this plant the never-measured
            signal feeds most of the models fitted on the machine. */}
        {neverMeasured.map((c) => (
          <div key={c.subject} className={`card ${styles.provLead}`}>
            <div className={styles.provHead}>
              <span className={`${styles.status} ${styles.statusLead}`}>NEVER MEASURED</span>
              <span className={styles.signalKey}>{c.subject}</span>
            </div>
            <p className={styles.notZero}>
              <strong>This is not zero.</strong> The column exists and no credible value has
              ever been recorded in it — this plant has no working instrument for{' '}
              <span className="mono">{c.subject}</span>. Any figure standing on it is a
              stated absence, never a reading of nought.
            </p>
            <p className={styles.because}>{c.because}</p>
            <p className={styles.consequence}>{c.consequence}</p>
            {/* Drawn only because the service said so in its own consequence line. A
                refusal is a correct outcome here, so it takes the refusal treatment and is
                never coloured as an error. */}
            {c.consequence.includes('NO_DIAGNOSIS') && (
              <p className="state-line">
                <StateChip state="NO_DIAGNOSIS" /> is the correct answer on that branch, by
                design — not a failure of the platform.
              </p>
            )}
          </div>
        ))}

        {otherSignals.length > 0 && (
          <Reveal as="div" className="grid-cards" runKey={`${equipmentKey}:${otherSignals.length}`}>
            {otherSignals.map((c) => (
              <div key={c.subject} className={`card ${styles.provCard}`} data-status={c.status}>
                <div className={styles.provHead}>
                  <span className={styles.status}>{c.status.replace('_', ' ')}</span>
                  <span className={styles.signalKey}>{c.subject}</span>
                </div>
                {SILENCE_QUALIFIER[c.silence] && (
                  <p className={styles.kind}>{SILENCE_QUALIFIER[c.silence]}</p>
                )}
                <p className={styles.because}>{c.because}</p>
                <p className={styles.consequence}>{c.consequence}</p>
              </div>
            ))}
          </Reveal>
        )}
      </section>

      <section className="card supporting" aria-labelledby="vocab">
        <h2 id="vocab">The five words, and what each one claims</h2>
        <dl className={styles.legend}>
          {STATUS_MEANING.map(([word, meaning]) => (
            <div key={word} className={styles.legendPair}>
              <dt>
                <span className={styles.status} data-status={word}>
                  {word.replace('_', ' ')}
                </span>
              </dt>
              <dd>{meaning}</dd>
            </div>
          ))}
        </dl>
        <p className={styles.note} style={{ marginTop: '12px', marginBottom: 0 }}>
          A signal absent from this page has had no claim made about it. The registry names
          the signals somebody has measured something about, so silence here is not the same
          statement as <span className="mono">MEASURED</span>.
        </p>
      </section>

      {/* ── 2. episodes over time ──────────────────────────────────────────── */}

      <section className="card" aria-labelledby="eps">
        <h2 id="eps">Episodes recorded against this asset</h2>
        <p className={styles.note}>
          Read from the episode index, one per equipment, label and day. The asset story
          itself was built without the fault history and says so in its own last section
          rather than implying the machine was clean.
        </p>

        {index.loading && <Skeleton lines={5} label="Loading episodes" />}

        {index.error && (
          <Degraded
            what="The episode index"
            detail={index.error}
            endpoint={index.endpoint ?? undefined}
          >
            <button type="button" className={`btn ${styles.retry}`} onClick={index.reload}>
              Ask again
            </button>
          </Degraded>
        )}

        {index.data && mine.length === 0 && (
          <EmptyState
            title={`No episode was returned for ${equipmentKey} in this window`}
            because={`The index returned ${index.data.episode_count} episodes across ${index.data.equipment_days} equipment-days and none of them belongs to this asset. That is an absence of diagnosed faults over the window, never a healthy machine — nothing here says this asset was checked and found clean. ${index.data.window.note}.`}
          />
        )}

        {index.data && mine.length > 0 && (
          <>
            <p className={styles.note}>
              {mine.length} of the {index.data.episode_count} episodes in the window belong to
              this asset. {index.data.window.note}. The most recent is open below; pick
              another to read its residual.
            </p>
            <div className="table-scroll">
              <table className="data stackable">
                <caption>
                  Every faulted episode on this asset, oldest first. One row is one
                  equipment, label and day.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Day</th>
                    <th scope="col">Fault label</th>
                    <th scope="col" className="num">
                      Slots
                    </th>
                    <th scope="col">First slot</th>
                    <th scope="col">Last slot</th>
                  </tr>
                </thead>
                <Reveal as="tbody" runKey={`${equipmentKey}:${mine.length}`}>
                  {mine.map((e) => (
                    <tr
                      key={e.id}
                      className={styles.epRow}
                      data-selected={selected?.id === e.id}
                    >
                      <td data-label="Day">
                        <button
                          type="button"
                          className={styles.pick}
                          aria-pressed={selected?.id === e.id}
                          onClick={() => setPicked(e.id)}
                        >
                          {e.day}
                        </button>
                      </td>
                      <td data-label="Fault label" className="mono">
                        {e.fault_label}
                      </td>
                      <td data-label="Slots" className="num">
                        {e.slot_count}
                      </td>
                      <td data-label="First slot" className="mono">
                        {e.first_slot.replace('T', ' ')}
                      </td>
                      <td data-label="Last slot" className="mono">
                        {e.last_slot.replace('T', ' ')}
                      </td>
                    </tr>
                  ))}
                </Reveal>
              </table>
            </div>
          </>
        )}
      </section>

      {/* ── 3. the residual behind the selected episode ────────────────────── */}

      {selected && (
        <section className="card" aria-labelledby="resid">
          <h2 id="resid">
            The residual behind {selected.fault_label} on {selected.day}
          </h2>

          {series.loading && <Skeleton lines={6} label="Loading the residual series" />}

          {series.error && (
            <Degraded
              what="The residual series"
              detail={series.error}
              endpoint={series.endpoint ?? undefined}
            >
              <button type="button" className={`btn ${styles.retry}`} onClick={series.reload}>
                Ask again
              </button>
            </Degraded>
          )}

          {series.data && (
            <>
              <ResidualChart
                points={series.data.points}
                band={series.data.band}
                bandAbsentReason={series.data.band_absent_reason}
                residual={series.data.residual}
                equipment={series.data.equipment_key}
                nullCount={series.data.null_count}
              />
              <p className={styles.note} style={{ marginTop: '12px', marginBottom: 0 }}>
                Plotted against this machine&apos;s own healthy band and never against zero.
                Models are fitted per asset, so the same band on the other chiller would mean
                something different — the comparison the chart makes is with this asset&apos;s
                own history.
              </p>
            </>
          )}
        </section>
      )}

      {/* ── 4. did it hold? ────────────────────────────────────────────────── */}

      {selected && (
        <section className="card" aria-labelledby="ver">
          <h2 id="ver">Verification — did what was measured clear?</h2>

          {verification.loading && <Skeleton lines={3} label="Loading the verification outcome" />}

          {verification.error && (
            <Degraded
              what="The verification outcome"
              detail={verification.error}
              endpoint={verification.endpoint ?? undefined}
            >
              <button
                type="button"
                className={`btn ${styles.retry}`}
                onClick={verification.reload}
              >
                Ask again
              </button>
            </Degraded>
          )}

          {verification.data && (
            <>
              <p className={styles.verdict}>
                <span className="pri" data-band={verification.data.outcome}>
                  {verification.data.outcome}
                </span>
                <span>{verification.data.reason}</span>
              </p>
              <dl className="kv">
                <dt>residual read</dt>
                <dd className="mono">{verification.data.residual_name}</dd>
                <dt>post-work window</dt>
                <dd>{verification.data.post_work_window_days} days after the episode</dd>
                <dt>in band before</dt>
                <dd className="mono">
                  {verification.data.before.in_band} of {verification.data.before.total}
                </dd>
                <dt>in band after</dt>
                <dd className="mono">
                  {verification.data.after.in_band} of {verification.data.after.total}
                </dd>
                <dt>post-work window diagnosable</dt>
                <dd>
                  {verification.data.post_work_was_diagnosable
                    ? 'yes — the engine reached a judgement in that window'
                    : 'no — the engine reached no judgement in that window, which is not the same as finding nothing wrong'}
                </dd>
                <dt>closes the work order</dt>
                <dd>
                  {verification.data.closes_the_work_order
                    ? 'yes'
                    : 'no — this outcome does not clear the close gate'}
                </dd>
                <dt>blocked by</dt>
                <dd>
                  {verification.data.blocked_by ?? (
                    <span className="absent">nothing was recorded as blocking it</span>
                  )}
                </dd>
              </dl>
              {verification.data.notes.length > 0 && (
                <Reveal
                  as="ul"
                  className="checks"
                  runKey={`${selected.id}:${verification.data.notes.length}`}
                >
                  {verification.data.notes.map((n, i) => (
                    <li key={`${selected.id}:${i}`} className="row-check">
                      {n}
                    </li>
                  ))}
                </Reveal>
              )}
              <p className={styles.note} style={{ marginBottom: 0 }}>
                The outcome comes from post-work residuals against this asset&apos;s own band
                and a deterministic rule. No closure note and no language model decides it.
              </p>
            </>
          )}
        </section>
      )}

      {/* ── 5. the model roster ────────────────────────────────────────────── */}

      <section className="card" aria-labelledby="models">
        <h2 id="models">The models fitted on this asset</h2>

        {story.loading && <Skeleton lines={5} label="Loading the model roster" />}

        {said && said.models.length === 0 && (
          <EmptyState
            title="No model is fitted on this asset"
            because="No model parameters, no reference band and no scored residual exist for it, so nothing about its behaviour may be judged here. That is the correct answer for this asset rather than a gap in the page."
          />
        )}

        {said && said.models.length > 0 && (
          <>
            <p className={styles.note}>
              {fitted.length} of the {said.models.length} the design names carry a fit. The one
              that does not is listed with its reason rather than left off — a roster that
              silently shows only what exists reads as complete.
            </p>
            <div className="table-scroll">
              <table className="data stackable">
                <thead>
                  <tr>
                    <th scope="col">Model</th>
                    <th scope="col" className="num">
                      nRMSE
                    </th>
                    <th scope="col">What travels with it</th>
                  </tr>
                </thead>
                <Reveal as="tbody" runKey={`${equipmentKey}:${said.models.length}`}>
                  {said.models.map((m) => (
                    <tr key={m.model_name}>
                      <td data-label="Model" className="mono">
                        {m.model_name}
                      </td>
                      {m.nrmse === null ? (
                        <td data-label="nRMSE">
                          <span className="absent">{m.absence}</span>
                        </td>
                      ) : (
                        <td data-label="nRMSE" className="num">
                          {m.nrmse}
                        </td>
                      )}
                      <td data-label="What travels with it">
                        {m.is_poor_fit && (
                          <span className="badge warn">
                            poor fit — the residual is partly the model&apos;s own error
                          </span>
                        )}
                        {m.takes_cond_flow && (
                          <span className="badge warn">
                            takes condenser flow, never measured here
                          </span>
                        )}
                        {!m.is_poor_fit && !m.takes_cond_flow && m.nrmse !== null && (
                          <span className="absent">nothing is flagged against it</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </Reveal>
              </table>
            </div>
          </>
        )}
      </section>

      {/* ── 6. what the story itself recorded ──────────────────────────────── */}

      {said && said.diagnoses.length > 0 && (
        <section className="card" aria-labelledby="diag">
          <h2 id="diag">Labels the story carries for this asset</h2>
          <Reveal as="ul" className="checks" runKey={`${equipmentKey}:${said.diagnoses.length}`}>
            {/* `text` already opens with the label and already says when the class declares
                itself undecidable. Restating either would be one fact rendered twice, and
                two renderings of one fact are two things that can disagree. */}
            {said.diagnoses.map((d) => (
              <li key={d.fault_label} className="row-check">
                <span>{d.text}</span>
              </li>
            ))}
          </Reveal>
        </section>
      )}

      <section className="card" aria-labelledby="work">
        <h2 id="work">Work raised against this asset</h2>

        {story.loading && <Skeleton lines={2} label="Loading outstanding work" />}

        {said && said.open_items.length === 0 && (
          <EmptyState
            title="No outstanding item was supplied with this story"
            because="Open items travel with the asset story and none was attached to this one, so this list is empty because nothing was read — not because nothing is open. An empty list here must never be read as a clear queue."
          />
        )}

        {said && said.open_items.length > 0 && (
          <Reveal as="ul" className="checks" runKey={`${equipmentKey}:${said.open_items.length}`}>
            {/* Same rule as the labels above: `text` already carries the kind, the
                reference, the state, the age and the blocker, in the service's words. */}
            {said.open_items.map((o) => (
              <li key={o.reference} className="row-check">
                <span>{o.text}</span>
              </li>
            ))}
          </Reveal>
        )}
      </section>

      {/* ── 7. the last section, and last is where a reader stops ──────────── */}

      <section className="card" aria-labelledby="cannot">
        <h2 id="cannot">What this page will not tell you</h2>

        {story.loading && <Skeleton lines={5} label="Loading stated absences" />}

        {said && (
          <p className={styles.note}>
            The service states {said.cannot_say.length} things it will not claim about this
            asset. {provenance.length} of them are signal provenance and are drawn at the top
            of this page; the {remainingSilences.length} below are the rest. None is a gap —
            each names what is missing, why, and what it costs.
          </p>
        )}

        {said && remainingSilences.length === 0 && said.cannot_say.length === 0 && (
          <EmptyState
            title="Nothing was recorded as unsayable about this asset"
            because="For an asset that can be scored the service is expected to state at least one absence, so an empty section here is worth checking against the service rather than read as a complete account."
          />
        )}

        {remainingSilences.length > 0 && (
          <Reveal
            as="ul"
            className={styles.silences}
            runKey={`${equipmentKey}:${remainingSilences.length}`}
          >
            {remainingSilences.map((c) => (
              <li key={`${c.silence}:${c.subject}`} className={styles.silence}>
                <div className={styles.provHead}>
                  <span className={styles.signalKey}>{c.subject}</span>
                  <span className={styles.kind}>{c.silence.replace(/_/g, ' ')}</span>
                </div>
                <p className={styles.because}>{c.because}</p>
                <p className={styles.consequence}>{c.consequence}</p>
              </li>
            ))}
          </Reveal>
        )}
      </section>

      {/* ── 8. the rest of the site ────────────────────────────────────────── */}

      <section className="card supporting" aria-labelledby="fleet">
        <h2 id="fleet">The other assets on this site</h2>

        {fleet.loading && <Skeleton lines={3} label="Loading the equipment list" />}

        {fleet.error && (
          <Degraded
            what="The equipment list"
            detail={fleet.error}
            endpoint={fleet.endpoint ?? undefined}
          />
        )}

        {fleet.data && (
          <>
            <p className={styles.note}>
              This site carries {fleet.data.total_count} assets and {fleet.data.scoreable_count}{' '}
              of them can be scored. The rest have a story too, and it is mostly a list of
              what cannot be said about them.
            </p>
            <Reveal as="ul" className={styles.others} runKey={otherAssets.length}>
              {otherAssets.map((e) => (
                <li key={e.key}>
                  <Link
                    href={`/asset/${encodeURIComponent(e.key)}`}
                    className={styles.otherLink}
                  >
                    <span>{e.display_name}</span>
                    {e.why_not && <span className={styles.whyNot}>{e.why_not}</span>}
                  </Link>
                </li>
              ))}
            </Reveal>
          </>
        )}
      </section>

      {/* The service's own rendering of the same story, kept behind a disclosure. It is not
          a second source — it is the same response, printed as the back end prints it, so a
          reader can check that this surface added nothing and dropped nothing. */}
      {said && (
        <section className="card supporting" aria-labelledby="record">
          <h2 id="record">The record as the service rendered it</h2>
          <details>
            <summary className={styles.summary}>Show the response in the words it arrived in</summary>
            <div className="table-scroll">
              <pre className={styles.record}>{said.rendered}</pre>
            </div>
          </details>
        </section>
      )}
    </>
  );
}
