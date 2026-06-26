"""Convert a PDF (e.g. a kicad-cli schematic export) into one PNG per page.

Usage:
    python tools/pdf2png.py <input.pdf> [output_dir] [dpi]

Part of the KiCad render feedback loop:
    kicad-cli sch export pdf  ->  this script  ->  readable PNGs
"""
import sys
from pathlib import Path

import fitz  # PyMuPDF


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else pdf_path.parent
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 150

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    written = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=dpi)
        out = out_dir / f"{pdf_path.stem}-p{i}.png"
        pix.save(out)
        written.append(out)
    doc.close()

    for w in written:
        print(w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
