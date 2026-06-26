"""FastAPI application entry point."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.services.config import get_settings

settings = get_settings()
STATIC_DIR = Path(__file__).parent / "static"
PROJECTS_DIR = Path(settings.output_dir)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
# Generated scaffolds (preview SVGs, and later ZIP downloads) are served here.
app.mount("/projects", StaticFiles(directory=PROJECTS_DIR), name="projects")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
