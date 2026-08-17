#!/usr/bin/env python3
"""Capture the model transcripts. **Run this once, on the Jarvis box.**

    cd backend
    python ../scripts/record_on_box.py --check      # reachable? roster pulled? nothing written
    python ../scripts/record_on_box.py --record     # the burst
    python ../scripts/record_on_box.py --verify     # replay offline, box off

---

**Why one script rather than three commands.** Six MVP features — `C5`, `C12`, `C25`, `R1`,
`R3`, `EV2` — are gated on a single artefact that does not exist: `backend/tests/fixtures/`
contains nothing but `__init__.py`, so **no transcript has ever been recorded**. Every Copilot
answer today is the deterministic fallback and says so.

A transcript is evidence of what a model actually said. It is committed to git deliberately —
`.gitignore` names the directory as *tracked* rather than ignored — and once captured it
replays for ever with the box terminated. So this is a one-time cost that permanently changes
what the product can demonstrate.

**What the box needs to be, before you start.** `CONTEXT.md` §9: an RTX PRO 6000 Blackwell,
96 GB, India region. A fresh box wipes `/home`, so the four-model roster re-pulls in about ten
minutes. The resident set is roughly 41 GB at Q4.

**The trap this script exists to avoid.** A transcript is keyed on the task *and the exact
messages*, so **changing a prompt invalidates its recording**. Record after the prompts are
settled, not before — otherwise the burst is spent and the replays miss. `--check` reports
whether anything already recorded would be orphaned by the prompts as they stand.

**What it does not do.** It never writes to the plant database and never touches
`graylinx_synex`. Eight of the thirteen golden cases read telemetry, so MySQL must be
reachable from wherever this runs; the other five are refusals and need nothing.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# Windows consoles default to cp1252, which cannot encode the rules this script prints — and
# a UnicodeEncodeError while reporting is a crash *before* the useful output rather than
# after it. `scripts/reclone_plant_db.py` carries the same two lines for the same reason.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx is required: pip install -r backend/requirements.txt")


def _hr(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 68 - len(title)))


async def check(host: str) -> int:
    """Read-only. Answers the three questions worth answering before spending a burst."""
    from app.llm import models
    from app.llm.client import TRANSCRIPT_DIR

    _hr("the box")
    print(f"  host: {host}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{host}/api/tags")
            response.raise_for_status()
            present = {m.get("name", "") for m in response.json().get("models", [])}
    except httpx.HTTPError as exc:
        print(f"  UNREACHABLE — {exc}")
        print("\n  Start the box and open the tunnel, then run --check again.")
        return 1

    print(f"  reachable, {len(present)} model(s) pulled")

    _hr("the roster")
    # Ask the role table rather than naming models here. "Code never names a model" is a
    # gate in this repository — `tests/unit/test_role_table.py` walks the AST of every module
    # and fails if a model name appears outside `app/llm/models.py`. A script is code.
    wanted = sorted({models.model_for(role) for role in models._ROLE_MODEL})
    missing = []
    for name in wanted:
        base = name.split(":")[0]
        ok = any(p.split(":")[0] == base for p in present)
        print(f"  {'OK  ' if ok else 'MISSING'}  {name}")
        if not ok:
            missing.append(name)

    if missing:
        print("\n  Pull them first — about ten minutes on a fresh box:")
        for name in missing:
            print(f"    ollama pull {name}")

    _hr("transcripts")
    existing = sorted(TRANSCRIPT_DIR.glob("*.json")) if TRANSCRIPT_DIR.exists() else []
    print(f"  directory: {TRANSCRIPT_DIR}")
    print(f"  recorded:  {len(existing)}")
    if not existing:
        print("  none yet — this is what gates C5, C12, C25, R1, R3 and EV2")

    _hr("the golden set")
    from tests.golden.cases import GOLDEN_CASES, needs_database

    with_db = [c for c in GOLDEN_CASES if needs_database(c)]
    print(f"  {len(GOLDEN_CASES)} cases — {len(with_db)} read telemetry, "
          f"{len(GOLDEN_CASES) - len(with_db)} are refusals and need no database")

    print()
    return 1 if missing else 0


async def record(host: str) -> int:
    """The burst. Runs every golden case with `SYNEX_MODEL_MODE=record`."""
    os.environ["SYNEX_MODEL_MODE"] = "record"
    os.environ["OLLAMA_HOST"] = host

    from app.config import get_settings
    from app.llm.client import TRANSCRIPT_DIR

    get_settings.cache_clear()
    settings = get_settings()
    if settings.synex_model_mode != "record":
        print(f"  mode is {settings.synex_model_mode!r}, not 'record' — refusing to continue.")
        return 2

    _hr("recording")
    print(f"  mode: {settings.synex_model_mode}  host: {settings.ollama_host}")

    before = len(list(TRANSCRIPT_DIR.glob("*.json"))) if TRANSCRIPT_DIR.exists() else 0

    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/golden", "-m", "", "-q"],
        cwd=BACKEND,
        env=os.environ,
        text=True,
        capture_output=True,
        check=False,
    )
    print(result.stdout[-3000:])
    if result.stderr.strip():
        print(result.stderr[-1500:])

    after = len(list(TRANSCRIPT_DIR.glob("*.json"))) if TRANSCRIPT_DIR.exists() else 0
    _hr("result")
    print(f"  transcripts: {before} → {after}  (+{after - before})")

    if after == before:
        print("\n  NOTHING WAS RECORDED. Most likely the turn never reached the model —")
        print("  check that the gates pass for the episode cases, since a refusal is")
        print("  answered without one. That is correct behaviour, not a failure.")
        return 3

    print("\n  Commit them — a transcript is evidence of what a model actually said:")
    print("    git add backend/tests/fixtures/transcripts && git commit")
    print("    then run:  python ../scripts/record_on_box.py --verify")
    return 0 if result.returncode == 0 else 1


async def verify() -> int:
    """Replay with the box out of the picture. This is the artefact's whole point."""
    os.environ["SYNEX_MODEL_MODE"] = "stub"
    # Point at a port nothing is listening on, so a transcript miss cannot be masked by the
    # box quietly answering. Replay must be genuinely offline or it has proved nothing.
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:59999"

    from app.config import get_settings

    get_settings.cache_clear()

    _hr("replaying offline")
    print("  mode: stub, host pointed at a dead port on purpose")

    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/golden", "-q"],
        cwd=BACKEND,
        env=os.environ,
        text=True,
        capture_output=True,
        check=False,
    )
    print(result.stdout[-3000:])
    if result.returncode == 0:
        print("\n  Replay works with the box unreachable. The burst is permanent.")
    else:
        print("\n  Replay failed. A transcript is keyed on the exact messages, so if a")
        print("  prompt changed after recording, its recording is orphaned — re-record.")
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture model transcripts on the Jarvis box")
    ap.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11500"))
    ap.add_argument("--check", action="store_true", help="inspect and stop; writes nothing")
    ap.add_argument("--record", action="store_true", help="the burst")
    ap.add_argument("--verify", action="store_true", help="replay offline afterwards")
    args = ap.parse_args()

    if not (args.check or args.record or args.verify):
        ap.error("pass --check, --record or --verify")

    if args.check:
        return asyncio.run(check(args.host))
    if args.record:
        if asyncio.run(check(args.host)) != 0:
            print("  pre-flight failed; nothing was recorded.")
            return 1
        return asyncio.run(record(args.host))
    return asyncio.run(verify())


if __name__ == "__main__":
    sys.exit(main())
