# Verification Badge (Feature #5) — Design

**Date:** 2026-06-26
**Status:** Approved (design), pending implementation plan
**Feature:** Killer-Feature #5 of 4 selected (build order: #5 → M9 deploy → #1 → #3 → #2)

## Problem

The app already runs real KiCad checks (`validate_project` exports a PDF as an
open-check and runs ERC) and already renders a schematic SVG preview in the UI.
But the verifiability story is weak in two honest ways:

1. **The badge is unsharp and mildly dishonest.** When `kicad-cli` is not
   available, the UI still shows "✓ Validation passed" based on *structural*
   checks alone. It conflates "structurally consistent" with "actually verified
   by KiCad" — which contradicts the project philosophy of never feigning
   certainty.
2. **The proof stays trapped in the live UI.** `packaging.py` excludes the
   `preview/` folder and `validation_report.md` is plain text, so a downloaded
   ZIP (the thing a juror or engineer actually keeps) contains **no** rendered
   schematic and no verification summary. The proof does not travel with the
   artifact.

This feature sharpens the badge to be honest, and makes the KiCad-verification
proof part of the downloadable artifact.

## Scope

In scope (all three confirmed with the user):
- Honest badge with three explicit states: verified / verification-failed /
  structural-only.
- Verification proof embedded in the ZIP: persisted `schematic.pdf`, a
  universally-viewable `schematic_preview.png`, and a `VERIFICATION.md` summary.
- A compact verification card in the UI: KiCad version, "opens & exports ✓",
  "ERC ran — N violations".

Explicitly **out of scope** (YAGNI):
- Per-violation ERC breakdown (a dummy scaffold legitimately produces many
  warnings; listing them undercuts the "verified" message). Keep the existing
  count + severity totals only.
- Cryptographic signatures or content hashes of the artifact.
- Multi-sheet PDF/PNG handling beyond the root sheet (the root export already
  covers the hierarchy via kicad-cli).

## Design

### 1. Honest badge (three states)

The badge is derived from `kicad_cli_available` and `kicad_opens`:

| Condition | Badge | Colour |
|-----------|-------|--------|
| available & `kicad_opens` is True | ✅ "Verified in KiCad {version}" | green |
| available & `kicad_opens` is False | ❌ "KiCad verification failed" | red |
| not available | ⚠️ "Structural checks only — KiCad not available" | yellow |

The structural result (all non-KiCad checks passing) is shown as a **separate**
line beneath the badge, so "structurally consistent" and "KiCad-verified" are
never again conflated. In the live deployment the M9 image ships `kicad-cli`, so
the demo shows the green verified state.

### 2. Proof travels in the ZIP

Today the open-check PDF is written into a `TemporaryDirectory` inside
`validate_project` and discarded; the SVG preview goes into `project_dir/preview`
which the packager excludes. New behaviour, only when KiCad is available **and**
the project opens:

- Persist the open-check export as `project_dir/schematic.pdf` (strong proof: it
  genuinely opens/exports in KiCad).
- Convert it to `project_dir/schematic_preview.png` using the existing
  `tools/pdf2png.py` (PyMuPDF — already a dependency). PNG is universally
  viewable from a downloaded ZIP.
- Render `project_dir/VERIFICATION.md` from a new Jinja template
  `verification.md.j2`, containing: KiCad version, what was checked (opens &
  exports ✓, ERC ran, N violations with severity totals), and an embedded
  reference to `schematic_preview.png`.

All three live outside `preview/`, so `create_project_zip` includes them with no
change to its exclusion rule. No new dependency is introduced.

When KiCad is unavailable, none of these files are produced and `VERIFICATION.md`
is not written (the existing `validation_report.md` already states structural
results honestly).

### 3. Verification card in the UI

Beneath the badge, a compact card reads the new fields and shows: KiCad version ·
"opens & exports ✓" · "ERC ran — N violations". This turns a single word
("verified") into a legible machine-checked proof. Largely a frontend change.

### 4. Code touch-points (kept small)

- `app/services/kicad_cli.py`: add `version()` — runs `kicad-cli version`, parses
  and caches the version string. Returns `None` when unavailable.
- `app/models/schemas.py`: add `Validation.kicad_version: str | None = None`.
- `app/services/validation.py` and/or `app/api/routes.py`: persist the open-check
  PDF, generate the PNG, render `VERIFICATION.md`. The cleanest split: keep the
  open-check inside `validate_project` but have it write to `project_dir`
  (instead of a temp dir) when the project opens, and render `VERIFICATION.md`
  there; `routes.py` already calls `create_project_zip` afterwards.
- `app/templates/verification.md.j2`: new template.
- `app/static/index.html`: three-state badge logic + verification card.
- Tests: badge state mapping (verified / failed / structural-only) and a
  packaging test asserting `VERIFICATION.md` and `schematic_preview.png` are
  present in the ZIP when KiCad is available, and absent otherwise.

## Data flow

```
generate() [routes.py]
  → generate_scaffold(...)
  → validate_project(...)            # structural + real KiCad checks
       ├─ kicad.version()            # NEW: cached version string
       ├─ open-check export PDF      # CHANGED: persist to project_dir/schematic.pdf on success
       ├─ run ERC                    # unchanged
       ├─ pdf2png → schematic_preview.png   # NEW
       └─ render VERIFICATION.md     # NEW (only when verified)
  → export_svg → preview/            # unchanged (live UI preview)
  → create_project_zip(...)          # unchanged rule; now picks up the new root files
  → GenerateResponse(validation incl. kicad_version, preview_svg_url, ...)
```

## Error handling

- `kicad-cli version` failure → `version()` returns `None`; badge falls back to
  "Verified in KiCad" without a version number rather than erroring.
- PDF persist / PNG conversion failure → log a note in `validation.notes`, skip
  the embedded PNG, still write `VERIFICATION.md` (text-only). Verification
  correctness is already covered by the `kicad_opens` check; the embedded image
  is best-effort, mirroring how the SVG preview is already best-effort.
- KiCad unavailable → unchanged graceful degradation; no verification artifacts.

## Testing

- Unit: `version()` parsing of a sample `kicad-cli version` output; `None` when
  unavailable.
- Unit: badge-state derivation for the three `(available, opens)` combinations.
- Integration/packaging: ZIP contains `VERIFICATION.md` + `schematic_preview.png`
  when KiCad available and opens; contains neither when unavailable. Use the
  existing kicad-cli-gated test pattern so the suite still passes without
  kicad-cli installed.

## Definition of done

- Badge shows the correct one of three states, with a separate structural line.
- When KiCad verifies the project, the downloaded ZIP contains `schematic.pdf`,
  `schematic_preview.png`, and `VERIFICATION.md`.
- UI verification card shows KiCad version + checks.
- Tests pass both with and without kicad-cli present.
- No "production-ready" or otherwise dishonest claim is introduced.
