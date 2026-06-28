"""Power-sheet generation: map architecture power rails to verified KiCad
power-port symbols and emit the Power sub-sheet body.

Symbol geometry is NEVER synthesised — we embed fragments vendored from KiCad's
own power.kicad_sym (see tools/extract_power_symbols.py / data/power_symbols.kicad_sym).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

_STANDARD = {"+5V", "+3V3", "+12V", "+24V", "+1V8", "+1V2", "+2V5",
             "GND", "GNDA", "GNDD", "VCC", "VDD", "PWR_FLAG"}
# Keys MUST already be in _canon() form (UPPER-case, no whitespace) or the lookup is dead.
_ALIASES = {"+3.3V": "+3V3", "+3.3": "+3V3", "GROUND": "GND", "VSS": "GND",
            "VDC": "VCC"}

_DATA = Path(__file__).resolve().parent / "data" / "power_symbols.kicad_sym"
_UUID_NS = uuid.UUID("a1c17ec7-0000-4000-8000-000000000000")
_GRID = 1.27  # KiCad connection grid (mm); off-grid endpoints trip ERC warnings


def _snap(v: float) -> float:
    """Snap a coordinate to the 1.27 mm connection grid (spike-confirmed required)."""
    return round(round(v / _GRID) * _GRID, 2)


def _det_uuid(project_name: str, key: str) -> str:
    return str(uuid.uuid5(_UUID_NS, f"{project_name}:{key}"))


@dataclass(frozen=True)
class RailSymbol:
    rail: str       # original rail string
    lib_id: str     # e.g. "power:+5V"
    label: str      # on-sheet label / net name to display


def _canon(rail: str) -> str:
    return re.sub(r"\s+", "", rail.strip()).upper()


def map_rail(rail: str) -> RailSymbol:
    raw = rail.strip()
    key = _canon(rail)
    std_by_upper = {s.upper(): s for s in _STANDARD}
    if key in std_by_upper:
        return RailSymbol(raw, f"power:{std_by_upper[key]}", std_by_upper[key])
    if key in _ALIASES:
        std = _ALIASES[key]
        return RailSymbol(raw, f"power:{std}", std)
    m = re.search(r"(\d+)V(\d+)?", key)
    if m:
        whole, frac = m.group(1), m.group(2)
        cand = f"+{whole}V{frac}" if frac else f"+{whole}V"
        if cand.upper() in std_by_upper:
            return RailSymbol(raw, f"power:{std_by_upper[cand.upper()]}", raw)
    if "GND" in key or "GROUND" in key:
        return RailSymbol(raw, "power:GND", raw)
    return RailSymbol(raw, "power:PWR_FLAG", raw)


def _load_fragments() -> dict[str, str]:
    """Parse the vendored library into {lib_id: full (symbol …) fragment}."""
    text = _DATA.read_text(encoding="utf-8")
    frags: dict[str, str] = {}
    i = 0
    while True:
        i = text.find('(symbol "power:', i)
        if i < 0:
            break
        name = text[i + len('(symbol "'):text.find('"', i + len('(symbol "'))]
        depth, j = 0, i
        while j < len(text):
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        frags[name] = text[i:j + 1]
        i = j + 1
    return frags


@dataclass(frozen=True)
class PowerSheetBody:
    lib_symbols: str   # contents for the (lib_symbols …) block
    instances: str     # placed symbol instances + global labels


def power_sheet(rails: list[str], project_name: str, root_uuid: str,
                block_uuid: str) -> PowerSheetBody:
    frags = _load_fragments()
    mapped = [map_rail(r) for r in rails]
    used = {m.lib_id for m in mapped}
    missing = used - set(frags)
    if missing:
        raise KeyError(f"kicad_power: lib_ids not in vendored file: {missing}")
    lib = "\n".join(frags[lib_id] for lib_id in frags if lib_id in used)

    parts: list[str] = []
    x0, y0, dy = _snap(50.0), _snap(50.0), _snap(25.4)  # grid-aligned column
    for n, m in enumerate(mapped):
        ref = f"#PWR{n + 1:02d}"
        at_y = _snap(y0 + n * dy)
        sym_uuid = _det_uuid(project_name, f"pwr-sym:{block_uuid}:{n}")
        pin_uuid = _det_uuid(project_name, f"pwr-pin:{block_uuid}:{n}")
        parts.append(_instance(m, x0, at_y, ref, sym_uuid, pin_uuid,
                               project_name, root_uuid, block_uuid))
        if m.lib_id == "power:PWR_FLAG":
            lbl_uuid = _det_uuid(project_name, f"pwr-lbl:{block_uuid}:{n}")
            parts.append(_global_label(m.label, _snap(x0 + 6.35), at_y, lbl_uuid))
    return PowerSheetBody(lib_symbols=lib, instances="\n".join(parts))


def _instance(m: RailSymbol, x: float, y: float, ref: str, sym_uuid: str,
              pin_uuid: str, project_name: str, root_uuid: str,
              block_uuid: str) -> str:
    val = m.label
    return (
        f'\t(symbol\n'
        f'\t\t(lib_id "{m.lib_id}")\n'
        f'\t\t(at {x} {y} 0)\n'
        f'\t\t(unit 1)\n'
        f'\t\t(exclude_from_sim no)\n'
        f'\t\t(in_bom yes)\n'
        f'\t\t(on_board yes)\n'
        f'\t\t(dnp no)\n'
        f'\t\t(uuid "{sym_uuid}")\n'
        f'\t\t(property "Reference" "{ref}"\n'
        f'\t\t\t(at {x} {_snap(y - 3.81)} 0)\n'
        f'\t\t\t(hide yes)\n'
        f'\t\t\t(effects (font (size 1.27 1.27)))\n'
        f'\t\t)\n'
        f'\t\t(property "Value" "{val}"\n'
        f'\t\t\t(at {_snap(x + 2.54)} {_snap(y - 1.27)} 0)\n'
        f'\t\t\t(effects (font (size 1.27 1.27)) (justify left))\n'
        f'\t\t)\n'
        f'\t\t(property "Footprint" "" (at {x} {y} 0) (hide yes) (effects (font (size 1.27 1.27))))\n'
        f'\t\t(property "Datasheet" "" (at {x} {y} 0) (hide yes) (effects (font (size 1.27 1.27))))\n'
        f'\t\t(pin "1" (uuid "{pin_uuid}"))\n'
        f'\t\t(instances\n'
        f'\t\t\t(project "{project_name}"\n'
        f'\t\t\t\t(path "/{root_uuid}/{block_uuid}"\n'
        f'\t\t\t\t\t(reference "{ref}")\n'
        f'\t\t\t\t\t(unit 1)\n'
        f'\t\t\t\t)\n'
        f'\t\t\t)\n'
        f'\t\t)\n'
        f'\t)'
    )


def _global_label(name: str, x: float, y: float, lbl_uuid: str) -> str:
    return (
        f'\t(global_label "{name}"\n'
        f'\t\t(shape input)\n'
        f'\t\t(at {x} {y} 0)\n'
        f'\t\t(effects (font (size 1.27 1.27)) (justify left))\n'
        f'\t\t(uuid "{lbl_uuid}")\n'
        f'\t)'
    )
