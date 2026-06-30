"""Build the AI Circuit Architect jury pitch deck (Track 3 — Agent Society).

Run:  .venv/Scripts/python.exe -m deck.build_deck
Out:  deck/AI_Circuit_Architect.pptx
"""
from __future__ import annotations
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import deck.theme as T

ASSETS = T.ASSETS


def _blank(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    T.fill_background(s)
    return s


# --------------------------------------------------------------------------- 1
def slide_title(prs):
    s = _blank(prs)
    # logo framed in a white app-tile (motif), centred
    tile = T.panel(s, Inches(5.47), Inches(1.15), Inches(2.4), Inches(2.4),
                   fill=T.RGBColor(0xFF, 0xFF, 0xFF), line=None, radius=0.18)
    tile.shadow.inherit = False
    s.shapes.add_picture(f"{ASSETS}/logo.png", Inches(5.72), Inches(1.55),
                         width=Inches(1.9))
    T.add_text(s, Inches(1.0), Inches(3.95), Inches(11.33), Inches(1.0),
               "AI Circuit Architect", size=52, bold=True, color=T.TEXT,
               align=PP_ALIGN.CENTER, font=T.FONT_H)
    T.add_text(s, Inches(1.0), Inches(5.05), Inches(11.33), Inches(0.6),
               "From idea to PCB-ready schematic — a society of agents",
               size=21, color=T.MUTED, align=PP_ALIGN.CENTER)
    # track pill
    pill = T.panel(s, Inches(4.62), Inches(5.95), Inches(4.1), Inches(0.55),
                   fill=T.PANEL2, line=T.LINE, radius=0.5)
    T.add_text(s, Inches(4.62), Inches(5.95), Inches(4.1), Inches(0.55),
               "Qwen Hackathon  ·  Track: Agent Society", size=14,
               color=T.ACCENT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
               bold=True)
    return s


# --------------------------------------------------------------------------- 3
def slide_number(prs):
    s = _blank(prs)
    T.title(s, "Two heads beat one — and we measured it")

    # left: the big number + bars
    T.add_text(s, Inches(0.7), Inches(1.7), Inches(6.0), Inches(1.6),
               [("+3.2", {"size": 96, "bold": True, "color": T.ACCENT})],
               font=T.FONT_H)
    T.add_text(s, Inches(0.78), Inches(3.25), Inches(5.9), Inches(0.7),
               "more design concerns surfaced than a single LLM — on average, "
               "across 5 diverse hard designs (live Qwen).",
               size=15, color=T.MUTED, line_spacing=1.1)

    bar_x, bar_w_full = Inches(0.8), 5.4   # inches; full = 12/12
    def bar(y, frac, color, label, val):
        T.hbar(s, bar_x, y, Inches(bar_w_full), Inches(0.5), T.PANEL2)  # track
        T.hbar(s, bar_x, y, Inches(bar_w_full * frac), Inches(0.5), color)
        T.add_text(s, bar_x, y - Inches(0.34), Inches(5.4), Inches(0.3),
                   label, size=13, color=T.TEXT, bold=True)
        T.add_text(s, bar_x + Inches(bar_w_full * frac + 0.1), y + Inches(0.02),
                   Inches(1.4), Inches(0.4), val, size=14, color=color, bold=True,
                   anchor=MSO_ANCHOR.MIDDLE)
    bar(Inches(4.45), 11.6 / 12, T.ACCENT, "Multi-agent team", "11.6 / 12")
    bar(Inches(5.55), 8.4 / 12, T.MUTED, "Single agent", "8.4 / 12")
    T.add_text(s, Inches(0.8), Inches(6.35), Inches(6.0), Inches(0.5),
               "Coverage = engineering concern surfaced as work, scored by a "
               "deterministic 12-point rubric.", size=11, color=T.MUTED,
               italic=True, line_spacing=1.05)

    # right: per-design table
    px, py, pw = Inches(7.2), Inches(1.7), Inches(5.45)
    T.panel(s, px, py, pw, Inches(4.75), fill=T.PANEL, line=T.LINE)
    T.add_text(s, px + Inches(0.35), py + Inches(0.28), pw - Inches(0.7),
               Inches(0.4), "Per design  ·  coverage delta (multi − single)",
               size=14, color=T.TEXT, bold=True)
    rows = [("Motor + safety", "+2", T.MUTED),
            ("Precision analog", "+2", T.MUTED),
            ("Battery IoT", "+4", T.ACCENT),
            ("Medical wearable", "+5", T.ACCENT),
            ("Industrial gateway", "+3", T.TEXT)]
    ry = py + Inches(0.95)
    for name, delta, col in rows:
        T.add_text(s, px + Inches(0.4), ry, Inches(3.6), Inches(0.5), name,
                   size=15, color=T.TEXT, anchor=MSO_ANCHOR.MIDDLE)
        T.badge(s, px + pw - Inches(1.15), ry + Inches(0.02), Inches(0.46),
                col if col != T.TEXT else T.PANEL2, delta,
                txt_color=T.BG if col is T.ACCENT else T.TEXT, size=13)
        ry += Inches(0.7)
    T.add_text(s, px + Inches(0.4), ry + Inches(0.05), pw - Inches(0.8),
               Inches(0.5),
               [("↑  the gap widens with complexity", {"color": T.ACCENT,
                 "bold": True, "size": 14})])
    T.footer(s, 3)
    return s


# --------------------------------------------------------------------------- 5
def slide_conflict(prs):
    s = _blank(prs)
    T.title(s, "When agents disagree, the design gets better")

    # left: society-chat rework screenshot (crop off the diagram at the bottom)
    img_w = Inches(5.45)
    img_h = Inches(5.45 * (1559 * 0.60) / 1002)   # keep top 60% of the capture
    T.add_picture_panel(s, f"{ASSETS}/society_rework.png", Inches(0.7),
                        Inches(1.65), img_w, img_h,
                        crop=(0.0, 0.0, 0.0, 0.40), pad=0.07)

    # right: the negotiation narrative
    nx, nw = Inches(6.95), Inches(5.7)
    T.add_text(s, nx, Inches(1.6), nw, Inches(0.7),
               "Our system is not a pipeline. The Critic challenges the "
               "Architect, who reworks — live, in rounds.", size=16,
               color=T.MUTED, line_spacing=1.15)
    steps = [
        ("1", T.REVIEW, "Round 1 — Design Critic",
         "Flags a gap: the Architect's 5 blocks miss a Debug / SWD + status-LED block."),
        ("2", T.WARN, "↺ Rework — System Architect",
         "Reacts to the critique and revises: adds the Debug block → 6 blocks."),
        ("3", T.OK, "Round 2 — Design Critic",
         "Re-reviews the revision: no missing blocks remain. Conflict resolved."),
    ]
    sy = Inches(2.6)
    for num, col, head, body in steps:
        T.badge(s, nx, sy, Inches(0.5), col, num, txt_color=T.BG, size=16)
        T.add_text(s, nx + Inches(0.72), sy - Inches(0.04), nw - Inches(0.72),
                   Inches(0.4), head, size=15, bold=True, color=col)
        T.add_text(s, nx + Inches(0.72), sy + Inches(0.34), nw - Inches(0.72),
                   Inches(0.7), body, size=13.5, color=T.TEXT, line_spacing=1.1)
        sy += Inches(1.25)
    T.add_text(s, nx, sy + Inches(0.05), nw, Inches(0.6),
               [("This negotiation loop — not a single pass — is what raises "
                 "coverage.", {"italic": True, "color": T.ACCENT, "size": 14})],
               line_spacing=1.1)
    T.footer(s, 5)
    return s


SAMPLE = [slide_title, slide_number, slide_conflict]


def build(slides=SAMPLE, path="deck/AI_Circuit_Architect.pptx"):
    prs = Presentation()
    prs.slide_width = T.SLIDE_W
    prs.slide_height = T.SLIDE_H
    for fn in slides:
        fn(prs)
    prs.save(path)
    print(f"saved {path}  ({len(slides)} slides)")


if __name__ == "__main__":
    build()
