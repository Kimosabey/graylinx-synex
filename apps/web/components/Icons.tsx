/**
 * Icons — SVG, never emoji.
 *
 * Emoji are font-dependent, render differently on every platform, and cannot be themed by a
 * design token. A check mark that is green on one machine and black on another is not a
 * status indicator. These are stroked at a consistent 1.7 and inherit `currentColor`, so a
 * single icon works in both themes and in every semantic colour.
 *
 * Each is `aria-hidden`: the meaning is always carried by adjacent text as well, because
 * colour and shape are never the only signal.
 */

type Props = { className?: string; style?: React.CSSProperties };

const base = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: false,
};

export const IconCheck = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

/** Used for a soft failure and for degraded mode — informative, not alarming. */
export const IconAlert = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5M12 16.2v.3" />
  </svg>
);

/** The refusal. A hand, not a cross — this is "stop and think", not "something broke". */
export const IconHalt = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9 9h6v6H9z" />
  </svg>
);

export const IconChat = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z" />
  </svg>
);

export const IconGauge = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM13.4 10.6 19 5" />
    <path d="M4.2 18a9 9 0 1 1 15.6 0" />
  </svg>
);

/** Reports. A sheet with a bar series on it — distinct from `IconGauge`, which is a dial and
 *  belongs to the asset. The two shared a glyph until 2026-08-18, which made the collapsed rail
 *  ambiguous: collapsed, the icon is the whole of the label. */
export const IconReport = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M6.5 3.5h11A1.5 1.5 0 0 1 19 5v14a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 19V5a1.5 1.5 0 0 1 1.5-1.5z" />
    <path d="M9 16v-3M12 16v-6M15 16v-4" />
  </svg>
);

/** Work orders. A spanner — the job itself, distinct from the clipboard that is the job *pack*
 *  a technician carries and from the dial that belongs to the asset. Eight destinations need
 *  eight glyphs: collapsed, the icon is the whole of the label. */
export const IconWrench = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M15.8 6.2a3.6 3.6 0 0 0-4.9 4.2l-6 6a1.6 1.6 0 0 0 2.3 2.3l6-6a3.6 3.6 0 0 0 4.2-4.9l-2.2 2.2-2.1-.5-.5-2.1z" />
  </svg>
);

export const IconClipboard = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M9 4h6v3H9zM8 5.5H6.5A1.5 1.5 0 0 0 5 7v12a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 19V7a1.5 1.5 0 0 0-1.5-1.5H16" />
  </svg>
);

export const IconShield = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <path d="M12 3l7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6z" />
  </svg>
);

export const IconUsers = ({ className, style }: Props) => (
  <svg {...base} className={className} style={style}>
    <circle cx="9" cy="8" r="3" />
    <path d="M3.5 19a5.5 5.5 0 0 1 11 0M16 5.2a3 3 0 0 1 0 5.6M17 19a5.5 5.5 0 0 0-2-4.3" />
  </svg>
);
