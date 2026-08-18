"""Test-wide setup that must happen before any event loop exists.

Two entries, both at **import time** rather than in a fixture, because pytest-asyncio builds
its loop before any fixture runs and a policy set after that has no effect on the loop already
made — see `app/runtime.py`.

**The model mode is pinned to `stub` here, and this is the only place it is.** The application
default is `live`: a product whose models are off by default ships a demonstration where every
answer reports "language model - not used" and nothing is wrong. The gate has the opposite
need — a bare `pytest` must run on any machine, with no GPU and no box — so the offline suite
states its requirement instead of inheriting it. Setting it here rather than in `pytest.ini`
means it also holds for anything that imports the suite's fixtures directly.
"""
from __future__ import annotations

import os

from app.runtime import use_psycopg_compatible_event_loop

os.environ.setdefault("SYNEX_MODEL_MODE", "stub")

use_psycopg_compatible_event_loop()
