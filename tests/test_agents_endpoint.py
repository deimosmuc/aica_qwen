"""GET /api/agents exposes the team registry: names, roles and system prompts."""
from fastapi.testclient import TestClient

from app.agents import architect
from app.main import app

EXPECTED_KEYS = {
    "requirements", "architecture", "critique", "arbitration",
    "pcb_engineer", "pcb_critic", "baseline",
}


def test_agents_endpoint_lists_full_team():
    client = TestClient(app)
    r = client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert len(agents) == 7
    assert {a["key"] for a in agents} == EXPECTED_KEYS


def test_agents_entries_have_all_fields_non_empty():
    client = TestClient(app)
    agents = client.get("/api/agents").json()["agents"]
    for a in agents:
        for field in ("key", "name", "role", "description", "reads", "delivers", "prompt"):
            assert a[field], f"{a.get('key')}: empty field {field}"


def test_agents_prompt_matches_module_constant():
    client = TestClient(app)
    agents = client.get("/api/agents").json()["agents"]
    arch = next(a for a in agents if a["key"] == "architecture")
    assert arch["name"] == "System Architect"
    assert arch["prompt"] == architect.SYSTEM_PROMPT
