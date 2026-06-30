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
    # Curated, json_object-capable models the UI may select. "thinking" models
    # are excluded — they don't support json_object output, which the pipeline needs.
    qwen_models: list[str] = ["qwen-plus", "qwen-max", "qwen-turbo"]
    # Per-call HTTP timeout. qwen-max on complex prompts (large max_tokens) can
    # take well over a minute; a tight timeout silently drops the run to Mock.
    qwen_timeout_s: float = 180.0

    app_name: str = "AI Circuit Architect"
    app_version: str = "0.1.0"

    # --- API Guard: keeps Qwen calls sensible, sparse and cheap -------------
    guard_enabled: bool = True
    guard_budget_usd: float = 35.0          # hard total spend cap; then block
    guard_min_input_chars: int = 8          # reject empty / junk input
    # Anti-junk cap on a single call's user prompt. Must comfortably exceed the
    # inter-agent prompts (later agents embed earlier agents' full JSON output,
    # ~10k chars), otherwise the live pipeline degrades to Mock mid-run. Real cost
    # is bounded by guard_budget_usd, not this, so a generous value is safe.
    guard_max_input_chars: int = 32000      # reject oversized prompts
    # Cap answer length per call. Must fit a complex Architect JSON (7+ blocks
    # with connections) or the response truncates → invalid JSON → Mock fallback.
    # 1200 was too tight for hard designs; even 4000 truncated the most block-rich
    # Architect output (e.g. an industrial gateway), so use 6000. Real cost is
    # bounded by the $ budget, not this cap.
    guard_max_output_tokens: int = 6000     # cap answer length per call
    guard_rate_per_minute: int = 15         # runaway-loop backstop
    guard_rate_per_day: int = 250

    # Conservative price ESTIMATES (USD per 1K tokens). Deliberately set a bit
    # high so the budget guard errs on the safe side. Confirm against the
    # current Qwen price page before relying on exact figures.
    guard_price_in_per_1k: float = 0.001
    guard_price_out_per_1k: float = 0.002

    # Per-model price ESTIMATES (USD per 1K tokens). Unknown models fall back to
    # the flat guard_price_*_per_1k above. Confirm against the live Qwen price
    # page before relying on exact figures.
    guard_prices_per_1k: dict[str, dict[str, float]] = {
        "qwen-turbo": {"in": 0.0003, "out": 0.0006},
        "qwen-plus": {"in": 0.001, "out": 0.002},
        "qwen-max": {"in": 0.004, "out": 0.012},
    }

    # --- KiCad CLI: real validation + schematic preview ---------------------
    # kicad-cli is used as a tool (separate subprocess). When it is not present
    # the app degrades gracefully: structural validation still runs and the
    # preview is simply omitted, so the demo never breaks.
    kicad_enabled: bool = True
    kicad_cli_path: str = ""                 # empty -> auto-detect (PATH + known locations)
    kicad_timeout_s: int = 60

    # Where generated KiCad project scaffolds are written and served from.
    output_dir: str = "outputs/projects"

    def resolve_model(self, requested: str | None) -> str:
        """Return the requested model if it is allow-listed, else the default.
        Unknown / empty / None all degrade silently to qwen_model (no error)."""
        return requested if requested in self.qwen_models else self.qwen_model

    @property
    def mock_mode(self) -> bool:
        """True when no real API key is configured -> use prepared example data."""
        return not self.qwen_api_key.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
