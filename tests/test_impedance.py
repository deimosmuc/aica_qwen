"""Tests for the controlled-impedance lookup service."""
from app.models.schemas import NetClass
from app.services.impedance import aux_nets, fill_impedance, impedance_for, impedance_review


def test_known_interfaces_map_to_target_impedance():
    assert impedance_for("USB") == "90 Ω diff"
    assert impedance_for("USB3 SuperSpeed") == "90 Ω diff"
    assert impedance_for("CAN") == "120 Ω diff"
    assert impedance_for("RS485") == "120 Ω diff"
    assert impedance_for("Ethernet") == "100 Ω diff"
    assert impedance_for("HDMI") == "100 Ω diff"
    assert impedance_for("MIPI CSI") == "100 Ω diff"
    assert impedance_for("LVDS") == "100 Ω diff"
    assert impedance_for("PCIe") == "85 Ω diff"
    assert impedance_for("DDR3") == "40 Ω"


def test_power_and_generic_classes_have_no_impedance():
    assert impedance_for("PWR") is None
    assert impedance_for("Signal") is None
    assert impedance_for("GPIO") is None


def test_matches_against_net_names_not_just_class_name():
    # Class name is generic, but the net names reveal a USB interface.
    assert impedance_for("Signal", ["USB_DP", "USB_DM"]) == "90 Ω diff"


def test_case_insensitive():
    assert impedance_for("can") == impedance_for("CAN") == "120 Ω diff"


def test_fill_impedance_fills_only_empty_matching_classes():
    classes = [
        NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND"]),
        NetClass(name="USB", min_width_mm=0.2, clearance_mm=0.2, nets=["USB_DP"]),
    ]
    fill_impedance(classes)
    assert classes[0].impedance is None  # power class: no controlled impedance
    assert classes[1].impedance == "90 Ω diff"


def test_fill_impedance_does_not_overwrite_explicit_agent_value():
    classes = [
        NetClass(
            name="USB", min_width_mm=0.2, clearance_mm=0.2,
            nets=["USB_DP"], impedance="90 Ω diff (custom)",
        ),
    ]
    fill_impedance(classes)
    assert classes[0].impedance == "90 Ω diff (custom)"  # agent value wins


def test_fill_impedance_returns_same_list():
    classes = [NetClass(name="USB", min_width_mm=0.2, clearance_mm=0.2, nets=[])]
    assert fill_impedance(classes) is classes


def test_aux_nets_identifies_supply_and_config_nets():
    assert aux_nets(["VBUS", "CC1", "CC2", "VCONN", "USB_ID", "SHIELD", "GND", "+5V", "3V3"]) == [
        "VBUS", "CC1", "CC2", "VCONN", "USB_ID", "SHIELD", "GND", "+5V", "3V3",
    ]
    assert aux_nets(["USB_D+", "USB_D-", "CAN_H", "ETH_TX+"]) == []


def test_aux_only_class_gets_no_impedance_despite_usb_name():
    # A "USB Power" class holding only VBUS/CC must not inherit 90 Ω diff.
    assert impedance_for("USB Power", ["VBUS", "CC1", "CC2"]) is None
    classes = [NetClass(name="USB", min_width_mm=0.3, clearance_mm=0.2, nets=["VBUS", "CC1"])]
    fill_impedance(classes)
    assert classes[0].impedance is None


def test_impedance_review_flags_aux_nets_in_controlled_class():
    classes = fill_impedance([
        NetClass(name="USB", min_width_mm=0.15, clearance_mm=0.15,
                 nets=["USB_D+", "USB_D-", "VBUS", "CC1"]),
    ])
    findings = impedance_review(classes)
    assert len(findings) == 1
    assert "VBUS" in findings[0] and "CC1" in findings[0]
    assert "USB" in findings[0] and "90 Ω diff" in findings[0]


def test_impedance_review_clean_classes_yield_no_findings():
    classes = fill_impedance([
        NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["VBUS", "+3V3", "GND"]),
        NetClass(name="USB", min_width_mm=0.15, clearance_mm=0.15, nets=["USB_D+", "USB_D-"]),
    ])
    assert impedance_review(classes) == []
