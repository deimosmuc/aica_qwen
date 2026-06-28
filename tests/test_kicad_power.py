from app.generators.kicad_power import map_rail


def test_known_rails_map_to_standard_symbols():
    assert map_rail("+5V").lib_id == "power:+5V"
    assert map_rail("+3V3").lib_id == "power:+3V3"
    assert map_rail("GND").lib_id == "power:GND"


def test_rail_normalisation():
    assert map_rail("+3.3V").lib_id == "power:+3V3"
    assert map_rail("gnd").lib_id == "power:GND"
    assert map_rail(" +5v ").lib_id == "power:+5V"


def test_voltage_in_name_maps_to_nearest_standard_rail():
    m = map_rail("VIN_24V")
    assert m.lib_id == "power:+24V"
    assert m.label == "VIN_24V"  # original name preserved as the on-sheet label


def test_unknown_rail_falls_back_to_pwr_flag_with_label():
    m = map_rail("MYNET")
    assert m.lib_id == "power:PWR_FLAG"
    assert m.label == "MYNET"
