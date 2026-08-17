"""Test-wide setup that must happen before any event loop exists.

The only entry is the Windows event-loop policy — see `app/runtime.py` for why. It is set at
**import time** rather than in a fixture because pytest-asyncio builds its loop before any
fixture runs, and a policy set after that has no effect on the loop already made.
"""
from __future__ import annotations

from app.runtime import use_psycopg_compatible_event_loop

use_psycopg_compatible_event_loop()
