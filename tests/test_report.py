"""Feature E: PDF report generation."""
from app.generators.report import _logo_data_uri


def test_logo_data_uri_returns_png_data_uri_or_empty():
    uri = _logo_data_uri()
    # Either the bundled logo resolves to a base64 PNG data URI, or (if the asset
    # is absent in this checkout) an empty string so the header degrades to text.
    assert uri == "" or uri.startswith("data:image/png;base64,")


from app.generators.report import _report_context
from app.services.mock import mock_run


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
