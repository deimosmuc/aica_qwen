"""Milestone 7: the kicad-cli wrapper (resolution + graceful degradation)."""
from app.services.config import Settings
from app.services.kicad_cli import KiCadCli


def test_disabled_means_unavailable():
    cli = KiCadCli(Settings(kicad_enabled=False))
    assert cli.available is False
    assert cli.path is None


def test_bogus_path_degrades_gracefully():
    cli = KiCadCli(Settings(kicad_enabled=True, kicad_cli_path="/nope/not-a-real-kicad-cli"))
    # Falls back to PATH / known locations; on a machine without KiCad this is
    # simply unavailable rather than an error.
    assert cli.available in (True, False)
    if not cli.available:
        assert cli.path is None


def test_version_none_when_unavailable():
    cli = KiCadCli(Settings(kicad_enabled=False))
    assert cli.version() is None
