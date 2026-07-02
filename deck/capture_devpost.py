"""Capture crisp, tightly-clipped product screenshots for the Devpost gallery.

Drives the bat-detector example through the Senior Review Team profile (auto
mode) so the Critic->Architect rework renders, then clips: the live metro rail,
the proposed-architecture block diagram, the Agent-Society rework exchange and
the multi-vs-single comparison table. Output -> deck/assets/.

Needs the mock app on http://localhost:8011:
    .venv/Scripts/python.exe deck/capture_devpost.py
"""
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "http://localhost:8011"
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

# union bounding box (document coords) of a selector's matches + descendants
BBOX_JS = """
(sel) => {
  const roots=[...document.querySelectorAll(sel)];
  if(!roots.length) return null;
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,any=false;
  const eat=(e)=>{ for(const r of e.getClientRects()){ if(r.width<1||r.height<1) continue;
    any=true; x0=Math.min(x0,r.left);y0=Math.min(y0,r.top);x1=Math.max(x1,r.right);y1=Math.max(y1,r.bottom);} };
  for(const root of roots){ eat(root); root.querySelectorAll('*').forEach(eat); }
  if(!any) return null;
  return {x:x0+scrollX,y:y0+scrollY,width:x1-x0,height:y1-y0};
}
"""

def pad(b,p=16,pb=None):
    pb = p if pb is None else pb
    return {"x":max(0,b["x"]-p),"y":max(0,b["y"]-p),"width":b["width"]+2*p,"height":b["height"]+p+pb}

def clip(page, sel, name, p=16, pb=None):
    box = page.evaluate(BBOX_JS, sel)
    if not box or box["width"]<=1 or box["height"]<=1:
        print(f"  !! no bbox for {sel!r} -> skip {name}"); return False
    page.screenshot(path=str(OUT/name), clip=pad(box,p,pb), animations="disabled")
    print(f"  ok {name}  ({int(box['width'])}x{int(box['height'])})"); return True

def main():
    saved={}
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":1600,"height":2400}, device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.add_style_tag(content="*{animation:none!important;transition:none!important;}")

        # hide intro tour + mascot
        page.evaluate("""() => {
          const t=[...document.querySelectorAll('*')].find(e=>/30-SECOND TOUR/i.test(e.textContent)&&e.children.length<8);
          if(t){ let c=t; for(let i=0;i<5&&c;i++){ if(c.parentElement&&c.parentElement.children.length>1){c.style.display='none';break;} c=c.parentElement; } }
          document.querySelectorAll('[class*=intro],[alt*=mascot],img[alt*=mascot]').forEach(e=>e.style.display='none');
        }""")

        # configure + run
        page.locator("select").nth(0).select_option(label="Bat detector (Wi-Fi / USB)")
        page.locator("select").nth(1).select_option(label="Senior Review Team")
        cb=page.locator("input[type=checkbox]").first
        if not cb.is_checked(): cb.check()
        page.get_by_role("button", name="Run agents").click()

        # wait for the replay to finish: the "Approve architecture" button only
        # appears once the auto run has fully played out.
        try:
            page.get_by_role("button", name="Approve architecture").wait_for(timeout=150000)
        except PWTimeout:
            try:
                page.get_by_text("PCB-Readiness pack", exact=False).first.wait_for(timeout=15000)
            except PWTimeout:
                print("  !! timed out; capturing current state")
        page.wait_for_timeout(2000)

        # tag the section-3 architecture diagram so we clip only that one
        page.evaluate("""() => {
          const h=[...document.querySelectorAll('h1,h2,h3')].find(e=>/Proposed architecture/i.test(e.textContent));
          if(h){ let s=h.closest('section,div'); const svg=s&&s.querySelector('svg'); if(svg) svg.id='__cap_diagram'; }
          const tbl=[...document.querySelectorAll('table')].find(t=>/Engineering concern/i.test(t.textContent));
          if(tbl) tbl.id='__cap_compare';
        }""")

        saved["metro_rail"]=clip(page, ".rail", "metro_rail.png", p=12)
        saved["architecture"]=clip(page, "#__cap_diagram", "architecture.png", p=18, pb=64)
        saved["society_rework"]=clip(page, ".society-chat .bubble-left,.society-chat .bubble-right", "society_rework.png", p=16)

        # comparison table (open Advanced + run the headline preset)
        try:
            page.evaluate("""() => { const d=[...document.querySelectorAll('details')].find(d=>/Advanced/.test(d.textContent)); if(d)d.open=true; }""")
            page.wait_for_timeout(300)
            page.get_by_role("button", name="Architecture beats tier").click()
            page.wait_for_function(
                "() => { const t=[...document.querySelectorAll('table')].find(t=>/Engineering concern/i.test(t.textContent)); return t && t.offsetHeight>0; }",
                timeout=60000)
            page.wait_for_timeout(1500)
            page.evaluate("""() => { const t=[...document.querySelectorAll('table')].find(t=>/Engineering concern/i.test(t.textContent)); if(t) t.id='__cap_compare'; }""")
            saved["compare"]=clip(page, "#__cap_compare", "compare_panel.png", p=18)
        except Exception as e:
            print(f"  !! compare failed: {e!r}"); saved["compare"]=False

        browser.close()
    print(json.dumps(saved))

if __name__ == "__main__":
    main()
