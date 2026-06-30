"""Capture clean PNG assets for the jury pitch deck from the running app.

Drives the bat-detector example through the Senior Review Team profile (so the
Critic->Architect rework round renders) and saves tightly-clipped screenshots
of the metro rail, the Agent-Society rework exchange, the compare panel and the
generated schematic preview into deck/assets/.

Run with the app serving on http://localhost:8011 (mock mode):
    .venv/Scripts/python.exe deck/capture_assets.py
"""
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "http://localhost:8011"
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

# union bounding box (CSS px, document coords) of all elements matching a
# selector. Unions the rects of each match AND its descendants, so it works even
# when the matched element is display:contents (zero box, children render).
BBOX_JS = """
(sel) => {
  const roots = [...document.querySelectorAll(sel)];
  if (!roots.length) return null;
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9, any=false;
  const eat = (e) => {
    for (const r of e.getClientRects()) {
      if (r.width<1 || r.height<1) continue;
      any=true;
      x0=Math.min(x0,r.left); y0=Math.min(y0,r.top);
      x1=Math.max(x1,r.right); y1=Math.max(y1,r.bottom);
    }
  };
  for (const root of roots) { eat(root); root.querySelectorAll('*').forEach(eat); }
  if (!any) return null;
  return {x:x0+scrollX, y:y0+scrollY, width:x1-x0, height:y1-y0};
}
"""

def pad(bbox, p=14):
    return {"x": max(0, bbox["x"]-p), "y": max(0, bbox["y"]-p),
            "width": bbox["width"]+2*p, "height": bbox["height"]+2*p}

def clip_shot(page, sel, path, p=14):
    box = page.evaluate(BBOX_JS, sel)
    if not box or box["width"] <= 1 or box["height"] <= 1:
        print(f"  !! no bbox for {sel!r} -> skip {path.name}")
        return False
    page.screenshot(path=str(path), clip=pad(box, p), animations="disabled")
    print(f"  ok {path.name}  ({int(box['width'])}x{int(box['height'])})")
    return True

def main():
    saved = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 2800}, device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.add_style_tag(content="*{animation:none!important;transition:none!important;}")

        # hide the intro tour + mascot if showing (force-remove the whole card)
        page.evaluate("""() => {
          const tour=[...document.querySelectorAll('*')].find(e=>/THE 30-SECOND TOUR/.test(e.textContent)&&e.children.length<8);
          if(tour){ let c=tour; for(let i=0;i<5&&c;i++){ if(c.parentElement&&c.parentElement.children.length>1){c.style.display='none';break;} c=c.parentElement; } }
          document.querySelectorAll('[class*=intro], [alt*=mascot], img[alt*=mascot]').forEach(e=>e.style.display='none');
        }""")

        # configure run: bat detector + Senior Review Team + auto mode
        page.locator("select").nth(0).select_option(label="Bat detector (Wi-Fi / USB)")
        page.locator("select").nth(1).select_option(label="Senior Review Team")
        cb = page.locator("input[type=checkbox]").first
        if not cb.is_checked():
            cb.check()

        page.get_by_role("button", name="Run agents").click()

        # wait for the replay to finish (last PCB-rework line appears)
        try:
            page.get_by_text("increased to 0.4", exact=False).first.wait_for(timeout=90000)
        except PWTimeout:
            print("  !! timed out waiting for pipeline completion; capturing current state")
        page.wait_for_timeout(1500)  # let the final bubbles settle

        # 1) metro rail
        saved["metro_rail"] = clip_shot(page, ".rail-live", OUT / "metro_rail.png", p=10)

        # 2) Agent-Society rework exchange (society-chat is display:contents -> clip bubbles)
        page.get_by_role("button", name="Agent Society").click()
        page.wait_for_timeout(800)
        saved["society_rework"] = clip_shot(
            page, ".society-chat .bubble-left, .society-chat .bubble-right",
            OUT / "society_rework.png", p=16)

        # 3) compare panel: open Advanced, run the headline preset
        try:
            page.locator("summary", has_text="Advanced").click()
            page.wait_for_timeout(400)
            page.get_by_role("button", name="🏆 Architecture beats tier").click()
            page.get_by_text("Quality", exact=False).first.wait_for(timeout=60000)
            page.wait_for_timeout(1500)
            # the result table/panel — clip the nearest container holding the comparison
            saved["compare_panel"] = clip_shot(
                page, "table, [class*=compare-], [class*=cmp], [class*=result]",
                OUT / "compare_panel.png", p=14)
        except Exception as e:
            print(f"  !! compare panel failed: {e!r}")
            saved["compare_panel"] = False

        # 4) generate the KiCad project, screenshot the schematic preview
        try:
            page.get_by_role("button", name="Approve architecture").click()
            page.wait_for_timeout(400)
            page.get_by_role("button", name="Generate KiCad project").click()
            # schematic preview renders as an <img>/<svg>/<object>
            page.locator("img[src*='preview'], object[data*='preview'], svg.schematic, [class*=preview] svg, [class*=preview] img").first.wait_for(timeout=120000)
            page.wait_for_timeout(2000)
            saved["schematic"] = clip_shot(
                page, "[class*=preview] img, [class*=preview] svg, [class*=preview] object",
                OUT / "schematic.png", p=10)
        except Exception as e:
            print(f"  !! generate/schematic failed: {e!r}")
            saved["schematic"] = False

        browser.close()
    print(json.dumps(saved))

if __name__ == "__main__":
    main()
