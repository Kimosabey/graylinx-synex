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
  IconChat,
  IconCheck,
  IconClipboard,
  IconGauge,
  IconHalt,
  IconShield,
  IconUsers,
} from '@/components/Icons';
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
        setSelected(
          body.episodes?.find((e: Episode) => e.fault_label === 'CONDENSER_LOW_FLOW') ??
            body.episodes?.[0] ??
            null,
        );
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
  const graded = useMemo(() => turn.audits.find((a) => a.findings), [turn.audits]);
  const notes = useMemo(() => turn.audits.filter((a) => !a.findings), [turn.audits]);

  return (
    <div className="shell">
      <header className="topbar">
        {/* An `h1`, not a styled span. The page needs exactly one level-one heading for
            screen-reader navigation, and the product name is it — semantics are not a
            function of type size. Caught by the accessibility scan, which reported it as
            the page's only violation. */}
        <h1 className="brand">Graylinx Synex</h1>
        <span className="tagline">Intelligent Operations, Connected by AI.</span>
        <span className="spacer" />
        {turn.state && (
          <span className="state-line">
            <span className="state-pill" data-state={turn.state.state}>
              {turn.state.state}
            </span>
          </span>
        )}
      </header>

      <nav className="rail" aria-label="Surfaces">
        <div className="railgroup">
          <h2>Copilot</h2>
          <button className="navitem" aria-current="page">
            <IconChat className="ico" />
            Ask
          </button>
        </div>
        <div className="railgroup">
          <h2>Surfaces</h2>
          <button className="navitem" disabled title="Arrives with M2">
            <IconGauge className="ico" />
            Reliability
          </button>
          <button className="navitem" disabled title="Arrives with M2">
            <IconClipboard className="ico" />
            Work orders
          </button>
          <button className="navitem" disabled title="Arrives with M3">
            <IconShield className="ico" />
            Verification
          </button>
        </div>
        <div className="railgroup">
          <h2>Persona</h2>
          {PERSONAS.map(([key, label]) => (
            <button
              key={key}
              className="navitem"
              aria-current={persona === key ? 'page' : undefined}
              onClick={() => switchPersona(key)}
            >
              <IconUsers className="ico" />
              {label}
            </button>
          ))}
        </div>
      </nav>

      <main className="content">
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
          <section className="card" aria-labelledby="rt">
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
          <section className="card sunken" aria-labelledby="pv">
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
          <section className="card refusal" aria-labelledby="nd">
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
          <section className="card" aria-labelledby="an">
            <h2 id="an">Answer</h2>
            <p className="answer">{turn.text}</p>
          </section>
        )}

        {(graded || notes.length > 0) && (
          <section className="card" aria-labelledby="hc">
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
      </main>
    </div>
  );
}
