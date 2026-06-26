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
