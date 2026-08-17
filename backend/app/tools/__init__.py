"""The tool layer — what the agent may reach, and the one door it goes through.

`registry.py` declares what exists (`C20`); `gateway.py` decides whether this caller may have
it (`G4`) and that a retry does not act twice (`G5`); `plant_tools.py` binds the handlers.

Deliberately importable with the GPU terminated and MySQL stopped: a tool is a declaration
plus a coroutine, and neither needs a model.
"""
