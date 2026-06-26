"""Milestone 8: ZIP packaging of the generated scaffold."""
import zipfile

from app.generators.kicad import generate_scaffold
from app.services.mock import mock_run
from app.services.packaging import ZIP_NAME, create_project_zip

REQ_TEXT = "A 24V board with an STM32 and RS485."


def test_zip_contains_scaffold_excludes_preview(tmp_path):
    out = generate_scaffold(mock_run(REQ_TEXT), REQ_TEXT, tmp_path / "proj")
    # Simulate a rendered preview that must NOT be packaged.
    (out / "preview").mkdir()
    (out / "preview" / "project.svg").write_text("<svg/>", encoding="utf-8")

    zip_path = create_project_zip(out)
    assert zip_path.name == ZIP_NAME

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "project.kicad_sch" in names
    assert "project.kicad_pro" in names
    assert any(n.startswith("sheets/") for n in names)
    assert "README.md" in names
    # Excluded artefacts:
    assert not any(n.startswith("preview/") for n in names)
    assert ZIP_NAME not in names


def test_zip_includes_verification_artifacts(tmp_path):
    out = generate_scaffold(mock_run(REQ_TEXT), REQ_TEXT, tmp_path / "proj")
    # Simulate verification artifacts produced when KiCad verified the project.
    (out / "VERIFICATION.md").write_text("# Verification\n", encoding="utf-8")
    (out / "schematic_preview.png").write_bytes(b"\x89PNG\r\n")
    (out / "schematic.pdf").write_text("%PDF-1.5", encoding="utf-8")

    zip_path = create_project_zip(out)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "VERIFICATION.md" in names
    assert "schematic_preview.png" in names
    assert "schematic.pdf" in names
