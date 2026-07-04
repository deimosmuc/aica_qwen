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
`qwen` · `alibaba-cloud` · `python` · `fastapi` · `uvicorn` · `pydantic` ·
`alpine.js` · `javascript` · `elkjs` · `kicad` · `weasyprint` · `pymupdf` ·
`docker` · `github-actions` · `caddy` · `lets-encrypt` · `playwright`

*(Core / mandatory tech first: `qwen` + `alibaba-cloud`. All are actually used —
verified against the code. Trim freely if Devpost feels crowded; the ones I'd keep
no matter what are qwen, alibaba-cloud, python, fastapi, alpine.js, kicad, docker.)*

## Links
- **Live demo:** https://qwen.rocu.de  *(Basic-Auth login: `juror` / <password shared privately with judges>)*
- **GitHub:** https://github.com/deimosmuc/aica_qwen  *(set to public before submission)*
- **Demo video:** <YouTube link — ≤ 3 min>

---

## Inspiration
In an earlier project I tried to get an AI to put together a whole KiCad design for
me: schematic and layout, the full thing. I ran straight into the limits. Wiring up
every net and placing a complex board is genuinely hard, and it's still a problem for
another day.

But one part of that attempt worked better than I expected: the groundwork. The
project hierarchy, the sheet structure, the skeleton you'd otherwise assemble by hand
before the real design even begins. The AI was good at that scaffold and weak at
everything downstream.

So for this hackathon I took that idea and ran with it. Instead of asking one model to
do everything and stop at a plausible first draft, I built the scaffold out properly
and handed it to a small team of agents that refine each other's work and argue over
what's missing, then verify the result against real KiCad.

## What it does
AI Circuit Architect takes a plain-English brief — for example, "a battery-powered
Wi-Fi bat detector with USB-C charging" — and turns it into a structured KiCad
project you can open, inspect, and keep building on.

The work is split across six agents. A Requirements agent turns the brief into
structured requirements and asks a few A/B/C clarifying questions where it needs them.
An Architect proposes a block-level design with typed power and data connections. A
Design Critic, running on the stronger model tier, reviews that design and sends it
back for rework when something is missing, and an Arbitration step resolves the
disagreement. A PCB Engineer and a PCB Critic then prepare the board side and run the
same review-and-revise loop. So it isn't a single pass; it's a team that divides the
work and resolves its own disagreements.

The output is a KiCad scaffold: hierarchical sheets, a block diagram, power-port
symbols, sheet pins, and filled title blocks. It opens in KiCad and passes structural
ERC. You also get a PDF report, a downloadable ZIP, and a three-state badge that
records how far the KiCad verification got.

To be clear about the scope: this is a starting point, not a finished schematic. It
doesn't wire up every net or produce something ready for manufacturing. You approve
the architecture before anything is generated, and the engineer stays in control.

## How we built it
Every agent runs on the Qwen Cloud API, with the model tier chosen per role:
qwen-plus for the junior agents, qwen-max for the senior Critic, qwen-turbo for
cheaper work. The interface is a single FastAPI page with a live "metro-rail" view of
the pipeline and a chat panel that shows the agents handing work back and forth.

The KiCad verification is real rather than simulated. Each generated project is
opened, ERC-checked, and rendered by an actual KiCad 10 install through kicad-cli, so
the verification badge reflects what actually happened. Every Qwen call passes through
a single cost guard that enforces a hard dollar budget, caps tokens, and applies rate
limits; if a limit or error is hit, the app falls back to a scripted mock mode so the
demo keeps working. It's packaged with Docker, built by GitHub Actions, and deployed
on Alibaba Cloud ECS behind Caddy, which handles HTTPS.

## Challenges we ran into
A couple of problems were worth the time they cost. The most misleading one: a
too-tight output-token limit was cutting the Architect's JSON off mid-object. That
made the JSON invalid, which dropped the run into mock mode, which then showed up as a
"Qwen unreachable" message — even though Qwen was reachable the whole time. I raised
the limit and changed the code to report truncation as truncation.

The stronger model, on hard prompts, was both slow and prone to returning malformed
JSON. It now has a longer timeout and a sanitiser, so a bad response degrades
gracefully instead of failing the run. And getting the KiCad scaffold to open
reliably — correct power-symbol names, the exact hierarchical sheet-pin syntax,
coordinates snapped to grid — required a live render gate in the test suite that
rejects any project that doesn't open.

## Accomplishments that we're proud of
The result I trust most is a measured, reproducible one. Across five hard designs, the
multi-agent team covered 11.6 of 12 engineering concerns on average, against 8.4 for a
fair single-agent baseline, scored by a deterministic rubric — an average gain of +3.2
that widens with complexity. The rework loop is visible while it runs: a critic flags
a gap, the architect revises, the critic checks again. The framing also stays honest
throughout, with a three-state verification badge, a real budget guard, and no claim
of a finished board.

## What we learned
The multi-agent advantage didn't come from where I expected. The team doesn't design
anything cleverer; the difference is that the review step doesn't forget the
unglamorous safety and documentation items a single pass tends to drop —
reverse-polarity protection, a fuse, a reset line, an explicit note of what it's
unsure about. And that gap grows with complexity, which is when the help is most
useful. The other lesson was about demos: graceful degradation, mock mode, and honest
error messages matter as much as the happy path.

## What's next for AI Circuit Architect
Next, I'd like to give the candidate parts live pricing and availability through a
dedicated sourcing agent, so the shortlist reflects what's actually in stock. I also
want to extend the schematic enrichment toward wired sub-circuits — still with a human
approving each step — and add a self-correction loop that feeds the rubric's findings
back into the agents, so the system catches more of its own gaps before the user has to.

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
