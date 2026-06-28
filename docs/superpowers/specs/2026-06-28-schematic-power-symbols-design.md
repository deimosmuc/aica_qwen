# Schematic Enrichment — Stage 2: Real Power Symbols & Sheet Pins

**Date:** 2026-06-28
**Status:** Approved in brainstorming. Stage 1 already shipped; this is the deferred
Stage-2 work, queued for a Superpowers (writing-plans → execute) run.
**Track:** Polish (KiCad scaffold quality).

## Context

The KiCad scaffold's root sheet was "surprisingly empty". In brainstorming we split the
enrichment into two stages by risk:

- **Stage 1 (done, this branch):** title block, embedded block-diagram bitmap,
  colour-coded inter-block connection lines, legend + notes block. All deterministic
  template-filling, no `lib_symbols`, verified to open in KiCad 10 via `kicad-cli`.
  See `app/generators/kicad.py`, `app/generators/diagram_embed.py`,
  `app/templates/root.kicad_sch.j2`, `app/templates/sheet.kicad_sch.j2`.
- **Stage 2 (this spec):** make the schematic *electrically* richer — real power-port
  symbols on the existing Power sheet, and hierarchical sheet pins on the root blocks.

These two were deferred because they need verified `lib_symbols` definitions and risk
KiCad ERC errors — the parts of the original idea that are *not* quick template fills.

## Goals

- The Power sub-sheet (`sheets/power.kicad_sch`, today a placeholder text) shows real
  KiCad power-port symbols, one per rail in `architecture.power`
  (e.g. `VIN_24V`, `+5V`, `+3V3`, `GND`), with global labels.
- Each hierarchical block on the root sheet shows its interface as **sheet pins**
  (power + key signals), instead of a bare rectangle.
- Output stays byte-deterministic for the same approved plan (the existing
  `test_output_is_deterministic` must keep passing).
- Everything opens cleanly in KiCad 10; validated by rendering with `kicad-cli` in the
  dev loop (see the `kicad-render-loop` memory).

## Non-goals / out of scope

- No real component symbols, wiring, or netlists — still a *scaffold*, a human completes it.
- No attempt to make ERC fully clean. Placeholder power pins will legitimately be
  unconnected; we only avoid *structural* ERC errors (see Risks).

## Locked design decisions (from brainstorming)

- **Power rails:** real KiCad power-port symbols (not decorative text, not a drawn
  power-tree). User chose "Echte Power-Symbole".
- **Placement:** fill the **existing** `sheets/power.kicad_sch` rather than adding a new
  overview/power page. User chose "Bestehende Power-Seite füllen".
- **Symbol source:** `lib_symbols` definitions must be **extracted from a real KiCad
  project that opens cleanly** (same philosophy as the rest of the generator — never
  synthesise KiCad syntax from scratch). Generate a tiny reference project in KiCad,
  copy its verified power-symbol `lib_symbols` blocks, template them.

## Design

### A. Power symbols on the Power sheet

1. **Rail → symbol mapping.** Map well-known rail names to KiCad's standard power
   symbols: `+5V`, `+3V3`/`+3.3V`, `+12V`, `+24V`, `GND`, `+VDC`, etc. Unknown rails
   (e.g. `VIN_24V`) fall back to a **generic `power`/`PWR_FLAG`-style symbol** whose
   value/label is the raw rail name. Keep the mapping in one table next to `_CONN_COLOR`.
2. **`lib_symbols`.** Embed only the symbol definitions actually used on the sheet, in the
   sheet's `(lib_symbols …)` section. Source these from a verified reference project.
3. **Placement.** Lay the rails out vertically (a simple column), each: a power-port
   symbol instance + a global label with the rail name. Deterministic grid, det-UUIDs via
   `_det_uuid(project_name, …)`.
4. **Which sheet.** Detect the Power block (category == "power", or sheet filename
   `power*`). Only that sub-sheet gets symbols; other placeholders stay as-is.

### B. Sheet pins on root blocks

1. **Interface inference.** For each block, derive its pins from the `connections` that
   touch it: power-type connections → a power pin; data/control/debug → a signal pin.
   De-duplicate, cap the count to keep boxes readable.
2. **Pin direction & shape.** Source side → output; target side → input; both → bidi.
3. **Matching hierarchical labels.** Each sheet pin **must** have a matching
   hierarchical label inside the child sheet, or KiCad ERC flags an "unmatched sheet pin".
   So pin generation and child-sheet label generation are one coupled unit — emit both.
4. **Placement.** Pins on the box edges (power pins bottom/top, signals on sides),
   non-overlapping, deterministic.

## Architecture / where the code goes

- New `app/generators/kicad_power.py`: rail→symbol mapping, verified `lib_symbols`
  fragments, and a function returning the Power-sheet body (symbols + labels). Keeps
  `kicad.py` from growing further and is independently testable.
- Root sheet-pin geometry: a helper alongside `_route` in `kicad.py` (or a small
  `kicad_root.py` if `kicad.py` gets too large).
- New templates: `power_sheet.kicad_sch.j2` (or extend `sheet.kicad_sch.j2` with an
  optional symbols block), and sheet-pin + hierarchical-label fragments.

## Risks / things to verify first

1. **`lib_symbols` correctness is the whole ballgame.** Hand-written power-symbol defs
   that KiCad rejects will break the file silently (opens blank or errors). **Mitigation:**
   extract from a real project; render every generated sheet with `kicad-cli` and assert
   it produces a non-empty plot.
2. **Unmatched sheet pins = ERC errors.** Must emit matching hierarchical labels in the
   child sheet. Verify by running `kicad-cli sch erc` and checking we add no *new*
   structural errors beyond expected unconnected-pin warnings.
3. **Determinism.** UUIDs via `_det_uuid`; no wall-clock values. Keep the existing
   determinism test green.
4. **Generic rail fallback.** `PWR_FLAG` vs a custom power symbol — pick whichever the
   reference project provides and that doesn't trip ERC power-input rules.

## Test plan

- Unit: rail→symbol mapping (known + unknown rails); Power-sheet body contains a symbol +
  label per rail; sheet-pin inference from connections; every emitted sheet pin has a
  matching hierarchical label.
- Integration: `generate_scaffold` output — Power sheet has `lib_symbols` and N symbols;
  root blocks carry sheet pins; paren-balance + determinism still hold.
- Render gate (dev loop, not CI): `kicad-cli sch export pdf` on root + Power sheet renders
  non-empty; `kicad-cli sch erc` adds no new structural errors.
