"""QwenClient: distinguishing a truncated answer from an unreachable API."""
import pytest

from app.services.config import Settings
from app.services.guard import ApiGuard
from app.services.orchestrator import Orchestrator
from app.services.qwen_client import QwenClient, QwenError, QwenTruncatedError


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _client(tmp_path, monkeypatch, payload):
    settings = Settings(qwen_api_key="x")
    guard = ApiGuard(settings, state_dir=tmp_path, now=lambda: 1000.0)
    monkeypatch.setattr(
        "app.services.qwen_client.httpx.post", lambda *a, **k: _FakeResp(payload)
    )
    return QwenClient(settings, guard=guard)


def test_truncated_answer_raises_truncated_error(tmp_path, monkeypatch):
    # Model hit the output cap: valid-looking start, but finish_reason == "length".
    payload = {
        "choices": [{"message": {"content": '{"blocks": [{"name": "AFE'}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 6000},
    }
    client = _client(tmp_path, monkeypatch, payload)
    with pytest.raises(QwenTruncatedError):
        client.chat_json("sys", "A complex 24V board with an STM32")


def test_complete_answer_parses(tmp_path, monkeypatch):
    payload = {
        "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 5},
    }
    client = _client(tmp_path, monkeypatch, payload)
    assert client.chat_json("sys", "A 24V board with an STM32") == {"ok": True}


def test_truncated_is_a_qwen_error(tmp_path, monkeypatch):
    # Subclass relationship keeps existing `except QwenError` callers working.
    assert issubclass(QwenTruncatedError, QwenError)


def test_orchestrator_reports_cutoff_not_unreachable(tmp_path, monkeypatch):
    """A truncating client yields a Mock fallback whose notice says 'cut off',
    not the misleading 'unreachable'."""
    settings = Settings(qwen_api_key="x")

    class _Truncating:
        def chat_json(self, system, user, model=None):
            raise QwenTruncatedError("answer exceeded the 6000-token output cap and was cut off")

    res = Orchestrator(settings, client=_Truncating()).run("A 24V board with an STM32")
    assert res.mode == "mock"
    assert "cut off" in res.notice
    assert "unreachable" not in res.notice


def test_client_feeds_meter_after_a_call(tmp_path, monkeypatch):
    from app.services.metering import RunMeter
    payload = {
        "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 123, "completion_tokens": 45},
    }
    settings = Settings(qwen_api_key="x")
    guard = ApiGuard(settings, state_dir=tmp_path, now=lambda: 1000.0)
    monkeypatch.setattr(
        "app.services.qwen_client.httpx.post", lambda *a, **k: _FakeResp(payload)
    )
    meter = RunMeter()
    client = QwenClient(settings, guard=guard, meter=meter)
    client.chat_json("sys", "A 24V board with an STM32")
    snap = meter.snapshot()
    assert snap.calls == 1
    assert snap.input_tokens == 123
    assert snap.output_tokens == 45
    assert snap.cost_usd > 0
