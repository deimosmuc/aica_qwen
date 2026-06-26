"""HTTP API for the orchestration pipeline.

/api/run executes the multi-agent pipeline and returns the plan for human
approval. /api/generate runs only after the human approves: it builds the KiCad
scaffold, validates it (with real kicad-cli checks when available) and renders a
preview. No KiCad project is ever generated before approval.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.generators.kicad import generate_scaffold
from app.models.schemas import (
    CompareRequest,
    Comparison,
    GenerateRequest,
    GenerateResponse,
    RunRequest,
    RunResponse,
)
from app.services.comparison import run_comparison
from app.services.config import get_settings
from app.services.guard import ApiGuard
from app.services.kicad_cli import KiCadCli, KiCadCliError
from app.services.orchestrator import Orchestrator
from app.services.packaging import ZIP_NAME, create_project_zip
from app.services.validation import validate_project

router = APIRouter(prefix="/api", tags=["pipeline"])

_PROJECT_NAME = "project"


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "mode": "mock" if settings.mock_mode else "qwen",
    }


@router.get("/guard")
def guard_status() -> dict:
    """Current spend / rate status from the API Guard ledger."""
    return ApiGuard(get_settings()).status()


@router.post("/run", response_model=RunResponse)
def run(req: RunRequest) -> RunResponse:
    """Run the multi-agent pipeline over the user's requirements text.

    Returns the structured architecture plus the agent trace. No KiCad project
    is generated yet — that happens only after explicit human approval.
    """
    settings = get_settings()
    return Orchestrator(settings).run(req.requirements_text)


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate the KiCad scaffold for an approved plan, then validate it.

    The approved result is sent back by the client so we never re-call Qwen just
    to produce files. Real KiCad validation and the SVG preview run when
    kicad-cli is available; otherwise they degrade gracefully.
    """
    settings = get_settings()
    project_id = uuid.uuid4().hex[:8]
    project_dir = Path(settings.output_dir) / project_id

    generate_scaffold(req.result, req.requirements_text, project_dir, _PROJECT_NAME)

    kicad = KiCadCli(settings)
    validation = validate_project(project_dir, req.result, kicad, _PROJECT_NAME)

    preview_url: str | None = None
    if kicad.available:
        try:
            kicad.export_svg(project_dir / f"{_PROJECT_NAME}.kicad_sch", project_dir / "preview")
            preview_url = f"/projects/{project_id}/preview/{_PROJECT_NAME}.svg"
        except KiCadCliError:
            preview_url = None  # preview is best-effort; validation already covers correctness

    create_project_zip(project_dir)

    files = sorted(
        str(p.relative_to(project_dir)).replace("\\", "/")
        for p in project_dir.rglob("*")
        if p.is_file() and "preview" not in p.parts and p.suffix != ".zip"
    )
    return GenerateResponse(
        project_id=project_id,
        validation=validation,
        preview_svg_url=preview_url,
        download_url=f"/api/download/{project_id}",
        files=files,
    )


@router.get("/download/{project_id}")
def download(project_id: str) -> FileResponse:
    """Download the generated scaffold as a ZIP."""
    # Guard against path traversal: only a bare id is valid.
    if not project_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid project id.")
    zip_path = Path(get_settings().output_dir) / project_id / ZIP_NAME
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Project not found.")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"ai-circuit-architect-{project_id}.zip",
    )


@router.post("/compare", response_model=Comparison)
def compare(req: CompareRequest) -> Comparison:
    """Run the same requirement through the multi-agent pipeline and a single-agent
    baseline, and score both with the deterministic rubric."""
    return run_comparison(req.requirements_text, get_settings())
