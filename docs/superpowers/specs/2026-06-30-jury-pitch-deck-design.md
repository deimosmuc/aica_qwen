# Jury Pitch Deck — Design Spec

**Date:** 2026-06-30
**Deliverable:** PowerPoint deck for the Qwen hackathon submission (Track 3 — Agent Society)
**Status:** Approved (brainstorming), ready for implementation plan

## Purpose & constraints

A single deck that serves **both** as speaker support inside the 5-minute demo video **and** as a self-contained artifact uploaded to Devpost that reads without narration ("both in one" — compromise: clear visuals, but each slide carries enough text to stand alone).

- **Audience:** Track-3 jury (Agent Society). They explicitly score three things: (1) task decomposition + role assignment, (2) resolving disagreements/execution conflicts, (3) measurable efficiency gain over a single-agent baseline. The deck devotes one slide to each.
- **Length:** compact, 9 slides. No feature tour — one sharp story.
- **Language:** English only (project-wide directive).
- **Format:** 16:9 widescreen, `.pptx`.

## Visual identity (mirror the app)

Dark theme, mirroring `app/static/index.html` `:root` tokens so deck and product feel like one piece:

- Background `#0f1419`, panel `#1a212b` / `#222c38`, hairline `#2d3a48`
- Text `#e6edf3`, muted `#8b98a5`
- **Accent (primary) `#4f9cf9`** — matches the blue logo
- Amber `#d29922` = rework/conflict; Green `#3fb950` = verified/pass; Pink `#f778ba` = critic
- Logo: `app/static/assets/logo.png` (blue "AC" monogram with circuit traces), top-left or title hero
- Fonts: Segoe UI / system sans (matches the app's stack); no serif

## Imagery strategy (mix)

- **Real screenshots** for product proof: Society-chat with the amber rework arc (slide 5), Compare panel (slide 6), KiCad schematic + PDF report (slide 7). Captured from the app in Mock Mode via the preview server for determinism.
- **Clean vector graphics** built in the deck for concept slides: the +3.2 bar (slide 3), the 6-role team (slide 4), close recap (slide 9).

## Authoritative data (from `docs/comparison-batch.md`, all live qwen)

Headline = the **batch average over 5 diverse hard designs**, not a single run:

| Design | Multi | Single | Δ |
| --- | :---: | :---: | :---: |
| Motor + safety | 11/12 | 9/12 | +2 |
| Precision analog | 11/12 | 9/12 | +2 |
| Battery IoT | 12/12 | 8/12 | +4 |
| Medical wearable | 12/12 | 7/12 | +5 |
| Industrial gateway | 12/12 | 9/12 | +3 |
| **Average** | **11.6/12** | **8.4/12** | **+3.2** |

Key narrative: **the gap widens with complexity** (Medical +5, Battery IoT +4). What the single agent most often skips: reverse-polarity (5×), overcurrent/fuse (4×), docs/uncertainty (3×), surge/ESD (2×), clock (2×).

## Slide-by-slide

1. **Title** — Logo, "AI Circuit Architect", tagline *"From idea to PCB-ready schematic — a society of agents"*, Track: Agent Society. Vector hero on dark bg.
2. **Problem** — Schematic design is slow and expert-only; a *single* LLM systematically omits safety/review items. Vector.
3. **The number (front-loaded)** — **Multi 11.6/12 vs Single 8.4/12 = +3.2**, gap *widens* with complexity. Large vector bar + the 5-design mini-table. (Belongs in the video's first 60s.)
4. **Criterion 1 — Roles & decomposition** — 6 agents as a team: Requirements · Architect · Design Critic · Arbitration · PCB Engineer · PCB Critic, each with its model tier (juniors on qwen-plus, senior Critic on qwen-max). Vector role diagram.
5. **Criterion 2 — Conflict → resolution** ⭐ (the emotional/technical peak) — the Critic→Architect rework loop: round 1 a gap is flagged → round 2 clean. Real **screenshot** of the Society-chat view with the amber rework packets.
6. **Criterion 3 — Measurable efficiency** — the deterministic 12-point rubric; concrete list of what the single agent skips (reverse-polarity, overcurrent, reset). Real **screenshot** of the Compare panel.
7. **It's real** — proof it runs: real KiCad schematic (kicad-cli 10.0.2, **ERC 0**) + the professional PDF report. Real **screenshots** (schematic preview + report page).
8. **Human-in-the-loop & tech** — "AI prepares, human decides": approval gates, audience personas. Stack: Qwen (OpenAI-compatible) · FastAPI · KiCad-CLI · Docker. Vector + small icons.
9. **Close** — the three criteria ✓ + the +3.2 number restated + project link / CTA. Logo, vector.

## Out of scope (YAGNI)

- Per-feature slides for clarification, preset bench, impedance, personas as standalone (these live in the live tool / video, not the jury deck).
- Animations/transitions beyond simple builds (the deck must read statically on Devpost).
- Speaker notes script for the video narration — separate deliverable if wanted later.

## Showcase design (locked)

**Bat detector (Wi-Fi / USB)** — the built-in example at `app/static/index.html:1105`: *"Design the electronics for a bat-detection device. The ultrasonic bat calls should be captured with an ultrasonic MEMS microphone and their frequency spectrum streamed to a host PC over Wi-Fi and/or USB."* Memorable for the jury **and** reproducible in the video via the "Load example" button. Drive it in Mock Mode with the **Senior Review Team** profile so a visible rework round renders, and confirm ERC 0 for the slide-7 artifacts.

## Open items to resolve during implementation

- Whether the close slide's "project link" is the public GitHub URL (depends on the repo being pushed) or the deployed Devpost URL. Use a placeholder until both are final.
