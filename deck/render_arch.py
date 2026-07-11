"""Render the system architecture diagram from deck/architecture.html to PNG.

Crisp 2x export via Playwright element screenshot. Output -> deck/assets/.

    .venv/Scripts/python.exe deck/render_arch.py
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = (HERE / "architecture.html").as_uri()
OUT = HERE / "assets"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(400)  # let the logo + fonts settle
        loc = page.locator("#arch")
        loc.screenshot(path=str(OUT / "architecture_diagram.png"))
        box = loc.bounding_box()
        print(f"  ok architecture_diagram.png  ({int(box['width'])}x{int(box['height'])} @2x)")
        browser.close()


if __name__ == "__main__":
    main()
