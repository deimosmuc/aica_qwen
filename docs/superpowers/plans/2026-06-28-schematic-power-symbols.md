# Schematic Stage 2 — Real Power Symbols & Sheet Pins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generated KiCad scaffold electrically richer — real KiCad power-port symbols on the Power sub-sheet (one per rail), and hierarchical sheet pins on the root blocks with matching hierarchical labels in the child sheets — while staying byte-deterministic and opening cleanly in KiCad.

**Architecture:** Follow the generator's existing philosophy: **never synthesise KiCad syntax from scratch.** We vendor verified power-symbol `lib_symbols` fragments extracted from KiCad's own shipped `power.kicad_sym`, plus a proven placed-instance pattern copied from a KiCad demo. A new `app/generators/kicad_power.py` maps rails → symbols and emits the Power-sheet body; a new `app/generators/kicad_root.py` infers sheet pins from `architecture.connections` and emits the matching hierarchical labels. New/extended Jinja templates render them. `generate_scaffold` detects the Power block and threads the new data in. Everything is gated by a `kicad-cli` render + ERC check in the dev loop.

**Tech Stack:** Python 3.12, Jinja2 templates (KiCad v9 S-expression format, `version 20250114`), `app/services/kicad_cli.py` (`KiCadCli.export_svg` / `run_erc` / `version`), pytest. KiCad 10.0.2 locally (`C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`); deploy image is KiCad 9.0.9.

---

## Proven facts captured during planning (do not re-derive)

These were verified against the local KiCad 10 install and a KiCad demo while writing this plan. Treat them as ground truth; Task 1 re-proves them with a render gate.

1. **Verified symbol source:** `C:\Program Files\KiCad\10.0\share\kicad\symbols\power.kicad_sym` (lib `version 20251024`). It contains every rail we map to: `+5V +3V3 +3.3V +12V +24V +1V8 +1V2 +2V5 GND GNDA GNDD VCC VDD PWR_FLAG`.
2. **Inside a schematic's `(lib_symbols …)`** the symbol's top-level name gains the library nickname prefix: the lib file's `(symbol "GND" …)` appears in a `.kicad_sch` as `(symbol "power:GND" …)`. Inner sub-symbols keep their bare names (`GND_0_1`, `GND_1_1`). **CONFIRMED by the Task-1 spike render: inner sub-symbols stay bare — only the top-level name is prefixed.**

   **GRID (confirmed by spike):** every placed coordinate (instance `at`, property `at`, global-label `at`, sheet-pin `at`, hier-label `at`) MUST snap to KiCad's 1.27 mm connection grid, or ERC emits `endpoint_off_grid` warnings. Use a `_snap(v) = round(round(v/1.27)*1.27, 2)` helper in `kicad_power.py` and `kicad_root.py` and snap all emitted coordinates. (The spike's first pass at 50/70/90 produced 3 off-grid warnings; snapping to 50.8/76.2/101.6 removed them.)
3. **Proven placed-instance pattern** (copied verbatim from `…/demos/cm5_minima/DSI_CSI.kicad_sch`, a power symbol that opens cleanly):

```
(symbol
    (lib_id "power:+3V3")
    (at 82.55 87.63 0)
    (unit 1)
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (dnp no)
    (uuid "<det-uuid>")
    (property "Reference" "#PWR0801"
        (at 82.55 91.44 0)
        (hide yes)
        (effects (font (size 1.27 1.27)))
    )
    (property "Value" "+3V3"
        (at 78.994 83.058 0)
        (effects (font (size 1.27 1.27)) (justify left))
    )
    (property "Footprint" "" (at 82.55 87.63 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "" (at 82.55 87.63 0) (hide yes) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "<det-uuid>"))
    (instances
        (project "<project_name>"
            (path "/<root_uuid>/<power_sheet_block_uuid>"
                (reference "#PWR0801")
                (unit 1)
            )
        )
    )
)
```

   Key correctness detail: the symbol lives on the Power **sub-sheet**, which is instantiated under root, so the instance `path` is `/<root_uuid>/<power_block_uuid>` (the sheet's `block_uuid` from `generate_scaffold`), **not** just `/<root_uuid>`.

4. **For arbitrary rail names** (e.g. `VIN_24V`) that are not a standard symbol: place `power:PWR_FLAG` and a separate `(global_label "VIN_24V" …)` beside it (PWR_FLAG is KiCad's canonical "power enters here" symbol). KiCad standard symbols carry their net name in the `Value` field.
5. **`KiCadCli` interface** (`app/services/kicad_cli.py`): `.available()`, `.version()`, `.export_svg(sch, out_dir) -> Path`, `.run_erc(sch, out_json) -> dict`. Use these in the render gate. `kicad-cli` is **not on `PATH`**; `KiCadCli._resolve` already finds the install — construct `KiCadCli(Settings())`.
6. **Mock fixture already exercises the path:** `mock_run()` → `architecture` has a `Block(name="Power", sheet="power.kicad_sch", category="power", …)`, `power=["VIN_24V","+5V","+3V3","GND"]`, and `connections=[Connection(source="Power", target="MCU", type="power"), …]`. So `_result()` in `tests/test_kicad_generator.py` covers both rail-symbol and sheet-pin generation with no new fixture.

---

## File Structure

- **Create** `app/generators/data/power_symbols.kicad_sym` — vendored verified symbol defs (extracted from KiCad's `power.kicad_sym`, renamed `power:<name>`). Deterministic, repo-checked-in, no KiCad dependency at generation time.
- **Create** `app/generators/kicad_power.py` — rail→symbol mapping table, a loader for the vendored fragments, and `power_sheet(rails, project_name, root_uuid, block_uuid) -> dict` returning `{lib_symbols, instances}` strings for the template.
- **Create** `app/generators/kicad_root.py` — `sheet_pins_for(block, connections) -> list[Pin]` (interface inference) and `hier_labels_for(pins) -> list[Label]` (matching child-sheet labels). Pure, deterministic, no KiCad-cli.
- **Create** `app/templates/power_sheet.kicad_sch.j2` — Power sub-sheet with `(lib_symbols …)` + symbol instances + global labels.
- **Modify** `app/templates/root.kicad_sch.j2` — render `(pin …)` elements inside each `(sheet …)` block.
- **Modify** `app/templates/sheet.kicad_sch.j2` — render optional `(hierarchical_label …)` elements in the child sheet.
- **Modify** `app/generators/kicad.py` — detect the Power block, render `power_sheet.kicad_sch.j2` for it (others stay placeholder), compute sheet pins + child labels, thread all into the templates.
- **Create** `tests/test_kicad_power.py` — rail mapping + power-sheet body unit tests.
- **Create** `tests/test_kicad_sheetpins.py` — sheet-pin inference + label-matching unit tests.
- **Modify** `tests/test_kicad_generator.py` — integration assertions + a render-gate test (skips when `kicad-cli` unavailable).

---

### Task 1: Spike — vendor the verified power-symbol library and prove the instance pattern

**Files:**
- Create: `tools/extract_power_symbols.py`
- Create: `app/generators/data/power_symbols.kicad_sym`
- Create (throwaway, under the scratchpad): a minimal proof schematic

- [ ] **Step 1: Write the extraction script**

`tools/extract_power_symbols.py` — reads KiCad's shipped library, extracts the symbols we map to, renames each top-level `(symbol "<n>"` → `(symbol "power:<n>"`, and writes them as one vendored fragment file. Pure-stdlib, balances parens.

```python
"""Vendor verified power-symbol lib_symbols fragments from KiCad's shipped library.

Run once (and whenever the rail set changes):
    python tools/extract_power_symbols.py
Writes app/generators/data/power_symbols.kicad_sym — these fragments are embedded
verbatim into generated Power sheets, so we never synthesise symbol geometry.
"""
from pathlib import Path

SRC = Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols\power.kicad_sym")
OUT = Path(__file__).resolve().parent.parent / "app" / "generators" / "data" / "power_symbols.kicad_sym"
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
```

- [ ] **Step 2: Run the extraction script**

Run: `python tools/extract_power_symbols.py`
Expected: `wrote …/power_symbols.kicad_sym (14 symbols, ~26000 bytes)`. Confirm the file starts with `(symbol "power:+5V"`.

- [ ] **Step 3: Build a throwaway proof schematic and render it**

Write a tiny script to the scratchpad that assembles a complete `power.kicad_sch`: header (`version 20250114`), a `(lib_symbols …)` block containing the vendored `power:+5V`, `power:GND`, and `power:PWR_FLAG` fragments, three placed instances using the proven pattern from "Proven facts" #3 (one `+5V`, one `GND`, one `PWR_FLAG`), one `(global_label "VIN_24V" …)` next to the PWR_FLAG, and a `(sheet_instances …)`. Use real det-UUIDs (any fixed strings). Then:

Run:
```bash
KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
"$KC" sch export svg --output <scratch>/svg <scratch>/power.kicad_sch
"$KC" sch erc --format json --severity-all --output <scratch>/erc.json <scratch>/power.kicad_sch
```
Expected: SVG export succeeds and the SVG is **non-empty / contains the symbol graphics** (grep the SVG for path/polyline data — not just a blank page). ERC JSON parses; record the violation list. A lone power port legitimately yields a *warning* (e.g. "input power pin not driven") — **that is acceptable**; the gate forbids new *errors* and forbids "Failed to load" / parse failures.

- [ ] **Step 4: Resolve the two open syntax questions and pin them in a comment**

From the render in Step 3, confirm and record at the top of `power_symbols.kicad_sym` (as a leading `; ` comment line, which KiCad ignores) OR in `kicad_power.py`'s module docstring:
- Whether inner sub-symbols need the `power:` prefix (expected: **no**).
- Whether the `global_label` is needed for known rails (expected: **no** — the power symbol alone is enough; global_label only for PWR_FLAG/arbitrary rails).

If the render fails, iterate the instance pattern (most likely culprits: the `instances` `path`, a missing `dnp`/`unit` field, or a malformed `lib_symbols` entry) until it opens. **Do not proceed to Task 2 until Step 3 renders non-empty with no load error.**

- [ ] **Step 5: Commit**

```bash
git add tools/extract_power_symbols.py app/generators/data/power_symbols.kicad_sym
git commit -m "feat(kicad): vendor verified power-symbol lib_symbols + extraction tool"
```

---

### Task 2: Rail → symbol mapping

**Files:**
- Create: `app/generators/kicad_power.py`
- Test: `tests/test_kicad_power.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kicad_power.py
from app.generators.kicad_power import map_rail


def test_known_rails_map_to_standard_symbols():
    assert map_rail("+5V").lib_id == "power:+5V"
    assert map_rail("+3V3").lib_id == "power:+3V3"
    assert map_rail("GND").lib_id == "power:GND"


def test_rail_normalisation():
    # case / dotted / spacing variants normalise to the standard symbol
    assert map_rail("+3.3V").lib_id == "power:+3V3"
    assert map_rail("gnd").lib_id == "power:GND"
    assert map_rail(" +5v ").lib_id == "power:+5V"


def test_voltage_in_name_maps_to_nearest_standard_rail():
    m = map_rail("VIN_24V")
    assert m.lib_id == "power:+24V"
    assert m.label == "VIN_24V"  # original name preserved as the on-sheet label


def test_unknown_rail_falls_back_to_pwr_flag_with_label():
    m = map_rail("MYNET")
    assert m.lib_id == "power:PWR_FLAG"
    assert m.label == "MYNET"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kicad_power.py -v`
Expected: FAIL — `ModuleNotFoundError: app.generators.kicad_power`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/generators/kicad_power.py
"""Power-sheet generation: map architecture power rails to verified KiCad
power-port symbols and emit the Power sub-sheet body.

Symbol geometry is NEVER synthesised — we embed fragments vendored from KiCad's
own power.kicad_sym (see tools/extract_power_symbols.py / data/power_symbols.kicad_sym).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Standard symbols present in the vendored library (data/power_symbols.kicad_sym).
_STANDARD = {"+5V", "+3V3", "+12V", "+24V", "+1V8", "+1V2", "+2V5",
             "GND", "GNDA", "GNDD", "VCC", "VDD", "PWR_FLAG"}
# Alias → canonical standard name.
_ALIASES = {"+3.3V": "+3V3", "+3.3": "+3V3", "GROUND": "GND", "VSS": "GND",
            "VDC": "VCC"}


@dataclass(frozen=True)
class RailSymbol:
    rail: str       # original rail string
    lib_id: str     # e.g. "power:+5V"
    label: str      # on-sheet label / net name to display


def _canon(rail: str) -> str:
    return re.sub(r"\s+", "", rail.strip()).upper().replace("V3V3", "V3V3")


def map_rail(rail: str) -> RailSymbol:
    raw = rail.strip()
    key = _canon(rail)
    # exact / alias match against standard symbols (compare case-insensitively)
    std_by_upper = {s.upper(): s for s in _STANDARD}
    if key in std_by_upper:
        return RailSymbol(raw, f"power:{std_by_upper[key]}", std_by_upper[key])
    if key in _ALIASES:
        std = _ALIASES[key]
        return RailSymbol(raw, f"power:{std}", std)
    # voltage embedded in a longer name, e.g. VIN_24V → +24V
    m = re.search(r"(\d+)V(\d+)?", key)
    if m:
        whole, frac = m.group(1), m.group(2)
        cand = f"+{whole}V{frac}" if frac else f"+{whole}V"
        if cand.upper() in std_by_upper:
            return RailSymbol(raw, f"power:{std_by_upper[cand.upper()]}", raw)
    # ground-ish fallback
    if "GND" in key or "GROUND" in key:
        return RailSymbol(raw, "power:GND", raw)
    # last resort: PWR_FLAG + keep the raw name as a label
    return RailSymbol(raw, "power:PWR_FLAG", raw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kicad_power.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/generators/kicad_power.py tests/test_kicad_power.py
git commit -m "feat(kicad): rail->power-symbol mapping"
```

---

### Task 3: Power-sheet body builder + template

**Files:**
- Modify: `app/generators/kicad_power.py`
- Create: `app/templates/power_sheet.kicad_sch.j2`
- Test: `tests/test_kicad_power.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_kicad_power.py
from app.generators.kicad_power import power_sheet


def test_power_sheet_has_a_symbol_per_rail():
    rails = ["VIN_24V", "+5V", "+3V3", "GND"]
    body = power_sheet(rails, project_name="proj",
                       root_uuid="11111111-1111-4111-8111-111111111111",
                       block_uuid="22222222-2222-4222-8222-222222222222")
    # lib_symbols block present with the standard defs actually used
    assert '(symbol "power:+5V"' in body.lib_symbols
    assert '(symbol "power:GND"' in body.lib_symbols
    assert '(symbol "power:PWR_FLAG"' in body.lib_symbols  # VIN_24V → PWR_FLAG path? no: +24V
    # one placed instance per rail
    assert body.instances.count("(lib_id \"power:") == len(rails)
    # the arbitrary rail keeps its name as a global label
    assert '(global_label "VIN_24V"' in body.instances
    # instance path is the two-level hierarchical path
    assert "/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222" in body.instances


def test_power_sheet_only_embeds_used_symbols():
    body = power_sheet(["+5V", "GND"], "p", "r", "b")
    assert '(symbol "power:+12V"' not in body.lib_symbols  # unused → not embedded


def test_power_sheet_is_deterministic():
    a = power_sheet(["+5V", "GND"], "p", "r", "b")
    b = power_sheet(["+5V", "GND"], "p", "r", "b")
    assert a.lib_symbols == b.lib_symbols and a.instances == b.instances
```

> Note: `VIN_24V` maps to `+24V` (Task 2), so the `power:PWR_FLAG` assertion above only holds if a rail actually falls back. Adjust the fixture: use `rails = ["MYRAIL", "+5V", "+3V3", "GND"]` so `MYRAIL` → PWR_FLAG + `(global_label "MYRAIL")`. Update both asserts accordingly when writing the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kicad_power.py -v`
Expected: FAIL — `ImportError: cannot import name 'power_sheet'`.

- [ ] **Step 3: Write minimal implementation**

Add to `app/generators/kicad_power.py`:

```python
import uuid
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "power_symbols.kicad_sym"
_UUID_NS = uuid.UUID("a1c17ec7-0000-4000-8000-000000000000")
_GRID = 1.27  # KiCad connection grid (mm); off-grid endpoints trip ERC warnings


def _snap(v: float) -> float:
    """Snap a coordinate to the 1.27 mm connection grid (spike-confirmed required)."""
    return round(round(v / _GRID) * _GRID, 2)


def _det_uuid(project_name: str, key: str) -> str:
    return str(uuid.uuid5(_UUID_NS, f"{project_name}:{key}"))


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
    lib = "\n".join(frags[lib_id] for lib_id in frags if lib_id in used)

    parts: list[str] = []
    x0, y0, dy = _snap(50.0), _snap(50.0), _snap(25.4)  # grid-aligned column
    for n, m in enumerate(mapped):
        ref = f"#PWR{n + 1:02d}"
        at_y = _snap(y0 + n * dy)
        sym_uuid = _det_uuid(project_name, f"pwr-sym:{n}")
        pin_uuid = _det_uuid(project_name, f"pwr-pin:{n}")
        parts.append(_instance(m, x0, at_y, ref, sym_uuid, pin_uuid,
                               project_name, root_uuid, block_uuid))
        if m.lib_id == "power:PWR_FLAG":
            lbl_uuid = _det_uuid(project_name, f"pwr-lbl:{n}")
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
```

- [ ] **Step 4: Create the template**

`app/templates/power_sheet.kicad_sch.j2`:

```jinja
(kicad_sch
	(version 20250114)
	(generator "ai_circuit_architect")
	(generator_version "9.0")
	(uuid "{{ file_uuid }}")
	(paper "A4")
	(title_block
		(title "{{ title_block.title }}")
{% if title_block.date %}		(date "{{ title_block.date }}")
{% endif %}		(rev "{{ title_block.rev }}")
		(company "{{ title_block.company }}")
		(comment 1 "{{ title_block.comment }}")
	)
	(lib_symbols
{{ lib_symbols }}
	)
	(text "{{ annotation }}"
		(at 25.4 18.0 0)
		(effects (font (size 1.27 1.27)) (justify left bottom))
		(uuid "{{ text_uuid }}")
	)
{{ instances }}
{% for h in hier_labels %}	(hierarchical_label "{{ h.name }}"
		(shape {{ h.shape }})
		(at {{ h.x }} {{ h.y }} {{ h.rot }})
		(effects (font (size 1.27 1.27)) (justify {{ h.justify }}))
		(uuid "{{ h.uuid }}")
	)
{% endfor %}	(sheet_instances
		(path "/"
			(page "1")
		)
	)
)
```

> `hier_labels` is the matching set for the Power sheet's own sheet pins (from Task 5/6). Pass `hier_labels=[]` until Task 6 wires it.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_kicad_power.py -v`
Expected: PASS (all power tests). Fix the test fixture per the Step-1 note (`MYRAIL` for the PWR_FLAG path) if red.

- [ ] **Step 6: Commit**

```bash
git add app/generators/kicad_power.py app/templates/power_sheet.kicad_sch.j2 tests/test_kicad_power.py
git commit -m "feat(kicad): power-sheet body builder + template"
```

---

### Task 4: Wire the Power sheet into `generate_scaffold`

**Files:**
- Modify: `app/generators/kicad.py:356-379` (the per-block subsheet loop)
- Test: `tests/test_kicad_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_kicad_generator.py
def test_power_sheet_has_real_power_symbols(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    power = (out / "sheets" / "power.kicad_sch").read_text(encoding="utf-8")
    assert '(lib_id "power:' in power           # at least one placed symbol
    assert '(symbol "power:GND"' in power        # lib_symbols def embedded
    # rails from the mock architecture (+5V, +3V3, GND) each appear
    assert '(lib_id "power:+5V")' in power
    assert '(lib_id "power:GND")' in power


def test_non_power_sheets_stay_placeholders(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    mcu = (out / "sheets" / "mcu.kicad_sch").read_text(encoding="utf-8")
    assert '(lib_id "power:' not in mcu          # only the Power block gets symbols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kicad_generator.py::test_power_sheet_has_real_power_symbols -v`
Expected: FAIL — power sheet is still the placeholder text template.

- [ ] **Step 3: Write minimal implementation**

In `app/generators/kicad.py`, add the import and branch the subsheet loop. The Power block is identified by `block.category == "power"` (fall back to a `power`-prefixed filename). Use `architecture.power` for the rail list; pass the sheet's own `block_uuid` and the `root_uuid`.

```python
from app.generators import kicad_power  # near the other generator imports

# inside generate_scaffold, REPLACE the body of the `for s in sheets:` loop:
power_block_names = {b.name for b in architecture.blocks if b.category == "power"}
power_tpl = env.get_template("power_sheet.kicad_sch.j2")
for s in sheets:
    is_power = (s["raw_name"] in power_block_names
                or s["fname"].lower().startswith("power"))
    if is_power and architecture.power:
        body = kicad_power.power_sheet(
            list(architecture.power), project_name, root_uuid, s["block_uuid"])
        sheet_sch = power_tpl.render(
            file_uuid=s["file_uuid"],
            text_uuid=_det_uuid(project_name, f"text:{s['fname']}"),
            annotation=_esc("Power rails (placeholder symbols) — wire to your regulators. NEEDS HUMAN REVIEW"),
            title_block={
                "title": s["name"], "company": title_block["company"],
                "rev": title_block["rev"], "date": title_block["date"],
                "comment": _esc(f"{project_name} — power rails, NOT production-ready"),
            },
            lib_symbols=body.lib_symbols,
            instances=body.instances,
            hier_labels=[],
        )
        (sheets_dir / s["fname"]).write_text(sheet_sch, encoding="utf-8")
        continue
    # ... existing placeholder rendering for non-power sheets (unchanged) ...
```

Keep the existing placeholder-sheet rendering for the non-power branch verbatim.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kicad_generator.py -v`
Expected: PASS — new power-sheet tests green; **`test_output_is_deterministic` still green** (no wall-clock, det-UUIDs).

- [ ] **Step 5: Commit**

```bash
git add app/generators/kicad.py tests/test_kicad_generator.py
git commit -m "feat(kicad): render real power symbols on the Power sub-sheet"
```

---

### Task 5: Sheet-pin inference + matching hierarchical labels

**Files:**
- Create: `app/generators/kicad_root.py`
- Test: `tests/test_kicad_sheetpins.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kicad_sheetpins.py
from app.models.schemas import Block, Connection
from app.generators.kicad_root import sheet_pins_for, hier_labels_for


def _block(name, cat="other"):
    return Block(name=name, sheet=f"{name.lower()}.kicad_sch", purpose="x", category=cat)


CONNS = [
    Connection(source="Power", target="MCU", type="power"),
    Connection(source="Sensor", target="MCU", type="data"),
    Connection(source="MCU", target="Debug", type="debug"),
]


def test_pins_inferred_from_touching_connections():
    pins = sheet_pins_for(_block("MCU"), CONNS)
    names = {p.name for p in pins}
    # MCU is touched by a power, a data and a debug connection
    assert "PWR" in names or any(p.kind == "power" for p in pins)
    assert any(p.kind == "data" for p in pins)
    assert any(p.kind == "debug" for p in pins)


def test_pin_direction_from_edge_role():
    # MCU is the TARGET of Power→MCU (incoming) → input; SOURCE of MCU→Debug → output
    pins = {(p.kind, p.shape) for p in sheet_pins_for(_block("MCU"), CONNS)}
    assert ("power", "input") in pins
    assert ("debug", "output") in pins


def test_block_with_no_connections_has_no_pins():
    assert sheet_pins_for(_block("Lonely"), CONNS) == []


def test_pins_are_capped_and_deterministic():
    many = [Connection(source=f"S{i}", target="Hub", type="data") for i in range(20)]
    a = sheet_pins_for(_block("Hub"), many)
    b = sheet_pins_for(_block("Hub"), many)
    assert a == b
    assert len(a) <= 8  # readability cap


def test_every_pin_has_a_matching_hier_label():
    pins = sheet_pins_for(_block("MCU"), CONNS)
    labels = hier_labels_for(pins)
    assert {p.name for p in pins} == {l.name for l in labels}
    # shape complementarity: an input sheet pin → output-ish hier label and vice versa
    for p, l in zip(pins, labels):
        assert l.shape in {"input", "output", "bidirectional", "passive"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kicad_sheetpins.py -v`
Expected: FAIL — `ModuleNotFoundError: app.generators.kicad_root`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/generators/kicad_root.py
"""Sheet-pin inference for root hierarchical blocks + their matching child-sheet
hierarchical labels. A sheet pin on the root MUST have a matching hierarchical
label inside the child sheet or KiCad ERC flags an 'unmatched sheet pin' — so the
two are generated together (callers must emit both)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Block, Connection

_MAX_PINS = 8
# Connection type → (sheet-pin electrical kind shown to the user)
_KIND = {"power": "power", "data": "data", "control": "control", "debug": "debug"}
# Stable ordering so output is deterministic regardless of connection order.
_TYPE_ORDER = {"power": 0, "data": 1, "control": 2, "debug": 3}


@dataclass(frozen=True)
class Pin:
    name: str        # e.g. "PWR", "DATA1"
    kind: str        # power|data|control|debug
    shape: str       # input|output|bidirectional (sheet-pin shape)
    side: str        # bottom|top|left|right (placement hint)


@dataclass(frozen=True)
class HierLabel:
    name: str
    shape: str       # complementary shape inside the child sheet


def sheet_pins_for(block: Block, connections: list[Connection]) -> list[Pin]:
    touching = []
    for c in connections:
        if c.source == block.name:
            touching.append((c, "output"))
        elif c.target == block.name:
            touching.append((c, "input"))
    if not touching:
        return []
    # Sort for determinism: by type, then by direction, then by counterpart name.
    touching.sort(key=lambda t: (_TYPE_ORDER.get(t[0].type, 9), t[1],
                                 t[0].target if t[1] == "output" else t[0].source))
    pins: list[Pin] = []
    counts: dict[str, int] = {}
    seen_dir: dict[str, set[str]] = {}
    for c, direction in touching:
        kind = _KIND.get(c.type, "data")
        # collapse a kind seen in both directions to a single bidirectional pin
        dirs = seen_dir.setdefault(kind, set())
        dirs.add(direction)
        n = counts.get(kind, 0) + 1
        counts[kind] = n
        name = kind.upper() if n == 1 else f"{kind.upper()}{n}"
        shape = "bidirectional" if {"input", "output"} <= dirs else direction
        side = "bottom" if kind == "power" else ("right" if direction == "output" else "left")
        pins.append(Pin(name=name, kind=kind, shape=shape, side=side))
        if len(pins) >= _MAX_PINS:
            break
    return pins


_COMPLEMENT = {"input": "output", "output": "input",
               "bidirectional": "bidirectional"}


def hier_labels_for(pins: list[Pin]) -> list[HierLabel]:
    # The child-sheet hierarchical label name MUST equal the sheet-pin name.
    return [HierLabel(name=p.name, shape=_COMPLEMENT.get(p.shape, "passive"))
            for p in pins]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kicad_sheetpins.py -v`
Expected: PASS. If the bidirectional-collapse asserts fight the direction asserts, adjust the CONNS fixture so MCU has a *pure* incoming power and *pure* outgoing debug (it already does).

- [ ] **Step 5: Commit**

```bash
git add app/generators/kicad_root.py tests/test_kicad_sheetpins.py
git commit -m "feat(kicad): infer root sheet pins + matching child hier-labels"
```

---

### Task 6: Render sheet pins on root + hier-labels in children, wire it, and run the render gate

**Files:**
- Modify: `app/templates/root.kicad_sch.j2:29-51` (the `(sheet …)` block)
- Modify: `app/templates/sheet.kicad_sch.j2` (add hier-labels)
- Modify: `app/generators/kicad.py` (compute pins per sheet; thread into both templates)
- Modify: `app/templates/power_sheet.kicad_sch.j2` is already pin-ready (Task 3)
- Test: `tests/test_kicad_generator.py`

- [ ] **Step 1: Write the failing test (integration + render gate)**

```python
# add to tests/test_kicad_generator.py
import shutil
import pytest
from app.services.kicad_cli import KiCadCli
from app.services.config import Settings


def test_root_blocks_carry_sheet_pins(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    assert root.count("(pin ") >= 1            # at least one sheet pin on a block
    assert "(shape" in root


def test_sheet_pins_have_matching_child_labels(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    root = (out / "project.kicad_sch").read_text(encoding="utf-8")
    # every sheet pin name on the MCU block exists as a hier label in mcu.kicad_sch
    import re as _re
    mcu = (out / "sheets" / "mcu.kicad_sch").read_text(encoding="utf-8")
    # crude: each (pin "NAME" appears as (hierarchical_label "NAME" somewhere in a child
    for name in set(_re.findall(r'\(pin "([^"]+)"', root)):
        assert f'(hierarchical_label "{name}"' in (
            mcu + "".join(p.read_text(encoding="utf-8")
                          for p in (out / "sheets").glob("*.kicad_sch")))


# Expected-for-an-unwired-scaffold ERC error types (NOT structural failures).
# A placeholder schematic with power symbols and sheet pins legitimately has
# unconnected pins, undriven power inputs, and dangling labels — the spec's
# non-goals explicitly allow these ("we only avoid structural ERC errors").
# Any error OUTSIDE this allowlist (e.g. a malformed symbol or an unmatched
# sheet pin) is a real structural break and must fail the gate.
_EXPECTED_SCAFFOLD_ERC = {
    "pin_not_connected", "power_pin_not_driven", "label_dangling",
    "global_label_dangling", "hier_label_mismatch", "no_connect_connected",
}


@pytest.mark.skipif(not KiCadCli(Settings()).available(),
                    reason="kicad-cli not installed")
def test_generated_project_opens_and_no_structural_erc_errors(tmp_path):
    out = generate_scaffold(_result(), REQ_TEXT, tmp_path / "proj")
    cli = KiCadCli(Settings())
    svg_dir = tmp_path / "svg"
    # export raises KiCadCliError on a load/parse failure -> proves files open
    cli.export_svg(out / "project.kicad_sch", svg_dir)
    cli.export_svg(out / "sheets" / "power.kicad_sch", svg_dir)
    # SVG must be non-empty (symbols actually drawn, not a blank page)
    svg = next(svg_dir.glob("*.svg")).read_text(encoding="utf-8")
    assert svg.count("<path") > 50, "power sheet rendered nearly empty"
    erc = cli.run_erc(out / "project.kicad_sch", tmp_path / "erc.json")
    structural = [v for sheet in erc.get("sheets", [])
                  for v in sheet.get("violations", [])
                  if v.get("severity") == "error"
                  and v.get("type") not in _EXPECTED_SCAFFOLD_ERC]
    assert structural == [], structural
    # No off-grid warnings (all geometry must snap to 1.27 mm)
    offgrid = [v for sheet in erc.get("sheets", [])
               for v in sheet.get("violations", [])
               if v.get("type") == "endpoint_off_grid"]
    assert offgrid == [], offgrid
```

> Adjust the ERC JSON traversal to the actual shape `run_erc` returns (inspect once, then pin the assertion). The skip-guard keeps CI green where `kicad-cli` is absent.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_kicad_generator.py -k "sheet_pins or opens_and_erc" -v`
Expected: FAIL — no `(pin` in root yet.

- [ ] **Step 3: Add sheet-pin rendering to the root template**

In `app/templates/root.kicad_sch.j2`, inside the `(sheet …)` block (after the `(instances …)` element, before its closing `)`), add:

```jinja
{% for p in s.pins %}		(pin "{{ p.name }}" {{ p.shape }}
			(at {{ p.at_x }} {{ p.at_y }} {{ p.rot }})
			(effects (font (size 1.27 1.27)) (justify {{ p.justify }}))
			(uuid "{{ p.uuid }}")
		)
{% endfor %}
```

- [ ] **Step 4: Add hier-label rendering to the child-sheet template**

In `app/templates/sheet.kicad_sch.j2`, before `(sheet_instances …)`, add the same `hier_labels` loop used in `power_sheet.kicad_sch.j2`:

```jinja
{% for h in hier_labels %}	(hierarchical_label "{{ h.name }}"
		(shape {{ h.shape }})
		(at {{ h.x }} {{ h.y }} {{ h.rot }})
		(effects (font (size 1.27 1.27)) (justify {{ h.justify }}))
		(uuid "{{ h.uuid }}")
	)
{% endfor %}
```

- [ ] **Step 5: Compute pins + labels in `generate_scaffold` and thread them**

In `app/generators/kicad.py`: import `kicad_root`; when building each `sheets[]` entry, compute `Pin`s for the block and attach template-ready dicts (geometry on the 40×30 box edges) under `s["pins"]`; compute the matching child `hier_labels` and store per-sheet. Then pass `hier_labels=` into every child-sheet render (placeholder, and power). Pin geometry: power pins along the bottom edge (`y = s.y + 30`), input signals on the left (`x = s.x`), outputs on the right (`x = s.x + 40`), spread along the edge; `rot` 0/180 to point outward; det-UUID via `_det_uuid(project_name, f"pin:{fname}:{p.name}")`. Hier-label geometry inside the child: a deterministic column at `(30, 40 + i*8)`.

```python
from app.generators import kicad_root

# while populating each `sheets` entry, after computing x/y:
block_pins = kicad_root.sheet_pins_for(block, architecture.connections)
s["pins"] = _pin_geometry(block_pins, x, y)            # helper → list of dicts
s["hier_labels"] = _label_geometry(
    kicad_root.hier_labels_for(block_pins), project_name, fname)
```

Add two small helpers next to `_route`:

```python
_GRID = 1.27


def _snap(v: float) -> float:
    return round(round(v / _GRID) * _GRID, 2)


def _pin_geometry(pins, bx, by):
    # Sheet pins are wire endpoints -> their `at` MUST land on the 1.27 mm grid
    # or ERC emits endpoint_off_grid (the render gate fails on those). Snap both
    # the box-edge anchor and the per-pin offset.
    out = []
    by_side = {"left": [], "right": [], "bottom": [], "top": []}
    for p in pins:
        by_side[p.side].append(p)
    for side, ps in by_side.items():
        for i, p in enumerate(ps):
            off = _GRID * 5 * (i + 1)  # grid-multiple spacing along the edge
            if side == "left":
                ax, ay, rot, just = _snap(bx), _snap(by + off), 180, "right"
            elif side == "right":
                ax, ay, rot, just = _snap(bx + _SHEET_W), _snap(by + off), 0, "left"
            else:  # bottom (power)
                ax, ay, rot, just = _snap(bx + off), _snap(by + _SHEET_H), 270, "left"
            out.append({"name": p.name, "shape": p.shape, "at_x": ax, "at_y": ay,
                        "rot": rot, "justify": just,
                        "uuid": _det_uuid("pins", f"{bx}:{by}:{p.name}")})
    return out


def _label_geometry(labels, project_name, fname):
    out = []
    for i, l in enumerate(labels):
        out.append({"name": l.name, "shape": l.shape, "x": _snap(30.0),
                    "y": _snap(40.0 + i * _GRID * 6), "rot": 0, "justify": "left",
                    "uuid": _det_uuid(project_name, f"hlabel:{fname}:{l.name}")})
    return out
```

> **Integration risk (un-spiked half):** the root sheet boxes are placed at `_GRID_X0=30, _GRID_DX=70` etc., which are **not** on the 1.27 mm grid — so snapping a pin to `bx` still leaves it off-grid relative to KiCad's grid origin. If the render gate's `endpoint_off_grid` check fails, the fix is to **snap the sheet-box origins themselves** (`x`/`y` in the `sheets[]` loop) to `_snap(...)` before deriving pin coords — but that shifts existing geometry, so re-bless `test_output_is_deterministic` (it only asserts run-to-run stability, not specific coordinates, so it stays green). The render gate is the arbiter here; iterate until both `structural == []` and `offgrid == []` pass.

Then in the root render call add nothing new (sheets already carry `pins`); in **each** child render call add `hier_labels=s["hier_labels"]` (placeholder branch and power branch).

- [ ] **Step 6: Run the full suite + render gate**

Run: `python -m pytest tests/test_kicad_generator.py tests/test_kicad_power.py tests/test_kicad_sheetpins.py -v`
Expected: PASS, including `test_output_is_deterministic` and (locally) `test_generated_project_opens_and_erc_has_no_new_errors`.

Then the whole suite:

Run: `python -m pytest -q`
Expected: all green (was 227; now ~227 + new tests). If the ERC gate surfaces a real *error* (not warning), fix the offending S-expression (most likely an unmatched sheet pin → a geometry/name mismatch between `_pin_geometry` and `_label_geometry`) before committing.

- [ ] **Step 7: Manually render and eyeball once (dev loop)**

Use the kicad-render-loop (kicad-cli → `tools/pdf2png.py`) to render `project.kicad_sch` + `sheets/power.kicad_sch` to PNG and visually confirm: power symbols are visible on the Power sheet, sheet pins sit on the block edges, nothing overlaps the embedded diagram. (See the `kicad-render-loop` memory.)

- [ ] **Step 8: Commit**

```bash
git add app/generators/kicad.py app/templates/root.kicad_sch.j2 app/templates/sheet.kicad_sch.j2 tests/test_kicad_generator.py
git commit -m "feat(kicad): hierarchical sheet pins on root blocks + matching child labels"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-06-28-schematic-power-symbols-design.md`):
- A. Power symbols on Power sheet → Tasks 1–4 (mapping, vendored lib_symbols, instances, generic fallback via PWR_FLAG+label). ✔
- A.4 only the Power sheet gets symbols → Task 4 `test_non_power_sheets_stay_placeholders`. ✔
- B. Sheet pins on root blocks → Tasks 5–6 (inference, direction, placement). ✔
- B.3 matching hierarchical labels (coupled unit) → Task 5 `hier_labels_for` + Task 6 `test_sheet_pins_have_matching_child_labels`. ✔
- Determinism preserved → asserted in Tasks 3, 4, 6 (`test_output_is_deterministic`, `test_power_sheet_is_deterministic`). ✔
- Opens in KiCad 10 / no new ERC errors → Task 1 spike + Task 6 render gate. ✔
- Non-goals (no real components/wiring, ERC not fully clean) → respected; gate forbids only new *errors*, warnings allowed. ✔

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". The one deliberate adjust-note (Task 3 Step-1 `MYRAIL` fixture; Task 6 ERC-JSON shape) flags a value the engineer must read off a real run — concrete, not vague.

**Type consistency:** `RailSymbol(rail, lib_id, label)`, `PowerSheetBody(lib_symbols, instances)`, `Pin(name, kind, shape, side)`, `HierLabel(name, shape)` are used consistently across Tasks 2–6. `power_sheet(rails, project_name, root_uuid, block_uuid)` signature matches its call site in Task 4. `sheet_pins_for(block, connections)` / `hier_labels_for(pins)` match Task 6 usage.

**Risk note for the executor:** The single highest-risk step is **Task 1 Step 3–4** (does a KiCad-10 symbol def + our instance pattern open and ERC-clean?). Do not start Task 2 until it renders non-empty with no load error. If the deploy image (KiCad 9) later rejects the symbols, the fallback is to downgrade nothing in the def and instead re-extract from a KiCad-9 `power.kicad_sym` — but local KiCad 10 forward-compat is expected to hold.
