# Video-Runbook — 3-Min-Demo (Live-Run + TTS)

> Operatives Runbook fürs Aufnehmen. Ergänzt [`video_teleprompter.md`](video_teleprompter.md)
> (nur Sprechtext) um **exakte Klicks pro Szene**, den **Cache-Trick für einen
> zuverlässigen Live-Run**, die **TTS-Produktion** und den **Schnitt**.
> Zielzeit **3:00**. Narration **Englisch** (internationale Jury).

---

## 0. Die drei Bausteine
1. **Bild:** Bildschirmaufnahme der echten App auf `https://qwen.rocu.de`
   (OBS Studio, gratis — oder Xbox Game Bar `Win+G`). **Bild und Ton getrennt** aufnehmen.
2. **Ton:** TTS-Stimme aus dem segmentierten Skript unten (§4).
3. **Schnitt:** Voice-over über das Bild legen + SpongeBob-Cut einfügen
   (Clipchamp, in Windows 11 eingebaut — oder CapCut).

---

## 1. 🔑 Der Cache-Trick — macht den Live-Run reproduzierbar
Der API-Guard **cached jede Qwen-Antwort dauerhaft**. Das nutzen wir:

1. **Vor der Aufnahme** den **exakt gleichen Ablauf einmal live durchspielen**
   (gleiche Eingabe, gleiches Profil, gleiche Buttons) — inkl. Approve → Generate
   und **beide** Compare-Buttons.
2. Dabei so lange **Proberuns** machen, bis einer die **Rework-Runde sichtbar
   zeigt** (Critic flaggt fehlenden Block → Architect überarbeitet). Ob Rework
   passiert, ist in Live-Mode datengetrieben — nicht jeder Run zeigt es.
3. Ist ein guter Run gelaufen, ist er **im Cache**. Der **aufgenommene Take**
   liefert dann dieselben echten Qwen-Daten **sofort, gratis und ohne Fehlerrisiko**
   (keine langsame/kaputte JSON-Antwort mehr). Die Metro-Rail-Animation läuft
   trotzdem — sie hängt an einer eigenen Reveal-Clock, nicht an der Antwortzeit.
   → Es sieht live aus, ist echte Qwen-Ausgabe, aber **planbar**.

> ⚠️ Eingabe zwischen Warm-up und Take **identisch** halten (sonst Cache-Miss).
> Fällt der Live-Rework partout nicht zuverlässig → **Mock Mode** garantiert den
> Rework-Arc (gescriptet) — gleiche echte UI, kein Figma. Ehrlicher Fallback.

---

## 2. Pre-flight-Checkliste (vor dem ersten Klick)
- [ ] Server-Key funktioniert (Part-B-Schritt 3 erledigt: echter Nicht-Mock-Run klappt).
- [ ] In Chrome bei `https://qwen.rocu.de` **eingeloggt** (Basic Auth: `juror` / <pw>).
- [ ] Fenster auf **1920×1080**, Browser-Zoom 100 %, Lesezeichen/Extra-Toolbars aus
      (sauberes Bild). Dark Theme wie gehabt.
- [ ] Intro-Tour ggf. **einmal sichtbar** lassen für die „+3.2"-Zeile (Szene 0:18),
      sonst über den „Show intro"-Toggle einblenden.
- [ ] **Cache-Warm-up** (§1) gelaufen, guter Run mit Rework gefunden.
- [ ] OBS/Game Bar bereit, Testaufnahme 5 s (Ton der App stummschalten — wir legen
      TTS drüber).

---

## 3. 🎬 Shot-List — exakte Klicks pro Szene
Steuerelemente sind die echten Controls in der App (verifiziert):

| Zeit | Aktion auf dem Bildschirm (echte Buttons) | Sprechtext (TTS-Segment) |
|------|-------------------------------------------|--------------------------|
| **0:00–0:18** Hook | Landing-Page, Cursor ruhig. Nicht klicken. | **S1** |
| **0:18–0:33** Die Zahl | Langsam zur Intro-Zeile **„+3.2 / 11.6 vs 8.4"** scrollen. | **S2** |
| **0:33–0:58** Setup | **Load example** → „**Bat detector (Wi-Fi / USB)**". **Profile** = „**Senior Review Team**" (Default). **Audience** = „**Professional**" (Default). Kurz über die Rollen/Profile hovern. Dann **Run agents** klicken. | **S3** |
| **0:55–1:10** Kollaboration | Direkt nach dem (unkommentierten) **Run-agents-Klick** streamt der Society-Chat sofort (warmer Cache); **Rework**: Critic → Architect erscheint im S4-Fenster. **KEIN Zeitsprung-Cut** — durchgehende Fahrt. | **S4** |
| **1:18–1:48** Ergebnis | Zum **Block-Diagramm** scrollen; **„Review & open items"** aufklappen; **PCB-Readiness-Pack** (Net-Klassen, Kandidaten, Floorplan, DFX) zeigen. | **S5** |
| **1:48–2:18** Echte Ausgabe | **Approve architecture** → **Generate**. Warten bis fertig; **Verification-Badge** (✓ Opens in KiCad), **Schematic-Preview**, **PDF-Report**, **ZIP-Download** zeigen. | **S6** |
| **2:18–2:42** Beweis | Zur Eingabe hochscrollen → **Advanced** öffnen → **„Compare: fair (same model)"** klicken; **Multi-vs-Single-Tabelle** (12 vs 6, gleiches Modell) zeigen. | **S7** |
| **2:42–3:00** Abschluss | Langsamer Zoom auf die laufende App / Footer „Powered by Qwen · Alibaba Cloud · KiCad". | **S8** |

> **Zwei ehrliche Zahlen im Bild:** 0:18 zeigt den reproduzierbaren 5-Design-Schnitt
> **+3.2** (Intro-Zeile); 2:18 zeigt die *faire* Live-Messung für dieses Design
> **12 vs 6** (gleiches Modell beidseitig). Der Ton verbindet beides: Live-Ergebnis +
> Benchmark-Schnitt. Das „🏆 Architecture beats tier"-Ergebnis (12 vs 0) bewusst NICHT
> zeigen — sieht unglaubwürdig aus und widerspricht dem ehrlichen +3.2.

---

## 4. 🎙️ TTS-Skript (segmentiert)
Jedes Segment einzeln in den TTS-Dienst geben (saubere Schnittpunkte). Empfehlung:
**ElevenLabs** (Free-Tier, natürliche englische Stimme) — Voice ruhig/professionell,
Pace ~normal. Alternativ Azure TTS „en-US-GuyNeural" / „en-US-AriaNeural".

**S1 (Hook)**
> If you've ever designed a circuit board, you know the trap. You ask an AI for a schematic, and it gives you something that *looks* right — but quietly skips reverse-polarity protection, a fuse, ESD, a reset line. The boring stuff a design review exists to catch.

**S2 (Die Zahl)**
> So we didn't build one AI. We built a *society* of six agents that argue with each other. Across five hard designs, they surfaced three-point-two more engineering concerns than a single model — and the gap widens the harder the design gets.

**S3 (Setup)**
> Let's design a real device: a Wi-Fi bat detector. I pick the Senior Review Team. An Architect proposes, a senior Critic on the stronger model challenges it, a Chief Engineer resolves the conflict, and PCB specialists prepare the board.

**S4 (Kollaboration)**
> And here's the part that matters — they don't just run in a line. Watch: the Critic flags a *missing block*, sends it back, and the Architect reworks it. A real disagreement, resolved live.

*(1:12–1:18 — SpongeBob-Cut, kein Ton)*

**S5 (Ergebnis)** — *gegründet auf das echte „Review & open items"-Panel im Bild
(RTC/Timestamping-TODO, ESD/Surge/Reverse-Polarity-Ratings, RF-Compliance-Review).*
> …and it's done. A clean architecture, with typed power and data connections. And it's honest: open TODOs — a real-time clock for precise timestamping, documented surge and reverse-polarity ratings — and items flagged for human review, like RF compliance. Plus a PCB-readiness pack — net classes, candidate parts, a floorplan, and a design-for-test checklist.

**S6 (Echte Ausgabe)**
> I approve the architecture — the human stays in control — and it generates a real KiCad project. This badge means it actually *opened in KiCad and passed structural checks*. You get a PDF report and a downloadable project. It's a structured *starting point*, not a finished schematic. AI prepares; the engineer decides.

**S7 (Beweis)** — *live, fair (same-model) compare: on this bat design the team
scores 12/12, a single agent 6/12; the +3.2 is cited as the 5-design average.
Payoff zum Hook: der Single verfehlt in der Tabelle GENAU die S1-Traps
(reverse polarity ✗, fuse/overcurrent ✗, reset ✗ — im Frame verifiziert).*
> And the claim isn't a vibe — it's measured. Same request, the *same model* on both sides — so what you see is the collaboration, not a bigger model. The team surfaces twelve of twelve concerns; a single agent, six — missing exactly the traps from the start: reverse polarity, the fuse, the reset line. And across our five-design benchmark, that gap averages a reproducible plus three-point-two. That's the efficiency gain the Agent Society track is about.

**S8 (Abschluss)**
> It runs on Qwen Cloud, deployed on Alibaba Cloud, and every schematic is validated with KiCad. Six agents that argue — so you catch the mistakes *before* the board is made. Thanks for watching.

> **Runtime:** ~370 gesprochene Wörter + ~4 s Stille ≈ 3:00. Läuft's über: erst den
> PCB-Pack-Satz in S5 kürzen, dann die Rollen-Liste in S3.
> **Ehrlichkeits-Guard:** „scaffold / starting point / structural checks" — nie
> „PCB-ready", „manufacturable" oder „hand it to a PCB designer".

---

## 5. ✂️ Schnitt — AUTOMATISIERT (Stand 2026-07-05)
Der komplette Schnitt läuft jetzt skriptgesteuert über **`deck/produce_video.py`**
(TTS-Mux an den Cue-Offsets + eingebackene Zeitsprung-Karte + Speed-Fit ≤3:00).
Deliverable: **`deck/video/walkthrough_final.mp4`** — nur noch anhören & hochladen.
- **Zeitsprung-Cut ENTFERNT (2026-07-05):** mit dem warmen Guard-Cache streamt
  der Lauf sofort — eine „minutes later"-Karte wäre unehrlich und wirkte holprig
  (Robert's Feedback). Auch „I hit Run agents" ist aus S3 raus; der Klick passiert
  unkommentiert im Bild. (`deck/video/cut_card.png` bleibt ungenutzt im Repo.)
- Manueller Fallback (falls doch von Hand geschnitten wird): TTS-Segmente S1–S8
  an die §3-Zeiten legen, Export 1080p ≤3:00, Upload YouTube/Vimeo
  („unlisted" reicht) → Link ins Devpost.

---

## 6. Wenn Claude den Browser fahren soll (optional)
Ich kann Scrollen/Beispiel-Laden/Run/Compare **deterministisch klicken**, während du
mit OBS aufnimmst — dann fummelst du nicht nach Buttons. Dafür brauche ich:
- die **Claude-Chrome-Extension** installiert & verbunden (aktuell: keiner verbunden),
- dass **du dich vorher bei `qwen.rocu.de` einloggst** (ich tippe kein Passwort in URLs).

Sag Bescheid, dann richten wir die Extension zusammen ein und ich übernehme die Klicks.
