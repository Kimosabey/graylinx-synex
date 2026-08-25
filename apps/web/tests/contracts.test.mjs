/**
 * The two rules the web layer must not break, as tests.
 *
 * `node --test`, no test framework. The repo holds every dependency to a recorded reason
 * (it is why Ragas is banned), and a runner is not worth adding to assert two invariants
 * that are both source greps and one DOM shape.
 *
 * 1. **Only `FigureView` renders a number.** The plan asks for this one by name. A number
 *    formatted twice is a number that can disagree with itself, and the back end already
 *    rendered every figure exactly once — which is precisely what lets the numeric audit
 *    compare exact values instead of picking a tolerance.
 *
 * 2. **The frame list matches the back end.** `scripts/verify_sse_contract.py` checks this
 *    from the Python side; this is the same assertion from the TypeScript side, so a
 *    divergence fails in whichever job runs first.
 */

import { strict as assert } from 'node:assert';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const WEB = fileURLToPath(new URL('..', import.meta.url));
const SKIP = new Set(['node_modules', '.next', 'tests', 'out', 'dist']);

function sources(dir = WEB, acc = []) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) sources(full, acc);
    else if (/\.(ts|tsx)$/.test(name)) acc.push(full);
  }
  return acc;
}

// ── 1. only FigureView renders a number ──────────────────────────────────────

test('no module except FigureView formats a number', () => {
  const offenders = [];
  for (const file of sources()) {
    const rel = relative(WEB, file).replace(/\\/g, '/');
    if (rel === 'components/FigureView.tsx') continue;
    const text = readFileSync(file, 'utf8');
    for (const pattern of [/\.toFixed\(/, /Intl\.NumberFormat/, /\.toPrecision\(/]) {
      if (pattern.test(text)) offenders.push(`${rel} matches ${pattern}`);
    }
  }
  assert.deepEqual(
    offenders,
    [],
    'Only FigureView may render a number, and even it does not format — it prints the ' +
      'display string the back end produced. Offenders:\n  ' + offenders.join('\n  '),
  );
});

test('FigureView itself does not format either', () => {
  const text = readFileSync(join(WEB, 'components/FigureView.tsx'), 'utf8');
  assert.ok(!/\.toFixed\(/.test(text), 'FigureView must print figure.text, never re-format');
  assert.ok(text.includes('figure.text'), 'FigureView must render the back end display string');
});

// ── 2. the streaming contract matches the back end ───────────────────────────

const CONTRACT = join(
  WEB,
  '..',
  '..',
  'backend',
  'app',
  'agents',
  'sse_contract.py',
);

function pythonTuple(source, name) {
  const m = source.match(new RegExp(`${name}[^=]*=\\s*\\(([^)]*)\\)`, 's'));
  assert.ok(m, `${name} not found in sse_contract.py`);
  return [...m[1].matchAll(/"([a-z_A-Z]+)"/g)].map((x) => x[1]);
}

test('the frame list matches the back end contract exactly', () => {
  // Read as text rather than imported: `lib/frames.ts` is TypeScript, and adding a loader
  // to this test would mean adding a dependency to assert a list of ten strings.
  const declared = [
    ...readFileSync(join(WEB, 'lib/frames.ts'), 'utf8')
      .match(/export const FRAMES = \[([^\]]*)\]/s)[1]
      .matchAll(/'([a-z_]+)'/g),
  ].map((x) => x[1]);

  const backend = pythonTuple(readFileSync(CONTRACT, 'utf8'), 'FRAMES');
  assert.deepEqual(
    [...declared].sort(),
    [...backend].sort(),
    'The web frame list and the back-end contract disagree. This is the exact drift the ' +
      'contracts gate exists to catch: a frame the client stops handling renders as ' +
      'nothing, silently.',
  );
});

test('the answer states match the back end', () => {
  const declared = [
    ...readFileSync(join(WEB, 'lib/frames.ts'), 'utf8')
      .match(/export const ANSWER_STATES = \[([^\]]*)\]/s)[1]
      .matchAll(/'([A-Z_]+)'/g),
  ].map((x) => x[1]);

  // The back end re-exports these from app.domain.answer, so read them there.
  const answerPy = join(WEB, '..', '..', 'backend', 'app', 'domain', 'answer.py');
  const backend = [
    ...readFileSync(answerPy, 'utf8').matchAll(/^\s{4}([A-Z_]+) = "([A-Z_]+)"$/gm),
  ].map((x) => x[2]);

  assert.deepEqual([...declared].sort(), [...backend].sort());
  assert.ok(declared.includes('NO_DIAGNOSIS'), 'NO_DIAGNOSIS is a state, not an error');
});

// ── 3. the refusal must not be styled as an error ────────────────────────────

test('the refusal does not borrow the stop or warn colour', () => {
  const css = readFileSync(join(WEB, 'app/globals.css'), 'utf8');
  const refusal = css.match(/\.refusal\s*\{([^}]*)\}/s);
  assert.ok(refusal, '.refusal must be styled');
  assert.ok(
    !/var\(--stop\)|var\(--warn\)/.test(refusal[1]),
    'A NO_DIAGNOSIS is a correct outcome and the most common one on this data. Colouring ' +
      'it like an error softens it in the other direction — it reads as a bug rather than ' +
      'as an answer. D-015.',
  );
  assert.ok(/var\(--refusal\)/.test(refusal[1]), 'the refusal has its own token');
});
