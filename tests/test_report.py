"""Feature E: PDF report generation."""
from app.generators.report import _logo_data_uri


def test_logo_data_uri_returns_png_data_uri_or_empty():
    uri = _logo_data_uri()
    # Either the bundled logo resolves to a base64 PNG data URI, or (if the asset
    # is absent in this checkout) an empty string so the header degrades to text.
    assert uri == "" or uri.startswith("data:image/png;base64,")


from app.generators.report import _derive_title, _report_context
from app.services.mock import mock_run


def test_derive_title_strips_instruction_preamble():
    # The raw imperative prompt must not become the report title.
    assert (
        _derive_title("erstelle mir ein grundgerüst für ein 24V industrial sensor board")
        == "24V industrial sensor board"
    )
    # English preamble + acronym casing preserved.
    assert _derive_title("Please build me a board with an STM32 and RS485") == (
        "Board with an STM32 and RS485"
    )
    # Empty / filler-only input falls back to a generic name.
    assert _derive_title("") == "Circuit Design"
    assert _derive_title("create a circuit") == "Circuit"


from app.generators.report import CATEGORY_STYLE, _category_style, _legend_entries


def test_category_style_covers_all_categories():
    for cat in ["mcu", "sensor", "power", "connectivity", "debug", "status", "other"]:
        s = CATEGORY_STYLE[cat]
        assert set(s) == {"fill", "stroke", "text"}
        assert all(v.startswith("#") for v in s.values())


def test_category_style_unknown_falls_back_to_other():
    assert _category_style("banana") == CATEGORY_STYLE["other"]


def test_legend_entries_lists_present_categories():
    result = mock_run("x")
    result.architecture.blocks[0].category = "power"
    result.architecture.blocks[1].category = "mcu"
    entries = _legend_entries(result)
    labels = [e["label"] for e in entries]
    assert "Power" in labels and "MCU" in labels
    assert all({"label", "fill", "stroke"} <= set(e) for e in entries)


from app.generators.report import (
    _architecture_svg, _floorplan_svg, _wrap_label,
)


def test_wrap_label_breaks_long_text():
    lines = _wrap_label("Sensor Front-End Conditioning Block", 14)
    assert len(lines) >= 2 and all(len(ln) <= 14 for ln in lines)
    assert _wrap_label("MCU", 14) == ["MCU"]


def test_architecture_svg_colours_by_category_no_diagonals():
    svg = _architecture_svg(mock_run("x"))
    assert "#E6F1FB" in svg   # mcu fill
    assert "#FEF3C7" in svg   # power fill
    assert "<polyline" in svg  # orthogonal edges, not diagonal centre-to-centre lines


def test_floorplan_renders_zones_with_separation():
    svg = _floorplan_svg(mock_run("x"))
    assert "Power Entry" in svg or "MCU Core" in svg
    assert "stroke-dasharray" in svg   # dashed keep-out line for separation


def test_floorplan_falls_back_without_zones():
    r = mock_run("x")
    r.pcb_readiness.floorplan_zones = []
    svg = _floorplan_svg(r)
    assert svg.startswith("<svg")


def test_report_context_exposes_candidate_cards_and_legend():
    ctx = _report_context(mock_run("x"), "A board", "project")
    cards = ctx["component_choices"]
    assert cards and cards[0]["component_type"]
    rec = [c for c in cards[0]["candidates"] if c["recommended"]]
    assert len(rec) == 1 and 0 <= rec[0]["score"] <= 5
    assert rec[0]["stars"].count("★") >= 1
    assert ctx["legend"]


def test_report_context_title_override():
    r = mock_run("x")  # mock requirements carry a concise title ("Industrial Sensor Board")
    # An explicit project name wins over everything (F1-B).
    assert _report_context(r, "build me a 24V board", "project",
                           title="Falcon Sensor Hub")["title"] == "Falcon Sensor Hub"
    # Blank user title -> the agent's concise title wins next.
    assert _report_context(r, "build me a 24V board", "project",
                           title="   ")["title"] == r.requirements.title
    # No user title and no agent title -> heuristic fallback from the raw request.
    r.requirements.title = ""
    assert _report_context(r, "build me a 24V board", "project")["title"] == \
        _derive_title("build me a 24V board")


def test_report_template_renders_html_with_candidate_cards():
    """Render the Jinja template to HTML (no WeasyPrint) to catch template errors."""
    from app.generators.report import _jinja_env
    ctx = _report_context(mock_run("x"), "A 24V board", "project")
    ctx["architecture_svg"] = _architecture_svg(mock_run("x"))
    ctx["floorplan_svg"] = _floorplan_svg(mock_run("x"))
    html = _jinja_env.get_template("report.html.j2").render(**ctx)
    assert "Component Candidates" in html
    assert "Recommended" in html           # recommended badge present (English only)
    assert "STM32G0B1" in html             # recommended MCU part rendered
    assert 'class="legend"' in html        # category legend rendered


def test_report_context_core_fields():
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    ctx = _report_context(result, "A 24V industrial board with an STM32 and RS485.", "project")

    # Stats come straight from pcb_readiness.
    assert ctx["layerstack"] == "4-layer"
    assert ctx["net_class_count"] == 4
    assert ctx["min_clearance_mm"] == 0.2
    assert ctx["open_todo_count"] == len(result.arbitration.todo)

    # Net-class rows preserve order and key fields.
    assert [r["name"] for r in ctx["net_classes"]] == ["PWR", "Signal", "USB", "RS485"]
    assert ctx["net_classes"][0]["nets"]  # non-empty

    # Package hints are flattened to component -> package.
    assert ctx["package_hints"][0]["component_type"] == "STM32 MCU"

    # Global via constraints surface for the footer caption.
    assert ctx["via_drill_mm"] == 0.4
    assert ctx["via_annular_ring_mm"] == 0.15

    # Summary bullets include the human-review and todo items.
    bullet_text = " ".join(ctx["summary_bullets"])
    for item in result.arbitration.human_review:
        assert item in bullet_text


def test_report_context_handles_missing_pcb():
    result = mock_run("x")
    result.pcb_readiness = None
    ctx = _report_context(result, "x", "project")
    # Degrades to safe defaults instead of raising.
    assert ctx["layerstack"] == "—"
    assert ctx["net_class_count"] == 0
    assert ctx["net_classes"] == []
    assert ctx["package_hints"] == []


from app.generators.report import _architecture_svg


def test_architecture_svg_contains_block_labels():
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    svg = _architecture_svg(result)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # Every block name should appear as a label.
    for block in result.architecture.blocks:
        assert block.name in svg


def test_architecture_svg_placeholder_when_empty():
    result = mock_run("x")
    result.architecture.blocks = []
    svg = _architecture_svg(result)
    assert svg.startswith("<svg")
    assert "unavailable" in svg.lower()


from app.generators.report import _floorplan_svg


def test_floorplan_svg_has_outline_and_zones():
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    svg = _floorplan_svg(result)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # Board outline rect present.
    assert "<rect" in svg
    # At least the first few block names are placed as zone labels.
    assert result.architecture.blocks[0].name in svg


def test_floorplan_svg_placeholder_when_empty():
    result = mock_run("x")
    # Placeholder only when there is nothing to draw: no zones AND no blocks.
    result.pcb_readiness.floorplan_zones = []
    result.architecture.blocks = []
    svg = _floorplan_svg(result)
    assert svg.startswith("<svg")
    assert "unavailable" in svg.lower()


import pytest

from app.generators.report import generate_report_pdf


def test_generate_report_pdf_returns_pdf_bytes():
    # WeasyPrint may be installed yet fail to import because its native system
    # libraries (Pango/Cairo/GObject) are absent — on Windows this surfaces as an
    # OSError, not an ImportError, so importorskip alone is not enough. Skip on
    # either so the suite stays green wherever the libs are missing.
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"WeasyPrint system libs not installed in this environment: {exc}")
    result = mock_run("A 24V industrial board with an STM32 and RS485.")
    pdf = generate_report_pdf(result, "A 24V industrial board with an STM32 and RS485.", "project")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_report_context_groups_dfx():
    ctx = _report_context(mock_run("x"), "A board", "project")
    groups = ctx["dfx_groups"]
    keys = [g["key"] for g in groups]
    assert keys == ["testability", "dfm", "bringup"]
    for g in groups:
        for it in g["items"]:
            assert it["marker"] in ("✓", "➜", "⚠")


def test_report_template_renders_dfx_section():
    from app.generators.report import _jinja_env
    ctx = _report_context(mock_run("x"), "A 24V board", "project")
    ctx["architecture_svg"] = "<svg/>"; ctx["floorplan_svg"] = "<svg/>"
    html = _jinja_env.get_template("report.html.j2").render(**ctx)
    assert "Design for Test" in html
    assert "fiducials" in html.lower()


def test_report_context_persona_label():
    ctx = _report_context(mock_run("x"), "A board", "project", persona="student")
    assert ctx["persona_label"] == "Student"
    ctx2 = _report_context(mock_run("x"), "A board", "project")
    assert ctx2["persona_label"] == ""


def test_report_template_renders_persona_label():
    from app.generators.report import _jinja_env
    ctx = _report_context(mock_run("x"), "A 24V board", "project", persona="maker")
    ctx["architecture_svg"] = "<svg/>"; ctx["floorplan_svg"] = "<svg/>"
    html = _jinja_env.get_template("report.html.j2").render(**ctx)
    assert "Audience: Maker" in html
