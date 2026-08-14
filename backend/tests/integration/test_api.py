"""The API, end to end, with **no model configured and the GPU terminated**.

That constraint is the test. If these pass, the layering law held: the deterministic half of
the product answers on its own, and the language model is added in M1.4 to *explain* the
pack rather than to produce it. A failure here would mean something in the read path had
quietly grown a dependency on inference.

Marked `requires_box` because they need MySQL. They do not need Ollama, Postgres or Redis.
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.main import app
from app.services import audit_log
from app.services.control_plane import Persona, issue_persona_token

pytestmark = pytest.mark.requires_box


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c


# ── the claim of the milestone ──────────────────────────────────────────────────

async def test_the_whole_read_path_works_with_no_model(client: httpx.AsyncClient) -> None:
    """`stub` mode, `gpu_required` false, and every route answering. The layering proof."""
    health = (await client.get("/api/v1/health")).json()
    assert health["status"] == "ok"
    assert health["model_mode"] == "stub"
    assert health["gpu_required"] is False
    assert health["plant_database"]["connected"] is True


async def test_the_plant_connection_is_read_only_by_grant(client: httpx.AsyncClient) -> None:
    """Q42. Not root, and health says so rather than the claim living only in a document."""
    plant = (await client.get("/api/v1/health")).json()["plant_database"]
    assert plant["read_only_by_grant"] is True
    assert plant["user"] == "synex_plant_ro"


async def test_health_reports_degraded_rather_than_refusing_to_start(monkeypatch) -> None:
    """`CONTEXT.md` §13: the platform states when it is in degraded mode rather than
    silently substituting a weaker capability.

    Pointed at a port with nothing on it, the application must still start and must say
    *why* it is degraded. A back end that refuses to boot because a database is down cannot
    tell anybody what is wrong — and during a demonstration that is the difference between
    a recoverable moment and a dead screen.
    """
    from app import main

    broken = Settings(mysql_port=1)  # nothing listens here
    monkeypatch.setattr(main, "get_settings", lambda: broken)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            health = (await c.get("/api/v1/health")).json()

    assert health["status"] == "degraded"
    assert health["plant_database"]["connected"] is False
    assert health["plant_database"]["error"], "degraded mode must name the reason"

    # The routes that do not need the plant keep working — the roster, the ceilings and the
    # equipment registry are domain facts, not queries.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as c:
        assert (await c.get("/api/v1/models")).status_code == 200
        assert (await c.get("/api/v1/equipment")).status_code == 200


# ── coverage and episodes ───────────────────────────────────────────────────────

async def test_equipment_lists_all_twelve_with_ten_unscoreable(
    client: httpx.AsyncClient,
) -> None:
    """Ten of twelve carry `scoreable: false` **with a reason**. Filtering them out would
    imply the plant has two assets."""
    body = (await client.get("/api/v1/equipment")).json()
    assert body["total_count"] == 12
    assert body["scoreable_count"] == 2
    unscoreable = [e for e in body["equipment"] if not e["scoreable"]]
    assert len(unscoreable) == 10
    assert all(e["why_not"] for e in unscoreable)


async def test_thirty_nine_episodes_over_twelve_equipment_days(
    client: httpx.AsyncClient,
) -> None:
    """The `RC19` problem as data: a 3.25x inflation, served by the API."""
    body = (await client.get("/api/v1/episodes")).json()
    assert body["episode_count"] == 39
    assert body["equipment_days"] == 12


async def test_the_measured_window_is_the_default_and_says_so(
    client: httpx.AsyncClient,
) -> None:
    """D-009. A response that did not state which window it covered would be `C22`'s
    failure — the reader supplies "now" from their own head."""
    body = (await client.get("/api/v1/episodes")).json()
    assert body["window"]["includes_simulated"] is False
    assert "simulated span is excluded" in body["window"]["note"]


async def test_reaching_the_simulated_span_is_explicit_and_labelled(
    client: httpx.AsyncClient,
) -> None:
    body = (await client.get("/api/v1/episodes?include_simulated=true")).json()
    assert body["window"]["includes_simulated"] is True
    assert "fabricated" in body["window"]["note"]


# ── the pack ────────────────────────────────────────────────────────────────────

CRITICAL_EPISODE = "chiller_1:CONDENSER_LOW_FLOW:2026-04-15"


async def test_the_critical_episode_serves_a_complete_pack(
    client: httpx.AsyncClient,
) -> None:
    """The only `critical` class, on the day chiller 1 carried five labels at once."""
    pack = (await client.get(f"/api/v1/episodes/{CRITICAL_EPISODE}/pack")).json()
    assert pack["answer_state"] == "ANSWERED"
    assert pack["severity"]["text"] == "critical"
    assert len(pack["other_labels_same_day"]) == 4
    assert pack["window"]["start"].startswith("2026-04-15")


async def test_the_pack_badges_a_poor_fit_rather_than_hiding_it(
    client: httpx.AsyncClient,
) -> None:
    """48.03 and 36.41 on chiller 1. Showing a badged machine beside a clean one is more
    convincing than showing only the clean one — acceptance case 14."""
    pack = (await client.get(f"/api/v1/episodes/{CRITICAL_EPISODE}/pack")).json()
    assert pack["has_poor_fit"] is True
    poor = [r for r in pack["residuals"] if r["poor_fit"]]
    assert poor
    assert all("POOR FIT" in r["rendered"] for r in poor)


async def test_the_sixth_model_is_served_as_a_stated_absence(
    client: httpx.AsyncClient,
) -> None:
    """`null` plus a reason, never `0`. Constraint 14, over the wire."""
    pack = (await client.get(f"/api/v1/episodes/{CRITICAL_EPISODE}/pack")).json()
    absent = next(
        r for r in pack["residuals"] if r["name"] == "compressor_power_residual"
    )
    assert absent["figure"]["value"] is None
    assert absent["figure"]["text"] == "no model is fitted for this signal"


async def test_every_residual_carries_its_band_and_its_fit(
    client: httpx.AsyncClient,
) -> None:
    pack = (await client.get(f"/api/v1/episodes/{CRITICAL_EPISODE}/pack")).json()
    current = next(
        r for r in pack["residuals"] if r["name"] == "chiller_current_residual"
    )
    assert current["model_nrmse"] == 48.03
    assert "-38.677" in current["rendered"]


async def test_the_pack_exposes_exactly_what_the_model_will_be_handed(
    client: httpx.AsyncClient,
) -> None:
    """`prompt_data` is returned so a person can read it. That is the strongest available
    form of "the model only ever saw this" — stronger than a test, because a human can
    check it during the demonstration itself."""
    pack = (await client.get(f"/api/v1/episodes/{CRITICAL_EPISODE}/pack")).json()
    prompt = pack["prompt_data"]
    assert prompt["data_window"]
    assert prompt["severity"] == "critical"
    assert any("condenser flow" in s for s in prompt["signal_provenance"])


async def test_a_bad_episode_id_is_refused_clearly(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/episodes/nonsense/pack")
    assert r.status_code == 400
    assert "equipment:label" in r.json()["detail"]


# ── the persona switcher ────────────────────────────────────────────────────────

async def test_every_persona_response_says_it_is_not_authentication(
    client: httpx.AsyncClient,
) -> None:
    """D-013. It must be impossible to read this output and believe it is authentication."""
    for path in ("/api/v1/personas", "/api/v1/me"):
        body = (await client.get(path)).json()
        assert "not authentication" in body["warning"]


async def test_the_default_persona_grants_nothing_extra(client: httpx.AsyncClient) -> None:
    """A display default, not an authority default: it cannot approve, close or edit policy."""
    scope = (await client.get("/api/v1/me")).json()["scope"]
    assert scope["persona"] == "reliability_engineer"
    assert scope["is_production_identity"] is False
    assert "approve_work" not in scope["capabilities"]
    assert "edit_policy" not in scope["capabilities"]


async def test_switching_persona_changes_the_capability_set(
    client: httpx.AsyncClient,
) -> None:
    r = await client.post("/api/v1/personas/supervisor")
    assert r.status_code == 200
    assert "approve_work" in r.json()["scope"]["capabilities"]

    me = (await client.get("/api/v1/me")).json()["scope"]
    assert me["persona"] == "supervisor"
    assert "approve_work" in me["capabilities"]


async def test_an_unknown_persona_is_a_404_not_a_default(
    client: httpx.AsyncClient,
) -> None:
    r = await client.post("/api/v1/personas/chief_executive")
    assert r.status_code == 404


async def test_a_tampered_cookie_is_refused_rather_than_defaulted(
    client: httpx.AsyncClient,
) -> None:
    """A corrupted cookie choosing an identity is an authorization decision made by
    accident — the separation law's seventh row."""
    token = issue_persona_token(Persona.TECHNICIAN, Settings().jwt_secret)
    r = await client.get(
        "/api/v1/me", cookies={"synex_persona": token.replace("technician", "administrator")}
    )
    assert r.status_code == 400
    assert "persona token rejected" in r.json()["detail"]


# ── the audit trail ─────────────────────────────────────────────────────────────

async def test_one_audit_row_per_request_including_refusals(
    client: httpx.AsyncClient,
) -> None:
    """`G6`. A refusal is a turn like any other and is recorded like one."""
    audit_log.clear()
    await client.get("/api/v1/episodes")
    await client.get(f"/api/v1/episodes/{CRITICAL_EPISODE}/pack")

    body = (await client.get("/api/v1/audit")).json()
    assert body["total"] == 2
    assert {r["action"] for r in body["rows"]} == {"list_episodes", "episode_pack"}


async def test_every_audit_row_marks_the_identity_as_a_demonstration_one(
    client: httpx.AsyncClient,
) -> None:
    audit_log.clear()
    await client.get("/api/v1/episodes")
    rows = (await client.get("/api/v1/audit")).json()["rows"]
    assert all(r["identity_kind"] == "demonstration_persona" for r in rows)


async def test_the_audit_trail_admits_it_is_not_durable(
    client: httpx.AsyncClient,
) -> None:
    """A trail that quietly forgets is worse than one that says it will."""
    assert (await client.get("/api/v1/audit")).json()["durable"] is False


# ── the roster and the ceilings ─────────────────────────────────────────────────

async def test_the_roster_exposes_nine_roles_over_four_models(
    client: httpx.AsyncClient,
) -> None:
    body = (await client.get("/api/v1/models")).json()
    assert len(body["roster"]) == 9
    assert len(set(body["roster"].values())) == 4
    assert body["roster"]["sql"] == body["roster"]["tool"]
    assert body["roster"]["planner"] == body["roster"]["brain"]


async def test_the_auditor_is_never_the_brain(client: httpx.AsyncClient) -> None:
    """The auditor must not be the model that wrote the answer. A guarantee, not a
    preference — which is why the aliases live in the table and not in configuration."""
    roster = (await client.get("/api/v1/models")).json()["roster"]
    assert roster["auditor"] != roster["brain"]


async def test_the_ceilings_show_which_numbers_are_guesses(
    client: httpx.AsyncClient,
) -> None:
    """Q48. A reader can tell our numbers from our guesses without reading the code."""
    body = (await client.get("/api/v1/ceilings")).json()
    assert len(body["ceilings"]) == 10
    assert body["provisional_count"] == 3
    assert all(c["stops"] for c in body["ceilings"])
    provisional = [c for c in body["ceilings"] if c["provisional"]]
    assert all(c["question"] == "Q48" for c in provisional)
