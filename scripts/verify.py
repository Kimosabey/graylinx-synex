#!/usr/bin/env python3
"""Synex documentation compliance gate.

Run from the repository root:

    python scripts/verify.py
    python scripts/verify.py --strict     # also fail on TBD markers
    python scripts/verify.py --fix-names  # rewrite legacy product names in place

Exit code 0 means the repository is clean. Anything else means do not ship.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["docs/10-product", "docs/20-architecture", "mvp", "decisions", "brand"]
SCAN_ROOT_FILES = ["CLAUDE.md", "CONTEXT.md", "HANDOFF.md", "README.md"]

# Files that are allowed to mention legacy names, because they define the rule.
NAME_RULE_FILES = {"CLAUDE.md", "NAMING.md", "HANDOFF.md", "CONTEXT.md", "README.md", "verify.py"}

# Files that legitimately discuss TBD markers rather than containing unresolved ones.
STRICT_EXEMPT = {"CLAUDE.md", "README.md", "NAMING.md", "OPEN-QUESTIONS.md", "HANDOFF.md"}

# --------------------------------------------------------------------------
# Rule tables
# --------------------------------------------------------------------------

# Phrases produced by an old find-and-replace that damaged the document.
BANNED_PHRASES = {
    "checking that the work really worked": "verification",
    "checking that the answer is based on real information": "grounding",
    "where the data came from and how it was calculated": "lineage",
    "proof / supporting data": "evidence",
    "how important the equipment is": "criticality",
    "sending the issue to the right person/team": "escalation",
    "finding the likely problem": "diagnosis",
    "difference between expected and actual readings": "residuals",
    "based on real available information": "grounded",
    "access aread": "scoped",
    "limited mode": "degraded mode",
    "built around AI from the start": "AI-native",
    "testing and proof": "validation",
}

# Legacy product names. Key = regex, value = replacement.
LEGACY_NAMES = [
    (r"Graylinx Enterprise AI Platform", "Graylinx Synex"),
    (r"\bGEAP\b", "Synex"),
    (r"\bGraylinx AI Copilot\b", "Synex Copilot"),
    (r"\bAI Copilot\b", "Synex Copilot"),
    (r"\bthe chatbot\b", "the Copilot"),
    (r"\bChatbot / AI Copilot\b", "Synex Copilot"),
]

# Naming-law violations that have no safe automatic fix.
NAMING_VIOLATIONS = [
    (r"\bSynex AI\b", "Write 'Synex' — the AI is implied"),
    (r"\bSYNEX\b", "Synex is title case, never all caps"),
    (r"\bsynex\b(?![-_/.])", "Synex is title case in prose"),
    (r"Synex,? the HVAC", "Do not narrow Synex to HVAC — it is the first vertical, not the definition"),
]

# Statements that break the separation law.
SEPARATION_VIOLATIONS = [
    (r"(?i)\b(the )?(LLM|language model|copilot|ai)\b[^.\n]{0,60}\bdiagnos(e|es|ing)\b",
     "The language model never diagnoses — the FDD rules name the fault"),
    (r"(?i)\b(the )?(LLM|language model|copilot)\b[^.\n]{0,60}\b(grants?|decides?) (the )?permission",
     "The Control Plane grants permission, never the model"),
    (r"(?i)\bAI (decides|determines) (the )?priority",
     "Priority comes from a deterministic formula"),
]

# Two-letter prefixes MUST precede the single-letter class, or "RC1" matches
# "C1" and the register silently mis-counts instead of failing.
ID_PREFIX = r"(?:PL|RC|EV|[CRWAFKILVUSGE])"
# A sentence that *denies* the thing is correct, not a violation.
NEGATION_RE = re.compile(r"(?i)\b(never|not|cannot|can.t|no longer|does ?n.t|do ?n.t)\b")

FEATURE_ID_RE = re.compile(rf"\b{ID_PREFIX}\d{{1,2}}\b")
QUESTION_ID_RE = re.compile(r"\b([QNSD])(\d{1,3})\b")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, path: Path, line: int, msg: str) -> None:
        self.errors.append(f"{rel(path)}:{line}: {msg}")

    def warn(self, path: Path, line: int, msg: str) -> None:
        self.warnings.append(f"{rel(path)}:{line}: {msg}")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def targets() -> list[Path]:
    files: list[Path] = []
    for name in SCAN_ROOT_FILES:
        p = ROOT / name
        if p.exists():
            files.append(p)
    for d in SCAN_DIRS:
        base = ROOT / d
        if base.exists():
            files.extend(sorted(base.rglob("*.md")))
    return files


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_file(path: Path, text: str, rep: Report, strict: bool) -> None:
    exempt = path.name in NAME_RULE_FILES
    in_code = False

    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        low = line.lower()

        for phrase, correct in BANNED_PHRASES.items():
            if phrase in low and not exempt:
                rep.error(path, n, f"banned phrase {phrase!r} — use {correct!r}")

        if not exempt:
            for pattern, replacement in LEGACY_NAMES:
                if re.search(pattern, line):
                    rep.error(path, n, f"legacy name matching /{pattern}/ — use {replacement!r}")

        for pattern, why in NAMING_VIOLATIONS:
            if re.search(pattern, line) and not exempt:
                rep.error(path, n, f"naming law: {why}")

        for pattern, why in SEPARATION_VIOLATIONS:
            m = re.search(pattern, line)
            if m and not exempt and not NEGATION_RE.search(m.group(0)):
                rep.error(path, n, f"separation law: {why}")

        if strict and "TBD" in line and path.name not in STRICT_EXEMPT:
            if not re.search(r"TBD\s*\((?:[QNSD]\d+)\)", line):
                rep.error(path, n, "TBD without a question reference, e.g. TBD (Q1)")
            else:
                rep.warn(path, n, "unresolved TBD")


def check_register(rep: Report) -> tuple[set[str], int]:
    """The feature register is the single source of truth for feature IDs."""
    reg = ROOT / "mvp" / "FEATURE-REGISTER.md"
    if not reg.exists():
        rep.errors.append("mvp/FEATURE-REGISTER.md is missing — it is the source of truth")
        return set(), 0

    ids: set[str] = set()
    dupes: set[str] = set()
    in_cut: set[str] = set()
    count = 0
    for n, line in enumerate(reg.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(rf"\|\s*({ID_PREFIX}\d{{1,2}})\s*\|", line)
        if not m:
            continue
        fid = m.group(1)
        count += 1
        if fid in ids:
            dupes.add(fid)
            rep.error(reg, n, f"duplicate feature ID {fid}")
        ids.add(fid)
        if line.rstrip().rstrip("|").rsplit("|", 1)[-1].strip() == "MVP":
            in_cut.add(fid)

    body = reg.read_text(encoding="utf-8")
    m = re.search(r"\*\*Totals:\*\*\s*(\d+)\s*features", body)
    if m and int(m.group(1)) != count:
        rep.errors.append(
            f"mvp/FEATURE-REGISTER.md: stated total {m.group(1)} does not match "
            f"{count} rows found"
        )
    check_scope_tables(rep, in_cut, ids - in_cut)
    return ids, count


def check_id_references(files: list[Path], known: set[str], rep: Report) -> None:
    """Every feature ID used elsewhere must exist in the register."""
    if not known:
        return
    for path in files:
        if path.name == "FEATURE-REGISTER.md":
            continue
        in_code = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            # Only check inside explicit ID contexts to avoid false positives.
            for m in re.finditer(rf"(?:^|\s|\()({ID_PREFIX}\d{{1,2}})(?=[\s,.)\u2013-]|$)", line):
                fid = m.group(1)
                if fid not in known:
                    rep.warn(path, n, f"feature ID {fid} is not in the register")


def check_questions(rep: Report) -> None:
    q = ROOT / "decisions" / "OPEN-QUESTIONS.md"
    if not q.exists():
        rep.errors.append("decisions/OPEN-QUESTIONS.md is missing")
        return
    text = q.read_text(encoding="utf-8")
    if "## Closed" not in text:
        rep.error(q, 1, "missing a '## Closed' section — closed questions are archived, not deleted")


# Phrases that use a banned word generically rather than about this product.
# "the difference between a chatbot and a copilot" contrasts two categories; the
# naming law bans the word for our product, not from the language.
DOCX_EXEMPT_PHRASES = (
    "between a chatbot and a copilot",
)


def check_docx(rep: Report) -> int:
    """Scan the .docx sources for legacy names.

    This gate scanned *.md only, so the 78-page reference document was never
    checked — which is how 40 occurrences of "AI Copilot" and "Chatbot" survived
    in it unnoticed while every markdown file was clean. A .docx is a zip of XML:
    the body is word/document.xml, and the headers, footers and docProps (the
    title and keywords Word displays) all carry text too. All of them count.

    docs/90-archive/ is exempt. Superseded editions are kept precisely because
    they record what the document used to say.
    """
    import zipfile

    scanned = 0
    for path in sorted((ROOT / "docs").rglob("*.docx")):
        if "90-archive" in path.parts or path.name.startswith("~$"):
            continue
        scanned += 1
        try:
            with zipfile.ZipFile(path) as z:
                text = "".join(
                    z.read(n).decode("utf-8", "ignore")
                    for n in z.namelist() if n.endswith(".xml")
                )
        except (zipfile.BadZipFile, OSError) as exc:
            rep.errors.append(f"{rel(path)}: could not be read ({exc})")
            continue

        for phrase in DOCX_EXEMPT_PHRASES:
            text = text.replace(phrase, "")

        for pattern, replacement in LEGACY_NAMES:
            hits = len(re.findall(pattern, text))
            if hits:
                rep.errors.append(
                    f"{rel(path)}: {hits} occurrence(s) of a legacy name matching "
                    f"/{pattern}/ — use {replacement!r}")
        for pattern, why in NAMING_VIOLATIONS:
            hits = len(re.findall(pattern, text))
            if hits:
                rep.errors.append(f"{rel(path)}: {hits} occurrence(s) — naming law: {why}")
    return scanned


def check_structure(rep: Report) -> None:
    required = [
        "CLAUDE.md", "CONTEXT.md", "HANDOFF.md", "README.md",
        "brand/NAMING.md", "decisions/DECISIONS.md", "decisions/OPEN-QUESTIONS.md",
        "mvp/FEATURE-REGISTER.md", "mvp/MVP-SCOPE.md",
    ]
    for r in required:
        if not (ROOT / r).exists():
            rep.errors.append(f"required file missing: {r}")
    for d in ["docs/00-source", "docs/10-product", "docs/20-architecture", "docs/90-archive"]:
        if not (ROOT / d).is_dir():
            rep.errors.append(f"required directory missing: {d}")


# HANDOFF.md and DECISIONS.md are dated logs: a row that said "79 of 132" when it
# was written stays correct, and rewriting history to match today's total would
# destroy the traceability those files exist for.
COUNT_EXEMPT = {"HANDOFF.md", "decisions/DECISIONS.md"}
FEATURE_COUNT_RE = re.compile(r"\b(\d{2,3})\s+of\s+(?:the\s+)?(\d{2,3})\s+features\b")
BARE_COUNT_RE = re.compile(r"\b(?:is|are|holds)\s+(\d{2,3})\s+features\b")


def check_counts_html(total: int, rep: Report) -> None:
    """The pages quote the arithmetic too, and markdown-only scanning missed it.

    Section 3's heading read "What is in — 69 of 122" on the live site for three
    cuts, because check_counts walks *.md and a heading in HTML is neither markdown
    nor generated. Any "N of M" is checked here where M is plausibly a feature total;
    the pages also legitimately say "5 of 5" gates and "72 of 72" contrast pairs, so
    a small M is left alone.
    """
    if not total:
        return
    pat = re.compile(r"(\d{1,3})\s+of\s+(\d{2,3})\b")
    for name in ("mvp/MVP.html", "mvp/mock.html"):
        path = ROOT / name
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("*", "/*")):
                continue  # a comment may quote a number it is explaining
            for m in pat.finditer(line):
                num, denom = int(m.group(1)), int(m.group(2))
                if denom >= 100 and denom != total and num <= denom:
                    rep.error(path, n, f"{m.group(0)!r} — the register holds {total}. "
                                       f"Compute it from FEATURES instead of typing it")


def check_counts(files: list[Path], total: int, rep: Report) -> None:
    """Feature arithmetic is quoted in prose all over the repo; the register owns it.

    Only the denominator is checked. How many are in the cut is a proposal that a
    document may legitimately restate while it is being argued about; how many
    features exist is arithmetic, and two different answers to it means one is stale.
    """
    if not total:
        return
    for path in files:
        if rel(path).replace("\\", "/") in COUNT_EXEMPT:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in FEATURE_COUNT_RE.finditer(line):
                if int(m.group(2)) != total:
                    rep.error(path, n, f"{m.group(0)!r} — the register holds {total}")
            for m in BARE_COUNT_RE.finditer(line):
                if int(m.group(1)) != total:
                    rep.error(path, n, f"{m.group(0)!r} — the register holds {total}")


RANGE_RE = re.compile(rf"({ID_PREFIX})(\d{{1,2}})\s*[–—-]\s*(?:{ID_PREFIX})?(\d{{1,2}})")
SINGLE_RE = re.compile(rf"\b({ID_PREFIX}\d{{1,2}})\b")


def expand_ids(cell: str) -> set[str]:
    """Read an ID cell such as 'F1–F8, F10–F11, F14' into the set it denotes."""
    found: set[str] = set()
    rest = cell
    for m in RANGE_RE.finditer(cell):
        pfx, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        found |= {f"{pfx}{i}" for i in range(lo, hi + 1)}
        rest = rest.replace(m.group(0), " ")
    found |= set(SINGLE_RE.findall(rest))
    return found


def table_ids(block: str, column: int) -> set[str]:
    """Collect the IDs named in one column of a markdown table."""
    found: set[str] = set()
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) > column:
            found |= expand_ids(cells[column])
    return found


def check_scope_tables(rep: Report, in_cut: set[str], deferred: set[str]) -> None:
    """MVP-SCOPE.md names what is in and what is out; the register decides which.

    Both tables restate ID ranges, and a range is exactly the kind of thing that
    stops matching the register silently — the header count was corrected three
    times while the table beneath it was not. Checked as sets so a feature cannot
    be in neither table, or in both.
    """
    path = ROOT / "mvp" / "MVP-SCOPE.md"
    if not path.exists() or not in_cut:
        return
    text = path.read_text(encoding="utf-8")
    try:
        a = text.index("| Domain | In MVP | Why |")
        b = text.index("## What is out, and why")
        c = text.index("| Deferred | Reason |")
        d = text.index("## MVP acceptance criteria")
    except ValueError:
        rep.error(path, 1, "the 'what is in' / 'what is out' tables are not both present")
        return

    # Only the ID column counts. A reason may legitimately cite a feature that is in
    # the cut — "R1 already answers a question" is an argument for deferring R2, not
    # a claim that R1 is deferred — so reading the whole row would misread the prose.
    claimed_in = table_ids(text[a:b], column=1)
    claimed_out = table_ids(text[c:d], column=0)

    for label, claimed, actual in (("in the cut", claimed_in, in_cut),
                                   ("deferred", claimed_out, deferred)):
        missing = sorted(actual - claimed)
        extra = sorted(claimed - actual)
        if missing:
            rep.error(path, 1, f"{label} in the register but named by no row: "
                               f"{', '.join(missing)}")
        if extra:
            rep.error(path, 1, f"named as {label} but the register disagrees: "
                               f"{', '.join(extra)}")
    both = sorted(claimed_in & claimed_out)
    if both:
        rep.error(path, 1, f"named as both in and out: {', '.join(both)}")


def check_handoff_freshness(rep: Report) -> None:
    h = ROOT / "HANDOFF.md"
    if h.exists() and "## 7. Recent changes" not in h.read_text(encoding="utf-8"):
        rep.error(h, 1, "HANDOFF.md must keep a 'Recent changes' table")


def fix_names(files: list[Path]) -> int:
    changed = 0
    for path in files:
        if path.name in NAME_RULE_FILES:
            continue
        original = path.read_text(encoding="utf-8")
        text = original
        for pattern, replacement in LEGACY_NAMES:
            text = re.sub(pattern, replacement, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            print(f"  rewrote {rel(path)}")
            changed += 1
    return changed


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Synex documentation compliance gate")
    ap.add_argument("--strict", action="store_true", help="fail on unreferenced TBD markers")
    ap.add_argument("--fix-names", action="store_true", help="rewrite legacy product names in place")
    args = ap.parse_args()

    files = targets()
    if not files:
        print("No markdown found. Are you running this from the repository root?")
        return 2

    if args.fix_names:
        print("Rewriting legacy product names...")
        n = fix_names(files)
        print(f"{n} file(s) changed. Re-run without --fix-names to verify.\n")

    rep = Report()
    check_structure(rep)
    check_handoff_freshness(rep)
    check_questions(rep)
    known, count = check_register(rep)
    docx = check_docx(rep)

    for path in files:
        check_file(path, path.read_text(encoding="utf-8"), rep, args.strict)
    check_id_references(files, known, rep)
    check_counts(files, count, rep)
    check_counts_html(count, rep)

    print(f"Scanned {len(files)} markdown file(s) and {docx} source document(s). "
          f"Register holds {count} feature(s).\n")

    if rep.warnings:
        print(f"Warnings ({len(rep.warnings)}):")
        for w in rep.warnings[:40]:
            print(f"  {w}")
        if len(rep.warnings) > 40:
            print(f"  ... and {len(rep.warnings) - 40} more")
        print()

    if rep.errors:
        print(f"FAILED — {len(rep.errors)} error(s):")
        for e in rep.errors:
            print(f"  {e}")
        return 1

    print("PASSED — repository is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
