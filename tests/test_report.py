"""Feature E: PDF report generation."""
from app.generators.report import _logo_data_uri


def test_logo_data_uri_returns_png_data_uri_or_empty():
    uri = _logo_data_uri()
    # Either the bundled logo resolves to a base64 PNG data URI, or (if the asset
    # is absent in this checkout) an empty string so the header degrades to text.
    assert uri == "" or uri.startswith("data:image/png;base64,")
