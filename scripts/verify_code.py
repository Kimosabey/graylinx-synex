#!/usr/bin/env python3
"""Synex source compliance gate — the naming law, over code rather than prose.

Run from the repository root:

    python scripts/verify_code.py
    python scripts/verify_code.py --list    # print what would be scanned, and stop

Exit code 0 means the source is clean. Anything else means do not ship.

---

**Why this is a second script rather than three more directories in `verify.py`.**

The plan said to add `apps` and `services` to `SCAN_DIRS`. Trying it shows why that is
wrong: `verify.py` runs *seven* families of check, and only two of them mean anything
against source. The other five either cannot fire or fire constantly.

Two rules in particular turn a clean tree red, and both are correct rules for prose:

- **The lowercase-`synex` rule.** `NAMING_VIOLATIONS` bans a lowercase `synex` in a
  sentence, with a lookahead excusing `synex-` and `synex/` so that a path or a slug
  survives. Source is full of forms that lookahead does not cover — `graylinx_synex`
  is the database name, and it is followed by a space or a quote far more often than
  by a separator. Every one of those is a *correct* use: it is an identifier, not a
  sentence about the product.
- **The feature-ID check.** `C1` is `Copilot 1` in the register and a perfectly
  ordinary local name in code — a chiller constant, a coefficient, a test parameter.
  Worse, `check_id_references` reports unknown IDs as *warnings*, so pointing it at
  source would not fail the build; it would bury the real findings under noise until
  nobody reads the output. A gate nobody reads is not a gate.

So this script applies the rules that survive the change of medium — **the phrase
rules** — and nothing else. Concretely:

| Rule | Applied here | Why |
|---|---|---|
| `BANNED_PHRASES` | **yes** | A damaged phrase in a docstring reaches a reader through the API schema, and in a UI string it reaches them directly |
| `LEGACY_NAMES` | **yes** | `"AI Copilot"` in a button label is the same defect as in a chapter |
| `NAMING_VIOLATIONS`, minus lowercase-`synex` | **yes** | `Synex AI` and bare all-caps `SYNEX` read as wrong in a comment too. `SYNEX_MODEL_MODE` is untouched: `_` is a word character, so `\\bSYNEX\\b` does not match inside it |
| `SEPARATION_VIOLATIONS` | **yes** | This is the rule most worth having over code, because a module docstring is where an implementer writes down what they *think* the layer does |
| Feature IDs | **no** | `C1` collides with ordinary code |
| Register counts, scope tables, `.docx`, structure | **no** | Nothing in source restates them |

Two rules are added that exist only in source, because there is nothing in prose for
them to be about: the **Ragas ban** and the manifests it could re-enter through.

The naming law is imported from `verify.py`, never copied. `CLAUDE.md` §2.8 —
one source of truth per fact — applies to the rule tables themselves, and a second
copy of `BANNED_PHRASES` would rot in exactly the way the tables exist to prevent.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The rule tables, imported rather than restated. See the module docstring.
from verify import (
    BANNED_PHRASES,
    LEGACY_NAMES,
    NAMING_VIOLATIONS,
    SEPARATION_VIOLATIONS,
    denies,
)

# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------

SCAN_DIRS = ["backend", "apps", "packages", "ops", "tools", "scripts", ".github"]

CODE_SUFFIXES = {
    ".py", ".pyi",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sql", ".sh",
    ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".css", ".scss",
    ".md",  # a README beside code is code-adjacent prose and follows the same law
}

# Directories that are never ours to police: dependencies, build output, virtual
# environments, and recorded fixtures — a recorded model transcript is *evidence of
# what a model said*, and rewriting it to satisfy a naming rule would falsify it.
EXCLUDE_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".next", ".turbo",
    "dist", "build", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "htmlcov", ".git", "fixtures", "__snapshots__", "site",
}

EXCLUDE_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock",
}

# Files that state the rules rather than obeying them.
EXEMPT_FILES = {
    "verify.py",
    "verify_code.py",
    "test_verify_code.py",
}

# The lowercase-`synex` rule, excluded by identity rather than by index — reordering
# NAMING_VIOLATIONS in verify.py must not silently change what this script enforces.
LOWERCASE_SYNEX_PATTERN = r"\bsynex\b(?![-_/.])"

CODE_NAMING_VIOLATIONS = [
    (pattern, why)
    for pattern, why in NAMING_VIOLATIONS
    if pattern != LOWERCASE_SYNEX_PATTERN
]

# --------------------------------------------------------------------------
# Rules that exist only over source
# --------------------------------------------------------------------------

# Ragas was removed from the sibling because it hard-imports a class LangChain 1.x
# deleted — the framework-churn risk, realised. It is banned rather than merely
# unused: the failure mode is that someone reaches for the obvious RAG-evaluation
# library, and the build breaks on a transitive upgrade months later. DeepEval with
# a local Ollama judge is the decision it would displace.
BANNED_DEPENDENCIES = {
    "ragas": (
        "Ragas is banned — it hard-imports a class LangChain 1.x deleted, which is "
        "the framework-churn risk realised. Evaluation is DeepEval with a local "
        "Ollama judge"
    ),
}

# Matches an import or a manifest entry, not the word in a sentence explaining the
# ban. `from ragas import`, `import ragas`, `"ragas"`, `ragas==0.1.0`, `ragas>=…`.
def _dependency_patterns(name: str) -> list[re.Pattern[str]]:
    return [
        re.compile(rf"^\s*(?:from|import)\s+{name}\b", re.IGNORECASE),
        re.compile(rf"^\s*[-*]?\s*[\"']?{name}[\"']?\s*(?:[=<>~!]=?|@|:)", re.IGNORECASE),
        re.compile(rf"\brequire\([\"']{name}[\"']\)", re.IGNORECASE),
    ]


BANNED_DEPENDENCY_RES = {
    name: _dependency_patterns(name) for name in BANNED_DEPENDENCIES
}

MANIFESTS = {
    "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    "package.json", "setup.cfg", "environment.yml",
}


# --------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, path: Path, line: int, msg: str) -> None:
        self.errors.append(f"{rel(path)}:{line}: {msg}")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def targets() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CODE_SUFFIXES:
                continue
            if path.name in EXCLUDE_NAMES:
                continue
            if EXCLUDE_DIRS & set(path.parts):
                continue
            files.append(path)
    return files


def check_file(path: Path, text: str, rep: Report) -> None:
    exempt = path.name in EXEMPT_FILES
    is_markdown = path.suffix.lower() == ".md"
    in_fence = False

    for n, line in enumerate(text.splitlines(), 1):
        # Only markdown has fences worth skipping. In a .py file, ``` inside a
        # docstring is prose the rules should still read.
        if is_markdown and line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if is_markdown and in_fence:
            continue

        if not exempt:
            low = line.lower()
            for phrase, correct in BANNED_PHRASES.items():
                if phrase in low:
                    rep.error(path, n, f"banned phrase {phrase!r} — use {correct!r}")

            for pattern, replacement in LEGACY_NAMES:
                if re.search(pattern, line):
                    rep.error(
                        path, n,
                        f"legacy name matching /{pattern}/ — use {replacement!r}",
                    )

            for pattern, why in CODE_NAMING_VIOLATIONS:
                if re.search(pattern, line):
                    rep.error(path, n, f"naming law: {why}")

            for pattern, why in SEPARATION_VIOLATIONS:
                m = re.search(pattern, line)
                if m and not denies(line, m):
                    rep.error(path, n, f"separation law: {why}")

        for name, patterns in BANNED_DEPENDENCY_RES.items():
            if path.name in EXEMPT_FILES:
                continue
            for pat in patterns:
                if pat.search(line):
                    rep.error(path, n, BANNED_DEPENDENCIES[name])
                    break


def manifests() -> list[Path]:
    """Dependency manifests, found by name rather than by suffix.

    They cannot come from `targets()`: `requirements.txt` is a `.txt` file, and `.txt` is
    not in `CODE_SUFFIXES` — adding it would pull in every note and fixture in the tree.
    Found by name, this check sees `requirements.txt` and `requirements-dev.txt`, which is
    where a banned dependency is most likely to arrive in the first place.
    """
    found: list[Path] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if (
                path.is_file()
                and path.name in MANIFESTS
                and path.name not in EXCLUDE_NAMES
                and not (EXCLUDE_DIRS & set(path.parts))
            ):
                found.append(path)
    return found


def check_manifests(rep: Report) -> int:
    """A banned dependency can also arrive as a bare list entry with no operator.

    `pyproject.toml`'s `dependencies = ["ragas"]` pins nothing and matches none of the
    line patterns, and a bare `ragas` on its own line in `requirements.txt` matches none
    of them either — which is exactly the form somebody adds when they are trying
    something out. Manifests are therefore read whole, with a looser rule.
    """
    scanned = 0
    for path in manifests():
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            stripped = line.split("#", 1)[0].strip()
            if not stripped:
                continue
            for name, why in BANNED_DEPENDENCIES.items():
                quoted = re.search(rf"[\"']{name}[\"']", stripped, re.IGNORECASE)
                bare = re.match(rf"{name}\s*(?:[=<>~!\[].*)?$", stripped, re.IGNORECASE)
                if quoted or bare:
                    rep.error(path, n, why)
    return scanned


def main() -> int:
    ap = argparse.ArgumentParser(description="Synex source compliance gate")
    ap.add_argument("--list", action="store_true", help="print the scan set and stop")
    args = ap.parse_args()

    files = targets()

    if args.list:
        for path in files:
            print(rel(path))
        print(f"\n{len(files)} file(s) would be scanned.")
        return 0

    if not files:
        print(
            "No source found. Either this is not the repository root, or the build "
            "directories do not exist yet."
        )
        return 2

    rep = Report()
    for path in files:
        check_file(path, path.read_text(encoding="utf-8", errors="replace"), rep)
    manifests = check_manifests(rep)

    print(
        f"Scanned {len(files)} source file(s), including {manifests} dependency "
        f"manifest(s).\n"
    )

    if rep.errors:
        print(f"FAILED — {len(rep.errors)} error(s):")
        for e in rep.errors:
            print(f"  {e}")
        return 1

    print("PASSED — source is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
