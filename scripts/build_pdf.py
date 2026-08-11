#!/usr/bin/env python3
"""Render a markdown document to PDF — the copy that actually gets sent.

    python scripts/build_pdf.py mvp/SME-REVIEW.md
    python scripts/build_pdf.py --all      # every markdown that already has a PDF
    python scripts/build_pdf.py --check    # exit 1 if any PDF is older than its source

The agenda goes to a refrigeration engineer as a PDF, and the markdown is what we
maintain. That is a drift pair, and it drifted: SME-REVIEW.pdf sat a day behind its
source, missing two whole sections that had been written in the meantime — including the
three eliminations the hour is meant to spend itself on.

There is no pandoc, LibreOffice or WeasyPrint on this machine, and adding one to send a
nine-page document would be disproportionate. Chromium is already here for the page
checks, and it prints PDF natively, so the path is markdown -> HTML -> Chromium. The
print CSS below is deliberately plain: this is a working document somebody writes answers
on, not a brochure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
body {
  font: 10.5pt/1.5 "Segoe UI", -apple-system, system-ui, sans-serif;
  color: #1F2933; margin: 0;
}
h1 { font-size: 19pt; color: #0020B0; margin: 0 0 .3em; line-height: 1.25; }
h2 {
  font-size: 14pt; color: #0020B0; margin: 1.6em 0 .5em;
  padding-bottom: .22em; border-bottom: 1.5px solid #0020B0;
  page-break-after: avoid;
}
h3 { font-size: 11.8pt; margin: 1.3em 0 .4em; page-break-after: avoid; }
h4 { font-size: 10.8pt; margin: 1em 0 .3em; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code {
  font-family: "Cascadia Mono", Consolas, monospace; font-size: .89em;
  background: #EEF1F8; padding: .08em .3em; border-radius: 3px;
}
table {
  border-collapse: collapse; width: 100%; margin: .7em 0; font-size: 9.3pt;
  page-break-inside: avoid;
}
th, td { border: 1px solid #C7D0E2; padding: 4.5px 7px; text-align: left; vertical-align: top; }
th { background: #EEF1F8; font-weight: 600; }
blockquote {
  margin: .7em 0; padding: .5em .85em; background: #F7F8FC;
  border-left: 3px solid #0020B0; font-size: 9.8pt;
}
/* An unanswered prompt should look like somewhere to write. */
blockquote:has(strong:first-child) { background: #FFFDF5; border-left-color: #B8860B; }
hr { border: 0; border-top: 1px solid #D8DEEC; margin: 1.5em 0; }
strong { color: #0F1B3D; }
ul, ol { padding-left: 1.35em; }
h2 + p, h3 + p { margin-top: .3em; }
"""


def to_html(md_path: Path) -> str:
    import markdown
    html = markdown.markdown(
        md_path.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )
    title = md_path.stem.replace("-", " ").title()
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{CSS}</style></head>"
            f"<body>{html}</body></html>")


def render(md_path: Path) -> Path:
    from playwright.sync_api import sync_playwright
    out = md_path.with_suffix(".pdf")
    tmp = md_path.with_suffix(".build.html")
    tmp.write_text(to_html(md_path), encoding="utf-8")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(tmp.resolve().as_uri())
            page.wait_for_timeout(350)
            page.pdf(path=str(out), format="A4", print_background=True,
                     display_header_footer=True,
                     header_template="<div></div>",
                     footer_template=(
                         "<div style='width:100%;font:8pt \"Segoe UI\",sans-serif;"
                         "color:#6B7280;padding:0 16mm;display:flex;"
                         "justify-content:space-between'>"
                         f"<span>Graylinx Synex &middot; {md_path.name}</span>"
                         "<span class='pageNumber'></span></div>"))
            browser.close()
    finally:
        tmp.unlink(missing_ok=True)
    return out


def pairs() -> list[Path]:
    """Markdown files that already have a PDF beside them — those are the sent ones."""
    return sorted(p for p in ROOT.rglob("*.md")
                  if p.with_suffix(".pdf").exists()
                  and "node_modules" not in p.parts and "site" not in p.parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render markdown to PDF via Chromium")
    ap.add_argument("path", nargs="?", help="markdown file to render")
    ap.add_argument("--all", action="store_true", help="re-render every md that has a PDF")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any PDF is older than its markdown")
    args = ap.parse_args()

    if args.check:
        stale = [p for p in pairs()
                 if p.stat().st_mtime > p.with_suffix(".pdf").stat().st_mtime]
        if stale:
            print(f"FAILED — {len(stale)} PDF(s) older than their source:")
            for p in stale:
                print(f"  {p.relative_to(ROOT)}  ->  {p.with_suffix('.pdf').name}")
            print("  Fix: python scripts/build_pdf.py --all")
            return 1
        print(f"All {len(pairs())} PDF(s) are current.")
        return 0

    targets = pairs() if args.all else ([ROOT / args.path] if args.path else [])
    if not targets:
        ap.error("give a path, or --all, or --check")
    for md in targets:
        if not md.exists():
            sys.exit(f"not found: {md}")
        out = render(md)
        kb = out.stat().st_size / 1024
        print(f"{md.relative_to(ROOT)}  ->  {out.name}  ({kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
