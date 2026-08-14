'use client';

/**
 * The shell — topbar, rail, and the content column. Shared by every surface.
 *
 * Extracted from the Copilot page when Reports arrived. Two surfaces with two hand-written
 * topbars is how a product grows two topbars, and the rail's job is to show what exists —
 * including the surfaces that do not yet, disabled with the milestone they arrive in.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useCallback, useState } from 'react';
import {
  IconChat,
  IconClipboard,
  IconGauge,
  IconShield,
  IconUsers,
} from '@/components/Icons';

const API = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8001';

const PERSONAS = [
  ['reliability_engineer', 'Reliability Engineer'],
  ['technician', 'Technician'],
  ['supervisor', 'Supervisor'],
  ['administrator', 'Administrator'],
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [persona, setPersona] = useState('reliability_engineer');

  const switchPersona = useCallback(async (key: string) => {
    await fetch(`${API}/api/v1/personas/${key}`, { method: 'POST', credentials: 'include' });
    setPersona(key);
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        {/* An `h1`, not a styled span. The page needs exactly one level-one heading for
            screen-reader navigation, and the product name is it — semantics are not a
            function of type size. */}
        <h1 className="brand">Graylinx Synex</h1>
        <span className="tagline">Intelligent Operations, Connected by AI.</span>
        <span className="spacer" />
        <span className="window" title="Real readings stop here; everything after is simulated">
          measured to 2026-06-23 11:50
        </span>
      </header>

      <nav className="rail" aria-label="Surfaces">
        <div className="railgroup">
          <h2>Copilot</h2>
          <Link
            href="/"
            className="navitem"
            aria-current={pathname === '/' ? 'page' : undefined}
          >
            <IconChat className="ico" />
            Ask
          </Link>
        </div>

        <div className="railgroup">
          <h2>Surfaces</h2>
          <Link
            href="/reports"
            className="navitem"
            aria-current={pathname === '/reports' ? 'page' : undefined}
          >
            <IconGauge className="ico" />
            Reports
          </Link>
          {/* Shown disabled rather than hidden. A product that conceals its unbuilt half is
              the thing this whole approach argues against, and the title names the
              milestone each one arrives in. */}
          <button className="navitem" disabled title="Arrives with M2">
            <IconClipboard className="ico" />
            Work orders
          </button>
          <button className="navitem" disabled title="Arrives with M3">
            <IconShield className="ico" />
            Verification
          </button>
        </div>

        <div className="railgroup">
          <h2>Persona</h2>
          {PERSONAS.map(([key, label]) => (
            <button
              key={key}
              className="navitem"
              aria-current={persona === key ? 'page' : undefined}
              onClick={() => switchPersona(key)}
            >
              <IconUsers className="ico" />
              {label}
            </button>
          ))}
        </div>
      </nav>

      <main className="content">{children}</main>
    </div>
  );
}
