'use client';

/**
 * The shell — topbar, rail, and the content column. Shared by every surface.
 *
 * **Rebuilt 2026-08-17, and the reason is worth recording.** `CONTEXT.md` §10d names **eight
 * surfaces**, and the product had routes for two. Everything else happened as a card stacked
 * down the Copilot page: a case was not something you *opened*, it was a panel that appeared
 * below an answer, and a work order was a `div`. That is what made a working product read as
 * a demonstration — not the styling, the absence of anywhere to *be*.
 *
 * So the rail is now grouped by **who owns the surface**, because that is the real structure:
 * `CONTEXT.md` §10d assigns each one to a role, and constraint 25 insists the order is
 * *display* order rather than a capability ladder. A supervisor is not a senior technician —
 * ranking by seniority once sent a filter-drier restriction to a supervisor because one
 * incidental records question outranked three refrigeration measurements. So the groups are
 * headed by the work, never sorted by rank.
 *
 * **The persona switcher stays labelled as a demonstration.** `is_production_identity` is
 * hard-wired `False` (`Q41`), and a switcher that looked like sign-in would be the most
 * misleading control in the product.
 *
 * Below 640px the rail becomes a **bottom bar**, because that is where a thumb is. See
 * `globals.css` §responsive — the technician genuinely works on a phone in a plant room.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useCallback, useState } from 'react';
import { PageEnter } from '@/components/motion/PageEnter';
import { useRailCollapse } from '@/components/useRailCollapse';
import { SystemHealth } from '@/components/SystemHealth';
import { BuiltBy } from '@/components/BuiltBy';
import {
  IconAlert,
  IconChat,
  IconCheck,
  IconClipboard,
  IconGauge,
  IconReport,
  IconWrench,
  IconShield,
  IconUsers,
} from '@/components/Icons';

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

const PERSONAS = [
  ['reliability_engineer', 'Reliability Engineer'],
  ['technician', 'Technician'],
  ['supervisor', 'Supervisor'],
  ['administrator', 'Administrator'],
  ['analyst', 'Analyst'],
] as const;

/** The eight surfaces, grouped by the work rather than by rank. `CONTEXT.md` §10d. */
const GROUPS: ReadonlyArray<{
  heading: string;
  items: ReadonlyArray<{ href: string; label: string; short: string; Icon: typeof IconChat }>;
}> = [
  // **The mock's own grouping, restored.** `mvp/mock.html` is the designed shell and
  // `globals.css` already treats its `:root` as the source of truth; the rail had drifted to
  // four headings of its own invention — "Judge the fault", "Do the work", "Approve and
  // govern" — which read as a workflow the product does not actually enforce. ASK · WORK ·
  // LOOK · GOVERN is what was designed: one verb per group, and a reader picks by what they
  // are about to do rather than by which stage somebody decided they are in.
  {
    heading: 'Ask',
    items: [{ href: '/', label: 'Synex Copilot', short: 'Ask', Icon: IconChat }],
  },
  {
    heading: 'Work',
    items: [
      { href: '/case', label: 'Cases', short: 'Cases', Icon: IconCheck },
      { href: '/work-orders', label: 'Work orders', short: 'Work', Icon: IconWrench },
      { href: '/job', label: 'Job pack', short: 'Job', Icon: IconClipboard },
      { href: '/supervisor', label: 'Supervisor queue', short: 'Approve', Icon: IconShield },
    ],
  },
  {
    heading: 'Look',
    items: [
      { href: '/workspace', label: 'Reliability workspace', short: 'Queue', Icon: IconAlert },
      { href: '/asset/chiller_1', label: 'Asset', short: 'Asset', Icon: IconGauge },
      { href: '/reports', label: 'Reports', short: 'Reports', Icon: IconReport },
    ],
  },
  {
    heading: 'Govern',
    items: [{ href: '/admin', label: 'Scope & policy', short: 'Policy', Icon: IconUsers }],
  },
];

/**
 * What the bottom bar shows on a phone, per persona.
 *
 * **Max five, and the cap is not arbitrary** — it is the bottom-navigation limit in both
 * Material and Apple's guidance, and the reason is mechanical: eight 60px items on a 320px
 * screen is a 480px scroller, so half the surfaces sit off-screen behind a gesture nobody
 * is told about. A rail can hold eight because it scrolls vertically and is fully visible.
 *
 * So the phone shows the surfaces **that persona actually works on**. A technician standing
 * at a machine does not open the approval queue or the policy matrix; a supervisor approving
 * on a tablet does not open the job pack. Everything stays reachable at wider widths, where
 * the full rail returns — this narrows the bar, it does not remove a surface.
 */
const PHONE_BAR: Record<string, readonly string[]> = {
  technician: ['/job', '/case', '/'],
  supervisor: ['/supervisor', '/case', '/'],
  reliability_engineer: ['/workspace', '/asset/chiller_1', '/case', '/'],
  administrator: ['/admin', '/workspace', '/'],
  analyst: ['/reports', '/asset/chiller_1', '/'],
};

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [persona, setPersona] = useState('reliability_engineer');
  const { railRef, collapsed, ready, toggle } = useRailCollapse();

  const switchPersona = useCallback(async (key: string) => {
    await fetch(`${API}/api/v1/personas/${key}`, { method: 'POST', credentials: 'include' });
    setPersona(key);
    // A full reload rather than client state: `G1` recomputes scope every turn and never
    // inherits it, so a persona change must re-fetch every surface rather than re-label the
    // one on screen. Carrying the old data under a new name is exactly the leak G1 prevents.
    window.location.reload();
  }, []);

  const onPhoneBar = new Set(PHONE_BAR[persona] ?? PHONE_BAR.reliability_engineer);

  /** `/asset/chiller_1` should light up for `/asset/chiller_2` too. */
  const isCurrent = (href: string) =>
    href === '/' ? pathname === '/' : pathname.startsWith(href.split('/').slice(0, 2).join('/'));

  return (
    /* `data-ready` gates the CSS transition: the first paint must land at the stored width
       without animating into it, or the rail visibly slides open on every page load. */
    <div className="shell" data-rail={collapsed ? 'collapsed' : 'open'} data-ready={ready}>
      {/* Eight surfaces plus five personas is thirteen tab stops between the top of the page
          and the content, on every navigation. */}
      <a className="skip" href="#surface">
        Skip to the surface
      </a>

      <header className="topbar">
        {/* An `h1`, not a styled span. The page needs exactly one level-one heading for
            screen-reader navigation, and the product name is it — semantics are not a
            function of type size.

            **The accessible name is "Graylinx Synex" and the visual lockup is two halves.**
            The mark already draws the word "Graylinx", so setting it again in type would say
            the company's name twice on one bar — but the naming law governs what the page
            announces itself as, and a screen reader must not hear a bare "Synex". So the
            full name is carried by an `.sr-only` span and the two visual halves are
            `aria-hidden`: one accessible name, one visual lockup, no duplication in either.

            `.sr-only` is the clip-rect pattern, not `display: none` — which would take the
            name out of the accessibility tree as well and leave the `h1` empty. */}
        <h1 className="brand">
          <span className="sr-only">Graylinx Synex</span>
          <span className="lockup" aria-hidden="true">
            {/* The mark comes from `--logo`, which swaps per theme in `globals.css`. No file
                path here: a hardcoded one would show the dark mark on the dark bar. */}
            <span className="lockup-mark" />
            <span className="lockup-rule" />
            <span className="lockup-word">Synex</span>
          </span>
        </h1>

        <span className="tagline">Intelligent Operations, Connected by AI.</span>
        <span className="spacer" />

        {/* The platform's live state, and the data window read from it rather than typed
            in. Both stay on the phone where the tagline does not: the person most likely to
            read a figure as "now" is the technician standing at the machine. */}
        {/* **Identity sits in the bar, not in the navigation list.**
         *
         * It was a fifth `railgroup` — five buttons styled exactly like the eight surface links
         * beside them, doing something entirely different: not "go here" but "become someone
         * else", which reloads the whole application. Two controls that look alike and behave
         * differently is the mess; a rail answers *where do I go* and nothing else.
         *
         * Labelled a demonstration on the control itself, because `is_production_identity` is
         * hard-wired `False` (`Q41`) and a switcher that looked like sign-in would be the most
         * misleading control in the product. */}
        <label className="personaswitch">
          <span className="personaswitch-label">Viewing as</span>
          <select
            value={persona}
            onChange={(ev) => switchPersona(ev.target.value)}
            aria-label="Viewing as — a demonstration control, not sign-in"
          >
            {PERSONAS.map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <SystemHealth />
      </header>

      <nav className="rail" aria-label="Surfaces" ref={railRef}>
        <button
          type="button"
          className="railtoggle"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="rail-surfaces"
          /* The label says what pressing it DOES, not what the state is. "Collapse" when
             open, "Expand" when closed — a control named after its state reads as a status. */
          aria-label={collapsed ? 'Expand the surface rail' : 'Collapse the surface rail'}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          <span aria-hidden="true">{collapsed ? '›' : '‹'}</span>
        </button>

        <div id="rail-surfaces" className="railinner">
        {GROUPS.map((group) => (
          <div className="railgroup" key={group.heading}>
            <h2>{group.heading}</h2>
            {group.items.map(({ href, label, short, Icon }) => (
              <Link
                key={href}
                href={href}
                className="navitem"
                /* Hidden from the phone bar only — the CSS reads this, and every surface
                   returns at 640px and above. */
                data-phone={onPhoneBar.has(href) ? 'show' : 'hide'}
                aria-current={isCurrent(href) ? 'page' : undefined}
                /* Collapsed, this is an icon-only control. The accessible name and the
                   tooltip both stay, so the label leaves the screen and not the a11y tree. */
                aria-label={label}
                title={collapsed ? label : undefined}
              >
                <Icon className="ico" />
                {/* Two labels, one shown per breakpoint. The bottom bar has room for a word,
                    the rail has room for a name, and truncating with an ellipsis would hide
                    which surface you are about to open. */}
                <span className="long">{label}</span>
                <span className="short">{short}</span>
              </Link>
            ))}
          </div>
        ))}

        </div>
      </nav>

      {/* `PageEnter` is mounted here, once, rather than by each surface. Eight surfaces share
          one shell, so a hard cut between them makes every navigation look like a fresh page
          load — which is the opposite of what a persistent rail is for. Mounting it in the
          shell also means no surface can forget it and none can apply it twice.

          `tabIndex={-1}` so the skip link can move focus here; the shared focus ring uses
          `:focus-visible`, so a programmatic focus does not draw one. */}
      <main className="content" id="surface" tabIndex={-1}>
        <PageEnter>{children}</PageEnter>
        <BuiltBy />
      </main>
    </div>
  );
}
