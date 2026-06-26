"""Application configuration and mode detection.

Mock Mode is a core principle: if no QWEN_API_KEY is present, the app must
still work end-to-end using prepared example data, so the demo never breaks.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Qwen / Alibaba Model Studio (OpenAI-compatible endpoint).
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    app_name: str = "AI Circuit Architect"
    app_version: str = "0.1.0"

    # --- API Guard: keeps Qwen calls sensible, sparse and cheap -------------
    guard_enabled: bool = True
    guard_budget_usd: float = 5.0           # hard total spend cap; then block
    guard_min_input_chars: int = 8          # reject empty / junk input
    guard_max_input_chars: int = 8000       # reject oversized prompts
    guard_max_output_tokens: int = 1200     # cap answer length per call
    guard_rate_per_minute: int = 15         # runaway-loop backstop
    guard_rate_per_day: int = 250
    guard_max_calls_per_run: int = 8        # one /run must never exceed this

    # Conservative price ESTIMATES (USD per 1K tokens). Deliberately set a bit
    # high so the budget guard errs on the safe side. Confirm against the
    # current Qwen price page before relying on exact figures.
    guard_price_in_per_1k: float = 0.001
    guard_price_out_per_1k: float = 0.002

    # --- KiCad CLI: real validation + schematic preview ---------------------
    # kicad-cli is used as a tool (separate subprocess). When it is not present
    # the app degrades gracefully: structural validation still runs and the
    # preview is simply omitted, so the demo never breaks.
    kicad_enabled: bool = True
    kicad_cli_path: str = ""                 # empty -> auto-detect (PATH + known locations)
    kicad_timeout_s: int = 60

    # Where generated KiCad project scaffolds are written and served from.
    output_dir: str = "outputs/projects"

    @property
    def mock_mode(self) -> bool:
        """True when no real API key is configured -> use prepared example data."""
        return not self.qwen_api_key.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
