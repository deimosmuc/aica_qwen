"""Live smoke test for the full live pipeline (Requirements -> Arbitration).

Runs the orchestrator in Qwen mode through the API Guard and prints the result.
Needs QWEN_API_KEY in .env. Run:
    python tools/smoke_pipeline.py "A 24V sensor board with an STM32 and RS485"
"""
from __future__ import annotations

import json
import sys

from app.services.config import Settings
from app.services.orchestrator import Orchestrator


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else (
        "A 24V industrial sensor board with an STM32 microcontroller, "
        "USB-C for configuration and an RS485 fieldbus interface."
    )
    settings = Settings()
    if settings.mock_mode:
        print("No QWEN_API_KEY found (.env or env). Set it to run the live test.")
        return 1

    result = Orchestrator(settings).run(text)
    print(f"mode: {result.mode}")
    if result.notice:
        print(f"notice: {result.notice}")
    print("\n-- requirements --")
    print(json.dumps(result.requirements.model_dump(), indent=2, ensure_ascii=False))
    print("\n-- architecture --")
    print(json.dumps(result.architecture.model_dump(), indent=2, ensure_ascii=False))
    print("\n-- critique --")
    print(json.dumps(result.critique.model_dump(), indent=2, ensure_ascii=False))
    print("\n-- arbitration --")
    print(json.dumps(result.arbitration.model_dump(), indent=2, ensure_ascii=False))
    print("\n-- trace --")
    for step in result.trace:
        print(f"  [{step.status}] {step.agent} ({step.role}): {step.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
