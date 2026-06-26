# tools/compare_report.py
"""Generate a Markdown report of the multi- vs single-agent comparison.

Run in Qwen mode for the real numbers used in the repo/slide deck:
    .venv/Scripts/python.exe tools/compare_report.py "A 24V STM32 board with RS485" docs/comparison-report.md
In Mock Mode it produces an illustrative report (clearly labelled).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the script runnable directly (e.g. `python tools/compare_report.py ...`)
# by putting the project root on the import path before importing the app.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.comparison import run_comparison  # noqa: E402
from app.services.config import Settings  # noqa: E402


def _to_markdown(cmp) -> str:
    lines = [
        "# Multi-agent vs single-agent comparison",
        "",
        f"**Request:** {cmp.requirements_text}",
        "",
        f"**Mode:** {cmp.mode}",
    ]
    if cmp.notice:
        lines += ["", f"> {cmp.notice}"]
    lines += [
        "",
        f"**Multi-agent @ {cmp.multi_model}: {cmp.multi_score}/{cmp.total} concerns surfaced "
        f"({cmp.multi_calls} agent call{'s' if cmp.multi_calls != 1 else ''}; "
        f"{cmp.multi_findings} findings, {cmp.multi_honesty} honesty markers).**",
        f"**Single-agent @ {cmp.single_model}: {cmp.single_score}/{cmp.total} concerns surfaced "
        f"({cmp.single_calls} call{'s' if cmp.single_calls != 1 else ''}; "
        f"{cmp.single_findings} findings, {cmp.single_honesty} honesty markers).**",
        f"**Difference: {'+' if cmp.delta >= 0 else ''}{cmp.delta} concerns "
        f"({'multi-agent ahead' if cmp.delta > 0 else 'tie' if cmp.delta == 0 else 'single-agent ahead'}).**",
        "",
        "_Coverage = the concern was surfaced as engineering work (block / TODO /"
        " assumption / review item), not a placed component._",
        "",
        "| Engineering concern | Multi-agent | Single-agent |",
        "| --- | :---: | :---: |",
    ]
    for c in cmp.concerns:
        lines.append(f"| {c.label} | {'✅' if c.covered_multi else '—'} | {'✅' if c.covered_single else '—'} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else (
        "A 24V industrial sensor board with an STM32, USB-C for configuration, "
        "an RS485 fieldbus interface and status LEDs."
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("comparison-report.md")

    cmp = run_comparison(text, Settings())
    out_path.write_text(_to_markdown(cmp), encoding="utf-8")
    print(f"multi {cmp.multi_score}/{cmp.total} vs single {cmp.single_score}/{cmp.total} "
          f"(+{cmp.delta}); mode={cmp.mode}")
    print(f"report written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
