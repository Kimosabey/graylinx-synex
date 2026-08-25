"""Scheduled work. `RC17` is the only job today, and its whole point is that it runs.

`app.jobs` sits directly under `app.api` in the layering: a job is an entry point, like a
route, and it may reach everything a route may. Nothing imports *from* here.
"""
