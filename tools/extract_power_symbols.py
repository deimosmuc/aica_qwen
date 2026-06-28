"""Vendor verified power-symbol lib_symbols fragments from KiCad's shipped library.

Run once (and whenever the rail set changes):
    python tools/extract_power_symbols.py
Writes app/generators/data/power_symbols.kicad_sym — these fragments are embedded
verbatim into generated Power sheets, so we never synthesise symbol geometry.
"""
from pathlib import Path

SRC = Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols\power.kicad_sym")
OUT = (Path(__file__).resolve().parent.parent / "app" / "generators" / "data"
       / "power_symbols.kicad_sym")
RAILS = ["+5V", "+3V3", "+3.3V", "+12V", "+24V", "+1V8", "+1V2", "+2V5",
         "GND", "GNDA", "GNDD", "VCC", "VDD", "PWR_FLAG"]


def _extract(text: str, name: str) -> str:
    needle = f'(symbol "{name}"'
    i = text.find(needle)
    if i < 0:
        raise SystemExit(f"symbol {name!r} not found in {SRC}")
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        j += 1
    raise SystemExit(f"unbalanced parens extracting {name!r}")


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    frags = []
    for name in RAILS:
        frag = _extract(text, name)
        # Prefix only the top-level symbol name with the 'power:' library nickname.
        frag = frag.replace(f'(symbol "{name}"', f'(symbol "power:{name}"', 1)
        frags.append(frag)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(frags) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(frags)} symbols, {OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
