"""/api/generate accepts + validates the client-rendered architecture SVG (Phase 1)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.config import Settings
from app.services.mock import mock_run

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setattr("app.api.routes.get_settings", lambda: Settings(qwen_api_key=""))


def _body(svg=None):
    return {"requirements_text": "24V board", "result": mock_run("x").model_dump(),
            "architecture_svg": svg}


def test_generate_accepts_valid_client_svg(monkeypatch):
    seen = {}
    import app.api.routes as r

    def fake_pdf(result, text, name, architecture_svg=None, title=None, persona=None):
        seen["svg"] = architecture_svg
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(r, "generate_report_pdf", fake_pdf)
    ok_svg = "<svg viewBox='0 0 10 10'></svg>"
    resp = client.post("/api/generate", json=_body(ok_svg))
    assert resp.status_code == 200
    assert seen["svg"] == ok_svg


def test_generate_ignores_malformed_svg(monkeypatch):
    seen = {}
    import app.api.routes as r

    def fake_pdf(result, text, name, architecture_svg=None, title=None, persona=None):
        seen["svg"] = architecture_svg
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(r, "generate_report_pdf", fake_pdf)
    resp = client.post("/api/generate", json=_body("<script>nope</script>"))
    assert resp.status_code == 200
    assert seen["svg"] is None


def test_generate_passes_project_name_as_report_title(monkeypatch):
    seen = {}
    import app.api.routes as r

    def fake_pdf(result, text, name, architecture_svg=None, title=None, persona=None):
        seen["title"] = title
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(r, "generate_report_pdf", fake_pdf)
    body = {**_body(), "project_name": "Falcon Sensor Hub"}
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 200
    assert seen["title"] == "Falcon Sensor Hub"
