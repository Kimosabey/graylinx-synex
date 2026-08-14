import type { Metadata } from 'next';
import './globals.css';

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
      <body>{children}</body>
    </html>
  );
}
