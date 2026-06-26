"""Package a generated KiCad scaffold into a downloadable ZIP.

The ZIP contains exactly what the engineer downloads: the KiCad project, the
hierarchical sheets and the engineering reports. Internal artefacts such as the
rendered preview are excluded.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ZIP_NAME = "project.zip"
_EXCLUDE_TOP = {"preview"}


def create_project_zip(project_dir: str | Path, zip_path: str | Path | None = None) -> Path:
    project_dir = Path(project_dir)
    zip_path = Path(zip_path) if zip_path else project_dir / ZIP_NAME

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(project_dir.rglob("*")):
            if not p.is_file() or p == zip_path:
                continue
            rel = p.relative_to(project_dir)
            if rel.parts[0] in _EXCLUDE_TOP or rel.suffix == ".zip":
                continue
            zf.write(p, rel.as_posix())
    return zip_path
