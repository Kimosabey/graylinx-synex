"""Cases generated from the plant, not written by whoever wrote the router.

**The failure this exists for.** `eval_copilot.py` passed 31 of 31 while six ordinary questions
written minutes later all failed — because the same person wrote the router's keyword lists and
the suite's questions, so the suite tested the lists rather than the product. Every case it
held was a case somebody had already thought of. **A suite written by the router's author
measures the author.**

**So these are enumerated rather than chosen.** Every machine the plant has, crossed with every
question shape a person actually types; every fault class the model can emit; every signal in
the registry. Nobody picks which ones go in, so nobody can unconsciously pick the ones that
work. Twelve machines and nine classes produce far more cases than anybody would hand-write,
and the ones that fail are the ones worth reading.

**What is asserted is deliberately weak, and that is the point.** These cases cannot know the
right answer — the plant decides that. What they can prove is that the product never *breaks*:
no empty turn, no stack trace, no internal identifier, no value for a signal this plant never
metered, and no silence read as health. A generated suite that tried to assert content would be
asserting whatever its generator believed, which is the same trap one level up.

**Failures are written out as a work list.** `--record` appends every failing question to
`eval-flywheel.txt`, which is how a suite stops ossifying: today's failures are tomorrow's
hand-written cases with real expectations attached.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.domain import equipment as eq
from app.domain import faults, signals

#: Where failures accumulate between runs. A path rather than a database because the value is
#: in somebody reading it, and a file in the repository gets read.
FLYWHEEL = Path(__file__).resolve().parents[1] / "eval-flywheel.txt"

#: What a person types about one machine. Written as sentence shapes rather than as questions,
#: so the machine names come from the plant and not from whoever wrote this list.
PER_MACHINE: tuple[str, ...] = (
    "how is {m} doing?",
    "what happened on {m}?",
    "is {m} healthy?",
    "has {m} got any problems?",
    "what should I know about {m}?",
    "tell me about {m}",
    "is there anything wrong with {m}?",
    "what is {m} doing right now?",
)

#: What a person asks about a fault class they have seen on a screen somewhere.
PER_FAULT: tuple[str, ...] = (
    "what does {f} mean?",
    "which machines had {f}?",
    "how serious is {f}?",
    "what causes {f}?",
)

#: What a person asks about a reading. Every one of these names a signal the registry knows to
#: be unusable, so the honest answer is a stated absence — and a number would be an invention.
PER_SIGNAL: tuple[str, ...] = (
    "what is the {s} on chiller 1?",
    "show me {s}",
    "is {s} normal?",
)


def generate() -> list[tuple[str, str]]:
    """Every (level, question) pair the plant's own catalogue produces."""
    cases: list[tuple[str, str]] = []

    for machine in eq.all_equipment():
        spoken = machine.key.replace("_", " ")
        for shape in PER_MACHINE:
            cases.append((f"machine/{machine.key}", shape.format(m=spoken)))

    for fault in faults.FAULT_CLASSES:
        for shape in PER_FAULT:
            cases.append((f"fault/{fault.label}", shape.format(f=fault.label)))

    for signal in signals.SIGNALS:
        for shape in PER_SIGNAL:
            cases.append((f"signal/{signal.key}", shape.format(s=signal.display_name)))

    return cases


async def main() -> int:
    # Imported here rather than at module scope: this script adds `backend` to the path above,
    # and the shared harness must be found after that.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import eval_copilot as harness

    parser = argparse.ArgumentParser(description="Sweep generated cases against a live box.")
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--limit", type=int, default=0, help="stop after N cases")
    parser.add_argument("--filter", default="", help="only levels containing this")
    parser.add_argument("--record", action="store_true", help="append failures to the flywheel")
    args = parser.parse_args()

    cases = [c for c in generate() if args.filter in c[0]]
    if args.limit:
        cases = cases[: args.limit]

    import httpx

    failures: list[str] = []
    print(f"{len(cases)} generated case(s) — nobody chose these\n")

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        for i, (level, question) in enumerate(cases, 1):
            case = harness.Case(level=level, question=question, states=harness.ANY_STATE)
            got = await harness.ask(client, args.base, case)

            problems = []
            if "error" in got:
                problems = [got["error"]]
            else:
                # Deliberately not `check_correctness`: these cases cannot know the right
                # answer. What they prove is that nothing breaks.
                text = got.get("text") or ""
                if len(text) < 20:
                    problems.append(f"rendered {len(text)} characters - an empty turn")
                if got.get("state") is None:
                    problems.append("no answer state arrived")
                problems += harness.check_truthfulness(got)
                problems += harness.check_faithfulness(got)

            mark = "FAIL" if problems else "ok  "
            model = "M" if got.get("used_model") else "."
            print(
                f"{mark} [{model}] {i:>3}/{len(cases)} {level:<34} "
                f"{(got.get('state') or '-'):<14} {question[:44]}",
                flush=True,
            )
            for problem in problems:
                print(f"          {problem}", flush=True)
            if problems:
                failures.append(f"{level}\t{question}\t{'; '.join(problems)}")

    print(f"\n{len(cases) - len(failures)}/{len(cases)} generated cases behaved.")

    if failures and args.record:
        with FLYWHEEL.open("a", encoding="utf-8") as fh:
            for row in failures:
                fh.write(row + "\n")
        print(f"{len(failures)} failure(s) appended to {FLYWHEEL.name} — write real cases for them.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
