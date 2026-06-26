"""API Guard — the single chokepoint every Qwen call must pass through.

It enforces four things the user asked for:
- sensible   : reject empty / junk / oversized input before any call
- purposeful : cache identical requests so they are never paid for twice
- sparse     : cap the answer length per call
- not costly : hard budget cap (USD) with a pre-call cost estimate, plus
               per-minute / per-day rate limits and a kill switch

State (spend + call history + cache) is persisted to disk so limits survive a
restart. When a limit is hit the guard raises GuardBlocked; the orchestrator
catches that and falls back to Mock Mode with a clear notice to the user.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Callable

from app.services.config import Settings


class GuardBlocked(RuntimeError):
    """Raised when a call is refused. `reason` is a short human-readable note."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _estimate_tokens(text: str) -> int:
    # Rough heuristic: ~4 characters per token. Good enough for a pre-estimate.
    return max(1, len(text) // 4)


class ApiGuard:
    def __init__(
        self,
        settings: Settings,
        state_dir: Path | None = None,
        now: Callable[[], float] = time.time,
    ):
        self.s = settings
        self._now = now
        self._lock = threading.Lock()
        self._dir = state_dir or (Path("outputs") / ".guard")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self._dir / "ledger.json"
        self._cache_path = self._dir / "cache.json"
        self._ledger = self._load(self._ledger_path, {"spent_usd": 0.0, "timestamps": []})
        self._cache = self._load(self._cache_path, {})

    # --- persistence -------------------------------------------------------

    @staticmethod
    def _load(path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _save(self):
        self._ledger_path.write_text(json.dumps(self._ledger), encoding="utf-8")
        self._cache_path.write_text(json.dumps(self._cache), encoding="utf-8")

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _key(model: str, system: str, user: str) -> str:
        h = hashlib.sha256(f"{model}\x00{system}\x00{user}".encode("utf-8"))
        return h.hexdigest()

    def _counts(self) -> tuple[int, int]:
        now = self._now()
        ts = self._ledger["timestamps"]
        per_min = sum(1 for t in ts if t > now - 60)
        per_day = sum(1 for t in ts if t > now - 86_400)
        return per_min, per_day

    def _estimate_cost(self, system: str, user: str) -> float:
        in_tok = _estimate_tokens(system) + _estimate_tokens(user)
        out_tok = self.s.guard_max_output_tokens
        return (in_tok / 1000) * self.s.guard_price_in_per_1k + (
            out_tok / 1000
        ) * self.s.guard_price_out_per_1k

    # --- public API --------------------------------------------------------

    def precheck(self, system: str, user: str, model: str) -> dict | None:
        """Validate and authorise a call. Returns a cached response if one
        exists (so no network call is needed), else None to proceed.

        Raises GuardBlocked if the call must not happen.
        """
        if not self.s.guard_enabled:
            return None

        with self._lock:
            text = (user or "").strip()
            if len(text) < self.s.guard_min_input_chars:
                raise GuardBlocked("input too short or empty")
            if len(user) > self.s.guard_max_input_chars:
                raise GuardBlocked(
                    f"input too long ({len(user)} > {self.s.guard_max_input_chars} chars)"
                )

            # Cache hit -> free, no network, no cost.
            cached = self._cache.get(self._key(model, system, user))
            if cached is not None:
                return cached

            per_min, per_day = self._counts()
            if per_min >= self.s.guard_rate_per_minute:
                raise GuardBlocked(f"rate limit: {per_min} calls in the last minute")
            if per_day >= self.s.guard_rate_per_day:
                raise GuardBlocked(f"daily limit: {per_day} calls today")

            estimate = self._estimate_cost(system, user)
            if self._ledger["spent_usd"] + estimate > self.s.guard_budget_usd:
                raise GuardBlocked(
                    f"budget cap reached (${self._ledger['spent_usd']:.4f} spent, "
                    f"${self.s.guard_budget_usd:.2f} cap)"
                )
            return None

    def record(
        self,
        model: str,
        system: str,
        user: str,
        input_tokens: int,
        output_tokens: int,
        response: dict,
    ) -> float:
        """Record actual usage after a successful call and cache the response."""
        cost = (input_tokens / 1000) * self.s.guard_price_in_per_1k + (
            output_tokens / 1000
        ) * self.s.guard_price_out_per_1k
        with self._lock:
            self._ledger["spent_usd"] = round(self._ledger["spent_usd"] + cost, 6)
            self._ledger["timestamps"].append(self._now())
            # Keep the timestamp list bounded.
            self._ledger["timestamps"] = self._ledger["timestamps"][-1000:]
            self._cache[self._key(model, system, user)] = response
            self._save()
        return cost

    @property
    def max_output_tokens(self) -> int:
        return self.s.guard_max_output_tokens

    def status(self) -> dict:
        with self._lock:
            per_min, per_day = self._counts()
            spent = self._ledger["spent_usd"]
            return {
                "enabled": self.s.guard_enabled,
                "spent_usd": round(spent, 6),
                "budget_usd": self.s.guard_budget_usd,
                "remaining_usd": round(max(0.0, self.s.guard_budget_usd - spent), 6),
                "calls_last_minute": per_min,
                "calls_today": per_day,
                "rate_per_minute": self.s.guard_rate_per_minute,
                "rate_per_day": self.s.guard_rate_per_day,
                "blocked": spent >= self.s.guard_budget_usd,
            }
