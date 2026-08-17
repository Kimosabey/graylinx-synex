"""`EV2`–`EV4` — the evaluation gate.

Deliberately its own layer rather than a corner of `app.agents`. The gate judges the agent,
so it has to sit above it, and a judge that lives inside the thing it judges is one that gets
edited to agree. `importlinter.ini` places `eval` between `jobs` and `agents` for that reason.

Nothing here calls a model. An evaluation gate that needs the box is a gate that runs once a
burst, and the failure it exists to catch — a reassuring lie that 56 unit tests, a clean
typecheck and a 100% evaluation score all missed — is a failure that ships in between.
"""
