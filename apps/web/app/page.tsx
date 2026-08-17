'use client';

/**
 * The Copilot shell — topbar, rail, and one column of work, as `mvp/mock.html` lays it out.
 *
 * **The order on screen is the order of the argument.** Route, then evidence, then the
 * answer, then the audits. The reader sees the figures arrive *before* the prose, which is
 * the point: the evidence is not a summary of the answer, the answer is a reading of the
 * evidence. Reversing them would make the numbers look like illustration.
 *
 * Every interactive surface is a client component and there are no server actions on the
 * chat path — the plan's guidance for treating the App Router as a shell rather than as a
 * framework to fight.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { FigureView } from '@/components/FigureView';
import {
  IconAlert,
  IconCheck,
  IconHalt,
  IconUsers,
} from '@/components/Icons';
import { Differential } from '@/components/Differential';
import { ResidualChart, type SeriesBand, type SeriesPoint } from '@/components/ResidualChart';
import { useTurn } from '@/lib/useTurn';

interface WorkOrder {
  is_draft: boolean;
  title: string;
  priority: {
    band: string;
    is_complete: boolean;
    explanation: string;
    missing: { input: string; why: string }[];
  };
  evidence: { kind: string; text: string; source: string }[];
  cannot_close_until: string[];
  warnings: string[];
}

interface CaseItem {
  id: string;
  text: string;
  capability: string;
  blocking: boolean;
  is_sample: boolean;
  stored_reading: string | null;
  finding: string;
}

interface CaseView {
  state: string;
  content_is_sample: boolean;
  content_note: string;
  unreviewed_in_library: number;
  may_advance: boolean;
  advance_reason: string;
  operator_can_start: boolean;
  viewing_as: string;
  my_items: CaseItem[];
  for_others: { id: string; text: string; capability: string }[];
}

interface VerificationResult {
  outcome: 'PASS' | 'FAIL' | 'UNKNOWN';
  reason: string;
  closes_the_work_order: boolean;
  post_work_was_diagnosable: boolean;
  before: { in_band: number; total: number };
  after: { in_band: number; total: number };
  blocked_by: string | null;
  notes: string[];
}

interface Series {
  points: SeriesPoint[];
  band: SeriesBand | null;
  band_absent_reason: string | null;
  residual: string;
  equipment_key: string;
  null_count: number;
}

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

interface Episode {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  slot_count: number;
}

export default function Page() {
  const { turn, ask, stop } = useTurn();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selected, setSelected] = useState<Episode | null>(null);
  const [question, setQuestion] = useState('Why was this flagged, and what does the evidence support?');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [series, setSeries] = useState<Series | null>(null);
  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [ver, setVer] = useState<VerificationResult | null>(null);
  const [kase, setKase] = useState<CaseView | null>(null);
  const [viewAs, setViewAs] = useState('technician');

  useEffect(() => {
    fetch(`${API}/api/v1/episodes`, { credentials: 'include' })
      .then((r) => r.json())
      .then((body) => {
        setEpisodes(body.episodes ?? []);
        // Open on the critical episode: the only `critical` class, on the day chiller 1
        // carried five labels at once. It is the strongest single case in the data.
        setSelected(
          body.episodes?.find((e: Episode) => e.fault_label === 'CONDENSER_LOW_FLOW') ??
            body.episodes?.[0] ??
            null,
        );
      })
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  // The chart loads with the episode rather than with the turn: the evidence exists whether
  // or not anyone has asked a question about it, and showing it first is the same argument
  // the frame order makes — the answer is a reading of the evidence, not the other way round.
  useEffect(() => {
    if (!selected) return;
    setSeries(null);
    fetch(`${API}/api/v1/episodes/${encodeURIComponent(selected.id)}/series`, {
      credentials: 'include',
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setSeries)
      .catch(() => setSeries(null));

    // W2 · W3 · W4 — the job this episode would raise, with its evidence already attached.
    // Loaded alongside the chart because the whole point of the pillar is that the
    // justification travels with the work rather than being looked up afterwards.
    setWo(null);
    fetch(`${API}/api/v1/episodes/${encodeURIComponent(selected.id)}/work-order`, {
      credentials: 'include',
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setWo)
      .catch(() => setWo(null));

    // V1-V4 — did it work? Read the days after the episode as the post-work window. No
    // repair was ever recorded on this snapshot, so what is verified is a natural
    // clearing, which is exactly where the honest answer is most easily got wrong.
    setVer(null);
    fetch(
      `${API}/api/v1/episodes/${encodeURIComponent(selected.id)}/verification?after_days=8`,
      { credentials: 'include' },
    )
      .then((r) => (r.ok ? r.json() : null))
      .then(setVer)
      .catch(() => setVer(null));
  }, [selected]);

  // RC1 · RC3 · RC5 — the case this episode seeds, rendered for one capability. Reloaded
  // when the capability changes, because the task list is *theirs*, not everyone's.
  useEffect(() => {
    if (!selected) return;
    setKase(null);
    fetch(
      `${API}/api/v1/episodes/${encodeURIComponent(selected.id)}/case?viewing_as=${viewAs}`,
      { credentials: 'include' },
    )
      .then((r) => (r.ok ? r.json() : null))
      .then(setKase)
      .catch(() => setKase(null));
  }, [selected, viewAs]);

  const send = useCallback(() => {
    if (!question.trim()) return;
    ask({
      question,
      equipment_key: selected?.equipment_key,
      fault_label: selected?.fault_label,
      day: selected?.day,
    });
  }, [ask, question, selected]);

  const refused = turn.state?.state === 'NO_DIAGNOSIS' || Boolean(turn.refusal);
  const graded = useMemo(() => turn.audits.find((a) => a.findings), [turn.audits]);
  const notes = useMemo(() => turn.audits.filter((a) => !a.findings), [turn.audits]);

  return (
    <>

        <p className="muted" style={{ marginTop: 0 }}>
          The persona switcher is a demonstration affordance, not authentication — anyone
          here can select any persona. <code className="mono">Q41</code> is unanswered; see
          D-013.
        </p>

        <section className="card sunken" aria-labelledby="ep">
          <h2 id="ep">
            Detected episodes — measured window only
            {episodes.length > 0 && <> · {episodes.length} over 12 equipment-days</>}
          </h2>
          {loadError && (
            <p className="muted">Could not reach the back end on {API}: {loadError}</p>
          )}
          <div className="row">
            {episodes.slice(0, 12).map((e) => (
              <button
                key={e.id}
                className="chip"
                aria-pressed={selected?.id === e.id}
                onClick={() => setSelected(e)}
                title={`${e.slot_count} slot(s)`}
              >
                {e.equipment_key.replace('_', ' ')} · {e.fault_label} · {e.day}
              </button>
            ))}
          </div>
        </section>

        {series && series.points.length > 0 && (
          <section className="card" aria-labelledby="ch">
            <h2 id="ch">Residual against this asset&apos;s own band</h2>
            <ResidualChart
              points={series.points}
              band={series.band}
              bandAbsentReason={series.band_absent_reason}
              residual={series.residual}
              equipment={series.equipment_key.replace('_', ' ')}
              nullCount={series.null_count}
            />
          </section>
        )}

        {/* RC12-RC14. Mounted after the evidence and before the work order, because the
            differential is what stands between a named-but-ambiguous class and raising a job
            against whichever cause happened to be listed first. */}
        <Differential faultLabel={selected?.fault_label ?? null} />

        {wo && (
          <section className="card" aria-labelledby="wo">
            <h2 id="wo">
              Work order — draft{' '}
              <span className="pri" data-band={wo.priority.band}>
                {wo.priority.band}
              </span>
            </h2>
            <p className="answer measure">{wo.title}</p>

            <p className="muted">
              <strong>How this priority was reached:</strong> {wo.priority.explanation}
            </p>

            {!wo.priority.is_complete && wo.priority.missing.length > 0 && (
              <ul className="reasons">
                {wo.priority.missing.map((m) => (
                  <li key={m.input}>
                    <code className="mono">{m.input}</code> — {m.why}
                  </li>
                ))}
              </ul>
            )}

            {wo.warnings.map((w) => (
              <p className="muted" key={w}>
                {w}
              </p>
            ))}

            <p className="muted">
              <strong>Cannot close until:</strong>
            </p>
            <ul className="reasons">
              {wo.cannot_close_until.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>

            <p className="muted">
              {wo.evidence.length} pieces of evidence travel with this job — residuals with
              their bands and fit, every gate result, and the provenance of each unusable
              signal. Nothing is fetched again by whoever opens it.
            </p>
            <p className="muted">
              This is a <strong>draft</strong>. Nothing is persisted: Synex&apos;s own state
              belongs in PostgreSQL and that is not wired yet.
            </p>
          </section>
        )}

        {ver && (
          <section className="card" aria-labelledby="ver">
            <h2 id="ver">
              Verification — did it work?{' '}
              <span className="pri" data-band={ver.outcome}>
                {ver.outcome}
              </span>
            </h2>
            <p className="answer measure">{ver.reason}</p>

            <p className="muted">
              Readings inside this asset&apos;s own band: {ver.before.in_band} of{' '}
              {ver.before.total} before, {ver.after.in_band} of {ver.after.total} after.
            </p>

            {!ver.post_work_was_diagnosable && (
              <p className="muted">
                The gates did not pass over the post-work window, so nothing was being
                judged. A NULL means not diagnosed — never healthy.
              </p>
            )}

            {ver.notes.map((n) => (
              <p className="muted" key={n}>
                {n}
              </p>
            ))}

            <p className="muted">
              {ver.closes_the_work_order
                ? 'This closes the work order.'
                : ver.outcome === 'FAIL'
                  ? 'This does not close the work order — what was measured has not been fixed.'
                  : 'This does not close the work order. UNKNOWN is a permitted outcome, and an open job is the correct state when the data cannot decide.'}
              {ver.blocked_by && ` A PASS is unreachable until ${ver.blocked_by} is answered.`}
            </p>
          </section>
        )}

        {kase && (
          <section className="card" aria-labelledby="case">
            <h2 id="case">
              Case — {kase.state.replace('_', ' ')}{' '}
              <span className="pri" data-band={kase.may_advance ? 'PASS' : 'FAIL'}>
                {kase.may_advance ? 'can advance' : 'blocked'}
              </span>
            </h2>

            {/* The content is sample; the mechanism is not. Stated before the list, not
                after it, because a caveat under a checklist is read second. */}
            {kase.content_is_sample && (
              <p className="muted">
                <strong>Sample content.</strong> {kase.content_note}
              </p>
            )}

            <div className="row" role="group" aria-label="View the checklist as">
              {['operator', 'technician', 'supervisor'].map((c) => (
                <button
                  key={c}
                  className="chip"
                  aria-pressed={viewAs === c}
                  onClick={() => setViewAs(c)}
                >
                  as {c}
                </button>
              ))}
            </div>

            <ul className="checks">
              {kase.my_items.map((i) => (
                <li key={i.id} className={`row-check ${i.finding}`} data-blocking={i.blocking}>
                  <span className="mark" aria-hidden="true">
                    {i.finding === 'measured' ? '✓' : i.finding === 'cannot_check' ? '–' : '○'}
                  </span>
                  <span>
                    {i.text}
                    {i.blocking && <span className="badge warn">blocking</span>}
                    {i.stored_reading && (
                      <span className="stored">{i.stored_reading}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>

            <p className="muted">{kase.advance_reason}</p>

            {kase.for_others.length > 0 && (
              <p className="muted">
                {kase.for_others.length} check(s) belong to another capability and are not in
                this list — a check you cannot perform collapses out of your tasks rather
                than greying out at you. They stay on the case:{' '}
                {kase.for_others.map((i) => i.capability).join(', ')}.
              </p>
            )}

            {!kase.operator_can_start && (
              <p className="muted">
                Nothing here can be started by an operator, which should not happen — every
                fault class must leave one check somebody at the machine can do.
              </p>
            )}
          </section>
        )}

        <div className="composer">
          <label htmlFor="q" className="sr-only" style={{ position: 'absolute', left: -9999 }}>
            Your question
          </label>
          <input
            id="q"
            value={question}
            onChange={(ev) => setQuestion(ev.target.value)}
            onKeyDown={(ev) => ev.key === 'Enter' && !turn.streaming && send()}
            placeholder="Ask why a machine was flagged…"
            aria-label="Your question"
          />
          <button className="btn" onClick={turn.streaming ? stop : send} disabled={!question.trim()}>
            {turn.streaming ? 'Stop' : 'Ask'}
          </button>
        </div>

        {turn.route && (
          <section className="card supporting" aria-labelledby="rt">
            <h2 id="rt">Route</h2>
            <p className="mono">
              {turn.route.skill} · {turn.route.layer} · {turn.route.reason} ·{' '}
              {turn.route.used_model ? 'model arbiter used' : 'no model involved'}
            </p>
          </section>
        )}

        {turn.figures.length > 0 && (
          <section className="card" aria-labelledby="ev">
            <h2 id="ev">Evidence — every residual against this asset&apos;s own band</h2>
            {turn.figures.map((f, i) => (
              <FigureView key={f.name} figure={f} index={i} />
            ))}
          </section>
        )}

        {turn.evidence && (
          <section className="card supporting" aria-labelledby="pv">
            <h2 id="pv">Provenance</h2>
            <p className="muted">
              Window {turn.evidence.window.start} to {turn.evidence.window.end} · severity{' '}
              {turn.evidence.severity}
            </p>
            {turn.evidence.other_labels_same_day.length > 0 && (
              <p className="muted">
                Other labels the same day: {turn.evidence.other_labels_same_day.join(', ')} —
                one repair may explain several of them.
              </p>
            )}
            <ul className="reasons">
              {turn.evidence.signal_provenance.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <p className="mono">{turn.evidence.sources.join(' · ')}</p>
          </section>
        )}

        {/* D-015. A refusal gets its own card, its own rule and its own heading — and the
            accent, never red. A NO_DIAGNOSIS is a correct outcome and the most common one
            on this data; colouring it like an error would soften it in the other
            direction, making an answer look like a bug. */}
        {refused && turn.refusal && (
          <section className="card refusal measure" aria-labelledby="nd">
            <h2 id="nd">
              <IconHalt className="ico" style={{ verticalAlign: '-2px', marginRight: 6 }} />
              No diagnosis — a result, not a failure
            </h2>
            <p className="answer">{turn.refusal.text}</p>
            {turn.refusal.failed_gates.map((g) => (
              <div className="gate" key={g.gate}>
                <strong>{g.gate}</strong>
                <div>{g.why}</div>
                <div className="what">What would change this: {g.what_would_change_it}</div>
              </div>
            ))}
          </section>
        )}

        {turn.text && !refused && (
          <section className="card measure" aria-labelledby="an">
            <h2 id="an">Answer</h2>
            <p className="answer">{turn.text}</p>
          </section>
        )}

        {(graded || notes.length > 0) && (
          <section className="card supporting" aria-labelledby="hc">
            <h2 id="hc">Honesty checks</h2>
            {graded?.findings?.map((f) => (
              <div className="audit" key={f.audit} data-passed={f.passed}>
                {f.passed ? <IconCheck className="ico" /> : <IconAlert className="ico" />}
                <span>
                  <code>{f.audit}</code> — {f.detail}
                </span>
              </div>
            ))}
            {notes.map((a, i) => (
              <div className="audit" key={`n-${i}`} data-passed={!a.degraded}>
                {a.degraded ? <IconAlert className="ico" /> : <IconCheck className="ico" />}
                <span>{a.detail}</span>
              </div>
            ))}
          </section>
        )}

        {turn.error && <p className="muted">Stream error: {turn.error}</p>}
    </>
  );
}
