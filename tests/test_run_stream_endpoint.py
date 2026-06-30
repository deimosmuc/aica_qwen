"""POST /api/run/stream emits SSE events ending in a final RunResponse."""
import json

from fastapi.testclient import TestClient

from app.main import app


def _parse_sse(body: str):
    events = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_run_stream_mock_mode_streams_steps_then_final(monkeypatch):
    # Force mock mode by replacing get_settings with a key-less Settings, so the
    # test is deterministic and never calls the live (paid) Qwen API even when a
    # real key is present in .env.
    import app.api.routes as routes
    from app.services.config import Settings
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))
    client = TestClient(app)
    r = client.post("/api/run/stream", json={"requirements_text": "a 24V sensor board"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    stage = [e for e in events if e["type"] == "stage"]
    final = [e for e in events if e["type"] == "final"]
    assert len(stage) >= 6
    assert len(final) == 1 and events[-1]["type"] == "final"
    assert len(stage) == len(final[0]["result"]["trace"])
    assert final[0]["result"]["mode"] == "mock"
    assert stage[0]["step"]["agent"]   # each stage carries a TraceStep


def test_run_stream_respects_named_profile(monkeypatch):
    captured = {}
    import app.api.routes as routes
    from app.models.schemas import RunResponse, StreamEvent
    from app.services.mock import mock_run

    class FakeOrch:
        def __init__(self, settings, profile=None, client=None):
            captured["profile"] = profile

        def run_stream(self, text, guidance=None, revisions=None):
            yield StreamEvent(type="final", result=mock_run(text))

    monkeypatch.setattr(routes, "Orchestrator", FakeOrch)
    client = TestClient(app)
    r = client.post("/api/run/stream", json={"requirements_text": "x", "profile": "Senior Review Team"})
    assert r.status_code == 200
    assert captured["profile"].rework is True
