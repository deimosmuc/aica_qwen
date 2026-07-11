"""Capture full-frame gallery screenshots of the running app for the Devpost
Project Media image gallery.

Unlike capture_assets.py (which makes tightly-cropped component crops for the
pitch deck), this drives a full bat-detector run through the Senior Review Team
profile and saves whole, framed section panels at 2x DPR into deck/gallery/ —
so a juror sees the real app working end to end: the live agent pipeline, the
Critic->Architect rework, the proposed architecture, the honesty review, the
PCB-readiness pack, the multi-vs-single comparison, human approval and the
generated KiCad schematic.

Capture against the KEYED server (real Qwen agents) so the whole gallery is
coherent: the bat-detector brief yields a real bat-detector architecture, not
the fixed industrial-board Mock. Start the keyed app on port 8000 first:
    .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
    .venv/Scripts/python.exe deck/capture_gallery.py
Override the target with GALLERY_URL if the server runs elsewhere.
"""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = os.environ.get("GALLERY_URL", "http://localhost:8000")
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
OUT = HERE / "gallery"
OUT.mkdir(parents=True, exist_ok=True)

# Two polished design assets bracket the real app screenshots: the cover opens
# the gallery (and becomes the Devpost thumbnail), the system diagram closes it.
DESIGN_ASSETS = [
    (ASSETS / "devpost_cover.png", OUT / "00-cover.png"),
    (ASSETS / "architecture_diagram.png", OUT / "09-system-architecture.png"),
]

# Devpost gallery captions, in display order. Keep each ~1 line.
CAPTIONS = [
    ("00-cover.png",              "AI Circuit Architect — six AI agents turn a plain-English hardware brief into a KiCad-verified project scaffold."),
    ("01-describe.png",           "1 · Describe your hardware in plain English — pick an example, an audience, and a review team."),
    ("02-agent-collaboration.png","2 · Six specialist agents collaborate live — the Critic demands rework and the Architect revises, in rounds."),
    ("03-architecture.png",       "3 · The agreed architecture as a live block diagram — hierarchical sheets, power domains and interfaces."),
    ("04-review-open-items.png",  "4 · Honest by design — open TODOs and explicit 'needs human review' items, not false confidence."),
    ("05-pcb-readiness.png",      "5 · A PCB-readiness pack — net classes with controlled impedance, board constraints and component candidates."),
    ("06-compare.png",            "6 · Measurably better than one model — the team surfaces more engineering concerns per run."),
    ("07-human-approval.png",     "7 · Human-in-the-loop — nothing is generated until the engineer approves."),
    ("08-kicad-scaffold.png",     "8 · The generated KiCad scaffold — opened and verified by kicad-cli, with a schematic preview and downloadable ZIP."),
    ("09-system-architecture.png","How it works — the full system: Web UI, orchestrator, the six-agent society, the API cost guard and KiCad generation."),
]

# bbox (CSS px, document coords) of the nearest `section.panel` ancestor of the
# first <h2>/<h3> whose text contains `needle`. Falls back to the element's own
# rect. Returns null if nothing matches.
PANEL_BBOX_JS = """
(needle) => {
  const head = [...document.querySelectorAll('h1,h2,h3')]
    .find(h => h.textContent.trim().toLowerCase().includes(needle.toLowerCase()));
  if (!head) return null;
  let el = head;
  while (el && !(el.tagName === 'SECTION' && el.classList.contains('panel'))) el = el.parentElement;
  el = el || head;
  const r = el.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return null;
  return {x: r.left + scrollX, y: r.top + scrollY, width: r.width, height: r.height};
}
"""

# union bbox of all elements matching a selector (+ descendants) — for content
# that lives in a display:contents wrapper (e.g. the society chat bubbles).
UNION_BBOX_JS = """
(sel) => {
  const roots = [...document.querySelectorAll(sel)];
  if (!roots.length) return null;
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9, any=false;
  const eat = (e) => { for (const r of e.getClientRects()) {
    if (r.width<1 || r.height<1) continue; any=true;
    x0=Math.min(x0,r.left); y0=Math.min(y0,r.top); x1=Math.max(x1,r.right); y1=Math.max(y1,r.bottom);
  }};
  for (const root of roots){ eat(root); root.querySelectorAll('*').forEach(eat); }
  if (!any) return null;
  return {x:x0+scrollX, y:y0+scrollY, width:x1-x0, height:y1-y0};
}
"""

def pad(bbox, p=16):
    return {"x": max(0, bbox["x"] - p), "y": max(0, bbox["y"] - p),
            "width": bbox["width"] + 2 * p, "height": bbox["height"] + 2 * p}

def shot(page, bbox_js, sel, path, p=16):
    box = page.evaluate(bbox_js, sel)
    if not box or box["width"] <= 1 or box["height"] <= 1:
        print(f"  !! no bbox for {sel!r} -> skip {path.name}")
        return False
    # full_page so the clip resolves in document coords even for sections that
    # sit below the viewport surface (approval, generated scaffold)
    page.screenshot(path=str(path), clip=pad(box, p), full_page=True, animations="disabled")
    print(f"  ok {path.name}  ({int(box['width'])}x{int(box['height'])} css)")
    return True

def panel(page, needle, path, p=16):
    return shot(page, PANEL_BBOX_JS, needle, path, p)

def union(page, sel, path, p=16):
    return shot(page, UNION_BBOX_JS, sel, path, p)

def main():
    saved = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # generous height so tall panels fit in one clip; 2x for crisp images
        page = browser.new_page(viewport={"width": 1320, "height": 3200}, device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.add_style_tag(content="*{animation:none!important;transition:none!important;}")

        # --- 01) landing shot: describe form (intro tour still visible) ---
        page.wait_for_timeout(400)
        saved["01_describe"] = panel(page, "Describe your hardware", OUT / "01-describe.png")

        # now hide the intro tour + mascot for the working shots
        page.evaluate("""() => {
          const tour=[...document.querySelectorAll('*')].find(e=>/THE 30-SECOND TOUR/.test(e.textContent)&&e.children.length<8);
          if(tour){ let c=tour; for(let i=0;i<5&&c;i++){ if(c.parentElement&&c.parentElement.children.length>1){c.style.display='none';break;} c=c.parentElement; } }
          document.querySelectorAll('[class*=intro], [alt*=mascot], img[alt*=mascot]').forEach(e=>e.style.display='none');
        }""")

        # configure: bat detector + Senior Review Team + auto mode
        page.locator("select").nth(0).select_option(label="Bat detector (Wi-Fi / USB)")
        page.locator("select").nth(1).select_option(label="Senior Review Team")
        cb = page.locator("input[type=checkbox]").first
        if not cb.is_checked():
            cb.check()

        page.get_by_role("button", name="Run agents").click()

        # wait for the live pipeline to finish: the Human-approval CTA only
        # renders once the `final` event has set `result`. Real Qwen runs take
        # a few minutes (6 agents, qwen-max, optional rework), so allow plenty.
        try:
            page.get_by_role("button", name="Approve architecture").wait_for(timeout=360000)
        except PWTimeout:
            print("  !! timed out waiting for pipeline completion; capturing current state")
        page.wait_for_timeout(2000)  # let final bubbles + diagram settle

        # Guard: a Qwen/guard/validation failure drops the run to Mock, whose
        # architecture is the FIXED industrial board (RS485) — not the bat
        # detector. Abort loudly rather than silently shipping an incoherent
        # gallery (the exact bug this recapture is fixing).
        if page.get_by_text("Mock mode · demo").count():
            raise SystemExit(
                "  !! run fell back to Mock mode (industrial board) — aborting.\n"
                "     Check QWEN_API_KEY / guard budget and re-run against the keyed server.")

        # 02) full agent-collaboration panel: metro rail + trace + rework
        saved["02_agent_collaboration"] = panel(page, "Agent collaboration", OUT / "02-agent-collaboration.png")

        # 03) proposed architecture (block diagram + key info)
        saved["03_architecture"] = panel(page, "Proposed architecture", OUT / "03-architecture.png")
        # 04) review & open items (TODOs + needs-human-review — the honesty view)
        saved["04_review"] = panel(page, "Review & open items", OUT / "04-review-open-items.png")
        # 05) PCB-readiness pack
        saved["05_pcb_readiness"] = panel(page, "PCB-Readiness pack", OUT / "05-pcb-readiness.png")

        # 06) compare panel: open Advanced, run the headline preset
        try:
            page.locator("summary", has_text="Advanced").click()
            page.wait_for_timeout(400)
            page.get_by_role("button", name="🏆 Architecture beats tier").click()
            # the compare result renders its own panel headed "Multi-agent vs single-agent".
            # This kicks off another real multi-agent run, so allow minutes, not seconds.
            page.get_by_text("Multi-agent vs single-agent", exact=False).first.wait_for(timeout=240000)
            page.wait_for_timeout(1200)
            saved["06_compare"] = panel(page, "Multi-agent vs single-agent", OUT / "06-compare.png")
        except Exception as e:
            print(f"  !! compare panel failed: {e!r}")
            saved["06_compare"] = False

        # 07) human approval panel (capture the CTA before clicking it)
        try:
            saved["07_human_approval"] = panel(page, "Human approval", OUT / "07-human-approval.png")
        except Exception as e:
            print(f"  !! approval panel failed: {e!r}")
            saved["07_human_approval"] = False

        # 08) generate the KiCad project, screenshot the whole scaffold panel
        #     (validation badge + checks + schematic preview)
        try:
            page.get_by_role("button", name="Approve architecture").click()
            page.wait_for_timeout(400)
            page.get_by_role("button", name="Generate KiCad project").click()
            # wait for the generated scaffold panel (kicad-cli render can take a bit)
            page.get_by_text("KiCad scaffold", exact=False).first.wait_for(timeout=120000)
            # give the schematic <img> time to load if a preview is produced
            try:
                page.locator(".preview img").first.wait_for(state="visible", timeout=60000)
            except PWTimeout:
                pass
            page.wait_for_timeout(2000)
            saved["08_kicad_scaffold"] = panel(page, "KiCad scaffold", OUT / "08-kicad-scaffold.png")
        except Exception as e:
            print(f"  !! generate/scaffold failed: {e!r}")
            saved["08_kicad_scaffold"] = False

        browser.close()

    # bracket the app screenshots with the two polished design assets
    for src, dst in DESIGN_ASSETS:
        if src.exists():
            shutil.copyfile(src, dst)
            saved[dst.stem] = True
            print(f"  ok {dst.name}  (copied from {src.name})")
        else:
            saved[dst.stem] = False
            print(f"  !! missing design asset {src.name}")

    # write the caption manifest juror-facing gallery order + captions
    lines = ["# Devpost — Project Media (image gallery)", "",
             "Upload in this order. The first image is used as the gallery thumbnail.",
             "Captions are suggestions — paste into the Devpost caption field.", ""]
    for fname, cap in CAPTIONS:
        exists = (OUT / fname).exists()
        mark = "" if exists else "  ⚠️ MISSING"
        lines.append(f"- **{fname}** — {cap}{mark}")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ok README.md  ({len(CAPTIONS)} captions)")

    print(json.dumps(saved, indent=2))

if __name__ == "__main__":
    main()
