#!/usr/bin/env python3
"""Build the Synex documents from markdown.

    python scripts/build_docs.py              # product + architecture -> docx
    python scripts/build_docs.py --pdf        # also render a PDF
    python scripts/build_docs.py --part product

Requires pandoc on PATH. PDF rendering additionally requires LibreOffice
(`soffice`). The build refuses to run if `verify.py` fails, so a document that
breaks the naming law or the separation law can never be produced.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"

PARTS = {
    "product": ("docs/10-product", "Graylinx_Synex_Product"),
    "architecture": ("docs/20-architecture", "Graylinx_Synex_Architecture"),
}

FRONT = ["CONTEXT.md"]


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(
            f"'{tool}' was not found on PATH.\n"
            f"  pandoc:      https://pandoc.org/installing.html\n"
            f"  LibreOffice: https://www.libreoffice.org/download/"
        )
    return path


def run_verify() -> None:
    print("Running the compliance gate first...")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify.py")], cwd=ROOT)
    if result.returncode != 0:
        sys.exit("\nBuild refused: verify.py did not pass. Fix the errors above.")
    print()


def collect(folder: Path) -> list[Path]:
    files = sorted(p for p in folder.glob("*.md") if p.name.lower() != "readme.md")
    if not files:
        print(f"  (nothing in {folder.relative_to(ROOT)} yet — skipping)")
    return files


def build_part(key: str, want_pdf: bool) -> Path | None:
    folder_name, out_stem = PARTS[key]
    folder = ROOT / folder_name
    if not folder.is_dir():
        print(f"  {folder_name} does not exist — skipping")
        return None

    chapters = collect(folder)
    if not chapters:
        return None

    BUILD.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    out = BUILD / f"{out_stem}_{stamp}.docx"

    pandoc = need("pandoc")
    cmd = [
        pandoc,
        "--from", "gfm",
        "--to", "docx",
        "--toc", "--toc-depth=2",
        "--metadata", f"title=Graylinx Synex — {key.title()}",
        "--metadata", "subtitle=Intelligent Operations, Connected by AI",
        "-o", str(out),
    ]
    reference = ROOT / "brand" / "reference.docx"
    if reference.exists():
        cmd += ["--reference-doc", str(reference)]
    else:
        print("  note: brand/reference.docx not found — pandoc defaults will be used.")
        print("        Create one with: pandoc -o brand/reference.docx --print-default-data-file reference.docx")
    cmd += [str(p) for p in chapters]

    print(f"Building {out.name} from {len(chapters)} chapter(s)...")
    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"  -> {out.relative_to(ROOT)}")

    if want_pdf:
        soffice = need("soffice")
        print("  rendering PDF...")
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(BUILD), str(out)],
            check=True, cwd=ROOT,
        )
        print(f"  -> {out.with_suffix('.pdf').relative_to(ROOT)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Synex documents from markdown")
    ap.add_argument("--pdf", action="store_true", help="also render a PDF")
    ap.add_argument("--part", choices=list(PARTS) + ["all"], default="all")
    ap.add_argument("--skip-verify", action="store_true",
                    help="build without the compliance gate (not for anything you send)")
    args = ap.parse_args()

    if not args.skip_verify:
        run_verify()
    else:
        print("WARNING: compliance gate skipped. Do not send this build to anyone.\n")

    keys = list(PARTS) if args.part == "all" else [args.part]
    built = [b for b in (build_part(k, args.pdf) for k in keys) if b]

    if not built:
        print("\nNothing was built. The chapter folders are still empty — see task T2 in HANDOFF.md.")
        return 0

    print(f"\nDone. {len(built)} document(s) in build/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
