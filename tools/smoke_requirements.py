"""Live smoke test for the Requirements Agent against the real Qwen API.

Reads QWEN_API_KEY from .env (or the environment) and calls the agent once.
Run:
    python tools/smoke_requirements.py "A 24V sensor board with an STM32 and RS485"
"""
from __future__ import annotations

import json
import sys

from app.agents.requirements import RequirementsAgent
from app.services.config import Settings
from app.services.qwen_client import QwenClient


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else (
        "A 24V industrial sensor board with an STM32 microcontroller, "
        "USB-C for configuration and an RS485 fieldbus interface."
    )
    settings = Settings()
    if settings.mock_mode:
        print("No QWEN_API_KEY found (.env or env). Set it to run the live test.")
        return 1

    print(f"Model: {settings.qwen_model}")
    print(f"Input: {text}\n")
    client = QwenClient(settings)
    result = RequirementsAgent().run(client, text)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
