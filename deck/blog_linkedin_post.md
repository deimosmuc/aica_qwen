# LinkedIn post — AI Circuit Architect (Qwen Hackathon)

> English, first person, single native LinkedIn post. Written to satisfy the Devpost
> **Blog Post Prize** ("a URL to a published Blog or Social Post showing your journey
> building with Qwen Cloud") — the Qwen Cloud build experience is front and centre.
> ~2,600 chars (LinkedIn limit is 3,000). Fill in the two <…> links.

---

## POST BODY (paste into the LinkedIn composer)

A while back I tried to get an AI to design a complete circuit board for me — schematic and layout, the whole thing. It failed.

But *how* it failed is why I spent this hackathon building AI Circuit Architect.

Wiring up every net and placing a complex board turned out to be genuinely hard — the AI fell apart downstream. Yet one part worked far better than I expected: the groundwork. The project hierarchy, the sheet structure, the skeleton you'd otherwise assemble by hand before the real design even begins. AI was good at the scaffold and weak at everything after it.

So I stopped asking one model to do everything and stop at a plausible first draft. Instead I built the scaffold out properly and handed it to a society of six specialist agents that refine each other's work and argue over what's missing.

Building it on Qwen Cloud is where it got interesting:

→ Each agent runs on a Qwen model tier chosen by its role — qwen-plus for the junior agents, qwen-max for the senior Critic that demands rework, qwen-turbo for the cheap work. That per-role tiering was my single most useful decision: a cheap team with one strong reviewer beats one expensive model, at a fraction of the cost.

→ Qwen's OpenAI-compatible endpoint let me stand the whole pipeline up fast, and a single cost guard — hard budget, token caps, rate limits — meant I designed for cost from day one.

→ The honest part of building: qwen-max on hard prompts was sometimes slow and returned malformed JSON. So I added a longer timeout and a sanitiser — a bad response now degrades gracefully instead of killing the run. Building on a real, metered cloud makes you build for failure.

It's deployed on Alibaba Cloud, and every generated project is opened and ERC-checked by a real KiCad install — so the verification badge reflects what actually happened, not a simulation.

The result I trust most is measured: across five hard designs, the team surfaced 11.6 of 12 engineering concerns on average, vs 8.4 for a single agent — a reproducible +3.2 that widens with complexity. And it's not cleverer design. The review step simply doesn't forget the unglamorous safety items a single pass drops: reverse-polarity protection, a fuse, a reset line.

To be clear about scope: this produces a structured KiCad *scaffold* — a starting point that opens in KiCad and passes structural checks, not a finished or manufacturable schematic. You approve the architecture before anything is generated. AI prepares; the engineer decides.

Built for the Qwen Hackathon, Agent Society track. 3-minute demo, code and the live app in the comments 👇

#Qwen #AlibabaCloud #AIagents #KiCad #PCB #Hardware #LLM #BuildInPublic

---

## FIRST COMMENT (post immediately after — keeps links out of the body for reach)

Links:
🎥 3-min demo: <YouTube link>
💻 Code (open source): https://github.com/deimosmuc/aica_qwen
🌐 Live app (judge access): https://qwen.rocu.de
🏆 Devpost: <Devpost project link>

Built on Qwen Cloud + Alibaba Cloud, verified with KiCad.

---

## Posting tips

- **Attach the video natively.** Uploading the 2:55 clip straight to LinkedIn gets far
  more reach than a YouTube link — you keep the YouTube version for Devpost either way.
  (If you'd rather keep it text-first, attach `deck/assets/devpost_cover.png` as the image.)
- **Links go in the first comment**, not the body — LinkedIn tends to suppress posts
  with outbound links in the text. The post's OWN URL is what you submit for the
  Blog Post Prize, so eligibility is unaffected.
- **Tag the official accounts** if you can find them (e.g. Alibaba Cloud / Qwen on
  LinkedIn) — helps visibility for the prize.
- **Timing:** Tue–Thu, ~08:00–10:00 CET tends to perform best.
- After it's live, the LinkedIn post URL also goes into the Devpost "Blog/Social Post"
  field for the Blog Post Prize.
