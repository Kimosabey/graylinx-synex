"""`EV1` — the golden set, run.

Split deliberately. The cases that need no database — every refusal and the conversational
floor — run in the **default** gate, so CI proves the product's most important behaviours
with MySQL stopped and the box terminated. The episode cases are marked `requires_box` and
run against the real plant snapshot.

That split is not a convenience. On this data the refusal is the modal outcome, so the
refusal path is the one most worth having covered by the test everybody runs.
"""
from __future__ import annotations

import httpx
import pytest

from app.main import app
from tests.golden.cases import GOLDEN_CASES, GoldenCase, needs_database

OFFLINE = [c for c in GOLDEN_CASES if not needs_database(c)]
WITH_DB = [c for c in GOLDEN_CASES if needs_database(c)]


async def _run(client: httpx.AsyncClient, case: GoldenCase) -> dict:
    """Stream one case and fold the frames into something assertable."""
    import json as _json

    body: dict = {"question": case.question}
    if case.equipment_key:
        body |= {
            "equipment_key": case.equipment_key,
            "fault_label": case.fault_label,
            "day": case.day,
        }

    out: dict = {"figures": [], "audits": [], "text": "", "route": None, "state": None}
    event = None
    async with client.stream("POST", "/api/v1/ask", json=body) as r:
        assert r.status_code == 200, f"{case.name}: HTTP {r.status_code}"
        async for line in r.aiter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event:
                payload = _json.loads(line[6:])
                if event == "figure":
                    out["figures"].append(payload)
                elif event == "audit":
                    out["audits"].append(payload)
                elif event in {"token", "no_diagnosis"}:
                    out["text"] += payload["text"]
                elif event == "route":
                    out["route"] = payload
                elif event == "state":
                    out["state"] = payload
    return out


def _assert(case: GoldenCase, result: dict) -> None:
    why = f"\n  case: {case.name}\n  why it is in the set: {case.why}"

    assert result["state"], f"no state frame{why}"
    assert result["state"]["state"] == case.expect_state, (
        f"expected {case.expect_state}, got {result['state']['state']}{why}"
    )

    if case.expect_no_model_call:
        assert result["state"]["used_model"] is False, f"spent a model call{why}"
        assert result["route"]["used_model"] is False, f"the arbiter was reached{why}"

    if case.expect_route_layer:
        assert result["route"]["layer"].startswith(case.expect_route_layer), (
            f"routed at {result['route']['layer']!r}, expected "
            f"{case.expect_route_layer!r}{why}"
        )

    if case.expect_figures:
        assert result["figures"], f"no evidence was emitted{why}"
    else:
        assert not result["figures"], f"evidence emitted where none was expected{why}"

    if case.expect_poor_fit is not None:
        badged = any(f.get("poor_fit") for f in result["figures"])
        assert badged is case.expect_poor_fit, (
            f"poor-fit badge was {badged}, expected {case.expect_poor_fit}{why}"
        )
        if case.expect_poor_fit:
            assert "nRMSE" in result["text"] or any(
                "poor_fit_disclosed" in str(a) for a in result["audits"]
            ), f"a poorly fitted model was not disclosed in the answer{why}"

    # Every hard audit that ran must have passed. A golden case whose answer failed an
    # honesty check is not a passing case, however plausible the prose.
    for audit in result["audits"]:
        for finding in audit.get("findings", []):
            if finding["severity"] == "hard":
                assert finding["passed"], f"hard audit {finding['audit']} failed{why}"

    for term in case.forbid_terms:
        assert term.lower() not in result["text"].lower(), (
            f"the answer contains {term!r}, which it must not{why}"
        )

    # The dimension that exists because nothing asked it.
    text = result["text"].rstrip()
    if text:
        assert text[-1] in ".!?:\"')]`", (
            f"the answer does not appear to have finished: ...{text[-40:]!r}{why}"
        )


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c


# ── the cases that need nothing at all ──────────────────────────────────────────

@pytest.mark.parametrize("case", OFFLINE, ids=lambda c: c.name)
async def test_golden_case_offline(case: GoldenCase, client: httpx.AsyncClient) -> None:
    """Refusals and the conversational floor, with everything switched off.

    These are in the default gate on purpose: the refusal is what this platform does most,
    so it is what CI should be surest about.
    """
    _assert(case, await _run(client, case))


# ── the cases that need the plant ───────────────────────────────────────────────

@pytest.mark.requires_box
@pytest.mark.parametrize("case", WITH_DB, ids=lambda c: c.name)
async def test_golden_case_on_real_data(case: GoldenCase, client: httpx.AsyncClient) -> None:
    _assert(case, await _run(client, case))


# ── properties of the set itself ────────────────────────────────────────────────

def test_the_set_covers_both_machines_and_both_outcomes() -> None:
    """A golden set that only held the clean machine would never catch the badge
    disappearing, and one with no refusals would miss the modal outcome entirely."""
    assert any(c.equipment_key == "chiller_1" for c in GOLDEN_CASES)
    assert any(c.equipment_key == "chiller_2" for c in GOLDEN_CASES)
    assert any(c.expect_state == "NO_DIAGNOSIS" for c in GOLDEN_CASES)
    assert any(c.expect_state == "BLOCKED" for c in GOLDEN_CASES)
    assert any(c.expect_poor_fit is True for c in GOLDEN_CASES)
    assert any(c.expect_poor_fit is False for c in GOLDEN_CASES)


def test_every_case_says_why_it_is_in_the_set() -> None:
    """A golden case without a reason is one nobody can decide to delete."""
    for case in GOLDEN_CASES:
        assert len(case.why) > 40, f"{case.name} does not explain itself"


def test_a_third_of_the_set_needs_nothing_to_run() -> None:
    """If the whole set needed the plant, none of it would run in CI."""
    assert len(OFFLINE) >= len(GOLDEN_CASES) // 3
