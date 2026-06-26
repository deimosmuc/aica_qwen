"""Thin client for the Qwen Cloud API (OpenAI-compatible endpoint).

Notes baked in from the Qwen docs:
- We request `response_format={"type": "json_object"}` for structured output.
- Qwen requires the literal word "json" to appear in the messages when using
  that format, otherwise the API returns an error — we ensure it does.
- Use a non-thinking model (e.g. qwen-plus); thinking mode does not support
  json_object output.
"""
from __future__ import annotations

import json

import httpx

from app.services.config import Settings
from app.services.guard import ApiGuard


class QwenError(RuntimeError):
    """Raised when the Qwen API call fails or returns something unusable."""


class QwenTruncatedError(QwenError):
    """Raised when the model hit the output-token cap and the answer was cut off
    mid-stream (finish_reason == "length"). Distinct from being unreachable: the
    API was reached and answered — the answer was just too long for the cap."""


class QwenClient:
    def __init__(self, settings: Settings, guard: ApiGuard | None = None, timeout: float = 60.0):
        self._api_key = settings.qwen_api_key
        self._base_url = settings.qwen_base_url.rstrip("/")
        self._model = settings.qwen_model
        self._timeout = timeout
        self._guard = guard or ApiGuard(settings)

    def chat_json(self, system: str, user: str, model: str | None = None) -> dict:
        """Send a system+user prompt and return the parsed JSON object.

        Every call goes through the API Guard first: it may serve a cached
        result (no network, no cost) or refuse the call via GuardBlocked.
        """
        # Guarantee the "json" keyword requirement is satisfied.
        system = system.rstrip() + "\n\nReturn your answer as a single valid JSON object."
        model = model or self._model

        # Guard: validate, check budget/rate, or return a cached response.
        cached = self._guard.precheck(system, user, model)
        if cached is not None:
            return cached

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self._guard.max_output_tokens,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"

        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:300] if e.response is not None else ""
            raise QwenError(f"Qwen API returned {e.response.status_code}: {body}") from e
        except httpx.HTTPError as e:
            raise QwenError(f"Qwen request failed: {e}") from e

        data = resp.json()
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise QwenError(f"Unexpected Qwen response shape: {str(data)[:300]}") from e

        # The API answered, but if it hit the output-token cap the JSON is cut off
        # mid-stream — flag that distinctly so callers don't report it as "unreachable".
        if choice.get("finish_reason") == "length":
            raise QwenTruncatedError(
                f"answer exceeded the {self._guard.max_output_tokens}-token output cap "
                "and was cut off"
            )

        result = _parse_json_object(content)

        # Record real token usage so the budget ledger is accurate; fall back
        # to an estimate if the API omits the usage block.
        usage = data.get("usage") or {}
        input_tokens = usage.get("prompt_tokens") or (len(system) + len(user)) // 4
        output_tokens = usage.get("completion_tokens") or len(content) // 4
        self._guard.record(model, system, user, input_tokens, output_tokens, result)

        return result


def _parse_json_object(content: str) -> dict:
    """Parse model output into a dict, tolerating accidental code fences."""
    text = content.strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} span if the model wrapped the JSON.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise QwenError(f"Qwen did not return JSON: {content[:200]}")
        try:
            result = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise QwenError(f"Qwen did not return valid JSON: {content[:200]}") from e

    if not isinstance(result, dict):
        raise QwenError(f"Qwen returned a non-object JSON value: {content[:200]}")
    return result
