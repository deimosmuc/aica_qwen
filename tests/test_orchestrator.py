"""Orchestrator: per-role model wiring + behaviour preservation."""
from app.services.config import Settings
from app.services.orchestrator import Orchestrator
from app.services.profiles import PROFILES


def test_client_per_role_uses_profile_model():
    orch = Orchestrator(Settings(qwen_api_key="sk-test"), profile=PROFILES["Senior Review Team"])
    assert orch._client_for("critique")._model == "qwen-max"
    assert orch._client_for("arbitration")._model == "qwen-max"
    assert orch._client_for("architecture")._model == "qwen-plus"


def test_default_profile_is_uniform():
    s = Settings(qwen_api_key="sk-test")
    orch = Orchestrator(s)
    assert orch._client_for("critique")._model == s.qwen_model


def test_mock_mode_pipeline_unchanged():
    out = Orchestrator(Settings(qwen_api_key="")).run("a 24V board")
    assert out.mode == "mock"
    assert len(out.trace) == 4
    assert all(s.round == 1 for s in out.trace)


import app.services.orchestrator as orch_mod
from app.models.schemas import Arbitration, Architecture, Block, Critique, PcbCritique, PcbReadiness, Requirements
from app.services.profiles import RunProfile

_ALL_ROLES = ("requirements", "architecture", "critique", "arbitration", "pcb_engineer", "pcb_critique")


def _rework_profile(rounds=2):
    return RunProfile(
        name="t",
        models={r: "qwen-plus" for r in _ALL_ROLES},
        rework=True, max_rounds=rounds,
    )


def _stub_pcb_readiness() -> PcbReadiness:
    from app.models.schemas import ConstraintSet, NetClass, PackageHint
    return PcbReadiness(
        layerstack="2-layer",
        layerstack_reason="simple board",
        netclasses=[NetClass(name="Default", min_width_mm=0.2, clearance_mm=0.2)],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.4, via_annular_ring_mm=0.15),
        floorplan_text="MCU central.",
        floorplan_ascii="[MCU]",
        package_hints=[],
    )


def _patch_agents(monkeypatch, critic_fn, calls):
    monkeypatch.setattr(orch_mod.RequirementsAgent, "run",
                        lambda self, c, text, g=None: Requirements(requirements=["r"], confidence=0.5))

    def arch(self, c, requirements, g=None):
        calls["arch"] += 1
        return Architecture(blocks=[Block(name="MCU", sheet="mcu.kicad_sch", purpose="core")])

    def crit(self, c, requirements, architecture, g=None):
        calls["crit"] += 1
        return critic_fn(calls["crit"])

    monkeypatch.setattr(orch_mod.SystemArchitectAgent, "run", arch)
    monkeypatch.setattr(orch_mod.DesignCriticAgent, "run", crit)
    monkeypatch.setattr(orch_mod.ArbitrationAgent, "run",
                        lambda self, c, req, arch, crit, g=None: Arbitration(approved_architecture=arch))
    monkeypatch.setattr(orch_mod.PcbEngineerAgent, "run",
                        lambda self, c, req, arch, arb, g=None: _stub_pcb_readiness())
    monkeypatch.setattr(orch_mod.PcbCriticAgent, "run",
                        lambda self, c, req, pcb, g=None: PcbCritique())


def test_rework_stops_when_critic_is_clean(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["DUMMY_CLOCK"]) if n == 1 else Critique(), calls)
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"), profile=_rework_profile()).run("board")
    assert calls["arch"] == 2 and calls["crit"] == 2     # initial + exactly one rework
    assert any(s.round == 2 for s in out.trace)
    assert out.critique.missing_blocks == []             # final state is the clean one


def test_rework_is_bounded_when_critic_never_satisfied(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["still missing"]), calls)
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"), profile=_rework_profile(rounds=2)).run("board")
    assert calls["arch"] == 2 and calls["crit"] == 2     # capped at max_rounds, no infinite loop
    assert max(s.round for s in out.trace) == 2


def test_no_rework_when_profile_disables_it(monkeypatch):
    calls = {"arch": 0, "crit": 0}
    _patch_agents(monkeypatch, lambda n: Critique(missing_blocks=["DUMMY_CLOCK"]), calls)
    profile = _rework_profile().model_copy(update={"rework": False})
    out = orch_mod.Orchestrator(Settings(qwen_api_key="sk-test"), profile=profile).run("board")
    assert calls["arch"] == 1 and calls["crit"] == 1     # single pass despite missing blocks
    assert all(s.round == 1 for s in out.trace)


def test_mock_mode_rework_profile_shows_two_rounds():
    out = orch_mod.Orchestrator(Settings(qwen_api_key=""), profile=_rework_profile()).run("a 24V board")
    assert out.mode == "mock"
    assert sorted({s.round for s in out.trace}) == [1, 2]
    round1_critic = [s for s in out.trace if s.agent == "Design Critic" and s.round == 1][0]
    assert round1_critic.status == "warning"
    assert out.critique.missing_blocks == []


def test_mock_mode_non_rework_profile_is_single_pass():
    out = orch_mod.Orchestrator(Settings(qwen_api_key=""), profile=PROFILES["Uniform qwen-plus"]).run("board")
    assert len(out.trace) == 4
    assert all(s.round == 1 for s in out.trace)
