# app/services/rubric.py
"""Deterministic engineering-concern rubric for the multi- vs single-agent comparison.

A concern is "covered" when it is *surfaced as engineering work* (block / TODO /
assumption / review item / note) in the flattened output text — NOT when a
component is placed. Detection is plain, reproducible keyword matching so the
metric is auditable; the UI also shows both raw outputs so a human can verify.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Concern:
    id: str
    label: str
    terms: tuple[str, ...]


RUBRIC: tuple[Concern, ...] = (
    Concern("input_protection", "Surge/ESD protection on power input",
            ("tvs", "surge", "esd", "overvoltage", "varistor", "transient")),
    Concern("reverse_polarity", "Reverse-polarity protection",
            ("reverse polarity", "reverse-polarity", "ideal diode", "polarity protection", "reverse voltage")),
    Concern("overcurrent", "Overcurrent / fuse protection",
            ("fuse", "overcurrent", "over-current", "ptc", "current limit", "efuse")),
    Concern("power_domains", "Defined power rails / domains",
            ("rail", "power domain", "ldo", "dc-dc", "buck", "regulator", "+3v3", "+5v", "3v3", "5v")),
    Concern("decoupling", "Decoupling / filtering",
            ("decoupl", "bypass", "ferrite", "bulk capacit", "filtering")),
    Concern("debug_access", "Debug / programming access",
            ("swd", "jtag", "debug", "swclk", "swdio", "programming")),
    Concern("testability", "Test points / status indication",
            ("test point", "testpoint", "status led", "led", "test pad")),
    Concern("reset", "Reset circuit",
            ("reset", "nrst", "power-on reset", "watchdog", "por")),
    Concern("clock", "Clock source",
            ("clock", "crystal", "oscillator", "xtal", "hse", "lse")),
    Concern("interface_protection", "Interface isolation / termination",
            ("isolation", "isolat", "termination", "terminat", "common-mode", "choke", "bus protection")),
    Concern("connectors", "External connectors identified",
            ("connector", "header", "receptacle", "jack", "plug", "socket")),
    Concern("documentation_honesty", "Docs, assumptions, explicit uncertainty",
            ("assumption", "todo", "needs human review", "documentation", "datasheet")),
)

# Short / ambiguous tokens need word-boundary matching to avoid false positives
# (e.g. "led" inside "scheduled", "swd" inside "forward"). Longer stems use plain
# substring so plurals/derivatives still match.
_BOUNDARY = {"led", "swd", "jtag", "por", "ptc", "esd", "tvs", "hse", "lse"}


def _matches(term: str, low_text: str) -> bool:
    if term in _BOUNDARY:
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low_text) is not None
    return term in low_text


def score(text: str) -> dict[str, bool]:
    """Return {concern_id: surfaced?} for the given text."""
    low = text.lower()
    return {c.id: any(_matches(t, low) for t in c.terms) for c in RUBRIC}


def coverage(text: str) -> int:
    """Number of distinct concerns surfaced in the text."""
    return sum(score(text).values())
