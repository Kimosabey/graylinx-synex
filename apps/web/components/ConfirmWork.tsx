'use client';

/**
 * The act that turns a draft into a job — and the only one.
 *
 * **Why the answer alone was not enough.** A `NEEDS_APPROVAL` turn said a draft was ready,
 * named its priority and listed its evidence, and then stopped. Everything a reader needed to
 * decide was on screen and there was nowhere to say yes: the only route to a stored job ran
 * through a surface they would have to find. A product that can draft the work and cannot
 * accept it reads as a demonstration rather than a tool.
 *
 * **The id travels, never the draft.** Confirming rebuilds the draft from the same evidence
 * pack the answer was built from, so what gets stored is what was shown — kept literally by
 * the back end rather than by trusting whatever the browser was holding.
 *
 * **Three outcomes, and the button says which happened.** Stored; or an approval request came
 * back because this identity does not hold `approve_work`, which is not a refusal because
 * somebody else can sign it; or it was refused outright. A second confirm returns the first
 * row unmodified rather than raising a duplicate job, and that is reported as what it is.
 */

import { useState } from 'react';

import { IconHalt } from '@/components/Icons';

interface Props {
  /** `equipment:fault:day`, from the state frame. */
  episodeId: string;
}

type Result = { tone: 'stored' | 'awaiting' | 'refused'; text: string };

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

export function ConfirmWork({ episodeId }: Props) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  async function confirm() {
    setBusy(true);
    try {
      const response = await fetch(
        `${BASE}/api/v1/episodes/${encodeURIComponent(episodeId)}/work-order/confirm`,
        { method: 'POST' },
      );
      const body = await response.json();
      if (!response.ok) {
        setResult({ tone: 'refused', text: body?.detail ?? `HTTP ${response.status}` });
        return;
      }
      // The back end names its own outcome. Reading the shape rather than restating it keeps
      // one source of truth for what happened, so the wording here can never disagree with
      // the row that was — or was not — written.
      if (body?.work_order_id || body?.stored) {
        setResult({
          tone: 'stored',
          text:
            body.reason ??
            `Stored as ${body.work_order_id}. The evidence shown above travelled with it.`,
        });
      } else if (body?.approval_request || body?.state === 'NEEDS_APPROVAL') {
        setResult({
          tone: 'awaiting',
          text:
            body.reason ??
            'This identity may not approve work. The request is addressed to a capability, ' +
              'not a person — somebody who holds it can sign this.',
        });
      } else {
        setResult({ tone: 'refused', text: body?.reason ?? 'Refused, with no reason given.' });
      }
    } catch (cause) {
      setResult({ tone: 'refused', text: `The platform could not be reached: ${cause}` });
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <p className="confirmwork-result" data-tone={result.tone}>
        {result.tone === 'refused' && (
          <IconHalt className="ico" style={{ verticalAlign: '-2px', marginRight: 6 }} />
        )}
        {result.text}
      </p>
    );
  }

  return (
    <div className="confirmwork">
      <button type="button" className="btn primary" onClick={confirm} disabled={busy}>
        {busy ? 'Confirming…' : 'Confirm and raise this work order'}
      </button>
      {/* What confirming means, next to the control that does it. A reader who has to go
          somewhere else to find out what a button does will either not press it or press it
          without knowing. */}
      <span className="muted">
        Writes the job with the evidence above attached. Nothing is dispatched.
      </span>
    </div>
  );
}
