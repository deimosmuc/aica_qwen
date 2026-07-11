"""Record a 1080p screen-capture walkthrough of the REAL app for the 3-minute
Devpost demo video (picture track only — English TTS narration is laid on top
in the edit, per deck/video_runbook.md).

It drives the same verified flow as capture_gallery.py against the KEYED server
(real Qwen agents). The bat-detector run is already cached, so it replays fast,
deterministically and with the Critic->Architect rework visible — exactly the
"cache trick" from the runbook, but produced hands-free as a clean clip.

Outputs (deck/video/):
  walkthrough.webm        raw Playwright capture (1920x1080)
  walkthrough.mp4         H.264 convert (if the bundled ffmpeg can; else use webm)
  frames/NN-*.png         one sanity frame per beat, for review
  CUE_SHEET.md            beat -> script segment (S1..S8) -> real timestamp

Run (keyed app on :8000 must be up):
    .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
    .venv/Scripts/python.exe deck/capture_video.py
Override the target with GALLERY_URL.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from time import perf_counter

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = os.environ.get("GALLERY_URL", "http://localhost:8000")
HERE = Path(__file__).resolve().parent
OUT = HERE / "video"
FRAMES = OUT / "frames"
OUT.mkdir(parents=True, exist_ok=True)
FRAMES.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
FFMPEG = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" / "ffmpeg-1011" / "ffmpeg-win64.exe"

# Pacing (seconds). Generous and static-friendly — final sync happens in the
# edit against the TTS. Bump a beat here if its narration segment runs long.
HOLD = {
    "hook": 7.0, "number": 9.0, "setup": 2.0, "collab": 13.0,
    "diagram": 6.0, "review": 6.0, "pcb": 12.0, "output": 11.0,
    "compare": 10.0, "close": 9.0,
}
# produce_video.py writes per-beat holds sized to the TTS segment lengths so the
# picture matches the narration; pick them up here when present.
import json as _json  # noqa: E402
_holds_file = os.environ.get("VIDEO_HOLDS_JSON")
if _holds_file and Path(_holds_file).exists():
    HOLD.update({k: float(v) for k, v in _json.loads(Path(_holds_file).read_text()).items()})

# A visible fake cursor + click ripple (Playwright video renders no OS cursor).
CURSOR_JS = r"""
() => {
  if (document.getElementById('__vcursor')) return;
  const c = document.createElement('div');
  c.id = '__vcursor';
  Object.assign(c.style, {position:'fixed', left:'40px', top:'40px', width:'24px', height:'24px',
    zIndex:2147483647, pointerEvents:'none', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.55))'});
  c.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none">' +
    '<path d="M4 2 L4 20 L9 15 L12.5 22 L15.5 20.7 L12 14 L19 14 Z" fill="#ffffff" stroke="#0b0b0b" stroke-width="1.3" stroke-linejoin="round"/></svg>';
  document.documentElement.appendChild(c);
  window.__vmove = (x,y) => { c.style.left = x+'px'; c.style.top = y+'px'; };
  document.addEventListener('mousemove', e => window.__vmove(e.clientX, e.clientY), true);
  window.__vclick = (x,y) => {
    const r = document.createElement('div');
    Object.assign(r.style, {position:'fixed', left:(x-15)+'px', top:(y-15)+'px', width:'30px', height:'30px',
      border:'2px solid #4aa3ff', borderRadius:'50%', zIndex:2147483646, pointerEvents:'none', opacity:'0.9',
      transition:'transform .45s ease-out, opacity .45s ease-out'});
    document.documentElement.appendChild(r);
    requestAnimationFrame(()=>{ r.style.transform='scale(2.1)'; r.style.opacity='0'; });
    setTimeout(()=>r.remove(), 480);
  };
}
"""

cues: list[tuple[str, str, float]] = []
_t0 = 0.0


def mark(beat: str, segment: str):
    cues.append((beat, segment, perf_counter() - _t0))


def hold(page, key: str):
    page.wait_for_timeout(int(HOLD[key] * 1000))


def frame(page, name: str):
    page.screenshot(path=str(FRAMES / f"{name}.png"))


def move(page, x: float, y: float, steps: int = 26):
    page.mouse.move(x, y, steps=steps)


def _center(page, selector: str):
    loc = page.locator(selector).first
    box = loc.bounding_box()
    return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2) if box else None


def glide_click(page, selector: str, pre: float = 0.35):
    pos = _center(page, selector)
    if pos:
        move(page, *pos)
        page.evaluate("([x,y]) => window.__vclick && window.__vclick(x,y)", [pos[0], pos[1]])
    page.wait_for_timeout(int(pre * 1000))
    page.locator(selector).first.click()


def glide_to(page, selector: str):
    pos = _center(page, selector)
    if pos:
        move(page, *pos)


def sscroll_text(page, needle: str, block: str = "center", settle: float = 1.3):
    page.evaluate(
        """([needle, block]) => {
          const h = [...document.querySelectorAll('h1,h2,h3')]
            .find(e => e.textContent.trim().toLowerCase().includes(needle.toLowerCase()));
          if (!h) return false;
          let el = h;
          while (el && !(el.tagName === 'SECTION' && el.classList.contains('panel'))) el = el.parentElement;
          (el || h).scrollIntoView({behavior:'smooth', block:block});
          return true;
        }""",
        [needle, block],
    )
    page.wait_for_timeout(int(settle * 1000))


def sscroll_sel(page, selector: str, block: str = "center", settle: float = 1.2):
    page.locator(selector).first.evaluate(
        "(el, b) => el.scrollIntoView({behavior:'smooth', block:b})", block)
    page.wait_for_timeout(int(settle * 1000))


def main():
    global _t0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(OUT),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        _t0 = perf_counter()
        page.goto(URL, wait_until="networkidle")
        page.evaluate(CURSOR_JS)
        # keep the intro tour visible (the '+3.2' hero line lives inside it)
        page.evaluate(
            """() => { try {
              const el = document.querySelector('[x-data]');
              const d = window.Alpine && window.Alpine.$data ? window.Alpine.$data(el) : null;
              if (d && 'showIntro' in d) d.showIntro = true;
            } catch(e){} }""")
        page.wait_for_timeout(600)

        # --- S1 · Hook: landing page, cursor idle ---
        mark("hook", "S1")
        move(page, W * 0.42, H * 0.5)
        frame(page, "00-hook")
        hold(page, "hook")

        # --- S2 · The number: scroll to the +3.2 hero line ---
        mark("number", "S2")
        if page.locator(".intro-stat").count():
            sscroll_sel(page, ".intro-stat", block="center")
            pos = _center(page, ".intro-stat")
            if pos:
                move(page, pos[0], pos[1])
        frame(page, "01-number")
        hold(page, "number")

        # --- S3 · Setup: load the bat example, Senior Review Team, Run ---
        mark("setup", "S3")
        sscroll_text(page, "Describe your hardware", block="start")
        glide_to(page, "select")
        page.locator("select").nth(0).select_option(label="Bat detector (Wi-Fi / USB)")
        page.wait_for_timeout(700)
        glide_to(page, "select >> nth=1")
        page.locator("select").nth(1).select_option(label="Senior Review Team")
        page.wait_for_timeout(500)
        cb = page.locator(".auto-toggle input[type=checkbox]").first
        if cb.count() and not cb.is_checked():
            cb.check()
        hold(page, "setup")
        glide_click(page, "button.primary")  # Run agents
        frame(page, "02-setup")

        # --- S4 · live collaboration, continuous ride: with the warm cache the
        #     responses stream in right away, so there is NO time-jump cut —
        #     bubbles + the Critic->Architect rework appear during the narration ---
        page.wait_for_timeout(300)
        try:
            sscroll_sel(page, ".rail", block="start", settle=0.5)
        except Exception:
            pass
        mark("collab", "S4")
        hold(page, "collab")
        frame(page, "03-collab-bubbles")

        # ensure the run has actually completed before touching the result panels
        try:
            page.get_by_role("button", name="Approve architecture").wait_for(timeout=360000)
        except PWTimeout:
            print("  !! timed out waiting for pipeline completion; continuing")
        if page.get_by_text("Mock mode · demo").count():
            raise SystemExit(
                "  !! run fell back to Mock mode (industrial board) — aborting.\n"
                "     Check QWEN_API_KEY / guard budget / cache and re-run against the keyed server.")
        # the result view keeps the Agent Society tab selected after `final`;
        # click defensively in case the default (Trace) won
        society = page.locator("button", has_text="Agent Society").first
        if society.count():
            try:
                society.click()
            except Exception:
                pass
        page.wait_for_timeout(600)

        # --- S5 · The result: block diagram, review, PCB-readiness pack ---
        mark("result", "S5")
        sscroll_text(page, "Proposed architecture", block="center")
        hold(page, "diagram")
        frame(page, "06-diagram")
        sscroll_text(page, "Review & open items", block="center")
        hold(page, "review")
        frame(page, "07-review")
        sscroll_text(page, "PCB-Readiness pack", block="start")
        hold(page, "pcb")
        frame(page, "08-pcb")

        # --- S6 · Real output: approve -> generate -> verified KiCad scaffold ---
        mark("output", "S6")
        sscroll_text(page, "Human approval", block="center")
        page.wait_for_timeout(600)
        glide_click(page, "button:has-text('Approve architecture')")
        page.wait_for_timeout(600)
        glide_click(page, "button:has-text('Generate KiCad project')")
        try:
            page.get_by_text("KiCad scaffold", exact=False).first.wait_for(timeout=120000)
            try:
                page.locator(".preview img").first.wait_for(state="visible", timeout=60000)
            except PWTimeout:
                pass
        except PWTimeout:
            print("  !! generate/scaffold timed out; continuing")
        sscroll_text(page, "KiCad scaffold", block="start")
        page.wait_for_timeout(800)
        frame(page, "09-kicad")
        hold(page, "output")

        # --- S7 · Proof: Advanced -> Architecture beats tier -> compare table ---
        mark("compare", "S7")
        sscroll_text(page, "Describe your hardware", block="start")
        try:
            page.locator("summary", has_text="Advanced").first.click()
            page.wait_for_timeout(500)
            # Fair, same-model comparison (isolates the multi-agent contribution;
            # single-agent scores a believable ~6/12, not the tier-framing's 0).
            glide_click(page, "button:has-text('Compare: fair')")
            page.get_by_text("Multi-agent vs single-agent", exact=False).first.wait_for(timeout=240000)
            page.wait_for_timeout(800)
            sscroll_text(page, "Multi-agent vs single-agent", block="center")
        except Exception as e:
            print(f"  !! compare beat failed: {e!r}")
        frame(page, "10-compare")
        hold(page, "compare")

        # --- S8 · Close: settle on the footer / powered-by line ---
        mark("close", "S8")
        sscroll_sel(page, "footer", block="center")
        pos = _center(page, "footer")
        if pos:
            move(page, pos[0], pos[1])
        frame(page, "11-close")
        hold(page, "close")

        # finalize the video
        video = page.video
        ctx.close()
        browser.close()
        webm = Path(video.path()) if video else None

    # rename to a stable name + write the cue sheet
    final_webm = OUT / "walkthrough.webm"
    if webm and webm.exists():
        if final_webm.exists():
            final_webm.unlink()
        webm.rename(final_webm)
    total = cues[-1][2] + HOLD["close"] if cues else 0

    lines = [
        "# Demo video — cue sheet (picture track)", "",
        f"Source clip: `walkthrough.webm` (1920x1080). Approx length **{total:0.0f}s**.",
        "Timestamps are where each beat *starts* in the raw clip (±1 s). Lay TTS "
        "segment S1–S8 from `video_teleprompter.md` at these marks. One continuous "
        "ride — no time-jump cut (the cached run streams in immediately).",
        "", "| Clip time | Beat | Narration |", "|-----------|------|-----------|",
    ]
    seg_name = {
        "S1": "S1 · Hook", "S2": "S2 · The number", "S3": "S3 · Setup",
        "S4": "S4 · Live collaboration",
        "S5": "S5 · The result", "S6": "S6 · Real output", "S7": "S7 · Proof",
        "S8": "S8 · Close",
    }
    for beat, seg, t in cues:
        mm, ss = divmod(int(t), 60)
        lines.append(f"| {mm}:{ss:02d} | {beat} | {seg_name.get(seg, seg)} |")
    (OUT / "CUE_SHEET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # machine-readable beat offsets for the audio muxer (produce_video.py)
    (OUT / "cues.json").write_text(
        _json.dumps([{"beat": b, "segment": s, "t": round(t, 3)} for b, s, t in cues], indent=2),
        encoding="utf-8")

    # best-effort H.264 mp4 (Playwright's ffmpeg may lack libx264 -> keep webm)
    mp4 = OUT / "walkthrough.mp4"
    converted = False
    if final_webm.exists() and FFMPEG.exists():
        for vcodec in ("libx264", "mpeg4"):
            try:
                r = subprocess.run(
                    [str(FFMPEG), "-y", "-i", str(final_webm), "-c:v", vcodec,
                     "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
                    capture_output=True, text=True, timeout=600)
                if r.returncode == 0 and mp4.exists() and mp4.stat().st_size > 0:
                    converted = True
                    print(f"  ok walkthrough.mp4  ({vcodec})")
                    break
            except Exception as e:
                print(f"  !! mp4 convert ({vcodec}) failed: {e!r}")

    print(f"  ok walkthrough.webm  ({final_webm.stat().st_size // 1024} KB)"
          if final_webm.exists() else "  !! no webm produced")
    if not converted:
        print("  ~~ mp4 not produced — use the .webm (Windows Clipchamp imports it)")
    print(f"  ok CUE_SHEET.md  ({len(cues)} beats, ~{total:0.0f}s)")


if __name__ == "__main__":
    main()
