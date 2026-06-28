from app.models.schemas import Block, Connection
from app.generators.kicad_root import sheet_pins_for, hier_labels_for


def _block(name, cat="other"):
    return Block(name=name, sheet=f"{name.lower()}.kicad_sch", purpose="x", category=cat)


CONNS = [
    Connection(source="Power", target="MCU", type="power"),
    Connection(source="Sensor", target="MCU", type="data"),
    Connection(source="MCU", target="Debug", type="debug"),
]


def test_pins_inferred_from_touching_connections():
    pins = sheet_pins_for(_block("MCU"), CONNS)
    assert any(p.kind == "power" for p in pins)
    assert any(p.kind == "data" for p in pins)
    assert any(p.kind == "debug" for p in pins)


def test_pin_direction_from_edge_role():
    # MCU is the TARGET of Power->MCU (incoming) -> input; SOURCE of MCU->Debug -> output
    pins = {(p.kind, p.shape) for p in sheet_pins_for(_block("MCU"), CONNS)}
    assert ("power", "input") in pins
    assert ("debug", "output") in pins


def test_block_with_no_connections_has_no_pins():
    assert sheet_pins_for(_block("Lonely"), CONNS) == []


def test_pins_are_capped_and_deterministic():
    many = [Connection(source=f"S{i}", target="Hub", type="data") for i in range(20)]
    a = sheet_pins_for(_block("Hub"), many)
    b = sheet_pins_for(_block("Hub"), many)
    assert a == b
    assert len(a) <= 8  # readability cap


def test_every_pin_has_a_matching_hier_label():
    pins = sheet_pins_for(_block("MCU"), CONNS)
    labels = hier_labels_for(pins)
    assert {p.name for p in pins} == {l.name for l in labels}
    for p, l in zip(pins, labels):
        assert l.shape in {"input", "output", "bidirectional", "passive"}
