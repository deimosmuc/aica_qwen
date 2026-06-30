# Jury Pitch Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The actual `.pptx` generation uses the **anthropic-skills:pptx** skill (python-pptx); invoke it before Task 2.

**Goal:** Build a 9-slide PowerPoint pitch deck for the Qwen hackathon (Track 3 — Agent Society) in the app's dark visual look, usable both as video speaker-support and a standalone Devpost artifact.

**Architecture:** A single Python build script (`deck/build_deck.py`) generates `deck/AI_Circuit_Architect.pptx` via python-pptx. A small theme module centralizes colors/fonts/layout helpers so all slides are consistent. Product screenshots are captured once from the running app (Mock Mode, bat-detector example) into `deck/assets/`; concept slides are drawn as native pptx vector shapes.

**Tech Stack:** python-pptx (via anthropic-skills:pptx skill), the app's FastAPI dev server in Mock Mode for screenshots, the Claude_Preview MCP tools for capture.

**Spec:** `docs/superpowers/specs/2026-06-30-jury-pitch-deck-design.md`

---

## File Structure

- `deck/build_deck.py` — main build script; one function per slide, calls into the theme helpers.
- `deck/theme.py` — palette constants (mirroring `app/static/index.html` `:root`), font names, and reusable layout helpers (dark background fill, accent title bar, footer logo, bar-chart drawing).
- `deck/assets/` — captured screenshots + a copy of `logo.png`.
- `deck/AI_Circuit_Architect.pptx` — the generated output (committed).

---

## Task 1: Capture product screenshots (bat detector, Mock Mode)

Slides 5–7 need three real screenshots. Known env issue (memory): the preview `screenshot` tool can time out because of the metro-rail CSS animations — disable animations via `preview_eval` before capturing.

**Files:**
- Create: `deck/assets/society_rework.png`, `deck/assets/compare_panel.png`, `deck/assets/schematic.png`, `deck/assets/report_pdf.png`
- Copy: `app/static/assets/logo.png` → `deck/assets/logo.png`

- [ ] **Step 1: Start the app in Mock Mode**

Use `preview_start` against the `app-mock` launch config (port 8011, empty `QWEN_API_KEY` → deterministic mock). If preview tooling can't pick the config, run uvicorn with an empty key on port 8011.
Expected: server up, page loads.

- [ ] **Step 2: Run the bat-detector example with the Senior Review Team profile**

Via the UI (or `preview_eval`): select profile "Senior Review Team", click the "Bat detector (Wi-Fi / USB)" example, run the auto pipeline. This profile triggers the scripted `mock_run_rework` so a visible Critic→Architect rework round renders.
Expected: pipeline completes, Society chat shows round 1 + round 2, rework packet visible.

- [ ] **Step 3: Capture the Society-chat rework screenshot**

Disable animations first: `preview_eval` → inject `* { animation: none !important; transition: none !important; }`. Scroll the Society-chat view into frame, then `preview_screenshot`.
Expected: `deck/assets/society_rework.png` shows avatar bubbles + the amber rework round.

- [ ] **Step 4: Capture the Compare panel**

Trigger the `/compare` panel (preset "🏆 Architecture beats tier" or the fair preset), wait for the result table, `preview_screenshot`.
Expected: `deck/assets/compare_panel.png` shows the multi-vs-single rubric table.

- [ ] **Step 5: Capture the schematic preview**

After `/generate`, the SVG preview renders. `preview_screenshot` the schematic preview area (or reuse an existing real render PNG under `outputs/` for the bat-detector / MEMS-mic project if the live capture is noisy).
Expected: `deck/assets/schematic.png` shows the KiCad block-sheet schematic.

- [ ] **Step 6: Source the PDF-report image**

The WeasyPrint PDF only renders in Docker (not Windows). Use an existing rendered report page PNG (e.g. under `outputs/wifi-sensor-node-demo/`) as the report visual, or render the bat-detector report in the Docker image and convert page 1 via `tools/pdf2png.py`. Pick the cleanest available page-1 image → `deck/assets/report_pdf.png`.
Expected: `deck/assets/report_pdf.png` is a legible report page with the ELK diagram + tables.

- [ ] **Step 7: Copy the logo and commit assets**

```bash
cp app/static/assets/logo.png deck/assets/logo.png
git add deck/assets
git commit -m "assets: pitch-deck screenshots (bat detector, mock mode)"
```

---

## Task 2: Theme module + 3 sample slides (style checkpoint)

Build the shared theme and the three style-defining slides: Title (1), the +3.2 number (3), and the Conflict→Resolution slide (5). **STOP after this task for Robert's style approval before building the rest.**

**Files:**
- Create: `deck/theme.py`, `deck/build_deck.py`

- [ ] **Step 1: Invoke the pptx skill**

Invoke `anthropic-skills:pptx` to load the python-pptx workflow and helpers before writing the build script.

- [ ] **Step 2: Write `deck/theme.py`**

Palette constants mirroring `app/static/index.html:14-18` and helpers. Concrete content:

```python
# deck/theme.py — palette mirrors app/static/index.html :root
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

BG      = RGBColor(0x0F, 0x14, 0x19)
PANEL   = RGBColor(0x1A, 0x21, 0x2B)
PANEL2  = RGBColor(0x22, 0x2C, 0x38)
LINE    = RGBColor(0x2D, 0x3A, 0x48)
TEXT    = RGBColor(0xE6, 0xED, 0xF3)
MUTED   = RGBColor(0x8B, 0x98, 0xA5)
ACCENT  = RGBColor(0x4F, 0x9C, 0xF9)   # blue, matches logo
OK      = RGBColor(0x3F, 0xB9, 0x50)   # verified
WARN    = RGBColor(0xD2, 0x99, 0x22)   # rework / conflict
REVIEW  = RGBColor(0xF7, 0x78, 0xBA)   # critic
FONT    = "Segoe UI"

# 16:9 slide size in EMU (13.333in x 7.5in)
SLIDE_W = Emu(12192000)
SLIDE_H = Emu(6858000)

def fill_background(slide, color=BG):
    """Paint the whole slide background a solid color."""
    # implementation: add a full-bleed rectangle at z-order back, no line
    ...

def add_text(slide, left, top, width, height, text, size, color=TEXT,
             bold=False, align=PP_ALIGN.LEFT, font=FONT):
    """Add a textbox with one run; returns the textframe."""
    ...

def add_footer_logo(slide, logo_path="deck/assets/logo.png"):
    """Small logo bottom-right + muted slide tagline."""
    ...

def add_bar(slide, left, top, width, height, frac, color):
    """Draw a horizontal value bar (frac 0..1) for the +3.2 chart."""
    ...
```

Fill in the `...` bodies using python-pptx (`slide.shapes.add_shape`, `add_textbox`). Keep each helper short and single-purpose.

- [ ] **Step 3: Write `deck/build_deck.py` skeleton + slide 1 (Title)**

```python
# deck/build_deck.py
from pptx import Presentation
import deck.theme as T

def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    T.fill_background(s)
    # logo hero (centered-left), big title, tagline, track chip
    T.add_text(s, ..., "AI Circuit Architect", size=54, bold=True, color=T.TEXT)
    T.add_text(s, ..., "From idea to PCB-ready schematic — a society of agents",
               size=22, color=T.MUTED)
    T.add_text(s, ..., "Qwen Hackathon · Track: Agent Society", size=16, color=T.ACCENT)
    return s

def build():
    prs = Presentation()
    prs.slide_width = T.SLIDE_W
    prs.slide_height = T.SLIDE_H
    slide_title(prs)
    slide_number(prs)        # slide 3
    slide_conflict(prs)      # slide 5
    prs.save("deck/AI_Circuit_Architect.pptx")

if __name__ == "__main__":
    build()
```

- [ ] **Step 4: Add slide 3 (the +3.2 number)**

`slide_number(prs)`: big headline "Multi-agent +3.2 design-coverage points over a single agent", two bars (Multi 11.6/12 in ACCENT, Single 8.4/12 in MUTED) via `T.add_bar`, and the 5-design mini-table (Motor +2, Precision +2, Battery IoT +4, Medical +5, Gateway +3) with the caption "the gap widens with complexity". Numbers come from `docs/comparison-batch.md` — do not invent.

- [ ] **Step 5: Add slide 5 (Conflict → Resolution)**

`slide_conflict(prs)`: title "When agents disagree, the design gets better", left = the `deck/assets/society_rework.png` screenshot in a rounded panel, right = a 3-step caption (R1 Critic flags a missing block → Architect reworks → R2 clean) using WARN for the rework arrow. Insert image with `s.shapes.add_picture`.

- [ ] **Step 6: Build and render-check**

```bash
python -m deck.build_deck
```
Then convert to PNG to eyeball (via the pptx skill's render helper, e.g. LibreOffice headless or `tools/pdf2png.py` after a PDF export). Verify: dark bg, no text overflow, logo crisp, screenshot legible.

- [ ] **Step 7: Commit and STOP for review**

```bash
git add deck/theme.py deck/build_deck.py deck/AI_Circuit_Architect.pptx
git commit -m "feat(deck): theme + 3 sample slides (title, +3.2, conflict)"
```
Present the 3 rendered slide PNGs to Robert. **Do not proceed to Task 3 until he approves the style.**

---

## Task 3: Remaining 6 slides

After style approval, add slides 2, 4, 6, 7, 8, 9 to `build_deck.py`, each its own function called from `build()` in slide order.

**Files:**
- Modify: `deck/build_deck.py`

- [ ] **Step 1: Slide 2 (Problem)**

`slide_problem(prs)`: title "Schematic design is slow, expert-only — and one LLM cuts corners". Two-column: left "Today" (manual, days, EE expertise), right "A single LLM" (skips safety/review items: reverse-polarity, overcurrent, reset). Vector icons/blocks, no screenshot.

- [ ] **Step 2: Slide 4 (Roles & decomposition)**

`slide_roles(prs)`: title "A team, not a prompt — six specialist agents". Six labelled role cards in pipeline order: Requirements (plus) · Architect (plus) · Design Critic (max) · Arbitration · PCB Engineer (plus) · PCB Critic (max). Show the model tier under each; colour the two Critics with REVIEW. Caption: "juniors propose, senior reviewers on qwen-max hold them to account".

- [ ] **Step 3: Slide 6 (Measurable efficiency)**

`slide_efficiency(prs)`: title "A deterministic 12-point rubric, not vibes". Left = `deck/assets/compare_panel.png`. Right = the "what single agent skipped" list from `docs/comparison-batch.md` (reverse-polarity 5×, overcurrent 4×, docs/uncertainty 3×, surge/ESD 2×, clock 2×).

- [ ] **Step 4: Slide 7 (It's real)**

`slide_real(prs)`: title "Real, openable output — verified in KiCad". Left = `deck/assets/schematic.png` with a green "ERC 0 · kicad-cli 10.0.2" verified badge chip (OK colour). Right = `deck/assets/report_pdf.png` with caption "professional PDF report + downloadable KiCad project ZIP".

- [ ] **Step 5: Slide 8 (Human-in-the-loop & tech)**

`slide_tech(prs)`: title "AI prepares, the human decides". Left = the loop: approval gates + audience personas (Professional/Student/Maker). Right = tech stack row: Qwen (OpenAI-compatible) · FastAPI · KiCad-CLI · Docker. Vector chips.

- [ ] **Step 6: Slide 9 (Close)**

`slide_close(prs)`: title "Three jury criteria, one society of agents". Three ticked rows: ✓ Decomposition & roles · ✓ Conflict resolution (rework loop) · ✓ +3.2 measured efficiency. Restate the +3.2 number large. Logo + project link placeholder `<github / live URL TBD>`.

- [ ] **Step 7: Build, render-check, commit**

```bash
python -m deck.build_deck
git add deck/build_deck.py deck/AI_Circuit_Architect.pptx
git commit -m "feat(deck): remaining 6 slides (problem, roles, efficiency, real, tech, close)"
```
Render all 9 to PNG and verify no overflow / consistent look.

---

## Task 4: Final polish & verification

**Files:**
- Modify: `deck/build_deck.py` (tweaks only)

- [ ] **Step 1: Full render pass**

Export the deck to PDF/PNG and review all 9 slides side by side. Check: consistent margins, no text clipping, every screenshot legible at slide size, accent/amber/green used consistently, English everywhere (no German leftover).

- [ ] **Step 2: Fit fixes**

Adjust any overflowing text boxes / oversized images found in Step 1. Re-render to confirm.

- [ ] **Step 3: Final commit**

```bash
git add deck/
git commit -m "feat(deck): final pitch deck — 9 slides, render-verified"
```

---

## Self-Review (plan vs spec)

- **Spec coverage:** All 9 slides map to tasks (1→T2, 3→T2, 5→T2; 2,4,6,7,8,9→T3). Look & palette → `theme.py` (T2.2). Mix imagery: screenshots (T1) + vector (T2/T3). Showcase = bat detector (T1.2). Three Track-3 criteria = slides 4/5/6. ✓
- **Placeholder scan:** the `...` in `theme.py`/`build_deck.py` are explicit "fill the helper body with python-pptx" instructions with the signature given, not vague TODOs; the project-link placeholder is a deliberate spec open-item. ✓
- **Type consistency:** helper names (`fill_background`, `add_text`, `add_footer_logo`, `add_bar`) and slide function names (`slide_title`/`slide_number`/`slide_conflict`/…) are used consistently across T2 and T3. ✓
- **Known risk:** preview screenshot timeout (animations) — mitigated by disabling animations via `preview_eval` (T1.3) and the option to reuse existing `outputs/` renders.
