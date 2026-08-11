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


SCOPE = ROOT / "mvp" / "MVP-SCOPE.md"
SCOPE_BEGIN = "<!-- BEGIN GENERATED — scripts/sync_mvp_html.py. Do not edit by hand. -->"
SCOPE_END = "<!-- END GENERATED -->"


def id_ranges(ids: list[str]) -> str:
    """'F1 F2 F3 F5' -> 'F1–F3, F5'. Ranges are how the scope document reads."""
    if not ids:
        return "— deferred whole"
    pfx = re.sub(r"\d", "", ids[0])
    nums = sorted(int(re.sub(r"\D", "", i)) for i in ids)
    out, start, prev = [], nums[0], nums[0]
    for v in nums[1:]:
        if v == prev + 1:
            prev = v
            continue
        out.append(f"{pfx}{start}" if start == prev else f"{pfx}{start}–{pfx}{prev}")
        start = prev = v
    out.append(f"{pfx}{start}" if start == prev else f"{pfx}{start}–{pfx}{prev}")
    return ", ".join(out)


def render_scope(rows: list[dict]) -> str:
    """The shape of the cut, as a table nobody has to keep in step by hand.

    The per-group reasons above it are prose and stay prose. This is the arithmetic,
    and the arithmetic belongs to the register.
    """
    used = sorted({r["d"] for r in rows}, key=lambda k: list(DOMAINS).index(k))
    by = {d: ([r["id"] for r in rows if r["d"] == d and r["ph"] == "MVP"],
              [r["id"] for r in rows if r["d"] == d and r["ph"] != "MVP"]) for d in used}
    # deepest first, so the shape of the cut is the shape of the table
    order = sorted(used, key=lambda d: (-len(by[d][0]), list(DOMAINS).index(d)))

    cut = sum(len(by[d][0]) for d in used)
    out = [SCOPE_BEGIN,
           "",
           "| Domain | In | Out | In the cut |",
           "|---|--:|--:|---|"]
    for d in order:
        inc, exc = by[d]
        label = DOMAINS[d]
        if exc and not inc:
            label = f"**{label}**"
        out.append(f"| {label} | {len(inc)} | {len(exc)} | {id_ranges(inc)} |")
    out.append(f"| **Total** | **{cut}** | **{len(rows) - cut}** | of {len(rows)} registered |")
    out.append("")

    whole_in = [DOMAINS[d] for d in order if by[d][0] and not by[d][1]]
    whole_out = [DOMAINS[d] for d in order if by[d][1] and not by[d][0]]
    p0 = sum(1 for r in rows if r["ph"] == "MVP" and r["p"] == "P0")
    ph2 = sum(1 for r in rows if r["ph"] == "Phase 2")
    ph3 = sum(1 for r in rows if r["ph"] == "Phase 3")

    out += [
        f"**{p0} of the {cut} are `P0`.** Almost nothing in the cut is optional; the "
        f"{cut - p0} that are not are there because the loop reads badly without them, "
        f"not because they are nice to have. Deferred work splits {ph2} to Phase 2 and "
        f"{ph3} to Phase 3.",
        "",
        f"**{len(whole_in)} domains are in whole** — {', '.join(whole_in)} — and "
        f"**{len(whole_out)} are out whole** — {', '.join(whole_out)}. That is the shape "
        "of the decision, not an accident of counting. A demonstrator has to close the "
        "loop *completely* and does not have to be *broad*, so the middle of the loop is "
        "taken entire while domains that are genuinely valuable, but not on it, are taken "
        "not at all.",
        "",
        SCOPE_END,
    ]
    return "\n".join(out)


def sync_scope(rows: list[dict], check: bool) -> int:
    if not SCOPE.exists():
        return 0
    text = SCOPE.read_text(encoding="utf-8")
    if SCOPE_BEGIN not in text or SCOPE_END not in text:
        print(f"note: {SCOPE.name} has no generated block; skipping")
        return 0
    start = text.index(SCOPE_BEGIN)
    end = text.index(SCOPE_END) + len(SCOPE_END)
    block = render_scope(rows)
    if text[start:end] == block:
        print(f"mvp/MVP-SCOPE.md is current.")
        return 0
    if check:
        print("FAILED — mvp/MVP-SCOPE.md's shape table is stale.")
        print("  Fix: python scripts/sync_mvp_html.py")
        return 1
    SCOPE.write_text(text[:start] + block + text[end:], encoding="utf-8")
    print("mvp/MVP-SCOPE.md updated — the shape table now matches the register.")
    return 0


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
        return sync_scope(rows, args.check)

    if args.check:
        print(f"FAILED — mvp/MVP.html is stale. The register holds {counted} features "
              f"({counted_mvp} in the cut); the page does not match.")
        print("  Fix: python scripts/sync_mvp_html.py")
        sync_scope(rows, True)
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
    return sync_scope(rows, args.check)


if __name__ == "__main__":
    sys.exit(main())
