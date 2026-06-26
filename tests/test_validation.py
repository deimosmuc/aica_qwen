"""Milestone 7: the validation stage (structural + real KiCad checks)."""
import pytest

from app.generators.kicad import generate_scaffold
from app.services.config import Settings
from app.services.kicad_cli import KiCadCli, KiCadCliError
from app.services.mock import mock_run
from app.services.validation import validate_project

REQ_TEXT = "A 24V board with an STM32 and RS485."


class FakeKiCad:
    """Stand-in for KiCadCli so validation logic is tested without the binary."""

    def __init__(self, available=True, opens=True, erc=None, fail_erc=False):
        self._available = available
        self._opens = opens
        self._erc = erc if erc is not None else {"sheets": []}
        self._fail_erc = fail_erc

    @property
    def available(self):
        return self._available

    def export_pdf(self, sch, out):
        if not self._opens:
            raise KiCadCliError("export failed")
        from pathlib import Path

        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text("%PDF-1.5")
        return Path(out)

    def run_erc(self, sch, out):
        if self._fail_erc:
            raise KiCadCliError("erc failed")
        return self._erc


def _scaffold(tmp_path):
    return generate_scaffold(mock_run(REQ_TEXT), REQ_TEXT, tmp_path / "proj")


def test_clean_scaffold_passes_structural_checks(tmp_path):
    out = _scaffold(tmp_path)
    v = validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=False))
    assert v.ok is True
    assert v.kicad_cli_available is False
    assert all(c.passed for c in v.checks)
    assert (out / "validation_report.md").is_file()


def test_report_written_and_marks_pass(tmp_path):
    out = _scaffold(tmp_path)
    validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=False))
    report = (out / "validation_report.md").read_text(encoding="utf-8")
    assert "Overall: PASS" in report


def test_missing_sheet_fails_validation(tmp_path):
    out = _scaffold(tmp_path)
    # Break the hierarchy: remove one subsheet file.
    next(iter((out / "sheets").glob("*.kicad_sch"))).unlink()
    v = validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=False))
    assert v.ok is False
    assert any("hierarchical sheets" in c.name and not c.passed for c in v.checks)


def test_production_ready_claim_fails(tmp_path):
    out = _scaffold(tmp_path)
    (out / "architecture.md").write_text(
        "# Architecture\n\nThis board is production-ready and certified.\n", encoding="utf-8"
    )
    v = validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=False))
    assert v.ok is False
    assert any("production-ready" in c.name and not c.passed for c in v.checks)


def test_real_kicad_checks_recorded_when_available(tmp_path):
    out = _scaffold(tmp_path)
    erc = {"sheets": [{"violations": [{"severity": "warning"}, {"severity": "error"}]}]}
    v = validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=True, opens=True, erc=erc))
    assert v.kicad_cli_available is True
    assert v.kicad_opens is True
    assert v.erc_violations == 2
    assert v.erc_by_severity == {"warning": 1, "error": 1}
    assert any(c.name == "KiCad opens & exports the project" and c.passed for c in v.checks)


def test_kicad_open_failure_fails_validation(tmp_path):
    out = _scaffold(tmp_path)
    v = validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=True, opens=False))
    assert v.ok is False
    assert v.kicad_opens is False


@pytest.mark.skipif(
    not KiCadCli(Settings()).available, reason="kicad-cli not installed in this environment"
)
def test_real_kicad_cli_end_to_end(tmp_path):
    out = _scaffold(tmp_path)
    v = validate_project(out, mock_run(REQ_TEXT), KiCadCli(Settings()))
    assert v.kicad_cli_available is True
    assert v.kicad_opens is True  # the generated scaffold really opens in KiCad
    assert v.ok is True
