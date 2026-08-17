"""Platform quirks that must be settled before the event loop is created.

One entry today, and it is not cosmetic: on Windows, Python 3.8+ defaults to
`ProactorEventLoop`, and **psycopg3 cannot run async on it** —

    psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode

`langgraph-checkpoint-postgres` is built on psycopg3, so without this the durable case
checkpointer fails at connect time. `asyncpg` and `aiomysql` are unaffected and work on the
selector loop, so the fix costs nothing elsewhere.

**Why a module rather than a line in `main.py`.** The policy has to be set *before* any loop
is created, which means before `uvicorn` starts and before pytest-asyncio builds its loop.
Two callers, one rule — and a rule that lives in one place cannot be applied in one and
forgotten in the other. `tests/conftest.py` calls it at import time; `main.py` calls it at
module scope.

It is a no-op everywhere except Windows, and it is safe to call more than once.
"""
from __future__ import annotations

import asyncio
import sys


def use_psycopg_compatible_event_loop() -> bool:
    """Switch Windows to the selector loop. Returns whether it changed anything.

    Deliberately not silent about *why*: a future reader who sees a policy being set with no
    explanation will delete it, and the failure it prevents surfaces only when Postgres is
    actually reachable — which is to say, not in the offline gate.
    """
    if sys.platform != "win32":
        return False

    policy = asyncio.get_event_loop_policy()
    if isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
        return False

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return True
