'use client';

/**
 * `U6` — the reliability workspace. The triage queue a reliability engineer works from.
 *
 * **What this surface is for.** A person decides what to look at next. So the screen answers
 * three questions before it answers anything else: what did the FDD engine detect, which of
 * those became a case, and can this episode be judged at all. Everything else is detail
 * behind a row.
 *
 * **Two endpoints, because one of them cannot see the gap.** `/api/v1/workspace` is the
 * surface of record — the case queue, the sections this identity is not admitted to, and the
 * queue order with its reason. `/api/v1/episodes` is what the detector actually found. The
 * workspace route derives its detection list from the cases themselves, so it can only ever
 * report *all detected episodes have a case*; comparing the two routes here is the only place
 * the difference is visible. That difference is inherited constraint 21 — **detection is not
 * seeding** — and twenty-two episodes once sat outside the queue while it read as a clean
 * plant.
 *
 * **Nothing on this page is ranked here.** Rows render in the order the API returned them and
 * there is no client-side sort anywhere in this file. The order and its reason are printed
 * verbatim from `order_reason`, which says in the back end's own words that this is age and
 * not a ranking. The FDD rules name the fault, the Control Plane decides who may see it, and
 * a deterministic formula sets the priority band — the language model explains, and explains
 * only.
 *
 * **The gates are read on request, not assumed.** Judgeability and the priority band each
 * cost a round trip per episode, so a row says *gates not read* until it has been read, never
 * *judgeable*. The header action reads the whole queue; expanding one row reads just that one.
 *
 * **`NO_DIAGNOSIS` is a correct outcome here.** It renders through `StateChip`, which carries
 * the refusal treatment and prints the word — never an error row, never the stop colour.
 *
 * `PageEnter` is deliberately absent: `Shell` mounts it once for every surface.
 */

import Link from 'next/link';
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FigureView } from '@/components/FigureView';
import { IconAlert, IconCheck } from '@/components/Icons';
import { Degraded, EmptyState, PageHeader, Skeleton, StateChip } from '@/components/Surface';
import { Pressable, Reveal, ValueChange } from '@/components/motion';
import { API_BASE, useApi } from '@/components/useApi';
import type { AnswerState, FigureFrame } from '@/lib/frames';
import s from './workspace.module.css';

/* ── the shapes the back end actually returns ─────────────────────────────── */

interface Admission {
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

interface ResidualBehind {
  equipment_key: string;
  model_name: string;
  nrmse: number | null;
  absence: string;
}

interface FaultRow {
  seed_key: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  state: string;
  slot_count: number;
  residuals: ResidualBehind[];
  residuals_note: string;
  fit_note: string;
  case_note: string;
}

interface WorkspaceView {
  faults: FaultRow[];
  withheld: Admission[];
  unreadable: UnreadableCase[];
  detected_not_queued: string[];
  seeding_note: string;
  order_reason: string;
  viewing_as: string;
  store_note: string;
}

interface Episode {
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
  episodes: Episode[];
}

interface Gate {
  gate: string;
  passed: boolean;
  reason: string;
  remedy: string;
  unresolved_question: string | null;
}

interface PackResidual {
  name: string;
  figure: Omit<FigureFrame, 'name' | 'verdict' | 'model_nrmse' | 'poor_fit'>;
  verdict: string;
  model_nrmse: number | null;
  poor_fit: boolean;
  rendered: string;
  source: string;
}

interface Pack {
  episode_id: string;
  answer_state: AnswerState;
  window: { start: string; end: string; is_snapshot: boolean; source: string };
  may_diagnose: boolean;
  has_poor_fit: boolean;
  severity: { value: string; text: string };
  model_declares_undecidable: boolean;
  residuals: PackResidual[];
  gates: Gate[];
  signal_provenance: string[];
  sources: string[];
  other_labels_same_day: string[];
}

interface Priority {
  band: string;
  fault_label: string;
  severity: string;
  slot_count: number;
  sustained: boolean;
  used: string[];
  missing: { input: string; why: string }[];
  is_complete: boolean;
  explanation: string;
}

interface Draft {
  is_draft: boolean;
  equipment_display: string;
  title: string;
  priority: Priority;
  cannot_close_until: string[];
  warnings: string[];
}

/* ── reading the evidence behind a row ────────────────────────────────────── */

/**
 * One episode, read or not read. A discriminated union rather than three optional fields, so
 * *not read yet* and *read and refused* cannot be confused for one another — which is the
 * distinction this whole surface turns on.
 */
type Read =
  | { status: 'reading' }
  | { status: 'read'; pack: Pack; draft: Draft }
  | { status: 'failed'; error: string };

/**
 * How many episodes are read at once.
 *
 * Both requests behind a row recompute a day of residuals against that asset's own bands, so
 * this is deliberately small: the API is shared, and a queue that reads itself as fast as it
 * can is a queue that makes every other surface slow while it does.
 */
const LANES = 3;

async function readEpisode(id: string, signal: AbortSignal): Promise<Read> {
  const at = `${API_BASE}/api/v1/episodes/${encodeURIComponent(id)}`;
  try {
    const [packed, drafted] = await Promise.all([
      fetch(`${at}/pack`, { credentials: 'include', signal }),
      fetch(`${at}/work-order`, { credentials: 'include', signal }),
    ]);
    // The status line as the server gave it, per route — a 403 on the pack and a 503 on the
    // draft are different facts, and the reader is the one who has to act on the difference.
    if (!packed.ok) throw new Error(`pack: ${packed.status} ${packed.statusText}`.trim());
    if (!drafted.ok) throw new Error(`work order: ${drafted.status} ${drafted.statusText}`.trim());
    return {
      status: 'read',
      pack: (await packed.json()) as Pack,
      draft: (await drafted.json()) as Draft,
    };
  } catch (cause) {
    return { status: 'failed', error: cause instanceof Error ? cause.message : String(cause) };
  }
}

function useGateReads() {
  const [reads, setReads] = useState<Record<string, Read>>({});
  const known = useRef<Record<string, Read>>({});
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    known.current = reads;
  }, [reads]);

  useEffect(
    () => () => {
      controller.current?.abort();
      // Cleared as well as aborted: React re-mounts effects in development, and reusing an
      // aborted controller would make every later read fail for a reason that is not real.
      controller.current = null;
    },
    [],
  );

  const read = useCallback(async (ids: string[]) => {
    // A row that failed is retried; a row already read, or still reading, is left alone. The
    // alternative — skipping everything already touched — leaves the control dead after a
    // single network blip, with no way back except a page reload.
    const todo = ids.filter((id) => {
      const already = known.current[id];
      return already === undefined || already.status === 'failed';
    });
    if (todo.length === 0) return;

    controller.current ??= new AbortController();
    const { signal } = controller.current;

    const starting: Record<string, Read> = {};
    todo.forEach((id) => {
      starting[id] = { status: 'reading' };
    });
    known.current = { ...known.current, ...starting };
    setReads((previous) => ({ ...previous, ...starting }));

    let cursor = 0;
    const lane = async () => {
      while (!signal.aborted) {
        const next = cursor;
        cursor += 1;
        if (next >= todo.length) return;
        const id = todo[next];
        const outcome = await readEpisode(id, signal);
        if (signal.aborted) return;
        known.current = { ...known.current, [id]: outcome };
        setReads((previous) => ({ ...previous, [id]: outcome }));
      }
    };

    await Promise.all(Array.from({ length: Math.min(LANES, todo.length) }, lane));
  }, []);

  return { reads, read };
}

/* ── small presentational helpers. Nothing here formats a number. ─────────── */

/** `2026-04-10T15:20:00` becomes `15:20` — a substring of what the API sent, not a reformat. */
const clock = (iso: string) => iso.slice(11, 16);

const words = (key: string) => key.replace(/_/g, ' ');

/** The identity constraint 35 gives a case: one per equipment, fault and day. */
const identity = (equipment: string, label: string, day: string) => `${equipment}|${label}|${day}`;

/* ── the surface ──────────────────────────────────────────────────────────── */

export default function WorkspacePage() {
  const workspace = useApi<WorkspaceView>('/api/v1/workspace');
  const detected = useApi<EpisodeList>('/api/v1/episodes');
  const { reads, read } = useGateReads();

  const [asset, setAsset] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const view = workspace.data;
  const episodes = useMemo(() => detected.data?.episodes ?? [], [detected.data]);
  const faults = useMemo(() => view?.faults ?? [], [view]);

  /** Which assets this queue actually covers — taken from the rows, never a written list. */
  const assets = useMemo(() => {
    const seen: string[] = [];
    episodes.forEach((episode) => {
      if (!seen.includes(episode.equipment_key)) seen.push(episode.equipment_key);
    });
    return seen;
  }, [episodes]);

  /**
   * Filtering is not ranking. The API order is preserved exactly; this narrows the set the
   * reader is looking at and reorders nothing.
   */
  const shown = useMemo(
    () => (asset === null ? episodes : episodes.filter((e) => e.equipment_key === asset)),
    [episodes, asset],
  );

  /**
   * Constraint 21, computed across the two routes because neither can see it alone. Matched
   * on the triple constraint 35 defines rather than on either route's key string, since the
   * case store joins it with a pipe and the episode route with a colon.
   */
  const unseeded = useMemo(() => {
    if (view === null || detected.data === null) return null;
    const queued = new Set(faults.map((f) => identity(f.equipment_key, f.fault_label, f.day)));
    return episodes.filter((e) => !queued.has(identity(e.equipment_key, e.fault_label, e.day)));
  }, [view, detected.data, faults, episodes]);

  const readCount = shown.filter((e) => reads[e.id]?.status === 'read').length;
  const sweeping = shown.some((e) => reads[e.id]?.status === 'reading');

  const toggle = useCallback(
    (id: string) => {
      setOpen((current) => (current === id ? null : id));
      void read([id]);
    },
    [read],
  );

  const readAll = useCallback(() => void read(shown.map((e) => e.id)), [read, shown]);

  const measured = detected.data?.window;

  return (
    <>
      <PageHeader
        title="Reliability workspace"
        lede="Every episode the FDD engine detected in the measured window, the case each one opens, and whether it can be judged at all. The order comes from the back end with its reason attached; nothing on this page is re-ordered here."
        meta={
          measured ? (
            <>
              Measured window ends {measured.end.replace('T', ' ')} · {measured.note} · viewing as{' '}
              {words(view?.viewing_as ?? 'an unresolved persona')}
            </>
          ) : (
            'Data window not read yet'
          )
        }
        actions={
          shown.length > 0 ? (
            <button
              type="button"
              className={`btn ${s.tap}`}
              onClick={readAll}
              disabled={sweeping || readCount === shown.length}
              aria-live="polite"
            >
              {sweeping
                ? `Reading — ${readCount} of ${shown.length}`
                : readCount === shown.length
                  ? `Gates read on all ${shown.length}`
                  : `Read the gates on ${shown.length} episodes`}
            </button>
          ) : null
        }
      />

      {workspace.error && (
        <Degraded
          what="The reliability workspace"
          detail={workspace.error}
          endpoint={workspace.endpoint ?? undefined}
        >
          <p className="muted">
            The case queue, the withheld sections and the queue order all come from this route,
            so none of them appears below. Start the back end and reload — nothing here is
            served from a cache in the meantime.
          </p>
        </Degraded>
      )}

      {detected.error && (
        <Degraded
          what="The detected-episode list"
          detail={detected.error}
          endpoint={detected.endpoint ?? undefined}
        >
          <p className="muted">
            Without it the queue cannot be checked against the detector, so an empty queue below
            means only that no case is open. It does not mean the plant is clean.
          </p>
        </Degraded>
      )}

      {(workspace.loading || detected.loading) && (
        <section className="card">
          <h2>Reading the queue</h2>
          <Skeleton lines={6} label="Reading the reliability workspace" />
        </section>
      )}

      {/* ── the four counts ─────────────────────────────────────────────── */}

      {detected.data && (
        <div className={s.tiles}>
          <div className={s.tile}>
            <span className={s.tileLabel}>Episodes detected</span>
            <span className={s.tileValue}>{detected.data.episode_count}</span>
            <p className={s.tileNote}>
              Across {detected.data.equipment_days} equipment-days. One per equipment, fault and
              day.
            </p>
          </div>

          <div className={s.tile}>
            <span className={s.tileLabel}>Cases open</span>
            <span className={s.tileValue} data-absent={view === null}>
              {view === null ? 'not read' : faults.length}
            </span>
            <p className={s.tileNote}>
              {view === null
                ? 'The case store was not reached on this page load.'
                : view.store_note ||
                  'Read from the case store. A case is what a detected episode becomes once it is seeded.'}
            </p>
          </div>

          <div className={s.tile} data-attention={unseeded !== null && unseeded.length > 0}>
            <span className={s.tileLabel}>Detected, no case</span>
            <span className={s.tileValue} data-absent={unseeded === null}>
              {unseeded === null ? 'not checked' : unseeded.length}
            </span>
            <p className={s.tileNote}>
              {unseeded === null
                ? 'Both the queue and the detector have to be readable before this can be compared at all.'
                : 'Detection is not seeding. A detector that fires into nowhere leaves a queue that reads as a plant with nothing wrong.'}
            </p>
          </div>

          <div className={s.tile}>
            <span className={s.tileLabel}>Gates read</span>
            {/* Deliberately not a `ValueChange`. The sweep moves this figure dozens of times
                from one press, and that primitive expresses *you changed something and this
                answered* — thirty-nine tweens in a row would read as flicker, not as cause. */}
            <span className={s.tileValue}>
              {readCount} of {shown.length}
            </span>
            <p className={s.tileNote}>
              Whether an episode can be judged costs a request per row, so a row that has not
              been read says so rather than implying an outcome.
            </p>
          </div>
        </div>
      )}

      {/* ── the order, and who set it ───────────────────────────────────── */}

      {view && (
        <section className="card supporting measure" aria-labelledby="ordering">
          <h2 id="ordering">How this queue is ordered</h2>
          <p className="muted">{view.order_reason}</p>
          <p className="muted">
            The FDD rules name the fault. The Control Plane decides who may see it. A
            deterministic formula sets the priority band, and three of its four inputs do not
            exist on this plant, so most rows carry no band at all. The language model explains
            a row; it ranks nothing here, and no row is re-sorted in the browser.
          </p>
        </section>
      )}

      {/* ── the open cases ──────────────────────────────────────────────── */}

      {view && (
        <section className="card" aria-labelledby="open-cases">
          <h2 id="open-cases">Cases open</h2>
          {faults.length === 0 ? (
            <EmptyState
              title="No case is open in this queue"
              because={`${view.seeding_note}${
                view.store_note ? ` ${view.store_note}` : ''
              } An empty case queue is not a clean plant: it means nothing has been seeded, or everything seeded has left the queue. The detected episodes below are the check on that.`}
            />
          ) : (
            <Reveal as="div" className="grid-cards" runKey={faults.length}>
              {faults.map((fault) => (
                <Pressable
                  key={fault.seed_key}
                  href={`/case/${encodeURIComponent(fault.seed_key)}`}
                  className="card"
                  ariaLabel={`Open the case for ${fault.fault_label} on ${words(
                    fault.equipment_key,
                  )}, ${fault.day}`}
                >
                  <span className={s.caseTop}>
                    <span className={s.caseFault}>{fault.fault_label}</span>
                    <span className="badge verdict">{words(fault.state)}</span>
                  </span>
                  <p className={s.caseMeta}>
                    {words(fault.equipment_key)} · {fault.day} · {fault.slot_count} slots
                  </p>
                  {fault.fit_note && <p className={s.caseNote}>{fault.fit_note}</p>}
                  {fault.residuals_note && <p className={s.caseNote}>{fault.residuals_note}</p>}
                  {fault.case_note && <p className={s.caseNote}>{fault.case_note}</p>}
                </Pressable>
              ))}
            </Reveal>
          )}
        </section>
      )}

      {/* ── the detected episodes ───────────────────────────────────────── */}

      {detected.data && (
        <section className="card" aria-labelledby="detected">
          <h2 id="detected">Detected episodes</h2>

          {unseeded !== null && (
            <p className="muted">
              {unseeded.length === 0
                ? `Every one of the ${episodes.length} detected episodes has a case in the queue above. Checked across the two routes rather than assumed.`
                : `${unseeded.length} of ${episodes.length} detected episodes have no case in the queue above. Until one is seeded the case queue cannot show it, and a queue that shows nothing reads as a plant with nothing wrong.`}
            </p>
          )}

          {assets.length > 1 && (
            <div className={s.controls}>
              <span className={s.controlLabel}>Asset</span>
              <button
                type="button"
                className={`chip ${s.tap}`}
                aria-pressed={asset === null}
                onClick={() => setAsset(null)}
              >
                All
              </button>
              {assets.map((key) => (
                <button
                  key={key}
                  type="button"
                  className={`chip ${s.tap}`}
                  aria-pressed={asset === key}
                  onClick={() => setAsset(key)}
                >
                  {words(key)}
                </button>
              ))}
              <span className={s.shown}>
                <ValueChange value={`${shown.length} shown`} />
              </span>
            </div>
          )}

          {shown.length === 0 ? (
            <EmptyState
              title="No detected episode matches this filter"
              because="The filter narrows what is displayed and does nothing else. Clear it to see every episode the detector returned for the measured window."
            />
          ) : (
            <table className="data stackable">
              <caption>
                In the order the API returned. Rows are not sorted, scored or grouped in the
                browser.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Fault</th>
                  <th scope="col">Equipment</th>
                  <th scope="col">Day</th>
                  <th scope="col">Slots</th>
                  <th scope="col">Span</th>
                  <th scope="col">Can it be judged</th>
                  <th scope="col">Priority</th>
                </tr>
              </thead>
              <Reveal as="tbody" runKey={`${asset ?? 'all'}:${shown.length}`}>
                {shown.map((episode) => {
                  const state = reads[episode.id];
                  const isOpen = open === episode.id;
                  const rowId = `episode-${episode.id.replace(/[^a-zA-Z0-9]/g, '-')}`;

                  return (
                    /* Two sibling rows, never an extra cell on the first one: a `td` added to
                       the row it belongs to would break the column count and, below 640px,
                       land inside the stacked card rather than under it. */
                    <Fragment key={episode.id}>
                      <tr id={rowId}>
                        <td data-label="Fault">
                          <button
                            type="button"
                            className={`linklike ${s.rowButton}`}
                            onClick={() => toggle(episode.id)}
                            aria-expanded={isOpen}
                            aria-controls={`${rowId}-panel`}
                          >
                            <span className={s.caret} aria-hidden="true">
                              ›
                            </span>
                            <span className={s.fault}>{episode.fault_label}</span>
                          </button>
                        </td>
                        <td data-label="Equipment">{words(episode.equipment_key)}</td>
                        <td data-label="Day" className="num">
                          {episode.day}
                        </td>
                        <td data-label="Slots" className="num">
                          {episode.slot_count}
                        </td>
                        <td data-label="Span" className="num">
                          {clock(episode.first_slot)}–{clock(episode.last_slot)}
                        </td>
                        <td data-label="Can it be judged">
                          <span className={s.judgeCell}>
                            {state === undefined && (
                              <span className="absent">gates not read</span>
                            )}
                            {state?.status === 'reading' && (
                              <span className="absent">reading the gates</span>
                            )}
                            {state?.status === 'failed' && (
                              <span className="absent">could not be read</span>
                            )}
                            {state?.status === 'read' && (
                              <>
                                <StateChip state={state.pack.answer_state} />
                                {state.pack.has_poor_fit && (
                                  <span className="badge warn">poor fit</span>
                                )}
                              </>
                            )}
                          </span>
                        </td>
                        <td data-label="Priority">
                          {state?.status === 'read' ? (
                            <span className="pri" data-band={state.draft.priority.band}>
                              {state.draft.priority.band}
                            </span>
                          ) : (
                            <span className="absent">not computed yet</span>
                          )}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <EpisodeDetail
                            episode={episode}
                            state={state}
                            panelId={`${rowId}-panel`}
                          />
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </Reveal>
            </table>
          )}
        </section>
      )}

      {/* ── what this identity is not admitted to ───────────────────────── */}

      {view && view.withheld.length > 0 && (
        <section className="card supporting measure" aria-labelledby="withheld">
          <h2 id="withheld">Withheld from this identity</h2>
          <p className="muted">
            Reported rather than omitted: a surface that quietly showed two sections of three
            would read as complete. Each line names the capability that would admit it, and a
            capability is not a rank.
          </p>
          <ul className={s.list}>
            {view.withheld.map((entry) => (
              <li key={entry.section}>
                <strong>{words(entry.section)}</strong> — {entry.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      {view && view.unreadable.length > 0 && (
        <section className="card supporting measure" aria-labelledby="unreadable">
          <h2 id="unreadable">Rows the state machine could not read</h2>
          <p className="muted">
            Reported rather than dropped. A case that disappears because a string did not parse
            leaves a surface that looks calm and is not.
          </p>
          <ul className={s.list}>
            {view.unreadable.map((entry) => (
              <li key={entry.seed_key}>
                <code>{entry.seed_key}</code> — {entry.reason}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/* ── one expanded row ─────────────────────────────────────────────────────── */

function EpisodeDetail({
  episode,
  state,
  panelId,
}: {
  episode: Episode;
  state: Read | undefined;
  panelId: string;
}) {
  return (
    <td className={s.detailCell} colSpan={7} id={panelId} data-label="">
      {(state === undefined || state.status === 'reading') && (
        <Skeleton lines={4} label={`Reading the evidence behind ${episode.fault_label}`} />
      )}

      {state?.status === 'failed' && (
        <Degraded
          what={`The evidence behind ${episode.fault_label}`}
          detail={state.error}
          endpoint={`${API_BASE}/api/v1/episodes/${episode.id}`}
        />
      )}

      {state?.status === 'read' && (
        <ReadDetail episode={episode} pack={state.pack} draft={state.draft} />
      )}
    </td>
  );
}

function ReadDetail({ episode, pack, draft }: { episode: Episode; pack: Pack; draft: Draft }) {
  const failed = pack.gates.filter((gate) => !gate.passed);

  return (
    <div className={s.detail}>
      <div className={s.panel}>
        <h3>Can this be judged</h3>
        <p className="state-line">
          <StateChip state={pack.answer_state} />
          <span>
            {pack.may_diagnose
              ? 'Every gate passed, so this episode may be diagnosed.'
              : `${failed.length} of ${pack.gates.length} gates did not pass, so a refusal is the correct outcome rather than an answer.`}
          </span>
        </p>

        {pack.gates.map((gate) => (
          <p className="audit" data-passed={gate.passed} key={gate.gate}>
            {gate.passed ? <IconCheck className="ico" /> : <IconAlert className="ico" />}
            <span>
              <code>{gate.gate}</code>
              {gate.reason ? ` — ${gate.reason}` : ' — passed'}
              {gate.remedy ? ` What would change it: ${gate.remedy}` : ''}
              {gate.unresolved_question ? ` (${gate.unresolved_question})` : ''}
            </span>
          </p>
        ))}

        <p className="muted">Severity: {pack.severity.text}</p>

        {pack.model_declares_undecidable && (
          <p className="muted">
            This class declares itself undecidable — the data could not separate the candidate
            causes. That is the trained model reporting ambiguity, not a gap to be tidied away.
          </p>
        )}

        {pack.other_labels_same_day.length > 0 && (
          <p className="muted">
            The same machine carried {pack.other_labels_same_day.join(', ')} on this day. One
            repair may explain several of them.
          </p>
        )}

        <div className={s.rowLinks}>
          <Link className={s.rowLink} href={`/case/${encodeURIComponent(episode.id)}`}>
            Open the case
          </Link>
          <Link className={s.rowLink} href={`/asset/${encodeURIComponent(episode.equipment_key)}`}>
            Open {words(episode.equipment_key)}
          </Link>
        </div>
      </div>

      <div className={s.panel}>
        <h3>
          Priority
          <span className="pri" data-band={draft.priority.band}>
            {draft.priority.band}
          </span>
        </h3>
        <p className="muted">{draft.priority.explanation}</p>
        <p className="muted">
          Computed from {draft.priority.used.join(', ')}. What the formula could not reach:
        </p>
        <ul className={s.list}>
          {draft.priority.missing.map((gap) => (
            <li key={gap.input}>
              <strong>{words(gap.input)}</strong> — {gap.why}
            </li>
          ))}
        </ul>

        {draft.warnings.length > 0 && (
          <>
            <h3>Before anyone is dispatched</h3>
            <ul className={s.list}>
              {draft.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </>
        )}

        <h3>Residuals behind this row</h3>
        {pack.residuals.map((residual, index) => (
          <FigureView
            key={residual.name}
            index={index}
            figure={{
              ...residual.figure,
              name: residual.name,
              verdict: residual.verdict,
              model_nrmse: residual.model_nrmse,
              poor_fit: residual.poor_fit,
            }}
          />
        ))}

        <h3>Where it came from</h3>
        <ul className={s.provenance}>
          {pack.sources.map((source) => (
            <li key={source}>{source}</li>
          ))}
          {pack.signal_provenance.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
