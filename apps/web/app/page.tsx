'use client';

/**
 * The Copilot shell.
 *
 * Every interactive surface is a client component and there are no server actions on the
 * chat path — the plan's guidance for treating the App Router as a shell rather than as a
 * framework to fight. The stream is read in `useTurn`.
 *
 * **The order on screen is the order of the argument.** Route, then evidence, then the
 * answer, then the audits. A reader sees the figures arrive *before* the prose, which is the
 * point: the evidence is not a summary of the answer, the answer is a reading of the
 * evidence. Reversing them would make the numbers look like illustration.
 */

import { useCallback, useEffect, useState } from 'react';
import { FigureView } from '@/components/FigureView';
import { useTurn } from '@/lib/useTurn';

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

interface Episode {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  slot_count: number;
}

const PERSONAS = [
  ['reliability_engineer', 'Reliability Engineer'],
  ['technician', 'Technician'],
  ['supervisor', 'Supervisor'],
  ['administrator', 'Administrator'],
] as const;

export default function Page() {
  const { turn, ask, stop } = useTurn();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selected, setSelected] = useState<Episode | null>(null);
  const [persona, setPersona] = useState<string>('reliability_engineer');
  const [question, setQuestion] = useState('Why was this flagged, and what does the evidence support?');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/episodes`, { credentials: 'include' })
      .then((r) => r.json())
      .then((body) => {
        setEpisodes(body.episodes ?? []);
        // Open on the critical episode: the only `critical` class, on the day chiller 1
        // carried five labels at once. It is the strongest single case in the data.
        const hero =
          body.episodes?.find((e: Episode) => e.fault_label === 'CONDENSER_LOW_FLOW') ??
          body.episodes?.[0] ??
          null;
        setSelected(hero);
      })
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  const switchPersona = useCallback(async (key: string) => {
    await fetch(`${API}/api/v1/personas/${key}`, { method: 'POST', credentials: 'include' });
    setPersona(key);
  }, []);

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

  return (
    <main className="wrap">
      <header className="masthead">
        <h1>Graylinx Synex</h1>
        <p>Intelligent Operations, Connected by AI.</p>
      </header>

      {/* The persona switcher is labelled as a demonstration affordance, here as well as in
          every API response. D-013: the danger with a stand-in is that it stops being one. */}
      <div className="card">
        <h2>Persona — a demonstration switcher, not authentication</h2>
        <div className="row">
          {PERSONAS.map(([key, label]) => (
            <button
              key={key}
              className="chip"
              aria-pressed={persona === key}
              onClick={() => switchPersona(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>
          Detected episodes — measured window only
          {episodes.length > 0 && <> · {episodes.length} over 12 equipment-days</>}
        </h2>
        {loadError && <p className="muted">Could not reach the back end: {loadError}</p>}
        <div className="row">
          {episodes.slice(0, 14).map((e) => (
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
      </div>

      <div className="composer">
        <input
          value={question}
          onChange={(ev) => setQuestion(ev.target.value)}
          onKeyDown={(ev) => ev.key === 'Enter' && !turn.streaming && send()}
          placeholder="Ask why a machine was flagged…"
          aria-label="Your question"
        />
        <button onClick={turn.streaming ? stop : send} disabled={!question.trim()}>
          {turn.streaming ? 'Stop' : 'Ask'}
        </button>
      </div>

      {turn.route && (
        <div className="card">
          <h2>Route</h2>
          <p className="mono">
            {turn.route.skill} · {turn.route.layer} · {turn.route.reason}
            {' · '}
            {turn.route.used_model ? 'model arbiter used' : 'no model involved'}
          </p>
        </div>
      )}

      {turn.figures.length > 0 && (
        <div className="card">
          <h2>Evidence — every residual against this asset&apos;s own band</h2>
          {turn.figures.map((f) => (
            <FigureView key={f.name} figure={f} />
          ))}
        </div>
      )}

      {turn.evidence && (
        <div className="card">
          <h2>Provenance</h2>
          <p className="muted">Window: {turn.evidence.window.start} to {turn.evidence.window.end}</p>
          <p className="muted">Severity: {turn.evidence.severity}</p>
          {turn.evidence.other_labels_same_day.length > 0 && (
            <p className="muted">
              Other labels the same day: {turn.evidence.other_labels_same_day.join(', ')} — one
              repair may explain several of them.
            </p>
          )}
          <ul className="muted">
            {turn.evidence.signal_provenance.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="mono">{turn.evidence.sources.join(' · ')}</p>
        </div>
      )}

      {/* D-015. A refusal gets its own card, its own colour and its own heading. Rendering
          it in the same typeface as a confident answer would soften it by presentation, and
          on this data the refusal is the modal outcome — 5,309 slots against 674. */}
      {refused && turn.refusal && (
        <div className="card refusal">
          <h2>No diagnosis — and this is a result, not a failure</h2>
          <p className="answer">{turn.refusal.text}</p>
          {turn.refusal.failed_gates.map((g) => (
            <div className="gate" key={g.gate}>
              <strong>{g.gate}</strong> — {g.why}
              <div className="what">What would change this: {g.what_would_change_it}</div>
            </div>
          ))}
        </div>
      )}

      {turn.text && !refused && (
        <div className="card">
          <h2>Answer</h2>
          <p className="answer">{turn.text}</p>
        </div>
      )}

      {turn.audits.length > 0 && (
        <div className="card">
          <h2>Honesty checks</h2>
          {turn.audits.map((a, i) =>
            a.findings ? (
              a.findings.map((f) => (
                <div className="audit" key={f.audit} data-passed={f.passed}>
                  <span className="mark">{f.passed ? '✓' : '!'}</span>
                  <span>
                    <strong>{f.audit}</strong> — {f.detail}
                  </span>
                </div>
              ))
            ) : (
              <div className="audit" key={`d-${i}`} data-passed={!a.degraded}>
                <span className="mark">{a.degraded ? '!' : '✓'}</span>
                <span>{a.detail}</span>
              </div>
            ),
          )}
        </div>
      )}

      {turn.state && (
        <p className="muted">
          Answer state: <strong>{turn.state.state}</strong>
          {turn.state.used_model === false && <> · assembled without a model</>}
        </p>
      )}

      {turn.error && <p className="muted">Stream error: {turn.error}</p>}
    </main>
  );
}
