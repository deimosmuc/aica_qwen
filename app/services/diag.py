"""Lightweight diagnostics for live-Qwen failures.

When Qwen returns JSON that doesn't satisfy an agent's schema, the pipeline
degrades to example data (see orchestrator). That keeps the demo alive but
hides *what* Qwen got wrong. This module captures the offending detail to a
log file so a failed live run can actually be diagnosed afterwards.

Logging is best-effort: it must never raise and never break a run.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "qwen_validation_errors.jsonl"


def field_summary(exc: ValidationError, limit: int = 3) -> str:
    """A short, human-readable description of the failing field(s), e.g.
    'architecture.blocks.0.category (Input should be ...)'. Safe for the UI."""
    parts = []
    for err in exc.errors()[:limit]:
        loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
        parts.append(f"{loc} — {err.get('msg', 'invalid')}")
    extra = exc.error_count() - limit
    if extra > 0:
        parts.append(f"(+{extra} more)")
    return "; ".join(parts)


def log_validation_error(exc: ValidationError, *, agent: str = "", model: str = "") -> None:
    """Append one JSONL record describing a Qwen schema-validation failure,
    including the offending value(s) Qwen produced. Never raises."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "agent": agent,
            "model": model,
            "error_count": exc.error_count(),
            "errors": [
                {
                    "loc": ".".join(str(p) for p in err.get("loc", ())),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                    "input": err.get("input"),
                }
                for err in exc.errors()
            ],
        }
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # diagnostics must never break the run
