/**
 * The case surface's read contract — **transcribed from the running API, not guessed.**
 *
 * Every interface here was taken from an actual response on
 * `http://127.0.0.1:8001/api/v1/episodes/…`, which is the only way a surface can promise that
 * nothing on it was invented. Where the back end sends a field this surface does not render,
 * the field is simply absent from the type; where it sends one this surface *does* render,
 * the name and the shape are its own.
 *
 * **Nothing in this module formats a number.** `FigureView` is the only component permitted
 * to render one, and `tests/contracts.test.mjs` greps for the formatting APIs to keep it that
 * way. The helpers below split strings and match enums; none of them touches arithmetic.
 */

import type { SeriesBand, SeriesPoint } from '@/components/ResidualChart';
import { ANSWER_STATES, type AnswerState } from '@/lib/frames';

/* ── the index: every detected episode, one case each ──────────────────────── */

/**
 * One detected episode — and therefore exactly one case.
 *
 * `RC8`'s idempotency is the id: `equipment:label:day`. Inherited constraint 35 — a single
 * real fault spans hundreds of consecutive readings, so a case per slot would bury one
 * afternoon under hundreds of rows.
 */
export interface EpisodeRow {
  id: string;
  equipment_key: string;
  fault_label: string;
  day: string;
  slot_count: number;
  first_slot: string;
  last_slot: string;
}

export interface EpisodeIndex {
  window: { end: string; includes_simulated: boolean; note: string };
  episode_count: number;
  equipment_days: number;
  episodes: EpisodeRow[];
}

export interface EquipmentRow {
  key: string;
  display_name: string;
  kind: string;
  scoreable: boolean;
  why_not: string | null;
}

export interface EquipmentIndex {
  equipment: EquipmentRow[];
  scoreable_count: number;
  total_count: number;
}

/* ── the evidence pack ─────────────────────────────────────────────────────── */

/**
 * A figure the back end already rendered. `text` is what goes on screen; `value` exists only
 * so a client can tell an absence from a zero.
 */
export interface PackFigure {
  label: string;
  value: number | null;
  unit: string | null;
  basis: string;
  absence: string | null;
  provenance: string;
  text: string;
  note: string | null;
}

export interface PackResidual {
  name: string;
  figure: PackFigure;
  verdict: string;
  model_nrmse: number | null;
  poor_fit: boolean;
  rendered: string;
  source: string;
}

/**
 * One deterministic gate. A gate that fails is not an error — it produces `NO_DIAGNOSIS`,
 * naming the check that stopped it and what would change the answer.
 */
export interface PackGate {
  gate: string;
  passed: boolean;
  reason: string;
  remedy: string;
  unresolved_question: string | null;
}

export interface EvidencePack {
  episode_id: string;
  answer_state: string;
  window: { start: string; end: string; is_snapshot: boolean; source: string };
  may_diagnose: boolean;
  has_poor_fit: boolean;
  severity: { value: string; text: string };
  model_declares_undecidable: boolean;
  residuals: PackResidual[];
  gates: PackGate[];
  signal_provenance: string[];
  sources: string[];
  other_labels_same_day: string[];
}

/* ── the case itself ───────────────────────────────────────────────────────── */

/**
 * `RC3`. Five capabilities — who can *answer* a checklist item. Not a ladder and not the
 * persona system: inherited constraint 25 keeps role order display order.
 */
export const CAPABILITIES = [
  'operator',
  'maintenance',
  'technician',
  'supervisor',
  'vendor',
] as const;

export type CaseCapability = (typeof CAPABILITIES)[number];

export interface CaseItem {
  id: string;
  text: string;
  capability: string;
  blocking: boolean;
  is_sample: boolean;
  stored_reading: string | null;
  finding: string;
}

export interface CaseBody {
  id: string;
  equipment_key: string;
  equipment_display: string;
  fault_label: string | null;
  day: string;
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

/* ── the work raised, and the proof it worked ──────────────────────────────── */

export interface WorkOrderDraft {
  is_draft: boolean;
  equipment_key: string;
  equipment_display: string;
  fault_label: string;
  day: string;
  title: string;
  priority: {
    band: string;
    fault_label: string;
    severity: string;
    slot_count: number;
    sustained: boolean;
    used: string[];
    missing: { input: string; why: string }[];
    is_complete: boolean;
    explanation: string;
  };
  evidence: { kind: string; text: string; source: string }[];
  cannot_close_until: string[];
  warnings: string[];
}

export interface VerificationBody {
  episode_id: string;
  post_work_window_days: number;
  post_work_was_diagnosable: boolean;
  outcome: string;
  reason: string;
  residual_name: string;
  before: { in_band: number; total: number };
  after: { in_band: number; total: number };
  closes_the_work_order: boolean;
  blocked_by: string | null;
  notes: string[];
}

export interface SeriesBody {
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

/* ── helpers ───────────────────────────────────────────────────────────────── */

/**
 * The id a case is named by, split back into its three parts.
 *
 * Returns `null` rather than a partial object, because a malformed id must produce a stated
 * refusal on screen and not a page half-filled with the pieces that happened to parse.
 *
 * **Two encodings of one identity arrive here, and both are legitimate.** Constraint 35's
 * triple — equipment, fault class, day — is joined with a colon by `list_episodes`
 * (`backend/app/api/v1/episodes.py`) and with a pipe by `CaseRow.make_seed_key`
 * (`backend/app/db/state.py`). The reliability workspace links with the seed key, the case
 * queue links with the episode id, and they address the same case. Rejecting the pipe form
 * would tell a reader arriving from an open case that their own case id is malformed.
 *
 * So both are accepted and `canonical` carries the colon form the episode routes are keyed
 * by. Every request this surface makes is built from `canonical`, never from the raw segment,
 * or the id would parse and the fetch would still 404. Neither delimiter can occur inside a
 * part: equipment keys and fault labels are underscore-cased and the day is an ISO date.
 */
export function parseCaseId(
  raw: string,
): { equipmentKey: string; faultLabel: string; day: string; canonical: string } | null {
  const parts = raw.split(raw.includes('|') ? '|' : ':');
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) return null;
  return {
    equipmentKey: parts[0],
    faultLabel: parts[1],
    day: parts[2],
    canonical: parts.join(':'),
  };
}

/**
 * A route segment as the router hands it back, decoded once and safely.
 *
 * Case ids carry colons, so a link writes `%3A` into the path. Next decodes the parameter for
 * us, but a hand-typed or double-encoded URL still arrives escaped, and `decodeURIComponent`
 * throws on a malformed escape rather than returning it unchanged.
 */
export function decodeSegment(raw: string): string {
  if (!raw.includes('%')) return raw;
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

/**
 * `CONTEXT.md` §7 — every turn ends in exactly one of six states.
 *
 * Anything else is reported as itself rather than coerced into the nearest of the six. A
 * seventh state arriving is a contract break worth seeing, not worth rounding off.
 */
export function asAnswerState(value: string): AnswerState | null {
  return (ANSWER_STATES as readonly string[]).includes(value) ? (value as AnswerState) : null;
}

/**
 * What each of the six means, in the words of the answer contract.
 *
 * Product copy, not data: no figure, no threshold and no judgement about any machine lives
 * here. `NO_DIAGNOSIS` is described as an outcome because that is what it is — on this data
 * it is the modal one.
 */
export const STATE_MEANING: Record<AnswerState, string> = {
  ANSWERED:
    'Every gate passed, so the evidence below could be read. Which fault class this is stays the isolation path’s answer; the language model only puts it in plain English.',
  PARTIAL:
    'Part of the question is answered and the rest is not. What is missing is named rather than left to be inferred from a gap.',
  NO_DIAGNOSIS:
    'A deterministic gate stopped the diagnosis before anything was named. A correct outcome, and the most common one on this data — the gate says what stopped it and what would change it.',
  NEEDS_APPROVAL:
    'The Control Plane requires an authorization before this goes further. Authority is plain software; it is never granted by the language model.',
  BLOCKED: 'Something outside this case has to move before the case can. What that is, is named.',
  FAILED:
    'The turn did not complete. Nothing here may be read as a statement about the equipment — nothing was judged.',
};

/** `2026-04-10T13:40:00` → `13:40`. A slice, not a format: no locale, no arithmetic. */
export function clockOf(iso: string): string {
  return iso.length >= 16 ? iso.slice(11, 16) : iso;
}

/** `2026-04-10T13:40:00` → `2026-04-10 13:40`, for a line that needs the day as well. */
export function stampOf(iso: string): string {
  return iso.length >= 16 ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : iso;
}
