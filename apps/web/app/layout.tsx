import type { Metadata } from 'next';
import './globals.css';
import { Shell } from '@/components/Shell';

export const metadata: Metadata = {
  title: 'Graylinx Synex',
  description: 'Intelligent Operations, Connected by AI.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // `data-theme="light"` pins the default, exactly as `mvp/mock.html` does. The dark
    // tokens stay defined and reachable two ways — `[data-theme='dark']` for an explicit
    // switch, and `prefers-color-scheme` guarded by `:root:not([data-theme='light'])` — so
    // pinning light here disables the automatic swap without deleting dark support. A
    // demonstration should not change appearance because the room's laptop is set to dark.
    <html lang="en" data-theme="light">
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
