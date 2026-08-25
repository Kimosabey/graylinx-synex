'use client';

/**
 * The answer, rendered with the structure the back end actually gives it.
 *
 * **What this replaces, and the bug the first version still had.** Originally the whole answer
 * was one `<p>`. The first fix split on blank lines and made a block a list only when *every*
 * line in it was a bullet — which was still wrong for the text this product produces, because
 * it contains no blank lines at all:
 *
 *     Chiller 1 on 2026-04-15 (1 slot(s), …).
 *     Detected label: CONDENSER_LOW_FLOW. Severity: critical.
 *       - Dp_residual: 80.7 — high for this asset (healthy band …); model nRMSE 5.38
 *       - Sp_residual: 78.5 — high for this asset …
 *
 * Two prose lines and six bullets, in one block, with single newlines. "All lines are bullets"
 * was false, so the entire thing rendered as a paragraph and the residual list arrived as a
 * wall of `<br>`-separated text — the format least likely to be read by somebody standing at a
 * machine.
 *
 * So blocks are split into **runs**: consecutive bullet lines become a list, everything else
 * becomes prose, and a block may hold several of each. That is the shape both answer paths
 * actually emit — the deterministic composition and the model, which is prompted to write its
 * residuals the same way.
 *
 * **Deliberately not a markdown renderer.** Pulling in a markdown library would let untrusted
 * model output decide what elements this page can produce — headings, links, images, raw HTML.
 * This handles three things that carry meaning here and passes everything else through as plain
 * text: paragraphs, list items, and inline code. Anything the model invents beyond that renders
 * as the characters it typed, which is the correct failure.
 *
 * **No number is reformatted.** Every figure arrives already rendered by the back end — that is
 * what lets the numeric audit compare exact values rather than pick a tolerance — so this only
 * ever wraps text in elements.
 */

import { Fragment, type ReactNode } from 'react';

/** A leading `- ` or `• `, with any indentation. Both answer paths use it per residual. */
const BULLET = /^\s*[-•]\s+/;

/** Split on backticks and wrap the odd segments. Nothing else in the string is interpreted. */
function withCode(line: string, key: string): ReactNode[] {
  return line.split('`').map((part, i) =>
    i % 2 === 1 ? (
      <code key={`${key}-c${i}`}>{part}</code>
    ) : (
      <Fragment key={`${key}-t${i}`}>{part}</Fragment>
    ),
  );
}

interface Run {
  kind: 'prose' | 'list';
  lines: string[];
}

/** Group consecutive lines of the same kind. A block may hold several runs of each. */
function runsOf(lines: string[]): Run[] {
  const runs: Run[] = [];
  for (const line of lines) {
    const kind: Run['kind'] = BULLET.test(line) ? 'list' : 'prose';
    const last = runs[runs.length - 1];
    if (last && last.kind === kind) last.lines.push(line);
    else runs.push({ kind, lines: [line] });
  }
  return runs;
}

export function AnswerText({ text }: { text: string }) {
  if (!text.trim()) return null;

  // Blank lines separate blocks where they exist; single newlines separate lines within one.
  const blocks = text.trim().split(/\n\s*\n/);

  return (
    <div className="answer">
      {blocks.flatMap((block, b) =>
        runsOf(block.split('\n').filter((l) => l.trim())).map((run, r) =>
          run.kind === 'list' ? (
            <ul className="answer-list" key={`b${b}r${r}`}>
              {run.lines.map((line, i) => (
                <li key={`b${b}r${r}i${i}`}>
                  {withCode(line.replace(BULLET, ''), `b${b}r${r}i${i}`)}
                </li>
              ))}
            </ul>
          ) : (
            <p key={`b${b}r${r}`}>
              {run.lines.map((line, i) => (
                <Fragment key={`b${b}r${r}l${i}`}>
                  {i > 0 && <br />}
                  {withCode(line, `b${b}r${r}l${i}`)}
                </Fragment>
              ))}
            </p>
          ),
        ),
      )}
    </div>
  );
}
