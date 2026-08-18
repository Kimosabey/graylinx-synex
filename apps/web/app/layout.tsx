import type { Metadata } from 'next';
import { IBM_Plex_Mono, Rubik } from 'next/font/google';
import './globals.css';
import { Shell } from '@/components/Shell';

/**
 * **Rubik for the interface, IBM Plex Mono for anything measured.**
 *
 * Rubik is Harshan's choice and it suits the product: a geometric sans with slightly softened
 * terminals, which reads as approachable without becoming informal — the right register for a
 * tool a technician uses in a plant room rather than a trading desk. It ships as a **variable**
 * font across 300–900, so the whole weight range costs one file instead of four.
 *
 * **The mono is a deliberate pairing, not a leftover.** This interface is unusually dense in
 * measured values — residuals, bands, windows, locators, citations, fault labels — and every
 * one is set in `--mono`. Rubik has no monospace sibling, so the mono is chosen rather than
 * inherited: Plex Mono shares Rubik's humanist proportions and generous x-height, so a reading
 * sits beside a sentence without the jump in colour and size you get from pairing a geometric
 * sans with a terminal typeface. Tabular figures matter more here than family unity.
 *
 * **Self-hosted at build time by `next/font`** — no CDN request, no render-blocking stylesheet,
 * no layout shift from a late webfont, and it keeps working on a plant network that cannot
 * reach Google. That is why these are imports and not the `<link rel="preconnect">` tags
 * Google Fonts hands out: the tags would make every page wait on a third party.
 */
const sans = Rubik({
  subsets: ['latin'],
  // Variable across the full range, so weight is a continuum rather than four discrete files.
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-sans',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  // A template, so every surface names itself in the tab. Eight tabs all reading "Graylinx
  // Synex" is eight tabs a person cannot tell apart, and this product is used with several
  // open at once — a case beside the asset it belongs to beside the job raised from it.
  title: { default: 'Graylinx Synex', template: '%s · Synex' },
  description: 'Intelligent Operations, Connected by AI.',
  // `app/icon.png` and `app/apple-icon.png` are picked up by convention — the Graylinx mark
  // lifted from `mvp/mock.html`, so the tab, the home screen and the app bar are one identity.
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // `data-theme="light"` pins the default, exactly as `mvp/mock.html` does. The dark
    // tokens stay defined and reachable two ways — `[data-theme='dark']` for an explicit
    // switch, and `prefers-color-scheme` guarded by `:root:not([data-theme='light'])` — so
    // pinning light here disables the automatic swap without deleting dark support. A
    // demonstration should not change appearance because the room's laptop is set to dark.
    <html lang="en" data-theme="light" className={`${sans.variable} ${mono.variable}`}>
      {/* `suppressHydrationWarning` on <body> only.
       *
       * Browser extensions write attributes onto <body> before React hydrates — ColorZilla
       * adds `cz-shortcut-listen`, password managers and grammar tools add their own. React
       * sees the server HTML and the client DOM disagree and reports a hydration mismatch
       * that no application change can fix, because the application did not cause it.
       *
       * Scoped to this one element deliberately. Putting it higher, or on a component that
       * renders real content, would suppress genuine mismatches — the ones caused by
       * `Date.now()`, locale formatting or a `typeof window` branch, which are real bugs
       * worth hearing about. */}
      <body suppressHydrationWarning>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
