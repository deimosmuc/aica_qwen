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


def test_generate_includes_pdf_report(monkeypatch, tmp_path):
    settings = Settings(kicad_enabled=False, output_dir=str(tmp_path), qwen_api_key="")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)

    client = TestClient(app)
    text = "A 24V industrial board with an STM32 and RS485."
    payload = {"requirements_text": text, "result": mock_run(text).model_dump()}
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # When WeasyPrint is available the PDF is generated, listed, and downloadable.
    try:
        import weasyprint  # noqa: F401
    except Exception:
        # No system libs: report generation is best-effort, so report_url is null.
        assert data["report_url"] is None
        return

    assert data["report_url"] == f"/api/report/{data['project_id']}"
    assert "AI_Circuit_Architect_Report.pdf" in data["files"]
    pdf = client.get(data["report_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")


def test_report_endpoint_guards(monkeypatch, tmp_path):
    settings = Settings(kicad_enabled=False, output_dir=str(tmp_path), qwen_api_key="")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    client = TestClient(app)
    assert client.get("/api/report/deadbeef").status_code == 404
    assert client.get("/api/report/bad..id").status_code == 400
