# Feature D — PCB-Readiness Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 5th agent stage (PCB Engineer + PCB Critic rework loop) that produces `PCB_READINESS.md` and `pcb_constraints.kicad_dru` in the ZIP, visible in the Agent Society chat.

**Architecture:** `PcbEngineerAgent` (qwen-plus) generates layerstack/netclasses/constraints/floorplan/package hints as structured JSON; `PcbCriticAgent` (qwen-max) reviews and returns `missing_blocks`; a rework loop (max 2 rounds, same pattern as existing Architect/Critic loop) runs in the orchestrator. After the final approved `PcbReadiness`, a Python template generates the `.kicad_dru` file deterministically — no LLM writes raw KiCad syntax. Both agents emit `TraceStep` entries so the Society chat shows them automatically.

**Tech Stack:** Python/Pydantic (existing), Jinja2 (existing via kicad generator), FastAPI (existing), Alpine.js (existing UI)

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `app/models/schemas.py` | Modify | Add `NetClass`, `ConstraintSet`, `PackageHint`, `PcbReadiness`; extend `RunResponse` |
| `app/agents/pcb_engineer.py` | Create | PCB Engineer Agent prompt + `run()` |
| `app/agents/pcb_critic.py` | Create | PCB Critic Agent prompt + `run()` |
| `app/generators/pcb_dru.py` | Create | Deterministic `.kicad_dru` generator from `ConstraintSet` + `list[NetClass]` |
| `app/services/profiles.py` | Modify | Add `"pcb_engineer"` + `"pcb_critique"` to `ROLES` and all `PROFILES` |
| `app/services/orchestrator.py` | Modify | Add `_pcb_design_and_review()`, extend `run()` with 5th stage |
| `app/services/stepwise.py` | Modify | Add `"pcb_engineer"` to `_STAGE_ORDER`, add mock+live step handler |
| `app/services/mock.py` | Modify | Add fixed `PcbReadiness` to `mock_run()` and `mock_run_rework()` |
| `app/generators/kicad.py` | Modify | Write `PCB_READINESS.md` + `pcb_constraints.kicad_dru` into project dir |
| `app/static/index.html` | Modify | `avatarColor` entry for PCB Engineer; phase divider in Society chat |
| `tests/test_pcb_schemas.py` | Create | Schema validation tests |
| `tests/test_pcb_engineer.py` | Create | Agent unit tests (mock client) |
| `tests/test_pcb_critic.py` | Create | Critic unit tests (mock client) |
| `tests/test_pcb_dru.py` | Create | DRU generator output tests |
| `tests/test_orchestrator_pcb.py` | Create | End-to-end mock run: 5+ TraceSteps, ZIP has new files |

---

## Task 1: Schemas — PcbReadiness models

**Files:**
- Modify: `app/models/schemas.py`
- Create: `tests/test_pcb_schemas.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pcb_schemas.py
from app.models.schemas import NetClass, ConstraintSet, PackageHint, PcbReadiness, RunResponse

def test_netclass_fields():
    nc = NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3V3"])
    assert nc.name == "PWR"
    assert nc.nets == ["GND", "+3V3"]

def test_constraint_set_fields():
    cs = ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                       via_drill_mm=0.3, via_annular_ring_mm=0.1)
    assert cs.via_drill_mm == 0.3

def test_package_hint_fields():
    ph = PackageHint(component_type="MCU", recommended_package="QFN-32",
                     reason="thermal pad improves heat dissipation")
    assert ph.recommended_package == "QFN-32"

def test_pcb_readiness_round_trip():
    pr = PcbReadiness(
        layerstack="4-layer",
        layerstack_reason="RF module requires solid GND plane",
        netclasses=[NetClass(name="Signal", min_width_mm=0.2, clearance_mm=0.2, nets=[])],
        constraints=ConstraintSet(min_clearance_mm=0.2, min_track_width_mm=0.2,
                                  via_drill_mm=0.3, via_annular_ring_mm=0.1),
        floorplan_text="Isolate RF section from digital core.",
        floorplan_ascii="[RF] | [MCU] [PWR]",
        package_hints=[PackageHint(component_type="Resistor",
                                   recommended_package="0603",
                                   reason="hand-solderable")],
    )
    assert pr.layerstack == "4-layer"
    data = pr.model_dump()
    assert data["netclasses"][0]["name"] == "Signal"

def test_run_response_pcb_readiness_optional():
    # RunResponse.pcb_readiness must default to None (additive, no breaking change)
    from app.services.mock import mock_run
    r = mock_run("test")
    assert r.pcb_readiness is None
```

- [ ] **Step 2: Run tests — expect ImportError**

```
cd C:\dev\Qwen_Cloud_Agents_06_2026
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_schemas.py -v
```
Expected: `ImportError: cannot import name 'NetClass'`

- [ ] **Step 3: Add schemas to `app/models/schemas.py`**

Add after the `Arbitration` class (around line 113, before `TraceStep`):

```python
# --- PCB-Readiness Pack (Feature D) -----------------------------------------

class NetClass(BaseModel):
    name: str
    min_width_mm: float
    clearance_mm: float
    nets: list[str] = []

class ConstraintSet(BaseModel):
    min_clearance_mm: float
    min_track_width_mm: float
    via_drill_mm: float
    via_annular_ring_mm: float

class PackageHint(BaseModel):
    component_type: str
    recommended_package: str
    reason: str

class PcbReadiness(BaseModel):
    layerstack: str          # "2-layer" | "4-layer" | "6-layer"
    layerstack_reason: str
    netclasses: list[NetClass]
    constraints: ConstraintSet
    floorplan_text: str
    floorplan_ascii: str
    package_hints: list[PackageHint]
```

Then add to `RunResponse` (around line 152):

```python
    pcb_readiness: PcbReadiness | None = None
```

- [ ] **Step 4: Run tests — all pass**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_schemas.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add app/models/schemas.py tests/test_pcb_schemas.py
git commit -m "feat(pcb): add PcbReadiness Pydantic schemas"
```

---

## Task 2: PCB Engineer Agent

**Files:**
- Create: `app/agents/pcb_engineer.py`
- Create: `tests/test_pcb_engineer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pcb_engineer.py
import json
import pytest
from unittest.mock import MagicMock
from app.agents.pcb_engineer import PcbEngineerAgent
from app.models.schemas import (
    Architecture, Block, Connection, Requirements, ClarifyingQuestion,
    Arbitration, PcbReadiness
)

def _mock_requirements() -> Requirements:
    return Requirements(
        requirements=["24V input", "STM32 MCU", "RS485 interface"],
        constraints=["Industrial environment"],
        clarifications=[],
    )

def _mock_architecture() -> Architecture:
    return Architecture(
        blocks=[
            Block(name="MCU", description="STM32", interfaces=[], power_rails=["+3.3V"]),
            Block(name="RS485", description="Transceiver", interfaces=["RS485"], power_rails=["+3.3V"]),
            Block(name="Power", description="24V→3.3V", interfaces=[], power_rails=["24V", "+3.3V"]),
        ],
        connections=[],
        power_rails=["+3.3V", "24V", "GND"],
    )

def _mock_arbitration() -> Arbitration:
    return Arbitration(
        approved_architecture=_mock_architecture(),
        todo=["TODO: add TVS diode"],
        human_review=[],
        accepted_assumptions=["Single-board design"],
    )

def _agent_response() -> dict:
    return {
        "layerstack": "4-layer",
        "layerstack_reason": "Solid GND plane needed for RS485 signal integrity",
        "netclasses": [
            {"name": "PWR", "min_width_mm": 0.5, "clearance_mm": 0.3, "nets": ["GND", "+3.3V", "24V"]},
            {"name": "Signal", "min_width_mm": 0.2, "clearance_mm": 0.2, "nets": ["RS485_A", "RS485_B"]},
        ],
        "constraints": {
            "min_clearance_mm": 0.2,
            "min_track_width_mm": 0.2,
            "via_drill_mm": 0.4,
            "via_annular_ring_mm": 0.15,
        },
        "floorplan_text": "Power section isolated in corner. RS485 transceiver near connector.",
        "floorplan_ascii": "+------------------+\n| [PWR]  | [RS485] |\n| [MCU]           |\n+------------------+",
        "package_hints": [
            {"component_type": "MCU", "recommended_package": "LQFP-64", "reason": "hand-solderable"},
            {"component_type": "Resistor", "recommended_package": "0603", "reason": "hand-solderable"},
        ],
    }

def test_pcb_engineer_returns_pcb_readiness():
    client = MagicMock()
    client.chat_json.return_value = _agent_response()
    agent = PcbEngineerAgent()
    result = agent.run(client, _mock_requirements(), _mock_architecture(), _mock_arbitration())
    assert isinstance(result, PcbReadiness)
    assert result.layerstack == "4-layer"
    assert len(result.netclasses) == 2
    assert result.netclasses[0].name == "PWR"
    assert result.constraints.via_drill_mm == 0.4

def test_pcb_engineer_package_hints():
    client = MagicMock()
    client.chat_json.return_value = _agent_response()
    result = PcbEngineerAgent().run(
        client, _mock_requirements(), _mock_architecture(), _mock_arbitration()
    )
    assert any(h.component_type == "MCU" for h in result.package_hints)

def test_pcb_engineer_guidance_included():
    client = MagicMock()
    client.chat_json.return_value = _agent_response()
    PcbEngineerAgent().run(
        client, _mock_requirements(), _mock_architecture(), _mock_arbitration(),
        guidance=["Prefer SMD components"]
    )
    call_args = client.chat_json.call_args
    assert "Prefer SMD components" in call_args[0][1]
```

- [ ] **Step 2: Run — expect ImportError**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_engineer.py -v
```
Expected: `ImportError: No module named 'app.agents.pcb_engineer'`

- [ ] **Step 3: Create `app/agents/pcb_engineer.py`**

```python
"""PCB Engineer Agent — role: PCB Layout Preparation Engineer.

Analyses the approved architecture and produces structured PCB-readiness
recommendations: layerstack, netclasses, design constraints, floorplan
strategy, and package hints. Does NOT produce layout or routing.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block
from app.models.schemas import (
    Arbitration, Architecture, ConstraintSet, NetClass,
    PackageHint, PcbReadiness, Requirements,
)

NAME = "PCB Engineer"
ROLE = "PCB Layout Preparation Engineer"

SYSTEM_PROMPT = """You are a PCB layout preparation engineer.

You receive an approved hardware architecture and its requirements. Your job
is to produce structured PCB-readiness recommendations to hand off to a PCB
designer. You never fabricate electronics knowledge.

Analyse the architecture and produce:

1. LAYERSTACK: recommend 2-layer, 4-layer, or 6-layer with a clear reason.
   - 2-layer: simple digital, low frequency, no RF, no dense power
   - 4-layer: any RF, dense power distribution, high-speed signals, or isolation required
   - 6-layer: complex RF + high-speed + multi-power-domain simultaneously

2. NETCLASSES: group nets by electrical character.
   - Always include: PWR (power nets), Signal (general digital)
   - Add: HV (>50V), RF (RF/antenna), USB, CAN, RS485 if present in architecture
   - Calculate min_width_mm from current: I(A) * 0.6 for internal layers (rough rule)
   - clearance_mm: 0.2mm minimum; 0.5mm for >50V; 1.0mm for >150V

3. CONSTRAINTS: board-level design rules (these become the .kicad_dru file).
   - min_clearance_mm: driven by highest voltage net class
   - min_track_width_mm: driven by lowest current signal class
   - via_drill_mm: minimum 0.3mm (hand drill) or 0.2mm (laser/machine)
   - via_annular_ring_mm: minimum 0.1mm

4. FLOORPLAN: describe component group placement strategy in prose, then as
   an ASCII sketch. The sketch uses bracket notation: [GroupName].
   Keep the ASCII sketch under 8 lines.

5. PACKAGE HINTS: for each major component type in the architecture,
   recommend a package with a reason. Consider:
   - Manufacturing target (prototype hand-solder vs. pick-and-place)
   - Thermal requirements (QFN for heat-producing ICs)
   - Connector robustness (THT screw terminals for power entry only)
   - Pitch: 0402 for compact, 0603 for hand-solderable, 0805 for robust

Rules:
- Only reference nets and components visible in the architecture.
- Never invent components or blocks not in the architecture.
- Be specific: give actual mm values, not ranges.

Output a JSON object with exactly these keys:
- "layerstack": string ("2-layer" | "4-layer" | "6-layer")
- "layerstack_reason": string
- "netclasses": array of {name, min_width_mm, clearance_mm, nets}
- "constraints": {min_clearance_mm, min_track_width_mm, via_drill_mm, via_annular_ring_mm}
- "floorplan_text": string (prose)
- "floorplan_ascii": string (ASCII sketch, use \\n for newlines)
- "package_hints": array of {component_type, recommended_package, reason}
"""


class PcbEngineerAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements: Requirements,
        architecture: Architecture,
        arbitration: Arbitration,
        guidance: list[str] | None = None,
    ) -> PcbReadiness:
        user = (
            "Produce PCB-readiness recommendations for this approved architecture.\n\n"
            "REQUIREMENTS:\n"
            + requirements.model_dump_json(indent=2)
            + "\n\nARCHITECTURE:\n"
            + architecture.model_dump_json(indent=2)
            + "\n\nARBITRATION TODOs:\n"
            + "\n".join(arbitration.todo)
            + guidance_block(guidance)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        return PcbReadiness(
            layerstack=data["layerstack"],
            layerstack_reason=data["layerstack_reason"],
            netclasses=[NetClass(**nc) for nc in data.get("netclasses", [])],
            constraints=ConstraintSet(**data["constraints"]),
            floorplan_text=data.get("floorplan_text", ""),
            floorplan_ascii=data.get("floorplan_ascii", ""),
            package_hints=[PackageHint(**ph) for ph in data.get("package_hints", [])],
        )
```

- [ ] **Step 4: Run tests — all pass**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_engineer.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add app/agents/pcb_engineer.py tests/test_pcb_engineer.py
git commit -m "feat(pcb): add PcbEngineerAgent"
```

---

## Task 3: PCB Critic Agent

**Files:**
- Create: `app/agents/pcb_critic.py`
- Create: `tests/test_pcb_critic.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pcb_critic.py
from unittest.mock import MagicMock
from app.agents.pcb_critic import PcbCriticAgent
from app.models.schemas import (
    Architecture, Block, Requirements, ClarifyingQuestion,
    ConstraintSet, NetClass, PackageHint, PcbReadiness, PcbCritique,
)

def _pcb_readiness(via_drill=0.4) -> PcbReadiness:
    return PcbReadiness(
        layerstack="4-layer",
        layerstack_reason="RF module present",
        netclasses=[
            NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3.3V"]),
            NetClass(name="Signal", min_width_mm=0.2, clearance_mm=0.2, nets=["TX", "RX"]),
        ],
        constraints=ConstraintSet(
            min_clearance_mm=0.2,
            min_track_width_mm=0.2,
            via_drill_mm=via_drill,
            via_annular_ring_mm=0.15,
        ),
        floorplan_text="MCU central, RF in corner.",
        floorplan_ascii="[RF] [MCU]\n[PWR]",
        package_hints=[PackageHint(component_type="MCU", recommended_package="QFN-32", reason="thermal")],
    )

def _requirements() -> Requirements:
    return Requirements(
        requirements=["500mA peak current on PWR rail"],
        constraints=[],
        clarifications=[],
    )

def test_critic_finds_missing_blocks():
    client = MagicMock()
    client.chat_json.return_value = {
        "missing_blocks": ["Via drill 0.2mm too small for 500mA PWR net — increase to 0.4mm"],
        "warnings": [],
        "risks": [],
    }
    result = PcbCriticAgent().run(client, _requirements(), _pcb_readiness(via_drill=0.2))
    assert isinstance(result, PcbCritique)
    assert len(result.missing_blocks) == 1
    assert "0.2mm" in result.missing_blocks[0]

def test_critic_clean_pass():
    client = MagicMock()
    client.chat_json.return_value = {
        "missing_blocks": [],
        "warnings": [],
        "risks": [],
    }
    result = PcbCriticAgent().run(client, _requirements(), _pcb_readiness(via_drill=0.4))
    assert result.missing_blocks == []

def test_critic_guidance_forwarded():
    client = MagicMock()
    client.chat_json.return_value = {"missing_blocks": [], "warnings": [], "risks": []}
    PcbCriticAgent().run(
        client, _requirements(), _pcb_readiness(),
        guidance=["Target: hand-assembly prototype"]
    )
    assert "hand-assembly" in client.chat_json.call_args[0][1]
```

- [ ] **Step 2: Run — expect ImportError**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_critic.py -v
```
Expected: `ImportError: No module named 'app.agents.pcb_critic'`

- [ ] **Step 3: Add `PcbCritique` to schemas**

In `app/models/schemas.py`, add after `PcbReadiness`:

```python
class PcbCritique(BaseModel):
    missing_blocks: list[str] = []
    warnings: list[str] = []
    risks: list[str] = []
```

- [ ] **Step 4: Create `app/agents/pcb_critic.py`**

```python
"""PCB Critic Agent — role: Senior PCB Reviewer.

Reviews the PCB-readiness recommendations for engineering correctness.
Reports missing_blocks (must be fixed), warnings, and risks.
Never redesigns — only reports findings.
"""
from __future__ import annotations

from app.agents.base import ChatClient, guidance_block
from app.models.schemas import PcbCritique, PcbReadiness, Requirements

NAME = "Design Critic"   # same display name — appears in Society chat as the same Critic
ROLE = "Senior PCB Reviewer"

SYSTEM_PROMPT = """You are a senior PCB reviewer.

You receive PCB-readiness recommendations and the project requirements.
Your job is to find engineering errors, missing items, and risks. You never
fabricate electronics knowledge and you never redesign.

Review for:
- Via drill size vs. peak current on each net class (rule of thumb: >300mA needs via_drill >= 0.4mm)
- Track width vs. peak current (rule of thumb: 1A needs ~0.5mm on outer layer)
- Clearance vs. voltage (>50V needs >=0.5mm; >150V needs >=1.0mm)
- Missing critical net class (is GND in PWR netclass? is there a netclass for every interface?)
- Layerstack vs. design complexity (RF on 2-layer is a risk)
- Package hints: any component type from the architecture missing a hint?
- Floorplan: obvious conflicts (e.g. RF and switching power supply adjacent)?

Rules:
- Only flag problems supported by the data in front of you.
- missing_blocks = items that MUST be fixed before PCB layout starts.
- warnings = items worth noting but not blocking.
- risks = conditional problems (e.g. "if supply exceeds 50V, increase clearance").

Output a JSON object with exactly these keys:
- "missing_blocks": array of strings (each describing one problem + fix)
- "warnings": array of strings
- "risks": array of strings
"""


class PcbCriticAgent:
    name = NAME
    role = ROLE

    def run(
        self,
        client: ChatClient,
        requirements: Requirements,
        pcb_readiness: PcbReadiness,
        guidance: list[str] | None = None,
    ) -> PcbCritique:
        user = (
            "Review these PCB-readiness recommendations.\n\n"
            "REQUIREMENTS:\n"
            + requirements.model_dump_json(indent=2)
            + "\n\nPCB READINESS:\n"
            + pcb_readiness.model_dump_json(indent=2)
            + guidance_block(guidance)
        )
        data = client.chat_json(SYSTEM_PROMPT, user)
        return PcbCritique(
            missing_blocks=list(data.get("missing_blocks", [])),
            warnings=list(data.get("warnings", [])),
            risks=list(data.get("risks", [])),
        )
```

- [ ] **Step 5: Run tests — all pass**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_critic.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```
git add app/models/schemas.py app/agents/pcb_critic.py tests/test_pcb_critic.py
git commit -m "feat(pcb): add PcbCriticAgent + PcbCritique schema"
```

---

## Task 4: KiCad DRU generator

**Files:**
- Create: `app/generators/pcb_dru.py`
- Create: `tests/test_pcb_dru.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pcb_dru.py
from app.generators.pcb_dru import generate_dru
from app.models.schemas import ConstraintSet, NetClass

def _constraints() -> ConstraintSet:
    return ConstraintSet(
        min_clearance_mm=0.2,
        min_track_width_mm=0.2,
        via_drill_mm=0.4,
        via_annular_ring_mm=0.15,
    )

def _netclasses() -> list[NetClass]:
    return [
        NetClass(name="PWR", min_width_mm=0.5, clearance_mm=0.3, nets=["GND", "+3V3"]),
        NetClass(name="Signal", min_width_mm=0.2, clearance_mm=0.2, nets=["TX", "RX"]),
    ]

def test_dru_starts_with_version():
    dru = generate_dru(_constraints(), _netclasses())
    assert dru.startswith("(version 1)")

def test_dru_contains_clearance():
    dru = generate_dru(_constraints(), _netclasses())
    assert "0.2mm" in dru
    assert "clearance" in dru

def test_dru_contains_via_drill():
    dru = generate_dru(_constraints(), _netclasses())
    assert "0.4mm" in dru
    assert "via_drill" in dru

def test_dru_contains_netclass_names():
    dru = generate_dru(_constraints(), _netclasses())
    assert "PWR" in dru
    assert "Signal" in dru

def test_dru_contains_net_names():
    dru = generate_dru(_constraints(), _netclasses())
    assert "GND" in dru
    assert "+3V3" in dru

def test_dru_empty_netclasses():
    dru = generate_dru(_constraints(), [])
    assert "(version 1)" in dru
    assert "PWR" not in dru
```

- [ ] **Step 2: Run — expect ImportError**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_dru.py -v
```

- [ ] **Step 3: Create `app/generators/pcb_dru.py`**

```python
"""Deterministic KiCad 9 Design Rules (.kicad_dru) generator.

Builds the file content from structured ConstraintSet + NetClass data.
No LLM involved — pure Python template, syntactically guaranteed correct.
"""
from __future__ import annotations

from app.models.schemas import ConstraintSet, NetClass


def generate_dru(constraints: ConstraintSet, netclasses: list[NetClass]) -> str:
    lines: list[str] = ["(version 1)", ""]

    lines += [
        f'(rule "Default clearance"',
        f'   (constraint clearance (min {constraints.min_clearance_mm}mm)))',
        "",
        f'(rule "Minimum track width"',
        f'   (constraint track_width (min {constraints.min_track_width_mm}mm)))',
        "",
        f'(rule "Via drill"',
        f'   (constraint via_drill (min {constraints.via_drill_mm}mm)))',
        "",
        f'(rule "Via annular ring"',
        f'   (constraint annular_width (min {constraints.via_annular_ring_mm}mm)))',
    ]

    for nc in netclasses:
        lines += [
            "",
            f'(rule "Net class {nc.name}"',
            f'   (constraint clearance (min {nc.clearance_mm}mm))',
            f'   (constraint track_width (min {nc.min_width_mm}mm))',
        ]
        if nc.nets:
            net_expr = " ".join(f'"{n}"' for n in nc.nets)
            lines.append(f'   (condition "A.Net == {net_expr} || B.Net == {net_expr}")')
        lines.append(")")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests — all pass**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_pcb_dru.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```
git add app/generators/pcb_dru.py tests/test_pcb_dru.py
git commit -m "feat(pcb): deterministic KiCad 9 DRU generator"
```

---

## Task 5: Profiles — add PCB stage slots

**Files:**
- Modify: `app/services/profiles.py`

- [ ] **Step 1: Update `ROLES` and `PROFILES`**

In `app/services/profiles.py`, change:

```python
ROLES = ("requirements", "architecture", "critique", "arbitration")
```
to:
```python
ROLES = ("requirements", "architecture", "critique", "arbitration",
         "pcb_engineer", "pcb_critique")
```

Update the `"Senior Review Team"` profile models dict:

```python
"Senior Review Team": RunProfile(
    name="Senior Review Team",
    models={
        "requirements": "qwen-plus",
        "architecture": "qwen-plus",
        "critique": "qwen-max",
        "arbitration": "qwen-max",
        "pcb_engineer": "qwen-plus",
        "pcb_critique": "qwen-max",
    },
    rework=True,
    max_rounds=2,
),
```

The `uniform_profile()` helper already iterates `ROLES`, so all uniform profiles get the new slots automatically.

- [ ] **Step 2: Run full test suite — no regressions**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```
Expected: all existing tests still pass

- [ ] **Step 3: Commit**

```
git add app/services/profiles.py
git commit -m "feat(pcb): add pcb_engineer/pcb_critique slots to profiles"
```

---

## Task 6: Orchestrator — 5th stage

**Files:**
- Modify: `app/services/orchestrator.py`
- Create: `tests/test_orchestrator_pcb.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_orchestrator_pcb.py
from app.services.orchestrator import Orchestrator
from app.services.profiles import PROFILES

def test_mock_run_includes_pcb_readiness():
    orch = Orchestrator(profile=PROFILES["Senior Review Team"])
    result = orch.run("RS485 isolation board with STM32")
    assert result.pcb_readiness is not None
    assert result.pcb_readiness.layerstack in ("2-layer", "4-layer", "6-layer")

def test_mock_run_trace_has_pcb_steps():
    orch = Orchestrator(profile=PROFILES["Senior Review Team"])
    result = orch.run("RS485 isolation board with STM32")
    pcb_steps = [s for s in result.trace if s.agent == "PCB Engineer"]
    assert len(pcb_steps) >= 1

def test_mock_run_trace_has_pcb_critic_step():
    orch = Orchestrator(profile=PROFILES["Senior Review Team"])
    result = orch.run("RS485 isolation board with STM32")
    # PCB Critic uses same display name as Design Critic
    critic_steps = [s for s in result.trace if s.role == "Senior PCB Reviewer"]
    assert len(critic_steps) >= 1

def test_mock_rework_has_pcb_rework_round():
    orch = Orchestrator(profile=PROFILES["Senior Review Team"])
    result = orch.run("RS485 isolation board with STM32")
    pcb_steps = [s for s in result.trace if s.agent == "PCB Engineer"]
    # rework profile: at least round 1; may have round 2 if mock shows rework
    assert all(s.round >= 1 for s in pcb_steps)
```

- [ ] **Step 2: Run — expect failure (pcb_readiness is None)**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_orchestrator_pcb.py -v
```
Expected: `AssertionError: assert None is not None`

- [ ] **Step 3: Add PCB methods to `app/services/orchestrator.py`**

Add imports at top:
```python
from app.agents.pcb_engineer import PcbEngineerAgent
from app.agents.pcb_critic import PcbCriticAgent
from app.models.schemas import PcbCritique, PcbReadiness
```

Add helper methods to the `Orchestrator` class (after `_critic_step`):

```python
@staticmethod
def _pcb_eng_step(pcb: PcbReadiness, round_no: int, ms: int) -> TraceStep:
    return TraceStep(
        agent=PcbEngineerAgent.name,
        role=PcbEngineerAgent.role,
        status="ok",
        duration_ms=ms,
        round=round_no,
        summary=(
            f"Live Qwen: recommended {pcb.layerstack}, "
            f"{len(pcb.netclasses)} netclasses, "
            f"via drill {pcb.constraints.via_drill_mm}mm."
        ),
    )

@staticmethod
def _pcb_critic_step(critique: PcbCritique, round_no: int, ms: int) -> TraceStep:
    n = len(critique.missing_blocks)
    return TraceStep(
        agent=PcbCriticAgent.name,
        role=PcbCriticAgent.role,
        status="warning" if n else "ok",
        duration_ms=ms,
        round=round_no,
        summary=(
            f"Live Qwen (round {round_no}): flagged {n} PCB issues."
            if n else
            f"Live Qwen (round {round_no}): all PCB constraints valid."
        ),
    )

def _pcb_design_and_review(
    self,
    requirements: Requirements,
    architecture: Architecture,
    arbitration: Arbitration,
    guidance: list[str],
) -> tuple[PcbReadiness, list[TraceStep]]:
    steps: list[TraceStep] = []
    t = perf_counter()
    pcb = PcbEngineerAgent().run(
        self._client_for("pcb_engineer"), requirements, architecture, arbitration, guidance
    )
    steps.append(self._pcb_eng_step(pcb, 1, int((perf_counter() - t) * 1000)))

    t = perf_counter()
    critique = PcbCriticAgent().run(
        self._client_for("pcb_critique"), requirements, pcb, guidance
    )
    steps.append(self._pcb_critic_step(critique, 1, int((perf_counter() - t) * 1000)))

    round_no = 1
    while self.profile.rework and critique.missing_blocks and round_no < self.profile.max_rounds:
        round_no += 1
        rework_guidance = guidance + [
            "PREVIOUS PCB REVIEW FOUND THESE ISSUES — address all of them:",
            *critique.missing_blocks,
        ]
        t = perf_counter()
        pcb = PcbEngineerAgent().run(
            self._client_for("pcb_engineer"), requirements, architecture, arbitration, rework_guidance
        )
        steps.append(self._pcb_eng_step(pcb, round_no, int((perf_counter() - t) * 1000)))

        t = perf_counter()
        critique = PcbCriticAgent().run(
            self._client_for("pcb_critique"), requirements, pcb, rework_guidance
        )
        steps.append(self._pcb_critic_step(critique, round_no, int((perf_counter() - t) * 1000)))

    return pcb, steps
```

In the `run()` method, after the arbitration call and before the mock branch, add the PCB stage to the live path. Find the line that builds `RunResponse` and add `pcb_readiness=pcb_readiness` to it. The full live `run()` tail should look like:

```python
            pcb_readiness, pcb_steps = self._pcb_design_and_review(
                requirements, architecture, arbitration, guidance or []
            )

            # ... existing trace assembly ...
            trace = [
                # existing steps ...
                *pcb_steps,
            ]

            return RunResponse(
                # ... existing fields ...
                pcb_readiness=pcb_readiness,
                trace=trace,
                # ...
            )
```

(The exact line numbers will depend on the current file; follow the existing pattern for adding to `trace` and `RunResponse`.)

- [ ] **Step 4: Update mock path in `run()`**

The mock branch currently returns `mock_run()` or `mock_run_rework()`. Those functions will be updated in Task 7 to include `pcb_readiness`. No changes needed here yet — the tests will pass after Task 7.

- [ ] **Step 5: Run orchestrator PCB tests**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest tests/test_orchestrator_pcb.py -v
```
Expected: tests pass once Task 7 (mock) is complete. If they fail now with `pcb_readiness is None`, that is expected — proceed to Task 7.

- [ ] **Step 6: Commit**

```
git add app/services/orchestrator.py tests/test_orchestrator_pcb.py
git commit -m "feat(pcb): orchestrator _pcb_design_and_review + 5th stage"
```

---

## Task 7: Mock mode — PCB readiness fixtures

**Files:**
- Modify: `app/services/mock.py`

- [ ] **Step 1: Add fixed PcbReadiness to `mock_run()`**

In `app/services/mock.py`, add imports:

```python
from app.models.schemas import (
    # existing imports ...
    ConstraintSet, NetClass, PackageHint, PcbCritique, PcbReadiness,
)
```

Add a `_mock_pcb_readiness()` helper before `mock_run()`:

```python
def _mock_pcb_readiness() -> PcbReadiness:
    """Fixed illustrative PCB-readiness data for Mock Mode and the demo video."""
    return PcbReadiness(
        layerstack="4-layer",
        layerstack_reason=(
            "RS485 interface and isolated DC-DC converter require solid GND plane "
            "on inner layer 2 for EMI containment."
        ),
        netclasses=[
            NetClass(
                name="PWR",
                min_width_mm=0.5,
                clearance_mm=0.3,
                nets=["GND", "+3.3V", "+24V"],
            ),
            NetClass(
                name="Signal",
                min_width_mm=0.2,
                clearance_mm=0.2,
                nets=["RS485_A", "RS485_B", "SWDIO", "SWDCLK"],
            ),
            NetClass(
                name="ISO",
                min_width_mm=0.2,
                clearance_mm=0.5,
                nets=["ISO_GND", "ISO_PWR"],
            ),
        ],
        constraints=ConstraintSet(
            min_clearance_mm=0.2,
            min_track_width_mm=0.2,
            via_drill_mm=0.4,
            via_annular_ring_mm=0.15,
        ),
        floorplan_text=(
            "Left half: isolated RS485 section with DC-DC converter. "
            "Right half: MCU + debug header + status LEDs. "
            "Power entry (24V screw terminal) at top-left corner. "
            "Isolation barrier runs vertically through board centre."
        ),
        floorplan_ascii=(
            "+--------------------+--------------------+\n"
            "| [24V IN]  [DC-DC]  | [MCU]   [DEBUG]   |\n"
            "|                    |                    |\n"
            "| [RS485]  [ISOLAT.] | [LEDs]  [USB-C]   |\n"
            "+--------------------+--------------------+\n"
            "         ISO BARRIER ^\n"
        ),
        package_hints=[
            PackageHint(
                component_type="MCU (STM32)",
                recommended_package="LQFP-64 (10×10mm)",
                reason="Hand-solderable, good debugger access, no BGA risk for prototype",
            ),
            PackageHint(
                component_type="RS485 Transceiver",
                recommended_package="SOIC-8",
                reason="Widely available, hand-solderable, 1.27mm pitch",
            ),
            PackageHint(
                component_type="Resistors / Capacitors",
                recommended_package="0603",
                reason="Best balance of density and hand-solderability for prototype",
            ),
            PackageHint(
                component_type="Power entry connector",
                recommended_package="2-pin 5.08mm screw terminal (THT)",
                reason="THT screw terminals withstand mechanical stress from wire insertion",
            ),
            PackageHint(
                component_type="DC-DC converter",
                recommended_package="SIP or SMD module (e.g. Murata NME series)",
                reason="Isolated DC-DC module simplifies layout vs. discrete design",
            ),
        ],
    )
```

In `mock_run()`, add `pcb_readiness=_mock_pcb_readiness()` to the `RunResponse(...)` call.

Add two PCB TraceSteps to the `trace` list in `mock_run()`:

```python
        TraceStep(agent="PCB Engineer", role="PCB Layout Preparation Engineer", status="ok",
                  summary="4-layer recommended. 3 netclasses (PWR/Signal/ISO). Floorplan: isolation barrier centre."),
        TraceStep(agent="Design Critic", role="Senior PCB Reviewer", status="ok",
                  summary="All PCB constraints valid. Via drill 0.4mm sufficient for 500mA PWR net."),
```

- [ ] **Step 2: Update `mock_run_rework()` to show PCB rework**

In `mock_run_rework()`, add PCB rework rounds to the trace (after the Arbitration step):

```python
        # PCB rework: round 1 via-drill too small, round 2 corrected
        TraceStep(agent="PCB Engineer", role="PCB Layout Preparation Engineer",
                  status="ok", round=1,
                  summary="4-layer, 3 netclasses. Via drill 0.2mm (initial draft)."),
        TraceStep(agent="Design Critic", role="Senior PCB Reviewer",
                  status="warning", round=1,
                  summary="1 issue: via drill 0.2mm too small for 500mA PWR net — increase to 0.4mm."),
        TraceStep(agent="PCB Engineer", role="PCB Layout Preparation Engineer",
                  status="ok", round=2,
                  summary="Via drill corrected to 0.4mm. All constraints updated."),
        TraceStep(agent="Design Critic", role="Senior PCB Reviewer",
                  status="ok", round=2,
                  summary="All PCB constraints valid. Pack ready."),
```

Also add `pcb_readiness=_mock_pcb_readiness()` to `mock_run_rework()`'s returned `RunResponse`.

- [ ] **Step 3: Run full test suite**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```
Expected: all pass (target ~120+ tests)

- [ ] **Step 4: Commit**

```
git add app/services/mock.py
git commit -m "feat(pcb): mock PcbReadiness + PCB rework trace in mock_run"
```

---

## Task 8: ZIP integration — write PCB files

**Files:**
- Modify: `app/generators/kicad.py`

- [ ] **Step 1: Add PCB file generation to `generate_scaffold()`**

In `app/generators/kicad.py`, add import:
```python
from app.generators.pcb_dru import generate_dru
```

In `generate_scaffold()`, after the `agent_trace.json` write (around line 207), add:

```python
    # PCB-Readiness Pack (Feature D) — only when present in result
    if result.pcb_readiness is not None:
        pcb = result.pcb_readiness

        # 1. KiCad 9 design rules file
        dru_content = generate_dru(pcb.constraints, pcb.netclasses)
        (project_dir / "pcb_constraints.kicad_dru").write_text(dru_content, encoding="utf-8")

        # 2. Human-readable PCB readiness report
        nc_table = "\n".join(
            f"| {nc.name} | {nc.min_width_mm}mm | {nc.clearance_mm}mm | {', '.join(nc.nets) or '—'} |"
            for nc in pcb.netclasses
        )
        ph_table = "\n".join(
            f"| {ph.component_type} | {ph.recommended_package} | {ph.reason} |"
            for ph in pcb.package_hints
        )
        report = f"""# PCB Readiness Report

Generated by AI Circuit Architect

## Layerstack

**Recommendation:** {pcb.layerstack}

{pcb.layerstack_reason}

## Net Classes

| Class | Min Width | Clearance | Nets |
|---|---|---|---|
{nc_table}

## Design Constraints

| Parameter | Value |
|---|---|
| Minimum clearance | {pcb.constraints.min_clearance_mm}mm |
| Minimum track width | {pcb.constraints.min_track_width_mm}mm |
| Via drill | {pcb.constraints.via_drill_mm}mm |
| Via annular ring | {pcb.constraints.via_annular_ring_mm}mm |

## Floorplan

{pcb.floorplan_text}

```
{pcb.floorplan_ascii}
```

## Package & Manufacturing Hints

| Component Type | Recommended Package | Reason |
|---|---|---|
{ph_table}

## KiCad Files

- `pcb_constraints.kicad_dru` — import via PCB Editor → File → Import → Design Rules
"""
        (project_dir / "PCB_READINESS.md").write_text(report, encoding="utf-8")
```

- [ ] **Step 2: Verify files appear in ZIP**

```python
# Quick smoke test — run in Python shell
import os, zipfile, tempfile
os.environ.setdefault("QWEN_API_KEY", "")
from app.services.mock import mock_run
from app.generators.kicad import generate_scaffold
from app.services.packaging import create_project_zip
import tempfile, pathlib

with tempfile.TemporaryDirectory() as tmp:
    result = mock_run("RS485 board")
    project_dir = generate_scaffold("test_project", "RS485 board", result)
    zip_path = create_project_zip(project_dir)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        print(names)
        assert any("PCB_READINESS.md" in n for n in names), "Missing PCB_READINESS.md"
        assert any("pcb_constraints.kicad_dru" in n for n in names), "Missing .kicad_dru"
        print("OK — both PCB files present in ZIP")
```

Run: `QWEN_API_KEY="" .venv/Scripts/python.exe -c "<paste above>"`

- [ ] **Step 3: Run full test suite**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```
Expected: all pass

- [ ] **Step 4: Commit**

```
git add app/generators/kicad.py
git commit -m "feat(pcb): write PCB_READINESS.md + pcb_constraints.kicad_dru to ZIP"
```

---

## Task 9: Stepwise — PCB Engineer as 5th stage

**Files:**
- Modify: `app/services/stepwise.py`

- [ ] **Step 1: Extend `_STAGE_ORDER`**

In `app/services/stepwise.py`, change:

```python
_STAGE_ORDER = ["requirements", "architecture", "critique", "arbitration"]
```
to:
```python
_STAGE_ORDER = ["requirements", "architecture", "critique", "arbitration", "pcb_engineer"]
```

- [ ] **Step 2: Add imports**

```python
from app.agents.pcb_engineer import PcbEngineerAgent
from app.agents.pcb_critic import PcbCriticAgent
from app.models.schemas import PcbCritique, PcbReadiness
```

- [ ] **Step 3: Add mock step slice for `pcb_engineer`**

In `_mock_step()`, add a case for `"pcb_engineer"`:

```python
    if stage == "pcb_engineer":
        mock = mock_run("")
        return StepResponse(
            stage=stage,
            mode="mock",
            pcb_readiness=mock.pcb_readiness,
            trace_step=TraceStep(
                agent="PCB Engineer",
                role="PCB Layout Preparation Engineer",
                status="ok",
                summary="4-layer recommended. 3 netclasses. Floorplan: isolation barrier centre.",
            ),
        )
```

- [ ] **Step 4: Add live step for `pcb_engineer` in `run_stage()`**

In the live-stage dispatch section of `run_stage()` (the big `if stage == ...` chain), add:

```python
    elif stage == "pcb_engineer":
        assert acc.requirements and acc.architecture and acc.arbitration, \
            "pcb_engineer requires requirements, architecture, and arbitration"
        t = perf_counter()
        pcb = PcbEngineerAgent().run(
            client, acc.requirements, acc.architecture, acc.arbitration, guidance
        )
        # Single-pass in stepwise (no rework loop — user can re-run the stage)
        ms = int((perf_counter() - t) * 1000)
        return StepResponse(
            stage=stage,
            mode="qwen",
            pcb_readiness=pcb,
            trace_step=TraceStep(
                agent=PcbEngineerAgent.name,
                role=PcbEngineerAgent.role,
                status="ok",
                duration_ms=ms,
                summary=(
                    f"Live Qwen: {pcb.layerstack}, "
                    f"{len(pcb.netclasses)} netclasses, "
                    f"via drill {pcb.constraints.via_drill_mm}mm."
                ),
            ),
        )
```

- [ ] **Step 5: Add `pcb_readiness` field to `StepResponse` schema**

In `app/models/schemas.py`, find `StepResponse` and add:

```python
    pcb_readiness: PcbReadiness | None = None
```

- [ ] **Step 6: Run full test suite**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```
git add app/services/stepwise.py app/models/schemas.py
git commit -m "feat(pcb): add pcb_engineer as 5th stepwise stage"
```

---

## Task 10: UI — Society chat + PCB stage card

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Add PCB Engineer avatar colour**

Find the `avatarColor(agent)` function (around line 782). Add to the `map` object:

```js
'PCB Engineer': '#0d9488',
```

- [ ] **Step 2: Add phase divider in Society chat**

In both Society chat `<div>` blocks (one in auto-run result section around line 517, one in stepwise section around line 399), add a phase divider between Arbitration and PCB Engineer bubbles. Replace the existing `<template x-for>` loop with one that injects a divider when the agent switches to PCB phase:

```html
<template x-for="(s, i) in societyBubbles" :key="i">
  <div>
    <div x-show="s.agent==='PCB Engineer' && (i===0 || societyBubbles[i-1].agent!=='PCB Engineer')"
         style="display:flex;align-items:center;gap:8px;margin:8px 0">
      <div style="flex:1;height:1px;background:var(--line)"></div>
      <span style="font-size:11px;color:var(--muted)">PCB-Readiness Phase</span>
      <div style="flex:1;height:1px;background:var(--line)"></div>
    </div>
    <div :class="s.agent==='Design Critic' ? 'bubble-right' : 'bubble-left'">
      <!-- existing bubble content unchanged -->
      <div class="bubble-avatar" :style="avatarColor(s.agent)"
           x-text="s.agent.slice(0,3).toUpperCase()"></div>
      <div class="bubble-body">
        <div class="bubble-meta">
          <span x-text="s.agent"></span>
          <span x-show="s.round > 1" x-text="'· Round ' + s.round"></span>
          <span x-show="s.status==='warning'" class="chip-rework">↺ Rework</span>
        </div>
        <div class="bubble-text"
             x-text="s.summary.slice(0,120) + (s.summary.length > 120 ? '…' : '')"></div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Verify in browser (Mock Mode)**

Start the mock server:
```
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8011 --env-file /dev/null
```
Open http://localhost:8011, run the pipeline, open the "💬 Agent Society" tab. Confirm:
- PCB Engineer appears in teal
- Design Critic (PCB Reviewer) appears in red on the right
- Phase divider "PCB-Readiness Phase" separates Arbitration from PCB steps

- [ ] **Step 4: Run full test suite**

```
QWEN_API_KEY="" .venv/Scripts/python.exe -m pytest -q
```
Expected: all pass (target ≥ 125 tests)

- [ ] **Step 5: Commit**

```
git add app/static/index.html
git commit -m "feat(pcb): Society chat phase divider + PCB Engineer avatar colour"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| PcbReadiness schema (layerstack, netclasses, constraints, floorplan, package_hints) | Task 1 |
| PCB Engineer Agent + prompt | Task 2 |
| PCB Critic Agent + rework loop | Task 3, Task 6 |
| .kicad_dru deterministic generator (KiCad 9) | Task 4 |
| Profile slots (pcb_engineer/pcb_critique per profile) | Task 5 |
| Orchestrator 5th stage with rework loop | Task 6 |
| Mock mode with fixed PcbReadiness + rework trace | Task 7 |
| ZIP: PCB_READINESS.md + pcb_constraints.kicad_dru | Task 8 |
| Stepwise: pcb_engineer as 5th STAGE | Task 9 |
| Society chat: PCB avatar + phase divider | Task 10 |

All spec requirements covered. No gaps found.
