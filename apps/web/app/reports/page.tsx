'use client';

/**
 * Reports — `R10` reconciliation and `R5` drill-down. The second P0 pillar.
 *
 * **Every headline figure this product states, recomputed from source, on load.** Not
 * sampled and not spot-checked. The documented column comes from the domain layer where the
 * measured facts are held as data; the recomputed column comes from a live query; neither
 * reads the other.
 *
 * **The figures that cannot be recomputed are shown, not hidden.** A reconciliation report
 * claiming 100% agreement while quietly excluding what it could not check would be exactly
 * the reassuring lie the rest of this product refuses. They render as "not recomputed" in
 * the muted absence style, and the summary counts them separately.
 *
 * Every row opens onto its source: the table, the row count, the plain-English basis, and a
 * bounded sample. A number a reader cannot open is a number they have to take on trust.
 */

import { Fragment, useCallback, useEffect, useState } from 'react';
import { AskCopilot } from '@/components/AskCopilot';
import { IconAlert, IconCheck } from '@/components/Icons';

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

interface Row {
  key: string;
  label: string;
  documented: number;
  recomputed: number | null;
  agrees: boolean;
  checkable: boolean;
  source_table: string;
  source_rows: number;
  basis: string;
}

interface Report {
  answer_state: string;
  summary: string;
  rows: Row[];
  checked: number;
  agreeing: number;
  all_agree: boolean;
  window: { end: string; note: string };
}

interface Source {
  figure: Row;
  sample: { equipment: string; slot_time: string; fault_label: string }[];
  sample_note: string;
}

export default function ReportsPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/reports/reconciliation`, { credentials: 'include' })
      .then((r) => r.json())
      .then(setReport)
      .catch((e: Error) => setError(e.message));
  }, []);

  const drill = useCallback(
    async (key: string) => {
      if (open === key) {
        setOpen(null);
        setSource(null);
        return;
      }
      setOpen(key);
      setSource(null);
      const r = await fetch(
        `${API}/api/v1/reports/figures/${encodeURIComponent(key)}/source`,
        { credentials: 'include' },
      );
      if (r.ok) setSource(await r.json());
    },
    [open],
  );

  return (
    <>
      <section className="card supporting">
        <h2>Reconciliation — every reported number, recomputed from source</h2>
        {/* This page is one report. The Copilot writes the wider one, and says what it leaves
            out — so a reader who wants the whole picture has somewhere to go from here. */}
        <div className="askcopilot-row">
          <AskCopilot question="Give me a report on the plant">
            Ask for the whole-plant report
          </AskCopilot>
        </div>
        {error && <p className="muted">Could not reach the back end: {error}</p>}
        {report && (
          <>
            <p className="muted">{report.summary}</p>
            <p className="muted">
              Recomputed on load, over the measured window only — {report.window.note.toLowerCase()}.
            </p>
          </>
        )}
      </section>

      {report && (
        <section className="card" aria-labelledby="rec">
          <h2 id="rec">
            {report.agreeing} of {report.checked} agree
          </h2>
          <table className="recon">
            <thead>
              <tr>
                <th scope="col">Figure</th>
                <th scope="col" className="num">
                  Documented
                </th>
                <th scope="col" className="num">
                  From source
                </th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <Fragment key={row.key}>
                  <tr
                    className="recon-row"
                    data-agrees={row.agrees}
                    data-checkable={row.checkable}
                  >
                    <td>
                      <button
                        className="linklike"
                        onClick={() => drill(row.key)}
                        aria-expanded={open === row.key}
                      >
                        {row.checkable ? (
                          row.agrees ? (
                            <IconCheck className="ico" />
                          ) : (
                            <IconAlert className="ico" />
                          )
                        ) : (
                          <IconAlert className="ico" />
                        )}
                        {row.label}
                      </button>
                    </td>
                    {/* Both columns are already numbers from the back end; nothing here
                        formats them, which is the same rule FigureView follows. */}
                    <td className="num mono">{row.documented}</td>
                    <td className="num mono">
                      {row.checkable ? (
                        row.recomputed
                      ) : (
                        <span className="absent">not recomputed</span>
                      )}
                    </td>
                    <td className="mono src">{row.source_table}</td>
                  </tr>
                  {open === row.key && (
                    <tr className="recon-detail">
                      <td colSpan={4}>
                        <p className="muted">
                          <strong>Basis:</strong> {row.basis}
                        </p>
                        {source?.figure.key === row.key && (
                          <>
                            <p className="muted">{source.sample_note}</p>
                            {source.sample.length > 0 && (
                              <ul className="mono sample">
                                {source.sample.slice(0, 8).map((s) => (
                                  <li key={s.slot_time + s.equipment}>
                                    {s.equipment} · {s.slot_time.replace('T', ' ')} ·{' '}
                                    {s.fault_label}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card supporting measure">
        <h2>Why this page exists</h2>
        <p className="muted">
          A report that states a number and cannot show where it came from asks to be taken
          on trust. Every figure here is recomputed from the source table on load and shown
          beside what the documents claim — and the one that cannot be recomputed says so
          rather than being counted as agreeing.
        </p>
      </section>
    </>
  );
}
