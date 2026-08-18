'use client';

/**
 * Administrator — `U8`, over `G1`–`G3`. The governance surface.
 *
 * **What this screen is for.** What Graylinx Synex is allowed to do, and to whom: the policy
 * version in force, the capabilities each persona holds, the risk levels and what clears them,
 * the boundaries nothing clears, and the record that every request was made. It is a *read*
 * surface and it does not offer to write — the persona-to-capability map is a constant in the
 * Control Plane and the required capability per risk level is a constant in the authority
 * table, so authoring either is a code change reviewed like any other. `Q76` is open and the
 * screen says so rather than growing a control that would not work.
 *
 * **The three failures this layout is built against.**
 *
 * 1. *A governance screen that reads as a seniority ladder.* A list of roles down a page reads
 *    as a chain of command whatever the caption says, and ranking capability by seniority once
 *    sent a filter-drier restriction to a supervisor because one incidental records question
 *    outranked three refrigeration measurements. So personas are a *grid* rather than a column,
 *    every card lists the capabilities it does **not** hold as well as those it does, and the
 *    back end’s own computed finding — that these sets do not nest — is shown with the
 *    incomparable pairs behind it. Constraints 13 and 25.
 *
 * 2. *A screen that governs nothing and does not say so.* Nothing authenticates behind this
 *    surface: `gl_user`, `gl_role` and `gl_access` hold zero rows and `is_production_identity`
 *    is hard-wired false (`Q41`, D-013). That notice is the first thing on the page, because a
 *    caveat printed after the matrix it qualifies has already been read too late.
 *
 * 3. *A boundary presented as a gap.* Equipment control is refused permanently and for every
 *    persona — Synex reads the plant and never commands it. It takes the refusal treatment,
 *    which is calm and deliberate by design: colouring a permanent guarantee like an error
 *    would read as something broken rather than as something decided. `--refusal`, never
 *    `--stop`, never `--warn`.
 *
 * **Nothing on this page is typed in.** Every figure, every name and every sentence of
 * reasoning comes off `/api/v1/administrator` and `/api/v1/audit`. The one exception is the
 * equipment-control guarantee, which is a product boundary rather than a reading — it is
 * labelled as such, kept out of the API-derived list, and carries no number.
 */

import { useCallback } from 'react';
import { Degraded, EmptyState, PageHeader, Skeleton, StateChip } from '@/components/Surface';
import { Reveal, ValueChange } from '@/components/motion';
import { useApi } from '@/components/useApi';
import { IconCheck, IconHalt } from '@/components/Icons';
import { ANSWER_STATES, type AnswerState } from '@/lib/frames';
import s from './admin.module.css';

/* ── the wire ──────────────────────────────────────────────────────────────── */

interface ApprovalRow {
  risk: string;
  requirement: string;
  required_capability: string | null;
  holders: string[];
  /** The engine’s own sentence for this level. Rendered verbatim, never paraphrased. */
  who: string;
}

interface PersonaRow {
  persona: string;
  display_name: string;
  capabilities: string[];
}

interface MissingCapability {
  name: string;
  /** The feature or question the absence traces to — `G8`, `Q41`, `Q76`. */
  source: string;
  reason: string;
}

interface AdministratorView {
  policy: {
    version: string;
    is_stated: boolean;
    statement: string;
    version_is_a_string: string;
  };
  identity_kind: string;
  identity_note: string;
  is_production_identity: boolean;
  approval_matrix: ApprovalRow[];
  personas: PersonaRow[];
  order_note: string;
  ordering: {
    forms_a_ladder: boolean;
    contained_pairs: string[][];
    incomparable_pairs: string[][];
    finding: string;
  };
  not_available: MissingCapability[];
  viewing_as: string;
}

interface AuditRow {
  request_id: string;
  persona: string;
  identity_kind: string;
  action: string;
  equipment_key: string | null;
  answer_state: string;
  policy_version: string;
  gates_failed: string[];
  at: number;
}

interface AuditTrail {
  durable: boolean;
  total: number;
  rows: AuditRow[];
}

/** The one requirement that is a refusal rather than a threshold. `policy.Requirement`. */
const NO_APPROVAL_CLEARS_IT = 'no_approval_clears_it';

/** How much of the tail to ask for. A request parameter, not a figure — what lands on screen
 *  is counted from the response, so the reader is told how many of how many they are seeing. */
const TRAIL_TAIL = 25;

/**
 * An epoch seconds value to the form every timestamp in this product is written in.
 *
 * UTC deliberately, and labelled UTC in the column head: an audit row read months later on a
 * machine in another timezone must not silently shift. Nothing is rounded and nothing is
 * formatted beyond dropping the sub-second tail — `FigureView` remains the only component
 * that renders a figure, and this is a clock reading rather than a measurement.
 */
function auditTime(at: number): string {
  return new Date(at * 1000).toISOString().replace('T', ' ').slice(0, 19);
}

/** `CONTEXT.md` §7 allows six. Anything else is printed as it arrived rather than coerced into
 *  the nearest one — a seventh state showing up as `BLOCKED` would be a silent mis-report. */
function isAnswerState(value: string): value is AnswerState {
  return (ANSWER_STATES as readonly string[]).includes(value);
}

export default function AdminPage() {
  const view = useApi<AdministratorView>('/api/v1/administrator');
  const trail = useApi<AuditTrail>(`/api/v1/audit?limit=${TRAIL_TAIL}`);

  const { reload: reloadView } = view;
  const { reload: reloadTrail } = trail;

  // `G1`: scope is recomputed every turn and never inherited. So the primary action on this
  // surface is to ask again — not to save, because there is nothing here to save.
  const reread = useCallback(() => {
    reloadView();
    reloadTrail();
  }, [reloadView, reloadTrail]);

  const v = view.data;

  // Computed once rather than per card: the column set is the same for all five, and it is the
  // union of what the Control Plane actually granted rather than a list held in this file.
  const capabilityColumns = v ? everyCapability(v.personas) : [];

  return (
    <>
      <PageHeader
        title="Administrator"
        lede="What Graylinx Synex is allowed to do, and to whom. The policy version in force, the capability each persona holds, the risk levels and what clears them — and the boundaries that nothing clears."
        meta={
          v ? (
            <>
              viewing as {v.viewing_as}
              <span className={s.metaSep}>·</span>
              policy {v.policy.version}
              <span className={s.metaSep}>·</span>
              identity {v.identity_kind}
            </>
          ) : (
            'scope is recomputed for this request and never inherited'
          )
        }
        actions={
          <button
            type="button"
            className="btn"
            onClick={reread}
            title="Scope is recomputed every turn and never cached, so this asks the Control Plane again rather than redrawing what is already here."
          >
            Re-read the record
          </button>
        }
      />

      {view.loading && (
        <section className="card" aria-label="Loading the governance record">
          <Skeleton lines={5} label="Reading the governance record" />
        </section>
      )}

      {view.error && (
        <Degraded
          what="The governance record"
          detail={view.error}
          endpoint={view.endpoint ?? undefined}
        >
          <p className="muted">
            Neither the approval matrix nor the capability map is shown from memory while this
            is down: both are computed per request by the Control Plane, and a cached copy
            would be an authorization record that outlived the reason it was granted. The
            permanent boundary below is a product guarantee rather than a reading, so it stands
            whether or not this endpoint answers.
          </p>
        </Degraded>
      )}

      {/* ── identity ─────────────────────────────────────────────────────────
          First, because it qualifies everything under it. */}
      {v && (
        <section className={s.notice} aria-labelledby="identity-h">
          <div className={s.noticeTop}>
            <p className={s.noticeTitle} id="identity-h">
              This surface governs a demonstration persona
            </p>
            <span className={s.noticeKind}>{v.identity_kind}</span>
          </div>
          <p className={s.noticeBody}>{v.identity_note}</p>
          <p className={s.noticeFlag}>
            {v.is_production_identity
              ? 'This identity is marked as a production identity.'
              : 'is_production_identity is false, and it is not a setting. Turning this into authentication means replacing the Control Plane module deliberately, which is exactly the size of act it should be.'}
          </p>
        </section>
      )}

      {/* ── permanently refused ──────────────────────────────────────────────
          The signature of this screen. Rendered whether or not the endpoint answered, because
          the first item is a guarantee rather than a reading. */}
      <section className="card refusal" aria-labelledby="refused-h">
        <h2 id="refused-h">
          <IconHalt className={s.headIco} /> Permanently refused
        </h2>
        <p className="muted measure">
          None of these is a missing feature and none is cleared by seniority. There is no
          approver anywhere in the product who can sign one of them off, and no persona for
          whom the answer is different.
        </p>

        <Reveal as="ul" className={s.refusedList} runKey={v ? v.approval_matrix.length : 0}>
          <li className={s.refusedItem}>
            <p className={s.refusedName}>Issue a control command to plant equipment</p>
            <span className={s.refusedTag}>every persona, every phase</span>
            <p className={s.refusedWhy}>
              Synex reads the plant; it never commands it. Agents are read-only with respect to
              hardware control and no tool issues a control command to plant equipment, in any
              phase. A request to start, stop or set back a machine is refused inside the turn
              and sent to the plant control system, which is a separate authority with its own
              operators. This is the shape of the product, not a stage it has yet to reach.
            </p>
            <p className={s.guarantee}>
              A product guarantee rather than a reading — it holds whether or not this endpoint
              answers, so it carries no figure and none is shown.
            </p>
          </li>

          {(v?.approval_matrix ?? [])
            .filter((row) => row.requirement === NO_APPROVAL_CLEARS_IT)
            .map((row) => (
              <li className={s.refusedItem} key={row.risk}>
                <p className={s.refusedName}>
                  Anything the approval engine classes{' '}
                  <span className={s.riskName}>{row.risk}</span>
                </p>
                <span className={s.refusedTag}>{row.requirement}</span>
                <p className={s.refusedWhy}>{row.who}</p>
              </li>
            ))}
        </Reveal>
      </section>

      {/* ── the approval matrix ──────────────────────────────────────────── */}
      {v && (
        <section className="card" aria-labelledby="matrix-h">
          <h2 id="matrix-h">The approval matrix</h2>
          <p className="muted measure">
            Every row is the approval engine&rsquo;s own output against a probe action rather
            than a restatement of it, and the holders come from the same scope computation a
            live turn makes. A capability added to the Control Plane appears here without an
            edit, so the two cannot disagree.
          </p>

          <Reveal as="ul" className={s.matrix} runKey={v.approval_matrix.length}>
            {v.approval_matrix.map((row) => (
              <li className={s.matrixRow} key={row.risk}>
                <span className={s.riskName}>{row.risk}</span>
                <div className={s.matrixBody}>
                  <div className={s.reqLine}>
                    <span
                      className={s.reqPill}
                      data-refused={row.requirement === NO_APPROVAL_CLEARS_IT}
                    >
                      {row.requirement}
                    </span>
                    {row.required_capability && (
                      <span className={s.capChip}>{row.required_capability}</span>
                    )}
                    {row.holders.length > 0 && (
                      <>
                        <span className={s.chipLabel}>held by</span>
                        {row.holders.map((holder) => (
                          <span className={s.holder} key={holder}>
                            {holder}
                          </span>
                        ))}
                      </>
                    )}
                  </div>
                  <p className={s.who}>{row.who}</p>
                </div>
              </li>
            ))}
          </Reveal>
        </section>
      )}

      {/* ── capabilities, by persona ─────────────────────────────────────────
          A grid, not a column. See the note at the top of this file. */}
      {v && (
        <section className="card" aria-labelledby="caps-h">
          <h2 id="caps-h">Capabilities, by persona</h2>
          <p className="muted measure">{v.order_note}</p>

          <Reveal as="div" className="grid-cards" runKey={v.personas.length}>
            {v.personas.map((persona) => (
              <article className={s.personaCard} key={persona.persona}>
                <h3 className={s.personaName}>
                  {persona.display_name}
                  <span className={s.personaKey}>{persona.persona}</span>
                </h3>
                <ul className={s.capList}>
                  {capabilityColumns.map((capability) => {
                    const held = persona.capabilities.includes(capability);
                    return (
                      <li key={capability}>
                        <div className={s.capRow} data-held={held}>
                          <span>{capability}</span>
                          <span className={s.capMark}>
                            {held ? (
                              <>
                                <IconCheck className={s.capIco} />
                                held
                              </>
                            ) : (
                              'not held'
                            )}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </article>
            ))}
          </Reveal>
        </section>
      )}

      {/* ── the ordering evidence ────────────────────────────────────────────
          Computed by the back end rather than asserted, because the sentence was already
          written in the sibling implementation and did not hold. */}
      {v && (
        <section className="card" aria-labelledby="order-h">
          <h2 id="order-h">Is the order a ladder?</h2>
          <p className={s.verdict}>
            {v.ordering.forms_a_ladder
              ? 'These capability sets form a ladder.'
              : 'These capability sets do not form a ladder.'}
          </p>
          <p className="muted measure">{v.ordering.finding}</p>

          {v.ordering.incomparable_pairs.length > 0 && (
            <div className={s.pairGroup}>
              <p className={s.pairLabel}>
                Incomparable — each holds something the other does not
              </p>
              <Reveal
                as="ul"
                className={s.pairList}
                runKey={v.ordering.incomparable_pairs.length}
              >
                {v.ordering.incomparable_pairs.map((pair) => (
                  <li className={s.pair} key={pair.join('|')}>
                    {pair[0]}
                    <span className={s.pairJoin}>&harr;</span>
                    {pair[1]}
                  </li>
                ))}
              </Reveal>
            </div>
          )}

          {v.ordering.contained_pairs.length > 0 && (
            <div className={s.pairGroup}>
              <p className={s.pairLabel}>
                Contained — one set includes the other, which is set inclusion and not rank
              </p>
              <Reveal as="ul" className={s.pairList} runKey={v.ordering.contained_pairs.length}>
                {v.ordering.contained_pairs.map((pair) => (
                  <li className={s.pair} key={pair.join('|')}>
                    {pair[0]}
                    <span className={s.pairJoin}>&sub;</span>
                    {pair[1]}
                  </li>
                ))}
              </Reveal>
            </div>
          )}
        </section>
      )}

      {/* ── the policy version ───────────────────────────────────────────── */}
      {v && (
        <section className="card supporting measure" aria-labelledby="policy-h">
          <h2 id="policy-h">Policy version</h2>
          <p className="muted">{v.policy.statement}</p>
          <p className="muted">{v.policy.version_is_a_string}</p>
          {!v.policy.is_stated && (
            <p className="muted">
              No version is stated on this record, so a decision taken now cannot be traced to
              the rules that were in force when it was taken.
            </p>
          )}
        </section>
      )}

      {/* ── the trail ────────────────────────────────────────────────────────
          `G6`. Degraded independently of the record above: two endpoints, two failures, and a
          screen that showed one outage for both would be misreporting one of them. */}
      <section className="card" aria-labelledby="trail-h">
        <h2 id="trail-h">The trail</h2>

        {trail.loading && <Skeleton lines={4} label="Reading the audit trail" />}

        {trail.error && (
          <Degraded
            what="The audit trail"
            detail={trail.error}
            endpoint={trail.endpoint ?? undefined}
          />
        )}

        {trail.data && (
          <>
            <div className={s.trailTop}>
              <span className={s.trailCount}>
                <ValueChange value={String(trail.data.total)} figure="audit_rows" />
              </span>
              <span className={s.trailCountLabel}>
                rows recorded — one per request, including every refusal
              </span>
            </div>

            <p className={s.durability}>
              {trail.data.durable
                ? 'This sink is durable: the rows survive a restart of the process.'
                : 'This sink is not durable. The rows do not survive a restart, so the count above is what has been recorded since this process started rather than the whole history — stated rather than implied, because a trail that quietly forgets is worse than one that says it will.'}
            </p>

            {trail.data.rows.length === 0 ? (
              <EmptyState
                title="No rows in the trail"
                because="Nothing has been asked of this process since it started. Every request writes exactly one row, including refusals and blocked turns, so an empty trail means no request arrived — not that requests arrived and went unrecorded."
              />
            ) : (
              <>
                <p className="muted">
                  The most recent {trail.data.rows.length} of {trail.data.total}, newest first.
                </p>
                <div className="table-scroll">
                  <table className="data stackable">
                    <caption>
                      Persona, action, the state the turn ended in, and the policy version it
                      was decided under.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">At (UTC)</th>
                        <th scope="col">Persona</th>
                        <th scope="col">Action</th>
                        <th scope="col">Asset</th>
                        <th scope="col">State</th>
                        <th scope="col">Policy</th>
                        <th scope="col">Gates failed</th>
                      </tr>
                    </thead>
                    <Reveal as="tbody" runKey={trail.data.rows.length}>
                      {[...trail.data.rows].reverse().map((row) => (
                        <tr key={row.request_id}>
                          <td data-label="At (UTC)" className="mono">
                            {auditTime(row.at)}
                          </td>
                          <td data-label="Persona">{row.persona}</td>
                          <td data-label="Action" className="mono">
                            {row.action}
                          </td>
                          <td data-label="Asset">
                            {row.equipment_key ?? (
                              <span className="absent">not asset-scoped</span>
                            )}
                          </td>
                          <td data-label="State">
                            {isAnswerState(row.answer_state) ? (
                              <StateChip state={row.answer_state} className={s.trailState} />
                            ) : (
                              <span className="mono">{row.answer_state}</span>
                            )}
                          </td>
                          <td data-label="Policy" className="mono">
                            {row.policy_version}
                          </td>
                          <td data-label="Gates failed">
                            {row.gates_failed.length > 0 ? (
                              <span className={s.gates}>{row.gates_failed.join(', ')}</span>
                            ) : (
                              <span className="absent">none</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </Reveal>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </section>

      {/* ── what this surface cannot do ──────────────────────────────────────
          Last word, and named individually. Three distinct gaps read as a record; one vague
          disclaimer reads as a shrug. */}
      {v && v.not_available.length > 0 && (
        <section className="card supporting" aria-labelledby="gaps-h">
          {/* No refusal icon here, and the omission is deliberate: a gap is not a boundary.
              `IconHalt` says *stop and think*, and putting it on three open questions would
              dress an unanswered question as a decision the platform has taken. */}
          <h2 id="gaps-h">Not available from this surface</h2>
          <Reveal as="ul" className={s.refusedList} runKey={v.not_available.length}>
            {v.not_available.map((gap) => (
              <li className={s.gapCard} key={gap.source}>
                <div className={s.gapTop}>
                  <p className={s.gapName}>{gap.name}</p>
                  <span className={s.gapSource}>{gap.source}</span>
                </div>
                <p className={s.gapWhy}>{gap.reason}</p>
              </li>
            ))}
          </Reveal>
        </section>
      )}
    </>
  );
}

/**
 * Every capability any persona holds, so each card can show its absences as well as its
 * holdings — the evidence that these sets do not nest is only legible when both are on screen.
 *
 * Derived from the response rather than from a list held here: a capability added to the
 * Control Plane must appear without an edit to this file, or this page becomes a second source
 * of truth for the one fact that decides routing.
 */
function everyCapability(personas: PersonaRow[]): string[] {
  return Array.from(new Set(personas.flatMap((p) => p.capabilities))).sort();
}
