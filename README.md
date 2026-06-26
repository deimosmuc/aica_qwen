# AI Circuit Architect

> Multi-agent hardware architecture assistant for KiCad — the "Cursor for Hardware Architecture".

A team of AI agents turns natural-language hardware requirements into a structured
KiCad **project scaffold** (architecture, hierarchical sheets, placeholder components,
engineering TODOs, assumptions, validation). It deliberately does **not** produce a
finished schematic — the human engineer stays in control and approves the architecture
before anything is generated.

Built for the **Qwen Cloud Global AI Hackathon 2026** — track: *Agent Society*.

## Status

Milestone 1 — scaffold: FastAPI backend, Mock Mode, and a web UI showing the full
flow (requirements → agent collaboration → human approval → download). The real
Qwen-backed agents and KiCad generation arrive in later milestones.

## Quick start (local)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 — with no `QWEN_API_KEY` set, the app runs in **Mock Mode**
and the full demo works with prepared example data.

## Run with Docker

```bash
docker compose up --build
```

## Tests

```bash
pytest
```

## Mock Mode

If `QWEN_API_KEY` is empty or missing, the app automatically switches to Mock Mode so
the demo always works. Set the key in a `.env` file (see `.env.example`) to enable the
real Qwen agents.

## Architecture

```
User → Orchestrator → Requirements → Architect → Critic → Arbitration → (human approval) → KiCad scaffold → Validation → ZIP
```

Agents never talk to each other directly. Only the orchestrator owns state; every agent
is stateless and exchanges structured JSON. This keeps the system deterministic and easy
to debug.

## License

MIT — see [LICENSE](LICENSE).
