# tests/test_rubric.py
"""Comparison rubric: deterministic concern detection."""
from app.services.rubric import RUBRIC, coverage, score


def test_detects_present_concern():
    s = score("TODO: add TVS surge protection on the 24V input")
    assert s["input_protection"] is True


def test_absent_concern_is_false():
    s = score("Just a microcontroller and a connector.")
    assert s["input_protection"] is False
    assert s["reset"] is False


def test_word_boundary_avoids_false_match():
    # "scheduled" must NOT trigger the short token "led" (testability).
    assert score("the build is scheduled")["testability"] is False
    # "forward" must NOT trigger "swd" (debug_access).
    assert score("look forward")["debug_access"] is False


def test_rubric_has_twelve_concerns():
    assert len(RUBRIC) == 12
    assert len({c.id for c in RUBRIC}) == 12


def test_coverage_counts_distinct_concerns():
    text = "SWD debug header and a reset circuit"
    s = score(text)
    assert s["debug_access"] is True
    assert s["reset"] is True
    assert coverage(text) == sum(s.values())
