"""Generate a professional PDF 'PCB Design Brief' from a pipeline RunResponse.

Pure, dependency-light helpers plus a single WeasyPrint render entry point. All
helpers are independently testable; WeasyPrint is imported lazily so the rest of
the module (and its tests) work even where the system libraries are absent.
"""
from __future__ import annotations

import base64
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "static" / "assets"
_LOGO_PATH = _ASSETS_DIR / "logo.png"


def _logo_data_uri() -> str:
    """Return the bundled logo as a base64 PNG data URI, or "" if it is missing.

    Embedding as a data URI keeps the rendered HTML fully self-contained so
    WeasyPrint needs no external file resolution.
    """
    if not _LOGO_PATH.is_file():
        return ""
    encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
