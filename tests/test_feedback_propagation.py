"""User feedback reaches the agents.

Two channels, both honored by every agent:
- the user's verbatim original request (so detail isn't lost after the
  Requirements agent structures it), and
- soft revision requests from a prior result / course-correction.

These tests pin that the prompt blocks render, that every agent actually puts
them in front of the model, and that the orchestrator and stepwise pipeline
thread them all the way through.
"""
from fastapi.testclient import TestClient

import app.api.routes as routes
import app.services.orchestrator as orch_mod
from app.agents.arbitration import ArbitrationAgent
from app.agents.architect import SystemArchitectAgent
from app.agents.base import guidance_block, original_request_block, revision_block
from app.agents.critic import DesignCriticAgent
from app.agents.pcb_critic import PcbCriticAgent
from app.agents.pcb_engineer import PcbEngineerAgent
from app.agents.requirements import RequirementsAgent
from app.main import app
from app.models.schemas import (
    Arbitration, Architecture, Block, Critique, PcbCritique, PcbReadiness, Requirements,
)
from app.services.config import Settings

ORIG = "A bat detector with a MEMS mic and an SD card, powered by 2x AA."
REVS = ["Use USB-C instead of micro-USB", "Add a low-battery LED"]


class FakeClient:
    """Captures the (system, user) prompt and returns a fixed payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, model=None):
        self.calls.append({"system": system, "user": user})
        return self.payload


# --- block renderers ---------------------------------------------------------


def test_blocks_empty_render_to_nothing():
    assert original_request_block(None) == ""
    assert original_request_block("   ") == ""
    assert revision_block(None) == ""
    assert revision_block([]) == ""
    assert revision_block(["", "  "]) == ""


def test_blocks_render_their_content():
    orig = original_request_block(ORIG)
    assert "ORIGINAL USER REQUEST" in orig and ORIG in orig
    rev = revision_block(REVS)
    assert "REVISION REQUESTS" in rev
    assert "- Use USB-C instead of micro-USB" in rev
    assert "- Add a low-battery LED" in rev


def test_revision_block_is_distinct_from_hard_constraints():
    # Soft revisions must NOT be framed as the mandatory company-policy block.
    # (The revision block may reference it — "unless they conflict with …" — but
    # must not carry the hard-constraints header itself.)
    rev = revision_block(REVS)
    assert rev.lstrip().startswith("REVISION REQUESTS")
    assert "MANDATORY USER CONSTRAINTS — hard requirements" not in rev
    assert "MANDATORY USER CONSTRAINTS — hard requirements" in guidance_block(REVS)


# --- every agent puts the feedback in front of the model ---------------------

REQS = Requirements(requirements=["bat detector"], confidence=0.6)
ARCH = Architecture(blocks=[Block(name="MCU", sheet="mcu.kicad_sch", purpose="core")])
_PCB_PAYLOAD = {
    "layerstack": "2-layer", "layerstack_reason": "simple",
    "netclasses": [], "floorplan_text": "", "floorplan_ascii": "", "package_hints": [],
    "constraints": {"min_clearance_mm": 0.2, "min_track_width_mm": 0.2,
                    "via_drill_mm": 0.4, "via_annular_ring_mm": 0.15},
}


def _assert_feedback_present(user: str, *, expect_original: bool):
    assert "REVISION REQUESTS" in user and "Use USB-C instead of micro-USB" in user
    if expect_original:
        assert "ORIGINAL USER REQUEST" in user and ORIG in user


def test_requirements_agent_carries_revisions():
    c = FakeClient({"requirements": ["r"], "confidence": 0.5})
    RequirementsAgent().run(c, ORIG, [], revisions=REVS)
    # The Requirements agent already gets the raw text as its main payload, so it
    # only needs the revision block (not a second verbatim copy).
    _assert_feedback_present(c.calls[0]["user"], expect_original=False)


def test_architect_carries_original_and_revisions():
    c = FakeClient({"blocks": [{"name": "MCU", "sheet": "mcu.kicad_sch", "purpose": "core"}]})
    SystemArchitectAgent().run(c, REQS, [], original_request=ORIG, revisions=REVS)
    _assert_feedback_present(c.calls[0]["user"], expect_original=True)


def test_critic_carries_original_and_revisions():
    c = FakeClient({})
    DesignCriticAgent().run(c, REQS, ARCH, [], original_request=ORIG, revisions=REVS)
    _assert_feedback_present(c.calls[0]["user"], expect_original=True)


def test_arbitration_carries_original_and_revisions():
    c = FakeClient({})
    ArbitrationAgent().run(c, REQS, ARCH, Critique(), [], original_request=ORIG, revisions=REVS)
    _assert_feedback_present(c.calls[0]["user"], expect_original=True)


def test_pcb_engineer_carries_original_and_revisions():
    c = FakeClient(_PCB_PAYLOAD)
    PcbEngineerAgent().run(c, REQS, ARCH, Arbitration(approved_architecture=ARCH), [],
                           original_request=ORIG, revisions=REVS)
    _assert_feedback_present(c.calls[0]["user"], expect_original=True)


def test_pcb_critic_carries_original_and_revisions():
    pcb = PcbReadiness.model_validate(_PCB_PAYLOAD)
    c = FakeClient({})
    PcbCriticAgent().run(c, REQS, pcb, [], original_request=ORIG, revisions=REVS)
    _assert_feedback_present(c.calls[0]["user"], expect_original=True)


# --- orchestrator threads feedback to EVERY downstream agent -----------------


def _capture_agents(monkeypatch, seen):
    """Replace every agent.run with a stub that records the original_request and
    revisions it received, and returns a minimal valid object."""

    def rec(agent, **kw):
        seen[agent] = {"original_request": kw.get("original_request"),
                       "revisions": kw.get("revisions")}

    monkeypatch.setattr(orch_mod.RequirementsAgent, "run",
                        lambda self, c, text, g=None, **kw: (rec("requirements", **kw),
                                                             Requirements(requirements=["r"], confidence=0.5))[1])
    monkeypatch.setattr(orch_mod.SystemArchitectAgent, "run",
                        lambda self, c, req, g=None, **kw: (rec("architecture", **kw), ARCH)[1])
    monkeypatch.setattr(orch_mod.DesignCriticAgent, "run",
                        lambda self, c, req, arch, g=None, **kw: (rec("critique", **kw), Critique())[1])
    monkeypatch.setattr(orch_mod.ArbitrationAgent, "run",
                        lambda self, c, req, arch, crit, g=None, **kw: (rec("arbitration", **kw),
                                                                        Arbitration(approved_architecture=arch))[1])
    monkeypatch.setattr(orch_mod.PcbEngineerAgent, "run",
                        lambda self, c, req, arch, arb, g=None, **kw: (rec("pcb_engineer", **kw),
                                                                       PcbReadiness.model_validate(_PCB_PAYLOAD))[1])
    monkeypatch.setattr(orch_mod.PcbCriticAgent, "run",
                        lambda self, c, req, pcb, g=None, **kw: (rec("pcb_critic", **kw), PcbCritique())[1])


def test_orchestrator_threads_feedback_to_all_downstream_agents(monkeypatch):
    seen = {}
    _capture_agents(monkeypatch, seen)
    orch_mod.Orchestrator(Settings(qwen_api_key="sk-test")).run(ORIG, [], REVS)

    # Requirements gets the revisions (its text payload already is the original).
    assert seen["requirements"]["revisions"] == REVS
    # Every later agent gets BOTH the verbatim original request and the revisions.
    for role in ("architecture", "critique", "arbitration", "pcb_engineer", "pcb_critic"):
        assert seen[role]["original_request"] == ORIG, role
        assert seen[role]["revisions"] == REVS, role


# --- endpoints accept the revisions field ------------------------------------


def test_run_stream_endpoint_accepts_revisions(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))  # mock mode
    client = TestClient(app)
    r = client.post("/api/run/stream",
                    json={"requirements_text": ORIG, "revisions": REVS})
    assert r.status_code == 200


def test_step_endpoint_accepts_revisions(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(qwen_api_key=""))  # mock mode
    client = TestClient(app)
    r = client.post("/api/step",
                    json={"stage": "requirements", "requirements_text": ORIG, "revisions": REVS})
    assert r.status_code == 200
