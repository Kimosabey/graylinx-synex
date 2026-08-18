'use client';

/**
 * **The case queue — `RC1`–`RC18`, the surface `CONTEXT.md` §10d gives to Reliability and
 * Supervisor.**
 *
 * A case is the lifecycle between a named fault and a closed work order, and this is the list
 * of them. Every row is real: it comes from `/api/v1/episodes`, which returns the episodes the
 * trained model actually labelled inside the measured window. There is no fixture, no sample
 * row and no placeholder count anywhere on this page — when the back end is unreachable the
 * page says so with `<Degraded>` and shows nothing else, because a queue that renders invented
 * rows while the store is down is the exact dishonesty the product argues against.
 *
 * **Three rules shape the list itself.**
 *
 * *One case per equipment, fault and day.* Inherited constraint 35, and `RC8`'s idempotency —
 * the case id **is** the episode id, so a rescan cannot open a second.
 *
 * *Grouping is display-level only.* Constraint 12: the per-label cases are the trained model's
 * actual output, and rewriting them into one destroys the record of what it emitted. So the
 * equipment-day heading groups the view and never the data, and every label keeps its own row.
 *
 * *Nothing is ranked.* Constraint 36 warns against picking the longest-running label as
 * primary — the ambiguous class is usually both the longest-running and the least informative.
 * This list does not pick one at all: equipment-days run newest first, and inside a day the
 * rows are in the order they were first detected. That is chronology, not judgement.
 *
 * **Empty is never silent.** Inherited constraint 7 — `NULL` means *not diagnosed*, never
 * *healthy* — so an empty queue carries the sentence that says which.
 */

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Degraded, EmptyState, PageHeader, Skeleton, StateChip } from '@/components/Surface';
import { Pressable, Reveal } from '@/components/motion';
import { useApi } from '@/components/useApi';
import { ANSWER_STATES } from '@/lib/frames';
import {
  STATE_MEANING,
  clockOf,
  type EpisodeIndex,
  type EpisodeRow,
  type EquipmentIndex,
} from './api';
import styles from './case.module.css';

const ALL = 'all';

interface DayGroup {
  key: string;
  equipmentKey: string;
  day: string;
  rows: EpisodeRow[];
}

/**
 * One heading per equipment-day, newest first; the rows inside it in detection order.
 *
 * Deliberately not "most severe first" and not "longest-running first". Severity is never
 * taken from how far a residual sits outside its band — non-faults were measured to deviate
 * more than faults — and the longest-running label is usually the one that says least.
 */
function groupByEquipmentDay(rows: readonly EpisodeRow[]): DayGroup[] {
  const groups = new Map<string, DayGroup>();
  for (const row of rows) {
    const key = `${row.equipment_key}|${row.day}`;
    const found = groups.get(key);
    if (found) found.rows.push(row);
    else groups.set(key, { key, equipmentKey: row.equipment_key, day: row.day, rows: [row] });
  }
  const out = [...groups.values()];
  for (const group of out) {
    group.rows.sort((a, b) => a.first_slot.localeCompare(b.first_slot));
  }
  out.sort((a, b) => b.day.localeCompare(a.day) || a.equipmentKey.localeCompare(b.equipmentKey));
  return out;
}

export default function CaseQueuePage() {
  const episodes = useApi<EpisodeIndex>('/api/v1/episodes');
  const equipment = useApi<EquipmentIndex>('/api/v1/equipment');

  const [assetFilter, setAssetFilter] = useState<string>(ALL);
  const [labelFilter, setLabelFilter] = useState<string>(ALL);

  /** Display names as the back end holds them. Falls back to the key, never to a guess. */
  const displayName = useMemo(() => {
    const names = new Map<string, string>();
    for (const asset of equipment.data?.equipment ?? []) names.set(asset.key, asset.display_name);
    return (key: string) => names.get(key) ?? key.replace('_', ' ');
  }, [equipment.data]);

  const rows = useMemo(() => episodes.data?.episodes ?? [], [episodes.data]);

  const assets = useMemo(
    () => [...new Set(rows.map((row) => row.equipment_key))].sort(),
    [rows],
  );
  const labels = useMemo(() => [...new Set(rows.map((row) => row.fault_label))].sort(), [rows]);

  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          (assetFilter === ALL || row.equipment_key === assetFilter) &&
          (labelFilter === ALL || row.fault_label === labelFilter),
      ),
    [rows, assetFilter, labelFilter],
  );

  const groups = useMemo(() => groupByEquipmentDay(filtered), [filtered]);
  const filtering = assetFilter !== ALL || labelFilter !== ALL;

  return (
    <>
      <PageHeader
        title="Cases"
        lede="A case carries one fault on one machine from detection to a repair that has been proved. Graylinx Synex opens exactly one per equipment, fault and day, so a rescan cannot open a second."
        meta={
          episodes.data ? (
            <>
              {episodes.data.episode_count} cases · {episodes.data.equipment_days} equipment-days
              · measured window ends {episodes.data.window.end.replace('T', ' ')} ·{' '}
              {episodes.data.window.note}
            </>
          ) : (
            'Data window not read yet'
          )
        }
        actions={
          <button className="btn ghost" onClick={episodes.reload} disabled={episodes.loading}>
            {episodes.loading ? 'Reading…' : 'Reload'}
          </button>
        }
      />

      {episodes.error && (
        <Degraded
          what="The case queue"
          detail={episodes.error}
          endpoint={episodes.endpoint ?? undefined}
        >
          <p className="muted">
            No case is listed below, and that is because nothing was read — not because nothing
            is open. Start the Synex back end and reload.
          </p>
        </Degraded>
      )}

      {episodes.loading && (
        <section className="card" aria-label="Loading the case queue">
          <Skeleton lines={7} label="Reading the detected episodes" />
        </section>
      )}

      {episodes.data && (
        <>
          <section className="card sunken" aria-labelledby="filters">
            <h2 id="filters">Filter the queue</h2>
            <div className={styles.toolbar}>
              <div className={styles.filterGroup}>
                <span className={styles.filterLabel} id="asset-filter">
                  Equipment
                </span>
                <div className="row" role="group" aria-labelledby="asset-filter">
                  <button
                    className="chip"
                    aria-pressed={assetFilter === ALL}
                    onClick={() => setAssetFilter(ALL)}
                  >
                    All
                  </button>
                  {assets.map((key) => (
                    <button
                      key={key}
                      className="chip"
                      aria-pressed={assetFilter === key}
                      onClick={() => setAssetFilter(key)}
                    >
                      {displayName(key)}
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.filterGroup}>
                <label className={styles.filterLabel} htmlFor="label-filter">
                  Fault class
                </label>
                <select
                  id="label-filter"
                  className={styles.select}
                  value={labelFilter}
                  onChange={(event) => setLabelFilter(event.target.value)}
                >
                  <option value={ALL}>Every class</option>
                  {labels.map((label) => (
                    <option key={label} value={label}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {filtering && (
              <p className="muted">
                Showing {filtered.length} of {rows.length} cases. That is a filter, not a
                finding — nothing has been removed from the queue.
              </p>
            )}

            <p className="muted" style={{ marginBottom: 0 }}>
              {episodes.data.episode_count} cases against {episodes.data.equipment_days}{' '}
              equipment-days. One repair may explain several of them — a job raised per label is
              how one problem becomes several visits. Equipment-days run newest first and the
              rows inside each are in the order they were first detected; nothing here is ranked.
            </p>
          </section>

          {equipment.error && (
            <Degraded
              what="Equipment display names"
              detail={equipment.error}
              endpoint={equipment.endpoint ?? undefined}
            >
              <p className="muted">
                The queue below is unaffected — every case is still read from the episode list.
                Assets are named by their key until the register can be reached.
              </p>
            </Degraded>
          )}

          {rows.length === 0 ? (
            <EmptyState
              title="No case in this window"
              because="Nothing was diagnosed over the measured window — which is not the same as nothing being wrong. A NULL means not diagnosed, never healthy, and a window nobody scored looks exactly like a clean plant."
            />
          ) : groups.length === 0 ? (
            <EmptyState
              title="No case matches this filter"
              because={`The queue holds ${rows.length} case(s) and none of them matches ${
                assetFilter === ALL ? 'every asset' : displayName(assetFilter)
              } with ${
                labelFilter === ALL ? 'every class' : labelFilter
              }. Nothing has been removed from the queue — this is a filter, not a finding.`}
            >
              <div className="row" style={{ marginTop: 10 }}>
                <button
                  className="chip"
                  onClick={() => {
                    setAssetFilter(ALL);
                    setLabelFilter(ALL);
                  }}
                >
                  Clear the filter
                </button>
              </div>
            </EmptyState>
          ) : (
            groups.map((group) => (
              <div className={styles.dayGroup} key={group.key}>
                <div className={styles.dayHead}>
                  <h2 className={styles.dayTitle}>
                    {displayName(group.equipmentKey)} · {group.day}
                  </h2>
                  <span className={styles.dayCount}>
                    {group.rows.length} case(s) on this equipment-day
                  </span>
                </div>

                <Reveal as="ul" className={styles.caseList} runKey={`${group.key}:${filtered.length}`}>
                  {group.rows.map((row) => (
                    <li key={row.id}>
                      <Pressable
                        href={`/case/${encodeURIComponent(row.id)}`}
                        className="card"
                        ariaLabel={`Open the case for ${row.fault_label} on ${displayName(
                          row.equipment_key,
                        )}, ${row.day}`}
                      >
                        <span className={styles.caseRow}>
                          <span className={styles.caseLabel}>{row.fault_label}</span>
                          <span className={styles.caseMeta}>
                            {row.slot_count} slot(s) · {clockOf(row.first_slot)}–
                            {clockOf(row.last_slot)}
                          </span>
                        </span>
                      </Pressable>
                    </li>
                  ))}
                </Reveal>
              </div>
            ))
          )}
        </>
      )}

      {/* The answer contract, set out as a key. It states what each of the six words means and
          claims nothing about any case — the state a given case reached is on the case itself,
          read from its evidence pack. `NO_DIAGNOSIS` takes the refusal accent and never the
          stop colour, because it is a correct outcome rather than an error. */}
      <section className="card supporting" aria-labelledby="contract">
        <h2 id="contract">The answer contract — every turn ends in exactly one of six states</h2>
        <ul className={styles.stateKey}>
          {ANSWER_STATES.map((state) => (
            <li className={styles.stateKeyItem} key={state}>
              <span>
                <StateChip state={state} />
              </span>
              <p className={styles.stateKeyText}>{STATE_MEANING[state]}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="card supporting measure">
        <h2>What this queue is, and what it is not</h2>
        <p className="muted">
          Detection has no screen of its own: it runs, and what it produces arrives here as a
          case. A detector that fires into nowhere is worse than no detector, because the queue
          then reads as empty. Nothing on this surface writes — Synex’s own case store is not
          wired yet, so every case is shown at the state it was seeded in and none has been
          advanced, deferred or closed here.
        </p>
        <p className="muted">
          Synex Copilot is the other door to the same work.{' '}
          <Link href="/">Ask the Copilot about a machine</Link> and the case it opens is this
          one — the same evidence, the same gates, the same refusal when the data cannot decide.
        </p>
      </section>
    </>
  );
}
