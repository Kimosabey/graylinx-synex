'use client';

/**
 * One residual over one day, drawn against **that asset's own healthy band**.
 *
 * This chart is `F15` made visible, and it is the single most convincing thing on the
 * screen. Chiller 1's current residual has a healthy median of −25.645 and a band of
 * [−38.677, −12.613] — a band that never approaches zero. Plotted against zero, ordinary
 * running looks like a catastrophic excursion. Plotted against its own band, the same
 * numbers read correctly, and the reader does not have to be *told* that "high" is
 * per-asset; they can see it.
 *
 * **Form.** Trend over time against a reference range → a line with a band behind it. Not
 * diverging, despite being "above/below a baseline": above the band and below the band are
 * both abnormal and the middle is normal, which is a status question, not a polarity one.
 *
 * **Colour, and what carries meaning.** One series, so no legend box — the caption names it.
 * The band is a recessive surface tint, not a series colour. Out-of-band points take the
 * reserved status colour, and colour is **never the only signal**: the band itself shows the
 * separation, and the extreme point is enlarged, ringed against the surface and directly
 * labelled.
 *
 * Marks stay thin, and size is deliberately *not* used to flag out-of-band. On chiller 1
 * every reading is out of band, so enlarging all 113 emphasises nothing and reads as a wall
 * of noise — the first version of this chart did exactly that. Emphasis is spent on the one
 * point worth pointing at.
 *
 * **Nothing here formats a number.** Axis ticks round to integers and path coordinates are
 * raw floats; no number-formatting API is called anywhere in this file, because `FigureView`
 * is the only component allowed to render a figure and an exception list is how that rule
 * stops being one. The web contract test enforces it — and it caught this file twice: once
 * for real, and once for naming the banned APIs in this very paragraph.
 *
 * Palette validated with the data-viz validator in both modes. Every check that applies to
 * a one-series-plus-status chart passes: CVD separation ΔE 27.0 protan (light) and 16.9
 * (dark), normal-vision floor 33.4 / 21.6, contrast ≥ 3:1 against both surfaces. The two
 * FAILs it reports are the categorical lightness-band and chroma-floor rules, and the
 * validator's own scope note excludes a lone status colour from those.
 *
 * **A NULL is not a gap.** `compressor_power_residual` is NULL in all 21,534 rows, and a
 * line that simply skips a point reads as "nothing to report here". The count is stated
 * beneath the plot instead — inherited constraint 7, in a chart.
 */

import { useMemo, useState } from 'react';

export interface SeriesPoint {
  t: string;
  v: number | null;
  label: string | null;
}

export interface SeriesBand {
  median: number;
  lower: number;
  upper: number;
}

interface Props {
  points: SeriesPoint[];
  band: SeriesBand | null;
  bandAbsentReason: string | null;
  residual: string;
  equipment: string;
  nullCount: number;
}

const W = 720;
const H = 220;
const PAD = { top: 14, right: 16, bottom: 26, left: 52 };

export function ResidualChart({
  points,
  band,
  bandAbsentReason,
  residual,
  equipment,
  nullCount,
}: Props) {
  const [hover, setHover] = useState<number | null>(null);

  const real = useMemo(() => points.filter((p) => p.v !== null), [points]);

  const scale = useMemo(() => {
    if (real.length === 0) return null;
    const values = real.map((p) => p.v as number);
    // The band is part of the domain even where no reading reaches it — otherwise a series
    // sitting entirely inside its band would render with the band cropped off-screen, and
    // the one comparison the chart exists to make would be invisible.
    const candidates = band
      ? [...values, band.lower, band.upper, band.median]
      : values;
    const lo = Math.min(...candidates);
    const hi = Math.max(...candidates);
    const pad = (hi - lo) * 0.12 || 1;
    return { lo: lo - pad, hi: hi + pad };
  }, [real, band]);

  if (!scale) {
    return (
      <p className="muted">
        No readings for {residual} on this day — nothing to plot, which is a statement
        rather than an empty chart.
      </p>
    );
  }

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (points.length <= 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
  const y = (v: number) => PAD.top + plotH - ((v - scale.lo) / (scale.hi - scale.lo)) * plotH;

  const outOfBand = (v: number) => (band ? v > band.upper || v < band.lower : false);

  // Broken into runs so a NULL leaves a real discontinuity in the path rather than a
  // straight line drawn *through* a slot where nothing was measured.
  const runs: string[] = [];
  let current: string[] = [];
  points.forEach((p, i) => {
    if (p.v === null) {
      if (current.length) runs.push(current.join(' '));
      current = [];
      return;
    }
    current.push(`${current.length ? 'L' : 'M'}${x(i)},${y(p.v)}`);
  });
  if (current.length) runs.push(current.join(' '));

  const extreme = real.reduce(
    (worst, p) =>
      band && Math.abs((p.v as number) - band.median) > Math.abs((worst.v as number) - band.median)
        ? p
        : worst,
    real[0],
  );
  const extremeIndex = points.indexOf(extreme);

  const ticks = [scale.hi, (scale.hi + scale.lo) / 2, scale.lo];
  const hovered = hover !== null ? points[hover] : null;

  return (
    <figure className="chart">
      <figcaption>
        {residual} on {equipment} — plotted against this asset&apos;s own healthy band, not
        against zero.
      </figcaption>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        role="img"
        aria-label={
          `${residual} for ${equipment} over ${points.length} slots. ` +
          (band
            ? `Healthy band ${band.lower} to ${band.upper}, median ${band.median}. ` +
              `${real.filter((p) => outOfBand(p.v as number)).length} of ${real.length} readings sit outside it.`
            : 'No reference band is fitted for this asset, so nothing can be judged.')
        }
        onMouseLeave={() => setHover(null)}
      >
        {/* The band. A recessive surface tint — it is context, not a series. */}
        {band && (
          <>
            <rect
              x={PAD.left}
              y={y(band.upper)}
              width={plotW}
              height={Math.max(1, y(band.lower) - y(band.upper))}
              className="chart-band"
            />
            {/* Solid hairline, never dashed — dashing reads as "projection". */}
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(band.median)}
              y2={y(band.median)}
              className="chart-median"
            />
            <text x={W - PAD.right} y={y(band.median) - 5} className="chart-annot" textAnchor="end">
              healthy median {band.median}
            </text>
          </>
        )}

        {/* Axis: one hairline, one shade off the surface. */}
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={H - PAD.bottom} className="chart-axis" />
        {ticks.map((t) => (
          <text key={t} x={PAD.left - 8} y={y(t) + 4} className="chart-tick" textAnchor="end">
            {Math.round(t)}
          </text>
        ))}

        {runs.map((d, i) => (
          <path key={i} d={d} className="chart-line" />
        ))}

        {points.map((p, i) =>
          p.v === null ? null : (
            <g key={p.t}>
              {/* Thin marks throughout. Size is **not** used to flag out-of-band, because on
                  chiller 1 every reading is out of band — emphasising all 113 emphasises
                  nothing and reads as a wall of noise. The band does that work: the reader
                  sees the whole series sitting clear of it. Size and a surface ring are
                  spent on the extreme alone, which is the one point worth pointing at. */}
              <circle
                cx={x(i)}
                cy={y(p.v)}
                r={i === extremeIndex ? 5 : 2.5}
                className={
                  (outOfBand(p.v) ? 'chart-dot out' : 'chart-dot') +
                  (i === extremeIndex ? ' extreme' : '')
                }
              />
              {/* Hit target larger than the mark. */}
              <circle
                cx={x(i)}
                cy={y(p.v)}
                r={12}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
              />
            </g>
          ),
        )}

        {/* Direct-label the extreme only. A number on every point is chaos and goes unread. */}
        {band && extremeIndex >= 0 && extreme.v !== null && outOfBand(extreme.v) && (
          <text
            x={x(extremeIndex)}
            y={y(extreme.v) - 11}
            className="chart-annot out"
            textAnchor="middle"
          >
            {extreme.v}
          </text>
        )}

        {hovered && hovered.v !== null && (
          <g pointerEvents="none">
            <line
              x1={x(hover as number)}
              x2={x(hover as number)}
              y1={PAD.top}
              y2={H - PAD.bottom}
              className="chart-crosshair"
            />
            <text
              x={Math.min(x(hover as number) + 8, W - 150)}
              y={PAD.top + 12}
              className="chart-annot"
            >
              {hovered.t.slice(11, 16)} · {hovered.v}
              {outOfBand(hovered.v) ? ' · outside the band' : ' · inside the band'}
            </text>
          </g>
        )}
      </svg>

      {/* A NULL is a statement, not a gap in a line. */}
      {nullCount > 0 && (
        <p className="muted">
          {nullCount} of {points.length} slots have no value for this residual — shown as
          breaks in the line, not as zero.
        </p>
      )}
      {bandAbsentReason && <p className="muted">{bandAbsentReason}</p>}
      {band && (
        <p className="muted">
          Healthy band {band.lower} to {band.upper}.{' '}
          {real.filter((p) => outOfBand(p.v as number)).length} of {real.length} readings sit
          outside it — <strong>for this machine</strong>, which is not the same question as
          how far they sit from zero.
        </p>
      )}
    </figure>
  );
}
