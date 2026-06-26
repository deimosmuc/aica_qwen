"""Milestone 6: the KiCad scaffold generator."""
import json

from app.generators.kicad import generate_scaffold
from app.models.schemas import (
    Arbitration,
    Architecture,
    Block,
    Critique,
    Requirements,
    RunResponse,
    TraceStep,
)
from app.services.mock import mock_run

REQ_TEXT = "A 24V industrial board with an STM32 and RS485."


def _result() -> RunResponse:
    return mock_run(REQ_TEXT)


def test_generates_all_expected_files(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    expected = [
        "project.kicad_pro",
        "project.kicad_sch",
        "architecture.md",
        "todo.md",
        "assumptions.md",
        "README.md",
        "agent_trace.json",
    ]
    for name in expected:
        assert (out / name).is_file(), f"missing {name}"
    # One subsheet per block.
    n_blocks = len(_result().architecture.blocks)
    assert len(list((out / "sheets").glob("*.kicad_sch"))) == n_blocks


def test_root_references_every_subsheet(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    for sheet_file in (out / "sheets").glob("*.kicad_sch"):
        assert f"sheets/{sheet_file.name}" in root


def test_project_file_lists_root_and_all_blocks(tmp_path):
    result = _result()
    out = generate_scaffold(result, REQ_TEXT, tmp_path / "proj")
    pro = json.loads((out / "project.kicad_pro").read_text(encoding="utf-8"))
    # Root + one entry per block.
    assert len(pro["sheets"]) == 1 + len(result.architecture.blocks)
    assert pro["sheets"][0][1] == "Root"


def test_every_kicad_file_has_valid_header(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    files = [out / "project.kicad_sch", *(out / "sheets").glob("*.kicad_sch")]
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert text.startswith("(kicad_sch")
        assert "(version 20250114)" in text
        assert text.count("(") == text.count(")"), f"unbalanced parens in {f.name}"


def test_todo_and_assumptions_carry_arbitration_data(tmp_path):
    result = _result()
    out = generate_scaffold(result, REQ_TEXT, tmp_path / "proj")
    todo = (out / "todo.md").read_text(encoding="utf-8")
    for item in result.arbitration.todo:
        assert item in todo
    for item in result.arbitration.human_review:
        assert item in todo
    assumptions = (out / "assumptions.md").read_text(encoding="utf-8")
    for item in result.arbitration.accepted_assumptions:
        assert item in assumptions


def test_output_is_deterministic(tmp_path):
    a = generate_scaffold(_result(), REQ_TEXT, tmp_path / "a")
    b = generate_scaffold(_result(), REQ_TEXT, tmp_path / "b")
    for name in ["project.kicad_pro", "project.kicad_sch", "architecture.md"]:
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_special_characters_do_not_break_kicad_syntax(tmp_path):
    # A block name with a quote/backslash must be escaped, not corrupt the file.
    arch = Architecture(
        blocks=[Block(name='Power "HV"\\X', sheet="power.kicad_sch", purpose='24V "main"')],
        power=["VIN_24V"],
    )
    result = RunResponse(
        mode="mock",
        requirements=Requirements(),
        architecture=arch,
        critique=Critique(),
        arbitration=Arbitration(approved_architecture=arch),
        trace=[TraceStep(agent="A", role="r", summary="s")],
    )
    out = generate_scaffold(result, REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    assert root.count("(") == root.count(")")
    assert '\\"HV\\"' in root  # the quotes were escaped
