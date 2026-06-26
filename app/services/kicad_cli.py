"""Thin wrapper around the KiCad command-line tool (`kicad-cli`).

kicad-cli is used as a *tool* — a separate subprocess we invoke, exactly like
PyMuPDF for PDF rendering or CI pipelines calling git/ffmpeg. It is GPL-3.0; our
own (MIT) code is not a derivative work because we only execute it.

It powers two product features:
- real validation: proving the generated scaffold actually opens/exports in KiCad,
- a server-side schematic preview rendered to SVG for the UI.

When kicad-cli is not installed the wrapper reports ``available is False`` and the
callers degrade gracefully — the app must always work (same principle as Mock Mode).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.services.config import Settings


class KiCadCliError(RuntimeError):
    """Raised when a kicad-cli invocation fails or times out."""


_UNSET = object()


# Known install locations to try when no explicit path is configured and the
# tool is not on PATH. Linux first (the deployment target), then local Windows.
_KNOWN_PATHS = (
    "/usr/bin/kicad-cli",
    "/usr/local/bin/kicad-cli",
    r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
)


class KiCadCli:
    def __init__(self, settings: Settings):
        self.timeout = settings.kicad_timeout_s
        self._path = self._resolve(settings) if settings.kicad_enabled else None
        self._version_cache = _UNSET  # lazily filled by version()

    @staticmethod
    def _resolve(settings: Settings) -> str | None:
        candidates: list[str] = []
        if settings.kicad_cli_path:
            candidates.append(settings.kicad_cli_path)
        candidates.append("kicad-cli")  # PATH
        candidates.extend(_KNOWN_PATHS)
        for c in candidates:
            found = shutil.which(c)
            if found:
                return found
            if Path(c).is_file():
                return c
        return None

    @property
    def available(self) -> bool:
        return self._path is not None

    @property
    def path(self) -> str | None:
        return self._path

    def version(self) -> str | None:
        """Return the kicad-cli version string, or None if unavailable.

        Cached after the first call. A failed/zero-output query caches as None
        so the badge can still say "Verified in KiCad" without a number.
        """
        if self._version_cache is not _UNSET:
            return self._version_cache
        if not self._path:
            self._version_cache = None
            return None
        try:
            proc = self._run(["version"])
        except KiCadCliError:
            self._version_cache = None
            return None
        out = proc.stdout.strip() if proc.returncode == 0 else ""
        self._version_cache = out or None
        return self._version_cache

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        if not self._path:
            raise KiCadCliError("kicad-cli is not available")
        try:
            proc = subprocess.run(
                [self._path, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:  # pragma: no cover - environment dependent
            raise KiCadCliError(f"kicad-cli timed out after {self.timeout}s") from e
        except OSError as e:  # pragma: no cover - environment dependent
            raise KiCadCliError(f"kicad-cli could not be executed: {e}") from e
        return proc

    def export_pdf(self, sch_path: str | Path, out_pdf: str | Path) -> Path:
        """Export the (whole hierarchical) schematic to a PDF. Proves it opens."""
        out = Path(out_pdf)
        proc = self._run(["sch", "export", "pdf", "--output", str(out), str(sch_path)])
        if proc.returncode != 0 or not out.is_file():
            raise KiCadCliError(f"sch export pdf failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return out

    def export_svg(self, sch_path: str | Path, out_dir: str | Path) -> Path:
        """Export each sheet to SVG into ``out_dir``; returns the root sheet SVG.

        kicad-cli writes ``<basename>.svg`` for the root sheet plus one SVG per
        subsheet. We return the root, which is what the UI previews.
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        proc = self._run(["sch", "export", "svg", "--output", str(out), str(sch_path)])
        root_svg = out / (Path(sch_path).stem + ".svg")
        if proc.returncode != 0 or not root_svg.is_file():
            raise KiCadCliError(f"sch export svg failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return root_svg

    def run_erc(self, sch_path: str | Path, out_json: str | Path) -> dict:
        """Run ERC and return the parsed JSON report.

        kicad-cli exits 0 even when violations exist (we do not pass
        --exit-code-violations), so a nonzero code means the run itself failed.
        """
        out = Path(out_json)
        proc = self._run(
            ["sch", "erc", "--format", "json", "--severity-all", "--output", str(out), str(sch_path)]
        )
        if proc.returncode != 0 or not out.is_file():
            raise KiCadCliError(f"sch erc failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return json.loads(out.read_text(encoding="utf-8"))
