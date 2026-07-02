"""Render the Devpost cover + square thumbnail from deck/cover.html to PNG.

Crisp 2x export via Playwright element screenshots. Output -> deck/assets/.

    .venv/Scripts/python.exe deck/render_cover.py
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = (HERE / "cover.html").as_uri()
OUT = HERE / "assets"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "#cover": "devpost_cover.png",     # 1280x720 (16:9 gallery / thumbnail)
    "#square": "devpost_thumb.png",    # 1000x1000 (square tile / social)
}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(400)  # let the logo + fonts settle
        for sel, name in TARGETS.items():
            page.locator(sel).screenshot(path=str(OUT / name))
            box = page.locator(sel).bounding_box()
            print(f"  ok {name}  ({int(box['width'])}x{int(box['height'])} @2x)")
        browser.close()


if __name__ == "__main__":
    main()
