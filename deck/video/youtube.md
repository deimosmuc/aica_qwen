# YouTube — copy-paste text for the demo video

> English (matches the narration + the international jury). Timestamps are for the
> final 2:55 cut — nudge by a second if YouTube complains. Set visibility to
> **Unlisted** for the Devpost submission (or Public if you like).

---

## Title (pick one)

**Recommended:**
`AI Circuit Architect — six AI agents turn plain English into a KiCad project`

Alternatives:
- `Six AI agents that argue about your circuit board | AI Circuit Architect (Qwen)`
- `AI Circuit Architect: a society of AI agents designs a KiCad scaffold, verified`

---

## Description

Six AI agents debate a plain-English hardware brief into a structured, KiCad-verified project scaffold — and catch the boring-but-critical things a single AI quietly skips.

Ask one model for a schematic and it gives you something that *looks* right, but drops reverse-polarity protection, a fuse, ESD, a reset line — the stuff a design review exists to catch. So instead of one model, AI Circuit Architect runs a *society* of six specialist agents that refine each other's work and argue over what's missing, then verify the result against real KiCad.

In this demo, a plain-English "Wi-Fi bat detector" becomes:
• a block-level architecture with typed power and data connections
• a live critic-vs-architect rework loop (the critic sends the design back; the architect revises)
• an honest review pass — open TODOs and explicit "needs human review" items
• a PCB-readiness pack — net classes, controlled impedance, candidate parts, a floorplan, a design-for-test checklist
• a generated KiCad project that actually opens in KiCad and passes structural ERC
• a fair, in-app comparison: the team surfaces 12 of 12 engineering concerns vs 6 for a single agent — a reproducible +3.2 across a five-design benchmark

Honest about scope: this is a structured *starting point*, not a finished or manufacturable schematic. It doesn't wire up every net. You approve the architecture before anything is generated — the engineer stays in control. AI prepares; the human decides.

Built for the Qwen Hackathon (Agent Society track).

⏱️ Chapters
0:00  The trap with one-shot AI schematics
0:21  Why a team, not one model (+3.2)
0:38  Describe a Wi-Fi bat detector
0:59  The agents collaborate — the critic demands rework
1:13  The result: architecture, review, PCB-readiness pack
1:41  Human approval → a verified KiCad project
2:10  Measured, not a vibe: multi-agent vs single (12 vs 6)
2:40  Runs on Qwen + Alibaba Cloud, verified with KiCad

🔗 Links
• Code (open source): https://github.com/deimosmuc/aica_qwen
• Live demo (judge access): https://qwen.rocu.de
• Devpost: <add your Devpost project link>

🛠️ Built with
Qwen Cloud (qwen-plus / qwen-max / qwen-turbo, model tier per agent role) · Alibaba Cloud ECS · Python · FastAPI · Alpine.js · elkjs · KiCad 10 (kicad-cli, real ERC) · WeasyPrint · Docker · GitHub Actions · Caddy

#Qwen #AlibabaCloud #AIagents #MultiAgent #KiCad #PCB #ElectronicsDesign #LLM #AgenticAI #Hackathon

---

## Tags (comma-separated, paste into the Tags field)

AI Circuit Architect, Qwen, Alibaba Cloud, AI agents, multi-agent, agentic AI, LLM, KiCad, PCB design, electronics design, hardware design, schematic, EDA, Qwen hackathon, Agent Society, FastAPI, generative AI, AI for hardware, engineering, hackathon project

---

## Pinned comment (optional)

Honest scope: AI Circuit Architect produces a structured KiCad *scaffold* — an
architecture starting point that opens in KiCad and passes structural checks — not a
finished or manufacturable schematic. The engineer approves the architecture and stays
in control. Code is open source: https://github.com/deimosmuc/aica_qwen
