/**
 * The streaming frame contract, mirrored from the back end.
 *
 * `backend/app/agents/sse_contract.py` is the source of truth and
 * `scripts/verify_sse_contract.py` fails the build if these two lists disagree — the check
 * that kills "the web renders a frame the API stopped sending". Ten frames, not the nine the
 * plan lists: D-015 added `no_diagnosis` and is the later decision.
 */

export const FRAMES = [
  'route',
  'stage',
  'token',
  'figure',
  'evidence',
  'audit',
  'no_diagnosis',
  'state',
  'done',
  'error',
] as const;

export type FrameName = (typeof FRAMES)[number];

/** CONTEXT.md §7. Every turn ends in exactly one of these six. */
export const ANSWER_STATES = [
  'ANSWERED',
  'PARTIAL',
  'NO_DIAGNOSIS',
  'NEEDS_APPROVAL',
  'BLOCKED',
  'FAILED',
] as const;

export type AnswerState = (typeof ANSWER_STATES)[number];

export interface RouteFrame {
  skill: string;
  layer: string;
  reason: string;
  equipment_key: string | null;
  used_model: boolean;
}

export interface StageFrame {
  stage: string;
  detail: string;
}

/**
 * A figure, already rendered by the back end.
 *
 * `text` is the display string and `value` is present only so a client can tell an absence
 * (`null`) from a zero. **Render `text`, never `value`.** The back end formats every number
 * exactly once, which is what lets the numeric audit compare values rather than guess a
 * tolerance — and re-formatting here would reintroduce the rounding it exists to catch.
 */
export interface FigureFrame {
  name: string;
  label: string;
  value: number | null;
  unit: string | null;
  basis: string;
  absence: string | null;
  provenance: string;
  text: string;
  note: string | null;
  verdict: string;
  model_nrmse: number | null;
  poor_fit: boolean;
}

export interface EvidenceFrame {
  window: { start: string; end: string; is_snapshot: boolean; source: string };
  sources: string[];
  signal_provenance: string[];
  other_labels_same_day: string[];
  severity: string;
}

export interface AuditFinding {
  audit: string;
  passed: boolean;
  severity: 'hard' | 'soft';
  detail: string;
}

export interface AuditFrame {
  passed: boolean;
  replaced?: boolean;
  degraded?: boolean;
  detail?: string;
  badges?: string[];
  findings?: AuditFinding[];
}

export interface NoDiagnosisFrame {
  text: string;
  failed_gates: {
    gate: string;
    why: string;
    what_would_change_it: string;
    unresolved_question: string | null;
  }[];
}

export interface StateFrame {
  state: AnswerState;
  used_model?: boolean;
}
