"""Milestone 7: the /api/generate endpoint (approve -> generate -> validate)."""
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.services.config import Settings
from app.services.mock import mock_run


def test_generate_builds_and_validates(monkeypatch, tmp_path):
    # kicad disabled -> deterministic, fast, no binary needed.
    settings = Settings(kicad_enabled=False, output_dir=str(tmp_path), qwen_api_key="")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)

    client = TestClient(app)
    payload = {
        "requirements_text": "A 24V industrial board with an STM32 and RS485.",
        "result": mock_run("A 24V industrial board with an STM32 and RS485.").model_dump(),
    }
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["project_id"]
    assert data["validation"]["ok"] is True
    assert data["validation"]["kicad_cli_available"] is False
    assert data["preview_svg_url"] is None  # no kicad -> no preview
    # The scaffold and the validation report are part of the output.
    assert "project.kicad_sch" in data["files"]
    assert "validation_report.md" in data["files"]
    assert any(f.startswith("sheets/") for f in data["files"])

    # The ZIP is downloadable.
    assert data["download_url"] == f"/api/download/{data['project_id']}"
    dl = client.get(data["download_url"])
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    assert len(dl.content) > 0


def test_download_unknown_project_404(monkeypatch, tmp_path):
    settings = Settings(kicad_enabled=False, output_dir=str(tmp_path), qwen_api_key="")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    client = TestClient(app)
    assert client.get("/api/download/deadbeef").status_code == 404
    assert client.get("/api/download/bad..id").status_code == 400
