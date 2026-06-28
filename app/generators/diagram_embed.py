"""Embed the architecture block diagram into a KiCad schematic as a bitmap.

The block diagram is produced as an SVG (the same one the PDF report uses). KiCad
schematics can carry a raster image natively via an ``(image ...)`` element whose
payload is base64-encoded PNG. This module is the bridge:

    SVG (string)  --fitz-->  PNG (bytes)  --base64-->  (image ...) S-expression

Everything is best-effort: if PyMuPDF cannot rasterise the SVG (or is missing),
``svg_to_png`` returns ``None`` and the caller simply omits the image — exactly
how the rest of the pipeline treats previews. The functions are pure and
independently testable.
"""
from __future__ import annotations

import base64

# A PNG embedded at this DPI, displayed in KiCad with scale 1.0, renders at
# (pixels / DPI * 25.4) mm. We render at a fixed DPI so the on-sheet size is a
# deterministic function of the SVG's aspect ratio (see _SCALE_FOR_WIDTH).
_RENDER_DPI = 150
_PX_PER_MM = _RENDER_DPI / 25.4


def svg_to_png(svg: str, dpi: int = _RENDER_DPI) -> bytes | None:
    """Rasterise an SVG string to PNG bytes. Best-effort: ``None`` on any failure."""
    try:
        import fitz  # PyMuPDF, already a project dependency

        doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
        try:
            pix = doc[0].get_pixmap(dpi=dpi)
            return pix.tobytes("png")
        finally:
            doc.close()
    except Exception:
        return None


def png_pixel_size(png: bytes) -> tuple[int, int] | None:
    """Return (width, height) in pixels from a PNG's IHDR, or None if not a PNG."""
    if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width = int.from_bytes(png[16:20], "big")
    height = int.from_bytes(png[20:24], "big")
    return width, height


def scale_for_width(png: bytes, target_width_mm: float) -> float:
    """KiCad ``scale`` factor that renders ``png`` at ``target_width_mm`` wide.

    At scale 1.0 the bitmap is (pixels / _PX_PER_MM) mm wide; we solve for the
    factor that hits the requested width. Falls back to 1.0 for a non-PNG input.
    """
    size = png_pixel_size(png)
    if not size or size[0] == 0:
        return 1.0
    natural_mm = size[0] / _PX_PER_MM
    return round(target_width_mm / natural_mm, 4)


def image_height_mm(png: bytes, target_width_mm: float) -> float:
    """On-sheet height (mm) the image occupies when scaled to ``target_width_mm``."""
    size = png_pixel_size(png)
    if not size or size[0] == 0:
        return 0.0
    return round(target_width_mm * size[1] / size[0], 2)


def fit_box(png: bytes, max_w_mm: float, max_h_mm: float) -> tuple[float, float, float]:
    """Fit the image inside a ``max_w_mm`` x ``max_h_mm`` box, preserving aspect.

    Returns ``(width_mm, height_mm, scale)``. Tall diagrams become height-bound,
    wide ones width-bound — so a near-square ELK layout no longer dominates the
    sheet. Falls back to a width-bound 2:1 guess for a non-PNG input.
    """
    size = png_pixel_size(png)
    if not size or size[0] == 0 or size[1] == 0:
        return (max_w_mm, round(max_w_mm / 2, 2), 1.0)
    natural_w = size[0] / _PX_PER_MM
    natural_h = size[1] / _PX_PER_MM
    scale = min(max_w_mm / natural_w, max_h_mm / natural_h)
    return (round(natural_w * scale, 2), round(natural_h * scale, 2), round(scale, 4))


def _b64_lines(data: bytes, width: int = 76) -> list[str]:
    b64 = base64.b64encode(data).decode("ascii")
    return [b64[i : i + width] for i in range(0, len(b64), width)]


def kicad_image_element(
    png: bytes, *, at_x: float, at_y: float, scale: float, uuid: str, indent: str = "\t"
) -> str:
    """Render a KiCad v9 ``(image ...)`` S-expression with the PNG embedded.

    ``at_x``/``at_y`` are the image *centre* on the sheet (mm). Indentation uses
    tabs to match the surrounding template files.
    """
    i1, i2, i3 = indent, indent * 2, indent * 3
    lines = [
        f"{i1}(image",
        f"{i2}(at {round(at_x, 2)} {round(at_y, 2)})",
        f"{i2}(scale {scale})",
        f'{i2}(uuid "{uuid}")',
        f"{i2}(data",
    ]
    lines += [f'{i3}"{chunk}"' for chunk in _b64_lines(png)]
    lines += [f"{i2})", f"{i1})"]
    return "\n".join(lines)
