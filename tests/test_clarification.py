"""Feature B: adaptive clarification — schema + mock."""
from app.models.schemas import ClarifyOption, ClarifyingQuestion, Requirements


def test_clarifying_question_validates():
    q = ClarifyingQuestion(
        id="power",
        text="Which power source?",
        options=[ClarifyOption(label="USB-C, 5V", detail="simple"), ClarifyOption(label="Li-Ion")],
        select="multi",
        assumption="USB 5V",
    )
    assert q.select == "multi"
    assert q.options[0].label == "USB-C, 5V"
    assert q.options[0].detail == "simple"
    assert q.options[1].detail == ""  # detail defaults to empty


def test_clarifying_question_defaults_to_single_select():
    q = ClarifyingQuestion(id="x", text="?")
    assert q.select == "single"
    assert q.options == []


def test_requirements_backfills_questions_from_clarifications():
    r = Requirements(clarifications=[ClarifyingQuestion(id="p", text="Which supply?")])
    assert r.questions == ["Which supply?"]


def test_requirements_keeps_explicit_questions():
    r = Requirements(
        questions=["explicit one"],
        clarifications=[ClarifyingQuestion(id="p", text="Which supply?")],
    )
    assert r.questions == ["explicit one"]  # explicit questions are NOT overwritten


def test_requirements_sanitizes_malformed_clarifications_from_qwen():
    # A real live qwen response once emitted a corrupted clarifications array:
    # one entry's "options" was a string (truncated JSON), and loose option
    # objects (no id/text) were promoted into the array. This must not crash;
    # the salvageable clarification survives and the junk is dropped.
    r = Requirements.model_validate(
        {
            "requirements": ["ECG front-end"],
            "confidence": 0.9,
            "clarifications": [
                {"id": "rate", "text": "Sample rate?", "options": ":[{"},
                {"label": "250 Hz", "detail": "basic monitoring"},
                {"label": "500 Hz", "detail": "captures fast features"},
            ],
        }
    )
    assert len(r.clarifications) == 1          # only the one with id+text survives
    assert r.clarifications[0].id == "rate"
    assert r.clarifications[0].options == []   # string options coerced to empty list
    assert r.questions == ["Sample rate?"]     # backfill still works


def test_requirements_tolerates_non_list_clarifications():
    r = Requirements.model_validate({"requirements": ["x"], "clarifications": "oops"})
    assert r.clarifications == []


def test_mock_requirements_has_clarifications():
    from app.services.mock import mock_run

    r = mock_run("").requirements
    assert len(r.clarifications) >= 2
    # at least one single and one multi, so the demo exercises both UIs
    assert any(c.select == "single" for c in r.clarifications)
    assert any(c.select == "multi" for c in r.clarifications)
    # every clarification offers concrete options and a fallback assumption
    assert all(c.options for c in r.clarifications)
    assert all(c.assumption for c in r.clarifications)
    # questions are backfilled so the legacy "Open questions" chip still counts
    assert len(r.questions) == len(r.clarifications)
