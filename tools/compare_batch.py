"""Batch comparison over several harder, diverse designs to get n>1 real data.

Run live (needs QWEN_API_KEY in .env):
    PYTHONPATH=. python tools/compare_batch.py
Prints per-prompt scores and an aggregate of which concerns multi-agent caught
that the single-agent baseline missed (the pattern for the pitch narrative).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.comparison import run_comparison  # noqa: E402
from app.services.config import Settings  # noqa: E402

PROMPTS = [
    ("Motor+safety",
     "A 48V BLDC motor controller with field-oriented control, an STM32G4, "
     "CAN-FD, functional-safety (SIL2) requirements, over-temperature and "
     "over-current shutdown, and an isolated debug interface."),
    ("Precision analog",
     "A 24-bit precision data-acquisition board: 8 differential analog inputs "
     "with PGA, low-noise references, thermocouple and RTD support, USB and "
     "Ethernet, powered from a single 12V supply."),
    ("Battery IoT",
     "A battery-powered outdoor IoT sensor node with LoRa, GNSS, solar "
     "harvesting and Li-ion charging, an nRF52 SoC, ultra-low standby current "
     "and -20..+60C operation."),
    ("Medical wearable",
     "A wearable ECG patch: analog front end for biopotential, 3.7V Li-po, "
     "BLE, on-board flash logging, patient isolation/leakage-current safety, "
     "and a USB-C charging/service port."),
    ("Industrial gateway",
     "An industrial protocol gateway bridging RS485 Modbus, CAN, and dual "
     "10/100 Ethernet, powered from 24V with surge protection, an i.MX SoC, "
     "DDR memory, eMMC, and a real-time clock with battery backup."),
]


def main() -> int:
    settings = Settings()
    if settings.mock_mode:
        print("No QWEN_API_KEY — set it to run live.")
        return 1

    missed_by_single: Counter = Counter()
    rows = []
    for name, text in PROMPTS:
        cmp = run_comparison(text, settings)
        rows.append((name, cmp.multi_score, cmp.single_score, cmp.delta, cmp.total, cmp.mode))
        for c in cmp.concerns:
            if c.covered_multi and not c.covered_single:
                missed_by_single[c.label] += 1
        print(f"  done: {name:18s} multi {cmp.multi_score}/{cmp.total}  "
              f"single {cmp.single_score}/{cmp.total}  delta +{cmp.delta}  ({cmp.mode})")

    print("\n=== Summary ===")
    print(f"{'Design':18s} {'multi':>6s} {'single':>7s} {'delta':>6s} {'mode':>6s}")
    deltas = []
    for name, m, s, d, t, mode in rows:
        deltas.append(d)
        print(f"{name:18s} {m:>4d}/{t:<1d} {s:>5d}/{t:<1d} {('+'+str(d)):>6s} {mode:>6s}")
    if deltas:
        print(f"\navg delta: +{sum(deltas)/len(deltas):.2f}  (min +{min(deltas)}, max +{max(deltas)})")

    print("\n=== Concerns the single-agent missed (count across designs) ===")
    for label, n in missed_by_single.most_common():
        print(f"  {n}x  {label}")

    # Markdown artifact for the deck.
    live = [r for r in rows if r[5] == "qwen"]
    md = ["# Multi-agent vs single-agent — batch over hard designs", ""]
    md.append(f"_{len(live)}/{len(rows)} designs measured live (qwen); "
              "coverage = concern surfaced as engineering work, scored by the "
              "deterministic 12-point rubric._")
    md += ["", "| Design | Multi-agent | Single-agent | Δ | Mode |",
           "| --- | :---: | :---: | :---: | :---: |"]
    for name, m, s, d, t, mode in rows:
        md.append(f"| {name} | {m}/{t} | {s}/{t} | +{d} | {mode} |")
    if live:
        am = sum(r[1] for r in live) / len(live)
        as_ = sum(r[2] for r in live) / len(live)
        md.append(f"| **Average (live)** | **{am:.1f}/12** | **{as_:.1f}/12** "
                  f"| **+{am - as_:.1f}** | |")
    md += ["", "## What the single agent most often missed (live runs)", ""]
    for label, n in missed_by_single.most_common():
        md.append(f"- **{n}×** {label}")
    Path("docs/comparison-batch.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\nreport written to docs/comparison-batch.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
