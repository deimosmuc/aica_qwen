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


def test_root_has_filled_title_block(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj", generated_date="2026-06-28")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    assert "(title_block" in root
    assert '(company "AI Circuit Architect")' in root
    assert '(rev "DRAFT")' in root
    assert '(date "2026-06-28")' in root


def test_date_omitted_keeps_output_deterministic_across_days(tmp_path):
    # Without an explicit date the title block carries no date line, so the same
    # plan always yields byte-identical files regardless of the wall clock.
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    assert "(date " not in root


def test_subsheets_carry_title_block(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    for sheet in (out / "sheets").glob("*.kicad_sch"):
        text = sheet.read_text(encoding="utf-8")
        assert "(title_block" in text
        assert '(company "AI Circuit Architect")' in text


def test_root_embeds_block_diagram_image(tmp_path):
    # PyMuPDF is a project dependency, so the bitmap embeds in this environment.
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    assert "(image" in root
    assert "(data" in root


def test_root_omits_inter_block_connection_lines(tmp_path):
    result = _result()
    out = generate_scaffold(result, REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    # The embedded block-diagram bitmap already shows the connections, so the root
    # sheet draws bare sub-sheet rectangles — no connection polylines, no colour legend.
    assert "(polyline" not in root
    assert "217 119 6 1" not in root  # the 'power' connection colour must be gone


def test_client_svg_is_embedded_instead_of_fallback(tmp_path):
    # A distinctive client SVG must change the embedded bitmap vs. the Python
    # fallback diagram — i.e. the ELK export actually reaches the schematic.
    client_svg = (
        '<svg viewBox="0 0 300 120" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="0" y="0" width="300" height="120" fill="#ffffff"/>'
        '<rect x="20" y="20" width="120" height="60" rx="8" fill="#E6F1FB" stroke="#2563EB"/>'
        '<text x="80" y="55" text-anchor="middle">MCU</text></svg>'
    )
    a = generate_scaffold(_result(), REQ_TEXT, tmp_path / "a")
    b = generate_scaffold(_result(), REQ_TEXT, tmp_path / "b", architecture_svg=client_svg)
    root_a = (a / "project.kicad_sch").read_text(encoding="utf-8")
    root_b = (b / "project.kicad_sch").read_text(encoding="utf-8")
    assert "(image" in root_b and "(data" in root_b
    assert root_a != root_b  # different diagram → different embedded PNG


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


def test_schematic_has_dfx_note(tmp_path):
    from app.services.mock import mock_run
    from app.generators.kicad import generate_scaffold
    r = mock_run("usb can board")
    generate_scaffold(r, "usb can board", tmp_path, "TestBoard")
    sch = (tmp_path / "TestBoard.kicad_sch").read_text(encoding="utf-8")
    assert "DFT / DFM / BRING-UP" in sch
    assert "fiducial" in sch.lower()


def test_power_sheet_has_real_power_symbols(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    power = (out / "sheets" / "power.kicad_sch").read_text(encoding="utf-8")
    assert '(lib_id "power:' in power
    assert '(symbol "power:GND"' in power
    assert '(lib_id "power:+5V")' in power
    assert '(lib_id "power:GND")' in power


def test_non_power_sheets_stay_placeholders(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    mcu = (out / "sheets" / "mcu.kicad_sch").read_text(encoding="utf-8")
    assert '(lib_id "power:' not in mcu
