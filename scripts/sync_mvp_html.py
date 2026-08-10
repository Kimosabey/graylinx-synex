#!/usr/bin/env python3
"""Regenerate the feature data inside mvp/MVP.html from the register.

    python scripts/sync_mvp_html.py           # rewrite the block, report what changed
    python scripts/sync_mvp_html.py --check   # verify only; exit 1 if the page is stale

`mvp/FEATURE-REGISTER.md` is the single source of truth for feature IDs
(CLAUDE.md hard rule 8). The explorer page needs the same rows as JavaScript, and
a hand-transcribed copy of 122 features is a drift waiting to happen — so it is
generated instead, between two markers, and nothing else in the page is touched.

Run this after any edit to the register. `--check` belongs in the same habit as
verify.py: if it fails, the page is telling readers something the register does
not say.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "mvp" / "FEATURE-REGISTER.md"
PAGE = ROOT / "mvp" / "MVP.html"

BEGIN = "/* BEGIN GENERATED — scripts/sync_mvp_html.py. Do not edit by hand. */"
END = "/* END GENERATED */"

# Must agree with ID_PREFIX in verify.py: two-letter prefixes first.
ID = r"(?:PL|RC|EV|[CRWAFKILVUSGE])\d{1,2}"

# Domain label per prefix. The register's own section headings, shortened for a
# menu row. A prefix missing here is an error, not a default.
DOMAINS = {
    "C": "Synex Copilot",
    "R": "Reports",
    "W": "Work Orders",
    "A": "Asset Intelligence",
    "F": "Reliability & FDD",
    "RC": "Case Resolution",
    "K": "Knowledge",
    "PL": "Planning",
    "I": "Inventory",
    "L": "Alerts",
    "V": "Verification",
    "E": "Energy & Cost",
    "EV": "Evaluation",
    "U": "Roles",
    "S": "Safety",
    "G": "Control Plane",
}


def prefix_of(fid: str) -> str:
    m = re.match(r"(PL|RC|EV|[CRWAFKILVUSGE])", fid)
    assert m, f"unparseable feature ID: {fid}"
    return m.group(1)


def split_engine(cell: str) -> list[str]:
    """`LLM + SW` -> ['LLM', 'SW'], stripping the register's backticks."""
    return [p.strip() for p in cell.replace("`", "").split("+") if p.strip()]


def read_register() -> list[dict]:
    rows: list[dict] = []
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 7 or not re.fullmatch(ID, cells[0]):
            continue
        fid, name, does, user, engine, pri, phase = cells
        rows.append({
            "id": fid,
            "d": prefix_of(fid),
            "n": name,
            "w": does,
            "u": user,
            "e": split_engine(engine),
            "p": pri,
            "ph": phase,
        })
    return rows


def stated_totals() -> tuple[int, int]:
    body = REGISTER.read_text(encoding="utf-8")
    m = re.search(r"\*\*Totals:\*\*\s*(\d+)\s*features,\s*of which\s*(\d+)", body)
    if not m:
        sys.exit("mvp/FEATURE-REGISTER.md: could not find the Totals line")
    return int(m.group(1)), int(m.group(2))


def render(rows: list[dict]) -> str:
    used = sorted({r["d"] for r in rows}, key=lambda k: list(DOMAINS).index(k))
    missing = [d for d in used if d not in DOMAINS]
    if missing:
        sys.exit(f"no domain label for prefix(es): {missing} — add them to this script")

    out = [BEGIN,
           f"/* {len(rows)} features from mvp/FEATURE-REGISTER.md,",
           f"   {sum(1 for r in rows if r['ph'] == 'MVP')} of them in the proposed MVP cut. */",
           "const DOMAINS = {"]
    out += [f"  {d}:{json.dumps(DOMAINS[d])}," for d in used]
    out.append("};")
    out.append("")
    out.append("const FEATURES = [")
    for r in rows:
        out.append(
            f"  {{id:{json.dumps(r['id'])}, d:{json.dumps(r['d'])}, "
            f"n:{json.dumps(r['n'])},"
        )
        out.append(
            f"   w:{json.dumps(r['w'])}, u:{json.dumps(r['u'])}, "
            f"e:{json.dumps(r['e'])}, p:{json.dumps(r['p'])}, ph:{json.dumps(r['ph'])}}},"
        )
    out.append("];")
    out.append(END)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync mvp/MVP.html from the register")
    ap.add_argument("--check", action="store_true",
                    help="verify only; exit 1 if the page is stale")
    args = ap.parse_args()

    rows = read_register()
    total, mvp = stated_totals()
    counted, counted_mvp = len(rows), sum(1 for r in rows if r["ph"] == "MVP")

    if counted != total or counted_mvp != mvp:
        sys.exit(f"register disagrees with itself: Totals says {total} features / {mvp} "
                 f"in the cut, rows give {counted} / {counted_mvp}")

    page = PAGE.read_text(encoding="utf-8")
    if BEGIN not in page or END not in page:
        sys.exit(f"{PAGE.name}: generated block markers are missing — "
                 f"cannot sync without them")

    start = page.index(BEGIN)
    end = page.index(END) + len(END)
    block = render(rows)

    if page[start:end] == block:
        print(f"mvp/MVP.html is current — {counted} features, {counted_mvp} in the cut.")
        return 0

    if args.check:
        print(f"FAILED — mvp/MVP.html is stale. The register holds {counted} features "
              f"({counted_mvp} in the cut); the page does not match.")
        print("  Fix: python scripts/sync_mvp_html.py")
        return 1

    old = re.findall(rf"id:\"({ID})\"", page[start:end])
    PAGE.write_text(page[:start] + block + page[end:], encoding="utf-8")
    added = [r["id"] for r in rows if r["id"] not in old]
    removed = [i for i in old if i not in {r["id"] for r in rows}]
    print(f"mvp/MVP.html updated — {counted} features, {counted_mvp} in the cut.")
    if added:
        print(f"  added:   {', '.join(added)}")
    if removed:
        print(f"  removed: {', '.join(removed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
