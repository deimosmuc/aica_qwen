"""Sheet-pin inference for root hierarchical blocks + their matching child-sheet
hierarchical labels. A sheet pin on the root MUST have a matching hierarchical
label inside the child sheet or KiCad ERC flags an 'unmatched sheet pin' — so the
two are generated together (callers must emit both)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Block, Connection

_MAX_PINS = 8
_KIND = {"power": "power", "data": "data", "control": "control", "debug": "debug"}
# Stable ordering so output is deterministic regardless of connection order.
_TYPE_ORDER = {"power": 0, "data": 1, "control": 2, "debug": 3}


@dataclass(frozen=True)
class Pin:
    name: str        # e.g. "PWR", "DATA1"
    kind: str        # power|data|control|debug
    shape: str       # input|output|bidirectional (sheet-pin shape)
    side: str        # bottom|top|left|right (placement hint)


@dataclass(frozen=True)
class HierLabel:
    name: str
    shape: str       # complementary shape inside the child sheet


def sheet_pins_for(block: Block, connections: list[Connection]) -> list[Pin]:
    touching = []
    for c in connections:
        if c.source == block.name:
            touching.append((c, "output"))
        elif c.target == block.name:
            touching.append((c, "input"))
    if not touching:
        return []
    touching.sort(key=lambda t: (_TYPE_ORDER.get(t[0].type, 9), t[1],
                                 t[0].target if t[1] == "output" else t[0].source))
    pins: list[Pin] = []
    counts: dict[str, int] = {}
    seen_dir: dict[str, set[str]] = {}
    for c, direction in touching:
        kind = _KIND.get(c.type, "data")
        dirs = seen_dir.setdefault(kind, set())
        dirs.add(direction)
        n = counts.get(kind, 0) + 1
        counts[kind] = n
        name = kind.upper() if n == 1 else f"{kind.upper()}{n}"
        shape = "bidirectional" if {"input", "output"} <= dirs else direction
        side = "bottom" if kind == "power" else ("right" if direction == "output" else "left")
        pins.append(Pin(name=name, kind=kind, shape=shape, side=side))
        if len(pins) >= _MAX_PINS:
            break
    return pins


_COMPLEMENT = {"input": "output", "output": "input",
               "bidirectional": "bidirectional"}


def hier_labels_for(pins: list[Pin]) -> list[HierLabel]:
    # The child-sheet hierarchical label name MUST equal the sheet-pin name.
    return [HierLabel(name=p.name, shape=_COMPLEMENT.get(p.shape, "passive"))
            for p in pins]
