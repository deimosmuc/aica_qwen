# tests/test_comparison.py
"""The comparison service (multi-agent vs single-agent)."""
from app.models.schemas import Comparison
from app.services.comparison import run_comparison
from app.services.config import Settings

TEXT = "A 24V industrial board with an STM32, USB-C and RS485 and status LEDs."


def _mock_settings():
    return Settings(qwen_api_key="")  # mock_mode True


def test_mock_comparison_shows_multi_ahead():
    cmp = run_comparison(TEXT, _mock_settings())
    assert isinstance(cmp, Comparison)
    assert cmp.mode == "mock"
    assert cmp.total == 12
    assert cmp.multi_score > cmp.single_score
    assert cmp.delta == cmp.multi_score - cmp.single_score


def test_mock_comparison_concern_flags():
    cmp = run_comparison(TEXT, _mock_settings())
    by_id = {c.id: c for c in cmp.concerns}
    # The pipeline's Critic surfaces surge protection; the single-pass mock does not.
    assert by_id["input_protection"].covered_multi is True
    assert by_id["input_protection"].covered_single is False


def test_mock_comparison_is_labelled_illustrative():
    cmp = run_comparison(TEXT, _mock_settings())
    assert cmp.notice is not None
    assert "illustrative" in cmp.notice.lower()
    assert cmp.multi_calls == 4
    assert cmp.single_calls == 0
