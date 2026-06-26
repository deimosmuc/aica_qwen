# Third-party tools

AI Circuit Architect itself is licensed under the MIT License (see `LICENSE`).
It uses the following third-party tools as separate programs (invoked as
subprocesses), not as linked libraries. Their licenses apply only to those
tools, not to this project's source code.

## KiCad (`kicad-cli`)

- Used for: real validation of the generated scaffold (open/export + ERC) and
  rendering the schematic preview to SVG.
- How: invoked as a separate command-line process (`kicad-cli`). This project
  does not link against KiCad and is not a derivative work of it.
- License: GNU General Public License v3.0 (GPL-3.0).
- Source: https://www.kicad.org/  •  https://gitlab.com/kicad/code/kicad

If a distributed container image bundles KiCad, the KiCad components remain under
GPL-3.0 and their source is available at the link above.

## PyMuPDF (development only)

- Used for: converting rendered PDFs to PNG in the developer verification loop
  (`tools/pdf2png.py`). Not part of the application runtime.
- License: GNU AGPL-3.0 (or commercial). Source: https://github.com/pymupdf/PyMuPDF
