"""The golden set — `EV1`. **Re-exported, not defined here.**

The cases moved to `app/eval/golden.py` on 2026-08-17, and this module now points at them.
Two things were wrong with owning them under `tests/`:

* The application could not see its own acceptance set. `app/eval/scorecard.py` carried the
  size as a literal, so every coverage sentence quoted a restated number rather than a count —
  and `CLAUDE.md` §2.8 says one source of truth per fact.
* Nothing checked the **set** for decay, only the cases in it. A set that quietly loses its
  only `NO_DIAGNOSIS` case still passes every case it retains. `app/eval/golden.py` registers
  those properties as invariants and `tests/eval/test_golden_gate.py` feeds it decayed sets.

Everything about how the cases are run is unchanged — `test_golden_set.py` streams each one
against the live application exactly as before.

**One correction to the plan, kept here because it is where people look.** It asks for *"five
determinate episodes on chiller 2"*. Chiller 2 has **two**: `REFRIGERANT_SIDE_HIGH_HEAD` on 12
and 13 April. Its other five episodes are all classes that declare themselves undecidable.
Rather than pad the set with chiller 1 cases and call them chiller 2's, the set uses all seven
of chiller 2's episodes and says so — the shape of this data is that ambiguity is the median
outcome, and a golden set that hid it would be testing a plant we do not have.

**The hero is chiller 2.** Its worst model runs at nRMSE 3.77 against chiller 1's 48.03, so its
residuals can be shown without qualification. Chiller 1 stays in the set and **must badge** —
that is acceptance case 14, and a set that only contained the clean machine would never catch
the badge disappearing.
"""
from __future__ import annotations

from app.eval.golden import (
    CHILLER_1,
    CHILLER_2,
    CONVERSATION,
    GOLDEN_CASES,
    REFUSALS,
    GoldenCase,
    needs_database,
)

__all__ = [
    "CHILLER_1",
    "CHILLER_2",
    "CONVERSATION",
    "GOLDEN_CASES",
    "REFUSALS",
    "GoldenCase",
    "needs_database",
]
