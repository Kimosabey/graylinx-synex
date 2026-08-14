#!/usr/bin/env python3
"""Synex streaming contract gate.

Run from the repository root:

    python scripts/verify_sse_contract.py
    python scripts/verify_sse_contract.py --show   # print the contract and stop

Exit code 0 means the two halves of the product agree about the stream.

---

**The failure this exists to prevent** is the one the plan calls out for the `contracts` CI
job: *the web renders a field the API stopped sending*. On a streaming interface that
failure is silent. A frame the client no longer handles does not throw; it falls through a
`switch` and the turn simply renders less than it should — usually the evidence, the audit
badge, or the refusal, because those are the frames a happy-path change forgets.

`backend/app/agents/sse_contract.py` is the single source of truth. This script checks three
things against it, and says plainly which of them it was able to check.

**1 — The contract is structurally sound.** Ten distinct frames; the terminal, closing,
numeric and refusal frames are all members; refusal and error are distinct.

**2 — The code contract matches the settled document.** `CONTEXT.md` §7 names the six
answer states, and it is settled product truth — if code and document disagree, the code is
wrong. This check has teeth today, before a single frame is emitted, and it is the reason
this script is written in M0 rather than M1.5.

**3 — Both halves name only frames that exist**, and the web handles all of them. This is
pending until the emitter (M1.4) and the client (M1.5) land. The script reports it as
*pending* rather than *passed*: a check that silently passes because it found nothing to
check is how a gate rots.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "backend" / "app" / "agents" / "sse_contract.py"
WEB_DIR = ROOT / "apps" / "web"

EXCLUDE_DIRS = {"node_modules", ".next", "dist", "build", "__pycache__", ".venv"}


def load_contract():
    """Load the contract module directly, without importing the `app` package.

    Importing `app.agents` would drag in whatever else that package grows, and this gate
    must keep working when the graph it describes is half-written.
    """
    spec = importlib.util.spec_from_file_location("synex_sse_contract", CONTRACT_PATH)
    if not spec or not spec.loader:
        raise SystemExit(f"cannot load the contract at {CONTRACT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.pending: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def pend(self, msg: str) -> None:
        self.pending.append(msg)


# ── 1. structure ────────────────────────────────────────────────────────────────

def check_structure(c, rep: Report) -> None:
    frames = c.FRAMES

    if len(frames) != len(set(frames)):
        dupes = sorted({f for f in frames if list(frames).count(f) > 1})
        rep.error(f"duplicate frame(s) in FRAMES: {', '.join(dupes)}")

    for name, value in (
        ("TERMINAL_STATE_FRAME", c.TERMINAL_STATE_FRAME),
        ("STREAM_CLOSING_FRAME", c.STREAM_CLOSING_FRAME),
        ("NUMERIC_FRAME", c.NUMERIC_FRAME),
        ("REFUSAL_FRAME", c.REFUSAL_FRAME),
    ):
        if value not in frames:
            rep.error(f"{name} is {value!r}, which is not one of FRAMES")

    # D-015, as an assertion. A refusal rendered through the answer-text frame is the
    # softening CLAUDE.md 2.6 forbids, and it is exactly the shape the inherited
    # implementation had.
    if c.REFUSAL_FRAME == "token":
        rep.error(
            "the refusal frame is 'token' — D-015 exists because emitting NO_DIAGNOSIS as "
            "answer text leaves the interface unable to style a refusal differently"
        )
    if c.REFUSAL_FRAME == "error":
        rep.error(
            "the refusal frame is 'error' — a refusal is a correct outcome, not a failure. "
            "Conflating them makes an honest NO_DIAGNOSIS look like a bug"
        )
    if "NO_DIAGNOSIS" not in c.ANSWER_STATES:
        rep.error("NO_DIAGNOSIS is missing from ANSWER_STATES — CLAUDE.md 2.6")


# ── 2. the code contract against the settled document ───────────────────────────

def check_against_context(c, rep: Report) -> None:
    """`CONTEXT.md` §7 owns the answer states. Code that disagrees with it is wrong."""
    path = ROOT / "CONTEXT.md"
    if not path.exists():
        rep.error("CONTEXT.md is missing — it is the settled truth the contract answers to")
        return

    text = path.read_text(encoding="utf-8")
    m = re.search(r"## 7\. Answer contract(.*?)(?=\n## )", text, re.S)
    if not m:
        rep.error("CONTEXT.md has no '## 7. Answer contract' section to check against")
        return

    section = m.group(1)
    documented = re.findall(r"`([A-Z][A-Z_]{2,})`", section)
    stated = re.search(r"exactly one of (\w+) states", section)

    if not documented:
        rep.error("CONTEXT.md §7 names no answer states in backticks")
        return

    in_doc, in_code = set(documented), set(c.ANSWER_STATES)
    if in_doc != in_code:
        missing = sorted(in_doc - in_code)
        extra = sorted(in_code - in_doc)
        if missing:
            rep.error(
                f"ANSWER_STATES is missing {', '.join(missing)} — CONTEXT.md §7 names them"
            )
        if extra:
            rep.error(
                f"ANSWER_STATES adds {', '.join(extra)}, which CONTEXT.md §7 does not name"
            )

    # The prose says "six". If someone adds a seventh state to both the document and the
    # code but forgets the word, the document contradicts itself.
    words = {"four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
    if stated and stated.group(1) in words:
        n = words[stated.group(1)]
        if n != len(c.ANSWER_STATES):
            rep.error(
                f"CONTEXT.md §7 says 'exactly one of {stated.group(1)} states' but the "
                f"contract holds {len(c.ANSWER_STATES)}"
            )


# ── 3. both halves, once they exist ─────────────────────────────────────────────

# Backend emit sites: `yield frame("evidence", ...)`, `event="state"`, `"event": "done"`.
PY_FRAME_RE = re.compile(
    r"""(?:frame|emit|send)\(\s*["']([a-z_]+)["']"""
    r"""|event\s*[=:]\s*["']([a-z_]+)["']""",
)

# Web handler sites: `case 'evidence':`, `frame.type === "audit"`, `event === 'done'`.
TS_FRAME_RE = re.compile(
    r"""case\s+["']([a-z_]+)["']\s*:"""
    r"""|(?:type|event|name)\s*===\s*["']([a-z_]+)["']""",
)


def _walk(base: Path, suffixes: set[str]) -> list[Path]:
    out: list[Path] = []
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix in suffixes and not (EXCLUDE_DIRS & set(path.parts)):
            out.append(path)
    return out


def _tokens(paths: list[Path], pattern: re.Pattern[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for m in pattern.finditer(line):
                token = m.group(1) or m.group(2)
                if token:
                    found.setdefault(token, []).append(
                        f"{path.relative_to(ROOT)}:{n}".replace("\\", "/")
                    )
    return found


def check_emitters(c, rep: Report) -> None:
    """Every frame name the back end emits must be in the contract."""
    sources = [
        p for p in _walk(ROOT / "backend" / "app", {".py"})
        if p.name != "sse_contract.py"
    ]
    emitted = _tokens(sources, PY_FRAME_RE)
    if not emitted:
        rep.pend("no back-end emit site found yet — the graph arrives in M1.4")
        return
    for token, sites in sorted(emitted.items()):
        if token not in c.FRAMES:
            rep.error(f"back end emits frame {token!r}, which is not in the contract "
                      f"({sites[0]})")


def check_web(c, rep: Report) -> None:
    """The web must handle every frame, and name no frame that does not exist."""
    if not WEB_DIR.is_dir():
        rep.pend("apps/web does not exist yet — the client arrives in M1.5")
        return

    sources = _walk(WEB_DIR, {".ts", ".tsx"})
    handled = _tokens(sources, TS_FRAME_RE)
    if not handled:
        rep.pend("apps/web exists but handles no frame yet — the client arrives in M1.5")
        return

    for token, sites in sorted(handled.items()):
        if token not in c.FRAMES:
            rep.error(f"the web handles frame {token!r}, which is not in the contract "
                      f"({sites[0]})")

    unhandled = [f for f in c.FRAMES if f not in handled]
    if unhandled:
        rep.error(
            "the web handles no case for: " + ", ".join(unhandled) +
            " — an unhandled frame renders as nothing, silently"
        )


# ── entry point ─────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Synex streaming contract gate")
    ap.add_argument("--show", action="store_true", help="print the contract and stop")
    args = ap.parse_args()

    if not CONTRACT_PATH.exists():
        print(f"FAILED — the contract is missing: {CONTRACT_PATH.relative_to(ROOT)}")
        return 1

    c = load_contract()

    if args.show:
        print(f"{len(c.FRAMES)} frames:")
        for f in c.FRAMES:
            tags = [
                tag for tag, value in (
                    ("terminal", c.TERMINAL_STATE_FRAME),
                    ("closes", c.STREAM_CLOSING_FRAME),
                    ("numeric", c.NUMERIC_FRAME),
                    ("refusal", c.REFUSAL_FRAME),
                ) if value == f
            ]
            print(f"  {f:<14}{' · '.join(tags)}")
        print(f"\n{len(c.ANSWER_STATES)} answer states:")
        for s in c.ANSWER_STATES:
            print(f"  {s}")
        return 0

    rep = Report()
    check_structure(c, rep)
    check_against_context(c, rep)
    check_emitters(c, rep)
    check_web(c, rep)

    print(
        f"Contract holds {len(c.FRAMES)} frame(s) and {len(c.ANSWER_STATES)} answer state(s).\n"
    )

    if rep.pending:
        print(f"Pending ({len(rep.pending)}) — not yet checkable, and not counted as passed:")
        for p in rep.pending:
            print(f"  {p}")
        print()

    if rep.errors:
        print(f"FAILED — {len(rep.errors)} error(s):")
        for e in rep.errors:
            print(f"  {e}")
        return 1

    print("PASSED — the streaming contract is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
