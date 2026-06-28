"""HTTP API for the orchestration pipeline.

/api/run executes the multi-agent pipeline and returns the plan for human
approval. /api/generate runs only after the human approves: it builds the KiCad
scaffold, validates it (with real kicad-cli checks when available) and renders a
preview. No KiCad project is ever generated before approval.
"""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.generators.kicad import generate_scaffold
from app.generators.report import generate_report_pdf
from app.models.schemas import (
    BenchRequest,
    BenchResult,
    CompareRequest,
    Comparison,
    GenerateRequest,
    GenerateResponse,
    RunRequest,
    RunResponse,
    StepRequest,
    StepResponse,
)
from app.services.bench import run_bench
from app.services.comparison import run_comparison
from app.services.config import get_settings
from app.services.guard import ApiGuard
from app.services.kicad_cli import KiCadCli, KiCadCliError
from app.services.orchestrator import Orchestrator
from app.services.packaging import ZIP_NAME, create_project_zip
from app.services.persona import persona_instruction
from app.services.profiles import profile_for
from app.services.stepwise import run_stage
from app.services.validation import validate_project

router = APIRouter(prefix="/api", tags=["pipeline"])

_PROJECT_NAME = "project"
_REPORT_NAME = "AI_Circuit_Architect_Report.pdf"
_MAX_CLIENT_SVG = 200_000


def _safe_client_svg(svg: str | None) -> str | None:
    """Accept a client-rendered architecture SVG only if it looks like an SVG and
    is within a sane size cap; otherwise drop it so the report falls back to the
    Python-rendered diagram."""
    if not svg or not isinstance(svg, str):
        return None
    s = svg.strip()
    if not s.startswith("<svg") or len(s) > _MAX_CLIENT_SVG:
        return None
    return s


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
    profile = profile_for(req.profile, req.model, settings)
    guidance = [persona_instruction(req.persona)] + req.guidance
    return Orchestrator(settings, profile).run(req.requirements_text, guidance)


@router.post("/run/stream")
async def run_stream(req: RunRequest) -> StreamingResponse:
    """Server-Sent Events version of /api/run: emit one `stage` event per
    finished agent, then a `final` event with the full result. Lets the UI show
    real live progress instead of a spinner for the whole multi-minute run."""
    settings = get_settings()
    profile = profile_for(req.profile, req.model, settings)
    guidance = [persona_instruction(req.persona)] + req.guidance
    orch = Orchestrator(settings, profile)

    async def event_source():
        gen = orch.run_stream(req.requirements_text, guidance)
        done = object()

        def _next():
            try:
                return next(gen)
            except StopIteration:
                return done

        while True:
            event = await anyio.to_thread.run_sync(_next)
            if event is done:
                break
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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

    client_svg = _safe_client_svg(req.architecture_svg)
    generate_scaffold(
        req.result, req.requirements_text, project_dir, _PROJECT_NAME,
        generated_date=date.today().isoformat(),
        architecture_svg=client_svg,
    )

    kicad = KiCadCli(settings)
    validation = validate_project(project_dir, req.result, kicad, _PROJECT_NAME)

    preview_url: str | None = None
    if kicad.available:
        try:
            kicad.export_svg(project_dir / f"{_PROJECT_NAME}.kicad_sch", project_dir / "preview")
            preview_url = f"/projects/{project_id}/preview/{_PROJECT_NAME}.svg"
        except KiCadCliError:
            preview_url = None  # preview is best-effort; validation already covers correctness

    report_url: str | None = None
    try:
        pdf_bytes = generate_report_pdf(
            req.result, req.requirements_text, _PROJECT_NAME,
            architecture_svg=client_svg, title=req.project_name, persona=req.persona,
        )
        (project_dir / _REPORT_NAME).write_bytes(pdf_bytes)
        report_url = f"/api/report/{project_id}"
    except Exception:
        # Report is best-effort: missing WeasyPrint system libs must not break
        # scaffold generation or the ZIP. The button is simply hidden.
        report_url = None

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
        report_url=report_url,
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


@router.get("/report/{project_id}")
def report(project_id: str) -> FileResponse:
    """Download the generated PDF design brief."""
    if not project_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid project id.")
    pdf_path = Path(get_settings().output_dir) / project_id / _REPORT_NAME
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"ai-circuit-architect-{project_id}.pdf",
    )


@router.post("/compare", response_model=Comparison)
def compare(req: CompareRequest) -> Comparison:
    """Run the same requirement through the multi-agent pipeline and a single-agent
    baseline, and score both with the deterministic rubric."""
    return run_comparison(
        req.requirements_text, get_settings(), req.multi_model, req.single_model
    )


@router.post("/bench", response_model=BenchResult)
def bench(req: BenchRequest) -> BenchResult:
    """Run the curated preset trio over one request and compare cost + quality."""
    return run_bench(req.requirements_text, get_settings())


@router.post("/step", response_model=StepResponse)
def step(req: StepRequest) -> StepResponse:
    """Run a single agent stage (for the step-by-step, human-sign-off flow).

    The client passes back the already-approved prior results so each stage has
    what it needs. Auto mode uses /run instead.
    """
    settings = get_settings()
    profile = profile_for(req.profile, req.model, settings)
    # The pcb_critic stage maps to the "pcb_critique" model slot (stage vs role name).
    role = "pcb_critique" if req.stage == "pcb_critic" else req.stage
    settings = settings.model_copy(
        update={"qwen_model": profile.models.get(role, settings.qwen_model)})
    req = req.model_copy(update={"guidance": [persona_instruction(req.persona)] + req.guidance})
    try:
        return run_stage(req, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
