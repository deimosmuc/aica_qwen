"""Unit tests for the block-diagram → KiCad bitmap bridge."""
from app.generators import diagram_embed as de

_SVG = (
    '<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="10" y="10" width="180" height="80" fill="#E6F1FB" stroke="#2563EB"/>'
    '<text x="100" y="55" text-anchor="middle">MCU</text></svg>'
)


def test_svg_to_png_returns_png_bytes():
    png = de.svg_to_png(_SVG)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_svg_to_png_best_effort_on_garbage():
    assert de.svg_to_png("not an svg at all") is None


def test_png_pixel_size_reads_ihdr():
    png = de.svg_to_png(_SVG)
    w, h = de.png_pixel_size(png)
    assert w > 0 and h > 0
    assert w > h  # the 2:1 viewBox stays wider than tall


def test_png_pixel_size_rejects_non_png():
    assert de.png_pixel_size(b"nope") is None


def test_scale_for_width_hits_target():
    png = de.svg_to_png(_SVG)
    w_px, _ = de.png_pixel_size(png)
    scale = de.scale_for_width(png, 120.0)
    # natural_mm * scale should reproduce the target width.
    natural_mm = w_px / de._PX_PER_MM
    assert abs(natural_mm * scale - 120.0) < 0.5


def test_image_height_preserves_aspect_ratio():
    png = de.svg_to_png(_SVG)
    w_px, h_px = de.png_pixel_size(png)
    h_mm = de.image_height_mm(png, 120.0)
    assert abs(h_mm - 120.0 * h_px / w_px) < 0.1


def test_fit_box_caps_tall_diagram_by_height():
    # A near-square diagram must be height-bound, not width-bound, so it does not
    # dominate the sheet.
    png = de.svg_to_png(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="0" y="0" width="100" height="100" fill="#eee"/></svg>'
    )
    w, h, scale = de.fit_box(png, 120.0, 44.0)
    assert h <= 44.0 + 0.1
    assert w <= 120.0 + 0.1
    assert abs(w - h) < 1.0  # 1:1 source stays square


def test_fit_box_caps_wide_diagram_by_width():
    w, h, scale = de.fit_box(de.svg_to_png(_SVG), 120.0, 44.0)  # _SVG is 2:1
    assert w <= 120.0 + 0.1
    assert h <= 44.0 + 0.1


def test_kicad_image_element_is_balanced_and_embeds_data():
    png = de.svg_to_png(_SVG)
    el = de.kicad_image_element(png, at_x=148.5, at_y=42.0, scale=0.5, uuid="u-1")
    assert el.count("(") == el.count(")")
    assert "(image" in el and "(data" in el
    assert '(uuid "u-1")' in el
    assert "(at 148.5 42.0)" in el


def test_transparent_bg_neutralises_background_rect():
    svg = ('<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg">'
           '<rect x="0" y="0" width="10" height="10" fill="#ffffff"/>'
           '<rect x="1" y="1" width="3" height="3" fill="#E6F1FB"/></svg>')
    out = de.transparent_bg(svg)
    assert 'fill="none"' in out            # background neutralised
    assert '#E6F1FB' in out                # category box untouched
    assert out.count('fill="none"') == 1   # only the first (background) rect


def test_transparent_bg_handles_f8fafc_and_no_bg():
    assert 'fill="none"' in de.transparent_bg('<svg><rect fill="#f8fafc"/></svg>')
    nobg = '<svg><rect fill="#E6F1FB"/></svg>'
    assert de.transparent_bg(nobg) == nobg  # nothing to strip


def test_svg_to_png_transparent_returns_png():
    png = de.svg_to_png(_SVG, transparent=True)
    assert png is not None and png[:8] == b"\x89PNG\r\n\x1a\n"
