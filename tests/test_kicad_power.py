from app.generators.kicad_power import map_rail, power_sheet


def test_known_rails_map_to_standard_symbols():
    assert map_rail("+5V").lib_id == "power:+5V"
    assert map_rail("+3V3").lib_id == "power:+3V3"
    assert map_rail("GND").lib_id == "power:GND"
    assert map_rail("GNDA").lib_id == "power:GNDA"
    assert map_rail("GNDD").lib_id == "power:GNDD"


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


def test_power_sheet_has_a_symbol_per_rail():
    rails = ["MYRAIL", "+5V", "+3V3", "GND"]
    body = power_sheet(rails, project_name="proj",
                       root_uuid="11111111-1111-4111-8111-111111111111",
                       block_uuid="22222222-2222-4222-8222-222222222222")
    assert '(symbol "power:+5V"' in body.lib_symbols
    assert '(symbol "power:GND"' in body.lib_symbols
    assert '(symbol "power:PWR_FLAG"' in body.lib_symbols
    assert body.instances.count('(lib_id "power:') == len(rails)
    assert '(global_label "MYRAIL"' in body.instances
    assert "/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222" in body.instances


def test_power_sheet_only_embeds_used_symbols():
    body = power_sheet(["+5V", "GND"], "p", "r", "b")
    assert '(symbol "power:+12V"' not in body.lib_symbols


def test_power_sheet_is_deterministic():
    a = power_sheet(["+5V", "GND"], "p", "r", "b")
    b = power_sheet(["+5V", "GND"], "p", "r", "b")
    assert a.lib_symbols == b.lib_symbols and a.instances == b.instances
