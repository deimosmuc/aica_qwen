# Final To-Dos — Hackathon Submission

> **DEADLINE: July 20, 2026** (extended from July 9 — confirmed by Robert 2026-07-11).
> Track: **Agent Society**. Submission via Devpost.
> Legend: 🧑 = only Robert can do · 🤖 = Claude can prepare/do · ✅ = done

---

## 🔴 0. Proof of Deployment — MANDATORY (no proof = not eligible!)

New requirement from the Devpost×Qwen email (2026-07-01). Two pieces of evidence:

- [x] ✅ **Code file with the Qwen Cloud Base URL visible.** Already satisfied —
  link this at submission: [`app/services/config.py:18`](app/services/config.py)
  → `qwen_base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"`
  (also in `.env.example:6`, `deploy/app.env.example:10`). This is the accepted
  standard DashScope-International URL.
- [x] ✅ 🧑 **Screenshot of running resources in the Alibaba Cloud Workbench.**
  *(done 2026-07-04 — instance `i-gw8eiydjod7emy4zs7uq`, region Germany (Frankfurt),
  status Running; DNS-confirmed public IP 43.114.8.16 = `qwen.rocu.de`. Console kept
  in Chinese deliberately — Qwen/Alibaba jury reads it; all required fields legible.)*
  1. Log in to the [Alibaba Cloud ECS Console](https://ecs.console.aliyun.com).
  2. Go to **ECS → Instances**, pick the region where the server runs.
  3. Instance must show status **"Running"** — screenshot so **name/ID, region,
     status** are visible. Save it for the Devpost upload.
- [x] ✅ 🧑 **Confirm the plan/URL match.** *(2026-07-04 — live server returns real,
  non-mock answers, so the standard `dashscope-intl` URL is correct.)* We use the standard `dashscope-intl` URL.
  Only if your Qwen key is a **"Token Plan"** key would we need the
  `token-plan.ap-southeast-1.maas.aliyuncs.com` URL instead. If the live server
  returns real (non-mock) answers, we're correct as-is.

---

## ✅ 1. Devpost Submission Checklist (from the email)

- [x] ✅ 🧑 Public, open-source code repo (public since 2026-07-04, verified live)
- [x] ✅ Code file with Qwen Cloud Base URL clearly visible (`app/services/config.py`)
- [x] ✅ 🧑 Screenshot: proof of deployment on Alibaba Cloud (see §0) *(2026-07-04)*
- [ ] **3-minute** demo video — real working app, **not** a Figma mockup (see §4)
  - ⚠️ Note: the email says **3 min** (earlier we assumed 5). Plan for **3 min**.
- [x] ✅ Track identified: **Agent Society**

---

## 2. Server / Deployment  🧑 (with 🤖 support)

- [x] ✅ Server limits (API-Guard) adjusted in `app.env` ($35 budget, 6000 output tokens, 15/min, 250/day)
- [x] ✅ 🧑 Take the Alibaba Workbench "Running" screenshot (§0) *(2026-07-04)*
- [ ] ⏭️ 🧑 **Rotate the Qwen API key — SKIPPED deliberately (2026-07-04).** Key was
  never leaked/committed (secret scan green: not in working tree or git history), so
  making the repo public did NOT expose it. Rotate only IF the key appears on screen
  during video capture, or the local `.env` is ever suspected exposed. If needed:
  generate a fresh key in the Alibaba console → update **only** `deploy/app.env`
  on the server → `docker compose up -d --force-recreate app`.
- [ ] 🧑 Verify the live demo still works end-to-end after any change (real Qwen run, not Mock)

## 3. GitHub / Repo  🧑 + 🤖

- [x] ✅ 🤖 **Re-run the secret scan right before pushing:** `bash tools/secret_scan.sh`
  (exits non-zero if anything leaks). Checks working tree + full git history for
  keys/PATs/auth-hashes and confirms `.env`, `deploy/app.env`, `deploy/caddy.env`
  are gitignored + untracked. Audit was **PASS** on 2026-07-01, re-run **PASS 2026-07-04** right before the push.
- [x] ✅ 🤖 Commit the new submission files (README, `docs/DEVPOST.md`, `deck/assets/*`,
  `deck/cover.html`, `deck/render_cover.py`, `deck/capture_devpost.py`, this file). *(2026-07-02, secret scan PASS before commit)*
- [x] ✅ 🧑 Make the repo **public** on GitHub (`deimosmuc/aica_qwen`). *(2026-07-04)*
- [x] ✅ 🧑 Enable **GitHub Secret Scanning + Push Protection** (free on public repos) as a second net. *(both ON, 2026-07-04)*
- [x] ✅ 🤖 **Honesty fix:** intro-tour line in `app/static/index.html` reworded to
  "structured KiCad starting point — an architecture scaffold ... review and build on";
  full scan of user-facing strings found no other overpromise (all remaining
  "production-ready" mentions are negated or part of the honesty validator). *(2026-07-02)*

## 4. Demo Video (3 min)  🧑 record + 🤖 script

- [x] ✅ **3-minute storyboard/script written** (below) + clean **teleprompter
  read-aloud version** in [`deck/video_teleprompter.md`](deck/video_teleprompter.md).
- [x] ✅ 🤖 Picture track DONE — recorded scripted via Playwright against the keyed
  local server (`deck/capture_video.py` + `deck/produce_video.py`), real Qwen data
  from the warm cache (bat-detector run incl. rework + fair compare). NOT Mock
  (Mock would show the wrong industrial board), not a Figma mockup.
- [x] ✅ 🤖 Voice-over DONE via edge-tts (en-US-GuyNeural, Robert's pick) — clips in
  `deck/video/audio/`, muxed automatically by `deck/produce_video.py`.
- [x] ✅ 🤖 Time-jump cut REMOVED entirely (2026-07-05, Robert's call): the warm
  guard cache streams the run in immediately, so a "minutes later" card was
  dishonest and jarring. One continuous ride; "I hit Run agents" dropped from S3
  (the click happens uncommented on screen). No SpongeBob, no card, no manual edit.
- [ ] 🧑 Listen through `deck/video/walkthrough_final.mp4` once (esp. "KiCad"/"Qwen"
  pronunciation), then upload to YouTube/Vimeo (≤3 min) and paste the link into Devpost.

### 📹 3-Minute Video Script — Live App Walkthrough

**Format:** screen recording of the real app (no PowerPoint / no Figma). Narration
in **English**. Total **3:00**. Keep energy up; you're taking a fellow engineer on a
quick ride. Stage notes in German for Robert; the *"You say"* lines are what you speak.

| Time | On screen (live app) | You say (EN) |
|------|----------------------|--------------|
| **0:00–0:18** · Hook | App landing page at `qwen.rocu.de`, cursor idle | "If you've ever designed a circuit board, you know the trap: you ask an AI for a schematic, and it gives you something that *looks* right — but quietly skips reverse-polarity protection, a fuse, ESD, a reset line. The boring stuff that a design review exists to catch." |
| **0:18–0:33** · Idea + number | Scroll to the intro line showing **11.6 vs 8.4 / +3.2** | "So we didn't build one AI. We built a *society* of six agents that argue with each other. Across five hard designs they surfaced **+3.2 more engineering concerns** than a single model — and the gap widens the harder the design gets." |
| **0:33–0:58** · Set up the run | Load the **Bat detector** example; pick **Senior Review Team** + **Audience: Professional**; hover the agent roles | "Let's design a real device — a Wi-Fi bat detector. I pick the *Senior Review Team*: an Architect proposes, a senior Critic on the stronger model challenges it, a Chief Engineer resolves the conflict, then PCB specialists prepare the board." *(Run agents wird unkommentiert geklickt)* |
| **0:55–1:10** · Live collaboration | Right after the click the **Agent Society** chat streams in (warm cache — immediate); Critic flags a gap → Architect reworks. **No time-jump cut** — continuous ride. | "And here's the part that matters — they don't just run in a line. Watch: the Critic flags a **missing block**, sends it *back*, and the Architect reworks it. That's a real disagreement being resolved, live." |
| **1:18–1:48** · The result | Back to the app: the **block diagram**, **Review & open items**, **PCB-Readiness pack** | "…and it's done. A clean architecture with typed power and data connections. And it's honest: open TODOs — a real-time clock for precise timestamping, documented surge and reverse-polarity ratings — and items flagged for human review, like RF compliance. Plus a PCB-readiness pack: net classes, candidate parts, a floorplan, and a design-for-test checklist." |
| **1:48–2:18** · Real output | Click **Approve architecture** → **Generate**; show the **verification badge**, schematic preview, **PDF report**, **ZIP** | "I approve the architecture — the human stays in control — and it generates a real **KiCad project**. This badge means it actually *opened in KiCad and passed structural checks*. You get a PDF report and a downloadable project. It's a structured **starting point**, not a finished schematic — AI prepares, the engineer decides." |
| **2:18–2:42** · Proof | Open **Advanced → Compare: fair (same model)**; show the **Multi vs Single** table | "And the claim isn't a vibe — it's measured, live and in-app. Same request, the *same model* on both sides — so this is the collaboration itself, not a bigger model. The team surfaces **12 of 12** concerns; a single agent, **6**. Across our five-design benchmark that gap averages a reproducible **+3.2**. That's the efficiency gain the Agent Society track is about." |
| **2:42–3:00** · Close | Slow zoom on the running app / footer "Powered by Qwen · Alibaba Cloud · KiCad" | "It runs on **Qwen Cloud**, deployed on **Alibaba Cloud**, and every schematic is validated with **KiCad**. Six agents that argue — so you catch the mistakes *before* the board is made. Thanks for watching." |

**Tips**
- Two honest numbers on screen: the reproducible 5-design average **+3.2** (intro, 0:18) *and* the **fair live compare 12 vs 6** for this design (2:18). The narration ties them together. Do **not** show the "🏆 Architecture beats tier" result (12 vs 0) — a single agent scoring ~0 looks broken and oversells the honest +3.2.
- No time-jump cut: the warm cache streams the run in immediately — the video is one continuous ride.
- If you narrate live while clicking, record **video and audio separately** and lay the voice-over on top — much cleaner than talking while hunting for buttons.
- Honesty guardrails for the voice-over: say "scaffold / starting point / structural checks", never "PCB-ready", "manufacturable", or "hand it to a PCB designer".

## 5. Devpost Form Content  🧑 enter + 🤖 prepared

Source text is ready in [`docs/DEVPOST.md`](docs/DEVPOST.md).

- [x] ✅ Tagline / elevator pitch (in DEVPOST.md)
- [x] ✅ Project description (Inspiration / What it does / How we built it / …)
- [x] ✅ "Built with" tags
- [x] ✅ Cover image + gallery screenshots (`deck/assets/devpost_cover.png`, `devpost_thumb.png`, `metro_rail.png`, `architecture.png`, `society_rework.png`, `compare_panel.png`)
- [ ] 🧑 Enter all of the above into the Devpost form
- [ ] 🧑 Add links: **live demo** `https://qwen.rocu.de` + **juror login** (share password privately, NOT in the repo), GitHub URL, video URL
- [ ] 🧑 Link `app/services/config.py` as the Base-URL proof
- [ ] 🧑 Upload the Alibaba Workbench screenshot
- [ ] 🧑 Attach the pitch deck (export `deck/AI_Circuit_Architect.pptx` → PDF)
- [ ] 🧑 Add team members

## 6. Pitch Deck  🤖 + 🧑

- [x] ✅ 9-slide deck built (`deck/AI_Circuit_Architect.pptx`)
- [x] ✅ 🤖 Re-check all deck claims for honesty (no "PCB-ready" / "manufacturable")
  *(2026-07-04 — audited build_deck.py + extracted the built pptx text: 9 slides, no
  un-negated overpromise. Honest "scaffold / starting point / structural ERC clean".)*
- [x] ✅ 🤖 Export to PDF for the Devpost attachment *(`deck/AI_Circuit_Architect.pdf`, 9pp, LibreOffice)*

---

## Already Done (progress so far)

- ✅ App feature-complete + browser-verified; full 6-agent pipeline with rework loops
- ✅ Deployed & running on Alibaba Cloud ECS (`https://qwen.rocu.de`, HTTPS + Basic Auth)
- ✅ Server API-Guard limits set to sane values
- ✅ `docs/DEVPOST.md` — full submission text (honest framing)
- ✅ `README.md` — rewritten, public-ready, with cover + screenshots + honest scope
- ✅ Devpost images rendered (cover, square thumb, 4 product screenshots) in `deck/assets/`
- ✅ Secret audit clean (no keys in repo or git history)
- ✅ Qwen Base URL present & visible in code (proof-of-deployment item 1)

## Key facts / gotchas to remember

- **Deadline:** July 20, 2026 (extended from July 9). Don't cut it close.
- **Video = 3 minutes** (email), not 5.
- **No proof of deployment = disqualified.** The Workbench screenshot is the one
  irreplaceable thing only Robert can produce.
- Keep the real Qwen key ONLY in local `.env` and server `deploy/app.env` — never
  in README, docs, commits, issues, or the video.
- The live demo login password is shared with judges privately, never in the repo.
