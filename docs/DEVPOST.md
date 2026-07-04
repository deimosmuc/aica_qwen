# Devpost Submission — AI Circuit Architect

> Copy-paste source for the Devpost submission form. Track: **Agent Society**.
> All claims are deliberately honest — the app produces a *structured KiCad
> scaffold* and a *PCB-readiness pack (prep)*, **not** a finished/manufacturable
> schematic. Keep it that way.

---

## Project name
AI Circuit Architect

## Tagline / Elevator pitch (≤ ~200 chars)
A society of six AI agents that debates natural-language hardware requirements
into a structured, KiCad-verified project scaffold — measurably more complete
than a single agent (+3.2 / 12 coverage).

**Alternatives:**
- Six specialist agents turn a plain-English idea into a KiCad project scaffold —
  with a real critic-vs-architect rework loop that catches what one agent misses.
- Multi-agent electronics co-pilot: NL requirements → architecture → verified
  KiCad scaffold + PCB-readiness pack. AI prepares, the human decides.

## "Built with" tags
`qwen` · `alibaba-cloud` · `python` · `fastapi` · `docker` · `kicad` ·
`caddy` · `pydantic` · `playwright`

## Links
- **Live demo:** https://qwen.rocu.de  *(Basic-Auth login: `juror` / <password shared privately with judges>)*
- **GitHub:** https://github.com/deimosmuc/aica_qwen  *(set to public before submission)*
- **Demo video:** <YouTube link — ≤ 3 min>

---

## Inspiration
A single large language model, asked to design a circuit, gives you a plausible
answer — and quietly skips the boring-but-critical parts: reverse-polarity
protection, overcurrent fusing, a reset line, ESD/surge handling, an explicit
statement of what it is *unsure* about. Those omissions are exactly what a real
engineering review catches. We wanted to see whether a **society of specialist
agents that argue with each other** would close that gap — and whether the gain
would be *measurable*, not just a nice story.

## What it does
AI Circuit Architect turns a plain-English hardware brief ("a battery-powered
Wi-Fi bat detector with USB-C charging") into a **structured KiCad project
scaffold** you can open, inspect and keep building on.

Six agents collaborate, each with a role:
1. **Requirements** — turns the brief into structured requirements and asks
   adaptive A/B/C clarifying questions.
2. **Architect** — proposes a block-level architecture (typed power/data/control
   connections).
3. **Design Critic** *(on the stronger qwen-max tier)* — reviews the architecture
   and **demands rework** when blocks or protections are missing.
4. **Arbitration** — resolves the critic-vs-architect disagreement into a final
   design.
5. **PCB Engineer** — produces a PCB-readiness pack: net classes, constraints,
   candidate parts, floorplan zones, a design-for-test/manufacturing checklist.
6. **PCB Critic** — reviews that pack and drives a second rework loop.

The output is a downloadable ZIP containing a KiCad project (hierarchical sheets,
block diagram, power-port symbols, sheet pins, filled title blocks) that **opens
in KiCad and passes structural ERC**, plus a professional PDF report and an
honest three-state verification badge (verified-in-KiCad / structural-only /
failed).

**Important, honest scope:** this is a *starting point* — a structured scaffold
and readiness prep. It is **not** a complete, wired, manufacturable schematic.
The human engineer stays in control and approves the architecture before anything
is generated (human-in-the-loop).

## The Agent-Society angle (Track 3)
The three things the Agent-Society track asks for, and where each lives:

1. **Task decomposition + role assignment** — six agents with distinct roles and
   model tiers (juniors on qwen-plus, the Critic supervisor on qwen-max).
2. **Conflict resolution** — not a straight pipeline: the **Design Critic →
   Architect rework loop** and the **Arbitration** step are a genuine
   disagree-and-resolve cycle, mirrored again by the **PCB Critic → PCB
   Engineer** loop. You can watch it happen live in the "Agent Society" chat view.
3. **Measurable efficiency gain vs. a single-agent baseline** — over 5 diverse,
   hard designs the multi-agent system scored **11.6 / 12 vs. 8.4 / 12 for a fair
   single-agent baseline — an average +3.2 coverage gain that widens with
   complexity** (Medical wearable +5, Battery IoT +4). The single pass most often
   skips reverse-polarity (5×), overcurrent/fuse (4×), explicit uncertainty (3×),
   surge/ESD (2×) and a clock (2×). Scored by a deterministic 12-concern rubric,
   so the number is reproducible, not a vibe.

## How we built it
- **Qwen Cloud API** (OpenAI-compatible endpoint) drives every agent; the model
  tier is chosen per role (qwen-plus / qwen-max / qwen-turbo).
- **FastAPI + a single-page UI** (Alpine.js) for the run / step / compare / bench
  flows, the live "metro-rail" pipeline view and the Agent-Society chat.
- **kicad-cli as a real runtime tool** — generated scaffolds are opened, ERC-checked
  and rendered to SVG/PDF by an actual KiCad 10 install, so the verification badge
  reflects reality.
- **An API cost guard** — every Qwen call passes one chokepoint enforcing a hard
  USD budget, per-call token caps, response caching and rate limits. On any limit
  or error it falls back to a scripted Mock Mode, so the demo never breaks.
- **Deployment:** GitHub Actions builds a Docker image → GitHub Container Registry
  → pulled onto an **Alibaba Cloud ECS** box, with **Caddy** terminating HTTPS
  (Let's Encrypt) and Basic Auth in front of the app.

## Challenges we ran into
- **Truncation looked like an outage.** A too-tight output-token cap silently cut
  the Architect's JSON mid-object → invalid JSON → Mock fallback, surfaced as a
  misleading "Qwen unreachable" notice. We raised the cap and made truncation
  report itself honestly.
- **qwen-max on very complex prompts** is both slow (>60 s) and occasionally
  returns malformed JSON. We added a longer timeout and a sanitizer/validation
  fallback so a bad response degrades gracefully instead of crashing the run.
- **Making the KiCad scaffold real, not fake.** Getting a generated project to
  actually open and pass structural ERC (correct power-symbol nicknames,
  hierarchical sheet-pin syntax, on-grid coordinates) took a live kicad-cli render
  gate in the tests.

## Accomplishments we're proud of
- A **reproducible +3.2 coverage gain** backed by a deterministic rubric — a real
  number, not a claim.
- A visible **conflict→resolution arc** (critic flags a gap → architect reworks →
  critic clean) that you can literally watch in the Agent-Society view.
- Honest engineering throughout: a three-state verification badge, a cost guard
  with a hard budget, and framing that never overpromises.

## What we learned
- Multi-agent value shows up most on the *unglamorous* safety/review items a
  single pass skips — and the gap widens with design complexity.
- For a live demo, graceful degradation (Mock Mode, caching, honest notices) is as
  important as the happy path.

## What's next
- Live BOM pricing as a dedicated Sourcing Agent on top of the candidate parts.
- Deeper schematic enrichment toward wired sub-circuits (still human-approved).
- A runtime self-correction loop that feeds rubric gaps back into the agents.

---

## Submission checklist
- [ ] GitHub repo set to **public**, README polished
- [ ] Demo video (≤3 min) recorded, +3.2 number in the first 60 s, uploaded & linked
- [ ] Live-demo URL + juror login entered in Devpost
- [ ] Cover image + gallery screenshots uploaded (in `deck/assets/`):
  - `devpost_thumbnail.png` (1200×800, **3:2**) — **the Devpost card thumbnail** (condensed: title, agent dots, big +3.2; reads when small)
  - `devpost_cover.png` (1280×720, 16:9) — hero / gallery banner
  - `devpost_thumb.png` (1000×1000) — square tile / social
  - `metro_rail.png`, `architecture.png`, `society_rework.png`, `compare_panel.png` — product shots
  - Regenerate anytime: `python deck/render_cover.py` (thumbnail/cover/square) · `python deck/capture_devpost.py` (product, needs mock app on :8011)
- [ ] PowerPoint deck attached (PDF export)
- [ ] Alibaba Cloud deployment + Qwen API usage mentioned in the text (mandatory tech)
- [ ] Team members added
