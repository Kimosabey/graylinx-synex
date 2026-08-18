'use client';

/**
 * Everything a turn did, gathered under the turn that did it.
 *
 * **The gap this closes.** Synex already emits the route taken and why, the model used, every
 * figure with its provenance, the window, the honesty audits and now the second model's
 * verdict — all as SSE frames, all correct. They were rendered as five separate cards stacked
 * down the page, so reading *how* one answer was reached meant scrolling past the machinery of
 * the one before it. The Thermynx implementation puts the same material in a single collapsible
 * panel under each answer, and that is the right shape: the answer is what you read, and the
 * working is what you open when you doubt it.
 *
 * **Closed by default, and that is the whole argument.** A reader who has to fold away the
 * evidence before reaching the next answer stops reading the evidence. Closed, the panel is one
 * line that says how much there is to check; open, it is the complete account. Nothing is
 * hidden — the summary line names the counts, so an empty inspector and a full one are
 * distinguishable without opening either.
 *
 * **It never re-formats a figure.** Every value here arrives already rendered by the back end,
 * which is what lets the numeric audit compare exact strings rather than pick a tolerance.
 */

import type { AuditFrame, EvidenceFrame, FigureFrame, RouteFrame } from '@/lib/frames';

export interface InspectorProps {
  route: RouteFrame | null;
  figures: FigureFrame[];
  evidence: EvidenceFrame | null;
  audits: AuditFrame[];
  usedModel: boolean;
}

export function Inspector({ route, figures, evidence, audits, usedModel }: InspectorProps) {
  const findings = audits.flatMap((a) => a.findings ?? []);
  const failed = findings.filter((f) => !f.passed);
  const provenance = evidence?.signal_provenance ?? [];

  const nothingToShow = !route && figures.length === 0 && !evidence && findings.length === 0;
  if (nothingToShow) return null;

  // The summary counts what is inside, so a closed panel still says how much working there is.
  const parts = [
    route ? `routed by ${route.layer}` : null,
    figures.length ? `${figures.length} figure(s)` : null,
    provenance.length ? `${provenance.length} provenance note(s)` : null,
    findings.length ? `${findings.length} check(s)` : null,
    failed.length ? `${failed.length} failed` : null,
  ].filter(Boolean);

  return (
    <details className="inspector">
      <summary>
        How this answer was reached — {parts.join(' · ')}
      </summary>

      {route && (
        <div className="inspector-block">
          <h3>Route</h3>
          <p className="mono">
            {route.skill} · {route.layer} · {route.reason}
          </p>
          <p className="muted">
            {/* Which of the five layers settled it matters more than the skill: layer 3 means a
                keyword decided and no model was spent, and that is a fact about cost as well as
                about determinism. */}
            {usedModel
              ? 'A model was consulted for this turn.'
              : 'No model was consulted — the deterministic layers settled it.'}
          </p>
        </div>
      )}

      {evidence && (
        <div className="inspector-block">
          <h3>Evidence</h3>
          <p className="muted">
            Window {evidence.window.start} to {evidence.window.end}
            {evidence.window.is_snapshot ? ' (snapshot)' : ''} · severity {evidence.severity}
          </p>
          {evidence.other_labels_same_day.length > 0 && (
            <p className="muted">
              Other labels the same day: {evidence.other_labels_same_day.join(', ')} — one repair
              may explain several of them.
            </p>
          )}
          {provenance.length > 0 && (
            <ul className="reasons">
              {provenance.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          <p className="mono">{evidence.sources.join(' · ')}</p>
        </div>
      )}

      {figures.length > 0 && (
        <div className="inspector-block">
          <h3>Figures</h3>
          <ul className="reasons">
            {figures.map((f) => (
              <li key={f.name}>
                <code>{f.name}</code> — {f.text}
                {f.poor_fit ? ' · poor fit' : ''}
                {f.provenance ? ` · ${f.provenance}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {findings.length > 0 && (
        <div className="inspector-block">
          <h3>Checks</h3>
          {findings.map((f) => (
            <div className="audit" key={f.audit} data-passed={f.passed}>
              <span>
                <code>{f.audit}</code> — {f.detail}
              </span>
            </div>
          ))}
        </div>
      )}
    </details>
  );
}
