"""Controlled-impedance defaults for common high-speed interfaces.

Single source of truth that maps an interface to its target characteristic
impedance. Used to (a) fill ``NetClass.impedance`` when the PCB Engineer omits it
(deterministic fallback, so it also works keyless in Mock Mode) and (b) anchor the
requirement in both the PDF report's net-class table and the KiCad schematic note.

Impedance is a *physical, manufacturable* property of a net class — getting it
wrong (or omitting it for USB/CAN/Ethernet/…) is a classic, expensive PCB mistake,
so we surface it as a first-class constraint rather than burying it.
"""
from __future__ import annotations

import re

# Ordered keyword → target impedance. First match wins; patterns are matched
# (case-insensitive) against the net-class name plus its net names. Differential
# pairs are flagged "diff"; single-ended controlled nets carry a plain value.
_IMPEDANCE_RULES: list[tuple[str, str]] = [
    (r"usb\s*-?\s*3|superspeed|ss[tr]x", "90 Ω diff"),
    (r"\busb\b|usb_?d|usbdp|usbdm", "90 Ω diff"),
    (r"\bcan\b|canfd|can_?[hl]", "120 Ω diff"),
    (r"rs-?_? ?485|rs485|profibus", "120 Ω diff"),
    (r"ethern|enet|rmii|rgmii|\d+base-?t|mdi\b", "100 Ω diff"),
    (r"hdmi|tmds|displayport|\bdp_?(lane|tx)", "100 Ω diff"),
    (r"mipi|\bcsi\b|\bdsi\b|d-?phy", "100 Ω diff"),
    (r"lvds", "100 Ω diff"),
    (r"pci-?e|pcie", "85 Ω diff"),
    (r"\bsata\b", "100 Ω diff"),
    (r"\bl?p?ddr\d?\b|\bdqs?\b|\bdq\d", "40 Ω"),
]


# Supply / auxiliary nets that are NEVER impedance-controlled, no matter which
# class they end up in: USB power+config (VBUS, CC, VCONN, ID), shields, ground
# and generic supply rails. Used to keep e.g. a "USB" class honest — only the
# actual differential data pair carries the 90 Ω requirement.
_AUX_NET_PATTERN = re.compile(
    r"vbus|vconn|\bcc\d?\b|usb_?id|\bid\b|shield|shld|\bgnd\b|agnd|dgnd"
    r"|\bvin\b|\bvcc\b|\bvdd\b|\bvbat\b|\+?\d+v\d*\b|v\d+_\d+\b",
    re.IGNORECASE,
)


def aux_nets(nets: list[str] | None) -> list[str]:
    """Subset of ``nets`` that are supply/auxiliary nets (never impedance-controlled)."""
    return [n for n in (nets or []) if _AUX_NET_PATTERN.search(n)]


def impedance_for(name: str, nets: list[str] | None = None) -> str | None:
    """Target controlled impedance for a net class, or ``None`` when it is not a
    known controlled-impedance interface (e.g. power or generic signal nets).

    Guardrail: a class whose nets are ALL supply/aux (e.g. a "USB Power" class
    holding only VBUS/CC) is not impedance-controlled even if its name matches."""
    net_list = nets or []
    if net_list and len(aux_nets(net_list)) == len(net_list):
        return None
    haystack = " ".join([name or "", *net_list]).lower()
    for pattern, z in _IMPEDANCE_RULES:
        if re.search(pattern, haystack):
            return z
    return None


def fill_impedance(netclasses: list) -> list:
    """Fill ``impedance`` on any net class that matches a known interface and does
    not already carry an explicit value (the agent's value always wins). Mutates
    and returns the same list."""
    for nc in netclasses:
        if not getattr(nc, "impedance", None):
            z = impedance_for(nc.name, getattr(nc, "nets", None))
            if z:
                nc.impedance = z
    return netclasses


def impedance_review(netclasses: list) -> list[str]:
    """Deterministic hygiene check: supply/aux nets inside an impedance-controlled
    class are a classic spec error (USB CC/VBUS "inheriting" 90 Ω diff). Returns
    one finding string per offending class, empty when everything is clean."""
    findings = []
    for nc in netclasses:
        z = getattr(nc, "impedance", None)
        if not z:
            continue
        offending = aux_nets(getattr(nc, "nets", None))
        if offending:
            findings.append(
                f'Net class "{nc.name}" is impedance-controlled ({z}) but contains '
                f"supply/auxiliary nets: {', '.join(offending)}. Only the actual "
                "high-speed data pair belongs in an impedance-controlled class — "
                "move these nets to PWR or Signal."
            )
    return findings
