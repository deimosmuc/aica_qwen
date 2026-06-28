from app.services.persona import (
    resolve_persona, persona_instruction, persona_label, PERSONA_INSTRUCTIONS,
)


def test_resolve_known_and_default():
    assert resolve_persona("student") == "student"
    assert resolve_persona("maker") == "maker"
    assert resolve_persona("professional") == "professional"
    assert resolve_persona(None) == "professional"      # default
    assert resolve_persona("banana") == "professional"  # unknown -> default


def test_instruction_and_label():
    assert "engineering student" in persona_instruction("student").lower()
    assert "hobbyist maker" in persona_instruction("maker").lower()
    assert "professional hardware engineer" in persona_instruction(None).lower()  # default
    assert persona_label("student") == "Student"
    assert persona_label("banana") == "Professional"


def test_every_persona_has_an_instruction():
    for key in ("professional", "student", "maker"):
        assert key in PERSONA_INSTRUCTIONS and PERSONA_INSTRUCTIONS[key].strip()
